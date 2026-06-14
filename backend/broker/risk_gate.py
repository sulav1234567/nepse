"""
Fail-closed safety gate for AUTONOMOUS LIVE order execution.

Any code path that would place a real order on behalf of a user without the user
present MUST pass through ``check_live_execution`` first. The gate denies by
default and only allows a trade when every condition is explicitly satisfied:

  * paper mode is off,
  * the global master arm switch is enabled,
  * the kill-switch is not active,
  * the user has personally opted in,
  * the order, daily-count and daily-loss limits are all respected.

This is the single chokepoint that prevents accidental real-money trading.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..settings import get_settings


@dataclass(frozen=True)
class GateDecision:
    allowed: bool
    reason: str


def check_live_execution(
    *,
    order_npr: float,
    trades_today: int,
    realized_loss_today_npr: float,
    user_opted_in: bool,
) -> GateDecision:
    """Return whether a single autonomous LIVE order may proceed. Denies by default."""
    s = get_settings()

    if s.broker_paper_mode:
        return GateDecision(False, "Paper mode is on — no live orders are placed.")
    if not s.autonomous_live_trading_enabled:
        return GateDecision(False, "Autonomous live trading is disabled (autonomous_live_trading_enabled=False).")
    if s.autonomous_kill_switch:
        return GateDecision(False, "Kill-switch is active — live trading is halted.")
    if not user_opted_in:
        return GateDecision(False, "User has not opted in to autonomous live trading.")
    if order_npr <= 0:
        return GateDecision(False, "Order amount must be positive.")
    if order_npr > s.autonomous_max_order_npr:
        return GateDecision(False, f"Order Rs.{order_npr:,.0f} exceeds the per-order cap Rs.{s.autonomous_max_order_npr:,.0f}.")
    if trades_today >= s.autonomous_max_trades_per_day:
        return GateDecision(False, f"Daily trade cap reached ({s.autonomous_max_trades_per_day} orders).")
    if realized_loss_today_npr >= s.autonomous_daily_loss_limit_npr:
        return GateDecision(
            False,
            f"Daily loss limit hit (Rs.{realized_loss_today_npr:,.0f} ≥ Rs.{s.autonomous_daily_loss_limit_npr:,.0f}).",
        )
    return GateDecision(True, "All risk checks passed.")
