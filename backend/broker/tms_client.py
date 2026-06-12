"""
TMS (Trade Management System) client for Nepal broker portals.

All NEPSE brokers use TMS portals (hosted at tms<N>.nepse.com.np or their own
domain) for order placement.  This client speaks the TMS REST/JSON API that the
official broker web portals use internally.

Setup (env vars):
    TMS_URL       – full base URL of your broker's TMS portal
                    e.g. https://tms49.nepse.com.np
    TMS_USERNAME  – your TMS login username (usually your client code)
    TMS_PASSWORD  – your TMS password
    TMS_PIN       – transaction PIN (required for order placement)

Finding your broker's TMS URL:
    Visit https://www.nepse.com.np/market-data/top-broker or ask your broker.
    The URL pattern is usually https://tms<broker_id>.nepse.com.np.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

import httpx

logger = logging.getLogger("nepse.broker.tms")

_COMMON_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Content-Type": "application/json",
}


@dataclass
class TMSOrder:
    order_id: str
    symbol: str
    order_type: str   # "BUY" | "SELL"
    quantity: int
    price: float
    status: str       # "PENDING" | "PARTIAL" | "COMPLETE" | "CANCELLED"
    placed_at: str
    filled_quantity: int = 0
    filled_price: float = 0.0


@dataclass
class TMSOrderResult:
    success: bool
    order_id: Optional[str]
    message: str
    raw: dict[str, Any] = field(default_factory=dict)


class TMSClient:
    """Client for broker TMS (Trade Management System) portals."""

    def __init__(
        self,
        tms_url: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        pin: Optional[str] = None,
    ) -> None:
        self.tms_url = (tms_url or os.getenv("TMS_URL", "")).rstrip("/")
        self.username = username or os.getenv("TMS_USERNAME", "")
        self.password = password or os.getenv("TMS_PASSWORD", "")
        self.pin = pin or os.getenv("TMS_PIN", "")
        self._token: Optional[str] = None
        self._refresh_token: Optional[str] = None
        self._business_date: Optional[str] = None
        self._http = httpx.Client(
            headers=_COMMON_HEADERS,
            timeout=30,
            verify=False,  # TMS certs often self-signed
            follow_redirects=True,
        )

    # ─── Auth ────────────────────────────────────────────────────────────────

    def login(self) -> bool:
        """Authenticate with the TMS portal."""
        if not self.tms_url:
            logger.error("TMS_URL not configured.")
            return False
        if not self.username or not self.password:
            logger.error("TMS credentials not configured (TMS_USERNAME / TMS_PASSWORD).")
            return False
        try:
            resp = self._http.post(
                f"{self.tms_url}/tmsapi/authenticate",
                json={"username": self.username, "password": self.password},
            )
            resp.raise_for_status()
            data = resp.json()
            self._token = (
                data.get("token")
                or data.get("accessToken")
                or data.get("id_token")
                or data.get("jwtToken")
            )
            self._refresh_token = data.get("refreshToken")
            if self._token:
                self._http.headers["Authorization"] = f"Bearer {self._token}"
                self._fetch_business_date()
                logger.info("TMS login successful for %s.", self.username)
                return True
            logger.error("No token in TMS login response: %s", list(data.keys()))
            return False
        except httpx.HTTPStatusError as exc:
            logger.error("TMS login HTTP error %s: %s", exc.response.status_code, exc.response.text[:200])
            return False
        except Exception as exc:
            logger.error("TMS login failed: %s", exc)
            return False

    def _fetch_business_date(self) -> None:
        try:
            resp = self._http.get(f"{self.tms_url}/tmsapi/dashboard/client/summary")
            if resp.status_code == 200:
                data = resp.json()
                self._business_date = (
                    data.get("currentBusinessDate")
                    or data.get("businessDate")
                    or datetime.now().strftime("%Y-%m-%d")
                )
        except Exception:
            self._business_date = datetime.now().strftime("%Y-%m-%d")

    def is_authenticated(self) -> bool:
        return self._token is not None

    def ensure_authenticated(self) -> bool:
        if not self.is_authenticated():
            return self.login()
        return True

    # ─── Order placement ─────────────────────────────────────────────────────

    def place_buy_order(
        self,
        symbol: str,
        quantity: int,
        price: float,
        order_type: str = "LIMIT",   # "LIMIT" | "MARKET"
    ) -> TMSOrderResult:
        """Place a buy order."""
        return self._place_order(symbol, "BUY", quantity, price, order_type)

    def place_sell_order(
        self,
        symbol: str,
        quantity: int,
        price: float,
        order_type: str = "LIMIT",
    ) -> TMSOrderResult:
        """Place a sell order."""
        return self._place_order(symbol, "SELL", quantity, price, order_type)

    def _place_order(
        self,
        symbol: str,
        side: str,
        quantity: int,
        price: float,
        order_type: str,
    ) -> TMSOrderResult:
        if not self.ensure_authenticated():
            return TMSOrderResult(False, None, "Not authenticated")
        if not self.pin:
            return TMSOrderResult(False, None, "TMS_PIN not configured — required for order placement")

        payload = {
            "stock": {"symbol": symbol, "script": symbol},
            "orderType": order_type,
            "side": side,
            "quantity": quantity,
            "price": price,
            "transactionPin": self.pin,
            "buySell": side,
            "scripId": symbol,
            "qty": quantity,
            "rate": price,
            "pin": self.pin,
        }
        try:
            resp = self._http.post(f"{self.tms_url}/tmsapi/order/", json=payload)
            resp.raise_for_status()
            data = resp.json()
            order_id = (
                str(data.get("orderId") or data.get("id") or data.get("orderNo") or "")
            )
            message = data.get("message") or data.get("statusDescription") or "Order placed"
            logger.info("%s order placed: %s x%d @ %.2f — ID: %s", side, symbol, quantity, price, order_id)
            return TMSOrderResult(True, order_id or None, message, data)
        except httpx.HTTPStatusError as exc:
            msg = f"HTTP {exc.response.status_code}: {exc.response.text[:200]}"
            logger.error("Order placement failed: %s", msg)
            return TMSOrderResult(False, None, msg)
        except Exception as exc:
            logger.error("Order placement error: %s", exc)
            return TMSOrderResult(False, None, str(exc))

    # ─── Order management ────────────────────────────────────────────────────

    def get_orders(self, page: int = 0, size: int = 50) -> list[TMSOrder]:
        """Fetch open/recent orders."""
        if not self.ensure_authenticated():
            return []
        try:
            resp = self._http.get(
                f"{self.tms_url}/tmsapi/order/",
                params={"page": page, "size": size},
            )
            resp.raise_for_status()
            raw_orders = resp.json()
            if isinstance(raw_orders, dict):
                raw_orders = raw_orders.get("content") or raw_orders.get("orders") or []
            orders: list[TMSOrder] = []
            for item in raw_orders:
                orders.append(TMSOrder(
                    order_id=str(item.get("orderId") or item.get("id") or ""),
                    symbol=item.get("script") or item.get("symbol") or "",
                    order_type=item.get("buySell") or item.get("side") or "",
                    quantity=int(item.get("orderQuantity") or item.get("qty") or 0),
                    price=float(item.get("orderRate") or item.get("rate") or item.get("price") or 0),
                    status=item.get("orderStatusDescription") or item.get("status") or "UNKNOWN",
                    placed_at=str(item.get("createdDate") or item.get("placedAt") or ""),
                    filled_quantity=int(item.get("tradedQty") or item.get("filledQty") or 0),
                    filled_price=float(item.get("tradedRate") or item.get("avgFillPrice") or 0),
                ))
            return orders
        except Exception as exc:
            logger.error("Failed to fetch orders: %s", exc)
            return []

    def cancel_order(self, order_id: str) -> bool:
        """Cancel a pending order by ID."""
        if not self.ensure_authenticated():
            return False
        try:
            resp = self._http.delete(
                f"{self.tms_url}/tmsapi/order/{order_id}",
                json={"transactionPin": self.pin, "pin": self.pin},
            )
            resp.raise_for_status()
            logger.info("Order %s cancelled.", order_id)
            return True
        except Exception as exc:
            logger.error("Cancel order %s failed: %s", order_id, exc)
            return False

    def get_portfolio(self) -> list[dict[str, Any]]:
        """Fetch current holdings from broker portal (collateral / demat)."""
        if not self.ensure_authenticated():
            return []
        try:
            resp = self._http.get(f"{self.tms_url}/tmsapi/portfolio/")
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, list):
                return data
            return data.get("portfolioItems") or data.get("holdings") or []
        except Exception as exc:
            logger.error("Failed to fetch broker portfolio: %s", exc)
            return []

    def get_cash_balance(self) -> float:
        """Fetch available cash balance."""
        if not self.ensure_authenticated():
            return 0.0
        try:
            resp = self._http.get(f"{self.tms_url}/tmsapi/dashboard/client/summary")
            resp.raise_for_status()
            data = resp.json()
            return float(
                data.get("availableBalance")
                or data.get("cash")
                or data.get("netBalance")
                or 0.0
            )
        except Exception as exc:
            logger.error("Failed to fetch cash balance: %s", exc)
            return 0.0

    def close(self) -> None:
        self._http.close()
