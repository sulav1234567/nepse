"""
Internet-backed training data builder for the autonomous NEPSE research platform.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime
from io import StringIO
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urljoin

import httpx
import pandas as pd
from bs4 import BeautifulSoup

from ..nepse_fetcher import SHARESANSAR_HEADERS, SHARESANSAR_SSL_VERIFY, fetch_all_stocks
from ..settings import Settings, get_settings

logger = logging.getLogger("nepse-alpha.autonomous.internet-data")

SHARESANSAR_COMPANY_BASE = "https://www.sharesansar.com/company"
SHARESANSAR_PRICE_HISTORY_URL = "https://www.sharesansar.com/company-price-history"
SHARESANSAR_QUARTERLY_URL = "https://www.sharesansar.com/company-quarterly-report"
SHARESANSAR_COMPANY_NEWS_URL = "https://www.sharesansar.com/company-news-category"
SHARESANSAR_ANNOUNCEMENT_URL = "https://www.sharesansar.com/company-announcement-category"
SHARESANSAR_INDEX_URL = "https://www.sharesansar.com/indices-sub-indices"
SHARESANSAR_LATEST_NEWS_URL = "https://www.sharesansar.com/category/latest"
YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
NRB_FOREX_URL = "https://www.nrb.org.np/api/forex/v1/rates"
WORLD_BANK_INDICATOR_URL = "https://api.worldbank.org/v2/country/NPL/indicator/BX.TRF.PWKR.CD.DT"

POSITIVE_TOKENS = {
    "bullish",
    "bonus",
    "buy",
    "cash dividend",
    "expand",
    "expansion",
    "gain",
    "growth",
    "improve",
    "improved",
    "improvement",
    "profit",
    "record",
    "renewal",
    "rise",
    "strong",
    "surge",
    "up",
    "लाभ",
    "बृद्धि",
    "सकारात्मक",
    "मुनाफा",
}
NEGATIVE_TOKENS = {
    "bearish",
    "correction",
    "crisis",
    "decline",
    "default",
    "delay",
    "drop",
    "fall",
    "fraud",
    "loss",
    "negative",
    "penalty",
    "probe",
    "sell",
    "selloff",
    "slump",
    "weak",
    "घाटा",
    "कमजोर",
    "नकारात्मक",
    "असुली",
}

YAHOO_MACRO_SERIES = {
    "NIFTY50": "^NSEI",
    "SENSEX": "^BSESN",
    "INDIA_VIX": "^INDIAVIX",
    "SP500": "^GSPC",
    "NASDAQ": "^IXIC",
    "DXY": "DX-Y.NYB",
    "SHANGHAI": "000001.SS",
    "HANG_SENG": "^HSI",
    "CRUDE_OIL": "CL=F",
    "GOLD_USD": "GC=F",
    "BTC_SENTIMENT": "BTC-USD",
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


def _slugify(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", text.strip().upper()) or "UNKNOWN"


def _parse_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text or text in {"-", "--", "N/A", "n/a", "None"}:
        return default
    text = (
        text.replace("&nbsp;", " ")
        .replace("\xa0", " ")
        .replace(",", "")
        .replace("%", "")
        .replace("Rs.", "")
        .replace("Rs", "")
        .replace("times", "")
    )
    cleaned = re.sub(r"[^0-9.\-]", "", text)
    if cleaned in {"", ".", "-", "-."}:
        return default
    try:
        return float(cleaned)
    except ValueError:
        return default


def _safe_datetime(value: Any) -> Optional[datetime]:
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return None
    if hasattr(parsed, "to_pydatetime"):
        return parsed.to_pydatetime()
    return None


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _normalize_label(label: Any) -> str:
    text = str(label or "").lower()
    text = BeautifulSoup(text, "lxml").get_text(" ", strip=True)
    text = text.replace("&", "and")
    text = re.sub(r"\(.*?\)", " ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def _score_sentiment(text: str) -> float:
    lowered = text.lower()
    positive_hits = sum(token in lowered for token in POSITIVE_TOKENS)
    negative_hits = sum(token in lowered for token in NEGATIVE_TOKENS)
    if positive_hits == 0 and negative_hits == 0:
        return 0.0
    raw = (positive_hits - negative_hits) / max(positive_hits + negative_hits, 1)
    return round(float(max(-1.0, min(1.0, raw))), 4)


def _extract_date_from_url(url: str) -> Optional[str]:
    match = re.search(r"(\d{4}-\d{2}-\d{2})(?:[/?#]|$)", url)
    return match.group(1) if match else None


def _lookup_value(mapping: dict[str, float], patterns: tuple[str, ...]) -> float:
    for label, value in mapping.items():
        if any(pattern in label for pattern in patterns):
            return value
    return 0.0


@dataclass
class CompanyContext:
    symbol: str
    company_id: str
    company_name: str
    sector: str
    url: str
    csrf_token: str
    cash_dividend_percent: float
    paid_up_value: float
    latest_close: float


class InternetTrainingDataBuilder:
    """Downloads training corpora from public internet sources into the data folders."""

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or get_settings()
        self.market_root = Path(self.settings.historical_data_dir)
        self.market_stocks_dir = self.market_root / "stocks"
        self.market_indices_dir = self.market_root / "indices"
        self.fundamental_root = Path(self.settings.fundamental_data_dir)
        self.macro_root = Path(self.settings.macro_data_dir)
        self.news_root = Path(self.settings.news_data_dir)
        self.manifest_root = Path("./data/manifests")
        self.request_delay_seconds = 0.05
        self.headers = dict(SHARESANSAR_HEADERS)
        self.headers.setdefault("User-Agent", "Mozilla/5.0")
        self.headers.setdefault("Accept-Language", "en-US,en;q=0.9")
        self.market_stocks_dir.mkdir(parents=True, exist_ok=True)
        self.market_indices_dir.mkdir(parents=True, exist_ok=True)
        self.fundamental_root.mkdir(parents=True, exist_ok=True)
        self.macro_root.mkdir(parents=True, exist_ok=True)
        self.news_root.mkdir(parents=True, exist_ok=True)
        self.manifest_root.mkdir(parents=True, exist_ok=True)

    def build(
        self,
        profile: str = "advanced",
        symbol_limit: Optional[int] = None,
        refresh: bool = False,
        market_news_pages: int = 5,
        market_article_body_limit: int = 30,
    ) -> dict[str, Any]:
        started_at = datetime.utcnow()
        requested_profile = profile.lower().strip()
        if requested_profile not in {"high_level", "advanced"}:
            raise ValueError("profile must be either 'high_level' or 'advanced'")

        fundamentals_file = self.fundamental_root / "sharesansar_quarterly_snapshots.csv"
        news_file = self.news_root / "sharesansar_news.jsonl"
        if refresh:
            for path in (fundamentals_file, news_file):
                if path.exists():
                    path.unlink()

        universe_payload = _run_sync(fetch_all_stocks())
        stock_rows = universe_payload.get("stocks", []) if isinstance(universe_payload, dict) else []
        stocks = [row for row in stock_rows if str(row.get("symbol", "")).strip()]
        stocks = sorted(stocks, key=lambda row: str(row.get("symbol", "")))
        if symbol_limit is not None:
            stocks = stocks[: max(0, symbol_limit)]

        universe_df = pd.DataFrame(stocks)
        if not universe_df.empty:
            universe_df.to_csv(self.market_root / "universe_snapshot.csv", index=False)

        symbol_price_map = {
            str(row.get("symbol", "")).upper(): _parse_float(row.get("cmp"))
            for row in stocks
        }

        summary = {
            "profile": requested_profile,
            "started_at": started_at.isoformat(),
            "symbols_requested": len(stocks),
            "market_files_written": 0,
            "market_files_skipped": 0,
            "fundamental_rows_written": 0,
            "news_rows_written": 0,
            "macro_files_written": 0,
            "failed_symbols": [],
            "sources": {
                "market": "ShareSansar company-price-history",
                "fundamentals": "ShareSansar company-quarterly-report",
                "news": "ShareSansar company-news-category / company-announcement-category / category/latest",
                "macro": "Yahoo Finance chart endpoint / NRB official forex API / World Bank indicator API",
            },
        }

        try:
            market_news_rows = self._fetch_market_news(
                pages=market_news_pages,
                body_limit=market_article_body_limit if requested_profile == "advanced" else 0,
            )
        except Exception as exc:
            logger.warning("Skipping market-news build because ShareSansar latest-news fetch failed: %s", exc)
            market_news_rows = []
        company_news_rows: list[dict[str, Any]] = []
        fundamentals_rows: list[dict[str, Any]] = []

        with httpx.Client(
            verify=SHARESANSAR_SSL_VERIFY,
            follow_redirects=True,
            timeout=30.0,
            headers=self.headers,
        ) as client:
            for index, stock in enumerate(stocks, start=1):
                symbol = str(stock.get("symbol", "")).upper().strip()
                if not symbol:
                    continue
                logger.info("Building %s dataset for %s (%s/%s)", requested_profile, symbol, index, len(stocks))

                try:
                    context = self._resolve_company_context(client, stock)
                    if context is None:
                        summary["failed_symbols"].append(symbol)
                        continue

                    market_path = self.market_stocks_dir / f"{_slugify(symbol)}.csv"
                    if refresh or not market_path.exists():
                        history_frame = self._fetch_company_price_history(client, context)
                        if history_frame.empty:
                            summary["failed_symbols"].append(symbol)
                        else:
                            history_frame.to_csv(market_path, index=False)
                            summary["market_files_written"] += 1
                    else:
                        summary["market_files_skipped"] += 1

                    if requested_profile == "advanced":
                        fundamental_row = self._fetch_quarterly_snapshot(client, context, stock)
                        latest_news_rows = self._fetch_company_news(client, context)
                        if latest_news_rows:
                            company_news_rows.extend(latest_news_rows)
                            latest_published = max(
                                (_safe_datetime(item.get("published_at")) for item in latest_news_rows),
                                default=None,
                            )
                            if fundamental_row is not None and latest_published is not None:
                                fundamental_row["report_date"] = latest_published.date().isoformat()
                        if fundamental_row is not None:
                            fundamentals_rows.append(fundamental_row)

                    time.sleep(self.request_delay_seconds)
                except Exception as exc:
                    logger.warning("Failed building internet dataset for %s: %s", symbol, exc)
                    summary["failed_symbols"].append(symbol)

        try:
            index_rows = self._fetch_nepse_index_history_full()
        except Exception as exc:
            logger.warning("Skipping NEPSE index history build because Sharesansar index fetch failed: %s", exc)
            index_rows = []
        if index_rows:
            pd.DataFrame(index_rows).to_csv(self.market_indices_dir / "NEPSE_INDEX.csv", index=False)

        macro_files_written = self._write_macro_series()
        summary["macro_files_written"] = macro_files_written

        if requested_profile == "advanced" and fundamentals_rows:
            summary["fundamental_rows_written"] = self._merge_csv_rows(
                fundamentals_file,
                fundamentals_rows,
                key_columns=["symbol", "fiscal_period"],
                sort_columns=["symbol", "report_date"],
            )

        all_news_rows = market_news_rows + company_news_rows
        if all_news_rows:
            summary["news_rows_written"] = self._merge_jsonl_rows(
                news_file,
                all_news_rows,
                key_field="source_url",
            )

        finished_at = datetime.utcnow()
        summary["finished_at"] = finished_at.isoformat()
        summary["duration_seconds"] = round((finished_at - started_at).total_seconds(), 2)
        summary["nepse_index_rows"] = len(index_rows)
        summary["limitations"] = [
            "Public internet sources currently expose about 26 years of NEPSE index history starting around 2000-01-03, not a full 40-50 year institutional archive.",
            "ShareSansar quarterly-report pages provide the latest available quarterly snapshot per company; they are valuable for advanced scoring but not a perfect historical statement warehouse.",
        ]

        manifest_path = self.manifest_root / f"{requested_profile}_training_data_manifest.json"
        manifest_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False, default=_json_default), encoding="utf-8")
        return summary

    def _resolve_company_context(self, client: httpx.Client, stock: dict[str, Any]) -> Optional[CompanyContext]:
        symbol = str(stock.get("symbol", "")).upper().strip()
        if not symbol:
            return None
        company_url = f"{SHARESANSAR_COMPANY_BASE}/{symbol}"
        response = client.get(company_url)
        response.raise_for_status()
        html = response.text
        soup = BeautifulSoup(html, "lxml")

        token_node = soup.select_one("meta[name=\"_token\"]")
        if token_node is None:
            raise ValueError(f"Missing CSRF token for {symbol}")

        company_id_match = re.search(r'id="companyid"[^>]*>([^<]+)<', html, flags=re.IGNORECASE)
        sector_match = re.search(r'id="sector"[^>]*>([^<]+)<', html, flags=re.IGNORECASE)
        if company_id_match is None:
            raise ValueError(f"Missing company id for {symbol}")

        header_node = soup.select_one("h1")
        company_name = str(stock.get("name", "")).strip()
        if not company_name and header_node is not None:
            company_name = " ".join(header_node.get_text(" ", strip=True).split())
            company_name = re.sub(r"\(\s*%s\s*\)$" % re.escape(symbol), "", company_name).strip()

        sector = str(stock.get("sector", "")).strip() or sector_match.group(1).strip() if sector_match else "Others"
        cash_dividend_match = re.search(r"Cash Dividend\s+([0-9.]+)\s*%", html, flags=re.IGNORECASE)
        paid_up_match = re.search(r"Paid Up\s+Rs\.\s*([0-9,]+(?:\.\d+)?)", html, flags=re.IGNORECASE)
        latest_close = _parse_float(stock.get("cmp"))

        return CompanyContext(
            symbol=symbol,
            company_id=company_id_match.group(1).strip(),
            company_name=company_name or symbol,
            sector=sector or "Others",
            url=company_url,
            csrf_token=token_node.get("content", ""),
            cash_dividend_percent=_parse_float(cash_dividend_match.group(1)) if cash_dividend_match else 0.0,
            paid_up_value=_parse_float(paid_up_match.group(1), 100.0) if paid_up_match else 100.0,
            latest_close=latest_close,
        )

    def _datatable_post(
        self,
        client: httpx.Client,
        url: str,
        *,
        referer: str,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        headers = {
            "X-CSRF-Token": str(data.pop("_csrf_token")),
            "X-Requested-With": "XMLHttpRequest",
            "Referer": referer,
            "User-Agent": self.headers["User-Agent"],
        }
        last_exception: Optional[Exception] = None
        for attempt in range(3):
            try:
                response = client.post(url, headers=headers, data=data)
                if response.status_code == 202:
                    time.sleep(0.8 * (attempt + 1))
                    continue
                response.raise_for_status()
                return response.json()
            except Exception as exc:
                last_exception = exc
                time.sleep(0.6 * (attempt + 1))
        raise RuntimeError(f"Failed calling {url}: {last_exception}")

    def _fetch_company_price_history(self, client: httpx.Client, context: CompanyContext) -> pd.DataFrame:
        payload = self._datatable_post(
            client,
            SHARESANSAR_PRICE_HISTORY_URL,
            referer=context.url,
            data={
                "_csrf_token": context.csrf_token,
                "company": context.company_id,
                "draw": 1,
                "start": 0,
                "length": -1,
            },
        )
        rows = payload.get("data", [])
        if not isinstance(rows, list) or not rows:
            return pd.DataFrame()

        records = [
            {
                "symbol": context.symbol,
                "company_name": context.company_name,
                "sector": context.sector,
                "date": row.get("published_date"),
                "open": _parse_float(row.get("open")),
                "high": _parse_float(row.get("high")),
                "low": _parse_float(row.get("low")),
                "close": _parse_float(row.get("close")),
                "volume": _parse_float(row.get("traded_quantity")),
                "turnover": _parse_float(row.get("traded_amount")),
                "change_percent": _parse_float(row.get("per_change")),
                "source": "SHARESANSAR_PRICE_HISTORY",
                "source_url": context.url,
            }
            for row in rows
            if row.get("published_date")
        ]
        frame = pd.DataFrame(records)
        if frame.empty:
            return frame
        frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
        frame = frame.dropna(subset=["date"])
        frame = frame.sort_values("date").drop_duplicates(subset=["symbol", "date"], keep="last")
        frame["date"] = frame["date"].dt.strftime("%Y-%m-%d")
        return frame

    def _fetch_quarterly_snapshot(
        self,
        client: httpx.Client,
        context: CompanyContext,
        stock: dict[str, Any],
    ) -> Optional[dict[str, Any]]:
        response = client.post(
            SHARESANSAR_QUARTERLY_URL,
            headers={
                "X-CSRF-Token": context.csrf_token,
                "X-Requested-With": "XMLHttpRequest",
                "Referer": context.url,
                "User-Agent": self.headers["User-Agent"],
            },
            data={
                "company": context.company_id,
                "symbol": context.symbol,
                "sector": context.sector,
            },
        )
        response.raise_for_status()
        html = response.text
        if "no data available" in html.lower():
            return None

        try:
            tables = pd.read_html(StringIO(html))
        except ValueError:
            return None
        if len(tables) < 3:
            return None

        balance_table, profit_table, metrics_table = tables[0], tables[1], tables[2]
        if balance_table.empty or profit_table.empty or metrics_table.empty:
            return None

        fiscal_period = str(metrics_table.columns[-1]) if len(metrics_table.columns) > 1 else ""

        balance_map = self._table_to_metric_map(balance_table)
        profit_map = self._table_to_metric_map(profit_table)
        metrics_map = self._table_to_metric_map(metrics_table)

        revenue = _lookup_value(
            profit_map,
            (
                "total operating income",
                "revenue from operations",
                "revenue",
                "net premiums earned",
                "gross income",
                "net interest fee and commission income",
            ),
        )
        net_profit = _lookup_value(
            profit_map,
            (
                "profit for the period",
                "profit after tax",
                "net profit",
                "net income",
                "profit for the year",
            ),
        )
        equity = _lookup_value(
            metrics_map,
            (
                "total shareholders equity",
                "shareholders equity",
                "total equity",
            ),
        )
        if equity <= 0:
            equity = _lookup_value(
                balance_map,
                (
                    "total equity",
                    "equity attributable to equity holders",
                    "shareholders equity",
                    "total shareholder s equity",
                ),
            )
        total_assets = _lookup_value(balance_map, ("total assets",))
        total_liabilities = _lookup_value(balance_map, ("total liabilities",))
        if total_liabilities <= 0 and total_assets > 0 and equity > 0:
            total_liabilities = max(total_assets - equity, 0.0)

        current_assets = _lookup_value(balance_map, ("current assets",))
        current_liabilities = _lookup_value(balance_map, ("current liabilities",))
        inventory = _lookup_value(balance_map, ("inventories", "inventory"))

        eps = _lookup_value(
            metrics_map,
            (
                "basic earnings per share annualized eps",
                "basic earnings per share",
                "annualized eps",
                "eps",
            ),
        )
        pe = _lookup_value(metrics_map, ("p e ratio", "pe ratio", "price earnings"))
        pb = _lookup_value(metrics_map, ("price to book", "p b ratio", "price book"))
        roe = _lookup_value(metrics_map, ("return on equity",))
        roa = _lookup_value(metrics_map, ("return on assets",))
        npl_ratio = _lookup_value(metrics_map, ("non performing loan", "npl"))
        casa_ratio = _lookup_value(metrics_map, ("casa", "current and savings"))
        book_value = _lookup_value(metrics_map, ("net worth per share", "book value per share"))
        if book_value <= 0 and equity > 0:
            shares_outstanding = _lookup_value(metrics_map, ("outstanding shares", "no of outstanding shares"))
            if shares_outstanding > 0:
                book_value = equity / shares_outstanding

        dividend_per_share = (context.cash_dividend_percent / 100.0) * max(context.paid_up_value, 0.0)
        dividend_yield = (dividend_per_share / context.latest_close * 100.0) if context.latest_close > 0 else 0.0

        debt_to_equity = (total_liabilities / equity) if equity > 0 else 0.0
        current_ratio = (current_assets / current_liabilities) if current_assets > 0 and current_liabilities > 0 else 0.0
        quick_ratio = ((current_assets - inventory) / current_liabilities) if current_assets > 0 and current_liabilities > 0 else 0.0
        net_profit_margin = (net_profit / revenue * 100.0) if revenue > 0 else 0.0

        latest_price = _parse_float(stock.get("cmp"), context.latest_close)
        if pe <= 0 and eps > 0 and latest_price > 0:
            pe = latest_price / eps
        if pb <= 0 and book_value > 0 and latest_price > 0:
            pb = latest_price / book_value

        if (
            fiscal_period.strip().lower() == "duration"
            or max(abs(eps), abs(pe), abs(pb), abs(revenue), abs(net_profit), abs(roe), abs(roa), abs(book_value)) == 0.0
        ):
            return None

        return {
            "symbol": context.symbol,
            "company_name": context.company_name,
            "sector": context.sector,
            "fiscal_period": fiscal_period,
            "report_date": datetime.utcnow().date().isoformat(),
            "eps": round(eps, 4),
            "pe": round(pe, 4),
            "pb": round(pb, 4),
            "dividend_yield": round(dividend_yield, 4),
            "revenue": round(revenue, 4),
            "revenue_growth_yoy": 0.0,
            "revenue_growth_qoq": 0.0,
            "net_profit": round(net_profit, 4),
            "net_profit_margin": round(net_profit_margin, 4),
            "roe": round(roe, 4),
            "roa": round(roa, 4),
            "debt_to_equity": round(debt_to_equity, 4),
            "current_ratio": round(current_ratio, 4),
            "quick_ratio": round(quick_ratio, 4),
            "book_value_per_share": round(book_value, 4),
            "npl_ratio": round(npl_ratio, 4) if npl_ratio > 0 else None,
            "casa_ratio": round(casa_ratio, 4) if casa_ratio > 0 else None,
            "source": "SHARESANSAR_QUARTERLY_REPORT",
            "source_url": context.url,
        }

    def _table_to_metric_map(self, frame: pd.DataFrame) -> dict[str, float]:
        if frame.empty or len(frame.columns) < 2:
            return {}
        label_column = frame.columns[0]
        value_column = frame.columns[-1]
        mapping: dict[str, float] = {}
        for _, row in frame.iterrows():
            normalized = _normalize_label(row.get(label_column))
            if not normalized:
                continue
            mapping[normalized] = _parse_float(row.get(value_column))
        return mapping

    def _fetch_company_news(self, client: httpx.Client, context: CompanyContext) -> list[dict[str, Any]]:
        category_specs = [
            (SHARESANSAR_COMPANY_NEWS_URL, 19, "ShareSansar Company Analysis"),
            (SHARESANSAR_ANNOUNCEMENT_URL, 11, "ShareSansar Company Announcement"),
        ]
        items: list[dict[str, Any]] = []
        for url, category, source_name in category_specs:
            payload = self._datatable_post(
                client,
                url,
                referer=context.url,
                data={
                    "_csrf_token": context.csrf_token,
                    "company": context.company_id,
                    "category": category,
                    "draw": 1,
                    "start": 0,
                    "length": -1,
                },
            )
            rows = payload.get("data", [])
            if not isinstance(rows, list):
                continue
            for row in rows:
                title_html = str(row.get("title", ""))
                title_soup = BeautifulSoup(title_html, "lxml")
                anchor = title_soup.find("a")
                title_text = " ".join(title_soup.get_text(" ", strip=True).split())
                href = anchor.get("href") if anchor else str(row.get("slug", ""))
                if not href:
                    continue
                source_url = urljoin("https://www.sharesansar.com", href)
                published_at = str(row.get("published_date") or _extract_date_from_url(source_url) or datetime.utcnow().date().isoformat())
                body = title_text
                items.append(
                    {
                        "source": source_name,
                        "source_url": source_url,
                        "symbol": context.symbol,
                        "language": "en",
                        "title": title_text,
                        "body": body,
                        "published_at": published_at,
                        "sentiment_score": _score_sentiment(f"{title_text} {body}"),
                    }
                )
        return items

    def _fetch_market_news(self, pages: int, body_limit: int) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        with httpx.Client(follow_redirects=True, timeout=30.0, headers=self.headers) as client:
            for page in range(1, max(1, pages) + 1):
                url = SHARESANSAR_LATEST_NEWS_URL if page == 1 else f"{SHARESANSAR_LATEST_NEWS_URL}?page={page}"
                response = client.get(url)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, "lxml")
                for anchor in soup.select('a[href*="/newsdetail/"]'):
                    href = anchor.get("href", "").strip()
                    if not href:
                        continue
                    source_url = urljoin("https://www.sharesansar.com", href)
                    if source_url in seen:
                        continue
                    if _extract_date_from_url(source_url) is None:
                        continue
                    title = " ".join(anchor.get_text(" ", strip=True).split())
                    if not title:
                        continue
                    seen.add(source_url)
                    rows.append(
                        {
                            "source": "ShareSansar Latest",
                            "source_url": source_url,
                            "symbol": None,
                            "language": "en",
                            "title": title,
                            "body": title,
                            "published_at": _extract_date_from_url(source_url) or datetime.utcnow().date().isoformat(),
                            "sentiment_score": _score_sentiment(title),
                        }
                    )

            rows.sort(key=lambda item: (str(item.get("published_at", "")), str(item.get("source_url", ""))), reverse=True)
            for item in rows[: max(0, body_limit)]:
                try:
                    article_response = client.get(item["source_url"])
                    article_response.raise_for_status()
                    article_soup = BeautifulSoup(article_response.text, "lxml")
                    body_node = article_soup.select_one("#newsdetail-content")
                    if body_node is not None:
                        body = " ".join(body_node.get_text(" ", strip=True).split())
                        item["body"] = body or item["title"]
                        item["sentiment_score"] = _score_sentiment(f"{item['title']} {item['body']}")
                except Exception as exc:
                    logger.debug("Skipping market-news body fetch for %s: %s", item["source_url"], exc)
        return rows

    def _fetch_nepse_index_history_full(self) -> list[dict[str, Any]]:
        today = datetime.utcnow().date().isoformat()
        response = httpx.get(
            SHARESANSAR_INDEX_URL,
            params={
                "index_id": 12,
                "from": "2000-01-01",
                "to": today,
                "draw": 1,
                "start": 0,
                "length": -1,
            },
            headers={
                "X-Requested-With": "XMLHttpRequest",
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "Referer": SHARESANSAR_INDEX_URL,
                "User-Agent": self.headers["User-Agent"],
            },
            follow_redirects=True,
            timeout=30.0,
            verify=SHARESANSAR_SSL_VERIFY,
        )
        response.raise_for_status()
        payload = response.json()
        rows = payload.get("data", []) if isinstance(payload, dict) else []
        if not isinstance(rows, list):
            return []
        result = [
            {
                "symbol": "NEPSE_INDEX",
                "company_name": "NEPSE Index",
                "sector": "Index",
                "date": row.get("published_date"),
                "open": _parse_float(row.get("open")),
                "high": _parse_float(row.get("high")),
                "low": _parse_float(row.get("low")),
                "close": _parse_float(row.get("current")),
                "volume": 0.0,
                "turnover": _parse_float(row.get("turnover")),
                "change_percent": _parse_float(row.get("per_change")),
                "source": "SHARESANSAR_NEPSE_INDEX",
                "source_url": SHARESANSAR_INDEX_URL,
            }
            for row in rows
            if row.get("published_date")
        ]
        result.sort(key=lambda item: str(item["date"]))
        return result

    def _write_macro_series(self) -> int:
        written = 0
        series_frames: dict[str, pd.DataFrame] = {}

        for series_name, ticker in YAHOO_MACRO_SERIES.items():
            try:
                frame = self._fetch_yahoo_series(series_name, ticker)
            except Exception as exc:
                logger.warning("Skipping macro series %s from Yahoo: %s", series_name, exc)
                continue
            if frame.empty:
                continue
            series_frames[series_name] = frame
            frame.to_csv(self.macro_root / f"{series_name}.csv", index=False)
            written += 1

        try:
            usd_npr = self._fetch_nrb_usd_npr_series()
        except Exception as exc:
            logger.warning("Skipping NRB USD/NPR series: %s", exc)
            usd_npr = pd.DataFrame()
        if not usd_npr.empty:
            series_frames["USD_NPR"] = usd_npr
            usd_npr.to_csv(self.macro_root / "USD_NPR.csv", index=False)
            written += 1

        if "GOLD_USD" in series_frames and "USD_NPR" in series_frames:
            gold_npr = self._derive_gold_npr(series_frames["GOLD_USD"], series_frames["USD_NPR"])
            if not gold_npr.empty:
                gold_npr.to_csv(self.macro_root / "GOLD_NPR.csv", index=False)
                written += 1

        try:
            remittance_growth = self._fetch_world_bank_remittance_growth()
        except Exception as exc:
            logger.warning("Skipping World Bank remittance series: %s", exc)
            remittance_growth = pd.DataFrame()
        if not remittance_growth.empty:
            remittance_growth.to_csv(self.macro_root / "REMITTANCE_GROWTH.csv", index=False)
            written += 1

        return written

    def _fetch_yahoo_series(self, series_name: str, ticker: str) -> pd.DataFrame:
        url = YAHOO_CHART_URL.format(ticker=ticker)
        response = httpx.get(
            url,
            params={"interval": "1d", "range": "max", "includeAdjustedClose": "true"},
            headers={"User-Agent": self.headers["User-Agent"]},
            timeout=30.0,
            follow_redirects=True,
        )
        response.raise_for_status()
        payload = response.json()
        result = (((payload.get("chart") or {}).get("result") or [None])[0]) or {}
        timestamps = result.get("timestamp") or []
        indicators = (((result.get("indicators") or {}).get("quote") or [None])[0]) or {}
        closes = indicators.get("close") or []
        rows = []
        for timestamp, close in zip(timestamps, closes):
            if close is None:
                continue
            date = datetime.utcfromtimestamp(int(timestamp)).date().isoformat()
            rows.append(
                {
                    "series_name": series_name,
                    "date": date,
                    "value": float(close),
                    "units": "close",
                    "source": f"YAHOO:{ticker}",
                }
            )
        frame = pd.DataFrame(rows)
        if frame.empty:
            return frame
        frame = frame.drop_duplicates(subset=["date"]).sort_values("date")
        return frame

    def _fetch_nrb_usd_npr_series(self) -> pd.DataFrame:
        rows: list[dict[str, Any]] = []
        page = 1
        while True:
            response = httpx.get(
                NRB_FOREX_URL,
                params={
                    "from": "2019-01-01",
                    "to": datetime.utcnow().date().isoformat(),
                    "per_page": 100,
                    "page": page,
                },
                headers={"User-Agent": self.headers["User-Agent"]},
                timeout=30.0,
                follow_redirects=True,
            )
            response.raise_for_status()
            payload = response.json()
            payload_rows = (((payload.get("data") or {}).get("payload")) or [])
            if not payload_rows:
                break
            for item in payload_rows:
                date_value = item.get("date")
                rates = item.get("rates") or []
                usd_entry = next(
                    (
                        rate
                        for rate in rates
                        if str((((rate.get("currency") or {}).get("iso3") or (rate.get("currency") or {}).get("ISO3")) or "")).upper() == "USD"
                    ),
                    None,
                )
                if usd_entry is None or not date_value:
                    continue
                buy = _parse_float(usd_entry.get("buy"))
                sell = _parse_float(usd_entry.get("sell"))
                rows.append(
                    {
                        "series_name": "USD_NPR",
                        "date": str(date_value),
                        "value": round((buy + sell) / 2.0 if buy and sell else max(buy, sell), 6),
                        "units": "npr_per_usd",
                        "source": "NRB_FOREX_API",
                    }
                )
            pagination = payload.get("pagination") or {}
            total_pages = int(pagination.get("pages") or page)
            if page >= total_pages:
                break
            page += 1

        frame = pd.DataFrame(rows)
        if frame.empty:
            return frame
        frame = frame.drop_duplicates(subset=["date"]).sort_values("date")
        return frame

    def _derive_gold_npr(self, gold_usd: pd.DataFrame, usd_npr: pd.DataFrame) -> pd.DataFrame:
        gold = gold_usd.rename(columns={"value": "gold_usd"}).copy()
        fx = usd_npr.rename(columns={"value": "usd_npr"}).copy()
        merged = gold.merge(fx[["date", "usd_npr"]], on="date", how="inner")
        if merged.empty:
            return pd.DataFrame()
        merged["value"] = merged["gold_usd"] * merged["usd_npr"]
        return merged[["date", "value"]].assign(
            series_name="GOLD_NPR",
            units="npr_per_ounce",
            source="DERIVED:GOLD_USD*USD_NPR",
        )[["series_name", "date", "value", "units", "source"]]

    def _fetch_world_bank_remittance_growth(self) -> pd.DataFrame:
        response = httpx.get(
            WORLD_BANK_INDICATOR_URL,
            params={"format": "json", "per_page": 100},
            headers={"User-Agent": self.headers["User-Agent"]},
            timeout=30.0,
            follow_redirects=True,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list) or len(payload) < 2:
            return pd.DataFrame()
        rows = payload[1]
        if not isinstance(rows, list):
            return pd.DataFrame()

        series = pd.DataFrame(
            [
                {
                    "year": int(row.get("date")),
                    "value_raw": _parse_float(row.get("value")),
                }
                for row in rows
                if row.get("date") and row.get("value") is not None
            ]
        )
        if series.empty:
            return series
        series = series.sort_values("year")
        series["value"] = series["value_raw"].pct_change() * 100.0
        series = series.dropna(subset=["value"])
        return pd.DataFrame(
            {
                "series_name": "REMITTANCE_GROWTH",
                "date": series["year"].astype(str) + "-12-31",
                "value": series["value"].round(6),
                "units": "percent_yoy",
                "source": "WORLD_BANK_BX.TRF.PWKR.CD.DT",
            }
        )

    def _merge_csv_rows(
        self,
        path: Path,
        rows: list[dict[str, Any]],
        *,
        key_columns: list[str],
        sort_columns: Optional[list[str]] = None,
    ) -> int:
        incoming = pd.DataFrame(rows)
        if incoming.empty:
            return 0
        if path.exists():
            existing = pd.read_csv(path)
            combined = pd.concat([existing, incoming], ignore_index=True)
        else:
            combined = incoming
        combined = combined.drop_duplicates(subset=key_columns, keep="last")
        if sort_columns:
            combined = combined.sort_values(sort_columns)
        combined.to_csv(path, index=False)
        return len(combined)

    def _merge_jsonl_rows(self, path: Path, rows: list[dict[str, Any]], *, key_field: str) -> int:
        existing: dict[str, dict[str, Any]] = {}
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    continue
                key = str(item.get(key_field, "")).strip()
                if key:
                    existing[key] = item
        for row in rows:
            key = str(row.get(key_field, "")).strip()
            if key:
                existing[key] = row

        ordered_rows = sorted(
            existing.values(),
            key=lambda item: (str(item.get("published_at", "")), str(item.get("source_url", ""))),
        )
        with path.open("w", encoding="utf-8") as handle:
            for item in ordered_rows:
                handle.write(json.dumps(item, ensure_ascii=False, default=_json_default))
                handle.write("\n")
        return len(ordered_rows)
