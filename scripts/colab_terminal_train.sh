#!/usr/bin/env bash
#
# Colab TERMINAL launcher for NEPSE autonomous model training (A100-tuned).
#
# The Colab *terminal* (Pro/Pro+ only) is a plain shell — it can NOT mount Google
# Drive and can NOT read Colab Secrets. So two things must be handled before this
# script will work:
#   1. Mount Drive from a NOTEBOOK CELL first:
#        from google.colab import drive; drive.mount('/content/drive')
#   2. Export your GitHub token in the terminal (Secrets aren't visible to the shell):
#        export GITHUB_TOKEN=ghp_xxx
#
# Then, in the terminal:
#        bash <(curl -s https://raw.githubusercontent.com/sulav1234567/nepse/main/scripts/colab_terminal_train.sh)
#   or, if the repo is already cloned:
#        bash /content/nepse-main/scripts/colab_terminal_train.sh
#
# Env overrides: REPO_DIR, DRIVE_ROOT, MAX_CYCLES, SYMBOL_LIMIT, SMOKE=1
set -euo pipefail

REPO_URL="https://github.com/sulav1234567/nepse.git"
REPO_DIR="${REPO_DIR:-/content/nepse-main}"
DRIVE_ROOT="${DRIVE_ROOT:-/content/drive/MyDrive/nepse-continuous-training}"
MAX_CYCLES="${MAX_CYCLES:-1}"          # 1 = one thorough run; 0 = continuous loop
SYMBOL_LIMIT="${SYMBOL_LIMIT:-}"       # empty = all stocks

echo "==> NEPSE Colab terminal trainer"

# --- 0. Pre-flight checks -----------------------------------------------------
if [ -z "${GITHUB_TOKEN:-}" ]; then
  echo "ERROR: GITHUB_TOKEN is not set. In the terminal run:  export GITHUB_TOKEN=ghp_xxx" >&2
  exit 1
fi
if [ ! -d "/content/drive/MyDrive" ]; then
  echo "ERROR: Google Drive is not mounted. Run this in a NOTEBOOK CELL first:" >&2
  echo "       from google.colab import drive; drive.mount('/content/drive')" >&2
  exit 1
fi

# --- 1. Clone or update the repo ---------------------------------------------
if [ -d "${REPO_DIR}/.git" ]; then
  echo "==> Updating existing repo at ${REPO_DIR}"
  git -C "${REPO_DIR}" -c "http.https://github.com/.extraheader=AUTHORIZATION: basic $(printf 'x-access-token:%s' "${GITHUB_TOKEN}" | base64 -w0)" pull --ff-only origin main
else
  echo "==> Cloning ${REPO_URL}"
  rm -rf "${REPO_DIR}"
  git clone --depth 1 "https://x-access-token:${GITHUB_TOKEN}@github.com/sulav1234567/nepse.git" "${REPO_DIR}"
  git -C "${REPO_DIR}" remote set-url origin "${REPO_URL}"
fi
git -C "${REPO_DIR}" log -1 --oneline
cd "${REPO_DIR}"

# --- 2. Install dependencies (keep the runtime's preinstalled CUDA torch) -----
echo "==> Installing dependencies"
pip install -q -r backend/requirements.txt
pip install -q -U xgboost lightgbm stable-baselines3 gymnasium mlflow
nvidia-smi || echo "WARNING: nvidia-smi failed — is the runtime set to A100 GPU?"

# --- 3. Train -----------------------------------------------------------------
# Drive is already mounted (checked above), so we DON'T pass --mount-drive.
COMMON_ARGS=(
  --device cuda
  --git-pull
  --profile advanced
  --drive-root "${DRIVE_ROOT}"
  --inference-batch-size 2048
)
# AUTO_DISCONNECT=1 (default) releases the Colab runtime when training ends.
[ "${AUTO_DISCONNECT:-1}" = "1" ] && COMMON_ARGS+=(--auto-disconnect)
[ -n "${SYMBOL_LIMIT}" ] && COMMON_ARGS+=(--symbol-limit "${SYMBOL_LIMIT}")

if [ "${SMOKE:-0}" = "1" ]; then
  echo "==> SMOKE TEST (small slice, ~a few minutes)"
  python3 scripts/colab_continuous_train.py "${COMMON_ARGS[@]}" \
    --max-cycles 1 --symbol-limit "${SYMBOL_LIMIT:-20}" \
    --market-news-pages 2 --market-article-body-limit 20 \
    --max-training-rows 20000 --lstm-epochs 3 --tft-epochs 3 --ppo-timesteps 2000
else
  echo "==> FULL TRAINING (A100 80GB tuned, max-cycles=${MAX_CYCLES})"
  python3 scripts/colab_continuous_train.py "${COMMON_ARGS[@]}" \
    --max-cycles "${MAX_CYCLES}" \
    --market-news-pages 20 --market-article-body-limit 200 --internet-refresh-cycles 6 \
    --train-interval-minutes 60 \
    --max-training-rows 600000 \
    --lstm-epochs 60 --tft-epochs 60 \
    --sequence-batch-size 1024 \
    --lstm-hidden-size 256 --tft-hidden-size 256 \
    --inference-batch-size 2048 \
    --ppo-timesteps 300000
fi

echo "==> Done. Latest artifact:"
echo "    ${DRIVE_ROOT}/artifact_backups/autonomous_model_suite_latest.joblib"
