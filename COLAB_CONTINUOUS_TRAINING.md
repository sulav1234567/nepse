# Google Colab Continuous Training

This notebook flow clones the private repo, refreshes latest NEPSE/public market data, trains with Colab GPU, and stores the trained model in Google Drive.

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

## 3. Install GPU Training Dependencies

```python
from google.colab import drive
drive.mount("/content/drive")
```

```bash
cd /content/nepse-main
pip install -U pip
pip install -r backend/requirements.txt
pip install -U xgboost lightgbm torch stable-baselines3 gymnasium mlflow
nvidia-smi
```

## 4. Start Continuous Beast Training

This runs forever until Colab disconnects. It saves the latest artifact to Google Drive every cycle.

```bash
cd /content/nepse-main
python scripts/colab_continuous_train.py \
  --mount-drive \
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
  --mount-drive \
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

Download or copy this file from Drive into the app:

```text
backend/model_artifacts/autonomous_model_suite.joblib
```

The PyTorch sequence models train on CUDA in Colab but are moved back to CPU before saving, so the artifact can load on machines without a GPU.
