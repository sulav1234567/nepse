# Google Colab Continuous Training

This notebook flow clones the private repo, refreshes latest NEPSE/public market data, trains with Colab GPU, and stores the trained model in Google Drive.

## Fastest Path: Ready-Made Notebook

Upload `notebooks/nepse_colab_training.ipynb` to [colab.research.google.com](https://colab.research.google.com) (File → Upload notebook), switch the runtime to GPU, add the `GITHUB_TOKEN` secret, and run the cells top to bottom. It covers everything in sections 1–5 below.

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

Mount Drive in a normal Python notebook cell first:

```python
from google.colab import drive
drive.mount("/content/drive")
```

```bash
cd /content/nepse-main
python scripts/colab_continuous_train.py \
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

The PyTorch sequence models train on CUDA in Colab but are moved back to CPU before saving, so the artifact can load on machines without a GPU.
