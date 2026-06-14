"""
Broker-intelligence features (accumulation / distribution by broker).

Built from the per-broker daily net positions produced by
``scripts/scrape_broker_floorsheet.py`` (data/broker/{SYMBOL}.csv). The thesis:
when the big brokers accumulate a stock and accumulation is concentrated in a few
hands, the stock has a higher chance of rising; heavy distribution by big brokers
is bearish. These features encode that signal for the model.

Public:
    infer_big_brokers(broker_dir) -> set[str]
    build_symbol_broker_features(symbol, big_brokers, broker_dir) -> DataFrame
        (date-indexed daily features + rolling accumulation trends)
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

logger = logging.getLogger("nepse.broker_features")

DEFAULT_BROKER_DIR = Path(__file__).resolve().parents[2] / "data" / "broker"
# Compact, committed per-symbol feature files (1 row/date × 15 cols) produced by
# scripts/consolidate_broker_features.py. Preferred over recomputing from the large
# raw floorsheet so Colab (which clones from git) gets broker features too.
PRECOMPUTED_DIR = Path(__file__).resolve().parents[2] / "data" / "broker_features"

# The feature columns this module contributes (used by callers to know the schema).
BROKER_FEATURE_COLS = [
    "bk_net_accumulation", "bk_net_distribution", "bk_accumulation_ratio",
    "bk_big_net", "bk_big_buy_flag", "bk_concentration", "bk_top_buyer_net_share",
    "bk_num_net_buyers", "bk_num_net_sellers", "bk_dominant_broker_net",
    "bk_big_net_5d", "bk_big_net_20d", "bk_big_net_60d",
    "bk_accum_trend_20d", "bk_distribution_flag",
]


@lru_cache(maxsize=1)
def infer_big_brokers(broker_dir: str = str(DEFAULT_BROKER_DIR), top_n: int = 15) -> tuple[str, ...]:
    """Rank brokers by total traded volume across all stored data → the 'big' tier.

    Big brokers (e.g. 58) move size; their net direction is the headline signal.
    Falls back to a known-large NEPSE broker set if no data is present yet.
    """
    directory = Path(broker_dir)
    totals: dict[str, float] = {}
    for csv_path in directory.glob("*.csv"):
        try:
            df = pd.read_csv(csv_path, usecols=["broker", "buy_qty", "sell_qty"])
        except Exception:
            continue
        vol = (df["buy_qty"].fillna(0) + df["sell_qty"].fillna(0)).groupby(df["broker"].astype(str)).sum()
        for broker, v in vol.items():
            totals[broker] = totals.get(broker, 0.0) + float(v)
    if not totals:
        # Sensible default: historically dominant NEPSE brokers.
        return ("58", "45", "34", "28", "49", "33", "47", "29", "59", "42")
    ranked = sorted(totals, key=lambda b: totals[b], reverse=True)
    return tuple(ranked[:top_n])


def build_symbol_broker_features(
    symbol: str,
    big_brokers: tuple[str, ...] | None = None,
    broker_dir: str = str(DEFAULT_BROKER_DIR),
    use_precomputed: bool = True,
) -> pd.DataFrame:
    """Per-date broker-intelligence features for one symbol (empty if no data).

    Prefers the compact committed file in data/broker_features/; otherwise computes
    from the raw floorsheet aggregates in data/broker/. Set use_precomputed=False to
    always recompute from raw (used by the consolidation script).
    """
    if use_precomputed:
        precomputed = PRECOMPUTED_DIR / f"{symbol.upper()}.csv"
        if precomputed.exists():
            try:
                return pd.read_csv(precomputed)
            except Exception as exc:
                logger.debug("Precomputed broker features unreadable for %s: %s", symbol, exc)

    path = Path(broker_dir) / f"{symbol.upper()}.csv"
    if not path.exists():
        return pd.DataFrame(columns=["date", *BROKER_FEATURE_COLS])

    try:
        df = pd.read_csv(path)
    except Exception as exc:
        logger.debug("Broker data load failed for %s: %s", symbol, exc)
        return pd.DataFrame(columns=["date", *BROKER_FEATURE_COLS])
    if df.empty:
        return pd.DataFrame(columns=["date", *BROKER_FEATURE_COLS])

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["broker"] = df["broker"].astype(str)
    df["net_qty"] = pd.to_numeric(df["net_qty"], errors="coerce").fillna(0.0)
    big = set(big_brokers or infer_big_brokers(broker_dir))
    dominant = next(iter(big_brokers or infer_big_brokers(broker_dir)), "58")

    rows = []
    for date, grp in df.groupby("date"):
        nets = grp.set_index("broker")["net_qty"]
        pos = nets[nets > 0]
        neg = nets[nets < 0]
        total_vol = float((grp["buy_qty"].abs() + grp["sell_qty"].abs()).sum()) or 1.0
        accumulation = float(pos.sum())
        distribution = float(-neg.sum())
        big_net = float(nets[nets.index.isin(big)].sum())
        # Herfindahl concentration of accumulation (few buyers accumulating ⇒ ~1).
        conc = float(((pos / pos.sum()) ** 2).sum()) if pos.sum() > 0 else 0.0
        top_buyer_net = float(pos.max()) if not pos.empty else 0.0
        rows.append({
            "date": date,
            "bk_net_accumulation": round(accumulation, 2),
            "bk_net_distribution": round(distribution, 2),
            "bk_accumulation_ratio": round((accumulation - distribution) / total_vol, 4),
            "bk_big_net": round(big_net, 2),
            "bk_big_buy_flag": 1.0 if big_net > 0 else 0.0,
            "bk_concentration": round(conc, 4),
            "bk_top_buyer_net_share": round(top_buyer_net / total_vol, 4),
            "bk_num_net_buyers": float(len(pos)),
            "bk_num_net_sellers": float(len(neg)),
            "bk_dominant_broker_net": round(float(nets.get(dominant, 0.0)), 2),
        })

    feat = pd.DataFrame(rows).sort_values("date").reset_index(drop=True)
    # Rolling accumulation trends — smart-money flow persistence is the real edge.
    feat["bk_big_net_5d"] = feat["bk_big_net"].rolling(5, min_periods=1).sum()
    feat["bk_big_net_20d"] = feat["bk_big_net"].rolling(20, min_periods=1).sum()
    feat["bk_big_net_60d"] = feat["bk_big_net"].rolling(60, min_periods=1).sum()
    feat["bk_accum_trend_20d"] = feat["bk_accumulation_ratio"].rolling(20, min_periods=1).mean()
    feat["bk_distribution_flag"] = (feat["bk_big_net_5d"] < 0).astype(float)
    feat["date"] = feat["date"].dt.strftime("%Y-%m-%d")
    return feat
