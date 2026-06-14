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
from .market_intelligence import build_market_intelligence
from .index_analysis import analyze_nepse_index
from .database import connect_to_mongodb, close_mongodb, UserManager
from .auth import AuthService, get_current_user
from .autonomous.api import router as autonomous_router
from .autonomous.service import get_research_platform
from .broker.api import router as broker_router

import numpy as np
import pandas as pd
from pathlib import Path
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
app.include_router(broker_router)


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


_MARKET_CSV_DIR = Path(__file__).resolve().parent.parent / "data" / "market" / "stocks"


def load_real_history(stock_data: StockData, bars: int = 180) -> list[HistoricalPrice]:
    """Load REAL OHLCV history for a stock from the local market CSV store.

    No synthetic/fabricated prices: if there is no stored history for the symbol
    we return an empty list and let callers report "data unavailable". When live
    intraday data is newer than the last stored bar, we append/refresh today's bar
    from the live quote (still real data, not invented).
    """
    csv_path = _MARKET_CSV_DIR / f"{stock_data.symbol.upper()}.csv"
    history: list[HistoricalPrice] = []
    if csv_path.exists():
        try:
            frame = pd.read_csv(csv_path).tail(bars)
            for _, row in frame.iterrows():
                close = float(row.get("close") or 0)
                if close <= 0:
                    continue
                history.append(HistoricalPrice(
                    date=str(row["date"])[:10],
                    open=round(float(row.get("open") or close), 2),
                    high=round(float(row.get("high") or close), 2),
                    low=round(float(row.get("low") or close), 2),
                    close=round(close, 2),
                    volume=int(float(row.get("volume") or 0)),
                ))
        except Exception as exc:
            logger.debug("Real history load failed for %s: %s", stock_data.symbol, exc)
            history = []

    # Fold in the live quote as the most recent bar (real data from the feed).
    if stock_data.cmp and stock_data.cmp > 0:
        today = datetime.now().strftime("%Y-%m-%d")
        live_bar = HistoricalPrice(
            date=today,
            open=round(stock_data.open or stock_data.cmp, 2),
            high=round(max(stock_data.high or stock_data.cmp, stock_data.cmp), 2),
            low=round(min(stock_data.low or stock_data.cmp, stock_data.cmp), 2),
            close=round(stock_data.cmp, 2),
            volume=int(stock_data.volume or 0),
        )
        if history and history[-1].date == today:
            history[-1] = live_bar
        elif history and history[-1].date < today:
            history.append(live_bar)
        elif not history:
            history.append(live_bar)
    return history


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
            hist = load_real_history(stock)
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
        "market_state": data.get("market_state", "UNKNOWN"),
        "is_live": data.get("is_live", False),
        "is_stale": data.get("is_stale", False),
        "as_of": data.get("as_of"),
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
            hist = load_real_history(stock)
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
    hist = load_real_history(stock)
    
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
    hist = load_real_history(stock)
    
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
# AI/ML PREDICTION ENDPOINTS — driven by the trained autonomous model suite.
# No synthetic fallback: if the model has no signals, these return 503.
# ═══════════════════════════════════════════════════════════════════════════════

def _confidence_band(score: float) -> str:
    if score >= 70:
        return "HIGH"
    if score >= 45:
        return "MEDIUM"
    return "LOW"


def _rise_probability(signal: str, confidence: float, return_7d: float) -> float:
    """Map the suite's signal + confidence to a 0-100 rise probability."""
    label = (signal or "").upper()
    if "STRONG BUY" in label:
        base = 50 + confidence * 0.45
    elif "BUY" in label:
        base = 50 + confidence * 0.32
    elif "STRONG SELL" in label:
        base = 50 - confidence * 0.45
    elif "SELL" in label:
        base = 50 - confidence * 0.32
    else:
        base = 50 + max(-8.0, min(8.0, return_7d)) * 1.2
    return round(max(5.0, min(95.0, base)), 1)


def _card_to_prediction(card, live_stock: dict, crash_risk: float, regime: str) -> dict:
    cmp = float(live_stock.get("cmp") or live_stock.get("ltp") or 0)
    votes = card.model_votes or []
    if votes:
        r7 = float(np.mean([v.predicted_return_7d for v in votes]))
        r30 = float(np.mean([v.predicted_return_30d for v in votes]))
        r90 = float(np.mean([v.predicted_return_90d for v in votes]))
    else:
        r7 = r30 = r90 = float(card.expected_return_percent)

    support = float(card.technical.support or 0)
    stop_loss = support if 0 < support < cmp else cmp * 0.95
    target_7d = cmp * (1 + r7 / 100)
    target_30d = cmp * (1 + r30 / 100)
    upside = max(target_7d, target_30d) - cmp
    downside = max(cmp - stop_loss, cmp * 0.005)

    reasons = list(card.top_reasons or [])
    warnings = list(card.warnings or [])
    rise_prob = _rise_probability(card.overall_signal, card.confidence_score, r7)

    technical = card.technical
    key_drivers = [
        {"feature": "RSI (14)", "value": round(technical.rsi_14, 1), "direction": "bullish" if technical.rsi_14 < 70 else "bearish", "importance": 0.8},
        {"feature": "MACD histogram", "value": round(technical.macd_histogram, 3), "direction": "bullish" if technical.macd_histogram > 0 else "bearish", "importance": 0.7},
        {"feature": "Bollinger position", "value": round(technical.bollinger_position, 2), "direction": "bullish" if technical.bollinger_position < 0.8 else "bearish", "importance": 0.5},
        {"feature": "ADX", "value": round(technical.adx, 1), "direction": "bullish" if technical.adx > 20 else "neutral", "importance": 0.4},
    ]

    return {
        "symbol": card.symbol,
        "name": card.company_name,
        "sector": card.sector,
        "cmp": round(cmp, 2),
        "changePercent": float(live_stock.get("changePercent") or 0),
        "riseProbability": rise_prob,
        "predictedChangePercent": round(r7, 2),
        "predictedRsChange": round(cmp * r7 / 100, 2),
        "predictedTarget": round(target_7d, 2),
        "confidence": _confidence_band(card.confidence_score),
        "risk": card.risk_level,
        "action": card.overall_signal,
        "recommendationSummary": "; ".join(reasons[:2]) or f"Model signal: {card.overall_signal}",
        "keyDrivers": key_drivers,
        "reasoning": " · ".join(reasons + warnings) or f"Trained ensemble signal {card.overall_signal} with {card.confidence_score:.0f}% confidence.",
        "modelScores": {v.model_name: round(v.confidence, 1) for v in votes},
        "buyRangeLow": round(min(cmp, max(stop_loss * 1.01, cmp * 0.97)), 2),
        "buyRangeHigh": round(cmp * 1.01, 2),
        "idealEntry": round(cmp, 2),
        "stopLoss": round(stop_loss, 2),
        "sellRangeLow": round(min(target_7d, target_30d), 2),
        "sellRangeHigh": round(max(target_7d, target_30d), 2),
        "expectedProfitRs": round(upside, 2),
        "expectedProfitPercent": round(upside / cmp * 100, 2) if cmp > 0 else 0.0,
        "expectedDownsideRs": round(downside, 2),
        "expectedDownsidePercent": round(downside / cmp * 100, 2) if cmp > 0 else 0.0,
        "riskRewardRatio": round(upside / downside, 2) if downside > 0 else 0.0,
        "holdDaysMin": 7,
        "holdDaysMax": 30,
        "timeToTargetDays": 30 if r30 > r7 else 7,
        "marketAlignment": regime,
        "crashRisk": round(crash_risk, 1),
        "exitTrigger": f"Close below stop loss Rs.{stop_loss:,.0f}",
        "signalAsOf": card.as_of.isoformat(),
        "expectedReturn90d": round(r90, 2),
    }


async def _trained_model_predictions() -> tuple[list[dict], dict, Any]:
    """Build prediction rows from the trained suite's signals + live prices."""
    platform = get_research_platform()
    cards = platform.signal_cards(limit=500)
    if not cards:
        raise HTTPException(
            status_code=503,
            detail="The trained model has no signals yet. Run POST /api/autonomous/signals/refresh after ingestion and training.",
        )

    data = await fetch_all_stocks()
    stocks = data.get("stocks", [])
    if not stocks:
        raise HTTPException(status_code=503, detail="Live market data is unavailable right now. Refusing to serve stale or fabricated prices.")
    live_map = {str(s.get("symbol", "")).upper(): s for s in stocks}

    market_data = await fetch_market_overview()
    market = await create_market_overview_from_data(market_data.get("data", {}))
    regime = detect_regime(market)
    market_intelligence = build_market_intelligence(market, stocks)
    crash_risk = float(market_intelligence.get("crash_risk", 0))

    predictions = []
    for card in cards:
        live_stock = live_map.get(card.symbol.upper())
        if not live_stock:
            continue
        cmp = float(live_stock.get("cmp") or live_stock.get("ltp") or 0)
        if cmp <= 0:
            continue
        predictions.append(_card_to_prediction(card, live_stock, crash_risk, regime.regime))

    predictions.sort(key=lambda p: p["riseProbability"], reverse=True)
    for rank, prediction in enumerate(predictions, start=1):
        prediction["rank"] = rank

    meta = {
        "totalStocks": len(stocks),
        "dataSource": data.get("source", "UNKNOWN"),
        "timestamp": data.get("timestamp"),
        "marketIntelligence": market_intelligence,
        "marketRegime": regime.regime,
        "signalsAsOf": cards[0].as_of.isoformat(),
    }
    return predictions, meta, platform


def _suite_feature_importance(platform, top_n: int = 20) -> list[dict]:
    """Real feature importances averaged across the suite's fitted tree models."""
    suite = platform.model_suite
    cols = list(getattr(suite, "feature_cols", []) or [])
    models = (getattr(suite.tree, "regressors", {}) or {}).get(7, [])
    if not cols or not models:
        return []
    aggregate = np.zeros(len(cols))
    counted = 0
    for model in models:
        importances = getattr(model, "feature_importances_", None)
        if importances is None or len(importances) != len(cols):
            continue
        values = np.asarray(importances, dtype=float)
        total = values.sum()
        if total > 0:
            aggregate += values / total
            counted += 1
    if counted == 0:
        return []
    aggregate /= counted
    ranked = sorted(zip(cols, aggregate), key=lambda item: item[1], reverse=True)[:top_n]
    return [{"feature": name, "importance": round(float(value), 4)} for name, value in ranked]


def _suite_model_metrics(platform) -> dict:
    suite = platform.model_suite
    return {
        "model_version": suite.model_version,
        "last_trained_at": suite.last_trained_at.isoformat() if suite.last_trained_at else None,
        "accuracy": suite.metrics.get("accuracy_7d", 0.0),
        "samples": suite.metrics.get("training_rows", 0),
        "features": len(getattr(suite, "feature_cols", []) or []),
        "training_time": 0.0,
        **{k: round(float(v), 4) for k, v in suite.metrics.items()},
    }


@app.get("/api/ai/predictions")
async def get_ai_predictions(top: int = 20):
    """
    Stock predictions computed by the TRAINED autonomous model suite
    (ensemble + LSTM + TFT + meta-learner), joined with live prices.
    """
    predictions, meta, platform = await _trained_model_predictions()
    return {
        "predictions": predictions[:top],
        "modelMetrics": _suite_model_metrics(platform),
        "featureImportance": _suite_feature_importance(platform),
        **meta,
    }


@app.get("/api/ai/prediction/{symbol}")
async def get_ai_prediction_detail(symbol: str):
    """Detailed trained-model prediction for a specific stock."""
    predictions, _, _ = await _trained_model_predictions()
    result = next((p for p in predictions if p["symbol"].upper() == symbol.upper()), None)
    if not result:
        raise HTTPException(status_code=404, detail=f"The trained model has no signal for {symbol}.")
    return result


@app.get("/api/ai/feature-importance")
async def get_feature_importance():
    """Feature importance from the trained suite's tree ensemble."""
    platform = get_research_platform()
    features = _suite_feature_importance(platform)
    return {"features": features, "totalFeatures": len(getattr(platform.model_suite, "feature_cols", []) or [])}


@app.get("/api/ai/model-metrics")
async def get_model_metrics():
    """Training and performance metrics of the trained autonomous model suite."""
    return _suite_model_metrics(get_research_platform())


# ═══════════════════════════════════════════════════════════════════════════════
# HEALTH CHECK
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/api/health")
async def health_check():
    from .autonomous.models import HAS_XGBOOST, HAS_LIGHTGBM, HAS_TORCH
    autonomous_platform = get_research_platform()
    autonomous_status = autonomous_platform._status()
    suite = autonomous_platform.model_suite

    # Check if we can fetch live data
    stocks_data = await fetch_all_stocks()
    data_source = stocks_data.get("source", "UNKNOWN")
    stocks_count = stocks_data.get("count", 0)

    return {
        "status": "operational",
        "version": "ULTIMATE-2.0-REALTIME",
        "stocks_loaded": stocks_count,
        "data_mode": f"LIVE DATA ONLY - Current source: {data_source}",
        "ml_trained": suite.model_version != "bootstrap",
        "model_version": suite.model_version,
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
            "lightgbm": HAS_LIGHTGBM,
            "torch": HAS_TORCH,
        }
    }
