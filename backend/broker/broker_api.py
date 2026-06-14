"""
Unified broker API — combines Mero Share (portfolio) + TMS (order execution).

Usage:
    api = get_broker_api()
    api.connect()
    portfolio = api.get_portfolio()
    result = api.buy("NABIL", quantity=10, price=1200.0)
    result = api.sell("NABIL", quantity=5, price=1250.0)
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from functools import lru_cache
from typing import Any, Optional

from .mero_share import MeroShareClient, MeroSharePortfolio
from .tms_client import TMSClient, TMSOrderResult

logger = logging.getLogger("nepse.broker.api")


@dataclass
class TradeRecord:
    trade_id: str
    symbol: str
    action: str         # "BUY" | "SELL"
    quantity: int
    price: float
    total_amount: float
    status: str
    timestamp: str
    order_id: Optional[str] = None
    notes: str = ""


class BrokerAPI:
    """
    High-level broker API for the NEPSE autonomous trading agent.

    Combines:
    - Mero Share: actual share holdings, unrealized P&L, transaction history
    - TMS broker portal: order placement, live order status, cash balance

    Paper trading mode:
      Set env BROKER_PAPER_MODE=true to simulate all orders without
      touching your broker account.  Perfect for testing the agent.
    """

    def __init__(
        self,
        mero_share: Optional[MeroShareClient] = None,
        tms: Optional[TMSClient] = None,
        paper_mode: Optional[bool] = None,
    ) -> None:
        self.mero_share = mero_share or MeroShareClient()
        self.tms = tms or TMSClient()
        self.paper_mode: bool = (
            paper_mode
            if paper_mode is not None
            else os.getenv("BROKER_PAPER_MODE", "true").lower() in {"1", "true", "yes"}
        )
        self._paper_portfolio: dict[str, float] = {}   # symbol -> units owned
        self._paper_cash: float = float(os.getenv("BROKER_PAPER_CASH", "100000"))
        self._paper_orders: list[TradeRecord] = []
        self._is_connected = False

        # Autonomous live-trading guardrails. Off until the user explicitly opts in;
        # the risk_gate additionally requires the global arm switch + limits.
        self.autonomous_opt_in: bool = os.getenv("AUTONOMOUS_OPT_IN", "false").lower() in {"1", "true", "yes"}
        self._trade_day: str = datetime.now().strftime("%Y-%m-%d")
        self._trades_today: int = 0
        self._realized_loss_today: float = 0.0

        if self.paper_mode:
            logger.info("Broker API in PAPER TRADING mode. No real orders will be placed.")

    def _roll_day(self) -> None:
        today = datetime.now().strftime("%Y-%m-%d")
        if today != self._trade_day:
            self._trade_day = today
            self._trades_today = 0
            self._realized_loss_today = 0.0

    def _gate_autonomous_order(self, amount: float, *, is_exit: bool) -> tuple[bool, str]:
        """Apply the fail-closed risk gate to an AUTONOMOUS live order.

        Exits (sells that reduce risk) are allowed as long as the system is armed
        and the kill-switch is off; new exposure (buys) faces the full gate.
        """
        from .risk_gate import check_live_execution

        self._roll_day()
        if is_exit:
            # De-risking: ignore per-order/daily caps so stop-losses always run,
            # but still require arm + opt-in + no kill-switch.
            decision = check_live_execution(
                order_npr=1.0, trades_today=0, realized_loss_today_npr=0.0,
                user_opted_in=self.autonomous_opt_in,
            )
        else:
            decision = check_live_execution(
                order_npr=amount,
                trades_today=self._trades_today,
                realized_loss_today_npr=self._realized_loss_today,
                user_opted_in=self.autonomous_opt_in,
            )
        return decision.allowed, decision.reason

    # ─── Connection ──────────────────────────────────────────────────────────

    def connect(self) -> bool:
        """Connect to both Mero Share and TMS."""
        if self.paper_mode:
            self._is_connected = True
            return True
        ms_ok = self.mero_share.login()
        tms_ok = self.tms.login()
        self._is_connected = ms_ok or tms_ok
        if not ms_ok:
            logger.warning("Mero Share connection failed. Portfolio data unavailable.")
        if not tms_ok:
            logger.warning("TMS connection failed. Order placement unavailable.")
        return self._is_connected

    def is_connected(self) -> bool:
        return self._is_connected

    # ─── Portfolio ───────────────────────────────────────────────────────────

    def get_portfolio(self) -> MeroSharePortfolio:
        """Fetch current holdings."""
        if self.paper_mode:
            from .mero_share import MeroShareHolding
            holdings = [
                MeroShareHolding(
                    symbol=sym,
                    company_name=sym,
                    units=units,
                    ltp=0.0,
                    previous_closing_price=0.0,
                    value_as_of_previous_closing=0.0,
                    total_cost=0.0,
                    wacc=0.0,
                    unrealized_gain=0.0,
                    unrealized_gain_pct=0.0,
                )
                for sym, units in self._paper_portfolio.items()
                if units > 0
            ]
            return MeroSharePortfolio(
                holdings=holdings,
                cash_balance=self._paper_cash,
                fetched_at=datetime.now().isoformat(),
            )
        return self.mero_share.get_portfolio()

    def get_cash_balance(self) -> float:
        """Return available cash balance."""
        if self.paper_mode:
            return self._paper_cash
        return self.tms.get_cash_balance()

    def get_holding_units(self, symbol: str) -> float:
        """How many units of `symbol` do we currently hold?"""
        if self.paper_mode:
            return self._paper_portfolio.get(symbol, 0.0)
        portfolio = self.mero_share.get_portfolio()
        for h in portfolio.holdings:
            if h.symbol == symbol:
                return h.units
        return 0.0

    # ─── Order execution ─────────────────────────────────────────────────────

    def buy(
        self,
        symbol: str,
        quantity: int,
        price: float,
        notes: str = "",
        autonomous: bool = False,
    ) -> TradeRecord:
        """Place a buy order. Set autonomous=True for agent-initiated (unattended) orders."""
        amount = quantity * price
        timestamp = datetime.now().isoformat()

        # Autonomous LIVE buys must clear the fail-closed risk gate.
        if autonomous and not self.paper_mode:
            ok, reason = self._gate_autonomous_order(amount, is_exit=False)
            if not ok:
                logger.warning("Autonomous live BUY blocked by risk gate: %s", reason)
                return TradeRecord("", symbol, "BUY", quantity, price, amount, "BLOCKED", timestamp, notes=f"Risk gate: {reason}")

        if self.paper_mode:
            if self._paper_cash < amount:
                logger.warning("Paper trade: insufficient cash (%.2f < %.2f)", self._paper_cash, amount)
                return TradeRecord("", symbol, "BUY", quantity, price, amount, "REJECTED", timestamp, notes="Insufficient cash")
            self._paper_cash -= amount
            self._paper_portfolio[symbol] = self._paper_portfolio.get(symbol, 0.0) + quantity
            record = TradeRecord(
                trade_id=f"PAPER-{len(self._paper_orders)+1:04d}",
                symbol=symbol,
                action="BUY",
                quantity=quantity,
                price=price,
                total_amount=round(amount, 2),
                status="COMPLETE",
                timestamp=timestamp,
                notes=notes,
            )
            self._paper_orders.append(record)
            logger.info("[PAPER] BUY %s x%d @ %.2f = Rs.%.2f", symbol, quantity, price, amount)
            return record

        result = self.tms.place_buy_order(symbol, quantity, price)
        status = "PENDING" if result.success else "FAILED"
        if result.success and autonomous:
            self._trades_today += 1
        return TradeRecord(
            trade_id=result.order_id or "",
            symbol=symbol,
            action="BUY",
            quantity=quantity,
            price=price,
            total_amount=round(amount, 2),
            status=status,
            timestamp=timestamp,
            order_id=result.order_id,
            notes=result.message,
        )

    def sell(
        self,
        symbol: str,
        quantity: int,
        price: float,
        notes: str = "",
        autonomous: bool = False,
    ) -> TradeRecord:
        """Place a sell order. Set autonomous=True for agent-initiated (unattended) orders."""
        amount = quantity * price
        timestamp = datetime.now().isoformat()

        # Autonomous LIVE sells (exits) must clear the gate (arm + opt-in + kill-switch).
        if autonomous and not self.paper_mode:
            ok, reason = self._gate_autonomous_order(amount, is_exit=True)
            if not ok:
                logger.warning("Autonomous live SELL blocked by risk gate: %s", reason)
                return TradeRecord("", symbol, "SELL", quantity, price, amount, "BLOCKED", timestamp, notes=f"Risk gate: {reason}")

        if self.paper_mode:
            held = self._paper_portfolio.get(symbol, 0.0)
            if held < quantity:
                logger.warning("Paper trade: not enough units to sell (%s: %.0f < %d)", symbol, held, quantity)
                return TradeRecord("", symbol, "SELL", quantity, price, amount, "REJECTED", timestamp, notes="Insufficient units")
            self._paper_portfolio[symbol] = held - quantity
            self._paper_cash += amount
            record = TradeRecord(
                trade_id=f"PAPER-{len(self._paper_orders)+1:04d}",
                symbol=symbol,
                action="SELL",
                quantity=quantity,
                price=price,
                total_amount=round(amount, 2),
                status="COMPLETE",
                timestamp=timestamp,
                notes=notes,
            )
            self._paper_orders.append(record)
            logger.info("[PAPER] SELL %s x%d @ %.2f = Rs.%.2f", symbol, quantity, price, amount)
            return record

        result = self.tms.place_sell_order(symbol, quantity, price)
        status = "PENDING" if result.success else "FAILED"
        return TradeRecord(
            trade_id=result.order_id or "",
            symbol=symbol,
            action="SELL",
            quantity=quantity,
            price=price,
            total_amount=round(amount, 2),
            status=status,
            timestamp=timestamp,
            order_id=result.order_id,
            notes=result.message,
        )

    def get_trade_history(self) -> list[TradeRecord]:
        """Return list of all trades (paper or live)."""
        if self.paper_mode:
            return list(self._paper_orders)
        raw_orders = self.tms.get_orders()
        return [
            TradeRecord(
                trade_id=o.order_id,
                symbol=o.symbol,
                action=o.order_type,
                quantity=o.quantity,
                price=o.price,
                total_amount=round(o.quantity * o.price, 2),
                status=o.status,
                timestamp=o.placed_at,
                order_id=o.order_id,
            )
            for o in raw_orders
        ]

    def close(self) -> None:
        self.mero_share.close()
        self.tms.close()


_broker_api_instance: Optional[BrokerAPI] = None


def get_broker_api() -> BrokerAPI:
    global _broker_api_instance
    if _broker_api_instance is None:
        _broker_api_instance = BrokerAPI()
    return _broker_api_instance
