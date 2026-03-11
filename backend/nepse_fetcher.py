"""
NEPSE-ALPHA ULTIMATE — Real-Time NEPSE Data Fetcher
Multi-source data fetching with automatic failover.
Primary:  NEPSE official API (nepalstock.com.np)
Fallback: Demo data (built-in)
"""

import httpx
import asyncio
import time
import json
import logging
from typing import Optional, Dict, List, Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# CACHE LAYER
# ─────────────────────────────────────────────────────────────────────────────

class DataCache:
    """Simple in-memory cache with TTL."""
    def __init__(self, ttl_seconds: int = 60):
        self.ttl = ttl_seconds
        self._cache: Dict[str, Any] = {}
        self._timestamps: Dict[str, float] = {}

    def get(self, key: str) -> Optional[Any]:
        if key in self._cache:
            if time.time() - self._timestamps[key] < self.ttl:
                return self._cache[key]
            else:
                del self._cache[key]
                del self._timestamps[key]
        return None

    def set(self, key: str, value: Any):
        self._cache[key] = value
        self._timestamps[key] = time.time()

    def clear(self):
        self._cache.clear()
        self._timestamps.clear()


cache = DataCache(ttl_seconds=60)


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
    """
    def __init__(self):
        self._token: Optional[str] = None
        self._token_timestamp: float = 0
        self._token_ttl: float = 280  # Refresh every ~4.5 minutes

    async def _refresh_token(self, client: httpx.AsyncClient) -> bool:
        """Get fresh auth token from NEPSE API."""
        try:
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
                    return True
                # Some versions return token directly
                if isinstance(data, str):
                    self._token = data
                    self._token_timestamp = time.time()
                    return True
        except Exception as e:
            logger.warning(f"NEPSE token refresh failed: {e}")
        return False

    def _is_token_valid(self) -> bool:
        return self._token is not None and (time.time() - self._token_timestamp < self._token_ttl)

    async def _get_headers(self, client: httpx.AsyncClient) -> Dict[str, str]:
        if not self._is_token_valid():
            await self._refresh_token(client)
        headers = dict(HEADERS)
        if self._token:
            headers["Authorization"] = f"Salter {self._token}"
        return headers

    async def fetch_today_prices(self) -> Optional[List[Dict]]:
        """Fetch today's prices for all stocks."""
        cached = cache.get("today_prices")
        if cached:
            return cached

        try:
            async with httpx.AsyncClient() as client:
                headers = await self._get_headers(client)
                # Try paginated endpoint
                resp = await client.get(
                    f"{NEPSE_BASE}/nepse-data/today-price",
                    params={"size": 500},
                    headers=headers,
                    timeout=15.0,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    # NEPSE API returns { content: [...], totalElements: N }
                    stocks = data.get("content", data) if isinstance(data, dict) else data
                    if isinstance(stocks, list) and len(stocks) > 0:
                        cache.set("today_prices", stocks)
                        logger.info(f"Fetched {len(stocks)} stocks from NEPSE API")
                        return stocks
        except Exception as e:
            logger.warning(f"NEPSE today-price fetch failed: {e}")
        return None

    async def fetch_market_summary(self) -> Optional[Dict]:
        """Fetch market summary/overview."""
        cached = cache.get("market_summary")
        if cached:
            return cached

        try:
            async with httpx.AsyncClient() as client:
                headers = await self._get_headers(client)
                resp = await client.get(
                    f"{NEPSE_BASE}/market-open",
                    headers=headers,
                    timeout=10.0,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    cache.set("market_summary", data)
                    return data
        except Exception as e:
            logger.warning(f"NEPSE market summary fetch failed: {e}")
        return None

    async def fetch_sector_indices(self) -> Optional[List[Dict]]:
        """Fetch sub-index/sector data."""
        cached = cache.get("sector_indices")
        if cached:
            return cached

        try:
            async with httpx.AsyncClient() as client:
                headers = await self._get_headers(client)
                resp = await client.get(
                    f"{NEPSE_BASE}/nepse-data/sub-index",
                    headers=headers,
                    timeout=10.0,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    if isinstance(data, list):
                        cache.set("sector_indices", data)
                        return data
        except Exception as e:
            logger.warning(f"NEPSE sector indices fetch failed: {e}")
        return None


nepse_client = NepseClient()


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


def normalize_nepse_stock(raw: Dict) -> Optional[Dict]:
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

async def fetch_all_stocks() -> Dict[str, Any]:
    """
    Fetch all stocks. Returns dict with 'stocks' list and 'source' indicator.
    Falls back to demo data if API unavailable.
    """
    # Try NEPSE API
    raw_data = await nepse_client.fetch_today_prices()
    if raw_data:
        stocks = []
        for raw in raw_data:
            normalized = normalize_nepse_stock(raw)
            if normalized:
                stocks.append(normalized)
        if len(stocks) > 0:
            return {
                "stocks": stocks,
                "source": "LIVE",
                "count": len(stocks),
                "timestamp": datetime.now().isoformat(),
            }

    # Fallback: Demo data
    from .demo_data import DEMO_STOCKS
    demo_stocks = []
    for s in DEMO_STOCKS:
        demo_stocks.append({
            "symbol": s.symbol,
            "name": s.name,
            "sector": s.sector,
            "cmp": s.cmp,
            "previousClose": s.previous_close,
            "change": s.change,
            "changePercent": s.change_percent,
            "volume": s.volume,
            "avgVolume20d": s.avg_volume_20d,
            "high52w": s.high_52w,
            "low52w": s.low_52w,
            "eps": s.eps,
            "pe": s.pe,
            "pb": s.pb,
            "roe": s.roe,
            "dividendYield": s.dividend_yield,
            "bookValue": s.book_value,
            "marketCap": s.market_cap,
            "open": s.cmp,
            "high": s.cmp,
            "low": s.cmp,
            "totalTrades": 0,
            "turnover": 0,
        })
    return {
        "stocks": demo_stocks,
        "source": "DEMO",
        "count": len(demo_stocks),
        "timestamp": datetime.now().isoformat(),
    }


async def fetch_market_overview() -> Dict[str, Any]:
    """Fetch market overview. Falls back to demo."""
    summary = await nepse_client.fetch_market_summary()
    if summary:
        return {
            "source": "LIVE",
            "data": summary,
            "timestamp": datetime.now().isoformat(),
        }

    from .demo_data import DEMO_MARKET
    return {
        "source": "DEMO",
        "data": DEMO_MARKET.model_dump(),
        "timestamp": datetime.now().isoformat(),
    }
