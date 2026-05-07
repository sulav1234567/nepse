"""
NEPSE main index candlestick and ML regime analysis.

ML Ensemble: RandomForestClassifier + GradientBoostingClassifier
Features: 18 technical indicators (RSI-7/14, MACD, BB%B, ATR%, EMA slopes, vol_ratio, swings...)
"""

from __future__ import annotations

from typing import Any

import numpy as np

from .engine import detect_candlestick_patterns
from .models import HistoricalPrice


# ─────────────────────────────────────────────────────────────────────────────
# MATH HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return round(float(max(low, min(high, value))), 2)


def _ema_series(prices: list[float], period: int) -> list[float]:
    if not prices:
        return []
    result = []
    k = 2.0 / (period + 1)
    ema = float(prices[0])
    for p in prices:
        ema = p * k + ema * (1 - k)
        result.append(ema)
    return result


def _ema(prices: list[float], period: int) -> float:
    series = _ema_series(prices, period)
    return round(series[-1], 2) if series else 0.0


def _rsi(prices: list[float], period: int = 14) -> float:
    if len(prices) < period + 1:
        return 50.0
    gains, losses = [], []
    for left, right in zip(prices[-(period + 1):-1], prices[-period:]):
        d = right - left
        gains.append(max(d, 0.0))
        losses.append(abs(min(d, 0.0)))
    avg_gain = float(np.mean(gains)) if gains else 0.0
    avg_loss = float(np.mean(losses)) if losses else 0.0
    if avg_loss == 0:
        return 100.0
    return round(100 - 100 / (1 + avg_gain / avg_loss), 2)


def _atr(candles: list[dict[str, Any]], period: int = 14) -> float:
    if len(candles) < 2:
        return 0.0
    trs = []
    for i in range(1, len(candles)):
        h = float(candles[i].get("high", 0))
        l = float(candles[i].get("low", 0))
        prev_c = float(candles[i - 1].get("close", 0))
        trs.append(max(h - l, abs(h - prev_c), abs(l - prev_c)))
    window = trs[-period:] if len(trs) >= period else trs
    return float(np.mean(window))


def _bollinger(prices: list[float], period: int = 20, std_dev: float = 2.0) -> tuple[float, float, float]:
    """Returns (upper, middle, lower)."""
    if len(prices) < period:
        p = prices[-1] if prices else 0.0
        return p, p, p
    window = prices[-period:]
    mid = float(np.mean(window))
    std = float(np.std(window))
    return mid + std_dev * std, mid, mid - std_dev * std


def _support_resistance(candles: list[dict[str, Any]]) -> tuple[float, float]:
    if not candles:
        return 0.0, 0.0
    window = candles[-20:] if len(candles) >= 20 else candles
    support = min(float(c.get("low", 0.0)) for c in window)
    resistance = max(float(c.get("high", 0.0)) for c in window)
    return round(support, 2), round(resistance, 2)


# ─────────────────────────────────────────────────────────────────────────────
# FEATURE ENGINEERING — 18 TECHNICAL FEATURES PER CANDLE
# ─────────────────────────────────────────────────────────────────────────────

def _build_feature_vector(candles: list[dict[str, Any]], idx: int) -> list[float]:
    """Build 18-feature vector for candle at `idx`."""
    window = candles[: idx + 1]
    closes = [float(c.get("close", 0)) for c in window]
    highs  = [float(c.get("high",  0)) for c in window]
    lows   = [float(c.get("low",   0)) for c in window]
    opens  = [float(c.get("open",  0)) for c in window]
    turns  = [float(c.get("turnover", 0)) for c in window]

    close = closes[-1]
    if close == 0:
        return [0.0] * 18

    # RSI
    rsi14 = _rsi(closes, 14)
    rsi7  = _rsi(closes, 7)

    # EMA
    ema9_s  = _ema_series(closes, 9)
    ema21_s = _ema_series(closes, 21)
    ema9  = ema9_s[-1]  if ema9_s  else close
    ema21 = ema21_s[-1] if ema21_s else close
    ema9_slope  = (ema9_s[-1]  - ema9_s[-4]) / max(abs(ema9_s[-4]),  1) if len(ema9_s)  >= 4 else 0.0
    ema21_slope = (ema21_s[-1] - ema21_s[-4]) / max(abs(ema21_s[-4]), 1) if len(ema21_s) >= 4 else 0.0
    ema_cross = (ema9 - ema21) / max(abs(ema21), 1)

    # MACD
    ema12 = _ema(closes, 12)
    ema26 = _ema(closes, 26)
    macd  = ema12 - ema26
    macd_series = _ema_series([ema12 - ema26], 9)
    macd_signal = macd_series[-1] if macd_series else 0.0
    macd_hist   = macd - macd_signal

    # Bollinger Bands
    bb_up, bb_mid, bb_lo = _bollinger(closes, 20)
    bb_width = (bb_up - bb_lo) / max(abs(bb_mid), 1)
    bb_pct   = (close - bb_lo) / max(abs(bb_up - bb_lo), 1e-6)

    # ATR %
    atr_raw = _atr(window, 14)
    atr_pct = atr_raw / max(close, 1)

    # Volume ratio (turnover vs 10-day avg)
    avg_turn10 = float(np.mean(turns[-10:])) if len(turns) >= 2 else (turns[-1] if turns else 1.0)
    vol_ratio  = turns[-1] / max(avg_turn10, 1.0)

    # Price swings
    swing3  = (close - closes[-4]) / max(abs(closes[-4]), 1) if len(closes) >= 4 else 0.0
    swing10 = (close - closes[-11]) / max(abs(closes[-11]), 1) if len(closes) >= 11 else 0.0
    price_vs_ema21 = (close - ema21) / max(abs(ema21), 1)

    # Candle body metrics
    c_range = max(highs[-1] - lows[-1], 1e-6)
    body    = abs(opens[-1] - close) / c_range
    hl_ratio = c_range / close

    return [
        rsi14, rsi7,
        ema9_slope * 100, ema21_slope * 100, ema_cross * 100,
        macd / max(close, 1) * 1000, macd_signal / max(close, 1) * 1000, macd_hist / max(close, 1) * 1000,
        bb_pct, bb_width * 100,
        atr_pct * 100,
        vol_ratio,
        swing3 * 100, swing10 * 100,
        price_vs_ema21 * 100,
        hl_ratio * 100, body * 100,
        1.0 if ema9 > ema21 else -1.0,
    ]


# ─────────────────────────────────────────────────────────────────────────────
# ML ENSEMBLE TRAINER + PREDICTOR
# ─────────────────────────────────────────────────────────────────────────────

def _train_and_predict(candles: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Self-supervised ML ensemble on the incoming candle series.
    Labels: 5-day forward return > +1% = BULLISH (2), < -1% = BEARISH (0), else SIDEWAYS (1)
    Models: RandomForest (55%) + GradientBoosting (45%)
    Returns: dict with probabilities and meta stats
    """
    try:
        from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier  # type: ignore
        from sklearn.preprocessing import StandardScaler  # type: ignore
    except ImportError:
        return {}  # fall back to heuristic

    MIN_SAMPLES = 15
    FORWARD_DAYS = 5
    BULL_THRESH  =  1.0  # %
    BEAR_THRESH  = -1.0  # %

    n = len(candles)
    if n < MIN_SAMPLES + FORWARD_DAYS:
        return {}

    closes = [float(c.get("close", 0)) for c in candles]
    X: list[list[float]] = []
    y: list[int] = []

    for i in range(MIN_SAMPLES - 1, n - FORWARD_DAYS):
        feat = _build_feature_vector(candles, i)
        fwd_ret = (closes[i + FORWARD_DAYS] - closes[i]) / max(closes[i], 1) * 100
        if fwd_ret > BULL_THRESH:
            label = 2  # BULLISH
        elif fwd_ret < BEAR_THRESH:
            label = 0  # BEARISH
        else:
            label = 1  # SIDEWAYS
        X.append(feat)
        y.append(label)

    if len(X) < 8 or len(set(y)) < 2:
        return {}

    X_arr = np.array(X, dtype=np.float32)
    y_arr = np.array(y, dtype=np.int32)

    # Replace NaN/Inf
    X_arr = np.nan_to_num(X_arr, nan=0.0, posinf=10.0, neginf=-10.0)

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X_arr)

    rf = RandomForestClassifier(n_estimators=120, max_depth=6, random_state=42, n_jobs=-1)
    gb = GradientBoostingClassifier(n_estimators=80, learning_rate=0.08, max_depth=4, random_state=42)
    rf.fit(X_scaled, y_arr)
    gb.fit(X_scaled, y_arr)

    # Predict on most recent full feature vector
    x_latest = np.array([_build_feature_vector(candles, n - 1)], dtype=np.float32)
    x_latest = np.nan_to_num(x_latest, nan=0.0, posinf=10.0, neginf=-10.0)
    x_latest_scaled = scaler.transform(x_latest)

    rf_probs = rf.predict_proba(x_latest_scaled)[0]
    gb_probs = gb.predict_proba(x_latest_scaled)[0]

    # Align classes [BEARISH=0, SIDEWAYS=1, BULLISH=2]
    classes = list(rf.classes_)
    def _prob(probs: np.ndarray, label: int) -> float:
        idx = classes.index(label) if label in classes else -1
        return float(probs[idx]) if idx >= 0 else 0.0

    w_rf, w_gb = 0.55, 0.45
    p_bull = _prob(rf_probs, 2) * w_rf + _prob(gb_probs, 2) * w_gb
    p_bear = _prob(rf_probs, 0) * w_rf + _prob(gb_probs, 0) * w_gb
    p_side = _prob(rf_probs, 1) * w_rf + _prob(gb_probs, 1) * w_gb

    # Normalise
    total = p_bull + p_bear + p_side + 1e-9
    p_bull /= total
    p_bear /= total

    # Feature importances for transparency
    feat_names = ["rsi14","rsi7","ema9_slope","ema21_slope","ema_cross","macd","macd_sig","macd_hist",
                  "bb_pct","bb_width","atr_pct","vol_ratio","swing3","swing10","ema21_gap","hl_ratio","body","ema_dir"]
    importances = dict(zip(feat_names, rf.feature_importances_.tolist()))
    top_feature = max(importances, key=importances.__getitem__)

    latest_feat = _build_feature_vector(candles, n - 1)
    feat_dict = dict(zip(feat_names, latest_feat))

    return {
        "rise_probability": round(p_bull * 100, 1),
        "crash_probability": round(p_bear * 100, 1),
        "trend_strength": round(max(p_bull, p_bear) * 100, 1),
        "macd": round(feat_dict.get("macd", 0), 3),
        "macd_signal": round(feat_dict.get("macd_sig", 0), 3),
        "macd_hist": round(feat_dict.get("macd_hist", 0), 3),
        "bb_pct": round(_clamp(feat_dict.get("bb_pct", 50), 0, 100), 1),
        "bb_width": round(feat_dict.get("bb_width", 0), 3),
        "atr_pct": round(feat_dict.get("atr_pct", 0), 3),
        "vol_ratio": round(feat_dict.get("vol_ratio", 1), 2),
        "top_feature": top_feature,
        "model_samples": len(X),
    }


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC ANALYSIS FUNCTION
# ─────────────────────────────────────────────────────────────────────────────

def analyze_nepse_index(
    candles: list[dict[str, Any]],
    market_intelligence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Full ML + technical analysis of the NEPSE main index.
    Falls back to heuristic scoring when < 20 candles are available.
    """
    intelligence = market_intelligence or {}
    if not candles:
        return {
            "bias": "UNKNOWN",
            "summary": "No live NEPSE index candles were available.",
            "patterns": [],
            "warnings": [],
            "signals": {},
        }

    closes = [float(c.get("close", 0.0)) for c in candles]
    highs  = [float(c.get("high",  0.0)) for c in candles]
    lows   = [float(c.get("low",   0.0)) for c in candles]
    latest = candles[-1]
    prev_close = closes[-2] if len(closes) > 1 else closes[-1]

    ema9  = _ema(closes, 9)
    ema21 = _ema(closes, 21)
    ema55 = _ema(closes, 55)
    rsi14 = _rsi(closes, 14)
    support, resistance = _support_resistance(candles)

    day_change_percent  = round(((closes[-1] - prev_close) / max(prev_close, 1.0)) * 100, 2)
    swing_5d  = round(((closes[-1] - closes[-5]) / max(closes[-5], 1.0)) * 100, 2)  if len(closes) >= 5  else day_change_percent
    swing_20d = round(((closes[-1] - closes[-20]) / max(closes[-20], 1.0)) * 100, 2) if len(closes) >= 20 else swing_5d
    volatility = float(np.std(np.diff(closes[-15:]))) if len(closes) >= 15 else float(np.std(np.diff(closes))) if len(closes) >= 2 else 0.0

    # Bollinger (%B)
    bb_up, bb_mid, bb_lo = _bollinger(closes, 20)
    bb_pct = _clamp((closes[-1] - bb_lo) / max(bb_up - bb_lo, 1e-6) * 100, 0, 100)
    bb_width = round((bb_up - bb_lo) / max(bb_mid, 1.0) * 100, 2)

    # MACD
    ema12 = _ema(closes, 12)
    ema26 = _ema(closes, 26)
    macd_raw = ema12 - ema26
    atr_raw = _atr(candles, 14)
    atr_pct = round(atr_raw / max(closes[-1], 1.0) * 100, 2)

    # ATR-based dynamic support / resistance
    atr5 = _atr(candles, 5)
    dynamic_support    = round(closes[-1] - 1.5 * atr5, 2)
    dynamic_resistance = round(closes[-1] + 1.5 * atr5, 2)
    eff_support    = round(max(support,    dynamic_support),    2)
    eff_resistance = round(min(resistance, dynamic_resistance), 2)

    # Candlestick pattern detection
    pattern_models = detect_candlestick_patterns([
        HistoricalPrice(
            date=str(c.get("date", "")),
            open=float(c.get("open", 0.0)),
            high=float(c.get("high", 0.0)),
            low=float(c.get("low", 0.0)),
            close=float(c.get("close", 0.0)),
            volume=int(float(c.get("turnover", 0.0)) or 0),
        )
        for c in candles[-8:]
    ])
    patterns = [p.model_dump() for p in pattern_models]
    bullish_pat = sum(p["strength"] for p in patterns if p["sentiment"] == "BULLISH")
    bearish_pat = sum(p["strength"] for p in patterns if p["sentiment"] == "BEARISH")
    candle_bias = bullish_pat - bearish_pat
    market_crash_risk = float(intelligence.get("crash_risk", 0.0))

    # ── ML Ensemble ──────────────────────────────────────────────────────────
    ml_result = _train_and_predict(candles)
    ml_available = bool(ml_result)

    if ml_available:
        rise_probability  = _clamp(ml_result["rise_probability"])
        crash_probability = _clamp(ml_result["crash_probability"])
        trend_strength    = _clamp(ml_result["trend_strength"])
        macd_val   = ml_result.get("macd", macd_raw)
        bb_pct_out = ml_result.get("bb_pct", bb_pct)
        atr_pct_out = ml_result.get("atr_pct", atr_pct)
        vol_ratio  = ml_result.get("vol_ratio", 1.0)
        model_note = f"ML ensemble ({ml_result.get('model_samples', 0)} samples, top: {ml_result.get('top_feature','')})"
    else:
        # Heuristic fallback (< 20 candles or sklearn missing)
        trend_edge = (
            day_change_percent * 9 + swing_5d * 2.2 + swing_20d * 0.9
            + (10 if ema9 > ema21 else -10)
            + (8 if closes[-1] > ema21 else -8)
            + candle_bias * 0.12 - max(0.0, rsi14 - 74) * 1.1
            - market_crash_risk * 0.12
        )
        downside_edge = (
            max(0.0, -day_change_percent) * 12 + max(0.0, -swing_5d) * 4.2
            + max(0.0, -swing_20d) * 1.6 + (12 if ema9 < ema21 else 0)
            + (8 if closes[-1] < ema21 else 0)
            + max(0.0, bearish_pat - bullish_pat) * 0.18
            + max(0.0, market_crash_risk - 28) * 0.85
            + max(0.0, volatility - 28) * 0.9
        )
        rise_probability  = _clamp(50 + trend_edge, 1, 99)
        crash_probability = _clamp(18 + downside_edge + max(0.0, rsi14 - 79) * 0.8 - max(0.0, trend_edge) * 0.45, 1, 99)
        trend_strength    = _clamp(abs(rise_probability - 50) * 2)
        macd_val, bb_pct_out, atr_pct_out, vol_ratio = macd_raw, bb_pct, atr_pct, 1.0
        model_note = "heuristic (insufficient candles for ML)"

    # ── Bias Determination ───────────────────────────────────────────────────
    if crash_probability >= 60 and rise_probability <= 50:
        bias = "BEARISH"
        summary = (f"The ML ensemble flags elevated downside risk ({crash_probability:.0f}% crash probability). "
                   f"EMA alignment and momentum pattern support a defensive stance. "
                   f"Capital preservation should dominate until support at {eff_support:,.0f} proves itself. "
                   f"BB%B={bb_pct_out:.0f}%, ATR={atr_pct_out:.1f}% — {model_note}.")
    elif rise_probability >= 62 and crash_probability <= 45:
        bias = "BULLISH"
        summary = (f"The ML ensemble gives {rise_probability:.0f}% rise probability — bullish signal. "
                   f"EMA stack is {'aligned' if ema9 > ema21 > ema55 else 'partially aligned'}, "
                   f"RSI={rsi14:.1f}, BB%B={bb_pct_out:.0f}%, vol_ratio={vol_ratio:.2f}x. "
                   f"Support at {eff_support:,.0f}, resistance at {eff_resistance:,.0f}. {model_note}.")
    elif max(rise_probability, crash_probability) < 58:
        bias = "SIDEWAYS"
        summary = (f"Neither bull nor bear has conviction — ML gives {rise_probability:.0f}% rise / "
                   f"{crash_probability:.0f}% crash. BB width={bb_width:.1f}% (compression). "
                   f"Wait for a break above {eff_resistance:,.0f} or below {eff_support:,.0f}. {model_note}.")
    else:
        bias = "HIGH VOLATILITY"
        summary = (f"Strong conflicting signals — ML rise={rise_probability:.0f}%, crash={crash_probability:.0f}%. "
                   f"ATR={atr_pct_out:.1f}% signals elevated range. Tighten stops, reduce size. {model_note}.")

    # ── Warnings ─────────────────────────────────────────────────────────────
    warnings: list[dict[str, str]] = []
    if crash_probability >= 60:
        warnings.append({
            "title": "Elevated Crash Risk (ML)",
            "message": f"The ensemble gives {crash_probability:.0f}% probability of a significant drop. Monitor below {eff_support:,.0f}.",
        })
    if closes[-1] < eff_support * 1.015:
        warnings.append({
            "title": "Support Test",
            "message": f"NEPSE is within 1.5% of support at {eff_support:,.2f}. A confirmed breakdown would accelerate selling.",
        })
    if rsi14 > 75:
        warnings.append({
            "title": "Overbought RSI",
            "message": f"RSI-14 at {rsi14:.1f} — stretched. Continuation is possible but pullback risk is elevated.",
        })
    if rsi14 < 34:
        warnings.append({
            "title": "Oversold / Capitulation",
            "message": f"RSI-14 at {rsi14:.1f} — deeply oversold. Bounce is possible but confirms market stress.",
        })
    if bb_pct_out >= 95:
        warnings.append({
            "title": "Upper Bollinger Extreme",
            "message": f"Price is at {bb_pct_out:.0f}% of the Bollinger Band — statistically stretched upward.",
        })
    if bb_pct_out <= 5:
        warnings.append({
            "title": "Lower Bollinger Extreme",
            "message": f"Price is at {bb_pct_out:.0f}% of the Bollinger Band — statistically stretched downward; mean reversion possible.",
        })

    return {
        "bias": bias,
        "summary": summary,
        "patterns": patterns,
        "warnings": warnings,
        "signals": {
            "close": round(closes[-1], 2),
            "day_change_percent": day_change_percent,
            "swing_5d": swing_5d,
            "swing_20d": swing_20d,
            "ema9":  ema9,
            "ema21": ema21,
            "ema55": ema55,
            "rsi14": rsi14,
            "support": eff_support,
            "resistance": eff_resistance,
            "rise_probability": rise_probability,
            "crash_probability": crash_probability,
            "trend_strength": trend_strength,
            "volatility": round(volatility, 2),
            "market_crash_risk": round(market_crash_risk, 2),
            "macd": round(macd_val, 3),
            "bb_pct": round(bb_pct_out, 1),
            "bb_width": bb_width,
            "atr_pct": atr_pct_out,
            "vol_ratio": round(vol_ratio, 2),
            "latest_date": latest.get("date"),
            "ml_available": ml_available,
        },
    }
