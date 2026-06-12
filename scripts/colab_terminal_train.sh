#!/usr/bin/env bash
# One-paste launcher for training in the Colab Terminal (Colab Pro/Pro+).
#
# Usage, inside a Colab Terminal:
#   bash <(curl -fsSL https://raw.githubusercontent.com/sulav1234567/nepse/main/scripts/colab_terminal_train.sh)
# or, if the repo is already cloned:
#   bash /content/nepse-main/scripts/colab_terminal_train.sh [extra colab_continuous_train.py args]
#
# Prerequisite: run the "Terminal mode" cell in notebooks/nepse_colab_training.ipynb
# first — it mounts Google Drive and stashes the GitHub token for this script.
# (Drive mounting and Colab Secrets only work from a notebook cell, not the terminal.)
#
# Training runs under nohup, so it survives closing the terminal pane. The log
# streams to the terminal and also persists in Drive.

set -euo pipefail

REPO_DIR=/content/nepse-main
DRIVE_ROOT=/content/drive/MyDrive/nepse-continuous-training
TOKEN_FILE=/content/.github_token

echo "== GPU =="
if ! nvidia-smi --query-gpu=name,memory.total --format=csv,noheader; then
    echo "ERROR: no GPU attached. Runtime > Change runtime type > A100 GPU, then reconnect." >&2
    exit 1
fi
GPU_NAME=$(nvidia-smi --query-gpu=name --format=csv,noheader | head -1)
case "$GPU_NAME" in
    *A100*) ;;
    *) echo "NOTE: GPU is '$GPU_NAME', not an A100. With Pro+, pick Runtime > Change runtime type > A100 GPU for the fastest run." ;;
esac

echo "== Google Drive =="
if [ ! -d /content/drive/MyDrive ]; then
    echo "ERROR: Drive is not mounted. Run the 'Terminal mode' cell in the notebook first:" >&2
    echo "  from google.colab import drive; drive.mount('/content/drive')" >&2
    exit 1
fi
mkdir -p "$DRIVE_ROOT"
echo "Artifacts will be saved under $DRIVE_ROOT"

echo "== GitHub token =="
if [ -z "${GITHUB_TOKEN:-}" ] && [ -f "$TOKEN_FILE" ]; then
    GITHUB_TOKEN=$(cat "$TOKEN_FILE")
fi
if [ -z "${GITHUB_TOKEN:-}" ]; then
    read -rs -p "Paste your GitHub fine-grained token (input hidden): " GITHUB_TOKEN
    echo
fi
if [ -z "$GITHUB_TOKEN" ]; then
    echo "ERROR: no GitHub token. Add it via the notebook's 'Terminal mode' cell or paste it when prompted." >&2
    exit 1
fi
export GITHUB_TOKEN

echo "== Repo =="
if [ -d "$REPO_DIR/.git" ]; then
    git -C "$REPO_DIR" pull --ff-only \
        "https://x-access-token:${GITHUB_TOKEN}@github.com/sulav1234567/nepse.git" main
else
    git clone --depth 1 "https://x-access-token:${GITHUB_TOKEN}@github.com/sulav1234567/nepse.git" "$REPO_DIR"
    git -C "$REPO_DIR" remote set-url origin https://github.com/sulav1234567/nepse.git
fi
git -C "$REPO_DIR" log -1 --oneline

echo "== Dependencies =="
# The runtime's preinstalled CUDA torch is kept as-is (never pip install -U torch here).
pip install -q -r "$REPO_DIR/backend/requirements.txt"
pip install -q -U xgboost lightgbm stable-baselines3 gymnasium mlflow

echo "== Training =="
LOG_FILE="$DRIVE_ROOT/terminal_train_$(date -u +%Y%m%dT%H%M%SZ).log"
cd "$REPO_DIR"
# A100-tuned defaults: larger sequence batches than the T4 settings. Extra
# script arguments are appended last, so they override these defaults.
nohup python scripts/colab_continuous_train.py \
    --device cuda \
    --git-pull \
    --profile advanced \
    --max-cycles 0 \
    --market-news-pages 20 \
    --market-article-body-limit 200 \
    --internet-refresh-cycles 6 \
    --train-interval-minutes 60 \
    --max-training-rows 250000 \
    --lstm-epochs 50 \
    --tft-epochs 50 \
    --sequence-batch-size 512 \
    --ppo-timesteps 100000 \
    "$@" \
    >>"$LOG_FILE" 2>&1 &
TRAIN_PID=$!
echo "Training started (pid $TRAIN_PID). It keeps running if you close this terminal."
echo "Log: $LOG_FILE"
echo "Stop it with: kill $TRAIN_PID"
echo "--- streaming log (Ctrl-C stops the stream, NOT the training) ---"
tail -f "$LOG_FILE"
