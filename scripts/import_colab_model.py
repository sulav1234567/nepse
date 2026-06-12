"""
Import a Colab-trained model artifact into the local app.

After training on Google Colab, download the artifact from Google Drive
(`nepse-continuous-training/artifact_backups/autonomous_model_suite_latest.joblib`)
and run:

    python scripts/import_colab_model.py ~/Downloads/autonomous_model_suite_latest.joblib

With no argument it looks for the newest autonomous_model_suite*.joblib in
~/Downloads. The current local artifact is backed up before being replaced,
and the imported artifact is loaded once to verify it works on this machine.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

LOCAL_ARTIFACT = REPO_ROOT / "backend" / "model_artifacts" / "autonomous_model_suite.joblib"


def _find_downloaded_artifact() -> Path | None:
    downloads = Path.home() / "Downloads"
    candidates = sorted(
        downloads.glob("autonomous_model_suite*.joblib"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return candidates[0] if candidates else None


def _verify_artifact(path: Path) -> None:
    import os

    os.chdir(REPO_ROOT)
    import joblib

    suite = joblib.load(path)
    version = getattr(suite, "model_version", "unknown")
    trained_at = getattr(suite, "last_trained_at", None)
    metrics = getattr(suite, "metrics", {})
    print(f"Verified artifact loads OK.")
    print(f"  model_version:   {version}")
    print(f"  last_trained_at: {trained_at}")
    if metrics:
        print("  metrics:")
        for key, value in sorted(metrics.items()):
            print(f"    {key}: {value}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Install a Colab-trained model artifact locally.")
    parser.add_argument(
        "artifact",
        nargs="?",
        help="Path to the downloaded .joblib artifact (default: newest match in ~/Downloads).",
    )
    parser.add_argument("--no-verify", action="store_true", help="Skip loading the artifact to verify it.")
    args = parser.parse_args()

    source = Path(args.artifact).expanduser() if args.artifact else _find_downloaded_artifact()
    if source is None:
        sys.exit(
            "No artifact found in ~/Downloads. Download autonomous_model_suite_latest.joblib "
            "from Google Drive first, or pass the path explicitly."
        )
    if not source.exists():
        sys.exit(f"Artifact not found: {source}")
    if source.resolve() == LOCAL_ARTIFACT.resolve():
        sys.exit("Source is already the installed artifact; nothing to do.")

    if not args.no_verify:
        print(f"Verifying {source} ...")
        _verify_artifact(source)

    LOCAL_ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    if LOCAL_ARTIFACT.exists():
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = LOCAL_ARTIFACT.with_name(f"autonomous_model_suite.backup_{stamp}.joblib")
        shutil.copy2(LOCAL_ARTIFACT, backup)
        print(f"Backed up current model to {backup}")

    shutil.copy2(source, LOCAL_ARTIFACT)
    print(f"Installed {source} -> {LOCAL_ARTIFACT}")
    print("Restart the backend so it loads the new model.")


if __name__ == "__main__":
    main()
