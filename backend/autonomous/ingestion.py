"""
Autonomous ingestion engine for market, fundamentals, macro, and news data.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

from ..deterministic import stable_rng
from ..nepse_fetcher import fetch_all_stocks, fetch_market_overview, fetch_nepse_index_history
from ..settings import Settings, get_settings
from .storage import (
    FundamentalSnapshot,
    MacroSeriesPoint,
    MarketBar,
    NewsArticle,
    AutonomousDatabase,
    get_database,
)

logger = logging.getLogger("nepse-alpha.autonomous.ingestion")

MARKET_COLUMN_ALIASES = {
    "symbol": ["symbol", "ticker", "scrip"],
    "company_name": ["company_name", "company", "name", "companyname"],
    "sector": ["sector", "sector_name", "industry"],
    "date": ["date", "datetime", "timestamp", "ts"],
    "open": ["open", "open_price", "opening_price"],
    "high": ["high", "high_price"],
    "low": ["low", "low_price"],
    "close": ["close", "closing_price", "close_price", "ltp", "cmp"],
    "volume": ["volume", "qty", "quantity", "total_trade_quantity"],
    "turnover": ["turnover", "amount", "value", "trade_value"],
}

FUNDAMENTAL_COLUMN_ALIASES = {
    "symbol": ["symbol", "ticker", "scrip"],
    "company_name": ["company_name", "company", "name"],
    "sector": ["sector", "sector_name", "industry"],
    "fiscal_period": ["fiscal_period", "period", "quarter", "fiscal_quarter"],
    "report_date": ["report_date", "date", "published_at"],
    "eps": ["eps", "earnings_per_share"],
    "pe": ["pe", "p_e", "price_earnings"],
    "pb": ["pb", "p_b", "price_book"],
    "dividend_yield": ["dividend_yield", "yield", "div_yield"],
    "revenue": ["revenue", "sales", "total_revenue"],
    "revenue_growth_yoy": ["revenue_growth_yoy", "sales_growth_yoy"],
    "revenue_growth_qoq": ["revenue_growth_qoq", "sales_growth_qoq"],
    "net_profit": ["net_profit", "profit_after_tax", "pat"],
    "net_profit_margin": ["net_profit_margin", "profit_margin"],
    "roe": ["roe", "return_on_equity"],
    "roa": ["roa", "return_on_assets"],
    "debt_to_equity": ["debt_to_equity", "de_ratio"],
    "current_ratio": ["current_ratio"],
    "quick_ratio": ["quick_ratio"],
    "book_value_per_share": ["book_value_per_share", "bvps", "book_value"],
    "npl_ratio": ["npl_ratio", "npl"],
    "casa_ratio": ["casa_ratio", "casa"],
}

NEWS_COLUMN_ALIASES = {
    "source": ["source"],
    "source_url": ["source_url", "url", "link"],
    "symbol": ["symbol", "ticker", "scrip"],
    "language": ["language", "lang"],
    "title": ["title", "headline"],
    "body": ["body", "content", "text"],
    "published_at": ["published_at", "date", "timestamp"],
    "sentiment_score": ["sentiment_score", "score", "sentiment"],
}


def _run_sync(coro: Any) -> Any:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _normalize_columns(df: pd.DataFrame, aliases: dict[str, list[str]]) -> pd.DataFrame:
    renamed = df.copy()
    lower_map = {column.lower(): column for column in renamed.columns}
    for target, options in aliases.items():
        if target in renamed.columns:
            continue
        for option in options:
            actual = lower_map.get(option.lower())
            if actual:
                renamed = renamed.rename(columns={actual: target})
                break
    return renamed


def _json_safe_value(value: Any) -> Any:
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    if pd.isna(value):
        return None
    if isinstance(value, dict):
        return {str(key): _json_safe_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe_value(item) for item in value]
    return value


def _read_tabular_file(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path)
    if path.suffix.lower() in {".parquet", ".pq"}:
        return pd.read_parquet(path)
    if path.suffix.lower() == ".json":
        return pd.read_json(path)
    raise ValueError(f"Unsupported file type for {path}")


class DataIngestionService:
    """Continuously loads market intelligence inputs into the autonomous database."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        database: Optional[AutonomousDatabase] = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.database = database or get_database()

    def ingest_local_market_data(self) -> int:
        root = Path(self.settings.historical_data_dir)
        count = 0
        with self.database.session() as session:
            for path in sorted(root.rglob("*")):
                if path.suffix.lower() not in {".csv", ".parquet", ".pq", ".json"}:
                    continue
                df = _normalize_columns(_read_tabular_file(path), MARKET_COLUMN_ALIASES)
                if "symbol" not in df.columns or "date" not in df.columns:
                    continue
                df["date"] = pd.to_datetime(df["date"], errors="coerce")
                df = df.dropna(subset=["symbol", "date"])
                records: list[dict[str, Any]] = []
                for _, row in df.iterrows():
                    close = float(row.get("close", 0.0) or 0.0)
                    records.append(
                        {
                            "symbol": str(row["symbol"]).upper(),
                            "company_name": str(row.get("company_name", row["symbol"])),
                            "sector": str(row.get("sector", "Others")),
                            "interval": "1d",
                            "ts": row["date"].to_pydatetime(),
                            "open": float(row.get("open", close) or close),
                            "high": float(row.get("high", close) or close),
                            "low": float(row.get("low", close) or close),
                            "close": close,
                            "volume": float(row.get("volume", 0.0) or 0.0),
                            "turnover": float(row.get("turnover", 0.0) or 0.0),
                            "source": f"FILE:{path.name}",
                        }
                    )
                self.database.bulk_upsert(
                    session,
                    MarketBar,
                    records,
                    key_columns=["symbol", "interval", "ts"],
                )
                count += len(records)
        return count

    def ingest_local_fundamentals(self) -> int:
        root = Path(self.settings.fundamental_data_dir)
        count = 0
        with self.database.session() as session:
            for path in sorted(root.rglob("*")):
                if path.suffix.lower() not in {".csv", ".parquet", ".pq", ".json"}:
                    continue
                df = _normalize_columns(_read_tabular_file(path), FUNDAMENTAL_COLUMN_ALIASES)
                if "symbol" not in df.columns or "report_date" not in df.columns:
                    continue
                df["report_date"] = pd.to_datetime(df["report_date"], errors="coerce")
                df = df.dropna(subset=["symbol", "report_date"])
                records: list[dict[str, Any]] = []
                for _, row in df.iterrows():
                    payload = {str(key): _json_safe_value(value) for key, value in row.to_dict().items()}
                    records.append(
                        {
                            "symbol": str(row["symbol"]).upper(),
                            "company_name": str(row.get("company_name", row["symbol"])),
                            "sector": str(row.get("sector", "Others")),
                            "fiscal_period": str(row.get("fiscal_period", "")),
                            "report_date": row["report_date"].to_pydatetime(),
                            "eps": float(row.get("eps", 0.0) or 0.0),
                            "pe": float(row.get("pe", 0.0) or 0.0),
                            "pb": float(row.get("pb", 0.0) or 0.0),
                            "dividend_yield": float(row.get("dividend_yield", 0.0) or 0.0),
                            "revenue": float(row.get("revenue", 0.0) or 0.0),
                            "revenue_growth_yoy": float(row.get("revenue_growth_yoy", 0.0) or 0.0),
                            "revenue_growth_qoq": float(row.get("revenue_growth_qoq", 0.0) or 0.0),
                            "net_profit": float(row.get("net_profit", 0.0) or 0.0),
                            "net_profit_margin": float(row.get("net_profit_margin", 0.0) or 0.0),
                            "roe": float(row.get("roe", 0.0) or 0.0),
                            "roa": float(row.get("roa", 0.0) or 0.0),
                            "debt_to_equity": float(row.get("debt_to_equity", 0.0) or 0.0),
                            "current_ratio": float(row.get("current_ratio", 0.0) or 0.0),
                            "quick_ratio": float(row.get("quick_ratio", 0.0) or 0.0),
                            "book_value_per_share": float(row.get("book_value_per_share", 0.0) or 0.0),
                            "npl_ratio": None if pd.isna(row.get("npl_ratio")) else float(row.get("npl_ratio", 0.0)),
                            "casa_ratio": None if pd.isna(row.get("casa_ratio")) else float(row.get("casa_ratio", 0.0)),
                            "raw_payload": payload,
                        }
                    )
                self.database.bulk_upsert(
                    session,
                    FundamentalSnapshot,
                    records,
                    key_columns=["symbol", "report_date", "fiscal_period"],
                )
                count += len(records)
        return count

    def ingest_local_macro_series(self) -> int:
        root = Path(self.settings.macro_data_dir)
        count = 0
        with self.database.session() as session:
            for path in sorted(root.rglob("*")):
                if path.suffix.lower() not in {".csv", ".parquet", ".pq", ".json"}:
                    continue
                df = _read_tabular_file(path)
                df = _normalize_columns(
                    df,
                    {
                        "series_name": ["series_name", "series", "name"],
                        "date": ["date", "timestamp", "ts"],
                        "value": ["value", "close", "rate"],
                        "units": ["units", "unit"],
                        "source": ["source"],
                    },
                )
                if "date" not in df.columns or "value" not in df.columns:
                    continue
                series_name = str(df.get("series_name", pd.Series([path.stem])).iloc[0] if "series_name" in df.columns else path.stem).upper()
                df["date"] = pd.to_datetime(df["date"], errors="coerce")
                df = df.dropna(subset=["date", "value"])
                records = [
                    {
                        "series_name": series_name,
                        "ts": row["date"].to_pydatetime(),
                        "value": float(row["value"]),
                        "units": str(row.get("units", "")),
                        "source": str(row.get("source", f"FILE:{path.name}")),
                        "metadata_json": {},
                    }
                    for _, row in df.iterrows()
                ]
                self.database.bulk_upsert(
                    session,
                    MacroSeriesPoint,
                    records,
                    key_columns=["series_name", "ts"],
                )
                count += len(records)
        return count

    def ingest_local_news(self) -> int:
        root = Path(self.settings.news_data_dir)
        count = 0
        with self.database.session() as session:
            for path in sorted(root.rglob("*")):
                if path.suffix.lower() == ".jsonl":
                    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
                    df = pd.DataFrame(rows)
                elif path.suffix.lower() in {".csv", ".json"}:
                    df = _read_tabular_file(path)
                else:
                    continue
                df = _normalize_columns(df, NEWS_COLUMN_ALIASES)
                if "source_url" not in df.columns or "published_at" not in df.columns:
                    continue
                df["published_at"] = pd.to_datetime(df["published_at"], errors="coerce")
                df = df.dropna(subset=["source_url", "published_at"])
                records = [
                    {
                        "source": str(row.get("source", path.stem)),
                        "source_url": str(row["source_url"]),
                        "symbol": None if pd.isna(row.get("symbol")) else str(row.get("symbol", "")).upper(),
                        "language": str(row.get("language", "en")),
                        "title": str(row.get("title", "")),
                        "body": str(row.get("body", "")),
                        "published_at": row["published_at"].to_pydatetime(),
                        "sentiment_score": float(row.get("sentiment_score", 0.0) or 0.0),
                        "entities_json": [],
                    }
                    for _, row in df.iterrows()
                ]
                self.database.bulk_upsert(
                    session,
                    NewsArticle,
                    records,
                    key_columns=["source_url"],
                )
                count += len(records)
        return count

    def _bootstrap_history(self, stock: dict[str, Any], as_of: datetime) -> list[dict[str, Any]]:
        rng = stable_rng("autonomous-bootstrap", stock.get("symbol"), stock.get("cmp"), stock.get("volume"))
        days = self.settings.bootstrap_sequence_days
        close = float(stock.get("cmp", 0.0) or 0.0)
        previous_close = float(stock.get("previousClose", close) or close)
        if close <= 0:
            return []
        volatility = 0.01 + min(0.06, abs(close - previous_close) / max(close, 1e-9))
        base = close * (0.82 + rng.random() * 0.12)
        records: list[dict[str, Any]] = []
        for offset in range(days, 0, -1):
            ts = as_of - timedelta(days=offset)
            if ts.weekday() == 5:
                continue
            trend = (days - offset) / days * rng.uniform(-0.06, 0.16)
            noise = rng.normal(0, volatility)
            base *= max(0.4, 1 + trend / max(days / 2, 1) + noise)
            high = base * (1 + abs(rng.normal(0.005, volatility / 2)))
            low = base * (1 - abs(rng.normal(0.005, volatility / 2)))
            open_price = low + rng.random() * max(high - low, 0.1)
            close_price = low + rng.random() * max(high - low, 0.1)
            volume = float(stock.get("avgVolume20d", stock.get("volume", 0.0)) or 0.0) * (0.6 + rng.random() * 0.8)
            records.append(
                {
                    "symbol": str(stock.get("symbol", "")).upper(),
                    "company_name": str(stock.get("name", stock.get("symbol", ""))),
                    "sector": str(stock.get("sector", "Others")),
                    "interval": "1d",
                    "ts": ts,
                    "open": round(open_price, 2),
                    "high": round(max(high, open_price, close_price), 2),
                    "low": round(min(low, open_price, close_price), 2),
                    "close": round(close_price, 2),
                    "volume": round(volume, 2),
                    "turnover": round(volume * close_price, 2),
                    "source": "SIMULATED_BOOTSTRAP",
                }
            )
        if records:
            records[-1]["close"] = round(close, 2)
            records[-1]["open"] = round(float(stock.get("open", close) or close), 2)
            records[-1]["high"] = round(float(stock.get("high", close) or close), 2)
            records[-1]["low"] = round(float(stock.get("low", close) or close), 2)
            records[-1]["volume"] = round(float(stock.get("volume", records[-1]["volume"]) or records[-1]["volume"]), 2)
            records[-1]["turnover"] = round(float(stock.get("turnover", records[-1]["turnover"]) or records[-1]["turnover"]), 2)
        return records

    def refresh_live_snapshot(self) -> dict[str, int]:
        stocks_payload = _run_sync(fetch_all_stocks())
        index_payload = _run_sync(fetch_nepse_index_history(days=self.settings.default_history_lookback_days))
        market_payload = _run_sync(fetch_market_overview())

        stocks = stocks_payload.get("stocks", [])
        now = datetime.utcnow()
        stock_records: list[dict[str, Any]] = []
        bootstrap_records: list[dict[str, Any]] = []
        with self.database.session() as session:
            existing_symbols = {
                symbol
                for (symbol,) in session.query(MarketBar.symbol).distinct().all()
            }
            for stock in stocks:
                close = float(stock.get("cmp", 0.0) or 0.0)
                if close <= 0:
                    continue
                stock_records.append(
                    {
                        "symbol": str(stock.get("symbol", "")).upper(),
                        "company_name": str(stock.get("name", stock.get("symbol", ""))),
                        "sector": str(stock.get("sector", "Others")),
                        "interval": "1d",
                        "ts": now,
                        "open": float(stock.get("open", close) or close),
                        "high": float(stock.get("high", close) or close),
                        "low": float(stock.get("low", close) or close),
                        "close": close,
                        "volume": float(stock.get("volume", 0.0) or 0.0),
                        "turnover": float(stock.get("turnover", 0.0) or 0.0),
                        "source": str(stocks_payload.get("source", "LIVE")),
                    }
                )
                if self.settings.allow_bootstrap_simulation and str(stock.get("symbol", "")).upper() not in existing_symbols:
                    bootstrap_records.extend(self._bootstrap_history(stock, now))

            self.database.bulk_upsert(
                session,
                MarketBar,
                bootstrap_records + stock_records,
                key_columns=["symbol", "interval", "ts"],
            )

            index_history = index_payload.get("history", [])
            index_records = [
                {
                    "symbol": "NEPSE_INDEX",
                    "company_name": "NEPSE Index",
                    "sector": "Index",
                    "interval": "1d",
                    "ts": pd.to_datetime(item["date"]).to_pydatetime(),
                    "open": float(item.get("open", item.get("close", 0.0))),
                    "high": float(item.get("high", item.get("close", 0.0))),
                    "low": float(item.get("low", item.get("close", 0.0))),
                    "close": float(item.get("close", 0.0)),
                    "volume": float(item.get("volume", 0.0) or 0.0),
                    "turnover": float(item.get("turnover", 0.0) or 0.0),
                    "source": str(index_payload.get("source", "LIVE")),
                }
                for item in index_history
                if item.get("date")
            ]
            self.database.bulk_upsert(
                session,
                MarketBar,
                index_records,
                key_columns=["symbol", "interval", "ts"],
            )

            market_data = market_payload.get("data", {})
            macro_records = []
            mapping = {
                "NRB_POLICY_RATE": market_data.get("interbank_rate"),
                "NEPSE_TBILL_91D": market_data.get("t_bill_yield"),
            }
            for series_name, value in mapping.items():
                if value is None:
                    continue
                macro_records.append(
                    {
                        "series_name": series_name,
                        "ts": now,
                        "value": float(value),
                        "units": "percent",
                        "source": str(market_payload.get("source", "LIVE")),
                        "metadata_json": {},
                    }
                )
            self.database.bulk_upsert(
                session,
                MacroSeriesPoint,
                macro_records,
                key_columns=["series_name", "ts"],
            )

        return {
            "stocks": len(stock_records),
            "bootstrap_bars": len(bootstrap_records),
            "index_bars": len(index_payload.get("history", [])),
        }

    def run_full_cycle(self) -> dict[str, int]:
        summary = {
            "market_rows": self.ingest_local_market_data(),
            "fundamental_rows": self.ingest_local_fundamentals(),
            "macro_rows": self.ingest_local_macro_series(),
            "news_rows": self.ingest_local_news(),
        }
        live_summary = self.refresh_live_snapshot()
        summary.update({f"live_{key}": value for key, value in live_summary.items()})
        logger.info("Autonomous ingestion cycle summary: %s", summary)
        return summary
