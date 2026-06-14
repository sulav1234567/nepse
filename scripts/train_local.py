"""
Local training script for the NEPSE autonomous model suite.

Reads all 334 stock CSVs from data/market/stocks/, builds feature frames,
and trains the full ensemble (XGBoost + LightGBM + LSTM + TFT + PPO-RL +
meta-learner) with walk-forward validation.

Usage:
    python scripts/train_local.py
    python scripts/train_local.py --max-stocks 50  # quick test
    python scripts/train_local.py --no-torch        # skip LSTM/TFT
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import numpy as np
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("nepse.train_local")


# ─── Data loading ─────────────────────────────────────────────────────────────

MARKET_CSV_DIR = REPO_ROOT / "data" / "market" / "stocks"
MACRO_DIR = REPO_ROOT / "data" / "macro"
FUNDAMENTALS_CSV = REPO_ROOT / "data" / "fundamentals" / "sharesansar_quarterly_snapshots.csv"
INDEX_CSV = REPO_ROOT / "data" / "market" / "indices" / "NEPSE_INDEX.csv"
REQUIRED_COLS = {"date", "open", "high", "low", "close", "volume"}


def load_stock_csvs(max_stocks: int | None = None) -> dict[str, pd.DataFrame]:
    """Load all CSVs. Returns symbol -> DataFrame with canonical columns."""
    csv_files = sorted(MARKET_CSV_DIR.glob("*.csv"))
    if max_stocks:
        csv_files = csv_files[:max_stocks]

    frames: dict[str, pd.DataFrame] = {}
    for csv_path in csv_files:
        symbol = csv_path.stem
        try:
            df = pd.read_csv(csv_path, parse_dates=["date"])
            df.columns = [c.lower().strip() for c in df.columns]
            if not REQUIRED_COLS.issubset(set(df.columns)):
                continue
            df = df.sort_values("date").reset_index(drop=True)
            df = df.dropna(subset=["close", "volume"])
            df["symbol"] = symbol
            # Parse sector / company name if present
            if "company_name" not in df.columns:
                df["company_name"] = symbol
            if "sector" not in df.columns:
                df["sector"] = "Others"
            # Ensure numeric types
            for col in ["open", "high", "low", "close", "volume"]:
                df[col] = pd.to_numeric(df[col], errors="coerce")
            df = df.dropna(subset=["close"])
            if len(df) >= 60:
                frames[symbol] = df
        except Exception as exc:
            logger.warning("Skipping %s: %s", symbol, exc)

    logger.info("Loaded %d stocks (of %d CSVs).", len(frames), len(csv_files))
    return frames


# ─── Macro / fundamentals / index loaders ─────────────────────────────────────
# These wire the SAME external data the live inference path uses into local
# training, so the local model has the full ~250-feature schema instead of a
# degraded price-only subset that would not match the served model.

def load_macro_frames() -> dict[str, pd.DataFrame]:
    """Load global/macro time-series as {SERIES_NAME: df[date, close]}."""
    frames: dict[str, pd.DataFrame] = {}
    if not MACRO_DIR.exists():
        return frames
    for csv_path in sorted(MACRO_DIR.glob("*.csv")):
        try:
            df = pd.read_csv(csv_path)
            cols = {c.lower(): c for c in df.columns}
            # Only time-series files (series_name,date,value); skip e.g. snapshots.
            if "value" not in cols or "date" not in cols:
                continue
            out = pd.DataFrame({
                "date": pd.to_datetime(df[cols["date"]], errors="coerce"),
                "close": pd.to_numeric(df[cols["value"]], errors="coerce"),
            }).dropna().sort_values("date").reset_index(drop=True)
            if not out.empty:
                frames[csv_path.stem.upper()] = out
        except Exception as exc:
            logger.warning("Macro load failed for %s: %s", csv_path.name, exc)
    return frames


def load_fundamentals() -> pd.DataFrame:
    """Load the quarterly fundamentals snapshot (eps, roe, npl, casa_ratio, ...)."""
    if not FUNDAMENTALS_CSV.exists():
        return pd.DataFrame()
    try:
        df = pd.read_csv(FUNDAMENTALS_CSV)
        df.columns = [c.lower().strip() for c in df.columns]
        return df
    except Exception as exc:
        logger.warning("Fundamentals load failed: %s", exc)
        return pd.DataFrame()


def load_index_frame() -> pd.DataFrame:
    """Load the NEPSE index frame used for beta/alpha and market-relative features."""
    if not INDEX_CSV.exists():
        return pd.DataFrame()
    try:
        df = pd.read_csv(INDEX_CSV)
        df.columns = [c.lower().strip() for c in df.columns]
        return df
    except Exception as exc:
        logger.warning("Index frame load failed: %s", exc)
        return pd.DataFrame()


def build_sector_frames(stock_frames: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Build a per-sector composite (mean close by date) as a sector-peer proxy."""
    by_sector: dict[str, list[pd.DataFrame]] = {}
    for df in stock_frames.values():
        if "sector" not in df.columns or df.empty:
            continue
        sector = str(df["sector"].iloc[-1])
        by_sector.setdefault(sector, []).append(df[["date", "close"]])
    sector_frames: dict[str, pd.DataFrame] = {}
    for sector, parts in by_sector.items():
        combined = pd.concat(parts)
        combined["date"] = pd.to_datetime(combined["date"], errors="coerce")
        composite = (
            combined.dropna(subset=["date"]).groupby("date", as_index=False)["close"].mean()
            .sort_values("date").reset_index(drop=True)
        )
        if not composite.empty:
            sector_frames[sector] = composite
    return sector_frames


# ─── Feature building bridge ──────────────────────────────────────────────────

def build_features_for_symbol(
    symbol: str,
    df: pd.DataFrame,
    *,
    fundamentals_all: pd.DataFrame | None = None,
    macro_frames: dict[str, pd.DataFrame] | None = None,
    index_frame: pd.DataFrame | None = None,
    sector_frames: dict[str, pd.DataFrame] | None = None,
) -> pd.DataFrame | None:
    """Build the autonomous feature frame for one symbol (full external context)."""
    try:
        from backend.autonomous.features import build_feature_frame

        price_frame = df.copy()
        if "turnover" not in price_frame.columns:
            price_frame["turnover"] = price_frame["close"] * price_frame["volume"]

        sector = str(df["sector"].iloc[-1]) if "sector" in df.columns else "Others"
        fundamentals = pd.DataFrame()
        if (
            fundamentals_all is not None
            and not fundamentals_all.empty
            and "symbol" in fundamentals_all.columns
        ):
            fundamentals = fundamentals_all[fundamentals_all["symbol"] == symbol]

        feature_frame = build_feature_frame(
            symbol=symbol,
            price_frame=price_frame,
            fundamentals_frame=fundamentals if not fundamentals.empty else None,
            sector_peer_frame=(sector_frames or {}).get(sector),
            macro_frames=macro_frames or None,
            market_frame=index_frame if (index_frame is not None and not index_frame.empty) else None,
        )
        if feature_frame is not None and not feature_frame.empty:
            if "sector" not in feature_frame.columns:
                sector = str(df["sector"].iloc[-1]) if "sector" in df.columns else "Others"
                feature_frame["sector"] = sector
            target_cols = [c for c in feature_frame.columns if c.startswith("target_return_")]
            feature_frame = feature_frame.dropna(subset=target_cols)
            if len(feature_frame) >= 30:
                return feature_frame
    except Exception as exc:
        logger.warning("Rich feature build failed for %s (%s); using minimal features.", symbol, exc)

    # Fallback: build minimal feature frame from OHLCV only
    return _build_minimal_features(symbol, df)


def _build_minimal_features(symbol: str, df: pd.DataFrame) -> pd.DataFrame | None:
    """Minimal feature engineering when the full pipeline isn't available."""
    try:
        from backend.autonomous.features import HORIZONS
    except ImportError:
        HORIZONS = (7, 30, 90)

    df = df.copy().sort_values("date").reset_index(drop=True)
    closes = df["close"].values.astype(float)
    volumes = df["volume"].values.astype(float)
    n = len(closes)

    features = pd.DataFrame(index=df.index)
    features["date"] = df["date"]
    features["symbol"] = symbol
    features["sector"] = df.get("sector", "Others")
    features["close"] = closes

    # Returns
    for w in (1, 3, 5, 7, 10, 14, 20, 30, 45, 60):
        col = f"return_{w}d"
        ret = pd.Series(closes).pct_change(w) * 100
        features[col] = ret.values

    # Volatility
    for w in (10, 20):
        features[f"volatility_{w}d"] = pd.Series(closes).pct_change().rolling(w, min_periods=2).std(ddof=0).values * 100

    # Volume ratio
    vol_s = pd.Series(volumes)
    features["volume_ratio_20d"] = (vol_s / vol_s.rolling(20, min_periods=5).mean()).clip(0, 10).values

    # RSI-14
    delta = pd.Series(closes).diff()
    gain = delta.clip(lower=0).rolling(14, min_periods=5).mean()
    loss = (-delta.clip(upper=0)).rolling(14, min_periods=5).mean()
    rs = gain / loss.replace(0, np.nan)
    features["rsi_14"] = (100 - 100 / (1 + rs)).fillna(50).values

    # MACD
    ema12 = pd.Series(closes).ewm(span=12, adjust=False).mean()
    ema26 = pd.Series(closes).ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    features["macd_histogram"] = (macd - signal).values

    # Bollinger bands
    sma20 = pd.Series(closes).rolling(20, min_periods=5).mean()
    std20 = pd.Series(closes).rolling(20, min_periods=5).std(ddof=0)
    features["bollinger_pct"] = ((pd.Series(closes) - sma20) / (2 * std20 + 1e-8)).clip(-2, 2).values

    # EMA alignment
    ema9 = pd.Series(closes).ewm(span=9, adjust=False).mean()
    ema21 = pd.Series(closes).ewm(span=21, adjust=False).mean()
    ema55 = pd.Series(closes).ewm(span=55, adjust=False).mean()
    features["ema_alignment"] = np.where(
        (ema9 > ema21) & (ema21 > ema55), 1.0,
        np.where((ema9 < ema21) & (ema21 < ema55), -1.0, 0.0)
    )

    # 52w position
    high52 = pd.Series(closes).rolling(252, min_periods=50).max()
    low52 = pd.Series(closes).rolling(252, min_periods=50).min()
    rng = (high52 - low52).replace(0, np.nan)
    features["position_52w"] = ((pd.Series(closes) - low52) / rng).clip(0, 1).values

    # ADX placeholder
    features["adx_14"] = 25.0
    features["beta_20d"] = 1.0
    features["market_return_1d"] = 0.0
    features["sentiment_mean"] = 0.0

    # Target labels
    for h in HORIZONS:
        future_ret = pd.Series(closes).pct_change(h).shift(-h) * 100
        features[f"target_return_{h}d"] = future_ret.values

    # Drop rows where targets are NaN
    target_cols = [f"target_return_{h}d" for h in HORIZONS]
    features = features.dropna(subset=target_cols)

    return features if len(features) >= 30 else None


# ─── Training ─────────────────────────────────────────────────────────────────

def run_training(max_stocks: int | None = None, no_torch: bool = False) -> None:
    if no_torch:
        import os
        os.environ["NEPSE_FORCE_CPU"] = "1"
        os.environ["NEPSE_LSTM_EPOCHS"] = "1"
        os.environ["NEPSE_TFT_EPOCHS"] = "1"

    logger.info("Loading CSVs from %s ...", MARKET_CSV_DIR)
    stock_frames = load_stock_csvs(max_stocks)
    if not stock_frames:
        logger.error("No stock data found. Make sure data/market/stocks/*.csv exist.")
        sys.exit(1)

    # Load the same external context the live inference path uses so the local
    # model is trained on the full feature schema (not a degraded price-only set).
    macro_frames = load_macro_frames()
    fundamentals_all = load_fundamentals()
    index_frame = load_index_frame()
    sector_frames = build_sector_frames(stock_frames)
    logger.info(
        "External context: %d macro series, %d fundamentals rows, %d sector composites, index=%s",
        len(macro_frames), len(fundamentals_all), len(sector_frames), not index_frame.empty,
    )

    logger.info("Building feature frames for %d symbols ...", len(stock_frames))
    t0 = time.time()
    symbol_feature_frames: dict[str, pd.DataFrame] = {}
    failed = 0
    for i, (sym, df) in enumerate(stock_frames.items(), 1):
        ff = build_features_for_symbol(
            sym, df,
            fundamentals_all=fundamentals_all,
            macro_frames=macro_frames,
            index_frame=index_frame,
            sector_frames=sector_frames,
        )
        if ff is not None and not ff.empty:
            symbol_feature_frames[sym] = ff
        else:
            failed += 1
        if i % 50 == 0:
            logger.info("  Feature progress: %d/%d (%.0fs elapsed)", i, len(stock_frames), time.time() - t0)

    logger.info(
        "Feature frames ready: %d ok, %d failed. (%.1fs)",
        len(symbol_feature_frames), failed, time.time() - t0,
    )

    if not symbol_feature_frames:
        logger.error("No usable feature frames — aborting.")
        sys.exit(1)

    logger.info("Training autonomous model suite ...")
    try:
        from backend.autonomous.models import AutonomousModelSuite
        suite = AutonomousModelSuite.load()
        t1 = time.time()
        suite.train(symbol_feature_frames)
        elapsed = time.time() - t1
        logger.info("Training complete in %.1fs.", elapsed)
        logger.info("Metrics: %s", suite.metrics)
        logger.info("Model version: %s", suite.model_version)
        artifact_path = suite.artifact_path
        logger.info("Model saved to %s", artifact_path)
    except Exception as exc:
        logger.error("Training failed: %s", exc, exc_info=True)
        sys.exit(1)

    # Print summary
    print("\n" + "=" * 60)
    print("  TRAINING COMPLETE — NEPSE Autonomous Model Suite")
    print("=" * 60)
    metrics = getattr(suite, "metrics", {})
    for k, v in metrics.items():
        print(f"  {k:35s}: {v}")
    print(f"  {'Symbols trained on':35s}: {len(symbol_feature_frames)}")
    print(f"  {'Model version':35s}: {suite.model_version}")
    print("=" * 60)
    print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train NEPSE autonomous model suite locally.")
    parser.add_argument("--max-stocks", type=int, default=None, help="Limit number of stocks for quick testing.")
    parser.add_argument("--no-torch", action="store_true", help="Skip LSTM/TFT training (faster).")
    args = parser.parse_args()
    run_training(max_stocks=args.max_stocks, no_torch=args.no_torch)
