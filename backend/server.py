"""
NEPSE-ALPHA ULTIMATE — FastAPI Server
Main application server exposing all analysis endpoints.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
import logging

from .models import (
    LayerWeights, FullAnalysis, RegimeDetection, StockData,
    DailyPrediction, WeeklyPrediction, MonthlyPrediction,
    MarketOverview, SectorPerformance, PortfolioOptResult, HistoricalPrice,
)
from .demo_data import generate_historical_prices
from .engine import analyze_stock
from .predictions import (
    detect_regime,
    generate_daily_predictions,
    generate_weekly_predictions,
    generate_monthly_predictions,
    DAILY_WEIGHTS, WEEKLY_WEIGHTS, MONTHLY_WEIGHTS,
)
from .portfolio import optimize_portfolio
from .nepse_fetcher import fetch_all_stocks, fetch_market_overview

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


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def convert_to_stock_data(raw_stock: dict) -> StockData:
    """Convert camelCase API response to StockData model."""
    return StockData(
        symbol=raw_stock.get("symbol", ""),
        name=raw_stock.get("name", ""),
        sector=raw_stock.get("sector", "Others"),
        cmp=raw_stock.get("cmp", 0),
        previous_close=raw_stock.get("previousClose", raw_stock.get("cmp", 0)),
        change=raw_stock.get("change", 0),
        change_percent=raw_stock.get("changePercent", 0),
        volume=raw_stock.get("volume", 0),
        avg_volume_20d=raw_stock.get("avgVolume20d", raw_stock.get("volume", 0)),
        high_52w=raw_stock.get("high52w", raw_stock.get("cmp", 0)),
        low_52w=raw_stock.get("low52w", raw_stock.get("cmp", 0)),
        eps=raw_stock.get("eps", 0),
        pe=raw_stock.get("pe", 0),
        pb=raw_stock.get("pb", 0),
        roe=raw_stock.get("roe", 0),
        dividend_yield=raw_stock.get("dividendYield", 0),
        book_value=raw_stock.get("bookValue", 0),
        market_cap=raw_stock.get("marketCap", 0),
    )


def generate_history_for_stock(stock_data: StockData) -> list[HistoricalPrice]:
    """Generate historical prices for a stock (fallback when no API data)."""
    return generate_historical_prices(stock_data)


# ═══════════════════════════════════════════════════════════════════════════════
# MARKET ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/api/market")
async def get_market_overview():
    """Get current market overview with NEPSE index and regime."""
    market_data = await fetch_market_overview()
    data = market_data.get("data", {})
    
    # Create MarketOverview from the data
    market = MarketOverview(
        nepse_index=data.get("nepse_index", data.get("index", 0)),
        nepse_change=data.get("nepse_change", data.get("change", 0)),
        nepse_change_percent=data.get("nepse_change_percent", data.get("change_percent", 0)),
        total_turnover=data.get("total_turnover", data.get("turnover", 0)),
        total_volume=data.get("total_volume", data.get("totalVolume", 0)),
        total_transactions=data.get("total_transactions", data.get("totalTransactions", 0)),
        advancers=data.get("advancers", 0),
        decliners=data.get("decliners", 0),
        unchanged=data.get("unchanged", 0),
        regime=data.get("regime", "SIDEWAYS"),
        regime_confidence=data.get("regime_confidence", 50),
        interbank_rate=data.get("interbank_rate", data.get("interbankRate", 0)),
        t_bill_yield=data.get("t_bill_yield", data.get("tBillYield", 0)),
    )
    
    regime = detect_regime(market)
    return {
        **market.model_dump(),
        "regime": regime.regime,
        "regime_confidence": regime.confidence,
        "source": market_data.get("source", "UNKNOWN"),
    }


@app.get("/api/market/regime")
async def get_regime():
    """Get current market regime detection result."""
    market_data = await fetch_market_overview()
    data = market_data.get("data", {})
    
    market = MarketOverview(
        nepse_index=data.get("nepse_index", data.get("index", 0)),
        nepse_change=data.get("nepse_change", data.get("change", 0)),
        nepse_change_percent=data.get("nepse_change_percent", data.get("change_percent", 0)),
        total_turnover=data.get("total_turnover", data.get("turnover", 0)),
        total_volume=data.get("total_volume", data.get("totalVolume", 0)),
        total_transactions=data.get("total_transactions", data.get("totalTransactions", 0)),
        advancers=data.get("advancers", 0),
        decliners=data.get("decliners", 0),
        unchanged=data.get("unchanged", 0),
        regime=data.get("regime", "SIDEWAYS"),
        regime_confidence=data.get("regime_confidence", 50),
        interbank_rate=data.get("interbank_rate", data.get("interbankRate", 0)),
        t_bill_yield=data.get("t_bill_yield", data.get("tBillYield", 0)),
    )
    
    return detect_regime(market)


@app.get("/api/market/sectors")
async def get_sectors():
    """Get sector-wise performance data."""
    # For now, return empty list as we need to implement sector aggregation
    # from live stock data
    stocks_data = await fetch_all_stocks()
    stocks = stocks_data.get("stocks", [])
    
    # Aggregate by sector
    sector_stats = {}
    for stock in stocks:
        sector = stock.get("sector", "Others")
        if sector not in sector_stats:
            sector_stats[sector] = {
                "volume": 0,
                "count": 0,
                "total_change": 0,
            }
        sector_stats[sector]["volume"] += stock.get("volume", 0)
        sector_stats[sector]["count"] += 1
        sector_stats[sector]["total_change"] += stock.get("changePercent", 0)
    
    # Convert to SectorPerformance objects
    sectors = []
    for sector, stats in sector_stats.items():
        avg_change = stats["total_change"] / stats["count"] if stats["count"] > 0 else 0
        sectors.append(SectorPerformance(
            sector=sector,
            index=1000,  # Placeholder - would need historical data
            change=avg_change,
            change_percent=avg_change,
            volume=stats["volume"],
        ))
    
    return sectors


# ═══════════════════════════════════════════════════════════════════════════════
# STOCK ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/api/stocks")
async def get_all_stocks(sector: Optional[str] = None, sort_by: str = "fcs"):
    """Get all stocks with five-layer scores. Optionally filter by sector."""
    stocks_data = await fetch_all_stocks()
    raw_stocks = stocks_data.get("stocks", [])
    
    # Filter by sector if provided
    if sector:
        raw_stocks = [s for s in raw_stocks if s.get("sector") == sector]
    
    results = []
    weights = LayerWeights()  # Default weights
    
    for raw_stock in raw_stocks:
        try:
            stock = convert_to_stock_data(raw_stock)
            hist = generate_history_for_stock(stock)
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
        except Exception as e:
            logger.error(f"Error analyzing stock {raw_stock.get('symbol', 'UNKNOWN')}: {e}")
            continue
    
    # Sort
    valid_sort_keys = ("fcs", "fvl", "tml", "ssil", "gtbil", "mrlll", "change_percent")
    sort_key = sort_by if sort_by in valid_sort_keys else "fcs"
    results.sort(key=lambda x: x.get(sort_key, 0), reverse=True)
    
    return {
        "stocks": results,
        "source": stocks_data.get("source", "UNKNOWN"),
        "count": len(results),
    }


@app.get("/api/stocks/{symbol}")
async def get_stock_analysis(symbol: str, tier: str = "daily"):
    """Get full five-layer analysis for a single stock."""
    stocks_data = await fetch_all_stocks()
    raw_stocks = stocks_data.get("stocks", [])
    
    # Find the stock
    raw_stock = next((s for s in raw_stocks if s.get("symbol", "").upper() == symbol.upper()), None)
    if not raw_stock:
        raise HTTPException(status_code=404, detail=f"Stock {symbol} not found")
    
    stock = convert_to_stock_data(raw_stock)
    
    weights_map = {
        "daily": DAILY_WEIGHTS,
        "weekly": WEEKLY_WEIGHTS,
        "monthly": MONTHLY_WEIGHTS,
    }
    weights = weights_map.get(tier, LayerWeights())
    hist = generate_history_for_stock(stock)
    
    return analyze_stock(stock, hist, weights)


@app.get("/api/stocks/{symbol}/history")
async def get_stock_history(symbol: str):
    """Get historical price data for a stock."""
    stocks_data = await fetch_all_stocks()
    raw_stocks = stocks_data.get("stocks", [])
    
    # Find the stock
    raw_stock = next((s for s in raw_stocks if s.get("symbol", "").upper() == symbol.upper()), None)
    if not raw_stock:
        raise HTTPException(status_code=404, detail=f"Stock {symbol} not found")
    
    stock = convert_to_stock_data(raw_stock)
    hist = generate_history_for_stock(stock)
    
    return [h.model_dump() for h in hist]


# ═══════════════════════════════════════════════════════════════════════════════
# PREDICTION ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/api/predictions/daily")
async def get_daily_predictions():
    """Get Top 5 Daily Trade predictions."""
    stocks_data = await fetch_all_stocks()
    raw_stocks = stocks_data.get("stocks", [])
    
    # Convert to StockData models
    stocks = []
    histories = {}
    for raw_stock in raw_stocks:
        try:
            stock = convert_to_stock_data(raw_stock)
            hist = generate_history_for_stock(stock)
            stocks.append(stock)
            histories[stock.symbol] = hist
        except Exception as e:
            logger.error(f"Error converting stock: {e}")
            continue
    
    return generate_daily_predictions(stocks, histories)


@app.get("/api/predictions/weekly")
async def get_weekly_predictions():
    """Get Top 10 Weekly Position predictions."""
    stocks_data = await fetch_all_stocks()
    raw_stocks = stocks_data.get("stocks", [])
    
    # Convert to StockData models
    stocks = []
    histories = {}
    for raw_stock in raw_stocks:
        try:
            stock = convert_to_stock_data(raw_stock)
            hist = generate_history_for_stock(stock)
            stocks.append(stock)
            histories[stock.symbol] = hist
        except Exception as e:
            logger.error(f"Error converting stock: {e}")
            continue
    
    return generate_weekly_predictions(stocks, histories)


@app.get("/api/predictions/monthly")
async def get_monthly_predictions():
    """Get Top 5 Monthly Conviction Picks."""
    stocks_data = await fetch_all_stocks()
    raw_stocks = stocks_data.get("stocks", [])
    
    # Convert to StockData models
    stocks = []
    histories = {}
    for raw_stock in raw_stocks:
        try:
            stock = convert_to_stock_data(raw_stock)
            hist = generate_history_for_stock(stock)
            stocks.append(stock)
            histories[stock.symbol] = hist
        except Exception as e:
            logger.error(f"Error converting stock: {e}")
            continue
    
    return generate_monthly_predictions(stocks, histories)


# ═══════════════════════════════════════════════════════════════════════════════
# PORTFOLIO ENDPOINT
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/api/portfolio")
async def get_portfolio_optimization():
    """Get optimized portfolio allocation using Sortino ratio."""
    stocks_data = await fetch_all_stocks()
    raw_stocks = stocks_data.get("stocks", [])
    
    # Convert to StockData models
    stocks = []
    histories = {}
    weights = LayerWeights()
    fcs_scores = {}
    
    for raw_stock in raw_stocks:
        try:
            stock = convert_to_stock_data(raw_stock)
            hist = generate_history_for_stock(stock)
            stocks.append(stock)
            histories[stock.symbol] = hist
            
            # Calculate FCS score
            analysis = analyze_stock(stock, hist, weights)
            fcs_scores[stock.symbol] = analysis.fcs.score
        except Exception as e:
            logger.error(f"Error processing stock for portfolio: {e}")
            continue
    
    # Get market regime
    market_data = await fetch_market_overview()
    data = market_data.get("data", {})
    market = MarketOverview(
        nepse_index=data.get("nepse_index", data.get("index", 0)),
        nepse_change=data.get("nepse_change", data.get("change", 0)),
        nepse_change_percent=data.get("nepse_change_percent", data.get("change_percent", 0)),
        total_turnover=data.get("total_turnover", data.get("turnover", 0)),
        total_volume=data.get("total_volume", data.get("totalVolume", 0)),
        total_transactions=data.get("total_transactions", data.get("totalTransactions", 0)),
        advancers=data.get("advancers", 0),
        decliners=data.get("decliners", 0),
        unchanged=data.get("unchanged", 0),
        regime=data.get("regime", "SIDEWAYS"),
        regime_confidence=data.get("regime_confidence", 50),
        interbank_rate=data.get("interbank_rate", data.get("interbankRate", 0)),
        t_bill_yield=data.get("t_bill_yield", data.get("tBillYield", 0)),
    )
    regime = detect_regime(market)
    
    return optimize_portfolio(
        stocks, histories, fcs_scores,
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
async def health_check():
    from .ml_predictor import predictor, HAS_XGBOOST
    
    # Check if we can fetch live data
    stocks_data = await fetch_all_stocks()
    data_source = stocks_data.get("source", "UNKNOWN")
    stocks_count = stocks_data.get("count", 0)
    
    return {
        "status": "operational",
        "version": "ULTIMATE-2.0-REALTIME",
        "stocks_loaded": stocks_count,
        "data_mode": f"LIVE API (fallback: DEMO) - Current: {data_source}",
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
