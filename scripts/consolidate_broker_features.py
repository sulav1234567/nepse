"""
Consolidate raw broker floorsheet aggregates → compact, committable feature files.

Reads data/broker/{SYMBOL}.csv (large, gitignored raw per-broker net positions),
computes the 15 broker-intelligence features per symbol-date, and writes
data/broker_features/{SYMBOL}.csv (1 row/date — small, committed to git so Colab
training picks it up after cloning).

Run after the scraper (scripts/scrape_broker_floorsheet.py), then commit
data/broker_features/.

Usage:
    python scripts/consolidate_broker_features.py
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.autonomous.broker_features import (  # noqa: E402
    DEFAULT_BROKER_DIR,
    PRECOMPUTED_DIR,
    build_symbol_broker_features,
    infer_big_brokers,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger("consolidate-broker")


def main() -> None:
    raw_dir = Path(DEFAULT_BROKER_DIR)
    if not raw_dir.exists():
        logger.error("No raw broker data at %s — run scripts/scrape_broker_floorsheet.py first.", raw_dir)
        sys.exit(1)

    PRECOMPUTED_DIR.mkdir(parents=True, exist_ok=True)
    big = infer_big_brokers()  # computed once from the full raw dataset
    logger.info("Big brokers (top by volume): %s", ", ".join(big))

    written = 0
    symbols = sorted(p.stem for p in raw_dir.glob("*.csv"))
    for symbol in symbols:
        feat = build_symbol_broker_features(symbol, big_brokers=big, use_precomputed=False)
        if feat.empty:
            continue
        feat.to_csv(PRECOMPUTED_DIR / f"{symbol}.csv", index=False)
        written += 1

    logger.info("Wrote compact broker features for %d symbols → %s", written, PRECOMPUTED_DIR)


if __name__ == "__main__":
    main()
