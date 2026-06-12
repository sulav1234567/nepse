"""
Autonomous NEPSE Trading Agent.

This is your personal CA (chartered accountant / autonomous agent) that:
  1. Scans all NEPSE stocks with the ML ensemble + 5-layer engine
  2. Identifies the highest-conviction BUY opportunities
  3. Sizes positions using the Kelly criterion (fraction)
  4. Places buy orders via the broker API
  5. Monitors open positions and exits when the sell zone is hit or stop-loss triggers
  6. Never risks more than MAX_POSITION_PCT of portfolio on a single stock

Architecture:
    AutonomousTradingAgent
        └── AutonomousResearchPlatform  (ML signals)
        └── BrokerAPI                   (Mero Share + TMS)
        └── RiskManager                 (position sizing, drawdown guard)
        └── TradingJournal              (persistent trade log)
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime, date
from pathlib import Path
from threading import Lock
from typing import Any, Coroutine, Optional

import numpy as np

logger = logging.getLogger("nepse.trading_agent")


def _run_async(coro: Coroutine) -> Any:
    """Run an async coroutine from sync code, even inside a running event loop."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(asyncio.run, coro).result()

# ─── Configuration ────────────────────────────────────────────────────────────

MAX_POSITION_PCT = float(os.getenv("AGENT_MAX_POSITION_PCT", "0.12"))    # 12% max per stock
MIN_RISE_PROBABILITY = float(os.getenv("AGENT_MIN_RISE_PROBABILITY", "68.0"))  # require ≥68% rise probability
MIN_RISK_REWARD = float(os.getenv("AGENT_MIN_RISK_REWARD", "1.5"))        # require ≥1.5 R:R
MAX_OPEN_POSITIONS = int(os.getenv("AGENT_MAX_OPEN_POSITIONS", "10"))     # max concurrent stocks
KELLY_FRACTION = float(os.getenv("AGENT_KELLY_FRACTION", "0.3"))          # fractional Kelly (conservative)
MIN_TRADE_AMOUNT_NPR = float(os.getenv("AGENT_MIN_TRADE_NPR", "5000"))    # minimum trade Rs.5,000
MAX_DRAWDOWN_PCT = float(os.getenv("AGENT_MAX_DRAWDOWN_PCT", "15.0"))     # halt if portfolio drops >15%
TRAILING_STOP_PCT = float(os.getenv("AGENT_TRAILING_STOP_PCT", "0.05"))   # 5% trailing stop


# ─── Data classes ─────────────────────────────────────────────────────────────

@dataclass
class AgentPosition:
    symbol: str
    sector: str
    units: int
    entry_price: float
    entry_date: str
    stop_loss: float
    target_1: float
    target_2: float
    current_price: float = 0.0
    highest_price: float = 0.0    # for trailing stop
    unrealized_pnl: float = 0.0
    unrealized_pnl_pct: float = 0.0
    ml_confidence: float = 0.0
    signal_score: float = 0.0
    status: str = "OPEN"          # OPEN | STOP_HIT | TARGET_HIT | MANUAL_EXIT
    exit_price: float = 0.0
    exit_date: str = ""
    realized_pnl: float = 0.0


@dataclass
class AgentSignal:
    symbol: str
    sector: str
    cmp: float
    rise_probability: float
    predicted_change_pct: float
    confidence: str              # LOW | MEDIUM | HIGH | VERY HIGH
    action: str                  # STRONG BUY | BUY | SPECULATIVE BUY | HOLD | AVOID
    risk_reward: float
    ideal_entry: float
    stop_loss: float
    target_1: float
    target_2: float
    fcs_score: float
    ml_vote: str                 # directional bias from ensemble
    reasoning: str
    kelly_size_pct: float = 0.0  # position size as % of portfolio


@dataclass
class AgentRunSummary:
    run_id: str
    started_at: str
    finished_at: str
    stocks_scanned: int
    signals_found: int
    orders_placed: int
    orders_failed: int
    positions_exited: int
    portfolio_value: float
    cash_balance: float
    total_pnl: float
    top_signals: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass
class AgentStatus:
    is_running: bool = False
    mode: str = "paper"               # paper | live
    last_run_at: Optional[str] = None
    next_run_at: Optional[str] = None
    open_positions: int = 0
    total_trades: int = 0
    total_realized_pnl: float = 0.0
    portfolio_value: float = 0.0
    cash_balance: float = 0.0
    peak_portfolio_value: float = 0.0
    max_drawdown_pct: float = 0.0
    win_rate: float = 0.0
    last_run_summary: Optional[dict[str, Any]] = None


# ─── Risk Manager ─────────────────────────────────────────────────────────────

class RiskManager:
    """Kelly criterion position sizing + drawdown guard."""

    def kelly_position_size(
        self,
        cash_available: float,
        rise_probability: float,    # 0-100
        win_loss_ratio: float,      # expected gain / expected loss (risk:reward)
        kelly_fraction: float = KELLY_FRACTION,
    ) -> float:
        """
        Full Kelly: f* = (p * b - q) / b
        where p = win probability, q = 1-p, b = win/loss ratio.
        Returns fraction of portfolio to allocate.
        """
        p = rise_probability / 100.0
        q = 1 - p
        if win_loss_ratio <= 0:
            return 0.0
        kelly_full = (p * win_loss_ratio - q) / win_loss_ratio
        kelly_scaled = max(0.0, min(kelly_fraction * kelly_full, MAX_POSITION_PCT))
        return kelly_scaled

    def size_in_units(
        self,
        price: float,
        portfolio_value: float,
        allocation_fraction: float,
    ) -> int:
        """Convert portfolio fraction to integer share units."""
        if price <= 0 or portfolio_value <= 0:
            return 0
        amount = portfolio_value * allocation_fraction
        amount = max(MIN_TRADE_AMOUNT_NPR, amount)
        units = int(amount / price)
        return max(0, units)

    def check_drawdown(
        self,
        current_value: float,
        peak_value: float,
    ) -> tuple[float, bool]:
        """Returns (drawdown_pct, should_halt)."""
        if peak_value <= 0:
            return 0.0, False
        drawdown = (peak_value - current_value) / peak_value * 100
        return round(drawdown, 2), drawdown >= MAX_DRAWDOWN_PCT


# ─── Trading Journal ──────────────────────────────────────────────────────────

class TradingJournal:
    """Persistent log of all positions and trades (stored as JSON lines)."""

    def __init__(self, journal_path: Optional[str] = None) -> None:
        self.path = Path(journal_path or os.getenv("AGENT_JOURNAL_PATH", "./backend/trading_journal.jsonl"))
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def log_position(self, position: AgentPosition) -> None:
        import json
        with self.path.open("a") as f:
            f.write(json.dumps({"type": "position", **asdict(position)}) + "\n")

    def log_summary(self, summary: AgentRunSummary) -> None:
        import json
        with self.path.open("a") as f:
            f.write(json.dumps({"type": "run_summary", **asdict(summary)}) + "\n")

    def load_open_positions(self) -> list[AgentPosition]:
        import json
        positions: dict[str, AgentPosition] = {}
        try:
            for line in self.path.read_text().splitlines():
                item = json.loads(line)
                if item.get("type") == "position":
                    sym = item["symbol"]
                    pos = AgentPosition(**{k: v for k, v in item.items() if k != "type"})
                    positions[sym] = pos
        except (FileNotFoundError, json.JSONDecodeError):
            pass
        return [p for p in positions.values() if p.status == "OPEN"]

    def load_all_positions(self) -> list[AgentPosition]:
        import json
        positions: list[AgentPosition] = []
        try:
            for line in self.path.read_text().splitlines():
                item = json.loads(line)
                if item.get("type") == "position":
                    positions.append(AgentPosition(**{k: v for k, v in item.items() if k != "type"}))
        except (FileNotFoundError, json.JSONDecodeError):
            pass
        return positions


# ─── Main Agent ───────────────────────────────────────────────────────────────

class AutonomousTradingAgent:
    """
    Your personal CA — scans NEPSE every market session and manages your portfolio.

    Quick start:
        agent = AutonomousTradingAgent()
        agent.run_once()          # one scan-and-trade cycle

    Paper mode (default, safe to test):
        Set BROKER_PAPER_MODE=true (or pass paper_mode=True) — all orders are
        simulated. Switch to live=True only when you're satisfied with performance.
    """

    def __init__(
        self,
        paper_mode: Optional[bool] = None,
    ) -> None:
        from ..broker.broker_api import get_broker_api, BrokerAPI
        self.broker: BrokerAPI = get_broker_api()
        if paper_mode is not None:
            self.broker.paper_mode = paper_mode
        self.risk = RiskManager()
        self.journal = TradingJournal()
        self._lock = Lock()
        self._status = AgentStatus(
            mode="paper" if self.broker.paper_mode else "live",
        )
        self._open_positions: list[AgentPosition] = self.journal.load_open_positions()
        self._peak_portfolio_value: float = 0.0

    # ─── Core scan ────────────────────────────────────────────────────────────

    def _load_local_history(self, symbol: str, bars: int = 120) -> list[Any]:
        """Load recent OHLCV history for a symbol from the local CSV store."""
        from ..models import HistoricalPrice

        csv_path = Path("data/market/stocks") / f"{symbol.upper()}.csv"
        if not csv_path.exists():
            return []
        try:
            import pandas as pd
            frame = pd.read_csv(csv_path).tail(bars)
            return [
                HistoricalPrice(
                    date=str(row["date"]),
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    volume=int(float(row["volume"] or 0)),
                )
                for _, row in frame.iterrows()
                if float(row.get("close") or 0) > 0
            ]
        except Exception as exc:
            logger.debug("Local history load failed for %s: %s", symbol, exc)
            return []

    def scan_market(self) -> list[AgentSignal]:
        """
        Fetch live market data and run ML + 5-layer analysis on all stocks.
        Returns signals sorted by conviction.
        """
        from ..nepse_fetcher import fetch_all_stocks, fetch_market_overview
        from ..ml_predictor import predictor as ml_predictor
        from ..engine import analyze_stock
        from ..predictions import detect_regime
        from ..models import StockData, HistoricalPrice, LayerWeights

        try:
            weights = LayerWeights(fvl=0.22, tml=0.28, ssil=0.15, gtbil=0.15, mrlll=0.20)
        except Exception:
            weights = None

        logger.info("Scanning NEPSE market...")
        try:
            payload = _run_async(fetch_all_stocks())
            all_stocks = payload.get("stocks", []) if isinstance(payload, dict) else []
        except Exception as exc:
            logger.error("Failed to fetch market data: %s", exc)
            return []

        if not all_stocks:
            return []

        # Regime detection — penalize signals in bear/volatile markets
        try:
            from ..server import create_market_overview_from_data

            overview_payload = _run_async(fetch_market_overview())
            market_overview = _run_async(
                create_market_overview_from_data(overview_payload.get("data", {}))
            )
            regime = detect_regime(market_overview)
        except Exception as exc:
            logger.warning("Regime detection unavailable: %s", exc)
            regime = None

        # ML predictions for all stocks
        try:
            ml_preds = ml_predictor.predict(all_stocks, market_regime=getattr(regime, "regime", None))
            ml_pred_map = {p["symbol"]: p for p in ml_preds}
        except Exception as exc:
            logger.warning("ML prediction failed: %s", exc)
            ml_pred_map = {}

        signals: list[AgentSignal] = []

        for stock_raw in all_stocks:
            symbol = stock_raw.get("symbol", "")
            cmp = float(stock_raw.get("cmp") or stock_raw.get("ltp") or 0)
            if not symbol or cmp <= 0:
                continue

            ml = ml_pred_map.get(symbol, {})
            rise_prob = float(ml.get("riseProbability", 50.0))
            action = ml.get("action", "HOLD")
            confidence = ml.get("confidence", "LOW")
            rr = float(ml.get("riskRewardRatio", 1.0))
            stop_loss = float(ml.get("stopLoss", cmp * 0.95))
            target_1 = float(ml.get("sellRangeLow", cmp * 1.05))
            target_2 = float(ml.get("sellRangeHigh", cmp * 1.10))
            ideal_entry = float(ml.get("idealEntry", cmp))
            pred_change_pct = float(ml.get("predictedChangePercent", 0.0))
            reasoning = ml.get("reasoning", "")

            # 5-layer FCS score
            fcs_score = 50.0
            try:
                from ..models import StockData, HistoricalPrice, LayerWeights
                sd = StockData(
                    symbol=symbol,
                    name=stock_raw.get("name") or symbol,
                    sector=stock_raw.get("sector") or "Others",
                    cmp=cmp,
                    open=float(stock_raw.get("open") or cmp),
                    high=float(stock_raw.get("high") or cmp),
                    low=float(stock_raw.get("low") or cmp),
                    previous_close=float(stock_raw.get("previousClose") or cmp),
                    change=float(stock_raw.get("change") or 0),
                    change_percent=float(stock_raw.get("changePercent") or 0),
                    volume=int(stock_raw.get("volume") or 0),
                    avg_volume_20d=int(stock_raw.get("avgVolume20d") or stock_raw.get("volume") or 1),
                    high_52w=float(stock_raw.get("high52w") or cmp * 1.3),
                    low_52w=float(stock_raw.get("low52w") or cmp * 0.7),
                    market_cap=float(stock_raw.get("marketCap") or 0),
                    pe=float(stock_raw.get("pe") or 0),
                    pb=float(stock_raw.get("pb") or 0),
                    eps=float(stock_raw.get("eps") or 0),
                    book_value=float(stock_raw.get("bookValue") or 0),
                    roe=float(stock_raw.get("roe") or 0),
                    dividend_yield=float(stock_raw.get("dividendYield") or 0),
                )
                if weights is not None:
                    from ..engine import analyze_stock
                    history = self._load_local_history(symbol)
                    if history:
                        analysis = analyze_stock(sd, history, weights)
                        fcs_score = float(analysis.fcs.score)
            except Exception as exc:
                logger.debug("FCS analysis failed for %s: %s", symbol, exc)

            # Kelly position sizing
            kelly_pct = self.risk.kelly_position_size(
                cash_available=self.broker.get_cash_balance(),
                rise_probability=rise_prob,
                win_loss_ratio=max(rr, 0.1),
            )

            signals.append(AgentSignal(
                symbol=symbol,
                sector=stock_raw.get("sector") or "Others",
                cmp=cmp,
                rise_probability=rise_prob,
                predicted_change_pct=pred_change_pct,
                confidence=confidence,
                action=action,
                risk_reward=rr,
                ideal_entry=ideal_entry,
                stop_loss=stop_loss,
                target_1=target_1,
                target_2=target_2,
                fcs_score=fcs_score,
                ml_vote=ml.get("modelScores", {}) and action or "HOLD",
                reasoning=reasoning,
                kelly_size_pct=round(kelly_pct * 100, 2),
            ))

        # Sort: highest rise_probability * risk_reward * fcs_score
        signals.sort(
            key=lambda s: s.rise_probability * max(0.1, s.risk_reward) * (s.fcs_score / 100),
            reverse=True,
        )
        logger.info("Scanned %d stocks, %d actionable signals.", len(all_stocks), sum(1 for s in signals if s.action in ("STRONG BUY", "BUY")))
        return signals

    # ─── Position monitoring ─────────────────────────────────────────────────

    def monitor_positions(self, live_prices: dict[str, float]) -> list[AgentPosition]:
        """Check open positions against stop-loss / targets. Return exits."""
        exited: list[AgentPosition] = []
        with self._lock:
            for pos in list(self._open_positions):
                cmp = live_prices.get(pos.symbol, pos.current_price)
                if cmp <= 0:
                    continue

                pos.current_price = cmp
                pos.highest_price = max(pos.highest_price or cmp, cmp)
                pnl = (cmp - pos.entry_price) * pos.units
                pos.unrealized_pnl = round(pnl, 2)
                pos.unrealized_pnl_pct = round((cmp / pos.entry_price - 1) * 100, 2) if pos.entry_price > 0 else 0

                # Trailing stop: if price moved up, ratchet the stop
                trailing_stop = pos.highest_price * (1 - TRAILING_STOP_PCT)
                effective_stop = max(pos.stop_loss, trailing_stop)

                reason = None
                exit_price = cmp

                if cmp <= effective_stop:
                    reason = f"Stop loss hit (price {cmp:.2f} <= stop {effective_stop:.2f})"
                    pos.status = "STOP_HIT"
                elif cmp >= pos.target_2:
                    reason = f"Target 2 hit (price {cmp:.2f} >= target {pos.target_2:.2f})"
                    pos.status = "TARGET_HIT"
                elif cmp >= pos.target_1 and pos.units > 1:
                    # Partial exit at target 1: sell half
                    partial_units = max(1, pos.units // 2)
                    logger.info("Partial exit: selling %d units of %s at T1 %.2f", partial_units, pos.symbol, cmp)
                    self.broker.sell(pos.symbol, partial_units, cmp, notes="Partial exit at T1")
                    pos.units -= partial_units
                    pos.target_1 = pos.target_2   # now wait for T2 with remainder
                    self.journal.log_position(pos)
                    continue

                if reason:
                    logger.info("Exiting %s: %s", pos.symbol, reason)
                    trade = self.broker.sell(pos.symbol, pos.units, exit_price, notes=reason)
                    pos.exit_price = exit_price
                    pos.exit_date = datetime.now().isoformat()
                    pos.realized_pnl = round((exit_price - pos.entry_price) * pos.units, 2)
                    self.journal.log_position(pos)
                    self._open_positions.remove(pos)
                    exited.append(pos)
                    self._status.total_realized_pnl += pos.realized_pnl
                    self._status.total_trades += 1

        return exited

    # ─── Buy logic ────────────────────────────────────────────────────────────

    def execute_buys(
        self,
        signals: list[AgentSignal],
        portfolio_value: float,
        cash: float,
    ) -> list[AgentPosition]:
        """Execute the top buy signals that pass risk filters."""
        open_symbols = {p.symbol for p in self._open_positions}
        already_at_max = len(self._open_positions) >= MAX_OPEN_POSITIONS

        new_positions: list[AgentPosition] = []
        for sig in signals:
            if already_at_max:
                logger.info("Max open positions (%d) reached. No new buys.", MAX_OPEN_POSITIONS)
                break

            # Skip if already holding
            if sig.symbol in open_symbols:
                continue

            # Conviction gate
            if sig.rise_probability < MIN_RISE_PROBABILITY:
                continue
            if sig.risk_reward < MIN_RISK_REWARD:
                continue
            if sig.action not in ("STRONG BUY", "BUY"):
                continue

            # Cash gate
            kelly_pct = self.risk.kelly_position_size(
                cash_available=cash,
                rise_probability=sig.rise_probability,
                win_loss_ratio=sig.risk_reward,
            )
            units = self.risk.size_in_units(sig.cmp, portfolio_value, kelly_pct)
            cost = units * sig.cmp
            if units == 0 or cost < MIN_TRADE_AMOUNT_NPR:
                continue
            if cost > cash:
                # Scale down to available cash
                units = int(cash * kelly_pct / sig.cmp)
                cost = units * sig.cmp
            if units == 0 or cost < MIN_TRADE_AMOUNT_NPR:
                continue

            # Place order
            logger.info(
                "BUYING %s: %d units @ Rs.%.2f (prob=%.1f%%, R:R=%.2f, kelly=%.1f%%)",
                sig.symbol, units, sig.cmp, sig.rise_probability, sig.risk_reward, kelly_pct * 100,
            )
            trade = self.broker.buy(
                symbol=sig.symbol,
                quantity=units,
                price=sig.cmp,
                notes=f"ML: {sig.action}, prob={sig.rise_probability:.1f}%, R:R={sig.risk_reward:.2f}",
            )

            if trade.status in ("COMPLETE", "PENDING"):
                pos = AgentPosition(
                    symbol=sig.symbol,
                    sector=sig.sector,
                    units=units,
                    entry_price=sig.cmp,
                    entry_date=datetime.now().isoformat(),
                    stop_loss=sig.stop_loss,
                    target_1=sig.target_1,
                    target_2=sig.target_2,
                    current_price=sig.cmp,
                    highest_price=sig.cmp,
                    ml_confidence=sig.rise_probability,
                    signal_score=sig.fcs_score,
                )
                with self._lock:
                    self._open_positions.append(pos)
                self.journal.log_position(pos)
                new_positions.append(pos)
                cash -= cost
                already_at_max = len(self._open_positions) >= MAX_OPEN_POSITIONS

        return new_positions

    # ─── Full agent cycle ────────────────────────────────────────────────────

    def run_once(self) -> AgentRunSummary:
        """
        Run one complete agent cycle:
          1. Connect to broker
          2. Check current portfolio value / drawdown guard
          3. Monitor open positions for exits
          4. Scan market for new buy signals
          5. Execute top-ranked buys

        Safe to call on a schedule (e.g., every market day at 11:00 NST).
        """
        run_id = datetime.now().strftime("RUN-%Y%m%d-%H%M%S")
        started_at = datetime.now().isoformat()
        errors: list[str] = []
        orders_placed = 0
        orders_failed = 0
        positions_exited = 0
        top_signals: list[dict[str, Any]] = []

        logger.info("=== Agent cycle %s START ===", run_id)
        self._status.is_running = True
        self._status.last_run_at = started_at

        # 1. Connect
        if not self.broker.is_connected():
            ok = self.broker.connect()
            if not ok:
                errors.append("Broker connection failed")
                logger.warning("Broker connection failed — running in offline mode")

        # 2. Portfolio health check
        portfolio = self.broker.get_portfolio()
        cash = self.broker.get_cash_balance()
        portfolio_value = portfolio.total_value + cash

        if portfolio_value == 0 and self.broker.paper_mode:
            portfolio_value = self.broker.get_cash_balance()

        if self._peak_portfolio_value == 0:
            self._peak_portfolio_value = portfolio_value
        self._peak_portfolio_value = max(self._peak_portfolio_value, portfolio_value)

        drawdown, should_halt = self.risk.check_drawdown(portfolio_value, self._peak_portfolio_value)
        if should_halt:
            msg = f"DRAWDOWN HALT: portfolio dropped {drawdown:.1f}% from peak. No new buys."
            logger.warning(msg)
            errors.append(msg)
        else:
            # 3. Monitor open positions
            live_prices = {h.symbol: h.ltp for h in portfolio.holdings if h.ltp > 0}
            exited = self.monitor_positions(live_prices)
            positions_exited = len(exited)
            if positions_exited:
                cash = self.broker.get_cash_balance()    # refresh after exits

            # 4. Scan market
            signals = self.scan_market()
            top_signals = [
                {
                    "symbol": s.symbol,
                    "sector": s.sector,
                    "cmp": s.cmp,
                    "rise_probability": s.rise_probability,
                    "action": s.action,
                    "risk_reward": s.risk_reward,
                    "kelly_size_pct": s.kelly_size_pct,
                    "reasoning": s.reasoning[:120] if s.reasoning else "",
                }
                for s in signals[:10]
            ]

            # 5. Execute buys
            if signals and cash >= MIN_TRADE_AMOUNT_NPR:
                new_positions = self.execute_buys(signals, portfolio_value, cash)
                orders_placed = len(new_positions)
                orders_failed = sum(
                    1 for s in signals[:MAX_OPEN_POSITIONS]
                    if s.action in ("STRONG BUY", "BUY")
                    and s.symbol not in {p.symbol for p in self._open_positions}
                ) - orders_placed
                orders_failed = max(0, orders_failed)

        # Update status
        self._status.open_positions = len(self._open_positions)
        self._status.portfolio_value = portfolio_value
        self._status.cash_balance = cash
        self._status.peak_portfolio_value = self._peak_portfolio_value
        self._status.max_drawdown_pct = drawdown
        all_closed = [p for p in self.journal.load_all_positions() if p.status != "OPEN"]
        if all_closed:
            wins = sum(1 for p in all_closed if p.realized_pnl > 0)
            self._status.win_rate = round(wins / len(all_closed) * 100, 1)
        self._status.is_running = False

        summary = AgentRunSummary(
            run_id=run_id,
            started_at=started_at,
            finished_at=datetime.now().isoformat(),
            stocks_scanned=len(top_signals),
            signals_found=sum(1 for s in (signals if "signals" in dir() else []) if s.action in ("STRONG BUY", "BUY")),
            orders_placed=orders_placed,
            orders_failed=orders_failed,
            positions_exited=positions_exited,
            portfolio_value=portfolio_value,
            cash_balance=cash,
            total_pnl=self._status.total_realized_pnl,
            top_signals=top_signals,
            errors=errors,
        )
        self._status.last_run_summary = asdict(summary)
        self.journal.log_summary(summary)
        logger.info("=== Agent cycle %s DONE: placed=%d, exited=%d, pnl=%.2f ===",
                    run_id, orders_placed, positions_exited, self._status.total_realized_pnl)
        return summary

    # ─── Status / control ────────────────────────────────────────────────────

    def get_status(self) -> dict[str, Any]:
        return {
            **self._status.__dict__,
            "open_positions": [asdict(p) for p in self._open_positions],
        }

    def get_open_positions(self) -> list[AgentPosition]:
        return list(self._open_positions)

    def force_exit_position(self, symbol: str, reason: str = "Manual exit") -> bool:
        """Manually close a specific position immediately."""
        with self._lock:
            for pos in list(self._open_positions):
                if pos.symbol == symbol:
                    cmp = pos.current_price or pos.entry_price
                    trade = self.broker.sell(pos.symbol, pos.units, cmp, notes=reason)
                    pos.exit_price = cmp
                    pos.exit_date = datetime.now().isoformat()
                    pos.realized_pnl = round((cmp - pos.entry_price) * pos.units, 2)
                    pos.status = "MANUAL_EXIT"
                    self.journal.log_position(pos)
                    self._open_positions.remove(pos)
                    self._status.total_realized_pnl += pos.realized_pnl
                    self._status.total_trades += 1
                    logger.info("Force-exited %s at %.2f, P&L=%.2f", symbol, cmp, pos.realized_pnl)
                    return True
        return False

    def get_recommendations(self, top_n: int = 20) -> list[dict[str, Any]]:
        """Get top buy recommendations without placing orders."""
        signals = self.scan_market()
        return [
            {
                "rank": i + 1,
                "symbol": s.symbol,
                "sector": s.sector,
                "cmp": s.cmp,
                "rise_probability": s.rise_probability,
                "action": s.action,
                "confidence": s.confidence,
                "risk_reward": s.risk_reward,
                "stop_loss": s.stop_loss,
                "target_1": s.target_1,
                "target_2": s.target_2,
                "kelly_size_pct": s.kelly_size_pct,
                "fcs_score": s.fcs_score,
                "reasoning": s.reasoning,
            }
            for i, s in enumerate(signals[:top_n])
        ]

    def audit_portfolio(self) -> dict[str, Any]:
        """
        Fetch the Mero Share portfolio and audit it with the AI signal engine.

        Each holding gets the model's current verdict (action, rise probability,
        FCS score) plus rule-based findings: concentration, sector exposure,
        unrealized P&L outliers, and model disagreement with what is held.
        """
        portfolio = self.broker.get_portfolio()
        cash = self.broker.get_cash_balance()
        fetched_at = portfolio.fetched_at or datetime.now().isoformat()

        if not portfolio.holdings:
            return {
                "fetched_at": fetched_at,
                "mode": self._status.mode,
                "health_score": 0,
                "summary": "No holdings found in the portfolio. Connect Mero Share or place trades first.",
                "totals": {"value": 0.0, "cost": 0.0, "gain": 0.0, "gain_pct": 0.0, "cash": cash},
                "holdings": [],
                "findings": [],
                "sector_exposure": [],
            }

        signals = {s.symbol: s for s in self.scan_market()}

        audited: list[dict[str, Any]] = []
        total_value = 0.0
        for h in portfolio.holdings:
            sig = signals.get(h.symbol)
            price = (sig.cmp if sig else 0.0) or h.ltp or h.wacc
            value = h.units * price
            total_value += value
            audited.append({
                "symbol": h.symbol,
                "company_name": h.company_name,
                "units": h.units,
                "wacc": h.wacc,
                "ltp": price,
                "value": round(value, 2),
                "unrealized_gain": h.unrealized_gain,
                "unrealized_gain_pct": h.unrealized_gain_pct,
                "sector": sig.sector if sig else "Unknown",
                "ai_action": sig.action if sig else "NO DATA",
                "rise_probability": sig.rise_probability if sig else None,
                "fcs_score": sig.fcs_score if sig else None,
                "stop_loss": sig.stop_loss if sig else None,
                "target_1": sig.target_1 if sig else None,
                "ai_reasoning": sig.reasoning if sig else "No live signal available for this symbol.",
            })

        for item in audited:
            item["weight_pct"] = round(item["value"] / total_value * 100, 2) if total_value > 0 else 0.0

        sector_value: dict[str, float] = {}
        for item in audited:
            sector_value[item["sector"]] = sector_value.get(item["sector"], 0.0) + item["value"]
        sector_exposure = sorted(
            (
                {"sector": sec, "value": round(val, 2), "weight_pct": round(val / total_value * 100, 2) if total_value > 0 else 0.0}
                for sec, val in sector_value.items()
            ),
            key=lambda s: s["value"],
            reverse=True,
        )

        findings: list[dict[str, str]] = []
        score = 100.0

        for item in audited:
            if item["weight_pct"] > 30:
                findings.append({
                    "severity": "critical",
                    "title": f"{item['symbol']} is {item['weight_pct']:.0f}% of the portfolio",
                    "detail": "A single stock above 30% exposes the portfolio to company-specific risk. Consider trimming.",
                })
                score -= 12
            elif item["weight_pct"] > 20:
                findings.append({
                    "severity": "warning",
                    "title": f"{item['symbol']} is {item['weight_pct']:.0f}% of the portfolio",
                    "detail": "Above 20% in one stock is aggressive. Watch this position closely.",
                })
                score -= 6

            if item["ai_action"] in {"SELL", "STRONG SELL"}:
                findings.append({
                    "severity": "warning",
                    "title": f"Model rates {item['symbol']} a {item['ai_action']}",
                    "detail": item["ai_reasoning"] or "The model expects this holding to underperform.",
                })
                score -= 6
            if item["unrealized_gain_pct"] < -15:
                findings.append({
                    "severity": "critical",
                    "title": f"{item['symbol']} is down {abs(item['unrealized_gain_pct']):.1f}%",
                    "detail": "Large unrealized loss. Decide deliberately: average down, hold, or cut — don't drift.",
                })
                score -= 8
            elif item["unrealized_gain_pct"] > 25 and item["ai_action"] not in {"BUY", "STRONG BUY"}:
                findings.append({
                    "severity": "info",
                    "title": f"{item['symbol']} is up {item['unrealized_gain_pct']:.1f}% and the model no longer rates it a buy",
                    "detail": "Consider booking partial profit or tightening the stop.",
                })
                score -= 2

        if sector_exposure and sector_exposure[0]["weight_pct"] > 50 and sector_exposure[0]["sector"] != "Unknown":
            findings.append({
                "severity": "warning",
                "title": f"{sector_exposure[0]['sector']} sector is {sector_exposure[0]['weight_pct']:.0f}% of the portfolio",
                "detail": "Heavy sector concentration: one regulatory or sector-wide shock hits most of the portfolio.",
            })
            score -= 8

        if len(audited) < 3:
            findings.append({
                "severity": "warning",
                "title": f"Only {len(audited)} holding(s)",
                "detail": "Fewer than 3 holdings gives little diversification benefit.",
            })
            score -= 8

        portfolio_total = total_value + cash
        if portfolio_total > 0 and cash / portfolio_total > 0.5:
            findings.append({
                "severity": "info",
                "title": f"{cash / portfolio_total * 100:.0f}% of capital is idle cash",
                "detail": "Large idle cash drags returns. Deploy gradually into model-rated buys if conviction allows.",
            })
            score -= 3

        buys = sum(1 for i in audited if i["ai_action"] in {"BUY", "STRONG BUY"})
        if audited and buys >= max(1, len(audited) // 2):
            findings.append({
                "severity": "good",
                "title": f"Model still rates {buys} of {len(audited)} holdings a buy",
                "detail": "The portfolio is broadly aligned with the model's current view.",
            })

        score = max(0.0, min(100.0, score))
        if score >= 80:
            summary = "Healthy portfolio. Keep positions aligned with the model and review concentration monthly."
        elif score >= 60:
            summary = "Reasonable portfolio with a few issues worth fixing — see the findings below."
        else:
            summary = "The portfolio needs attention: concentration, losses, or model-disagreement flags are stacking up."

        return {
            "fetched_at": fetched_at,
            "mode": self._status.mode,
            "health_score": round(score),
            "summary": summary,
            "totals": {
                "value": round(total_value, 2),
                "cost": portfolio.total_cost,
                "gain": portfolio.total_gain,
                "gain_pct": portfolio.total_gain_pct,
                "cash": cash,
            },
            "holdings": sorted(audited, key=lambda i: i["value"], reverse=True),
            "findings": findings,
            "sector_exposure": sector_exposure,
        }


# ─── Singleton ────────────────────────────────────────────────────────────────

_agent_instance: Optional[AutonomousTradingAgent] = None


def get_trading_agent() -> AutonomousTradingAgent:
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = AutonomousTradingAgent()
    return _agent_instance
