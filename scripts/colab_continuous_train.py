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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


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
        from google.colab import drive  # type: ignore
    except Exception:
        LOGGER.info("Not running inside Colab; skipping Drive mount.")
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

    os.environ.setdefault("NEPSE_TRAINING_MAX_ROWS", str(args.max_training_rows))
    os.environ.setdefault("NEPSE_LSTM_EPOCHS", str(args.lstm_epochs))
    os.environ.setdefault("NEPSE_TFT_EPOCHS", str(args.tft_epochs))
    os.environ.setdefault("NEPSE_SEQUENCE_BATCH_SIZE", str(args.sequence_batch_size))
    os.environ.setdefault("NEPSE_PPO_TIMESTEPS", str(args.ppo_timesteps))
    os.environ.setdefault("NEPSE_PPO_N_STEPS", str(args.ppo_n_steps))
    os.environ.setdefault("NEPSE_PPO_BATCH_SIZE", str(args.ppo_batch_size))

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
    parser.add_argument("--profile", choices=["high_level", "advanced"], default="advanced")
    parser.add_argument("--symbol-limit", type=int, default=None)
    parser.add_argument("--market-news-pages", type=int, default=20)
    parser.add_argument("--market-article-body-limit", type=int, default=200)
    parser.add_argument("--internet-refresh-cycles", type=int, default=6)
    parser.add_argument("--full-refresh", action="store_true", help="Overwrite internet data files during refresh.")
    parser.add_argument("--train-interval-minutes", type=float, default=60.0)
    parser.add_argument("--max-cycles", type=int, default=0, help="0 means run forever.")
    parser.add_argument("--git-pull", action="store_true", help="Pull latest code from the private GitHub repo each cycle.")
    parser.add_argument("--max-training-rows", type=int, default=250_000)
    parser.add_argument("--lstm-epochs", type=int, default=50)
    parser.add_argument("--tft-epochs", type=int, default=50)
    parser.add_argument("--sequence-batch-size", type=int, default=256)
    parser.add_argument("--ppo-timesteps", type=int, default=100_000)
    parser.add_argument("--ppo-n-steps", type=int, default=256)
    parser.add_argument("--ppo-batch-size", type=int, default=256)
    return parser.parse_args()


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


if __name__ == "__main__":
    main()
