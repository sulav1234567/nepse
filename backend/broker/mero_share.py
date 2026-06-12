"""
Mero Share (CDSC) API client.

Mero Share is Nepal's official share registry portal operated by CDSC.
This client uses the same REST endpoints as the official Mero Share mobile app.

Setup:
  Set env vars MERO_SHARE_CLIENT_ID and MERO_SHARE_PASSWORD
  (or pass credentials to the constructor).

API base: https://backend.cdsc.com.np
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

import httpx

logger = logging.getLogger("nepse.broker.mero_share")

_BASE_URL = "https://backend.cdsc.com.np"
_HEADERS = {
    "User-Agent": "MeroShare/10.8.5 (Android)",
    "Accept": "application/json",
    "Content-Type": "application/json",
}


@dataclass
class MeroShareHolding:
    symbol: str
    company_name: str
    units: float
    ltp: float
    previous_closing_price: float
    value_as_of_previous_closing: float
    total_cost: float
    wacc: float      # weighted average cost of capital (avg buy price)
    unrealized_gain: float
    unrealized_gain_pct: float


@dataclass
class MeroShareTransaction:
    transaction_date: str
    symbol: str
    company_name: str
    units: float
    rate: float
    amount: float
    transaction_type: str  # "buy" | "sell"
    remarks: str


@dataclass
class MeroSharePortfolio:
    holdings: list[MeroShareHolding] = field(default_factory=list)
    total_value: float = 0.0
    total_cost: float = 0.0
    total_gain: float = 0.0
    total_gain_pct: float = 0.0
    cash_balance: float = 0.0
    fetched_at: str = ""


class MeroShareClient:
    """Client for Mero Share (CDSC) investor portal."""

    def __init__(
        self,
        client_id: Optional[str] = None,
        password: Optional[str] = None,
        dp_id: Optional[str] = None,
    ) -> None:
        self.client_id = client_id or os.getenv("MERO_SHARE_CLIENT_ID", "")
        self.password = password or os.getenv("MERO_SHARE_PASSWORD", "")
        self.dp_id = dp_id or os.getenv("MERO_SHARE_DP_ID", "")
        self._token: Optional[str] = None
        self._demat_account: Optional[str] = None
        self._http = httpx.Client(
            base_url=_BASE_URL,
            headers=_HEADERS,
            timeout=30,
            verify=True,
        )

    # ─── Auth ───────────────────────────────────────────────────────────────

    def login(self) -> bool:
        """Authenticate with Mero Share using client credentials."""
        if not self.client_id or not self.password:
            logger.error("Mero Share credentials not set. Set MERO_SHARE_CLIENT_ID and MERO_SHARE_PASSWORD.")
            return False
        try:
            resp = self._http.post(
                "/api/meroShareClient/auth/loginWithClientId/",
                json={
                    "clientId": self.client_id,
                    "password": self.password,
                    "requestedClient": self.client_id,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            self._token = data.get("accessToken") or data.get("token")
            if self._token:
                self._http.headers["Authorization"] = f"Bearer {self._token}"
                logger.info("Mero Share login successful.")
                self._fetch_demat_account()
                return True
            logger.error("No token in login response: %s", data)
            return False
        except Exception as exc:
            logger.error("Mero Share login failed: %s", exc)
            return False

    def _fetch_demat_account(self) -> None:
        try:
            resp = self._http.get("/api/meroShareClient/myDetails/")
            resp.raise_for_status()
            data = resp.json()
            accounts = data.get("demat") or []
            if accounts:
                self._demat_account = accounts[0].get("boid") or accounts[0].get("dematNumber")
        except Exception as exc:
            logger.warning("Could not fetch demat account details: %s", exc)

    def is_authenticated(self) -> bool:
        return self._token is not None

    def ensure_authenticated(self) -> bool:
        if not self.is_authenticated():
            return self.login()
        return True

    # ─── Portfolio ───────────────────────────────────────────────────────────

    def get_portfolio(self) -> MeroSharePortfolio:
        """Fetch current holdings from Mero Share."""
        if not self.ensure_authenticated():
            return MeroSharePortfolio(fetched_at=datetime.now().isoformat())
        try:
            resp = self._http.get("/api/meroShareClient/myPurchased/")
            resp.raise_for_status()
            raw = resp.json()
            holdings: list[MeroShareHolding] = []
            total_value = 0.0
            total_cost = 0.0

            for item in raw.get("meroShareMyPurchased", []):
                units = float(item.get("totalQuantity") or item.get("quantity") or 0)
                ltp = float(item.get("lastTransactionPrice") or item.get("ltp") or 0)
                wacc = float(item.get("waccInPercent") or item.get("wacc") or item.get("avg_cost") or ltp)
                value = units * ltp
                cost = units * wacc
                gain = value - cost
                gain_pct = (gain / cost * 100) if cost > 0 else 0.0
                h = MeroShareHolding(
                    symbol=item.get("script") or item.get("symbol") or "",
                    company_name=item.get("scriptDesc") or item.get("companyName") or "",
                    units=units,
                    ltp=ltp,
                    previous_closing_price=float(item.get("previousClosingPrice") or ltp),
                    value_as_of_previous_closing=float(item.get("valueAsOfPreviousClosingPrice") or value),
                    total_cost=cost,
                    wacc=wacc,
                    unrealized_gain=round(gain, 2),
                    unrealized_gain_pct=round(gain_pct, 2),
                )
                holdings.append(h)
                total_value += value
                total_cost += cost

            total_gain = total_value - total_cost
            total_gain_pct = (total_gain / total_cost * 100) if total_cost > 0 else 0.0

            return MeroSharePortfolio(
                holdings=holdings,
                total_value=round(total_value, 2),
                total_cost=round(total_cost, 2),
                total_gain=round(total_gain, 2),
                total_gain_pct=round(total_gain_pct, 2),
                fetched_at=datetime.now().isoformat(),
            )
        except Exception as exc:
            logger.error("Failed to fetch portfolio: %s", exc)
            return MeroSharePortfolio(fetched_at=datetime.now().isoformat())

    # ─── Transactions ─────────────────────────────────────────────────────────

    def get_transactions(self, page: int = 0, size: int = 50) -> list[MeroShareTransaction]:
        """Fetch recent transactions."""
        if not self.ensure_authenticated():
            return []
        try:
            resp = self._http.get(
                "/api/meroShareClient/myPurchased/getPurchasedItemDetailsForOldPortfolio/",
                params={"page": page, "size": size},
            )
            resp.raise_for_status()
            raw = resp.json()
            txns: list[MeroShareTransaction] = []
            for item in raw.get("purchasedItems", []) or raw.get("content", []):
                txns.append(MeroShareTransaction(
                    transaction_date=str(item.get("transactionDate") or item.get("date") or ""),
                    symbol=item.get("script") or item.get("symbol") or "",
                    company_name=item.get("scriptDesc") or item.get("companyName") or "",
                    units=float(item.get("quantity") or 0),
                    rate=float(item.get("rate") or item.get("price") or 0),
                    amount=float(item.get("amount") or 0),
                    transaction_type="buy",
                    remarks=str(item.get("remarks") or ""),
                ))
            return txns
        except Exception as exc:
            logger.error("Failed to fetch transactions: %s", exc)
            return []

    def close(self) -> None:
        self._http.close()
