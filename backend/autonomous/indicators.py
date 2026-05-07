"""
Technical indicator and pattern detection utilities.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import numpy as np
import pandas as pd


def prepare_price_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Standardize a price frame for downstream analytics."""
    if frame.empty:
        return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])

    renamed = frame.rename(columns={"ts": "date"}).copy()
    if "date" not in renamed.columns:
        renamed["date"] = pd.RangeIndex(len(renamed))
    renamed["date"] = pd.to_datetime(renamed["date"], errors="coerce")
    for column in ("open", "high", "low", "close", "volume", "turnover"):
        if column not in renamed.columns:
            renamed[column] = 0.0
        renamed[column] = pd.to_numeric(renamed[column], errors="coerce").fillna(0.0)
    return renamed.sort_values("date").reset_index(drop=True)


def sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(period, min_periods=1).mean()


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False, min_periods=1).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    up = delta.clip(lower=0)
    down = -delta.clip(upper=0)
    avg_gain = up.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = down.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    result = 100 - 100 / (1 + rs)
    return result.fillna(50.0)


def macd(series: pd.Series, fast: int = 12, slow: int = 26, signal_period: int = 9) -> pd.DataFrame:
    ema_fast = ema(series, fast)
    ema_slow = ema(series, slow)
    macd_line = ema_fast - ema_slow
    signal_line = ema(macd_line, signal_period)
    histogram = macd_line - signal_line
    return pd.DataFrame(
        {
            "macd_line": macd_line,
            "macd_signal": signal_line,
            "macd_histogram": histogram,
        }
    )


def bollinger_bands(series: pd.Series, period: int = 20, std_dev: float = 2.0) -> pd.DataFrame:
    mid = sma(series, period)
    std = series.rolling(period, min_periods=1).std(ddof=0).fillna(0.0)
    upper = mid + std * std_dev
    lower = mid - std * std_dev
    width = (upper - lower) / mid.replace(0, np.nan)
    position = (series - lower) / (upper - lower).replace(0, np.nan)
    return pd.DataFrame(
        {
            "bb_mid": mid,
            "bb_upper": upper,
            "bb_lower": lower,
            "bb_width": width.fillna(0.0),
            "bb_position": position.clip(-1, 2).fillna(0.5),
        }
    )


def true_range(frame: pd.DataFrame) -> pd.Series:
    previous_close = frame["close"].shift(1).fillna(frame["close"])
    return pd.concat(
        [
            frame["high"] - frame["low"],
            (frame["high"] - previous_close).abs(),
            (frame["low"] - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)


def atr(frame: pd.DataFrame, period: int = 14) -> pd.Series:
    return true_range(frame).rolling(period, min_periods=1).mean()


def adx(frame: pd.DataFrame, period: int = 14) -> pd.Series:
    high = frame["high"]
    low = frame["low"]
    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    atr_values = atr(frame, period).replace(0, np.nan)
    plus_di = 100 * pd.Series(plus_dm, index=frame.index).ewm(alpha=1 / period, adjust=False).mean() / atr_values
    minus_di = 100 * pd.Series(minus_dm, index=frame.index).ewm(alpha=1 / period, adjust=False).mean() / atr_values
    dx = ((plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)) * 100
    return dx.ewm(alpha=1 / period, adjust=False, min_periods=period).mean().fillna(20.0)


def stochastic_oscillator(frame: pd.DataFrame, period: int = 14, smooth: int = 3) -> pd.DataFrame:
    lowest_low = frame["low"].rolling(period, min_periods=1).min()
    highest_high = frame["high"].rolling(period, min_periods=1).max()
    k = 100 * (frame["close"] - lowest_low) / (highest_high - lowest_low).replace(0, np.nan)
    d = k.rolling(smooth, min_periods=1).mean()
    return pd.DataFrame({"stoch_k": k.fillna(50.0), "stoch_d": d.fillna(50.0)})


def ichimoku(frame: pd.DataFrame) -> pd.DataFrame:
    high = frame["high"]
    low = frame["low"]
    close = frame["close"]

    conversion = (high.rolling(9, min_periods=1).max() + low.rolling(9, min_periods=1).min()) / 2
    base = (high.rolling(26, min_periods=1).max() + low.rolling(26, min_periods=1).min()) / 2
    span_a = ((conversion + base) / 2).shift(26)
    span_b = ((high.rolling(52, min_periods=1).max() + low.rolling(52, min_periods=1).min()) / 2).shift(26)
    lagging = close.shift(-26)
    return pd.DataFrame(
        {
            "tenkan_sen": conversion,
            "kijun_sen": base,
            "senkou_span_a": span_a,
            "senkou_span_b": span_b,
            "chikou_span": lagging,
        }
    )


def obv(frame: pd.DataFrame) -> pd.Series:
    direction = np.sign(frame["close"].diff().fillna(0.0))
    return (direction * frame["volume"]).cumsum()


def vwap(frame: pd.DataFrame, period: int = 20) -> pd.Series:
    typical_price = (frame["high"] + frame["low"] + frame["close"]) / 3
    volume = frame["volume"].replace(0, np.nan)
    pv = (typical_price * frame["volume"]).rolling(period, min_periods=1).sum()
    vv = volume.rolling(period, min_periods=1).sum()
    return (pv / vv).fillna(frame["close"])


def fibonacci_levels(frame: pd.DataFrame, lookback: int = 120) -> dict[str, float]:
    recent = frame.tail(lookback)
    if recent.empty:
        return {"38.2": 0.0, "50.0": 0.0, "61.8": 0.0}
    high = float(recent["high"].max())
    low = float(recent["low"].min())
    diff = high - low
    return {
        "38.2": round(high - diff * 0.382, 2),
        "50.0": round(high - diff * 0.5, 2),
        "61.8": round(high - diff * 0.618, 2),
    }


def support_resistance(frame: pd.DataFrame, lookback: int = 90) -> tuple[float, float]:
    recent = frame.tail(lookback)
    if recent.empty:
        return 0.0, 0.0
    closes = recent["close"]
    support = float(closes.quantile(0.2))
    resistance = float(closes.quantile(0.8))
    return round(support, 2), round(resistance, 2)


def _local_extrema(series: pd.Series) -> tuple[list[int], list[int]]:
    values = series.to_numpy()
    peaks: list[int] = []
    troughs: list[int] = []
    for idx in range(1, len(values) - 1):
        if values[idx] >= values[idx - 1] and values[idx] >= values[idx + 1]:
            peaks.append(idx)
        if values[idx] <= values[idx - 1] and values[idx] <= values[idx + 1]:
            troughs.append(idx)
    return peaks, troughs


def _is_doji(row: pd.Series) -> bool:
    candle_range = max(row["high"] - row["low"], 1e-9)
    body = abs(row["close"] - row["open"])
    return body / candle_range <= 0.1


def _is_hammer(row: pd.Series) -> bool:
    candle_range = max(row["high"] - row["low"], 1e-9)
    body = abs(row["close"] - row["open"])
    lower_shadow = min(row["open"], row["close"]) - row["low"]
    upper_shadow = row["high"] - max(row["open"], row["close"])
    return body / candle_range <= 0.35 and lower_shadow >= body * 2 and upper_shadow <= body


def _engulfing(frame: pd.DataFrame) -> Optional[str]:
    if len(frame) < 2:
        return None
    previous = frame.iloc[-2]
    current = frame.iloc[-1]
    prev_body_low = min(previous["open"], previous["close"])
    prev_body_high = max(previous["open"], previous["close"])
    curr_body_low = min(current["open"], current["close"])
    curr_body_high = max(current["open"], current["close"])

    if current["close"] > current["open"] and previous["close"] < previous["open"]:
        if curr_body_low <= prev_body_low and curr_body_high >= prev_body_high:
            return "Bullish Engulfing"
    if current["close"] < current["open"] and previous["close"] > previous["open"]:
        if curr_body_low <= prev_body_low and curr_body_high >= prev_body_high:
            return "Bearish Engulfing"
    return None


def _morning_star(frame: pd.DataFrame) -> bool:
    if len(frame) < 3:
        return False
    a, b, c = frame.iloc[-3], frame.iloc[-2], frame.iloc[-1]
    first_bearish = a["close"] < a["open"]
    small_middle = abs(b["close"] - b["open"]) <= abs(a["close"] - a["open"]) * 0.35
    third_bullish = c["close"] > c["open"]
    recovery = c["close"] >= (a["open"] + a["close"]) / 2
    return first_bearish and small_middle and third_bullish and recovery


def _flag_pattern(series: pd.Series, bullish: bool) -> bool:
    if len(series) < 20:
        return False
    pole = series.iloc[-20:-10]
    flag = series.iloc[-10:]
    pole_return = pole.iloc[-1] / max(pole.iloc[0], 1e-9) - 1
    flag_return = flag.iloc[-1] / max(flag.iloc[0], 1e-9) - 1
    flag_volatility = flag.pct_change().std(ddof=0)
    if bullish:
        return pole_return > 0.1 and -0.05 <= flag_return <= 0.02 and flag_volatility < 0.03
    return pole_return < -0.1 and -0.02 <= flag_return <= 0.05 and flag_volatility < 0.03


def detect_chart_patterns(frame: pd.DataFrame) -> list[dict[str, Any]]:
    recent = prepare_price_frame(frame).tail(80)
    if len(recent) < 5:
        return []

    patterns: list[dict[str, Any]] = []
    latest = recent.iloc[-1]
    peaks, troughs = _local_extrema(recent["close"])

    if _is_doji(latest):
        patterns.append(
            {
                "name": "Doji",
                "sentiment": "NEUTRAL",
                "strength": 45.0,
                "explanation": "Indecision candle detected near the latest close.",
            }
        )

    if _is_hammer(latest):
        patterns.append(
            {
                "name": "Hammer",
                "sentiment": "BULLISH",
                "strength": 70.0,
                "explanation": "Lower shadow absorption suggests buyers defended lower levels.",
            }
        )

    engulfing = _engulfing(recent)
    if engulfing is not None:
        bullish = "Bullish" in engulfing
        patterns.append(
            {
                "name": engulfing,
                "sentiment": "BULLISH" if bullish else "BEARISH",
                "strength": 75.0,
                "explanation": "Two-candle reversal with a full body engulfing the prior day.",
            }
        )

    if _morning_star(recent):
        patterns.append(
            {
                "name": "Morning Star",
                "sentiment": "BULLISH",
                "strength": 80.0,
                "explanation": "Three-candle reversal structure with strong recovery into the prior body.",
            }
        )

    closes = recent["close"].reset_index(drop=True)
    if len(peaks) >= 2:
        p1, p2 = peaks[-2], peaks[-1]
        peak_1 = closes.iloc[p1]
        peak_2 = closes.iloc[p2]
        valley = float(closes.iloc[p1:p2 + 1].min())
        if abs(peak_1 - peak_2) / max(peak_1, 1e-9) <= 0.03 and valley < min(peak_1, peak_2) * 0.95:
            patterns.append(
                {
                    "name": "Double Top",
                    "sentiment": "BEARISH",
                    "strength": 72.0,
                    "explanation": "Two similar peaks formed with a meaningful rejection between them.",
                }
            )

    if len(troughs) >= 2:
        t1, t2 = troughs[-2], troughs[-1]
        trough_1 = closes.iloc[t1]
        trough_2 = closes.iloc[t2]
        crest = float(closes.iloc[t1:t2 + 1].max())
        if abs(trough_1 - trough_2) / max(trough_1, 1e-9) <= 0.03 and crest > max(trough_1, trough_2) * 1.05:
            patterns.append(
                {
                    "name": "Double Bottom",
                    "sentiment": "BULLISH",
                    "strength": 74.0,
                    "explanation": "Repeated support test held and price rebounded between the two lows.",
                }
            )

    if len(peaks) >= 3:
        p1, p2, p3 = peaks[-3], peaks[-2], peaks[-1]
        left, head, right = closes.iloc[p1], closes.iloc[p2], closes.iloc[p3]
        shoulder_similarity = abs(left - right) / max(left, 1e-9) <= 0.05
        head_clear = head > left * 1.04 and head > right * 1.04
        if shoulder_similarity and head_clear:
            patterns.append(
                {
                    "name": "Head and Shoulders",
                    "sentiment": "BEARISH",
                    "strength": 78.0,
                    "explanation": "A three-peak topping structure is visible with a prominent central head.",
                }
            )

    rolling_peak = closes.rolling(15, min_periods=5).max()
    rolling_trough = closes.rolling(15, min_periods=5).min()
    if len(closes) >= 40:
        left_peak = float(closes.iloc[:15].max())
        cup_low = float(closes.iloc[15:30].min())
        right_peak = float(closes.iloc[30:].max())
        last_pullback = float(closes.iloc[-10:].min())
        if (
            abs(left_peak - right_peak) / max(left_peak, 1e-9) <= 0.08
            and cup_low <= left_peak * 0.88
            and last_pullback >= right_peak * 0.92
        ):
            patterns.append(
                {
                    "name": "Cup and Handle",
                    "sentiment": "BULLISH",
                    "strength": 76.0,
                    "explanation": "Rounded base with a shallow handle suggests accumulation before breakout.",
                }
            )

    if _flag_pattern(closes, bullish=True):
        patterns.append(
            {
                "name": "Bull Flag",
                "sentiment": "BULLISH",
                "strength": 69.0,
                "explanation": "Sharp impulse followed by controlled consolidation keeps the uptrend intact.",
            }
        )

    if _flag_pattern(closes, bullish=False):
        patterns.append(
            {
                "name": "Bear Flag",
                "sentiment": "BEARISH",
                "strength": 69.0,
                "explanation": "Downward impulse followed by weak bounce suggests continuation pressure.",
            }
        )

    return patterns


@dataclass
class TechnicalSnapshot:
    technical_score: float
    rsi_14: float
    macd_histogram: float
    bollinger_position: float
    adx: float
    ema_9: float
    ema_21: float
    ema_50: float
    ema_200: float
    stochastic_k: float
    stochastic_d: float
    obv_slope: float
    vwap_gap_percent: float
    support: float
    resistance: float
    fibonacci_38_2: float
    fibonacci_50: float
    fibonacci_61_8: float
    ichimoku_bias: str
    detected_patterns: list[str]


def build_technical_snapshot(frame: pd.DataFrame) -> TechnicalSnapshot:
    prepared = prepare_price_frame(frame)
    if prepared.empty:
        return TechnicalSnapshot(
            technical_score=50.0,
            rsi_14=50.0,
            macd_histogram=0.0,
            bollinger_position=0.5,
            adx=20.0,
            ema_9=0.0,
            ema_21=0.0,
            ema_50=0.0,
            ema_200=0.0,
            stochastic_k=50.0,
            stochastic_d=50.0,
            obv_slope=0.0,
            vwap_gap_percent=0.0,
            support=0.0,
            resistance=0.0,
            fibonacci_38_2=0.0,
            fibonacci_50=0.0,
            fibonacci_61_8=0.0,
            ichimoku_bias="NEUTRAL",
            detected_patterns=[],
        )

    close = prepared["close"]
    ema_9 = float(ema(close, 9).iloc[-1])
    ema_21 = float(ema(close, 21).iloc[-1])
    ema_50 = float(ema(close, 50).iloc[-1])
    ema_200 = float(ema(close, 200).iloc[-1])
    rsi_14 = float(rsi(close, 14).iloc[-1])
    macd_frame = macd(close)
    bb = bollinger_bands(close)
    stochastic = stochastic_oscillator(prepared)
    adx_value = float(adx(prepared).iloc[-1])
    obv_series = obv(prepared)
    obv_slope = float(obv_series.diff(5).iloc[-1]) if len(obv_series) > 5 else 0.0
    vwap_series = vwap(prepared)
    latest_close = float(close.iloc[-1])
    vwap_gap_percent = ((latest_close / max(float(vwap_series.iloc[-1]), 1e-9)) - 1) * 100
    fib = fibonacci_levels(prepared)
    support, resistance = support_resistance(prepared)
    cloud = ichimoku(prepared)
    span_a = float(cloud["senkou_span_a"].iloc[-1]) if not pd.isna(cloud["senkou_span_a"].iloc[-1]) else latest_close
    span_b = float(cloud["senkou_span_b"].iloc[-1]) if not pd.isna(cloud["senkou_span_b"].iloc[-1]) else latest_close
    if latest_close > max(span_a, span_b):
        ichimoku_bias = "BULLISH"
    elif latest_close < min(span_a, span_b):
        ichimoku_bias = "BEARISH"
    else:
        ichimoku_bias = "NEUTRAL"

    patterns = detect_chart_patterns(prepared)
    bullish_pattern_strength = sum(item["strength"] for item in patterns if item["sentiment"] == "BULLISH")
    bearish_pattern_strength = sum(item["strength"] for item in patterns if item["sentiment"] == "BEARISH")

    trend_score = 50.0
    trend_score += 8 if ema_9 > ema_21 else -8
    trend_score += 8 if ema_21 > ema_50 else -8
    trend_score += 8 if ema_50 > ema_200 else -8
    trend_score += 10 if latest_close > ema_200 else -10
    trend_score += np.clip((rsi_14 - 50) * 0.5, -15, 15)
    trend_score += np.clip(macd_frame["macd_histogram"].iloc[-1] * 40, -10, 10)
    trend_score += np.clip((adx_value - 20) * 0.6, 0, 12)
    trend_score += np.clip((bullish_pattern_strength - bearish_pattern_strength) * 0.08, -12, 12)
    trend_score += 6 if ichimoku_bias == "BULLISH" else (-6 if ichimoku_bias == "BEARISH" else 0)
    technical_score = float(np.clip(trend_score, 0, 100))

    return TechnicalSnapshot(
        technical_score=round(technical_score, 2),
        rsi_14=round(rsi_14, 2),
        macd_histogram=round(float(macd_frame["macd_histogram"].iloc[-1]), 4),
        bollinger_position=round(float(bb["bb_position"].iloc[-1]), 4),
        adx=round(adx_value, 2),
        ema_9=round(ema_9, 2),
        ema_21=round(ema_21, 2),
        ema_50=round(ema_50, 2),
        ema_200=round(ema_200, 2),
        stochastic_k=round(float(stochastic["stoch_k"].iloc[-1]), 2),
        stochastic_d=round(float(stochastic["stoch_d"].iloc[-1]), 2),
        obv_slope=round(obv_slope, 2),
        vwap_gap_percent=round(vwap_gap_percent, 2),
        support=support,
        resistance=resistance,
        fibonacci_38_2=fib["38.2"],
        fibonacci_50=fib["50.0"],
        fibonacci_61_8=fib["61.8"],
        ichimoku_bias=ichimoku_bias,
        detected_patterns=[item["name"] for item in patterns],
    )
