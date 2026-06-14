"""
FastAPI routes for the autonomous NEPSE research platform + trading agent.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel

from .schemas import AutonomousDashboardResponse, SignalCard
from .service import AutonomousResearchPlatform, get_research_platform
from .trading_agent import AutonomousTradingAgent, get_trading_agent

logger = logging.getLogger("nepse.autonomous.api")

router = APIRouter(prefix="/api/autonomous", tags=["autonomous"])


# ─── Trading agent request/response models ───────────────────────────────────

class BrokerConnectRequest(BaseModel):
    mero_share_client_id: Optional[str] = None
    mero_share_password: Optional[str] = None
    tms_url: Optional[str] = None
    tms_username: Optional[str] = None
    tms_password: Optional[str] = None
    tms_pin: Optional[str] = None
    paper_mode: bool = True


class ForceExitRequest(BaseModel):
    symbol: str
    reason: str = "Manual exit via API"


class ManualTradeRequest(BaseModel):
    symbol: str
    action: str   # "BUY" | "SELL"
    quantity: int
    price: float
    notes: str = ""


@router.get("/dashboard", response_model=AutonomousDashboardResponse)
def autonomous_dashboard(platform: AutonomousResearchPlatform = Depends(get_research_platform)) -> AutonomousDashboardResponse:
    return platform.dashboard(limit=10)


@router.get("/signals", response_model=list[SignalCard])
def autonomous_signals(limit: int = 25, platform: AutonomousResearchPlatform = Depends(get_research_platform)) -> list[SignalCard]:
    return platform.signal_cards(limit=limit)


@router.post("/signals/refresh")
def autonomous_refresh_signals(limit: int = 25, platform: AutonomousResearchPlatform = Depends(get_research_platform)) -> dict:
    """Start a full rescore (all stocks, latest model) in the background and return
    immediately. Poll GET /signals/refresh/status for completion."""
    return platform.start_background_rescore(limit=limit)


@router.get("/signals/refresh/status")
def autonomous_refresh_status(platform: AutonomousResearchPlatform = Depends(get_research_platform)) -> dict:
    return platform.rescore_status()


@router.get("/signals/{symbol}", response_model=SignalCard)
def autonomous_signal_detail(symbol: str, platform: AutonomousResearchPlatform = Depends(get_research_platform)) -> SignalCard:
    cards = platform.signal_cards(limit=500)
    for card in cards:
        if card.symbol.upper() == symbol.upper():
            return card
    raise HTTPException(status_code=404, detail=f"No autonomous signal available for {symbol}")


@router.get("/system/status")
def autonomous_system_status(platform: AutonomousResearchPlatform = Depends(get_research_platform)) -> dict:
    return platform.system_status().model_dump()


@router.get("/backtests/latest")
def autonomous_latest_backtest(platform: AutonomousResearchPlatform = Depends(get_research_platform)) -> dict:
    backtest = platform.latest_backtest()
    return {} if backtest is None else backtest.model_dump()


@router.post("/ingestion/run")
def autonomous_run_ingestion(platform: AutonomousResearchPlatform = Depends(get_research_platform)) -> dict:
    return platform.run_ingestion_cycle()


@router.post("/datasets/build")
def autonomous_build_training_dataset(
    profile: str = "advanced",
    symbol_limit: int | None = None,
    refresh: bool = False,
    market_news_pages: int = 5,
    market_article_body_limit: int = 30,
    platform: AutonomousResearchPlatform = Depends(get_research_platform),
) -> dict:
    return platform.build_internet_training_data(
        profile=profile,
        symbol_limit=symbol_limit,
        refresh=refresh,
        market_news_pages=market_news_pages,
        market_article_body_limit=market_article_body_limit,
    )


@router.post("/training/run")
def autonomous_run_training(force: bool = False, platform: AutonomousResearchPlatform = Depends(get_research_platform)) -> dict:
    return platform.train_models(force=force)


@router.post("/outcomes/evaluate")
def autonomous_evaluate_outcomes(platform: AutonomousResearchPlatform = Depends(get_research_platform)) -> dict:
    return platform.evaluate_prediction_outcomes()


# ─── Trading Agent endpoints ──────────────────────────────────────────────────

@router.get("/trader/status")
def trader_status(agent: AutonomousTradingAgent = Depends(get_trading_agent)) -> dict[str, Any]:
    """Get current agent status, open positions, P&L."""
    return agent.get_status()


@router.get("/trader/recommendations")
def trader_recommendations(
    top_n: int = 20,
    agent: AutonomousTradingAgent = Depends(get_trading_agent),
) -> list[dict[str, Any]]:
    """
    Return ML+FCS ranked buy recommendations without placing any orders.
    Safe to call at any time — read-only, no broker interaction.
    """
    try:
        return agent.get_recommendations(top_n=top_n)
    except Exception as exc:
        logger.error("Recommendations error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/trader/run")
def trader_run_cycle(
    background_tasks: BackgroundTasks,
    agent: AutonomousTradingAgent = Depends(get_trading_agent),
) -> dict[str, Any]:
    """
    Trigger one full agent cycle (scan + monitor + trade) in the background.
    Returns immediately with run_id; use /trader/status to poll progress.
    """
    if agent._status.is_running:
        raise HTTPException(status_code=409, detail="Agent is already running a cycle.")

    def _run() -> None:
        try:
            agent.run_once()
        except Exception as exc:
            logger.error("Agent run error: %s", exc)

    background_tasks.add_task(_run)
    return {"message": "Agent cycle started in background.", "mode": agent._status.mode}


@router.post("/trader/connect")
def trader_connect_broker(
    req: BrokerConnectRequest,
    agent: AutonomousTradingAgent = Depends(get_trading_agent),
) -> dict[str, Any]:
    """
    Configure and connect the broker account.
    Pass credentials here or pre-set them as environment variables:
      MERO_SHARE_CLIENT_ID, MERO_SHARE_PASSWORD
      TMS_URL, TMS_USERNAME, TMS_PASSWORD, TMS_PIN
    """
    import os
    broker = agent.broker
    broker.paper_mode = req.paper_mode

    if req.mero_share_client_id:
        broker.mero_share.client_id = req.mero_share_client_id
    if req.mero_share_password:
        broker.mero_share.password = req.mero_share_password
    if req.tms_url:
        broker.tms.tms_url = req.tms_url.rstrip("/")
    if req.tms_username:
        broker.tms.username = req.tms_username
    if req.tms_password:
        broker.tms.password = req.tms_password
    if req.tms_pin:
        broker.tms.pin = req.tms_pin

    ok = broker.connect()
    if not ok and not req.paper_mode:
        raise HTTPException(status_code=503, detail="Broker connection failed. Check credentials.")

    mode = "paper" if req.paper_mode else "live"
    return {
        "connected": ok or req.paper_mode,
        "mode": mode,
        "message": f"Broker connected in {mode} mode.",
    }


@router.get("/trader/portfolio")
def trader_portfolio(agent: AutonomousTradingAgent = Depends(get_trading_agent)) -> dict[str, Any]:
    """Get current portfolio holdings from Mero Share."""
    portfolio = agent.broker.get_portfolio()
    cash = agent.broker.get_cash_balance()
    return {
        "holdings": [
            {
                "symbol": h.symbol,
                "company_name": h.company_name,
                "units": h.units,
                "ltp": h.ltp,
                "wacc": h.wacc,
                "unrealized_gain": h.unrealized_gain,
                "unrealized_gain_pct": h.unrealized_gain_pct,
            }
            for h in portfolio.holdings
        ],
        "total_value": portfolio.total_value,
        "total_cost": portfolio.total_cost,
        "total_gain": portfolio.total_gain,
        "total_gain_pct": portfolio.total_gain_pct,
        "cash_balance": cash,
        "fetched_at": portfolio.fetched_at,
    }


@router.get("/trader/positions")
def trader_open_positions(agent: AutonomousTradingAgent = Depends(get_trading_agent)) -> list[dict[str, Any]]:
    """Get positions currently managed by the trading agent."""
    from dataclasses import asdict
    return [asdict(p) for p in agent.get_open_positions()]


@router.post("/trader/exit")
def trader_force_exit(
    req: ForceExitRequest,
    agent: AutonomousTradingAgent = Depends(get_trading_agent),
) -> dict[str, Any]:
    """Force-close a specific position immediately."""
    ok = agent.force_exit_position(req.symbol, req.reason)
    if not ok:
        raise HTTPException(status_code=404, detail=f"No open position found for {req.symbol}.")
    return {"message": f"Position {req.symbol} closed.", "success": True}


@router.post("/trader/manual-trade")
def trader_manual_trade(
    req: ManualTradeRequest,
    agent: AutonomousTradingAgent = Depends(get_trading_agent),
) -> dict[str, Any]:
    """Place a manual buy or sell order through the agent's broker."""
    from dataclasses import asdict
    action = req.action.upper()
    if action == "BUY":
        record = agent.broker.buy(req.symbol, req.quantity, req.price, notes=req.notes)
    elif action == "SELL":
        record = agent.broker.sell(req.symbol, req.quantity, req.price, notes=req.notes)
    else:
        raise HTTPException(status_code=400, detail="action must be BUY or SELL")
    return asdict(record)


@router.get("/trader/trades")
def trader_trade_history(agent: AutonomousTradingAgent = Depends(get_trading_agent)) -> list[dict[str, Any]]:
    """Get all trades (paper or live) placed by the agent."""
    from dataclasses import asdict
    return [asdict(t) for t in agent.broker.get_trade_history()]


@router.get("/trader/audit")
def trader_portfolio_audit(agent: AutonomousTradingAgent = Depends(get_trading_agent)) -> dict[str, Any]:
    """Fetch the Mero Share portfolio and audit it with the AI signal engine."""
    try:
        return agent.audit_portfolio()
    except Exception as exc:
        logger.error("Portfolio audit error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))
