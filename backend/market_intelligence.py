"""
NEPSE-ALPHA ULTIMATE — Market Intelligence Engine
Builds a market-state, crash-risk, and sector-leadership view from the
current live market snapshot and the available stock universe.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

import numpy as np

from .models import MarketOverview


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return round(float(max(low, min(high, value))), 2)


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _sector_breakdown(stocks: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], float]:
    sector_map: dict[str, list[dict[str, Any]]] = defaultdict(list)
    total_turnover_proxy = 0.0

    for stock in stocks:
        sector = str(stock.get("sector", "Others") or "Others")
        sector_map[sector].append(stock)
        total_turnover_proxy += _to_float(stock.get("turnover"), _to_float(stock.get("cmp")) * _to_float(stock.get("volume")))

    leaders: list[dict[str, Any]] = []
    laggards: list[dict[str, Any]] = []
    top_volume_share = 0.0

    for sector, members in sector_map.items():
        if not members:
            continue

        changes = np.array([_to_float(item.get("changePercent")) for item in members], dtype=float)
        volumes = np.array([_to_float(item.get("volume")) for item in members], dtype=float)
        turnover = sum(
            _to_float(item.get("turnover"), _to_float(item.get("cmp")) * _to_float(item.get("volume")))
            for item in members
        )
        breadth = float(np.mean(changes > 0)) if len(changes) else 0.0
        avg_change = float(np.mean(changes)) if len(changes) else 0.0
        median_change = float(np.median(changes)) if len(changes) else 0.0
        avg_volume = float(np.mean(volumes)) if len(volumes) else 0.0
        score = avg_change * 11 + breadth * 28 + np.tanh(avg_volume / 400_000) * 8
        sector_payload = {
            "sector": sector,
            "avg_change": round(avg_change, 2),
            "median_change": round(median_change, 2),
            "breadth": round(breadth * 100, 1),
            "count": len(members),
            "turnover_proxy": round(turnover, 2),
            "leadership_score": round(score, 2),
        }
        leaders.append(sector_payload)
        laggards.append(sector_payload)

        if total_turnover_proxy > 0:
            top_volume_share = max(top_volume_share, turnover / total_turnover_proxy)

    leaders.sort(key=lambda item: item["leadership_score"], reverse=True)
    laggards.sort(key=lambda item: item["leadership_score"])
    return leaders[:4], laggards[:4], round(top_volume_share, 3)


def build_market_intelligence(market: MarketOverview, stocks: list[dict[str, Any]]) -> dict[str, Any]:
    total = max(len(stocks), 1)
    changes = np.array([_to_float(stock.get("changePercent")) for stock in stocks], dtype=float) if stocks else np.array([0.0])
    volumes = np.array([_to_float(stock.get("volume")) for stock in stocks], dtype=float) if stocks else np.array([0.0])
    avg_volumes = np.array(
        [_to_float(stock.get("avgVolume20d"), max(1.0, _to_float(stock.get("volume")))) for stock in stocks],
        dtype=float,
    ) if stocks else np.array([1.0])

    breadth_ratio = market.advancers / max(1, market.advancers + market.decliners)
    up_volume_share = (
        float(np.sum(volumes[changes > 0])) / max(float(np.sum(volumes)), 1.0)
        if len(stocks) > 0 and float(np.sum(volumes)) > 0
        else breadth_ratio
    )
    average_change = float(np.mean(changes)) if len(changes) else 0.0
    median_change = float(np.median(changes)) if len(changes) else 0.0
    dispersion = float(np.std(changes)) if len(changes) else abs(market.nepse_change_percent)
    downside_tail = float(np.mean(changes <= -4.0)) if len(changes) else 0.0
    upside_tail = float(np.mean(changes >= 4.0)) if len(changes) else 0.0
    volume_ratio_mean = float(np.mean(np.divide(volumes, np.maximum(avg_volumes, 1)))) if len(changes) else 1.0
    turnover_b = market.total_turnover / 1_000_000_000 if market.total_turnover else 0.0

    leaders, laggards, concentration_risk = _sector_breakdown(stocks)

    trend_score = _clamp(
        50
        + market.nepse_change_percent * 10.5
        + (breadth_ratio - 0.5) * 75
        + average_change * 3
        + (up_volume_share - 0.5) * 30
    )
    liquidity_score = _clamp(
        40
        + min(turnover_b, 10) * 4.5
        + (up_volume_share - 0.5) * 35
        + min(max(volume_ratio_mean - 1.0, -0.5), 1.5) * 15
        - max(0.0, market.interbank_rate - 4.5) * 8
    )
    volatility_score = _clamp(abs(market.nepse_change_percent) * 16 + max(0.0, dispersion - 1.5) * 15)
    froth_score = _clamp(
        upside_tail * 100 * 0.7
        + max(0.0, market.nepse_change_percent) * 12
        + max(0.0, volume_ratio_mean - 1.1) * 24
        + max(0.0, dispersion - 2.2) * 10
    )
    drawdown_pressure = _clamp(
        max(0.0, -market.nepse_change_percent) * 14
        + max(0.0, 0.5 - breadth_ratio) * 110
        + downside_tail * 100 * 0.45
        + max(0.0, dispersion - 2.8) * 14
        + max(0.0, market.interbank_rate - 5.2) * 8
        + concentration_risk * 35
    )
    crash_risk = _clamp(drawdown_pressure - max(0.0, trend_score - 58) * 0.35)

    if crash_risk >= 72 or (breadth_ratio < 0.34 and market.nepse_change_percent < -1.2):
        bias = "BEARISH"
        action = "CAPITAL PRESERVATION"
    elif volatility_score >= 60 or froth_score >= 72:
        bias = "HIGH VOLATILITY"
        action = "TACTICAL ONLY"
    elif trend_score >= 64 and crash_risk < 40:
        bias = "BULLISH"
        action = "RISK-ON"
    else:
        bias = "NEUTRAL"
        action = "SELECTIVE"

    if crash_risk >= 75:
        crash_level = "SEVERE"
    elif crash_risk >= 60:
        crash_level = "ELEVATED"
    elif crash_risk >= 40:
        crash_level = "WATCH"
    else:
        crash_level = "LOW"

    support_band = max(
        0.006,
        min(0.05, abs(market.nepse_change_percent) / 100 + dispersion / 120),
    )
    support_low = round(market.nepse_index * (1 - support_band * 1.6), 2) if market.nepse_index else 0.0
    support_high = round(market.nepse_index * (1 - support_band * 0.7), 2) if market.nepse_index else 0.0
    resistance_low = round(market.nepse_index * (1 + support_band * 0.7), 2) if market.nepse_index else 0.0
    resistance_high = round(market.nepse_index * (1 + support_band * 1.6), 2) if market.nepse_index else 0.0

    warnings: list[dict[str, str]] = []
    opportunities: list[str] = []

    if crash_risk >= 60:
        warnings.append({
            "level": "HIGH",
            "title": "Crash Symptoms Rising",
            "message": "Breadth deterioration, downside tail-risk, and liquidity pressure are aligned. Keep exposure light and honor stops.",
        })
    if breadth_ratio < 0.4:
        warnings.append({
            "level": "MEDIUM",
            "title": "Breadth Weakness",
            "message": f"Only {breadth_ratio * 100:.0f}% of active names are advancing. Leadership is thinning beneath the index move.",
        })
    if concentration_risk > 0.34:
        warnings.append({
            "level": "MEDIUM",
            "title": "Leadership Narrowing",
            "message": "A small part of the market is carrying turnover. Narrow rallies are fragile and vulnerable to reversal.",
        })
    if froth_score >= 72:
        warnings.append({
            "level": "MEDIUM",
            "title": "FOMO Overheating",
            "message": "Momentum is strong, but speculative heat is elevated. Favor scaled entries instead of chasing extended candles.",
        })
    if market.interbank_rate > 6:
        warnings.append({
            "level": "HIGH",
            "title": "Liquidity Stress",
            "message": "Money-market conditions are tightening. Funding stress often weakens follow-through in Nepal's equity market.",
        })

    if bias == "BULLISH":
        opportunities.append("Breadth and volume participation support a risk-on backdrop for strong relative-strength names.")
    if leaders:
        leader = leaders[0]
        opportunities.append(
            f"{leader['sector']} is leading with {leader['avg_change']:+.2f}% average change and {leader['breadth']:.0f}% positive breadth."
        )
    if crash_risk < 35 and froth_score < 65:
        opportunities.append("Crash risk remains contained, so pullbacks into support are more constructive than random breakdowns.")
    if median_change > 0 and up_volume_share > 0.52:
        opportunities.append("Breadth quality is improving with gains supported by volume, not just thin prints.")

    bull_probability = _clamp(trend_score * 0.62 + liquidity_score * 0.25 - crash_risk * 0.18, 0, 100)
    bear_probability = _clamp(crash_risk * 0.72 + max(0.0, 50 - trend_score) * 0.38, 0, 100)

    return {
        "bias": bias,
        "action": action,
        "breadth_ratio": round(breadth_ratio * 100, 1),
        "up_volume_share": round(up_volume_share * 100, 1),
        "average_change": round(average_change, 2),
        "median_change": round(median_change, 2),
        "dispersion": round(dispersion, 2),
        "trend_score": trend_score,
        "liquidity_score": liquidity_score,
        "volatility_score": volatility_score,
        "froth_score": froth_score,
        "crash_risk": crash_risk,
        "crash_level": crash_level,
        "bull_probability": bull_probability,
        "bear_probability": bear_probability,
        "support_low": support_low,
        "support_high": support_high,
        "resistance_low": resistance_low,
        "resistance_high": resistance_high,
        "concentration_risk": round(concentration_risk * 100, 1),
        "warnings": warnings,
        "opportunities": opportunities[:4],
        "sector_leaders": leaders,
        "sector_laggards": laggards,
        "snapshot_stats": {
            "stocks": total,
            "advancers": market.advancers,
            "decliners": market.decliners,
            "unchanged": market.unchanged,
            "upside_tail": round(upside_tail * 100, 1),
            "downside_tail": round(downside_tail * 100, 1),
            "average_volume_ratio": round(volume_ratio_mean, 2),
        },
    }
