"""
NEPSE-ALPHA ULTIMATE — Regime Detection & Prediction Engine
Uses: statsmodels (rolling OLS), scipy (correlations), numpy
"""

import numpy as np
import pandas as pd
from datetime import datetime
from typing import Optional

from .models import (
    StockData, HistoricalPrice, LayerWeights, RegimeDetection,
    DailyPrediction, WeeklyPrediction, MonthlyPrediction, MarketOverview
)
from .engine import analyze_stock, get_signal


# ═══════════════════════════════════════════════════════════════════════════════
# REGIME DETECTION
# ═══════════════════════════════════════════════════════════════════════════════

REGIME_WEIGHTS = {
    "BULL TREND": LayerWeights(fvl=0.20, tml=0.35, ssil=0.15, gtbil=0.25, mrlll=0.05),
    "BEAR TREND": LayerWeights(fvl=0.40, tml=0.15, ssil=0.10, gtbil=0.30, mrlll=0.05),
    "HIGH VOLATILITY": LayerWeights(fvl=0.15, tml=0.30, ssil=0.10, gtbil=0.40, mrlll=0.05),
    "SIDEWAYS": LayerWeights(fvl=0.30, tml=0.20, ssil=0.10, gtbil=0.35, mrlll=0.05),
    "POLITICAL RISK": LayerWeights(fvl=0.25, tml=0.15, ssil=0.05, gtbil=0.25, mrlll=0.30),
}

REGIME_MULTIPLIERS = {
    "BULL TREND": 1.0,
    "BEAR TREND": 0.40,
    "HIGH VOLATILITY": 0.60,
    "SIDEWAYS": 0.70,
    "POLITICAL RISK": 0.25,
}

REGIME_CASH_BUFFER = {
    "BULL TREND": 0.10,
    "BEAR TREND": 0.50,
    "HIGH VOLATILITY": 0.30,
    "SIDEWAYS": 0.20,
    "POLITICAL RISK": 0.60,
}

REGIME_BEST_SIGNALS = {
    "BULL TREND": ["D2", "D4", "W1", "W3"],
    "BEAR TREND": ["M1", "M2", "D3"],
    "HIGH VOLATILITY": ["D4", "D1", "W1"],
    "SIDEWAYS": ["W1", "M2", "M1"],
    "POLITICAL RISK": ["M1"],
}


def detect_regime(market: MarketOverview) -> RegimeDetection:
    """Detect market regime from market overview data."""
    regime = market.regime
    confidence = market.regime_confidence

    # Basic regime heuristics
    if market.nepse_change_percent > 1.5 and market.advancers > market.decliners * 1.5:
        regime = "BULL TREND"
        confidence = min(90, 60 + market.nepse_change_percent * 10)
    elif market.nepse_change_percent < -1.5 and market.decliners > market.advancers * 1.5:
        regime = "BEAR TREND"
        confidence = min(90, 60 + abs(market.nepse_change_percent) * 10)
    elif abs(market.nepse_change_percent) > 3:
        regime = "HIGH VOLATILITY"
        confidence = 65
    elif abs(market.nepse_change_percent) < 0.5:
        regime = "SIDEWAYS"
        confidence = 55

    # Liquidity stress override
    if market.interbank_rate > 7:
        regime = "BEAR TREND"
        confidence = max(confidence, 70)

    weights = REGIME_WEIGHTS.get(regime, REGIME_WEIGHTS["BULL TREND"])
    multiplier = REGIME_MULTIPLIERS.get(regime, 1.0)
    cash_buffer = REGIME_CASH_BUFFER.get(regime, 0.10)
    best_signals = REGIME_BEST_SIGNALS.get(regime, [])

    descriptions = {
        "BULL TREND": "Market in confirmed uptrend. Trust momentum signals. Let winners run.",
        "BEAR TREND": "Market declining. Only buy deepest value with institutional backing. Capital preservation priority.",
        "HIGH VOLATILITY": "Circuit-break environment. Smart broker tracking critical. Execute via V-TWAP.",
        "SIDEWAYS": "Range-bound market. Find what smart money is quietly loading before breakout.",
        "POLITICAL RISK": "Political instability detected. Maximum cash position. Only hold what you'd lock up for a week.",
    }

    return RegimeDetection(
        regime=regime,
        confidence=confidence,
        weights=weights,
        position_multiplier=multiplier,
        cash_buffer=cash_buffer,
        description=descriptions.get(regime, ""),
        best_signals=best_signals,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# DAILY PREDICTION ENGINE (Tier 1: 1-5 sessions)
# ═══════════════════════════════════════════════════════════════════════════════

DAILY_WEIGHTS = LayerWeights(fvl=0.10, tml=0.40, ssil=0.25, gtbil=0.20, mrlll=0.05)


def generate_daily_predictions(
    stocks: list[StockData],
    histories: dict[str, list[HistoricalPrice]],
    interbank_rate: float = 4.25,
) -> list[DailyPrediction]:
    """Generate Top 5 Daily Trade predictions with sector diversification."""
    analyses = []
    for stock in stocks:
        hist = histories.get(stock.symbol, [])
        analysis = analyze_stock(stock, hist, DAILY_WEIGHTS, interbank_rate)
        analyses.append(analysis)

    # Sort by FCS descending; apply volume confirmation quality filter
    analyses.sort(key=lambda a: a.fcs.score, reverse=True)
    actionable = [
        a for a in analyses
        if a.fcs.score >= 50
        and a.indicators.volume_ratio >= 0.5  # skip extremely illiquid days
    ]

    # Sector-diversified top-5: max 2 picks per sector
    top: list = []
    sector_counts: dict[str, int] = {}
    for a in actionable:
        sector = a.stock.sector
        if sector_counts.get(sector, 0) < 2:
            top.append(a)
            sector_counts[sector] = sector_counts.get(sector, 0) + 1
        if len(top) == 5:
            break

    predictions = []
    for rank, a in enumerate(top, 1):
        signal_type = _classify_daily_signal(a)
        predictions.append(DailyPrediction(
            rank=rank,
            symbol=a.stock.symbol,
            name=a.stock.name,
            signal_type=signal_type,
            entry_zone=f"Rs.{a.stock.cmp - a.indicators.atr14:.0f} - Rs.{a.stock.cmp + a.indicators.atr14 * 0.5:.0f}",
            target=a.price_targets.pt1,
            stop_loss=a.price_targets.stop_loss,
            confidence=a.fcs.score,
            signal=a.fcs.signal,
            rationale="; ".join(a.fvl_details[:1] + a.tml_details[:1] + a.gtbil_details[:1]),
        ))

    return predictions


def _classify_daily_signal(analysis) -> str:
    """Classify into D1-D7 signal types."""
    ind = analysis.indicators
    stock = analysis.stock

    if ind.volume_ratio > 2.5 and stock.change_percent > 1:
        return "D1 — Pre-Open Volume Spike"
    if stock.change_percent > 2 and ind.volume_ratio > 1.5:
        return "D2 — Overnight Gap + Volume Breakout"
    if stock.change_percent < -3 and ind.rsi14 < 35:
        return "D3 — Intraday Reversal (Oversold)"
    if stock.change_percent > 8 and ind.volume_ratio > 1.2:
        return "D4 — Circuit Break Momentum"
    # D6: fresh EMA-9/EMA-21 cross (EMA9 just crossed above 21 — new golden cross)
    if ind.ema_alignment == "GOLDEN" and abs(ind.ema9 - ind.ema21) / max(ind.ema21, 1) < 0.02:
        return "D6 — Fresh EMA-9/21 Golden Cross"
    # D7: MACD bullish crossover (histogram turning positive)
    if ind.macd_histogram > 0 and ind.macd_histogram < abs(ind.macd_line) * 0.15:
        return "D7 — Fresh MACD Bullish Crossover"
    if ind.volume_ratio > 1.3 and ind.rsi14 > 50:
        return "D5 — Social Trigger Front-Run"
    return "D2 — Momentum Entry"


# ═══════════════════════════════════════════════════════════════════════════════
# WEEKLY PREDICTION ENGINE (Tier 2: 5-15 sessions)
# ═══════════════════════════════════════════════════════════════════════════════

WEEKLY_WEIGHTS = LayerWeights(fvl=0.20, tml=0.30, ssil=0.20, gtbil=0.25, mrlll=0.05)


def generate_weekly_predictions(
    stocks: list[StockData],
    histories: dict[str, list[HistoricalPrice]],
    interbank_rate: float = 4.25,
) -> list[WeeklyPrediction]:
    """Generate Top 10 Weekly Position predictions with sector diversification."""
    analyses = []
    for stock in stocks:
        hist = histories.get(stock.symbol, [])
        analysis = analyze_stock(stock, hist, WEEKLY_WEIGHTS, interbank_rate)
        analyses.append(analysis)

    analyses.sort(key=lambda a: a.fcs.score, reverse=True)

    # Sector-diversified top-10: max 3 picks per sector
    actionable = [a for a in analyses if a.fcs.score >= 45]
    top: list = []
    sector_counts: dict[str, int] = {}
    for a in actionable:
        sector = a.stock.sector
        if sector_counts.get(sector, 0) < 3:
            top.append(a)
            sector_counts[sector] = sector_counts.get(sector, 0) + 1
        if len(top) == 10:
            break

    predictions = []
    for a in top:
        signal_type = _classify_weekly_signal(a)
        predictions.append(WeeklyPrediction(
            symbol=a.stock.symbol,
            name=a.stock.name,
            entry_range=f"Rs.{a.stock.cmp - a.indicators.atr14 * 1.5:.0f} - Rs.{a.stock.cmp:.0f}",
            target_week=a.price_targets.pt1,
            stop_loss=a.price_targets.stop_loss,
            fcs=a.fcs.score,
            signal=a.fcs.signal,
            time_horizon="1-3 weeks",
            key_driver=signal_type,
        ))

    return predictions


def _classify_weekly_signal(analysis) -> str:
    ind = analysis.indicators
    stock = analysis.stock

    if ind.volume_ratio > 1.3 and abs(stock.change_percent) < 1.5 and analysis.fcs.layer_scores.gtbil > 65:
        return "W1 — Institutional Accumulation Breakout"
    if ind.ema_alignment == "GOLDEN" and ind.rsi14 > 40 and ind.rsi14 < 60:
        return "W2 — EMA Golden Cross Confirmation"
    if stock.change_percent > 5 and ind.volume_ratio < 1:
        return "W3 — Post-Circuit Cooldown Buy"
    if stock.dividend_yield > 5:
        return "W4 — Pre-Book-Close Dividend Setup"
    return "W5 — Sector Rotation Wave"


# ═══════════════════════════════════════════════════════════════════════════════
# MONTHLY PREDICTION ENGINE (Tier 3: 15-60 sessions)
# ═══════════════════════════════════════════════════════════════════════════════

MONTHLY_WEIGHTS = LayerWeights(fvl=0.35, tml=0.20, ssil=0.10, gtbil=0.25, mrlll=0.10)


def generate_monthly_predictions(
    stocks: list[StockData],
    histories: dict[str, list[HistoricalPrice]],
    interbank_rate: float = 4.25,
) -> list[MonthlyPrediction]:
    """Generate Top 5 Monthly Conviction Picks with sector diversification."""
    analyses = []
    for stock in stocks:
        hist = histories.get(stock.symbol, [])
        analysis = analyze_stock(stock, hist, MONTHLY_WEIGHTS, interbank_rate)
        analyses.append(analysis)

    analyses.sort(key=lambda a: a.fcs.score, reverse=True)

    # Sector-diversified top-5: max 2 picks per sector, higher quality filter
    actionable = [a for a in analyses if a.fcs.score >= 50]
    top: list = []
    sector_counts: dict[str, int] = {}
    for a in actionable:
        sector = a.stock.sector
        if sector_counts.get(sector, 0) < 2:
            top.append(a)
            sector_counts[sector] = sector_counts.get(sector, 0) + 1
        if len(top) == 5:
            break

    predictions = []
    for a in top:
        signal_type = _classify_monthly_signal(a)
        target_3m = round(a.price_targets.pt2 * 1.15)

        predictions.append(MonthlyPrediction(
            symbol=a.stock.symbol,
            name=a.stock.name,
            entry_strategy=f"Scale in over 3-5 sessions at Rs.{a.stock.cmp - a.indicators.atr14 * 2:.0f} - Rs.{a.stock.cmp:.0f}",
            target_1m=a.price_targets.pt1,
            target_3m=target_3m,
            stop_loss=a.price_targets.stop_loss,
            portfolio_weight=round(min(15, max(3, a.fcs.score / 7)), 1),
            signal=a.fcs.signal,
            thesis=_generate_thesis(a),
            catalyst_calendar=_get_catalyst_calendar(a.stock),
            invalidation_conditions=[
                f"Price closes below Rs.{a.price_targets.stop_loss:.0f}",
                f"BMR drops below 15%",
                "SIS rises above 88",
                "Political risk upgrades to CRITICAL",
                "NIFTY drops > 2% in single session",
            ],
        ))

    return predictions


def _classify_monthly_signal(analysis) -> str:
    stock = analysis.stock
    fcs = analysis.fcs

    if fcs.layer_scores.fvl > 80:
        return "M1 — Deep Value with Catalyst"
    if fcs.layer_scores.gtbil > 70:
        return "M2 — Sustained Institutional Accumulation"
    if stock.sector in ("Commercial Bank", "Development Bank"):
        return "M3 — Macro Regime Change Trade"
    if stock.sector == "Hydropower":
        return "M4 — Monsoon-Hydropower Seasonal Alpha"
    return "M5 — Post-Correction Recovery"


def _generate_thesis(analysis) -> str:
    stock = analysis.stock
    fcs = analysis.fcs
    parts = []

    if fcs.layer_scores.fvl > 65:
        parts.append(f"Fundamentally undervalued (FVL {fcs.layer_scores.fvl:.0f}/100)")
    if fcs.layer_scores.tml > 60:
        parts.append(f"Technical momentum positive (TML {fcs.layer_scores.tml:.0f}/100)")
    if fcs.layer_scores.gtbil > 60:
        parts.append(f"Institutional backing confirmed (GTBIL {fcs.layer_scores.gtbil:.0f}/100)")

    # Graham number context
    if stock.eps > 0 and stock.book_value > 0:
        graham = (22.5 * stock.eps * stock.book_value) ** 0.5
        margin = ((stock.cmp / graham) - 1) * 100
        if margin < -10:
            parts.append(f"Graham intrinsic value Rs.{graham:.0f} (CMP {margin:+.0f}% vs intrinsic)")

    parts.append(f"P/E {stock.pe:.1f}, P/B {stock.pb:.2f}, ROE {stock.roe:.1f}%, Div {stock.dividend_yield:.1f}%")

    return ". ".join(parts) + "."


def _get_catalyst_calendar(stock: StockData) -> str:
    month = datetime.now().month
    catalysts = []

    if stock.sector == "Hydropower" and month < 6:
        catalysts.append("Monsoon season (Jun-Sep): Generation peak")
    if stock.dividend_yield > 4:
        catalysts.append("High dividend: Pre-book-close rally window expected")

    catalysts.append("Q3 earnings release expected")
    catalysts.append("AGM season approaching")

    return " | ".join(catalysts)
