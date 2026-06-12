# Google Colab Continuous Training

This notebook flow clones the private repo, refreshes latest NEPSE/public market data, trains with a Colab GPU, and stores the trained model in Google Drive.

**GPU is the recommended runtime.** A TPU (v5e-1) is also supported via `--device tpu`, but it only accelerates the LSTM/TFT sequence models, and the training loop's per-batch loss reads force frequent TPU syncs that erase most of the gain. The GPU runs the sequence models natively with no such penalty. The XGBoost/LightGBM ensemble and PPO agent run on the host CPU on either runtime.

## Fastest Path: Ready-Made Notebook

Upload `notebooks/nepse_colab_training.ipynb` to [colab.research.google.com](https://colab.research.google.com) (File → Upload notebook), switch the runtime to **T4 GPU** (Runtime → Change runtime type), add the `GITHUB_TOKEN` secret, and run the cells top to bottom. It covers everything in sections 1–5 below.

When training is done, download the artifact from Drive and install it locally with:

```bash
python scripts/import_colab_model.py
```

The manual steps below are the same flow, cell by cell.

## 1. Add GitHub Token To Colab

Create a GitHub fine-grained token with read access to the private repo:

```text
https://github.com/sulav1234567/nepse
```

In Colab, open **Secrets** and add:

```text
GITHUB_TOKEN=your_token_here
```

Do not paste the token directly into notebook text or commit it.

## 2. Clone The Private Repo

```python
from google.colab import userdata
import os

token = userdata.get("GITHUB_TOKEN")
assert token, "Add GITHUB_TOKEN in Colab Secrets first."
os.environ["GITHUB_TOKEN"] = token
```

```bash
rm -rf /content/nepse-main
git clone https://x-access-token:${GITHUB_TOKEN}@github.com/sulav1234567/nepse.git /content/nepse-main
cd /content/nepse-main && git remote set-url origin https://github.com/sulav1234567/nepse.git
```

## 3. Install Training Dependencies

```python
from google.colab import drive
drive.mount("/content/drive")
```

The runtime's preinstalled CUDA build of torch is kept as-is (don't `pip install -U torch`).

```bash
cd /content/nepse-main
pip install -r backend/requirements.txt
pip install -U xgboost lightgbm stable-baselines3 gymnasium mlflow
nvidia-smi
```

## 4. Start Continuous Beast Training

This runs forever until Colab disconnects. It saves the latest artifact to Google Drive every cycle.

Mount Drive in a normal Python notebook cell first:

```python
from google.colab import drive
drive.mount("/content/drive")
```

```bash
cd /content/nepse-main
python scripts/colab_continuous_train.py \
  --device cuda \
  --git-pull \
  --profile advanced \
  --market-news-pages 20 \
  --market-article-body-limit 200 \
  --internet-refresh-cycles 6 \
  --train-interval-minutes 60 \
  --max-training-rows 250000 \
  --lstm-epochs 50 \
  --tft-epochs 50 \
  --sequence-batch-size 256 \
  --ppo-timesteps 100000
```

Outputs:

```text
/content/drive/MyDrive/nepse-continuous-training/model_artifacts/autonomous_model_suite.joblib
/content/drive/MyDrive/nepse-continuous-training/artifact_backups/autonomous_model_suite_latest.joblib
/content/drive/MyDrive/nepse-continuous-training/training_state.json
```

## 5. Smoke Test A Short Run

Use this first if you want to verify everything works before a long run:

```bash
cd /content/nepse-main
python scripts/colab_continuous_train.py \
  --device cuda \
  --profile advanced \
  --symbol-limit 20 \
  --market-news-pages 2 \
  --market-article-body-limit 20 \
  --max-cycles 1 \
  --max-training-rows 20000 \
  --lstm-epochs 3 \
  --tft-epochs 3 \
  --ppo-timesteps 2000
```

## 6. Use The Trained Artifact Locally

Download `autonomous_model_suite_latest.joblib` from Drive (`MyDrive/nepse-continuous-training/artifact_backups/`) into `~/Downloads`, then run:

```bash
python scripts/import_colab_model.py
```

It backs up the current local model, installs the downloaded one at `backend/model_artifacts/autonomous_model_suite.joblib`, and verifies it loads. Restart the backend afterwards. You can also pass an explicit path: `python scripts/import_colab_model.py /path/to/artifact.joblib`.

The PyTorch sequence models train on the GPU in Colab but are moved back to CPU before saving, so the artifact loads on machines without a GPU.

## Optional: TPU Runtime

If a GPU is unavailable, the v5e-1 TPU runtime works too: keep the runtime's matched torch/torch_xla pair (never upgrade torch there), and pass `--device tpu` instead of `--device cuda`. Expect it to be slower than the T4 for this workload.
