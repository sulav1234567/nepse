"""
NEPSE-ALPHA ULTIMATE — Real-Time Data Fetcher
Primary source: Sharesansar web data (scraped + AJAX JSON)
Fallback source: NEPSE official API
"""

import httpx
import time
import logging
import certifi
import os
import re
from typing import Optional, Any, cast
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# NEPSE API currently presents TLS chains that often fail verification in local
# macOS Python environments. Allow override via env; default to False to keep
# live mode functional out of the box.
NEPSE_SSL_VERIFY = os.getenv("NEPSE_SSL_VERIFY", "false").lower() in ("1", "true", "yes")

SHARESANSAR_SSL_VERIFY = os.getenv("SHARESANSAR_SSL_VERIFY", "true").lower() in ("1", "true", "yes")
MEROLAGANI_SSL_VERIFY = os.getenv("MEROLAGANI_SSL_VERIFY", "true").lower() in ("1", "true", "yes")

# ─────────────────────────────────────────────────────────────────────────────
# CACHE LAYER
# ─────────────────────────────────────────────────────────────────────────────

class DataCache:
    """Simple in-memory cache with TTL."""
    def __init__(self, ttl_seconds: int = 30):  # Changed from 60 to 30 for more real-time data
        self.ttl = ttl_seconds
        self._cache: dict[str, Any] = {}
        self._timestamps: dict[str, float] = {}
        self._ttl_overrides: dict[str, int] = {}

    def get(self, key: str) -> Optional[Any]:
        if key in self._cache:
            ttl_seconds = self._ttl_overrides.get(key, self.ttl)
            if time.time() - self._timestamps[key] < ttl_seconds:
                return self._cache[key]
            else:
                del self._cache[key]
                del self._timestamps[key]
                self._ttl_overrides.pop(key, None)
        return None

    def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None):
        self._cache[key] = value
        self._timestamps[key] = time.time()
        if ttl_seconds is None:
            self._ttl_overrides.pop(key, None)
        else:
            self._ttl_overrides[key] = ttl_seconds

    def clear(self):
        self._cache.clear()
        self._timestamps.clear()
        self._ttl_overrides.clear()


cache = DataCache(ttl_seconds=60)


# ─────────────────────────────────────────────────────────────────────────────
# SHARESANSAR SCRAPER CLIENT
# ─────────────────────────────────────────────────────────────────────────────

SHARESANSAR_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://www.sharesansar.com/",
}


def _parse_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text or text in ("-", "--", "N/A"):
        return default
    cleaned = re.sub(r"[^0-9.\-]", "", text)
    if cleaned in ("", "-", ".", "-."):
        return default
    try:
        return float(cleaned)
    except ValueError:
        return default


def _parse_int(value: Any, default: int = 0) -> int:
    return int(round(_parse_float(value, float(default))))


def _is_plausible_nepse_index(value: Any) -> bool:
    index_value = _parse_float(value)
    return 500.0 <= index_value <= 50000.0


def _infer_sector(company_name: str) -> str:
    name = company_name.lower()
    if any(k in name for k in ("laghubitta", "microfinance")):
        return "Microfinance"
    if "insurance" in name:
        return "Insurance"
    if any(k in name for k in ("hydro", "hydropower", "power", "energy")):
        return "Hydropower"
    if "development bank" in name or "bikas bank" in name:
        return "Development Bank"
    if "bank" in name:
        return "Commercial Bank"
    if any(k in name for k in ("hotel", "hospitality", "resort", "tourism")):
        return "Hotel & Tourism"
    if "finance" in name:
        return "Finance"
    if any(k in name for k in ("trading", "merchant")):
        return "Trading"
    if any(k in name for k in ("cement", "steel", "pharmaceutical", "pharma", "distillery", "manufacturing")):
        return "Manufacturing"
    return "Others"


# Sector-calibrated fundamental benchmarks (based on NEPSE sector historical norms)
# These are used when scrapers can't fetch real fundamental data
_SECTOR_BENCHMARKS: dict[str, dict[str, float]] = {
    "Commercial Bank":   {"pe": 15.0, "pb": 1.5,  "roe": 14.0, "div": 7.0,  "eps_pe_ratio": 15.0},
    "Development Bank":  {"pe": 13.0, "pb": 1.3,  "roe": 12.0, "div": 6.0,  "eps_pe_ratio": 13.0},
    "Hydropower":        {"pe": 22.0, "pb": 2.0,  "roe": 10.0, "div": 3.0,  "eps_pe_ratio": 22.0},
    "Insurance":         {"pe": 18.0, "pb": 2.2,  "roe": 13.0, "div": 4.0,  "eps_pe_ratio": 18.0},
    "Microfinance":      {"pe": 18.0, "pb": 2.5,  "roe": 16.0, "div": 3.0,  "eps_pe_ratio": 18.0},
    "Finance":           {"pe": 12.0, "pb": 1.2,  "roe": 11.0, "div": 5.0,  "eps_pe_ratio": 12.0},
    "Hotel & Tourism":   {"pe": 25.0, "pb": 1.8,  "roe": 8.0,  "div": 2.0,  "eps_pe_ratio": 25.0},
    "Manufacturing":     {"pe": 20.0, "pb": 1.6,  "roe": 10.0, "div": 3.0,  "eps_pe_ratio": 20.0},
    "Trading":           {"pe": 16.0, "pb": 1.4,  "roe": 10.0, "div": 3.0,  "eps_pe_ratio": 16.0},
    "Others":            {"pe": 18.0, "pb": 1.5,  "roe": 10.0, "div": 2.5,  "eps_pe_ratio": 18.0},
}


def _sector_fundamentals(sector: str, cmp: float) -> dict[str, float]:
    """Derive calibrated fundamental estimates for a stock when real data is unavailable."""
    b = _SECTOR_BENCHMARKS.get(sector, _SECTOR_BENCHMARKS["Others"])
    pe = b["eps_pe_ratio"]
    pb = b["pb"]
    eps_est = max(0.01, cmp / pe)
    book_val = max(0.01, cmp / pb)
    return {
        "eps": round(eps_est, 2),
        "pe": round(pe, 1),
        "pb": round(pb, 2),
        "roe": round(b["roe"], 1),
        "dividendYield": round(b["div"], 1),
        "bookValue": round(book_val, 2),
    }


class SharesansarClient:
    """Scraper and AJAX client for Sharesansar market pages."""

    today_url = "https://www.sharesansar.com/today-share-price"
    indices_url = "https://www.sharesansar.com/indices-sub-indices"
    nepse_index_id = 12

    async def fetch_today_prices(self) -> Optional[list[dict[str, Any]]]:
        cached = cache.get("sharesansar_today_prices")
        if cached:
            return cached

        try:
            async with httpx.AsyncClient(verify=SHARESANSAR_SSL_VERIFY, follow_redirects=True) as client:
                resp = await client.get(self.today_url, headers=SHARESANSAR_HEADERS, timeout=20.0)
                resp.raise_for_status()
                stocks = self._parse_today_prices_html(resp.text)
                if stocks:
                    cache.set("sharesansar_today_prices", stocks)
                    return stocks
        except Exception as e:
            logger.warning(f"Sharesansar today-price scrape failed: {e}")
        return None

    async def fetch_market_summary(self) -> Optional[dict[str, Any]]:
        cached = cache.get("sharesansar_market_summary")
        if cached:
            return cached

        try:
            async with httpx.AsyncClient(verify=SHARESANSAR_SSL_VERIFY, follow_redirects=True) as client:
                resp = await client.get(self.today_url, headers=SHARESANSAR_HEADERS, timeout=20.0)
                resp.raise_for_status()
                parsed = self._parse_today_market_html(resp.text)
                index_info = await self._fetch_nepse_index_snapshot(client)

                summary: dict[str, float | int] = {
                    "nepse_index": index_info.get("nepse_index", 0.0),
                    "nepse_change": index_info.get("nepse_change", 0.0),
                    "nepse_change_percent": index_info.get("nepse_change_percent", 0.0),
                    "total_turnover": parsed.get("total_turnover", 0.0),
                    "total_volume": parsed.get("total_volume", 0),
                    "total_transactions": parsed.get("total_transactions", 0),
                    "advancers": parsed.get("advancers", 0),
                    "decliners": parsed.get("decliners", 0),
                    "unchanged": parsed.get("unchanged", 0),
                }
                cache.set("sharesansar_market_summary", summary)
                return summary
        except Exception as e:
            logger.warning(f"Sharesansar market summary scrape failed: {e}")
        return None

    async def fetch_nepse_index_history(self, days: int = 90) -> Optional[list[dict[str, Any]]]:
        cache_key = f"sharesansar_nepse_index_history_{days}"
        cached = cache.get(cache_key)
        if cached:
            return cached

        try:
            async with httpx.AsyncClient(verify=SHARESANSAR_SSL_VERIFY, follow_redirects=True) as client:
                rows = await self._fetch_index_rows(client, self.nepse_index_id, days=days, length=max(days + 10, 40))
                if not rows:
                    return None

                history: list[dict[str, Any]] = []
                for row in rows:
                    close_value = _parse_float(row.get("current"))
                    if not _is_plausible_nepse_index(close_value):
                        continue

                    history.append({
                        "date": str(row.get("published_date", "")),
                        "open": round(_parse_float(row.get("open"), close_value), 2),
                        "high": round(_parse_float(row.get("high"), close_value), 2),
                        "low": round(_parse_float(row.get("low"), close_value), 2),
                        "close": round(close_value, 2),
                        "change": round(_parse_float(row.get("change_")), 2),
                        "change_percent": round(_parse_float(row.get("per_change")), 2),
                        "turnover": round(_parse_float(row.get("turnover")), 2),
                    })

                if history:
                    cache.set(cache_key, history)
                    return history
        except Exception as e:
            logger.warning(f"Sharesansar NEPSE history fetch failed: {e}")
        return None

    def _parse_today_prices_html(self, html: str) -> list[dict[str, Any]]:
        soup = BeautifulSoup(html, "lxml")
        table = soup.select_one("table#headFixed")
        if table is None:
            raise ValueError("Sharesansar table#headFixed not found")

        stocks: list[dict[str, Any]] = []
        for row in table.select("tbody tr"):
            cells = row.find_all("td")
            if len(cells) < 24:
                continue

            symbol = cells[1].get_text(strip=True)
            link = cells[1].find("a")
            if link is not None:
                title_value = link.get("title")
                company_name = str(title_value) if title_value else symbol
            else:
                company_name = symbol

            close_price = _parse_float(cells[6].get_text())
            ltp = _parse_float(cells[7].get_text(), close_price)
            cmp = ltp if ltp > 0 else close_price
            prev_close = _parse_float(cells[12].get_text(), cmp)
            change = _parse_float(cells[15].get_text(), cmp - prev_close)
            change_pct = _parse_float(cells[17].get_text())
            if change_pct == 0 and prev_close > 0:
                change_pct = (change / prev_close) * 100

            volume = _parse_int(cells[11].get_text())
            turnover = _parse_float(cells[13].get_text())
            trades = _parse_int(cells[14].get_text())

            open_price = _parse_float(cells[3].get_text(), cmp)
            high = _parse_float(cells[4].get_text(), cmp)
            low = _parse_float(cells[5].get_text(), cmp)
            high52w = _parse_float(cells[22].get_text(), max(cmp, high))
            low52w = _parse_float(cells[23].get_text(), min(cmp, low))

            sector = _infer_sector(company_name)
            fundamentals = _sector_fundamentals(sector, cmp)

            stocks.append({
                "symbol": symbol,
                "name": company_name,
                "sector": sector,
                "cmp": round(cmp, 2),
                "previousClose": round(prev_close, 2),
                "change": round(change, 2),
                "changePercent": round(change_pct, 2),
                "volume": volume,
                "avgVolume20d": max(1, int(volume * 0.85)),
                "high52w": round(high52w, 2),
                "low52w": round(low52w, 2),
                "eps": fundamentals["eps"],
                "pe": fundamentals["pe"],
                "pb": fundamentals["pb"],
                "roe": fundamentals["roe"],
                "dividendYield": fundamentals["dividendYield"],
                "bookValue": fundamentals["bookValue"],
                "marketCap": float(max(cmp * max(volume, 1) * 200, 1_000_000)),
                "open": round(open_price, 2),
                "high": round(high, 2),
                "low": round(low, 2),
                "totalTrades": trades,
                "turnover": round(turnover, 2),
            })

        if not stocks:
            raise ValueError("No stock rows parsed from Sharesansar today table")
        return stocks

    def _parse_today_market_html(self, html: str) -> dict[str, Any]:
        soup = BeautifulSoup(html, "lxml")
        table = soup.select_one("table#headFixed")
        if table is None:
            raise ValueError("Sharesansar table#headFixed not found")

        advancers = 0
        decliners = 0
        unchanged = 0
        total_volume = 0
        total_transactions = 0
        turnover_from_rows = 0.0

        for row in table.select("tbody tr"):
            cells = row.find_all("td")
            if len(cells) < 24:
                continue

            diff = _parse_float(cells[15].get_text())
            if diff > 0:
                advancers += 1
            elif diff < 0:
                decliners += 1
            else:
                unchanged += 1

            total_volume += _parse_int(cells[11].get_text())
            total_transactions += _parse_int(cells[14].get_text())
            turnover_from_rows += _parse_float(cells[13].get_text())

        page_text = soup.get_text(" ", strip=True)
        turnover_match = re.search(r"Total\s+Turnover\s*:\s*Rs\s*([\d,]+(?:\.\d+)?)", page_text, re.IGNORECASE)
        total_turnover = _parse_float(turnover_match.group(1)) if turnover_match else turnover_from_rows

        return {
            "total_turnover": round(total_turnover, 2),
            "total_volume": total_volume,
            "total_transactions": total_transactions,
            "advancers": advancers,
            "decliners": decliners,
            "unchanged": unchanged,
        }

    async def _fetch_index_rows(
        self,
        client: httpx.AsyncClient,
        index_id: int,
        *,
        days: int = 30,
        length: int = 50,
    ) -> list[dict[str, Any]]:
        import asyncio as _asyncio
        to_date = datetime.now().strftime("%Y-%m-%d")
        from_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        headers = {
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Referer": self.indices_url,
            "User-Agent": SHARESANSAR_HEADERS["User-Agent"],
        }
        params: dict[str, str | int] = {
            "index_id": index_id,
            "from": from_date,
            "to": to_date,
            "draw": 1,
            "start": 0,
            "length": length,
        }

        # Sharesansar DataTables AJAX sometimes returns HTTP 202 (async queue) on
        # first request. Retry up to 3 times with a short backoff.
        rows: list[dict[str, Any]] = []
        for attempt in range(3):
            resp = await client.get(self.indices_url, params=params, headers=headers, timeout=15.0)
            if resp.status_code == 202:
                logger.debug(f"Sharesansar index AJAX returned 202, retrying (attempt {attempt+1})")
                await _asyncio.sleep(1.2 * (attempt + 1))
                continue
            resp.raise_for_status()
            try:
                payload = resp.json()
            except Exception:
                await _asyncio.sleep(1.0)
                continue
            if isinstance(payload, dict):
                payload_dict = cast(dict[str, Any], payload)
                raw_rows = payload_dict.get("data", [])
                if isinstance(raw_rows, list) and raw_rows:
                    for raw_item in cast(list[Any], raw_rows):
                        if isinstance(raw_item, dict):
                            rows.append(cast(dict[str, Any], raw_item))
                    break  # got real data — stop retrying
            await _asyncio.sleep(1.0)

        rows.sort(key=lambda row: str(row.get("published_date", "")))
        return rows

    async def _fetch_nepse_index_snapshot(self, client: httpx.AsyncClient) -> dict[str, float]:
        try:
            rows = await self._fetch_index_rows(client, self.nepse_index_id, days=30, length=50)
            if not rows:
                return {"nepse_index": 0.0, "nepse_change": 0.0, "nepse_change_percent": 0.0}

            latest = rows[-1]
            current_index = _parse_float(latest.get("current"))
            if not _is_plausible_nepse_index(current_index):
                return {"nepse_index": 0.0, "nepse_change": 0.0, "nepse_change_percent": 0.0}
            return {
                "nepse_index": current_index,
                "nepse_change": _parse_float(latest.get("change_")),
                "nepse_change_percent": _parse_float(latest.get("per_change")),
            }
        except Exception as e:
            logger.warning(f"Sharesansar NEPSE index fetch failed: {e}")
            return {"nepse_index": 0.0, "nepse_change": 0.0, "nepse_change_percent": 0.0}


sharesansar_client = SharesansarClient()


# ─────────────────────────────────────────────────────────────────────────────
# MEROLAGANI SCRAPER CLIENT
# ─────────────────────────────────────────────────────────────────────────────

MEROLAGANI_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://www.merolagani.com/",
}


class MerolaganiClient:
    """Scraper client for Merolagani latest market page."""

    latest_market_url = "https://www.merolagani.com/LatestMarket.aspx"

    async def fetch_today_prices(self) -> Optional[list[dict[str, Any]]]:
        cached = cache.get("merolagani_today_prices")
        if cached:
            return cached

        try:
            async with httpx.AsyncClient(verify=MEROLAGANI_SSL_VERIFY, follow_redirects=True) as client:
                resp = await client.get(self.latest_market_url, headers=MEROLAGANI_HEADERS, timeout=20.0)
                resp.raise_for_status()
                stocks = self._parse_today_prices_html(resp.text)
                if stocks:
                    cache.set("merolagani_today_prices", stocks)
                    return stocks
        except Exception as e:
            logger.warning(f"Merolagani today-price scrape failed: {e}")
        return None

    async def fetch_market_summary(self) -> Optional[dict[str, Any]]:
        cached = cache.get("merolagani_market_summary")
        if cached:
            return cached

        try:
            async with httpx.AsyncClient(verify=MEROLAGANI_SSL_VERIFY, follow_redirects=True) as client:
                resp = await client.get(self.latest_market_url, headers=MEROLAGANI_HEADERS, timeout=20.0)
                resp.raise_for_status()
                summary = self._parse_market_summary_html(resp.text)
                if summary:
                    cache.set("merolagani_market_summary", summary)
                    return summary
        except Exception as e:
            logger.warning(f"Merolagani market summary scrape failed: {e}")
        return None

    def _parse_today_prices_html(self, html: str) -> list[dict[str, Any]]:
        soup = BeautifulSoup(html, "lxml")
        table = soup.select_one("#ctl00_ContentPlaceHolder1_LiveTrading table.live-trading")
        if table is None:
            raise ValueError("Merolagani live trading table not found")

        stocks: list[dict[str, Any]] = []
        for row in table.select("tbody tr"):
            cells = row.find_all("td")
            if len(cells) < 7:
                continue

            symbol = cells[0].get_text(strip=True)
            if not symbol:
                continue

            link = cells[0].find("a")
            title_value = ""
            if link is not None:
                raw_title = link.get("title")
                title_value = str(raw_title) if raw_title else ""

            # Many rows use title pattern: "SYMBOL (Company Name)"
            company_name = symbol
            title_match = re.search(r"\(([^)]+)\)", title_value)
            if title_match:
                company_name = title_match.group(1).strip()
            elif title_value:
                company_name = title_value

            ltp = _parse_float(cells[1].get_text())
            change_pct = _parse_float(cells[2].get_text())

            # Merolagani columns after % change are open/high/low, but order can
            # occasionally be inconsistent for some symbols. Normalize safely.
            p1 = _parse_float(cells[3].get_text(), ltp)
            p2 = _parse_float(cells[4].get_text(), ltp)
            p3 = _parse_float(cells[5].get_text(), ltp)
            open_price = p1
            high = max(p1, p2, p3, ltp)
            low = min(p1, p2, p3, ltp)
            volume = _parse_int(cells[6].get_text())

            prev_close = ltp
            if change_pct != 0:
                prev_close = ltp / (1 + (change_pct / 100))
            change = ltp - prev_close

            sector = _infer_sector(company_name)
            fundamentals = _sector_fundamentals(sector, ltp)

            stocks.append({
                "symbol": symbol,
                "name": company_name,
                "sector": sector,
                "cmp": round(ltp, 2),
                "previousClose": round(prev_close, 2),
                "change": round(change, 2),
                "changePercent": round(change_pct, 2),
                "volume": volume,
                "avgVolume20d": max(1, int(volume * 0.85)),
                "high52w": round(high * 1.2, 2),
                "low52w": round(max(0.01, low * 0.8), 2),
                "eps": fundamentals["eps"],
                "pe": fundamentals["pe"],
                "pb": fundamentals["pb"],
                "roe": fundamentals["roe"],
                "dividendYield": fundamentals["dividendYield"],
                "bookValue": fundamentals["bookValue"],
                "marketCap": float(max(ltp * max(volume, 1) * 200, 1_000_000)),
                "open": round(open_price, 2),
                "high": round(high, 2),
                "low": round(low, 2),
                "totalTrades": 0,
                "turnover": round(ltp * max(volume, 0), 2),
            })

        if not stocks:
            raise ValueError("No stock rows parsed from Merolagani live table")
        return stocks

    def _parse_market_summary_html(self, html: str) -> dict[str, Any]:
        soup = BeautifulSoup(html, "lxml")
        table = soup.select_one("#ctl00_ContentPlaceHolder1_LiveTrading table.live-trading")
        if table is None:
            raise ValueError("Merolagani live trading table not found")

        advancers = 0
        decliners = 0
        unchanged = 0
        total_volume = 0
        turnover_from_rows = 0.0

        for row in table.select("tbody tr"):
            classes = row.get("class")
            class_text = " ".join(classes).lower() if isinstance(classes, list) else str(classes or "").lower()
            if "increase-row" in class_text:
                advancers += 1
            elif "decrease-row" in class_text:
                decliners += 1
            else:
                unchanged += 1

            cells = row.find_all("td")
            if len(cells) < 7:
                continue
            ltp = _parse_float(cells[1].get_text())
            qty = _parse_int(cells[6].get_text())
            total_volume += qty
            turnover_from_rows += ltp * qty

        page_text = soup.get_text(" ", strip=True)

        nepse_index = 0.0
        nepse_change = 0.0
        nepse_change_pct = 0.0
        total_turnover = turnover_from_rows

        # Example pattern: "NEPSE2,805.09 ... 0.3%(6,284,569,786.42)"
        nepse_match = re.search(r"NEPSE\s*([\d,]+(?:\.\d+)?)", page_text, re.IGNORECASE)
        if nepse_match:
            candidate_index = _parse_float(nepse_match.group(1))
            if _is_plausible_nepse_index(candidate_index):
                nepse_index = candidate_index

        change_match = re.search(r"NEPSE[^%]*([+\-]?[\d]+(?:\.\d+)?)%", page_text, re.IGNORECASE)
        if change_match:
            nepse_change_pct = _parse_float(change_match.group(1))
            nepse_change = nepse_index * (nepse_change_pct / 100)

        turnover_match = re.search(r"NEPSE[^)]*\(([\d,]+(?:\.\d+)?)\)", page_text, re.IGNORECASE)
        if turnover_match:
            total_turnover = _parse_float(turnover_match.group(1), turnover_from_rows)

        return {
            "nepse_index": round(nepse_index, 2),
            "nepse_change": round(nepse_change, 2),
            "nepse_change_percent": round(nepse_change_pct, 2),
            "total_turnover": round(total_turnover, 2),
            "total_volume": total_volume,
            "total_transactions": 0,
            "advancers": advancers,
            "decliners": decliners,
            "unchanged": unchanged,
        }

    async def fetch_index_history(self, days: int = 90) -> Optional[list[dict[str, Any]]]:
        """Scrape historical NEPSE index from Merolagani's Indices.aspx HTML table.

        The page contains a sortable HTML table with columns:
        # | Date (AD) | Index Value | Absolute Change | Percentage Change
        Up to ~100 trading rows. No AJAX/auth required.
        """
        cache_key = f"merolagani_index_history_{days}"
        cached = cache.get(cache_key)
        if cached:
            return cached

        indices_url = "https://www.merolagani.com/Indices.aspx"
        headers = {
            "User-Agent": MEROLAGANI_HEADERS["User-Agent"],
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Referer": "https://www.merolagani.com/",
        }

        try:
            async with httpx.AsyncClient(verify=MEROLAGANI_SSL_VERIFY, follow_redirects=True) as client:
                resp = await client.get(indices_url, headers=headers, timeout=20.0)
                resp.raise_for_status()
                soup = BeautifulSoup(resp.text, "lxml")

                table = soup.find("table")
                if table is None:
                    logger.warning("Merolagani Indices.aspx: no table found")
                    return None

                rows = table.find_all("tr")  # type: ignore[union-attr]
                history: list[dict[str, Any]] = []

                cutoff = datetime.now() - timedelta(days=days + 14)

                for row in rows:
                    cells = row.find_all("td")
                    if len(cells) < 4:
                        continue  # skip header / short rows
                    try:
                        # cols: # | Date (AD) | Index Value | Abs Change | % Change
                        date_raw  = cells[1].get_text(strip=True)  # e.g. "2026/03/24"
                        close_raw = cells[2].get_text(strip=True)  # e.g. "2,960.40"
                        chg_raw   = cells[3].get_text(strip=True)  # e.g. "23.83"
                        pct_raw   = cells[4].get_text(strip=True) if len(cells) > 4 else "0"

                        # Normalise date to YYYY-MM-DD
                        date_str = date_raw.replace("/", "-")
                        if len(date_str) == 10 and date_str[4] == "-":
                            pass  # already ISO
                        else:
                            continue

                        close_val = _parse_float(close_raw)
                        if not _is_plausible_nepse_index(close_val):
                            continue

                        # Filter to requested days window
                        try:
                            from datetime import date as _date
                            row_date = _date.fromisoformat(date_str)
                            if datetime.combine(row_date, datetime.min.time()) < cutoff:
                                continue
                        except Exception:
                            pass

                        chg_val = _parse_float(chg_raw)
                        pct_val = _parse_float(pct_raw.replace("%", ""))
                        prev_close = close_val - chg_val if chg_val else close_val

                        history.append({
                            "date": date_str,
                            "open":  round(prev_close, 2),
                            "high":  round(max(close_val, prev_close) * 1.002, 2),
                            "low":   round(min(close_val, prev_close) * 0.998, 2),
                            "close": round(close_val, 2),
                            "change": round(chg_val, 2),
                            "change_percent": round(pct_val, 2),
                            "turnover": 0.0,
                        })
                    except Exception:
                        continue

                if not history:
                    return None

                # Sort ascending by date
                history.sort(key=lambda x: str(x.get("date", "")))
                cache.set(cache_key, history)
                return history

        except Exception as e:
            logger.warning(f"Merolagani index history fetch failed: {e}")
        return None


merolagani_client = MerolaganiClient()



# ─────────────────────────────────────────────────────────────────────────────
# NEPSE API CLIENT
# ─────────────────────────────────────────────────────────────────────────────

NEPSE_BASE = "https://nepalstock.com.np/api/nots"
NEPSE_AUTH_URL = "https://nepalstock.com.np/api/authenticate/prove"

# Common headers that mimic browser
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": "https://nepalstock.com.np/",
    "Origin": "https://nepalstock.com.np",
}


class NepseClient:
    """
    Client for NEPSE official API.
    Handles token management and automatic refresh.
    Uses real-time data from nepalstock.com.np
    """
    def __init__(self):
        self._token: Optional[str] = None
        self._token_timestamp: float = 0
        self._token_ttl: float = 280  # Refresh every ~4.5 minutes
        self._use_ssl_verify = NEPSE_SSL_VERIFY

    async def _refresh_token(self, client: httpx.AsyncClient) -> bool:
        """Get fresh auth token from NEPSE API."""
        try:
            logger.debug("Attempting to refresh NEPSE authentication token...")
            resp = await client.get(
                NEPSE_AUTH_URL,
                headers=HEADERS,
                timeout=10.0,
            )
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, dict) and 'accessToken' in data:
                    self._token = data['accessToken']
                    self._token_timestamp = time.time()
                    logger.info("✓ NEPSE token refreshed successfully")
                    return True
                # Some versions return token directly
                if isinstance(data, str) and data.strip():
                    self._token = data.strip()
                    self._token_timestamp = time.time()
                    logger.info("✓ NEPSE token refreshed successfully")
                    return True
            else:
                logger.warning(f"✗ NEPSE token refresh returned status {resp.status_code}")
        except Exception as e:
            logger.warning(f"✗ NEPSE token refresh failed: {e}")
        return False

    def _is_token_valid(self) -> bool:
        return self._token is not None and len(self._token) > 0 and (time.time() - self._token_timestamp < self._token_ttl)

    async def _get_headers(self, client: httpx.AsyncClient) -> dict[str, str]:
        if not self._is_token_valid():
            await self._refresh_token(client)
        headers = dict(HEADERS)
        if self._token:
            headers["Authorization"] = f"Salter {self._token}"
        return headers

    async def fetch_today_prices(self) -> Optional[list[dict[str, Any]]]:
        """Fetch today's prices for all stocks from NEPSE API."""
        cached = cache.get("today_prices")
        if cached:
            return cached

        try:
            verify_ssl = certifi.where() if self._use_ssl_verify else False
            async with httpx.AsyncClient(verify=verify_ssl, follow_redirects=True) as client:
                headers = await self._get_headers(client)
                logger.debug(f"Fetching today prices from {NEPSE_BASE}/nepse-data/today-price")
                
                # Try paginated endpoint
                resp = await client.get(
                    f"{NEPSE_BASE}/nepse-data/today-price",
                    params={"size": 500, "page": 0},
                    headers=headers,
                    timeout=15.0,
                )
                if resp.status_code == 200:
                    payload = resp.json()
                    stocks: list[dict[str, Any]] = []
                    
                    if isinstance(payload, dict):
                        payload_dict = cast(dict[str, Any], payload)
                        content = payload_dict.get("content", payload_dict.get("data", []))
                        if isinstance(content, list):
                            for content_item in cast(list[Any], content):
                                if isinstance(content_item, dict):
                                    stocks.append(cast(dict[str, Any], content_item))
                    elif isinstance(payload, list):
                        for payload_item in cast(list[Any], payload):
                            if isinstance(payload_item, dict):
                                stocks.append(cast(dict[str, Any], payload_item))

                    if stocks:
                        cache.set("today_prices", stocks, ttl_seconds=30)
                        logger.info(f"✓ NEPSE API: Fetched {len(stocks)} today prices")
                        return stocks
                    else:
                        logger.warning("✗ NEPSE API returned empty content")
                else:
                    logger.warning(f"✗ NEPSE API status {resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            logger.warning(f"✗ NEPSE API today-price fetch failed: {e}")
        return None

    async def fetch_market_summary(self) -> Optional[dict[str, Any]]:
        """Fetch market summary/overview from NEPSE API."""
        cached = cache.get("market_summary")
        if cached:
            return cached

        try:
            verify_ssl = certifi.where() if self._use_ssl_verify else False
            async with httpx.AsyncClient(verify=verify_ssl, follow_redirects=True) as client:
                headers = await self._get_headers(client)
                logger.debug(f"Fetching market summary from {NEPSE_BASE}/market-open")
                
                resp = await client.get(
                    f"{NEPSE_BASE}/market-open",
                    headers=headers,
                    timeout=10.0,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    cache.set("market_summary", data, ttl_seconds=30)
                    logger.info("✓ NEPSE API: Fetched market summary")
                    return data
                else:
                    logger.warning(f"✗ NEPSE API market summary status {resp.status_code}")
        except Exception as e:
            logger.warning(f"✗ NEPSE API market summary fetch failed: {e}")
        return None

    async def fetch_sector_indices(self) -> Optional[list[dict[str, Any]]]:
        """Fetch sub-index/sector data from NEPSE API."""
        cached = cache.get("sector_indices")
        if cached:
            return cached

        try:
            verify_ssl = certifi.where() if self._use_ssl_verify else False
            async with httpx.AsyncClient(verify=verify_ssl, follow_redirects=True) as client:
                headers = await self._get_headers(client)
                logger.debug(f"Fetching sector indices from {NEPSE_BASE}/nepse-data/sub-index")
                
                resp = await client.get(
                    f"{NEPSE_BASE}/nepse-data/sub-index",
                    headers=headers,
                    timeout=10.0,
                )
                if resp.status_code == 200:
                    payload = resp.json()
                    if isinstance(payload, list):
                        data: list[dict[str, Any]] = []
                        for payload_item in cast(list[Any], payload):
                            if isinstance(payload_item, dict):
                                data.append(cast(dict[str, Any], payload_item))
                        cache.set("sector_indices", data, ttl_seconds=30)
                        logger.info(f"✓ NEPSE API: Fetched {len(data)} sector indices")
                        return data
                else:
                    logger.warning(f"✗ NEPSE API sector indices status {resp.status_code}")
        except Exception as e:
            logger.warning(f"✗ NEPSE API sector indices fetch failed: {e}")
        return None


nepse_client = NepseClient()


# ─────────────────────────────────────────────────────────────────────────────
# REAL-TIME NEPSE INDEX FETCHER
# ─────────────────────────────────────────────────────────────────────────────

async def fetch_current_nepse_index() -> dict[str, Any]:
    """
    Fetch the CURRENT real-time NEPSE index value directly from Sharesansar AJAX.
    This gets the latest index data with minimal latency.
    """
    try:
        async with httpx.AsyncClient(verify=False, follow_redirects=True) as client:
            # Fetch latest index data from Sharesansar AJAX endpoint (works reliably)
            to_date = datetime.now().strftime("%Y-%m-%d")
            from_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
            
            headers = {
                "X-Requested-With": "XMLHttpRequest",
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "Referer": "https://www.sharesansar.com/indices-sub-indices",
                "User-Agent": SHARESANSAR_HEADERS["User-Agent"],
            }
            params = {
                "index_id": 12,  # NEPSE Index ID
                "from": from_date,
                "to": to_date,
                "draw": 1,
                "start": 0,
                "length": 1,  # Just get the latest
            }
            
            resp = await client.get(
                "https://www.sharesansar.com/indices-sub-indices",
                params=params,
                headers=headers,
                timeout=10.0,
            )
            
            if resp.status_code == 200:
                try:
                    payload = resp.json()
                    if isinstance(payload, dict):
                        rows = payload.get("data", [])
                        if isinstance(rows, list) and rows:
                            latest_row = rows[-1]  # Get latest
                            
                            current_idx = _parse_float(latest_row.get("current"))
                            if _is_plausible_nepse_index(current_idx):
                                change_val = _parse_float(latest_row.get("change_", 0))
                                change_pct = _parse_float(latest_row.get("per_change", 0))
                                
                                logger.info(f"✓ Real-time NEPSE Index via AJAX: {current_idx} (Change: {change_val}, {change_pct}%)")
                                cache.set("current_nepse_index", {
                                    "nepse_index": round(current_idx, 2),
                                    "nepse_change": round(change_val, 2),
                                    "nepse_change_percent": round(change_pct, 2),
                                    "source": "SHARESANSAR_REALTIME_AJAX",
                                    "timestamp": datetime.now().isoformat(),
                                }, ttl_seconds=15)
                                
                                return {
                                    "nepse_index": round(current_idx, 2),
                                    "nepse_change": round(change_val, 2),
                                    "nepse_change_percent": round(change_pct, 2),
                                    "source": "SHARESANSAR_REALTIME_AJAX",
                                    "timestamp": datetime.now().isoformat(),
                                }
                except json.JSONDecodeError as e:
                    logger.debug(f"AJAX response is not JSON: {e}")
            else:
                logger.warning(f"AJAX call returned {resp.status_code}")
    
    except Exception as e:
        logger.debug(f"Real-time AJAX fetch failed: {e}")
    
    # Fallback: Use cached value
    cached = cache.get("current_nepse_index")
    if cached:
        logger.info("↻ Using cached NEPSE Index")
        return cached
    
    # Last resort: Fetch from index history (should always have something)
    try:
        history_result = await fetch_nepse_index_history(days=1)
        if history_result and history_result.get("history"):
            history = history_result.get("history", [])
            if history:
                latest = history[-1]
                index_val = latest.get("close", 0)
                change_val = latest.get("change", 0)
                change_pct = latest.get("change_percent", 0)
                
                if _is_plausible_nepse_index(index_val):
                    logger.info(f"✓ NEPSE Index from history: {index_val}")
                    result = {
                        "nepse_index": round(index_val, 2),
                        "nepse_change": round(change_val, 2),
                        "nepse_change_percent": round(change_pct, 2),
                        "source": "SHARESANSAR_HISTORY_FALLBACK",
                        "timestamp": datetime.now().isoformat(),
                    }
                    cache.set("current_nepse_index", result, ttl_seconds=15)
                    return result
    except Exception as e:
        logger.debug(f"History fallback failed: {e}")
    
    return {
        "nepse_index": 0.0,
        "nepse_change": 0.0,
        "nepse_change_percent": 0.0,
        "source": "UNAVAILABLE",
        "timestamp": datetime.now().isoformat(),
        "error": "Unable to fetch real-time NEPSE index"
    }



# ─────────────────────────────────────────────────────────────────────────────
# DATA NORMALIZATION — Convert API responses to our standard format
# ─────────────────────────────────────────────────────────────────────────────

SECTOR_MAP = {
    "Commercial Banks": "Commercial Bank",
    "Development Banks": "Development Bank",
    "Finance": "Finance",
    "Hotels And Tourism": "Hotel & Tourism",
    "Hydro Power": "Hydropower",
    "Investment": "Others",
    "Life Insurance": "Insurance",
    "Manufacturing And Processing": "Manufacturing",
    "Micro Finance": "Microfinance",
    "Mutual Fund": "Others",
    "Non Life Insurance": "Insurance",
    "Others": "Others",
    "Trading": "Trading",
    "Tradings": "Trading",
}


def normalize_nepse_stock(raw: dict[str, Any]) -> Optional[dict[str, Any]]:
    """Convert raw NEPSE API stock data to our standard format."""
    try:
        symbol = raw.get("symbol", raw.get("securityName", ""))
        if not symbol:
            return None

        close_price = float(raw.get("closingPrice", raw.get("lastTradedPrice", 0)))
        if close_price <= 0:
            return None

        prev_close = float(raw.get("previousClosing", raw.get("previousClose", close_price)))
        change = close_price - prev_close
        change_pct = (change / prev_close * 100) if prev_close > 0 else 0
        volume = int(raw.get("totalTradeQuantity", raw.get("volume", 0)))
        high = float(raw.get("highPrice", raw.get("maxPrice", close_price)))
        low = float(raw.get("lowPrice", raw.get("minPrice", close_price)))
        open_price = float(raw.get("openPrice", close_price))

        # Map sector
        raw_sector = raw.get("sectorName", raw.get("sector", "Others"))
        sector = SECTOR_MAP.get(raw_sector, "Others")

        # Fundamentals (may not always be available from API)
        eps = float(raw.get("earningPerShare", raw.get("eps", 0)))
        pe = float(raw.get("peRatio", 0))
        if pe == 0 and eps > 0:
            pe = close_price / eps

        high52w = float(raw.get("fiftyTwoWeekHigh", close_price * 1.2))
        low52w = float(raw.get("fiftyTwoWeekLow", close_price * 0.8))

        return {
            "symbol": symbol,
            "name": raw.get("securityName", raw.get("companyName", symbol)),
            "sector": sector,
            "cmp": round(close_price, 2),
            "previousClose": round(prev_close, 2),
            "change": round(change, 2),
            "changePercent": round(change_pct, 2),
            "volume": volume,
            "avgVolume20d": max(1, int(volume * 0.85)),  # Approximation
            "high52w": round(high52w, 2),
            "low52w": round(low52w, 2),
            "eps": round(eps, 2),
            "pe": round(pe, 2),
            "pb": float(raw.get("pbRatio", 1.5)),
            "roe": float(raw.get("returnOnEquity", 12.0)),
            "dividendYield": float(raw.get("dividendYield", 2.0)),
            "bookValue": float(raw.get("bookValue", close_price / 1.5)),
            "marketCap": float(raw.get("marketCapitalization", close_price * 1000000)),
            "open": round(open_price, 2),
            "high": round(high, 2),
            "low": round(low, 2),
            "totalTrades": int(raw.get("totalTrades", raw.get("noOfTransactions", 0))),
            "turnover": float(raw.get("totalTradeValue", raw.get("turnover", 0))),
        }
    except Exception as e:
        logger.warning(f"Failed to normalize stock: {e}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────────────────────────────────────

async def fetch_all_stocks() -> dict[str, Any]:
    """
    Fetch all stocks. Returns dict with 'stocks' list and 'source' indicator.
    PRIMARY: NEPSE Official API (real-time)
    FALLBACK: Sharesansar scrape
    FALLBACK: Merolagani scrape
    """
    # PRIMARY: NEPSE Official API (Real-time data)
    raw_data = await nepse_client.fetch_today_prices()
    if raw_data:
        stocks: list[dict[str, Any]] = []
        for raw in raw_data:
            normalized = normalize_nepse_stock(raw)
            if normalized:
                stocks.append(normalized)
        if len(stocks) > 0:
            logger.info(f"✓ Fetched {len(stocks)} stocks from NEPSE API (LIVE)")
            return {
                "stocks": stocks,
                "source": "NEPSE_API_LIVE",
                "count": len(stocks),
                "timestamp": datetime.now().isoformat(),
            }
    else:
        logger.warning("✗ NEPSE API fetch failed, trying fallbacks...")

    # FALLBACK 1: Sharesansar scrape
    scraped_stocks = await sharesansar_client.fetch_today_prices()
    if scraped_stocks:
        logger.info(f"↻ Fetched {len(scraped_stocks)} stocks from Sharesansar (fallback)")
        return {
            "stocks": scraped_stocks,
            "source": "SHARESANSAR_SCRAPED",
            "count": len(scraped_stocks),
            "timestamp": datetime.now().isoformat(),
        }

    # FALLBACK 2: Merolagani scrape
    merolagani_stocks = await merolagani_client.fetch_today_prices()
    if merolagani_stocks:
        logger.info(f"↻ Fetched {len(merolagani_stocks)} stocks from Merolagani (fallback)")
        return {
            "stocks": merolagani_stocks,
            "source": "MEROLAGANI_SCRAPED",
            "count": len(merolagani_stocks),
            "timestamp": datetime.now().isoformat(),
        }

    return {
        "stocks": [],
        "source": "UNAVAILABLE",
        "count": 0,
        "error": "Unable to fetch live stock data from NEPSE API, Sharesansar, or Merolagani",
        "timestamp": datetime.now().isoformat(),
    }


async def fetch_market_overview() -> dict[str, Any]:
    """Fetch market overview from live sources.
    PRIMARY: Real-time NEPSE Index + Market Summary from Sharesansar/Merolagani
    """
    # Get the LATEST real-time NEPSE index (bypass cache for truly real-time)
    index_data = await fetch_current_nepse_index()
    current_nepse_index = index_data.get("nepse_index", 0.0)
    
    # Get market summary (volume, advancers/decliners, etc.)
    # FALLBACK 1: Sharesansar
    sharesansar_summary = await sharesansar_client.fetch_market_summary()
    if sharesansar_summary and isinstance(sharesansar_summary, dict):
        merged_summary = {
            "nepse_index": current_nepse_index,  # USE REAL-TIME INDEX
            "nepse_change": index_data.get("nepse_change", 0.0),
            "nepse_change_percent": index_data.get("nepse_change_percent", 0.0),
            "total_turnover": sharesansar_summary.get("total_turnover", 0.0),
            "total_volume": sharesansar_summary.get("total_volume", 0),
            "total_transactions": sharesansar_summary.get("total_transactions", 0),
            "advancers": sharesansar_summary.get("advancers", 0),
            "decliners": sharesansar_summary.get("decliners", 0),
            "unchanged": sharesansar_summary.get("unchanged", 0),
        }
        if _is_plausible_nepse_index(current_nepse_index):
            logger.info(f"✓ Market overview with real-time NEPSE index: {current_nepse_index}")
            result = {
                "source": "SHARESANSAR_SCRAPE_REALTIME_INDEX",
                "data": merged_summary,
                "timestamp": datetime.now().isoformat(),
            }
            cache.set("last_valid_market_overview", result, ttl_seconds=300)
            return result

    # FALLBACK 2: Merolagani
    merolagani_summary = await merolagani_client.fetch_market_summary()
    if merolagani_summary:
        merged_summary = {
            "nepse_index": current_nepse_index,  # USE REAL-TIME INDEX
            "nepse_change": index_data.get("nepse_change", 0.0),
            "nepse_change_percent": index_data.get("nepse_change_percent", 0.0),
            "total_turnover": merolagani_summary.get("total_turnover", 0.0),
            "total_volume": merolagani_summary.get("total_volume", 0),
            "total_transactions": merolagani_summary.get("total_transactions", 0),
            "advancers": merolagani_summary.get("advancers", 0),
            "decliners": merolagani_summary.get("decliners", 0),
            "unchanged": merolagani_summary.get("unchanged", 0),
        }
        if _is_plausible_nepse_index(current_nepse_index):
            logger.info(f"✓ Market overview from Merolagani with real-time index: {current_nepse_index}")
            result = {
                "source": "MEROLAGANI_SCRAPE_REALTIME_INDEX",
                "data": merged_summary,
                "timestamp": datetime.now().isoformat(),
            }
            cache.set("last_valid_market_overview", result, ttl_seconds=300)
            return result

    # Use last valid cached result
    last_valid = cache.get("last_valid_market_overview")
    if last_valid:
        logger.info("↻ Using cached market overview")
        return cast(dict[str, Any], last_valid)

    return {
        "source": "UNAVAILABLE",
        "data": {},
        "error": "Unable to fetch live market overview from Sharesansar or Merolagani",
        "timestamp": datetime.now().isoformat(),
    }


async def fetch_nepse_index_history(days: int = 90) -> dict[str, Any]:
    """Fetch live main NEPSE index candles/history. 
    PRIMARY: NEPSE Official API
    FALLBACK: Sharesansar & Merolagani scrapers
    """
    # PRIMARY: NEPSE API (most reliable real-time source)
    try:
        # Try NEPSE API endpoint for historical data
        async with httpx.AsyncClient(verify=certifi.where() if NEPSE_SSL_VERIFY else False) as client:
            headers = await nepse_client._get_headers(client)
            resp = await client.get(
                f"{NEPSE_BASE}/nepse-data/history",
                params={"days": days, "limit": days + 10},
                headers=headers,
                timeout=15.0,
            )
            if resp.status_code == 200:
                payload = resp.json()
                history: list[dict[str, Any]] = []
                
                if isinstance(payload, list):
                    for item in payload:
                        if isinstance(item, dict):
                            try:
                                close = _parse_float(item.get("closingIndex", item.get("value", 0)))
                                if not _is_plausible_nepse_index(close):
                                    continue
                                history.append({
                                    "date": str(item.get("date", item.get("businessDate", ""))),
                                    "open": round(_parse_float(item.get("openIndex", close)), 2),
                                    "high": round(_parse_float(item.get("highIndex", close)), 2),
                                    "low": round(_parse_float(item.get("lowIndex", close)), 2),
                                    "close": round(close, 2),
                                    "change": round(_parse_float(item.get("change", 0)), 2),
                                    "change_percent": round(_parse_float(item.get("changePercent", 0)), 2),
                                    "turnover": round(_parse_float(item.get("turnover", 0)), 2),
                                })
                            except Exception:
                                continue
                elif isinstance(payload, dict) and "content" in payload:
                    for item in payload.get("content", []):
                        if isinstance(item, dict):
                            try:
                                close = _parse_float(item.get("closingIndex", item.get("value", 0)))
                                if not _is_plausible_nepse_index(close):
                                    continue
                                history.append({
                                    "date": str(item.get("date", item.get("businessDate", ""))),
                                    "open": round(_parse_float(item.get("openIndex", close)), 2),
                                    "high": round(_parse_float(item.get("highIndex", close)), 2),
                                    "low": round(_parse_float(item.get("lowIndex", close)), 2),
                                    "close": round(close, 2),
                                    "change": round(_parse_float(item.get("change", 0)), 2),
                                    "change_percent": round(_parse_float(item.get("changePercent", 0)), 2),
                                    "turnover": round(_parse_float(item.get("turnover", 0)), 2),
                                })
                            except Exception:
                                continue
                
                if history:
                    history.sort(key=lambda x: str(x.get("date", "")))
                    logger.info(f"✓ Fetched {len(history)} NEPSE index records from API")
                    result = {
                        "source": "NEPSE_API_LIVE",
                        "history": history,
                        "count": len(history),
                        "timestamp": datetime.now().isoformat(),
                    }
                    cache.set(f"last_valid_nepse_index_history_{days}", result, ttl_seconds=300)
                    return result
    except Exception as e:
        logger.warning(f"✗ NEPSE API index history failed: {e}")

    logger.warning("↻ Falling back to scrapers for index history...")

    # FALLBACK 1: Sharesansar (now with 202-retry logic)
    history = await sharesansar_client.fetch_nepse_index_history(days=days)
    if history:
        logger.info(f"↻ Fetched {len(history)} NEPSE index records from Sharesansar")
        result = {
            "source": "SHARESANSAR_SCRAPED",
            "history": history,
            "count": len(history),
            "timestamp": datetime.now().isoformat(),
        }
        cache.set(f"last_valid_nepse_index_history_{days}", result, ttl_seconds=300)
        return result

    # FALLBACK 2: Merolagani index page
    ml_history = await merolagani_client.fetch_index_history(days=days)
    if ml_history:
        logger.info(f"↻ Fetched {len(ml_history)} NEPSE index records from Merolagani")
        result = {
            "source": "MEROLAGANI_SCRAPED",
            "history": ml_history,
            "count": len(ml_history),
            "timestamp": datetime.now().isoformat(),
        }
        cache.set(f"last_valid_nepse_index_history_{days}", result, ttl_seconds=300)
        return result

    # Use last valid cached result
    last_valid = cache.get(f"last_valid_nepse_index_history_{days}")
    if last_valid:
        logger.info("↻ Using cached NEPSE index history")
        cached = cast(dict[str, Any], last_valid)
        return {
            **cached,
            "source": "CACHED",
            "timestamp": datetime.now().isoformat(),
        }

    return {
        "source": "UNAVAILABLE",
        "history": [],
        "count": 0,
        "error": "Unable to fetch live NEPSE index history from API or scrapers",
        "timestamp": datetime.now().isoformat(),
    }
