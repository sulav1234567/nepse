"""
Feature engineering and domain scoring for autonomous NEPSE analytics.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Optional, Union

import numpy as np
import pandas as pd

from .indicators import (
    adx,
    atr,
    bollinger_bands,
    build_technical_snapshot,
    ema,
    fibonacci_levels,
    ichimoku,
    macd,
    obv,
    prepare_price_frame,
    rsi,
    sma,
    stochastic_oscillator,
    support_resistance,
    vwap,
)

LAG_WINDOWS = (3, 5, 7, 10, 14, 20, 30, 45, 60, 90, 120)
HORIZONS = (7, 30, 90)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or (isinstance(value, float) and np.isnan(value)):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _score_linear(value: float, low: float, high: float, inverse: bool = False) -> float:
    if high == low:
        return 50.0
    clipped = max(low, min(high, value))
    ratio = (clipped - low) / (high - low)
    if inverse:
        ratio = 1 - ratio
    return float(np.clip(ratio * 100, 0, 100))


def sector_medians(fundamentals: pd.DataFrame) -> dict[str, dict[str, float]]:
    if fundamentals.empty:
        return {}
    grouped = fundamentals.groupby("sector").median(numeric_only=True)
    return grouped.to_dict(orient="index")


@dataclass
class FundamentalSnapshotScore:
    score: float
    payload: dict[str, Any]
    deterioration_flags: list[str]


def score_fundamentals(
    latest: Optional[Union[dict[str, Any], pd.Series]],
    sector_reference: Optional[dict[str, float]] = None,
) -> FundamentalSnapshotScore:
    latest = dict(latest or {})
    sector_reference = sector_reference or {}

    eps = _safe_float(latest.get("eps"))
    pe = _safe_float(latest.get("pe"))
    pb = _safe_float(latest.get("pb"))
    dividend_yield = _safe_float(latest.get("dividend_yield"))
    revenue_growth_yoy = _safe_float(latest.get("revenue_growth_yoy"))
    revenue_growth_qoq = _safe_float(latest.get("revenue_growth_qoq"))
    net_profit_margin = _safe_float(latest.get("net_profit_margin"))
    roe = _safe_float(latest.get("roe"))
    roa = _safe_float(latest.get("roa"))
    debt_to_equity = _safe_float(latest.get("debt_to_equity"))
    current_ratio = _safe_float(latest.get("current_ratio"))
    quick_ratio = _safe_float(latest.get("quick_ratio"))
    book_value_per_share = _safe_float(latest.get("book_value_per_share"))
    npl_ratio = latest.get("npl_ratio")
    casa_ratio = latest.get("casa_ratio")

    sector_pe = _safe_float(sector_reference.get("pe"), 15.0)
    sector_pb = _safe_float(sector_reference.get("pb"), 1.8)
    sector_roe = _safe_float(sector_reference.get("roe"), 12.0)

    components = {
        "eps": _score_linear(eps, 0.0, max(eps, 30.0)),
        "pe": _score_linear(pe if pe > 0 else sector_pe, max(4.0, sector_pe * 0.4), max(12.0, sector_pe * 1.8), inverse=True),
        "pb": _score_linear(pb if pb > 0 else sector_pb, max(0.3, sector_pb * 0.4), max(1.0, sector_pb * 2.0), inverse=True),
        "dividend_yield": _score_linear(dividend_yield, 0.0, 12.0),
        "revenue_growth_yoy": _score_linear(revenue_growth_yoy, -20.0, 35.0),
        "revenue_growth_qoq": _score_linear(revenue_growth_qoq, -15.0, 20.0),
        "net_profit_margin": _score_linear(net_profit_margin, -5.0, 35.0),
        "roe": _score_linear(roe, max(2.0, sector_roe * 0.5), max(8.0, sector_roe * 1.7)),
        "roa": _score_linear(roa, -1.0, 10.0),
        "debt_to_equity": _score_linear(debt_to_equity, 0.0, 3.0, inverse=True),
        "current_ratio": _score_linear(current_ratio, 0.6, 3.0),
        "quick_ratio": _score_linear(quick_ratio, 0.3, 2.0),
        "book_value_per_share": _score_linear(book_value_per_share, 0.0, max(book_value_per_share, 300.0)),
    }

    if npl_ratio is not None:
        components["npl_ratio"] = _score_linear(_safe_float(npl_ratio), 0.0, 12.0, inverse=True)
    if casa_ratio is not None:
        components["casa_ratio"] = _score_linear(_safe_float(casa_ratio), 10.0, 55.0)

    weights = {
        "eps": 0.06,
        "pe": 0.10,
        "pb": 0.08,
        "dividend_yield": 0.06,
        "revenue_growth_yoy": 0.10,
        "revenue_growth_qoq": 0.06,
        "net_profit_margin": 0.10,
        "roe": 0.12,
        "roa": 0.08,
        "debt_to_equity": 0.08,
        "current_ratio": 0.05,
        "quick_ratio": 0.04,
        "book_value_per_share": 0.07,
        "npl_ratio": 0.05,
        "casa_ratio": 0.05,
    }

    weighted_score = 0.0
    total_weight = 0.0
    for key, value in components.items():
        weight = weights.get(key, 0.04)
        weighted_score += value * weight
        total_weight += weight
    score = weighted_score / max(total_weight, 1e-9)

    deterioration_flags: list[str] = []
    if revenue_growth_yoy < 0:
        deterioration_flags.append("Revenue growth turned negative year-over-year.")
    if revenue_growth_qoq < 0:
        deterioration_flags.append("Quarter-on-quarter sales momentum is weakening.")
    if net_profit_margin < 0:
        deterioration_flags.append("Net profit margin is negative.")
    if roe < sector_roe * 0.75:
        deterioration_flags.append("ROE is trailing the sector median.")
    if debt_to_equity > 2.0:
        deterioration_flags.append("Leverage is elevated relative to healthy NEPSE balance sheets.")
    if npl_ratio is not None and _safe_float(npl_ratio) > 5.0:
        deterioration_flags.append("Asset quality risk is rising through the NPL ratio.")

    return FundamentalSnapshotScore(
        score=round(float(np.clip(score, 0, 100)), 2),
        payload={
            "fundamental_score": round(float(np.clip(score, 0, 100)), 2),
            "eps": round(eps, 2),
            "pe": round(pe, 2),
            "pb": round(pb, 2),
            "dividend_yield": round(dividend_yield, 2),
            "revenue_growth_yoy": round(revenue_growth_yoy, 2),
            "revenue_growth_qoq": round(revenue_growth_qoq, 2),
            "net_profit_margin": round(net_profit_margin, 2),
            "roe": round(roe, 2),
            "roa": round(roa, 2),
            "debt_to_equity": round(debt_to_equity, 2),
            "current_ratio": round(current_ratio, 2),
            "quick_ratio": round(quick_ratio, 2),
            "book_value_per_share": round(book_value_per_share, 2),
            "npl_ratio": None if npl_ratio is None else round(_safe_float(npl_ratio), 2),
            "casa_ratio": None if casa_ratio is None else round(_safe_float(casa_ratio), 2),
        },
        deterioration_flags=deterioration_flags,
    )


def detect_regime(index_frame: pd.DataFrame, breadth_ratio: Optional[float] = None) -> dict[str, Any]:
    prepared = prepare_price_frame(index_frame)
    if prepared.empty:
        return {
            "regime": "SIDEWAYS",
            "confidence": 40.0,
            "trend_score": 50.0,
            "volatility_score": 45.0,
            "breadth_score": 50.0,
            "liquidity_score": 45.0,
            "explanation": "Insufficient index history; the engine is defaulting to a neutral market regime.",
        }

    close = prepared["close"]
    returns = close.pct_change().fillna(0.0)
    ema_21 = ema(close, 21)
    ema_55 = ema(close, 55)
    trend_score = 50.0 + np.clip(((close.iloc[-1] / max(ema_55.iloc[-1], 1e-9)) - 1) * 250, -25, 25)
    trend_score += 10 if ema_21.iloc[-1] > ema_55.iloc[-1] else -10

    volatility = returns.rolling(20, min_periods=5).std(ddof=0).iloc[-1] * np.sqrt(252) * 100
    volatility_score = float(np.clip(volatility * 1.8, 0, 100))

    breadth_score = float(np.clip((breadth_ratio or 0.5) * 100, 0, 100))
    average_turnover = prepared["turnover"].rolling(20, min_periods=5).mean().iloc[-1] if "turnover" in prepared else 0.0
    liquidity_score = float(np.clip(np.log1p(max(average_turnover, 0.0)) * 6.5, 0, 100))

    monthly_return = close.iloc[-1] / max(close.iloc[max(len(close) - 21, 0)], 1e-9) - 1 if len(close) > 21 else 0.0

    if monthly_return < -0.12 and volatility_score > 70:
        regime = "CRISIS"
        confidence = min(96.0, 62.0 + volatility_score * 0.4)
        explanation = "Deep drawdown and volatility expansion point to a crisis regime."
    elif monthly_return < -0.05 and trend_score < 45:
        regime = "BEAR"
        confidence = min(92.0, 55.0 + abs(monthly_return) * 220)
        explanation = "Trend structure is weak and downside momentum remains dominant."
    elif monthly_return > 0.07 and trend_score > 62 and breadth_score > 52:
        regime = "BULL"
        confidence = min(94.0, 58.0 + trend_score * 0.35)
        explanation = "Price trend, participation, and momentum all support a bullish market regime."
    elif monthly_return > 0.02 and volatility_score > 55:
        regime = "DISTRIBUTION"
        confidence = min(88.0, 52.0 + volatility_score * 0.3)
        explanation = "The market is still elevated, but volatility and participation divergence suggest distribution."
    else:
        regime = "SIDEWAYS"
        confidence = 55.0
        explanation = "Price is rotating within a broad range without a decisive trend break."

    return {
        "regime": regime,
        "confidence": round(confidence, 2),
        "trend_score": round(float(np.clip(trend_score, 0, 100)), 2),
        "volatility_score": round(volatility_score, 2),
        "breadth_score": round(breadth_score, 2),
        "liquidity_score": round(liquidity_score, 2),
        "explanation": explanation,
    }


def compute_macro_correlation_signal(
    price_frame: pd.DataFrame,
    macro_frames: Optional[dict[str, pd.DataFrame]],
    sector: str,
) -> tuple[float, list[dict[str, Any]], dict[str, float], str]:
    if not macro_frames:
        return 50.0, [], {"remittance_tailwind": 0.0, "policy_rate_trend": 0.0, "commodity_pressure": 0.0, "crypto_sentiment": 0.0}, "Neutral"

    prepared = prepare_price_frame(price_frame)
    if prepared.empty:
        return 50.0, [], {"remittance_tailwind": 0.0, "policy_rate_trend": 0.0, "commodity_pressure": 0.0, "crypto_sentiment": 0.0}, "Neutral"

    stock_returns = prepared.set_index("date")["close"].pct_change().dropna()
    signals: list[dict[str, Any]] = []
    score = 50.0
    aggregates = {
        "remittance_tailwind": 0.0,
        "policy_rate_trend": 0.0,
        "commodity_pressure": 0.0,
        "crypto_sentiment": 0.0,
    }

    sector_sensitivity = {
        "Commercial Bank": {"NRB_POLICY_RATE": -1.0, "REMITTANCE_GROWTH": 1.0, "NIFTY50": 0.6},
        "Development Bank": {"NRB_POLICY_RATE": -1.0, "REMITTANCE_GROWTH": 0.8, "NIFTY50": 0.5},
        "Hydropower": {"CRUDE_OIL": -0.4, "GOLD_NPR": -0.2, "NIFTY50": 0.5},
        "Hotel & Tourism": {"CRUDE_OIL": -0.8, "BTC_SENTIMENT": 0.3, "SP500": 0.3},
        "Microfinance": {"NRB_POLICY_RATE": -0.8, "REMITTANCE_GROWTH": 0.7},
    }.get(sector, {"NIFTY50": 0.4, "SP500": 0.3, "NRB_POLICY_RATE": -0.5})

    for series_name, macro_frame in macro_frames.items():
        macro_prepared = prepare_price_frame(macro_frame)
        if macro_prepared.empty:
            continue
        macro_series = macro_prepared.set_index("date")["close"].pct_change().dropna()
        aligned = stock_returns.to_frame("stock").join(macro_series.rename("macro"), how="inner")
        if len(aligned) < 15:
            continue

        best_signal: Optional[dict[str, Any]] = None
        for lag in (1, 2, 3):
            shifted = aligned["macro"].shift(lag)
            corr = float(aligned["stock"].corr(shifted))
            if np.isnan(corr):
                continue
            latest_direction = "UP" if macro_series.iloc[-1] >= 0 else "DOWN"
            impact_strength = corr * (1 if latest_direction == "UP" else -1)
            impact_strength *= sector_sensitivity.get(series_name, 0.25)
            candidate = {
                "series": series_name,
                "lag_days": lag,
                "correlation": round(corr, 4),
                "latest_direction": latest_direction,
                "impact": "BULLISH" if impact_strength >= 0 else "BEARISH",
                "impact_strength": impact_strength,
            }
            if best_signal is None or abs(candidate["impact_strength"]) > abs(best_signal["impact_strength"]):
                best_signal = candidate

        if best_signal is None:
            continue

        score += np.clip(best_signal["impact_strength"] * 20, -8, 8)
        if series_name == "REMITTANCE_GROWTH":
            aggregates["remittance_tailwind"] = best_signal["impact_strength"] * 100
        elif series_name == "NRB_POLICY_RATE":
            aggregates["policy_rate_trend"] = best_signal["impact_strength"] * 100
        elif series_name in {"CRUDE_OIL", "GOLD_USD", "GOLD_NPR"}:
            aggregates["commodity_pressure"] += best_signal["impact_strength"] * 100 / 3
        elif series_name == "BTC_SENTIMENT":
            aggregates["crypto_sentiment"] = best_signal["impact_strength"] * 100
        signals.append(best_signal)

    signals.sort(key=lambda item: abs(item["impact_strength"]), reverse=True)
    macro_bias = "Bullish" if score >= 55 else "Bearish" if score <= 45 else "Neutral"
    return float(np.clip(score, 0, 100)), signals[:5], aggregates, macro_bias


def build_feature_frame(
    symbol: str,
    price_frame: pd.DataFrame,
    fundamentals_frame: Optional[pd.DataFrame] = None,
    sector_peer_frame: Optional[pd.DataFrame] = None,
    macro_frames: Optional[dict[str, pd.DataFrame]] = None,
    sentiment_frame: Optional[pd.DataFrame] = None,
    market_frame: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    prepared = prepare_price_frame(price_frame)
    if prepared.empty:
        return pd.DataFrame()

    feature_frame = prepared[["date", "open", "high", "low", "close", "volume", "turnover"]].copy()
    feature_frame["symbol"] = symbol
    feature_frame["return_1d"] = feature_frame["close"].pct_change().fillna(0.0)

    for window in LAG_WINDOWS:
        feature_frame[f"return_{window}d"] = feature_frame["close"].pct_change(window)
        feature_frame[f"volatility_{window}d"] = feature_frame["return_1d"].rolling(window, min_periods=2).std(ddof=0)
        feature_frame[f"volume_mean_{window}d"] = feature_frame["volume"].rolling(window, min_periods=1).mean()
        feature_frame[f"volume_ratio_{window}d"] = feature_frame["volume"] / feature_frame[f"volume_mean_{window}d"].replace(0, np.nan)
        feature_frame[f"range_ratio_{window}d"] = (
            (feature_frame["high"].rolling(window, min_periods=1).max() - feature_frame["low"].rolling(window, min_periods=1).min())
            / feature_frame["close"].replace(0, np.nan)
        )
        feature_frame[f"close_zscore_{window}d"] = (
            (feature_frame["close"] - feature_frame["close"].rolling(window, min_periods=1).mean())
            / feature_frame["close"].rolling(window, min_periods=2).std(ddof=0).replace(0, np.nan)
        )

    feature_frame["sma_20"] = sma(feature_frame["close"], 20)
    feature_frame["sma_50"] = sma(feature_frame["close"], 50)
    feature_frame["ema_9"] = ema(feature_frame["close"], 9)
    feature_frame["ema_21"] = ema(feature_frame["close"], 21)
    feature_frame["ema_50"] = ema(feature_frame["close"], 50)
    feature_frame["ema_200"] = ema(feature_frame["close"], 200)
    feature_frame["rsi_14"] = rsi(feature_frame["close"], 14)
    feature_frame["atr_14"] = atr(feature_frame, 14)
    feature_frame["adx_14"] = adx(feature_frame, 14)
    macd_frame = macd(feature_frame["close"])
    bb_frame = bollinger_bands(feature_frame["close"])
    stochastic_frame = stochastic_oscillator(feature_frame)
    ichi_frame = ichimoku(feature_frame)
    feature_frame = pd.concat([feature_frame, macd_frame, bb_frame, stochastic_frame, ichi_frame], axis=1)
    feature_frame["obv"] = obv(feature_frame)
    feature_frame["vwap_20"] = vwap(feature_frame, 20)
    feature_frame["vwap_gap_percent"] = (
        (feature_frame["close"] / feature_frame["vwap_20"].replace(0, np.nan)) - 1
    ) * 100
    feature_frame["fibonacci_38_2"] = fibonacci_levels(feature_frame)["38.2"]
    feature_frame["fibonacci_50"] = fibonacci_levels(feature_frame)["50.0"]
    feature_frame["fibonacci_61_8"] = fibonacci_levels(feature_frame)["61.8"]
    support, resistance = support_resistance(feature_frame)
    feature_frame["support_level"] = support
    feature_frame["resistance_level"] = resistance
    feature_frame["distance_to_support_pct"] = (
        (feature_frame["close"] / max(support, 1e-9)) - 1
    ) * 100
    feature_frame["distance_to_resistance_pct"] = (
        (resistance / feature_frame["close"].replace(0, np.nan)) - 1
    ) * 100
    feature_frame["day_of_week"] = feature_frame["date"].dt.dayofweek
    feature_frame["month"] = feature_frame["date"].dt.month
    feature_frame["quarter"] = feature_frame["date"].dt.quarter
    feature_frame["is_month_end"] = feature_frame["date"].dt.is_month_end.astype(int)

    if sector_peer_frame is not None and not sector_peer_frame.empty:
        sector_prepared = prepare_price_frame(sector_peer_frame)
        sector_prepared["sector_return_1d"] = sector_prepared["close"].pct_change().fillna(0.0)
        sector_reference = sector_prepared[["date", "sector_return_1d", "close"]].rename(
            columns={"close": "sector_close"}
        )
        feature_frame = feature_frame.merge(sector_reference, on="date", how="left")
        feature_frame["relative_strength_20d"] = (
            feature_frame["return_20d"] - feature_frame["sector_close"].pct_change(20)
        )

    if market_frame is not None and not market_frame.empty:
        market_prepared = prepare_price_frame(market_frame)
        market_prepared["market_return_1d"] = market_prepared["close"].pct_change().fillna(0.0)
        market_reference = market_prepared[["date", "market_return_1d"]]
        feature_frame = feature_frame.merge(market_reference, on="date", how="left")
        for window in (5, 20, 60):
            covariance = feature_frame["return_1d"].rolling(window, min_periods=5).cov(feature_frame["market_return_1d"])
            market_variance = feature_frame["market_return_1d"].rolling(window, min_periods=5).var()
            feature_frame[f"beta_{window}d"] = covariance / market_variance.replace(0, np.nan)
            feature_frame[f"alpha_{window}d"] = feature_frame[f"return_{window}d"] - feature_frame[f"beta_{window}d"] * market_prepared["market_return_1d"].rolling(window, min_periods=1).sum().reindex(feature_frame.index, fill_value=0.0)

    if fundamentals_frame is not None and not fundamentals_frame.empty:
        fundamentals = fundamentals_frame.copy()
        fundamentals["report_date"] = pd.to_datetime(fundamentals["report_date"], errors="coerce")
        fundamentals = fundamentals.sort_values("report_date")
        merge_columns = [
            "report_date",
            "eps",
            "pe",
            "pb",
            "dividend_yield",
            "revenue_growth_yoy",
            "revenue_growth_qoq",
            "net_profit_margin",
            "roe",
            "roa",
            "debt_to_equity",
            "current_ratio",
            "quick_ratio",
            "book_value_per_share",
            "npl_ratio",
            "casa_ratio",
        ]
        fundamentals = fundamentals[merge_columns]
        feature_frame = pd.merge_asof(
            feature_frame.sort_values("date"),
            fundamentals.sort_values("report_date"),
            left_on="date",
            right_on="report_date",
            direction="backward",
        )
        for column in (
            "eps",
            "pe",
            "pb",
            "dividend_yield",
            "revenue_growth_yoy",
            "revenue_growth_qoq",
            "net_profit_margin",
            "roe",
            "roa",
            "debt_to_equity",
            "current_ratio",
            "quick_ratio",
            "book_value_per_share",
            "npl_ratio",
            "casa_ratio",
        ):
            feature_frame[column] = feature_frame[column].ffill().fillna(0.0)

    if sentiment_frame is not None and not sentiment_frame.empty:
        sentiment_prepared = sentiment_frame.copy()
        # Normalise: the frame may arrive with 'date' (renamed by service.py) or 'published_at'
        if "published_at" not in sentiment_prepared.columns and "date" in sentiment_prepared.columns:
            sentiment_prepared = sentiment_prepared.rename(columns={"date": "published_at"})
        sentiment_prepared["published_at"] = pd.to_datetime(sentiment_prepared["published_at"], errors="coerce")
        grouped = (
            sentiment_prepared.groupby(sentiment_prepared["published_at"].dt.floor("D"))["sentiment_score"]
            .agg(["mean", "std", "count"])
            .reset_index()
            .rename(columns={"published_at": "date", "mean": "sentiment_mean", "std": "sentiment_std", "count": "sentiment_count"})
        )
        feature_frame = feature_frame.merge(grouped, on="date", how="left")
        feature_frame["sentiment_mean"] = feature_frame["sentiment_mean"].fillna(0.0)
        feature_frame["sentiment_std"] = feature_frame["sentiment_std"].fillna(0.0)
        feature_frame["sentiment_count"] = feature_frame["sentiment_count"].fillna(0.0)

    if macro_frames:
        for series_name, macro_frame in macro_frames.items():
            macro_prepared = prepare_price_frame(macro_frame)
            if macro_prepared.empty:
                continue
            series = macro_prepared[["date", "close"]].rename(columns={"close": f"{series_name.lower()}_close"})
            feature_frame = feature_frame.merge(series, on="date", how="left")
            close_column = f"{series_name.lower()}_close"
            feature_frame[close_column] = feature_frame[close_column].ffill()
            feature_frame[f"{series_name.lower()}_return_1d"] = feature_frame[close_column].pct_change().fillna(0.0)
            for window in (5, 20, 60):
                feature_frame[f"{series_name.lower()}_return_{window}d"] = feature_frame[close_column].pct_change(window)
                feature_frame[f"{series_name.lower()}_corr_{window}d"] = feature_frame["return_1d"].rolling(window, min_periods=5).corr(
                    feature_frame[f"{series_name.lower()}_return_1d"]
                )

    feature_frame["future_close_7d"] = feature_frame["close"].shift(-7)
    feature_frame["future_close_30d"] = feature_frame["close"].shift(-30)
    feature_frame["future_close_90d"] = feature_frame["close"].shift(-90)
    feature_frame["target_return_7d"] = (feature_frame["future_close_7d"] / feature_frame["close"] - 1) * 100
    feature_frame["target_return_30d"] = (feature_frame["future_close_30d"] / feature_frame["close"] - 1) * 100
    feature_frame["target_return_90d"] = (feature_frame["future_close_90d"] / feature_frame["close"] - 1) * 100
    feature_frame["target_direction_7d"] = (feature_frame["target_return_7d"] > 0).astype(int)

    # Never ffill/fill the label columns: forward-filled targets fabricate
    # future returns for the most recent rows and poison training.
    label_columns = {
        "future_close_7d", "future_close_30d", "future_close_90d",
        "target_return_7d", "target_return_30d", "target_return_90d",
        "target_direction_7d",
    }
    numeric_columns = [
        column for column in feature_frame.select_dtypes(include=[np.number]).columns
        if column not in label_columns
    ]
    feature_frame[numeric_columns] = feature_frame[numeric_columns].replace([np.inf, -np.inf], np.nan)
    feature_frame[numeric_columns] = feature_frame[numeric_columns].ffill().fillna(0.0)
    return feature_frame


def feature_columns(frame: pd.DataFrame) -> list[str]:
    excluded = {
        "date",
        "symbol",
        "future_close_7d",
        "future_close_30d",
        "future_close_90d",
        "target_return_7d",
        "target_return_30d",
        "target_return_90d",
        "target_direction_7d",
        "report_date",
    }
    return [column for column in frame.columns if column not in excluded and pd.api.types.is_numeric_dtype(frame[column])]


def compute_sector_rotation(signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for signal in signals:
        grouped[signal.get("sector", "Others")].append(signal)

    results: list[dict[str, Any]] = []
    for sector, items in grouped.items():
        technical = np.mean([_safe_float(item.get("technical_score")) for item in items])
        fundamental = np.mean([_safe_float(item.get("fundamental_score")) for item in items])
        global_score = np.mean([_safe_float(item.get("global_sentiment_score")) for item in items])
        liquidity = np.mean([_safe_float(item.get("liquidity_score")) for item in items])
        rotation_score = np.clip(technical * 0.4 + fundamental * 0.3 + global_score * 0.15 + liquidity * 0.15, 0, 100)
        signal_label = "Overweight" if rotation_score >= 65 else "Underweight" if rotation_score <= 40 else "Market Weight"
        commentary = (
            f"{sector} leads on technical momentum and liquidity."
            if signal_label == "Overweight"
            else f"{sector} is losing leadership and should be sized cautiously."
            if signal_label == "Underweight"
            else f"{sector} is balanced with no strong rotational edge right now."
        )
        results.append(
            {
                "sector": sector,
                "rotation_score": round(float(rotation_score), 2),
                "leadership_score": round(float(technical), 2),
                "momentum_score": round(float(technical), 2),
                "valuation_score": round(float(fundamental), 2),
                "liquidity_score": round(float(liquidity), 2),
                "signal": signal_label,
                "commentary": commentary,
            }
        )
    results.sort(key=lambda item: item["rotation_score"], reverse=True)
    return results


def summarize_reason_stack(
    technical_snapshot: Any,
    fundamental_score: FundamentalSnapshotScore,
    macro_score: float,
    macro_signals: list[dict[str, Any]],
    expected_return_percent: float,
) -> list[str]:
    reasons: list[str] = []

    if technical_snapshot.technical_score >= 65:
        reasons.append(
            f"Technical score {technical_snapshot.technical_score:.1f}/100 is strong with RSI {technical_snapshot.rsi_14:.1f} and ADX {technical_snapshot.adx:.1f}."
        )
    if fundamental_score.score >= 60:
        reasons.append(
            f"Fundamental score {fundamental_score.score:.1f}/100 is supported by ROE {fundamental_score.payload['roe']:.1f}% and margin {fundamental_score.payload['net_profit_margin']:.1f}%."
        )
    if macro_score >= 55 and macro_signals:
        top_signal = macro_signals[0]
        reasons.append(
            f"Global overlay is constructive: {top_signal['series']} shows a {top_signal['impact'].lower()} {top_signal['lag_days']}-day correlation."
        )
    if technical_snapshot.detected_patterns:
        reasons.append(
            f"Pattern engine detected {', '.join(technical_snapshot.detected_patterns[:2])}, improving tactical timing."
        )
    reasons.append(f"Expected return profile is {expected_return_percent:.2f}% with model agreement used in confidence calibration.")
    return reasons[:5]
