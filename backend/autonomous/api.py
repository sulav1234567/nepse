"""
FastAPI routes for the autonomous NEPSE research platform.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from .schemas import AutonomousDashboardResponse, SignalCard
from .service import AutonomousResearchPlatform, get_research_platform

router = APIRouter(prefix="/api/autonomous", tags=["autonomous"])


@router.get("/dashboard", response_model=AutonomousDashboardResponse)
def autonomous_dashboard(platform: AutonomousResearchPlatform = Depends(get_research_platform)) -> AutonomousDashboardResponse:
    return platform.dashboard(limit=10)


@router.get("/signals", response_model=list[SignalCard])
def autonomous_signals(limit: int = 25, platform: AutonomousResearchPlatform = Depends(get_research_platform)) -> list[SignalCard]:
    return platform.generate_signal_cards(limit=limit)


@router.get("/signals/{symbol}", response_model=SignalCard)
def autonomous_signal_detail(symbol: str, platform: AutonomousResearchPlatform = Depends(get_research_platform)) -> SignalCard:
    cards = platform.generate_signal_cards(limit=200)
    for card in cards:
        if card.symbol.upper() == symbol.upper():
            return card
    raise HTTPException(status_code=404, detail=f"No autonomous signal available for {symbol}")


@router.get("/system/status")
def autonomous_system_status(platform: AutonomousResearchPlatform = Depends(get_research_platform)) -> dict:
    dashboard = platform.dashboard(limit=5)
    return dashboard.status.model_dump()


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
