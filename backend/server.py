"""
NEPSE-ALPHA ULTIMATE — FastAPI Server
Main application server exposing all analysis endpoints.
"""

from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, Any
import logging

from .models import (
    LayerWeights, FullAnalysis, RegimeDetection, StockData,
    DailyPrediction, WeeklyPrediction, MonthlyPrediction,
    MarketOverview, SectorPerformance, PortfolioOptResult, HistoricalPrice,
    UserRegister, UserLogin, TokenResponse, UserResponse,
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
from .nepse_fetcher import fetch_all_stocks, fetch_market_overview, fetch_nepse_index_history, fetch_current_nepse_index
from .deterministic import stable_rng
from .market_intelligence import build_market_intelligence
from .index_analysis import analyze_nepse_index
from .database import connect_to_mongodb, close_mongodb, UserManager
from .auth import AuthService, get_current_user
from .autonomous.api import router as autonomous_router
from .autonomous.service import get_research_platform

import numpy as np
from datetime import datetime, timedelta

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
app.include_router(autonomous_router)


# ═══════════════════════════════════════════════════════════════════════════════
# STARTUP AND SHUTDOWN EVENTS
# ═══════════════════════════════════════════════════════════════════════════════

@app.on_event("startup")
async def startup_event():
    """Initialize database on startup"""
    try:
        connect_to_mongodb()
        logger.info("✓ Application started - MongoDB initialized")
    except Exception as e:
        logger.warning(f"MongoDB unavailable; auth endpoints will be limited: {e}")
    try:
        get_research_platform()
        logger.info("✓ Autonomous research platform initialized")
    except Exception as e:
        logger.error(f"✗ Autonomous platform startup error: {e}")
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Close database connection on shutdown"""
    close_mongodb()
    logger.info("✓ Application shutdown - MongoDB closed")


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def convert_to_stock_data(raw_stock: dict[str, Any]) -> StockData:
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
        open=raw_stock.get("open", raw_stock.get("cmp", 0)),
        high=raw_stock.get("high", raw_stock.get("cmp", 0)),
        low=raw_stock.get("low", raw_stock.get("cmp", 0)),
        total_trades=raw_stock.get("totalTrades", 0),
        turnover=raw_stock.get("turnover", 0),
    )


def generate_history_for_stock(stock_data: StockData) -> list[HistoricalPrice]:
    """Generate synthetic historical prices for technical analysis when real data is unavailable."""
    _volatility_map = {
        "Hydropower": 0.035, "Commercial Bank": 0.018,
        "Development Bank": 0.022, "Insurance": 0.022,
        "Microfinance": 0.028, "Manufacturing": 0.015,
        "Hotel & Tourism": 0.030,
    }
    rng = stable_rng(
        "history",
        stock_data.symbol,
        stock_data.cmp,
        stock_data.previous_close,
        stock_data.volume,
        stock_data.high_52w,
        stock_data.low_52w,
    )
    data: list[HistoricalPrice] = []
    base_price = stock_data.cmp * 0.85
    volatility = _volatility_map.get(stock_data.sector, 0.025)
    days = 60
    now = datetime.now()

    for i in range(days, 0, -1):
        date = now - timedelta(days=i)
        if date.weekday() == 5:
            continue
        trend = (days - i) / days * 0.15
        noise = (rng.random() - 0.48) * volatility * 2
        day_return = trend / days + noise
        base_price *= (1 + day_return)
        high = base_price * (1 + rng.random() * volatility)
        low = base_price * (1 - rng.random() * volatility)
        open_p = low + rng.random() * (high - low)
        close_p = low + rng.random() * (high - low)
        volume = int(stock_data.avg_volume_20d * (0.6 + rng.random() * 0.9))
        data.append(HistoricalPrice(
            date=date.strftime("%Y-%m-%d"),
            open=round(open_p, 2),
            high=round(high, 2),
            low=round(low, 2),
            close=round(close_p, 2),
            volume=volume,
        ))

    if data:
        latest = data[-1]
        latest.open = round(stock_data.open if stock_data.open > 0 else latest.open, 2)
        latest.high = round(max(stock_data.high or latest.high, stock_data.cmp, latest.high), 2)
        latest.low = round(min(stock_data.low or latest.low, stock_data.cmp, latest.low), 2)
        latest.close = round(stock_data.cmp, 2)
        latest.volume = int(stock_data.volume or latest.volume)
    return data


async def create_market_overview_from_data(data: dict[str, Any]) -> MarketOverview:
    """Create MarketOverview model from API response data."""
    return MarketOverview(
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


async def prepare_stocks_for_analysis(raw_stocks: list[dict]) -> tuple[list[StockData], dict[str, list[HistoricalPrice]]]:
    """Convert raw stocks to StockData models and generate histories."""
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
    
    return stocks, histories


# ═══════════════════════════════════════════════════════════════════════════════
# AUTHENTICATION ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/api/auth/register", response_model=TokenResponse)
async def register(user_data: UserRegister):
    """
    Register a new user
    
    Args:
        user_data: User registration data (email, username, password, full_name)
    
    Returns:
        Token response with access token and user info
    """
    try:
        # Hash password
        hashed_password = AuthService.hash_password(user_data.password)
        
        # Create user in database
        user = UserManager.create_user(
            email=user_data.email,
            username=user_data.username,
            hashed_password=hashed_password,
            full_name=user_data.full_name
        )
        
        # Generate access token
        access_token = AuthService.create_access_token(user_data.email)
        
        # Prepare response
        user_response = UserResponse(
            id=user.get("_id"),
            email=user["email"],
            username=user["username"],
            full_name=user.get("full_name"),
            created_at=user.get("created_at"),
            is_active=user.get("is_active", True)
        )
        
        logger.info(f"✓ New user registered: {user_data.email}")
        
        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            user=user_response
        )
    
    except ValueError as e:
        logger.warning(f"Registration error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Registration error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed"
        )


@app.post("/api/auth/login", response_model=TokenResponse)
async def login(login_data: UserLogin):
    """
    Login user with email and password
    
    Args:
        login_data: Login credentials (email, password)
    
    Returns:
        Token response with access token and user info
    """
    try:
        # Authenticate user
        user = AuthService.authenticate_user(login_data.email, login_data.password)
        
        if not user:
            logger.warning(f"Failed login attempt: {login_data.email}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )
        
        # Generate access token
        access_token = AuthService.create_access_token(login_data.email)
        
        # Prepare response (remove password from response)
        user_response = UserResponse(
            id=user.get("_id"),
            email=user["email"],
            username=user["username"],
            full_name=user.get("full_name"),
            created_at=user.get("created_at"),
            is_active=user.get("is_active", True)
        )
        
        logger.info(f"✓ User logged in: {login_data.email}")
        
        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            user=user_response
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed"
        )


@app.get("/api/auth/me", response_model=UserResponse)
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    """
    Get current authenticated user info
    
    Args:
        current_user: Current authenticated user (from dependency)
    
    Returns:
        User information
    """
    return UserResponse(
        id=current_user.get("_id"),
        email=current_user["email"],
        username=current_user["username"],
        full_name=current_user.get("full_name"),
        created_at=current_user.get("created_at"),
        is_active=current_user.get("is_active", True)
    )


@app.post("/api/auth/logout")
async def logout(current_user: dict = Depends(get_current_user)):
    """
    Logout user (just return success message)
    Client should delete the token from localStorage
    
    Args:
        current_user: Current authenticated user (validates token)
    
    Returns:
        Logout confirmation message
    """
    logger.info(f"✓ User logged out: {current_user['email']}")
    return {"message": "Logged out successfully"}


# ═══════════════════════════════════════════════════════════════════════════════
# MARKET ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/api/market")
async def get_market_overview():
    """Get current market overview with NEPSE index and regime."""
    market_data = await fetch_market_overview()
    data = market_data.get("data", {})
    stocks_data = await fetch_all_stocks()

    market = await create_market_overview_from_data(data)
    regime = detect_regime(market)
    intelligence = build_market_intelligence(market, stocks_data.get("stocks", []))
    
    return {
        **market.model_dump(),
        "regime": regime.regime,
        "regime_confidence": regime.confidence,
        "source": market_data.get("source", "UNKNOWN"),
        "timestamp": market_data.get("timestamp"),
        "intelligence": intelligence,
    }


@app.get("/api/market/nepse-index")
async def get_current_nepse_index():
    """Get the CURRENT real-time NEPSE index value (minimal cache)."""
    return await fetch_current_nepse_index()

@app.get("/api/market/regime")
async def get_regime():
    """Get current market regime detection result."""
    market_data = await fetch_market_overview()
    data = market_data.get("data", {})
    
    market = await create_market_overview_from_data(data)
    return detect_regime(market)


@app.get("/api/market/intelligence")
async def get_market_intelligence():
    """Get live market state, crash-risk warnings, and sector leadership."""
    market_data = await fetch_market_overview()
    stocks_data = await fetch_all_stocks()
    data = market_data.get("data", {})

    market = await create_market_overview_from_data(data)
    regime = detect_regime(market)
    intelligence = build_market_intelligence(market, stocks_data.get("stocks", []))

    return {
        "market": {
            **market.model_dump(),
            "regime": regime.regime,
            "regime_confidence": regime.confidence,
        },
        "intelligence": intelligence,
        "source": market_data.get("source", stocks_data.get("source", "UNKNOWN")),
        "timestamp": market_data.get("timestamp") or stocks_data.get("timestamp"),
    }


@app.get("/api/market/index-history")
async def get_nepse_index_history(days: int = 90):
    """Get live main NEPSE index OHLC history."""
    return await fetch_nepse_index_history(days=days)


@app.get("/api/market/index-analysis")
async def get_nepse_index_analysis(days: int = 90):
    """Get live candlestick analysis for the main NEPSE index."""
    market_data = await fetch_market_overview()
    stocks_data = await fetch_all_stocks()
    history_data = await fetch_nepse_index_history(days=days)
    market = await create_market_overview_from_data(market_data.get("data", {}))
    intelligence = build_market_intelligence(market, stocks_data.get("stocks", []))
    analysis = analyze_nepse_index(history_data.get("history", []), intelligence)

    return {
        "market": {
            **market.model_dump(),
            "source": market_data.get("source", "UNKNOWN"),
        },
        "history": history_data.get("history", []),
        "analysis": analysis,
        "intelligence": intelligence,
        "source": history_data.get("source", market_data.get("source", "UNKNOWN")),
        "timestamp": history_data.get("timestamp") or market_data.get("timestamp"),
    }


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
            # Using 1000 as base index value - actual sector indices would require 
            # historical data tracking. This is a normalized baseline for comparison.
            index=1000,
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
    
    stocks, histories = await prepare_stocks_for_analysis(raw_stocks)
    return generate_daily_predictions(stocks, histories)


@app.get("/api/predictions/weekly")
async def get_weekly_predictions():
    """Get Top 10 Weekly Position predictions."""
    stocks_data = await fetch_all_stocks()
    raw_stocks = stocks_data.get("stocks", [])
    
    stocks, histories = await prepare_stocks_for_analysis(raw_stocks)
    return generate_weekly_predictions(stocks, histories)


@app.get("/api/predictions/monthly")
async def get_monthly_predictions():
    """Get Top 5 Monthly Conviction Picks."""
    stocks_data = await fetch_all_stocks()
    raw_stocks = stocks_data.get("stocks", [])
    
    stocks, histories = await prepare_stocks_for_analysis(raw_stocks)
    return generate_monthly_predictions(stocks, histories)


# ═══════════════════════════════════════════════════════════════════════════════
# PORTFOLIO ENDPOINT
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/api/portfolio")
async def get_portfolio_optimization():
    """Get optimized portfolio allocation using Sortino ratio."""
    stocks_data = await fetch_all_stocks()
    raw_stocks = stocks_data.get("stocks", [])
    
    # Prepare stocks and histories
    stocks, histories = await prepare_stocks_for_analysis(raw_stocks)
    
    # Calculate FCS scores
    weights = LayerWeights()
    fcs_scores = {}
    for stock in stocks:
        try:
            hist = histories.get(stock.symbol, [])
            analysis = analyze_stock(stock, hist, weights)
            fcs_scores[stock.symbol] = analysis.fcs.score
        except Exception as e:
            logger.error(f"Error calculating FCS for {stock.symbol}: {e}")
            continue
    
    # Get market regime
    market_data = await fetch_market_overview()
    data = market_data.get("data", {})
    market = await create_market_overview_from_data(data)
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
    """Get real-time stock data for ALL NEPSE stocks."""
    from .nepse_fetcher import fetch_all_stocks
    return await fetch_all_stocks()


@app.get("/api/live/market")
async def get_live_market():
    """Get live market overview."""
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
    market_data = await fetch_market_overview()
    market = await create_market_overview_from_data(market_data.get("data", {}))
    regime = detect_regime(market)
    market_intelligence = build_market_intelligence(market, stocks)

    predictor.ensure_trained(stocks)
    predictions = predictor.predict(
        stocks,
        market_context_override={
            "breadth_ratio": market_intelligence.get("breadth_ratio", 50) / 100,
            "avg_change": market_intelligence.get("average_change", 0),
            "interbank_rate": market.interbank_rate,
            "sector_momentum": market.nepse_change_percent,
            "market_change_percent": market.nepse_change_percent,
            "up_volume_share": market_intelligence.get("up_volume_share", 50) / 100,
        },
        market_regime=regime.regime,
        crash_risk=market_intelligence.get("crash_risk", 0),
    )

    return {
        "predictions": predictions[:top],
        "totalStocks": len(stocks),
        "dataSource": data.get("source", "DEMO"),
        "timestamp": data.get("timestamp"),
        "modelMetrics": predictor.get_model_metrics(),
        "featureImportance": predictor.get_feature_importance(),
        "marketIntelligence": market_intelligence,
        "marketRegime": regime.regime,
    }


@app.get("/api/ai/prediction/{symbol}")
async def get_ai_prediction_detail(symbol: str):
    """Get detailed ML prediction for a specific stock."""
    from .nepse_fetcher import fetch_all_stocks
    from .ml_predictor import predictor

    data = await fetch_all_stocks()
    stocks = data.get("stocks", [])

    predictor.ensure_trained(stocks)
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

    data = await fetch_all_stocks()
    predictor.ensure_trained(data.get("stocks", []))

    return {
        "features": predictor.get_feature_importance(),
        "totalFeatures": 30,
    }


@app.get("/api/ai/model-metrics")
async def get_model_metrics():
    """Get ML model training and performance metrics."""
    from .nepse_fetcher import fetch_all_stocks
    from .ml_predictor import predictor

    data = await fetch_all_stocks()
    predictor.ensure_trained(data.get("stocks", []))

    return predictor.get_model_metrics()


# ═══════════════════════════════════════════════════════════════════════════════
# HEALTH CHECK
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/api/health")
async def health_check():
    from .ml_predictor import predictor, HAS_XGBOOST
    autonomous_platform = get_research_platform()
    autonomous_status = autonomous_platform._status()
    
    # Check if we can fetch live data
    stocks_data = await fetch_all_stocks()
    data_source = stocks_data.get("source", "UNKNOWN")
    stocks_count = stocks_data.get("count", 0)
    
    return {
        "status": "operational",
        "version": "ULTIMATE-2.0-REALTIME",
        "stocks_loaded": stocks_count,
        "data_mode": f"LIVE DATA ONLY - Current source: {data_source}",
        "ml_trained": predictor.is_trained,
        "autonomous_platform": {
            "database_backend": autonomous_status.database_backend,
            "timescaledb_active": autonomous_status.timescaledb_active,
            "symbols_covered": autonomous_status.symbols_covered,
            "bars_loaded": autonomous_status.bars_loaded,
            "latest_training_at": autonomous_status.latest_training_at,
            "retrain_required": autonomous_status.retrain_required,
        },
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
