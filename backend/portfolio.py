"""
NEPSE-ALPHA ULTIMATE — Portfolio Optimizer
Uses: PyPortfolioOpt (pypfopt) for Sortino ratio optimization
      subject to regime multiplier constraints
"""

import numpy as np
import pandas as pd
from typing import Optional

from .models import PortfolioOptResult, StockData, HistoricalPrice


def optimize_portfolio(
    stocks: list[StockData],
    histories: dict[str, list[HistoricalPrice]],
    fcs_scores: dict[str, float],
    regime_multiplier: float = 1.0,
    risk_free_rate: float = 0.058,
    max_single_position: float = 0.15,
) -> PortfolioOptResult:
    """
    Portfolio optimization using Sortino ratio with regime constraints.
    
    Uses PyPortfolioOpt when available, falls back to custom implementation.
    """
    # Build returns DataFrame
    returns_data = {}
    symbols = []
    
    for stock in stocks:
        hist = histories.get(stock.symbol, [])
        if len(hist) < 10:
            continue
        closes = pd.Series([h.close for h in hist])
        daily_returns = closes.pct_change().dropna()
        if len(daily_returns) > 5:
            returns_data[stock.symbol] = daily_returns.values[-30:]  # last 30 days
            symbols.append(stock.symbol)
    
    if len(symbols) < 2:
        return PortfolioOptResult(
            weights={s.symbol: 1.0 / len(stocks) for s in stocks},
            expected_return=0.0,
            expected_volatility=0.0,
            sortino_ratio=0.0,
            sharpe_ratio=0.0,
        )
    
    # Pad to same length
    min_len = min(len(v) for v in returns_data.values())
    returns_df = pd.DataFrame({s: returns_data[s][-min_len:] for s in symbols})
    
    try:
        from pypfopt import expected_returns, risk_models
        from pypfopt.efficient_frontier import EfficientFrontier
        
        # Annualized expected returns (using mean historical returns)
        mu = expected_returns.mean_historical_return(
            returns_df.cumsum().apply(np.exp),  # Convert to prices
            frequency=252
        )
        
        # Covariance matrix
        S = risk_models.sample_cov(
            returns_df.cumsum().apply(np.exp),
            frequency=252
        )
        
        # Apply FCS-based return boost (higher conviction = higher expected return)
        for sym in symbols:
            if sym in fcs_scores:
                fcs_boost = (fcs_scores[sym] - 50) / 100 * 0.1  # +/- 10% based on FCS
                mu[sym] = mu[sym] + fcs_boost
        
        # Efficient frontier optimization
        ef = EfficientFrontier(mu, S, weight_bounds=(0, max_single_position * regime_multiplier))
        
        try:
            ef.max_sharpe(risk_free_rate=risk_free_rate)
        except Exception:
            ef.max_quadratic_utility()
        
        clean_weights = ef.clean_weights()
        perf = ef.portfolio_performance(risk_free_rate=risk_free_rate)
        
        # Compute Sortino ratio
        portfolio_returns = returns_df.dot(pd.Series(clean_weights).reindex(returns_df.columns).fillna(0))
        downside = portfolio_returns[portfolio_returns < 0]
        downside_dev = np.sqrt(np.mean(downside ** 2)) * np.sqrt(252) if len(downside) > 0 else 0.01
        ann_return = np.mean(portfolio_returns) * 252
        sortino = (ann_return - risk_free_rate) / downside_dev if downside_dev > 0 else 0
        
        return PortfolioOptResult(
            weights=clean_weights,
            expected_return=round(perf[0] * 100, 2),
            expected_volatility=round(perf[1] * 100, 2),
            sortino_ratio=round(sortino, 2),
            sharpe_ratio=round(perf[2], 2),
        )
        
    except ImportError:
        # Fallback: FCS-weighted allocation
        return _fallback_optimization(symbols, returns_df, fcs_scores, regime_multiplier, risk_free_rate)


def _fallback_optimization(
    symbols: list[str],
    returns_df: pd.DataFrame,
    fcs_scores: dict[str, float],
    regime_multiplier: float,
    risk_free_rate: float,
) -> PortfolioOptResult:
    """Fallback portfolio optimization using FCS-weighted allocation."""
    # Weight by FCS score
    raw_weights = {}
    total_fcs = 0
    for sym in symbols:
        fcs = fcs_scores.get(sym, 50)
        raw_weights[sym] = max(0, fcs - 30)  # Only allocate to FCS > 30
        total_fcs += raw_weights[sym]
    
    if total_fcs == 0:
        weights = {sym: 1.0 / len(symbols) for sym in symbols}
    else:
        weights = {sym: round(w / total_fcs * regime_multiplier, 4) for sym, w in raw_weights.items()}
    
    # Compute portfolio metrics
    weight_series = pd.Series(weights).reindex(returns_df.columns).fillna(0)
    port_returns = returns_df.dot(weight_series)
    
    ann_return = float(np.mean(port_returns) * 252)
    ann_vol = float(np.std(port_returns) * np.sqrt(252))
    
    downside = port_returns[port_returns < 0]
    downside_dev = float(np.sqrt(np.mean(downside ** 2)) * np.sqrt(252)) if len(downside) > 0 else 0.01
    
    sortino = (ann_return - risk_free_rate) / downside_dev if downside_dev > 0 else 0
    sharpe = (ann_return - risk_free_rate) / ann_vol if ann_vol > 0 else 0
    
    return PortfolioOptResult(
        weights=weights,
        expected_return=round(ann_return * 100, 2),
        expected_volatility=round(ann_vol * 100, 2),
        sortino_ratio=round(sortino, 2),
        sharpe_ratio=round(sharpe, 2),
    )
