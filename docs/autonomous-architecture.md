# Autonomous NEPSE Intelligence Architecture

## Diagram

```mermaid
flowchart LR
    A["Live NEPSE Feed<br/>CSV archives<br/>Financial statements<br/>Macro / global series<br/>News & notices"] --> B["Autonomous ingestion engine"]
    B --> C["PostgreSQL + TimescaleDB"]
    C --> D["Feature engineering layer"]
    D --> E["Technical analysis engine"]
    D --> F["Fundamental analysis engine"]
    D --> G["Global correlation engine"]
    D --> H["Sentiment engine"]
    D --> I["Sector rotation engine"]
    D --> J["Regime detector"]
    D --> K["Model suite<br/>LSTM<br/>TFT-style forecaster<br/>XGBoost / LightGBM<br/>PPO agent<br/>Sentiment model"]
    K --> L["Stacking meta-learner"]
    L --> M["Signal cards<br/>Top buy / avoid ranks<br/>Backtests<br/>Monitoring metrics"]
    M --> N["FastAPI API"]
    M --> O["Celery worker / beat"]
    O --> C
    N --> P["Next.js dashboard"]
    O --> Q["MLflow model registry"]
```

## Runtime layout

- `backend/autonomous/ingestion.py`
  Loads local archives, live snapshots, macro series, and news into the database.
- `backend/autonomous/storage.py`
  Defines Timescale-ready persistence models for bars, fundamentals, macro series, predictions, and backtests.
- `backend/autonomous/features.py`
  Builds the cross-sectional feature matrix and scores fundamentals, regimes, and global linkages.
- `backend/autonomous/indicators.py`
  Computes RSI, MACD, Bollinger Bands, EMAs, ADX, Stochastic, Ichimoku, OBV, VWAP, Fibonacci levels, support/resistance, and chart patterns.
- `backend/autonomous/models.py`
  Hosts the multi-model ensemble and contextual meta-learner.
- `backend/autonomous/backtesting.py`
  Runs walk-forward ranking backtests for monitoring and retraining gates.
- `backend/autonomous/tasks.py`
  Schedules 15-minute market-hour cycles, 6-hour off-hour rescoring, daily outcome evaluation, and monthly retraining.

## Data flow

1. Raw market/fundamental/macro/news inputs land in TimescaleDB.
2. Feature engineering builds a 200+ feature matrix per stock with lagged market, sector, macro, and sentiment context.
3. The technical, fundamental, and global engines produce interpretable domain scores.
4. The model suite predicts 7-day, 30-day, and 90-day returns.
5. The meta-learner blends domain and model outputs into confidence-scored signal cards.
6. Prediction runs and later realized outcomes are stored for monitoring and retraining logic.

## Operating modes

- `Bootstrap mode`
  If historical archives are missing, the system seeds live bars and synthetic bootstrap history so the product remains usable.
- `Trained mode`
  Once local archives accumulate and the worker finishes a training cycle, the dashboard switches to the learned ensemble and stores versioned model metrics.

## Deployment notes

- Local development defaults to SQLite so the code can start without infrastructure.
- Docker Compose overrides the database to PostgreSQL + TimescaleDB and adds Redis, Celery, and MLflow.
- The autonomous API lives under `/api/autonomous/*`.
