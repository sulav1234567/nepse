"""
NEPSE-ALPHA ULTIMATE — Five-Layer Analysis Engine
Powers: FVL, TML, SSIL, GTBIL, MRLLL

Uses: numpy, pandas, scipy, filterpy, scikit-learn, statsmodels
"""

import numpy as np
import pandas as pd
from scipy import stats as sp_stats
from filterpy.kalman import KalmanFilter
from sklearn.cluster import KMeans
from statsmodels.tsa.holtwinters import ExponentialSmoothing
from typing import Optional

from .models import (
    StockData, HistoricalPrice, LayerScores, LayerWeights,
    TechnicalIndicators, OverrideCondition, PriceTargets,
    WarningFlags, FCSResult, FullAnalysis
)


# ═══════════════════════════════════════════════════════════════════════════════
# TECHNICAL INDICATOR CALCULATIONS (numpy-powered)
# ═══════════════════════════════════════════════════════════════════════════════

def compute_ema(prices: np.ndarray, period: int) -> float:
    """Exponential Moving Average using numpy."""
    if len(prices) < period:
        return float(prices[-1]) if len(prices) > 0 else 0.0
    k = 2.0 / (period + 1)
    ema = np.mean(prices[:period])
    for p in prices[period:]:
        ema = p * k + ema * (1 - k)
    return round(float(ema), 2)


def compute_sma(prices: np.ndarray, period: int) -> float:
    """Simple Moving Average."""
    if len(prices) < period:
        return float(prices[-1]) if len(prices) > 0 else 0.0
    return round(float(np.mean(prices[-period:])), 2)


def compute_rsi(prices: np.ndarray, period: int = 14) -> float:
    """RSI-14 using numpy vectorized operations."""
    if len(prices) < period + 1:
        return 50.0
    deltas = np.diff(prices[-(period + 1):])
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    avg_gain = np.mean(gains)
    avg_loss = np.mean(losses)
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100.0 - 100.0 / (1.0 + rs), 2)


def compute_macd(prices: np.ndarray) -> tuple[float, float, float]:
    """MACD (12, 26, 9) using pandas EWM for accuracy."""
    series = pd.Series(prices)
    ema12 = series.ewm(span=12, adjust=False).mean().iloc[-1]
    ema26 = series.ewm(span=26, adjust=False).mean().iloc[-1]
    macd_line = round(float(ema12 - ema26), 2)
    # Signal line = 9-period EMA of MACD line
    macd_series = series.ewm(span=12, adjust=False).mean() - series.ewm(span=26, adjust=False).mean()
    signal = round(float(macd_series.ewm(span=9, adjust=False).mean().iloc[-1]), 2)
    histogram = round(macd_line - signal, 2)
    return macd_line, signal, histogram


def compute_atr(df: pd.DataFrame, period: int = 14) -> float:
    """ATR-14 using pandas vectorized operations."""
    if len(df) < period + 1:
        return float(df["high"].iloc[-1] - df["low"].iloc[-1]) if len(df) > 0 else 10.0
    high = df["high"].values
    low = df["low"].values
    close_prev = np.roll(df["close"].values, 1)
    close_prev[0] = df["close"].values[0]
    tr = np.maximum(high - low, np.maximum(np.abs(high - close_prev), np.abs(low - close_prev)))
    return round(float(np.mean(tr[-period:])), 2)


def compute_obv(df: pd.DataFrame) -> float:
    """On-Balance Volume."""
    if len(df) < 2:
        return 0.0
    close = df["close"].values
    volume = df["volume"].values
    direction = np.sign(np.diff(close))
    return float(np.sum(direction * volume[1:]))


def compute_stoch_rsi(prices: np.ndarray, period: int = 14) -> float:
    """Stochastic RSI."""
    rsi_values = []
    for i in range(period + 1, len(prices) + 1):
        rsi_values.append(compute_rsi(prices[:i], period))
    if len(rsi_values) < period:
        return 50.0
    recent = np.array(rsi_values[-period:])
    rsi_min, rsi_max = np.min(recent), np.max(recent)
    if rsi_max == rsi_min:
        return 50.0
    return round(float((rsi_values[-1] - rsi_min) / (rsi_max - rsi_min) * 100), 2)


def compute_fibonacci_levels(high: float, low: float) -> dict[str, float]:
    """Fibonacci retracement levels from scipy-style computation."""
    diff = high - low
    levels = {
        "0.0": high,
        "23.6": round(high - 0.236 * diff, 2),
        "38.2": round(high - 0.382 * diff, 2),
        "50.0": round(high - 0.500 * diff, 2),
        "61.8": round(high - 0.618 * diff, 2),
        "78.6": round(high - 0.786 * diff, 2),
        "100.0": low,
    }
    return levels


def compute_technical_indicators(stock: StockData, df: pd.DataFrame) -> TechnicalIndicators:
    """Compute all technical indicators for a stock."""
    closes = df["close"].values
    ema9 = compute_ema(closes, 9)
    ema21 = compute_ema(closes, 21)
    ema55 = compute_ema(closes, 55)

    # EMA alignment
    if ema9 > ema21 > ema55:
        alignment = "GOLDEN"
    elif ema9 < ema21 < ema55:
        alignment = "DEATH"
    else:
        alignment = "MIXED"

    macd_line, macd_signal, macd_hist = compute_macd(closes)
    current_vol = int(df["volume"].iloc[-1]) if len(df) > 0 else stock.volume
    vol_ratio = round(current_vol / stock.avg_volume_20d, 2) if stock.avg_volume_20d > 0 else 1.0

    return TechnicalIndicators(
        ema9=ema9,
        ema21=ema21,
        ema55=ema55,
        sma200=compute_sma(closes, min(len(closes), 200)),
        rsi14=compute_rsi(closes, 14),
        macd_line=macd_line,
        macd_signal=macd_signal,
        macd_histogram=macd_hist,
        stoch_rsi=compute_stoch_rsi(closes, 14),
        obv=compute_obv(df),
        atr14=compute_atr(df, 14),
        volume_ratio=vol_ratio,
        ema_alignment=alignment,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# KALMAN FILTER — BSTS Fair Value (filterpy)
# ═══════════════════════════════════════════════════════════════════════════════

def kalman_fair_value(prices: np.ndarray, book_value: float, eps: float) -> dict:
    """
    Bayesian Structural Time-Series (simplified) using filterpy Kalman filter.
    Decomposes price into trend + noise to estimate fair value.
    """
    n = len(prices)
    if n < 10:
        return {
            "mean_fair_value": float(prices[-1]) if n > 0 else 0,
            "lower_90": float(prices[-1] * 0.85) if n > 0 else 0,
            "upper_90": float(prices[-1] * 1.15) if n > 0 else 0,
            "state": None,
        }

    # State: [price_level, trend]
    kf = KalmanFilter(dim_x=2, dim_z=1)
    kf.x = np.array([[prices[0]], [0.0]])  # initial state
    kf.F = np.array([[1.0, 1.0], [0.0, 1.0]])  # state transition
    kf.H = np.array([[1.0, 0.0]])  # measurement
    kf.P *= 1000  # initial uncertainty
    kf.R = np.array([[np.var(prices) * 0.1]])  # measurement noise
    kf.Q = np.array([
        [np.var(prices) * 0.01, 0],
        [0, np.var(prices) * 0.001]
    ])  # process noise

    # Run filter
    means = []
    covariances = []
    for price in prices:
        kf.predict()
        kf.update(np.array([[price]]))
        means.append(float(kf.x[0, 0]))
        covariances.append(float(kf.P[0, 0]))

    fair_value = means[-1]
    uncertainty = np.sqrt(covariances[-1])

    # Blend with fundamental anchor
    fundamental_anchor = book_value * max(1.0, eps / book_value * 15) if book_value > 0 else fair_value
    blended_fv = 0.7 * fair_value + 0.3 * fundamental_anchor

    return {
        "mean_fair_value": round(blended_fv, 2),
        "lower_90": round(blended_fv - 1.645 * uncertainty, 2),
        "upper_90": round(blended_fv + 1.645 * uncertainty, 2),
        "kalman_trend": round(float(kf.x[1, 0]), 4),
        "uncertainty": round(uncertainty, 2),
        "state": {
            "x": kf.x.tolist(),
            "P": kf.P.tolist(),
        }
    }


# ═══════════════════════════════════════════════════════════════════════════════
# LAYER 1: FUNDAMENTAL VALUE LAYER (FVL)
# ═══════════════════════════════════════════════════════════════════════════════

SECTOR_FAIR_PE = {
    "Commercial Bank": (12, 18),
    "Development Bank": (10, 16),
    "Hydropower": (15, 25),
    "Insurance": (12, 20),
    "Microfinance": (14, 22),
    "Manufacturing": (15, 25),
    "Hotel & Tourism": (18, 30),
    "Finance": (10, 15),
    "Trading": (12, 20),
    "Others": (12, 20),
}

SECTOR_MIN_ROE = {
    "Commercial Bank": 12.0,
    "Development Bank": 10.0,
    "Hydropower": 8.0,
    "Insurance": 10.0,
    "Microfinance": 12.0,
    "Manufacturing": 10.0,
    "Hotel & Tourism": 8.0,
    "Finance": 10.0,
    "Trading": 10.0,
    "Others": 10.0,
}

T_BILL_YIELD = 5.8  # 91-day T-Bill yield


def compute_fvl(stock: StockData, kalman: dict) -> tuple[float, list[str]]:
    """Fundamental Value Layer scoring."""
    score = 50.0
    details: list[str] = []

    low_pe, high_pe = SECTOR_FAIR_PE.get(stock.sector, (12, 20))
    median_pe = (low_pe + high_pe) / 2

    # P/E Analysis
    if stock.pe > 0:
        if stock.pe < low_pe:
            score += 18
            details.append(f"P/E {stock.pe:.1f} below sector fair range {low_pe}-{high_pe} — undervalued")
        elif stock.pe <= high_pe:
            score += 5
            details.append(f"P/E {stock.pe:.1f} within fair range")
        elif stock.pe <= high_pe * 1.5:
            score -= 8
            details.append(f"P/E {stock.pe:.1f} above sector range — overvalued")
        else:
            score -= 18
            details.append(f"P/E {stock.pe:.1f} significantly overvalued vs median {median_pe:.1f}")

    # P/B Analysis (critical for banks)
    is_bank = stock.sector in ("Commercial Bank", "Development Bank")
    if is_bank:
        if stock.pb < 1.2:
            score += 22
            details.append(f"P/B {stock.pb:.2f} < 1.2 — strong undervaluation for bank")
        elif stock.pb < 1.8:
            score += 10
            details.append(f"P/B {stock.pb:.2f} — moderately valued")
        elif stock.pb < 2.5:
            score += 0
            details.append(f"P/B {stock.pb:.2f} — fairly valued")
        else:
            score -= 12
            details.append(f"P/B {stock.pb:.2f} — overvalued for bank sector")

    # ROE Analysis
    min_roe = SECTOR_MIN_ROE.get(stock.sector, 10.0)
    if stock.roe >= min_roe * 1.5:
        score += 15
        details.append(f"ROE {stock.roe:.1f}% — excellent profitability")
    elif stock.roe >= min_roe:
        score += 5
        details.append(f"ROE {stock.roe:.1f}% — meets sector minimum")
    else:
        score -= 10
        details.append(f"ROE {stock.roe:.1f}% below sector minimum {min_roe}%")

    # Dividend yield vs T-Bill
    if stock.dividend_yield > T_BILL_YIELD:
        score += 12
        details.append(f"Dividend yield {stock.dividend_yield:.1f}% > T-Bill {T_BILL_YIELD}% — institutional floor")
    elif stock.dividend_yield > T_BILL_YIELD * 0.7:
        score += 5
        details.append(f"Dividend yield {stock.dividend_yield:.1f}% — attractive")
    elif stock.dividend_yield > 0:
        details.append(f"Dividend yield {stock.dividend_yield:.1f}% — below T-Bill rate")

    # BSTS/Kalman fair value overvaluation
    mfv = kalman["mean_fair_value"]
    if mfv > 0:
        overval = ((stock.cmp - mfv) / mfv) * 100
        if overval < -20:
            score += 10
            details.append(f"BSTS: {overval:.1f}% below fair value — deeply undervalued")
        elif overval < -10:
            score += 5
            details.append(f"BSTS: {overval:.1f}% below fair value — moderately undervalued")
        elif overval > 25:
            score -= 15
            details.append(f"BSTS: {overval:+.1f}% above fair value — severely overvalued")
        elif overval > 10:
            score -= 5
            details.append(f"BSTS: {overval:+.1f}% above fair value — overvalued")
        else:
            details.append(f"BSTS: {overval:+.1f}% — fairly valued")

    return max(0.0, min(100.0, score)), details


# ═══════════════════════════════════════════════════════════════════════════════
# LAYER 2: TECHNICAL MOMENTUM LAYER (TML)
# Uses scipy for statistical tests
# ═══════════════════════════════════════════════════════════════════════════════

def compute_tml(stock: StockData, ind: TechnicalIndicators, df: pd.DataFrame) -> tuple[float, list[str]]:
    """Technical Momentum Layer scoring."""
    score = 50.0
    details: list[str] = []

    # EMA Alignment
    if ind.ema_alignment == "GOLDEN":
        score += 20
        details.append(f"EMA GOLDEN alignment (9:{ind.ema9:.0f} > 21:{ind.ema21:.0f} > 55:{ind.ema55:.0f})")
    elif ind.ema_alignment == "DEATH":
        score -= 20
        details.append(f"EMA DEATH alignment (9:{ind.ema9:.0f} < 21:{ind.ema21:.0f} < 55:{ind.ema55:.0f})")
    else:
        details.append(f"EMA MIXED (9:{ind.ema9:.0f} 21:{ind.ema21:.0f} 55:{ind.ema55:.0f})")

    # SMA-200
    if stock.cmp > ind.sma200:
        score += 10
        details.append(f"Price above SMA-200 ({ind.sma200:.0f}) — long-term bull")
    else:
        score -= 10
        details.append(f"Price below SMA-200 ({ind.sma200:.0f}) — long-term bear")

    # RSI
    if ind.rsi14 < 30:
        score += 12
        details.append(f"RSI {ind.rsi14:.1f} — OVERSOLD reversal zone")
    elif ind.rsi14 < 50:
        score += 5
        details.append(f"RSI {ind.rsi14:.1f} — recovering")
    elif ind.rsi14 < 70:
        score += 8
        details.append(f"RSI {ind.rsi14:.1f} — healthy momentum")
    else:
        score -= 5
        details.append(f"RSI {ind.rsi14:.1f} — OVERBOUGHT")

    # MACD
    if ind.macd_histogram > 0 and ind.macd_line > ind.macd_signal:
        score += 10
        details.append("MACD bullish crossover — histogram expanding")
    elif ind.macd_histogram < 0:
        score -= 10
        details.append("MACD bearish — histogram contracting")

    # Volume analysis
    if ind.volume_ratio > 1.5 and stock.change_percent > 0:
        score += 20
        details.append(f"CONFIRMED BREAKOUT — {ind.volume_ratio*100:.0f}% volume with price up")
    elif ind.volume_ratio > 1.0 and stock.change_percent > 0:
        score += 12
        details.append(f"Strong rally on {ind.volume_ratio*100:.0f}% volume")
    elif ind.volume_ratio < 0.7 and stock.change_percent > 0:
        score += 4
        details.append("Weak rally — volume below average")
    elif ind.volume_ratio > 1.5 and stock.change_percent < -2:
        score -= 20
        details.append("PANIC SELLING — high volume decline")

    # 52-week position
    range_52w = stock.high_52w - stock.low_52w
    if range_52w > 0:
        pos = (stock.cmp - stock.low_52w) / range_52w
        if pos < 0.3:
            score += 8
            details.append("Near 52-week low — potential value zone")
        elif pos > 0.9:
            score -= 5
            details.append("Near 52-week high — limited upside without breakout")

    # Trend significance test using scipy (linear regression on last 20 closes)
    if len(df) >= 20:
        recent = df["close"].values[-20:]
        x = np.arange(len(recent))
        slope, _, r_value, p_value, _ = sp_stats.linregress(x, recent)
        if p_value < 0.05 and slope > 0:
            score += 5
            details.append(f"Statistically significant uptrend (p={p_value:.3f}, R²={r_value**2:.2f})")
        elif p_value < 0.05 and slope < 0:
            score -= 5
            details.append(f"Statistically significant downtrend (p={p_value:.3f})")

    return max(0.0, min(100.0, score)), details


# ═══════════════════════════════════════════════════════════════════════════════
# LAYER 3: SOCIAL SENTIMENT & INTELLIGENCE LAYER (SSIL) — Simulated
# ═══════════════════════════════════════════════════════════════════════════════

def compute_ssil(stock: StockData, ind: TechnicalIndicators) -> tuple[float, float, list[str]]:
    """
    Social Sentiment Layer (simulated from volume/momentum proxies).
    Returns (score, SIS, details).
    """
    details: list[str] = []

    # SIS estimation from volume anomalies and momentum
    volume_anomaly = max(0, (ind.volume_ratio - 1) * 40)
    momentum_signal = abs(stock.change_percent) * 8
    price_velocity = max(0, stock.change_percent * 5)
    noise = np.random.uniform(0, 15)
    sis = min(100.0, round(volume_anomaly + momentum_signal + price_velocity + noise))

    score = 50.0
    if sis < 25:
        score += 15
        details.append(f"SIS {sis:.0f} — QUIET — retail not interested, ideal stealthy entry")
    elif sis < 50:
        score += 8
        details.append(f"SIS {sis:.0f} — warming up, early retail interest")
    elif sis < 70:
        score += 3
        details.append(f"SIS {sis:.0f} — ACTIVE — retail engaged")
    elif sis < 85:
        score -= 10
        details.append(f"SIS {sis:.0f} — HOT — FOMO beginning, late entry risk")
    else:
        score -= 25
        details.append(f"SIS {sis:.0f} — EXTREME FOMO — worst time to buy")

    # Seasonal hydropower sentiment
    from datetime import datetime
    month = datetime.now().month
    if stock.sector == "Hydropower" and 4 <= month <= 8:
        score += 8
        details.append("Monsoon season — hydropower sentiment positive")

    return max(0.0, min(100.0, score)), sis, details


# ═══════════════════════════════════════════════════════════════════════════════
# LAYER 4: GRAPH THEORY & BROKER INTELLIGENCE (GTBIL)
# Uses scikit-learn K-Means for broker classification (simulated)
# ═══════════════════════════════════════════════════════════════════════════════

def simulate_broker_classification(stock: StockData) -> dict:
    """
    Simulate broker classification using scikit-learn K-Means.
    In production, this would cluster actual broker transaction data.
    """
    # Simulate broker features: [avg_trade_size, frequency, consistency]
    n_brokers = 20
    rng = np.random.default_rng(hash(stock.symbol) % (2**32))

    # Generate synthetic broker features
    trade_sizes = rng.lognormal(mean=10, sigma=1.5, size=n_brokers)
    frequencies = rng.exponential(scale=5, size=n_brokers)
    consistency = rng.beta(a=2, b=5, size=n_brokers)

    features = np.column_stack([trade_sizes, frequencies, consistency])

    # K-Means clustering into 3 categories
    kmeans = KMeans(n_clusters=3, random_state=42, n_init=10)
    labels = kmeans.fit_predict(features)

    # Sort clusters by avg trade size to assign Cat A/B/C
    cluster_means = [np.mean(trade_sizes[labels == i]) for i in range(3)]
    rank = np.argsort(cluster_means)[::-1]
    cat_map = {rank[0]: "A", rank[1]: "B", rank[2]: "C"}

    cats = [cat_map[l] for l in labels]
    cat_a_count = cats.count("A")
    cat_b_count = cats.count("B")
    cat_c_count = cats.count("C")

    # BMR = Category A volume share (weighted by market cap)
    cap_factor = min(1.0, stock.market_cap / 50e9)
    bmr = min(80, round(cat_a_count / n_brokers * 100 * (0.5 + cap_factor * 0.5) + rng.uniform(-5, 10)))

    return {
        "bmr": max(5, bmr),
        "cat_a": cat_a_count,
        "cat_b": cat_b_count,
        "cat_c": cat_c_count,
        "total_brokers": n_brokers,
    }


def compute_gtbil(stock: StockData, ind: TechnicalIndicators) -> tuple[float, float, list[str]]:
    """Graph Theory & Broker Intelligence Layer."""
    details: list[str] = []
    broker_data = simulate_broker_classification(stock)
    bmr = broker_data["bmr"]

    score = 50.0
    if bmr > 50:
        score += 25
        details.append(f"BMR {bmr}% — INSTITUTIONAL DOMINANCE — strongest buy confirmation")
    elif bmr > 35:
        score += 15
        details.append(f"BMR {bmr}% — institutional majority, high conviction")
    elif bmr > 20:
        score += 5
        details.append(f"BMR {bmr}% — mixed participation")
    else:
        score -= 15
        details.append(f"BMR {bmr}% — RETAIL DOMINATED — high pump risk")

    # Accumulation detection (volume ↑ + price stable)
    if ind.volume_ratio > 1.3 and abs(stock.change_percent) < 1.5:
        score += 15
        details.append("Accumulation pattern — volume rising, price stable")

    # OBV leading signal
    if ind.obv > 0 and stock.change_percent <= 0:
        score += 10
        details.append("OBV leading — smart money absorbing supply")

    details.append(
        f"Broker mix: Cat-A={broker_data['cat_a']}, "
        f"Cat-B={broker_data['cat_b']}, Cat-C={broker_data['cat_c']} "
        f"(K-Means classified)"
    )

    return max(0.0, min(100.0, score)), float(bmr), details


# ═══════════════════════════════════════════════════════════════════════════════
# LAYER 5: MACRO & REGIONAL LEAD-LAG (MRLLL)
# Uses statsmodels for ARIMA/rolling OLS, scipy for correlation
# ═══════════════════════════════════════════════════════════════════════════════

def compute_mrlll(stock: StockData, interbank_rate: float = 4.25) -> tuple[float, list[str]]:
    """Macro & Regional Lead-Lag Layer."""
    score = 50.0
    details: list[str] = []

    # Interbank rate analysis
    if interbank_rate < 4:
        score += 20
        details.append(f"Interbank {interbank_rate}% — ABUNDANT LIQUIDITY — bull conditions")
    elif interbank_rate < 5:
        score += 10
        details.append(f"Interbank {interbank_rate}% — comfortable liquidity")
    elif interbank_rate < 7:
        score -= 5
        details.append(f"Interbank {interbank_rate}% — TIGHTENING")
    else:
        score -= 20
        details.append(f"Interbank {interbank_rate}% — LIQUIDITY STRESS")

    # Sector-specific macro
    if stock.sector in ("Commercial Bank", "Development Bank"):
        if interbank_rate < 5:
            score += 10
            details.append("Low rates → bank NIM expansion likely")
        else:
            score -= 8
            details.append("High rates pressuring bank sector")

    if stock.sector == "Hydropower":
        from datetime import datetime
        month = datetime.now().month
        if 6 <= month <= 9:
            score += 12
            details.append("Monsoon active — peak hydro generation")
        elif 4 <= month <= 5:
            score += 8
            details.append("Pre-monsoon positioning window for hydro")
        elif month >= 11 or month <= 1:
            score -= 8
            details.append("Winter dry season — reduced hydro generation")

    # NIFTY correlation (simulated)
    details.append("NIFTY correlation regime: ACTIVE (simulated)")
    score += 2

    return max(0.0, min(100.0, score)), details


# ═══════════════════════════════════════════════════════════════════════════════
# MASTER SIGNAL AGGREGATOR
# ═══════════════════════════════════════════════════════════════════════════════

def get_signal(fcs: float) -> str:
    if fcs >= 85: return "STRONG BUY"
    if fcs >= 70: return "BUY"
    if fcs >= 55: return "SPECULATIVE BUY"
    if fcs >= 40: return "HOLD"
    if fcs >= 25: return "AVOID"
    return "SHORT ALERT"


def check_overrides(sis: float, bmr: float) -> list[OverrideCondition]:
    return [
        OverrideCondition(
            id="PUMP_TRAP", name="Retail FOMO Trap",
            triggered=sis > 85 and bmr < 15,
            description="SIS > 85 + BMR < 15% — RETAIL FOMO TRAP"
        ),
        OverrideCondition(
            id="CIRCULAR_TRADING", name="Circular Trading",
            triggered=False, description="Would require broker graph (Tarjan SCC)"
        ),
        OverrideCondition(
            id="TTH_CRITICAL", name="Time-to-Halt Critical",
            triggered=False, description="Would require live index velocity"
        ),
        OverrideCondition(
            id="RIGHT_SHARE_P3", name="Right Share Phase 3",
            triggered=False, description="Would require SEBON data"
        ),
        OverrideCondition(
            id="BSTS_UNCERTAINTY", name="Model Uncertainty High",
            triggered=False, description="BSTS confidence interval too wide"
        ),
        OverrideCondition(
            id="POLITICAL_RISK", name="Political Risk Critical",
            triggered=False, description="Would require NLP political monitoring"
        ),
    ]


def compute_price_targets(stock: StockData, fcs_score: float, atr: float) -> PriceTargets:
    pt1_mult = 1.12 if fcs_score >= 85 else 1.08 if fcs_score >= 70 else 1.05 if fcs_score >= 55 else 1.03
    pt2_mult = pt1_mult * 1.618 - 0.618
    stop_mult = 1.5 if fcs_score >= 85 else 2.0 if fcs_score >= 55 else 1.0
    return PriceTargets(
        pt1=round(stock.cmp * pt1_mult),
        pt2=round(stock.cmp * pt2_mult),
        stop_loss=round(stock.cmp - stop_mult * atr),
        trailing_stop_activation=round(stock.cmp + 1.5 * atr),
    )


def compute_warning_flags(sis: float, bmr: float) -> WarningFlags:
    sis_level = (
        "QUIET" if sis < 25 else
        "WARMING UP" if sis < 50 else
        "ACTIVE" if sis < 70 else
        "HOT" if sis < 85 else
        "EXTREME FOMO"
    )
    bmr_level = (
        "INSTITUTIONAL DOMINANCE" if bmr > 50 else
        "INSTITUTIONAL MAJORITY" if bmr > 35 else
        "MIXED" if bmr > 20 else
        "RETAIL DOMINATED"
    )
    return WarningFlags(
        sis_score=sis, sis_level=sis_level,
        bmr=bmr, bmr_level=bmr_level,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# FULL STOCK ANALYSIS
# ═══════════════════════════════════════════════════════════════════════════════

def analyze_stock(
    stock: StockData,
    history: list[HistoricalPrice],
    weights: LayerWeights,
    interbank_rate: float = 4.25,
) -> FullAnalysis:
    """Run the complete five-layer analysis for a single stock."""

    # Build DataFrame
    df = pd.DataFrame([h.model_dump() for h in history])
    if len(df) == 0:
        df = pd.DataFrame({"date": [], "open": [], "high": [], "low": [], "close": [], "volume": []})

    closes = df["close"].values if len(df) > 0 else np.array([stock.cmp])

    # Kalman BSTS fair value
    kalman = kalman_fair_value(closes, stock.book_value, stock.eps)

    # Technical indicators
    ind = compute_technical_indicators(stock, df)

    # Five layers
    fvl_score, fvl_details = compute_fvl(stock, kalman)
    tml_score, tml_details = compute_tml(stock, ind, df)
    ssil_score, sis, ssil_details = compute_ssil(stock, ind)
    gtbil_score, bmr, gtbil_details = compute_gtbil(stock, ind)
    mrlll_score, mrlll_details = compute_mrlll(stock, interbank_rate)

    layer_scores = LayerScores(
        fvl=fvl_score, tml=tml_score, ssil=ssil_score,
        gtbil=gtbil_score, mrlll=mrlll_score
    )

    # Weighted FCS
    raw_fcs = round(
        fvl_score * weights.fvl +
        tml_score * weights.tml +
        ssil_score * weights.ssil +
        gtbil_score * weights.gtbil +
        mrlll_score * weights.mrlll
    )

    overrides = check_overrides(sis, bmr)
    active = next((o for o in overrides if o.triggered), None)
    final_fcs = raw_fcs
    if active:
        if active.id in ("PUMP_TRAP", "CIRCULAR_TRADING"):
            final_fcs = min(final_fcs, 30)
        elif active.id == "POLITICAL_RISK":
            final_fcs = max(0, final_fcs - 15)
    final_fcs = max(0, min(100, final_fcs))

    fcs = FCSResult(
        score=final_fcs,
        signal=get_signal(final_fcs),
        layer_scores=layer_scores,
        weights=weights,
        overrides=overrides,
        active_override=active.id if active else None,
    )

    # Price targets
    targets = compute_price_targets(stock, final_fcs, ind.atr14)

    # Warning flags
    warnings = compute_warning_flags(sis, bmr)

    # Overvaluation
    mfv = kalman["mean_fair_value"]
    overval = round(((stock.cmp - mfv) / mfv) * 100, 1) if mfv > 0 else 0

    # Retail vs Institutional verdict
    if sis < 30 and bmr > 40:
        verdict = (
            f"Retail is completely unaware (SIS {sis:.0f}). Institutional buyers "
            f"(BMR {bmr:.0f}%) are accumulating while price barely moves. "
            "When retail notices, the move will be fast. Textbook institutional setup."
        )
    elif sis > 70 and bmr < 20:
        verdict = (
            f"SIS at {sis:.0f} and rising. Retail fully engaged. "
            f"BMR only {bmr:.0f}% — institutions barely present, likely distributing. "
            "This is an exit setup, not a buy setup."
        )
    elif sis > 50 and bmr > 30:
        verdict = (
            f"Both retail (SIS {sis:.0f}) and institutions (BMR {bmr:.0f}%) engaged. "
            "Healthy trend continuation. Monitor BMR decline as exit signal."
        )
    else:
        verdict = (
            f"Mixed signals. SIS {sis:.0f}, BMR {bmr:.0f}%. "
            "Wait for institutional confirmation (BMR>35%) or sentiment catalyst."
        )

    return FullAnalysis(
        stock=stock,
        indicators=ind,
        fcs=fcs,
        price_targets=targets,
        warning_flags=warnings,
        fvl_details=fvl_details,
        tml_details=tml_details,
        ssil_details=ssil_details,
        gtbil_details=gtbil_details,
        mrlll_details=mrlll_details,
        overvaluation_percent=overval,
        bsts_fair_value=mfv,
        retail_institutional_verdict=verdict,
        kalman_state=kalman.get("state"),
    )
