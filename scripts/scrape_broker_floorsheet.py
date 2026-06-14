"""
Broker floorsheet scraper → compact per-broker daily net positions.

Source: chukul.com floorsheet API (transaction-level: symbol, buyer broker,
seller broker, quantity, rate). For each (symbol, date) we aggregate every
transaction into per-broker BUY/SELL quantity and net (bought − sold), then keep
the most significant accumulators/distributors. This is the raw signal behind
"which broker is buying/selling/holding which stock".

Storage:  data/broker/{SYMBOL}.csv  with columns:
    symbol, date, broker, buy_qty, sell_qty, buy_amt, sell_amt, net_qty

The script is RESUMABLE (skips (symbol,date) pairs already stored), rate-limited
and retry-safe, so a multi-day full backfill can run in the background and a daily
top-up keeps it current. Because the API is per-symbol-per-date only, a full
3-year backfill is hundreds of thousands of requests — run it incrementally.

Usage:
    python scripts/scrape_broker_floorsheet.py --days 30                 # last 30 trading days, all symbols
    python scripts/scrape_broker_floorsheet.py --symbols NABIL,UPPER     # specific symbols
    python scripts/scrape_broker_floorsheet.py --start 2023-06-01 --end 2026-06-12
    python scripts/scrape_broker_floorsheet.py --days 750 --sleep 0.4    # ~3y backfill (long!)
"""

from __future__ import annotations

import argparse
import csv
import logging
import sys
import time
from collections import defaultdict
from pathlib import Path

import httpx
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
MARKET_CSV_DIR = REPO_ROOT / "data" / "market" / "stocks"
INDEX_CSV = REPO_ROOT / "data" / "market" / "indices" / "NEPSE_INDEX.csv"
OUT_DIR = REPO_ROOT / "data" / "broker"

API = "https://chukul.com/api/data/floorsheet/"
HEADERS = {"User-Agent": "Mozilla/5.0", "Referer": "https://chukul.com/"}
TOP_KEEP = 20  # keep the top-N net buyers and top-N net sellers per symbol-day

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger("broker-scraper")

FIELDS = ["symbol", "date", "broker", "buy_qty", "sell_qty", "buy_amt", "sell_amt", "net_qty"]


def trading_dates() -> list[str]:
    """Real NEPSE trading dates from the index archive (ascending)."""
    if not INDEX_CSV.exists():
        return []
    df = pd.read_csv(INDEX_CSV)
    df.columns = [c.lower().strip() for c in df.columns]
    return sorted({str(d)[:10] for d in pd.to_datetime(df["date"], errors="coerce").dropna()})


def all_symbols() -> list[str]:
    return sorted(p.stem for p in MARKET_CSV_DIR.glob("*.csv"))


def existing_dates(symbol: str) -> set[str]:
    path = OUT_DIR / f"{symbol}.csv"
    if not path.exists():
        return set()
    try:
        df = pd.read_csv(path, usecols=["date"])
        return {str(d)[:10] for d in df["date"]}
    except Exception:
        return set()


def fetch_floorsheet(client: httpx.Client, symbol: str, date: str, retries: int = 3) -> list[dict] | None:
    for attempt in range(retries):
        try:
            resp = client.get(API, params={"symbol": symbol, "date": date, "page": 1}, timeout=20.0)
            if resp.status_code == 200:
                data = resp.json()
                return data if isinstance(data, list) else []
            if resp.status_code == 404:
                return []
            logger.debug("%s %s → HTTP %s", symbol, date, resp.status_code)
        except Exception as exc:
            logger.debug("%s %s attempt %d failed: %s", symbol, date, attempt + 1, exc)
        time.sleep(1.0 + attempt)
    return None


def aggregate(rows: list[dict]) -> list[dict]:
    """Transaction rows → per-broker buy/sell/net, keeping the biggest movers."""
    buy_q: dict[str, float] = defaultdict(float)
    sell_q: dict[str, float] = defaultdict(float)
    buy_a: dict[str, float] = defaultdict(float)
    sell_a: dict[str, float] = defaultdict(float)
    for r in rows:
        qty = float(r.get("quantity") or 0)
        amt = float(r.get("amount") or 0)
        b, s = str(r.get("buyer")), str(r.get("seller"))
        buy_q[b] += qty; buy_a[b] += amt
        sell_q[s] += qty; sell_a[s] += amt

    brokers = set(buy_q) | set(sell_q)
    agg = [
        {
            "broker": b,
            "buy_qty": round(buy_q[b], 2),
            "sell_qty": round(sell_q[b], 2),
            "buy_amt": round(buy_a[b], 2),
            "sell_amt": round(sell_a[b], 2),
            "net_qty": round(buy_q[b] - sell_q[b], 2),
        }
        for b in brokers
    ]
    # Keep the strongest accumulators and distributors (signal lives in the tails).
    agg.sort(key=lambda x: x["net_qty"])
    keep = agg[:TOP_KEEP] + agg[-TOP_KEEP:]
    seen = set()
    out = []
    for row in keep:
        if row["broker"] in seen:
            continue
        seen.add(row["broker"])
        out.append(row)
    return out


def append_rows(symbol: str, date: str, agg: list[dict]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f"{symbol}.csv"
    new = not path.exists()
    with path.open("a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if new:
            w.writeheader()
        for row in agg:
            w.writerow({"symbol": symbol, "date": date, **row})


def main() -> None:
    ap = argparse.ArgumentParser(description="Scrape broker floorsheet → per-broker daily net positions.")
    ap.add_argument("--days", type=int, default=30, help="Backfill the most recent N trading days.")
    ap.add_argument("--start", type=str, default=None, help="Start date YYYY-MM-DD (overrides --days).")
    ap.add_argument("--end", type=str, default=None, help="End date YYYY-MM-DD.")
    ap.add_argument("--symbols", type=str, default=None, help="Comma-separated symbols (default: all).")
    ap.add_argument("--max-symbols", type=int, default=None)
    ap.add_argument("--sleep", type=float, default=0.5, help="Seconds between requests (be polite).")
    args = ap.parse_args()

    dates = trading_dates()
    if not dates:
        logger.error("No trading dates found (need %s).", INDEX_CSV)
        sys.exit(1)
    if args.start:
        dates = [d for d in dates if d >= args.start]
    if args.end:
        dates = [d for d in dates if d <= args.end]
    if not args.start:
        dates = dates[-args.days:]

    symbols = [s.strip().upper() for s in args.symbols.split(",")] if args.symbols else all_symbols()
    if args.max_symbols:
        symbols = symbols[: args.max_symbols]

    total = len(symbols) * len(dates)
    logger.info("Backfill: %d symbols × %d dates = %d (symbol,date) pairs. Resumable.", len(symbols), len(dates), total)

    done = 0
    fetched = 0
    with httpx.Client(headers=HEADERS, verify=True) as client:
        for symbol in symbols:
            have = existing_dates(symbol)
            for date in dates:
                done += 1
                if date in have:
                    continue
                rows = fetch_floorsheet(client, symbol, date)
                if rows is None:
                    logger.warning("Giving up on %s %s after retries.", symbol, date)
                    continue
                if rows:
                    append_rows(symbol, date, aggregate(rows))
                    fetched += 1
                time.sleep(args.sleep)
            if symbols.index(symbol) % 10 == 0:
                logger.info("Progress: %d/%d pairs, %d days fetched, current=%s", done, total, fetched, symbol)

    logger.info("Done. %d symbol-days fetched into %s", fetched, OUT_DIR)


if __name__ == "__main__":
    main()
