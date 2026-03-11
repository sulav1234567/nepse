"""
NEPSE-ALPHA ULTIMATE — FastAPI Server
Main application server exposing all analysis endpoints.
"""

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
import logging

from .models import (
    LayerWeights, FullAnalysis, RegimeDetection,
    DailyPrediction, WeeklyPrediction, MonthlyPrediction,
    MarketOverview, SectorPerformance, PortfolioOptResult,
)
from .demo_data import (
    DEMO_STOCKS, DEMO_MARKET, DEMO_SECTORS,
    generate_historical_prices,
)
from .engine import analyze_stock
from .predictions import (
    detect_regime,
    generate_daily_predictions,
    generate_weekly_predictions,
    generate_monthly_predictions,
    DAILY_WEIGHTS, WEEKLY_WEIGHTS, MONTHLY_WEIGHTS,
)
from .portfolio import optimize_portfolio

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("nepse-alpha")

app = FastAPI(
    title="NEPSE-ALPHA ULTIMATE",
    description="Five-Layer Stock Prediction Intelligence for Nepal Stock Exchange",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Precompute demo histories ──────────────────────────────────────────────
_histories = {}
for s in DEMO_STOCKS:
    _histories[s.symbol] = generate_historical_prices(s)


# ═══════════════════════════════════════════════════════════════════════════════
# MARKET ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/api/market", response_model=MarketOverview)
def get_market_overview():
    """Get current market overview with NEPSE index and regime."""
    regime = detect_regime(DEMO_MARKET)
    return MarketOverview(
        **{**DEMO_MARKET.model_dump(), "regime": regime.regime, "regime_confidence": regime.confidence}
    )


@app.get("/api/market/regime", response_model=RegimeDetection)
def get_regime():
    """Get current market regime detection result."""
    return detect_regime(DEMO_MARKET)


@app.get("/api/market/sectors", response_model=list[SectorPerformance])
def get_sectors():
    """Get sector-wise performance data."""
    return DEMO_SECTORS


# ═══════════════════════════════════════════════════════════════════════════════
# STOCK ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/api/stocks")
def get_all_stocks(sector: Optional[str] = None, sort_by: str = "fcs"):
    """Get all stocks with five-layer scores. Optionally filter by sector."""
    stocks = DEMO_STOCKS
    if sector:
        stocks = [s for s in stocks if s.sector == sector]

    results = []
    weights = LayerWeights()  # Default weights
    
    for stock in stocks:
        hist = _histories.get(stock.symbol, [])
        analysis = analyze_stock(stock, hist, weights)
        results.append({
            "symbol": stock.symbol,
            "name": stock.name,
            "sector": stock.sector,
            "cmp": stock.cmp,
            "change": stock.change,
            "change_percent": stock.change_percent,
            "volume": stock.volume,
            "pe": stock.pe,
            "pb": stock.pb,
            "roe": stock.roe,
            "dividend_yield": stock.dividend_yield,
            "fvl": analysis.fcs.layer_scores.fvl,
            "tml": analysis.fcs.layer_scores.tml,
            "ssil": analysis.fcs.layer_scores.ssil,
            "gtbil": analysis.fcs.layer_scores.gtbil,
            "mrlll": analysis.fcs.layer_scores.mrlll,
            "fcs": analysis.fcs.score,
            "signal": analysis.fcs.signal,
        })

    # Sort
    sort_key = sort_by if sort_by in ("fcs", "fvl", "tml", "ssil", "gtbil", "mrlll", "change_percent") else "fcs"
    results.sort(key=lambda x: x.get(sort_key, 0), reverse=True)

    return results


@app.get("/api/stocks/{symbol}", response_model=FullAnalysis)
def get_stock_analysis(symbol: str, tier: str = "daily"):
    """Get full five-layer analysis for a single stock."""
    stock = next((s for s in DEMO_STOCKS if s.symbol == symbol.upper()), None)
    if not stock:
        return {"error": f"Stock {symbol} not found"}

    weights_map = {
        "daily": DAILY_WEIGHTS,
        "weekly": WEEKLY_WEIGHTS,
        "monthly": MONTHLY_WEIGHTS,
    }
    weights = weights_map.get(tier, LayerWeights())
    hist = _histories.get(stock.symbol, [])
    return analyze_stock(stock, hist, weights)


@app.get("/api/stocks/{symbol}/history")
def get_stock_history(symbol: str):
    """Get historical price data for a stock."""
    stock = next((s for s in DEMO_STOCKS if s.symbol == symbol.upper()), None)
    if not stock:
        return {"error": f"Stock {symbol} not found"}
    return [h.model_dump() for h in _histories.get(stock.symbol, [])]


# ═══════════════════════════════════════════════════════════════════════════════
# PREDICTION ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/api/predictions/daily", response_model=list[DailyPrediction])
def get_daily_predictions():
    """Get Top 5 Daily Trade predictions."""
    return generate_daily_predictions(DEMO_STOCKS, _histories)


@app.get("/api/predictions/weekly", response_model=list[WeeklyPrediction])
def get_weekly_predictions():
    """Get Top 10 Weekly Position predictions."""
    return generate_weekly_predictions(DEMO_STOCKS, _histories)


@app.get("/api/predictions/monthly", response_model=list[MonthlyPrediction])
def get_monthly_predictions():
    """Get Top 5 Monthly Conviction Picks."""
    return generate_monthly_predictions(DEMO_STOCKS, _histories)


# ═══════════════════════════════════════════════════════════════════════════════
# PORTFOLIO ENDPOINT
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/api/portfolio", response_model=PortfolioOptResult)
def get_portfolio_optimization():
    """Get optimized portfolio allocation using Sortino ratio."""
    weights = LayerWeights()
    fcs_scores = {}
    for stock in DEMO_STOCKS:
        hist = _histories.get(stock.symbol, [])
        analysis = analyze_stock(stock, hist, weights)
        fcs_scores[stock.symbol] = analysis.fcs.score

    regime = detect_regime(DEMO_MARKET)
    return optimize_portfolio(
        DEMO_STOCKS, _histories, fcs_scores,
        regime_multiplier=regime.position_multiplier,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# LIVE DATA ENDPOINTS (Real-time NEPSE)
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/api/live/stocks")
async def get_live_stocks():
    """Get real-time stock data for ALL NEPSE stocks. Falls back to demo."""
    from .nepse_fetcher import fetch_all_stocks
    return await fetch_all_stocks()


@app.get("/api/live/market")
async def get_live_market():
    """Get live market overview. Falls back to demo."""
    from .nepse_fetcher import fetch_market_overview
    return await fetch_market_overview()


# ═══════════════════════════════════════════════════════════════════════════════
# AI/ML PREDICTION ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/api/ai/predictions")
async def get_ai_predictions(top: int = 20):
    """
    Get ML-powered stock rise predictions.
    Uses ensemble of RandomForest + GradientBoosting + XGBoost.
    Returns ranked predictions with probability, target, and AI reasoning.
    """
    from .nepse_fetcher import fetch_all_stocks
    from .ml_predictor import predictor

    # Get latest stock data
    data = await fetch_all_stocks()
    stocks = data.get("stocks", [])

    # Train and predict
    if not predictor.is_trained:
        predictor.train(stocks)
    predictions = predictor.predict(stocks)

    return {
        "predictions": predictions[:top],
        "totalStocks": len(stocks),
        "dataSource": data.get("source", "DEMO"),
        "timestamp": data.get("timestamp"),
        "modelMetrics": predictor.get_model_metrics(),
    }


@app.get("/api/ai/prediction/{symbol}")
async def get_ai_prediction_detail(symbol: str):
    """Get detailed ML prediction for a specific stock."""
    from .nepse_fetcher import fetch_all_stocks
    from .ml_predictor import predictor

    data = await fetch_all_stocks()
    stocks = data.get("stocks", [])

    if not predictor.is_trained:
        predictor.train(stocks)
    predictions = predictor.predict(stocks)

    result = next((p for p in predictions if p["symbol"].upper() == symbol.upper()), None)
    if not result:
        return {"error": f"Stock {symbol} not found"}
    return result


@app.get("/api/ai/feature-importance")
async def get_feature_importance():
    """Get current ML feature importance rankings."""
    from .nepse_fetcher import fetch_all_stocks
    from .ml_predictor import predictor

    if not predictor.is_trained:
        data = await fetch_all_stocks()
        predictor.train(data.get("stocks", []))

    return {
        "features": predictor.get_feature_importance(),
        "totalFeatures": 30,
    }


@app.get("/api/ai/model-metrics")
async def get_model_metrics():
    """Get ML model training and performance metrics."""
    from .nepse_fetcher import fetch_all_stocks
    from .ml_predictor import predictor

    if not predictor.is_trained:
        data = await fetch_all_stocks()
        predictor.train(data.get("stocks", []))

    return predictor.get_model_metrics()


# ═══════════════════════════════════════════════════════════════════════════════
# HEALTH CHECK
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/api/health")
def health_check():
    from .ml_predictor import predictor, HAS_XGBOOST
    return {
        "status": "operational",
        "version": "ULTIMATE-1.0",
        "stocks_loaded": len(DEMO_STOCKS),
        "data_mode": "HYBRID (LIVE + DEMO fallback)",
        "ml_trained": predictor.is_trained,
        "libraries": {
            "numpy": True,
            "pandas": True,
            "scipy": True,
            "scikit-learn": True,
            "filterpy": True,
            "statsmodels": True,
            "xgboost": HAS_XGBOOST,
        }
    }
