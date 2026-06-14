"""
Continuous Colab trainer for the private NEPSE repo.

Run this from the repository root after cloning in Google Colab. It refreshes
public data, ingests the latest live snapshot, trains the autonomous ensemble,
and saves artifacts to Google Drive.
"""

from __future__ import annotations

import argparse
import base64
import json
import logging
import os
import shutil
import subprocess
import sys
import time
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Cosmetic, irreducible warnings that flood Colab logs without indicating a problem:
# LightGBM is fed numpy arrays at predict time (it was fit with column names) — the
# values are identical; sklearn just nags about the missing names.
warnings.filterwarnings("ignore", message="X does not have valid feature names")


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


LOGGER = logging.getLogger("nepse.colab.continuous-train")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run(command: list[str], *, cwd: Path = REPO_ROOT, env: dict[str, str] | None = None) -> None:
    LOGGER.info("Running: %s", " ".join(command))
    subprocess.run(command, cwd=str(cwd), env=env, check=True)


def _git_pull_private_repo(github_token: str | None) -> None:
    if not github_token:
        LOGGER.info("GITHUB_TOKEN not set; skipping git pull.")
        return
    auth = base64.b64encode(f"x-access-token:{github_token}".encode("utf-8")).decode("ascii")
    _run(
        [
            "git",
            "-c",
            f"http.https://github.com/.extraheader=AUTHORIZATION: basic {auth}",
            "pull",
            "--ff-only",
            "origin",
            "main",
        ]
    )


def _mount_drive() -> None:
    try:
        from IPython import get_ipython
        from google.colab import drive  # type: ignore
    except Exception:
        LOGGER.info("Not running inside Colab; skipping Drive mount.")
        return
    if get_ipython() is None:
        LOGGER.warning(
            "Drive mount requested from a non-notebook Python subprocess. "
            "Run `from google.colab import drive; drive.mount('/content/drive')` "
            "in a Colab Python cell, then rerun this script without --mount-drive."
        )
        return
    drive.mount("/content/drive", force_remount=False)


def _configure_environment(args: argparse.Namespace) -> Path:
    drive_root = Path(args.drive_root).expanduser()
    artifact_dir = drive_root / "model_artifacts"
    db_path = drive_root / "autonomous_nepse.db"
    mlruns_dir = drive_root / "mlruns"
    backup_dir = drive_root / "artifact_backups"

    for path in (artifact_dir, mlruns_dir, backup_dir):
        path.mkdir(parents=True, exist_ok=True)

    os.environ.setdefault("MODEL_ARTIFACT_DIR", str(artifact_dir))
    os.environ.setdefault("DATABASE_URL", f"sqlite:///{db_path}")
    os.environ.setdefault("MLFLOW_TRACKING_URI", f"file:{mlruns_dir}")

    if args.device:
        os.environ["NEPSE_DEVICE"] = args.device
        if args.device in {"tpu", "xla"}:
            os.environ.setdefault("PJRT_DEVICE", "TPU")

    os.environ.setdefault("NEPSE_TRAINING_MAX_ROWS", str(args.max_training_rows))
    os.environ.setdefault("NEPSE_LSTM_EPOCHS", str(args.lstm_epochs))
    os.environ.setdefault("NEPSE_TFT_EPOCHS", str(args.tft_epochs))
    os.environ.setdefault("NEPSE_SEQUENCE_BATCH_SIZE", str(args.sequence_batch_size))
    os.environ.setdefault("NEPSE_INFERENCE_BATCH_SIZE", str(args.inference_batch_size))
    os.environ.setdefault("NEPSE_LSTM_HIDDEN_SIZE", str(args.lstm_hidden_size))
    os.environ.setdefault("NEPSE_TFT_HIDDEN_SIZE", str(args.tft_hidden_size))
    os.environ.setdefault("NEPSE_PPO_TIMESTEPS", str(args.ppo_timesteps))
    os.environ.setdefault("NEPSE_PPO_N_STEPS", str(args.ppo_n_steps))
    os.environ.setdefault("NEPSE_PPO_BATCH_SIZE", str(args.ppo_batch_size))
    # Reduce CUDA fragmentation so large batches don't trip an avoidable OOM that
    # would kill the run. Stay just under the limit rather than over it.
    os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

    return backup_dir


def _log_gpu() -> None:
    try:
        import torch

        LOGGER.info("PyTorch: %s", torch.__version__)
        LOGGER.info("CUDA available: %s", torch.cuda.is_available())
        if torch.cuda.is_available():
            LOGGER.info("CUDA device: %s", torch.cuda.get_device_name(0))
    except Exception as exc:
        LOGGER.warning("Unable to inspect PyTorch/CUDA: %s", exc)
    if os.environ.get("NEPSE_DEVICE", "").lower() in {"tpu", "xla"}:
        try:
            import torch_xla.core.xla_model as xm

            LOGGER.info("XLA/TPU device: %s", xm.xla_device())
        except Exception as exc:
            LOGGER.warning("NEPSE_DEVICE=tpu set but torch_xla unavailable: %s", exc)


def _copy_versioned_artifact(artifact_path: Path, backup_dir: Path, model_version: str) -> Path | None:
    if not artifact_path.exists():
        return None
    safe_version = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in model_version)
    backup_path = backup_dir / f"autonomous_model_suite_{safe_version}.joblib"
    shutil.copy2(artifact_path, backup_path)
    latest_path = backup_dir / "autonomous_model_suite_latest.joblib"
    shutil.copy2(artifact_path, latest_path)
    return latest_path


def _write_state(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def _train_once(args: argparse.Namespace, cycle: int, backup_dir: Path) -> dict[str, Any]:
    from backend.autonomous.service import get_research_platform

    platform = get_research_platform()
    platform.initialize()

    should_refresh_internet_data = cycle == 1 or (
        args.internet_refresh_cycles > 0 and cycle % args.internet_refresh_cycles == 0
    )

    dataset_summary: dict[str, Any] = {"skipped": True}
    if should_refresh_internet_data:
        dataset_summary = platform.build_internet_training_data(
            profile=args.profile,
            symbol_limit=args.symbol_limit,
            refresh=args.full_refresh,
            market_news_pages=args.market_news_pages,
            market_article_body_limit=args.market_article_body_limit,
        )

    ingestion_summary = platform.run_ingestion_cycle()
    training_summary = platform.train_models(force=True)
    artifact_path = Path(platform.model_suite.artifact_path)
    backup_path = _copy_versioned_artifact(
        artifact_path,
        backup_dir,
        str(training_summary.get("model_version", "unknown")),
    )

    return {
        "cycle": cycle,
        "finished_at": _utc_now(),
        "dataset": dataset_summary,
        "ingestion": ingestion_summary,
        "training": training_summary,
        "artifact_path": str(artifact_path),
        "latest_backup_path": None if backup_path is None else str(backup_path),
        "env": {
            "MODEL_ARTIFACT_DIR": os.environ.get("MODEL_ARTIFACT_DIR"),
            "DATABASE_URL": os.environ.get("DATABASE_URL"),
            "NEPSE_TRAINING_MAX_ROWS": os.environ.get("NEPSE_TRAINING_MAX_ROWS"),
            "NEPSE_LSTM_EPOCHS": os.environ.get("NEPSE_LSTM_EPOCHS"),
            "NEPSE_TFT_EPOCHS": os.environ.get("NEPSE_TFT_EPOCHS"),
            "NEPSE_PPO_TIMESTEPS": os.environ.get("NEPSE_PPO_TIMESTEPS"),
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Continuously train the NEPSE autonomous model suite on Colab.")
    parser.add_argument("--drive-root", default="/content/drive/MyDrive/nepse-continuous-training")
    parser.add_argument("--mount-drive", action="store_true", help="Mount Google Drive before training.")
    parser.add_argument(
        "--device",
        choices=["cpu", "cuda", "tpu"],
        default=None,
        help="Compute device for the PyTorch sequence models. 'tpu' uses torch_xla (Colab TPU runtimes).",
    )
    parser.add_argument("--profile", choices=["high_level", "advanced"], default="advanced")
    parser.add_argument("--symbol-limit", type=int, default=None)
    parser.add_argument("--market-news-pages", type=int, default=20)
    parser.add_argument("--market-article-body-limit", type=int, default=200)
    parser.add_argument("--internet-refresh-cycles", type=int, default=6)
    parser.add_argument("--full-refresh", action="store_true", help="Overwrite internet data files during refresh.")
    parser.add_argument("--train-interval-minutes", type=float, default=60.0)
    parser.add_argument("--max-cycles", type=int, default=0, help="0 means run forever.")
    parser.add_argument("--git-pull", action="store_true", help="Pull latest code from the private GitHub repo each cycle.")
    # A100 80GB / 167GB RAM defaults — the previous values left the GPU ~2% used.
    # More data + bigger batches + larger sequence models exploit the hardware.
    parser.add_argument("--max-training-rows", type=int, default=600_000)
    parser.add_argument("--lstm-epochs", type=int, default=60)
    parser.add_argument("--tft-epochs", type=int, default=60)
    parser.add_argument("--sequence-batch-size", type=int, default=1024)
    # 2048 keeps the backtest forward pass safely under 80GB with hidden=256.
    # (4096 risks the OOM that was previously hit at 1024/hidden=128 on a 40GB card.)
    parser.add_argument("--inference-batch-size", type=int, default=2048)
    parser.add_argument("--lstm-hidden-size", type=int, default=256)
    parser.add_argument("--tft-hidden-size", type=int, default=256)
    parser.add_argument("--ppo-timesteps", type=int, default=300_000)
    parser.add_argument(
        "--auto-disconnect",
        action="store_true",
        help="Release the Colab runtime when training finishes (saves compute units).",
    )
    parser.add_argument("--ppo-n-steps", type=int, default=256)
    parser.add_argument("--ppo-batch-size", type=int, default=256)
    return parser.parse_args()


def _disconnect_runtime(grace_seconds: float = 10.0) -> None:
    """Release the Colab runtime when training is done, to stop burning compute units.

    Waits a few seconds first so the artifact finishes syncing to Drive, then tries
    the official Colab API (works from a notebook), falling back to ending the VM
    session (works from the terminal).
    """
    LOGGER.info("Training complete. Auto-disconnecting in %.0fs (letting Drive finish syncing)…", grace_seconds)
    time.sleep(grace_seconds)
    try:
        from google.colab import runtime  # type: ignore

        runtime.unassign()
        LOGGER.info("✓ Colab runtime released — compute units stopped.")
        return
    except Exception as exc:
        LOGGER.warning("Colab runtime API unavailable (%s); terminating the VM session instead.", exc)
    # Terminal/subprocess fallback: ending the session frees the runtime.
    os.system("kill -9 -1 >/dev/null 2>&1")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )
    args = parse_args()
    if args.mount_drive:
        _mount_drive()
    backup_dir = _configure_environment(args)
    state_path = Path(args.drive_root).expanduser() / "training_state.json"
    github_token = os.getenv("GITHUB_TOKEN")

    _log_gpu()
    cycle = 0
    while args.max_cycles <= 0 or cycle < args.max_cycles:
        cycle += 1
        started_at = _utc_now()
        try:
            if args.git_pull:
                _git_pull_private_repo(github_token)
            result = _train_once(args, cycle, backup_dir)
            result["started_at"] = started_at
            result["status"] = "ok"
            LOGGER.info("Cycle %s complete: %s", cycle, json.dumps(result["training"], default=str))
        except Exception as exc:
            LOGGER.exception("Cycle %s failed.", cycle)
            result = {
                "cycle": cycle,
                "started_at": started_at,
                "finished_at": _utc_now(),
                "status": "failed",
                "error": repr(exc),
            }
        _write_state(state_path, result)

        if args.max_cycles > 0 and cycle >= args.max_cycles:
            break
        sleep_seconds = max(60.0, args.train_interval_minutes * 60.0)
        LOGGER.info("Sleeping %.0f seconds before next cycle.", sleep_seconds)
        time.sleep(sleep_seconds)

    if args.auto_disconnect:
        _disconnect_runtime()


if __name__ == "__main__":
    main()
