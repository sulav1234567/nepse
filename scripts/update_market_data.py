"""
Incrementally update data/market/stocks/*.csv with the latest ShareSansar prices.

Fetches the full-market "today share price" table for each missing trading date
(one request per date, all ~350 companies at once) and merges the rows into the
existing per-symbol CSVs. Much faster and gentler on ShareSansar than the
per-company price-history endpoint, which aggressively rate-limits.

Usage:
    python scripts/update_market_data.py                 # from last known date till today
    python scripts/update_market_data.py --start 2026-05-08 --end 2026-06-12
"""

from __future__ import annotations

import argparse
import io
import logging
import re
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import httpx
import pandas as pd
from bs4 import BeautifulSoup

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.nepse_fetcher import SHARESANSAR_HEADERS, SHARESANSAR_SSL_VERIFY  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("update_market_data")

STOCKS_DIR = PROJECT_ROOT / "data" / "market" / "stocks"
TODAY_PRICE_PAGE = "https://www.sharesansar.com/today-share-price"
TODAY_PRICE_AJAX = "https://www.sharesansar.com/ajaxtodayshareprice"

# NEPSE trades Sunday-Thursday; Friday (4) and Saturday (5) are closed.
CLOSED_WEEKDAYS = {4, 5}


def latest_known_date() -> date:
    """Most recent date present across all stock CSVs."""
    best: date | None = None
    for csv_path in STOCKS_DIR.glob("*.csv"):
        try:
            last_line = csv_path.read_text().strip().rsplit("\n", 1)[-1]
            match = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", last_line)
            if match:
                value = date.fromisoformat(match.group(1))
                if best is None or value > best:
                    best = value
        except Exception:
            continue
    return best or date(2026, 1, 1)


def fetch_day_table(client: httpx.Client, token: str, day: date) -> pd.DataFrame | None:
    """Fetch the all-companies price table for one date. None if market closed."""
    response = client.post(
        TODAY_PRICE_AJAX,
        headers={
            "X-CSRF-Token": token,
            "X-Requested-With": "XMLHttpRequest",
            "Referer": TODAY_PRICE_PAGE,
        },
        data={"_token": token, "sector": "all_sec", "date": day.isoformat()},
    )
    response.raise_for_status()
    html = response.text

    as_of_match = re.search(r"As of\s*:\s*<span[^>]*>([\d-]+)", html)
    if not as_of_match or as_of_match.group(1) != day.isoformat():
        return None  # holiday / market closed — server returned a different day

    tables = pd.read_html(io.StringIO(html))
    if not tables:
        return None
    frame = tables[0]
    needed = {"Symbol", "Open", "High", "Low", "Close", "Vol", "Turnover", "Diff %"}
    if not needed.issubset(set(frame.columns)):
        logger.warning("%s: unexpected table columns %s", day, list(frame.columns))
        return None
    return frame


def day_table_to_records(day: date, frame: pd.DataFrame) -> list[dict]:
    """Convert one day's market table into CSV-schema row dicts."""
    records = []
    for _, row in frame.iterrows():
        symbol = str(row["Symbol"]).strip().upper()
        close = pd.to_numeric(row["Close"], errors="coerce")
        if not symbol or pd.isna(close):
            continue
        records.append({
            "symbol": symbol,
            "date": day.isoformat(),
            "open": pd.to_numeric(row["Open"], errors="coerce"),
            "high": pd.to_numeric(row["High"], errors="coerce"),
            "low": pd.to_numeric(row["Low"], errors="coerce"),
            "close": close,
            "volume": pd.to_numeric(row["Vol"], errors="coerce"),
            "turnover": pd.to_numeric(row["Turnover"], errors="coerce"),
            "change_percent": pd.to_numeric(row["Diff %"], errors="coerce"),
            "source": "SHARESANSAR_PRICE_HISTORY",
        })
    return records


def merge_records_into_csvs(records: list[dict]) -> tuple[int, int]:
    """Merge fetched rows into per-symbol CSVs. Returns (symbols updated, rows added)."""
    new_frame = pd.DataFrame(records)
    symbols_updated, rows_added = 0, 0
    for symbol, group in new_frame.groupby("symbol"):
        csv_path = STOCKS_DIR / f"{symbol}.csv"
        if not csv_path.exists():
            continue
        existing = pd.read_csv(csv_path, dtype={"date": str})
        tail = existing.iloc[-1] if len(existing) else {}
        group = group.copy()
        group["company_name"] = str(tail.get("company_name", symbol))
        group["sector"] = str(tail.get("sector", "Others"))
        group["source_url"] = str(tail.get("source_url", f"https://www.sharesansar.com/company/{symbol}"))
        group = group[list(existing.columns)] if set(group.columns) >= set(existing.columns) else group
        combined = pd.concat([existing, group], ignore_index=True)
        combined = combined.drop_duplicates(subset=["date"], keep="last").sort_values("date")
        added = len(combined) - len(existing)
        if added > 0:
            combined.to_csv(csv_path, index=False)
            symbols_updated += 1
            rows_added += added
    return symbols_updated, rows_added


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", type=date.fromisoformat, default=None)
    parser.add_argument("--end", type=date.fromisoformat, default=None)
    parser.add_argument("--delay", type=float, default=1.5, help="Delay between dates (s)")
    args = parser.parse_args()

    start = args.start or latest_known_date() + timedelta(days=1)
    end = args.end or datetime.now().date()
    if start > end:
        logger.info("Data already up to date (latest known: %s).", start - timedelta(days=1))
        return

    days = [
        start + timedelta(days=offset)
        for offset in range((end - start).days + 1)
        if (start + timedelta(days=offset)).weekday() not in CLOSED_WEEKDAYS
    ]
    logger.info("Fetching %d candidate trading days: %s .. %s", len(days), start, end)

    all_records: list[dict] = []
    trading_days = 0
    with httpx.Client(
        verify=SHARESANSAR_SSL_VERIFY,
        follow_redirects=True,
        timeout=40.0,
        headers=SHARESANSAR_HEADERS,
    ) as client:
        page = client.get(TODAY_PRICE_PAGE)
        page.raise_for_status()
        token_node = BeautifulSoup(page.text, "lxml").select_one('meta[name="_token"]')
        if token_node is None:
            logger.error("Could not extract CSRF token from ShareSansar page.")
            sys.exit(1)
        token = token_node.get("content", "")

        for day in days:
            try:
                frame = fetch_day_table(client, token, day)
            except Exception as exc:
                logger.warning("%s: fetch failed (%s)", day, exc)
                time.sleep(args.delay * 2)
                continue
            if frame is None:
                logger.info("%s: market closed, skipping", day)
            else:
                records = day_table_to_records(day, frame)
                all_records.extend(records)
                trading_days += 1
                logger.info("%s: %d symbol rows fetched", day, len(records))
            time.sleep(args.delay)

    if not all_records:
        logger.info("No new market rows fetched.")
        return

    symbols_updated, rows_added = merge_records_into_csvs(all_records)
    logger.info(
        "DONE: %d trading days fetched, %d rows added across %d symbols.",
        trading_days, rows_added, symbols_updated,
    )


if __name__ == "__main__":
    main()
