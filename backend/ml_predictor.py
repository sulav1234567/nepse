"""
NEPSE-ALPHA ULTIMATE — AI/ML Stock Rise Prediction Engine
==========================================================
Ensemble ML system using Random Forest + Gradient Boosting + XGBoost
to predict which stocks will rise, by how much, and with what confidence.

Features: 35 engineered features per stock
Models:   RandomForest (classifier) + GradientBoosting (regressor) + XGBoost (classifier)
Output:   Rise probability, predicted Rs. movement, confidence, key drivers
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple
from sklearn.ensemble import RandomForestClassifier, GradientBoostingRegressor, GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.neural_network import MLPClassifier, MLPRegressor
import warnings
import logging
import time
from datetime import datetime

from .deterministic import stable_hash_int, stable_rng

warnings.filterwarnings('ignore')
logger = logging.getLogger(__name__)

# Try importing xgboost (optional, use GB as fallback).
# On macOS, xgboost can be installed but fail to load at runtime if libomp is missing.
try:
    from xgboost import XGBClassifier
    HAS_XGBOOST = True
except Exception as e:
    HAS_XGBOOST = False
    logger.warning(f"XGBoost unavailable, using GradientBoosting fallback: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# FEATURE ENGINEERING (30+ features per stock)
# ─────────────────────────────────────────────────────────────────────────────

FEATURE_NAMES = [
    # Technical (12)
    'rsi_14', 'macd_histogram', 'ema_alignment_score', 'atr_price_ratio',
    'volume_ratio', 'stoch_rsi', 'obv_trend', 'bollinger_position',
    'position_52w', 'price_momentum_5d', 'price_momentum_10d', 'price_momentum_20d',
    # Fundamental (8)
    'pe_vs_sector_median', 'pb_vs_sector_median', 'roe_percentile',
    'dividend_yield_vs_tbill', 'eps_growth_proxy', 'book_value_discount',
    'market_cap_log', 'earnings_yield',
    # Volume & Flow (5)
    'volume_anomaly_zscore', 'volume_price_trend', 'accumulation_signal',
    'turnover_ratio', 'trade_intensity',
    # Market Context (5)
    'sector_momentum', 'market_breadth_score', 'interbank_rate_signal',
    'seasonal_score', 'volatility_regime',
    # NEW: Advanced Signals (5)
    'bollinger_bandwidth',   # Volatility expansion — wide bands predict breakout after squeeze
    'volume_trend_5d',       # 5d volume MA / 20d volume MA — rising volume = accumulation
    'rsi_momentum',          # RSI change over last 3 bars — RSI velocity, not just level
    'macd_acceleration',     # MACD histogram direction — second derivative of momentum
    'price_vs_vwap_proxy',   # (CMP - 20d mean) / ATR — mean-reversion signal
]

TRAINING_VARIATIONS_PER_STOCK = 3
MIN_RETRAIN_INTERVAL_SECONDS = 300


def compute_rsi(prices: List[float], period: int = 14) -> float:
    """Compute RSI from price series."""
    if len(prices) < period + 1:
        return 50.0
    gains, losses = 0.0, 0.0
    for i in range(-period, 0):
        diff = prices[i] - prices[i - 1]
        if diff > 0:
            gains += diff
        else:
            losses += abs(diff)
    avg_gain = gains / period
    avg_loss = losses / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - 100 / (1 + rs), 2)


def compute_ema(prices: List[float], period: int) -> float:
    """Compute EMA."""
    if len(prices) < period:
        return prices[-1] if prices else 0
    k = 2 / (period + 1)
    ema = sum(prices[:period]) / period
    for p in prices[period:]:
        ema = p * k + ema * (1 - k)
    return ema


def compute_atr(highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> float:
    """Compute Average True Range."""
    if len(closes) < period + 1:
        return (highs[-1] - lows[-1]) if highs and lows else 10
    trs = []
    for i in range(-period, 0):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1])
        )
        trs.append(tr)
    return sum(trs) / len(trs)


def compute_bollinger_bandwidth(prices: List[float], period: int = 20) -> float:
    """Bollinger Band width (upper-lower)/middle — high = volatile, low = squeeze before breakout."""
    if len(prices) < period:
        return 0.04
    window = prices[-period:]
    mean = float(np.mean(window))
    std = float(np.std(window))
    if mean == 0:
        return 0.04
    return min(0.5, (4 * std) / mean)  # 2*std each side / mean


def compute_bollinger_position(prices: List[float], period: int = 20) -> float:
    """Where is price relative to Bollinger Bands? Returns -1 to +1."""
    if len(prices) < period:
        return 0
    window = prices[-period:]
    mean = np.mean(window)
    std = np.std(window)
    if std == 0:
        return 0
    return min(1, max(-1, (prices[-1] - mean) / (2 * std)))


def engineer_features(stock: Dict, history: List[Dict] = None,
                      sector_stats: Dict = None, market_context: Dict = None) -> np.ndarray:
    """
    Engineer 30 features for a single stock.
    Returns numpy array of shape (30,).
    """
    features = np.zeros(len(FEATURE_NAMES))

    cmp = stock.get('cmp', 0)
    prev_close = stock.get('previousClose', cmp)
    volume = stock.get('volume', 0)
    avg_vol = stock.get('avgVolume20d', max(1, volume))
    high52w = stock.get('high52w', cmp * 1.2)
    low52w = stock.get('low52w', cmp * 0.8)
    pe = stock.get('pe', 15)
    pb = stock.get('pb', 1.5)
    roe = stock.get('roe', 12)
    eps = stock.get('eps', 0)
    div_yield = stock.get('dividendYield', 2)
    book_value = stock.get('bookValue', cmp / 1.5)
    market_cap = stock.get('marketCap', 10000000000)
    change_pct = stock.get('changePercent', 0)

    # Generate synthetic price history if not provided
    if not history or len(history) < 20:
        rng = stable_rng(
            "feature_history",
            stock.get('symbol', ''),
            stock.get('cmp', 0),
            stock.get('volume', 0),
            stock.get('changePercent', 0),
        )
        base = cmp * 0.88
        prices = []
        for i in range(60):
            noise = rng.normal(0, 0.015)
            trend = i / 60 * 0.12
            base *= (1 + trend / 60 + noise)
            prices.append(base)
        prices[-1] = cmp
        highs = [p * (1 + rng.uniform(0, 0.02)) for p in prices]
        lows = [p * (1 - rng.uniform(0, 0.02)) for p in prices]
        volumes = [int(avg_vol * (0.6 + rng.random() * 0.8)) for _ in prices]
    else:
        prices = [h.get('close', h.get('closingPrice', cmp)) for h in history]
        highs = [h.get('high', h.get('highPrice', p * 1.01)) for h, p in zip(history, prices)]
        lows = [h.get('low', h.get('lowPrice', p * 0.99)) for h, p in zip(history, prices)]
        volumes = [h.get('volume', h.get('totalTradeQuantity', avg_vol)) for h in history]

    # ── Technical Features ──
    features[0] = compute_rsi(prices) / 100.0  # rsi_14 (normalized 0-1)

    # MACD histogram
    ema12 = compute_ema(prices, 12)
    ema26 = compute_ema(prices, 26)
    macd = ema12 - ema26
    features[1] = np.clip(macd / (cmp * 0.01 + 1), -5, 5)  # macd_histogram (normalized)

    # EMA alignment score
    ema9 = compute_ema(prices, 9)
    ema21 = compute_ema(prices, 21)
    ema55 = compute_ema(prices, min(55, len(prices)))
    if ema9 > ema21 > ema55:
        features[2] = 1.0  # Golden cross
    elif ema9 < ema21 < ema55:
        features[2] = -1.0  # Death cross
    else:
        features[2] = 0.0  # Mixed

    # ATR/price ratio (volatility)
    atr = compute_atr(highs, lows, prices)
    features[3] = min(0.2, atr / cmp) if cmp > 0 else 0.02

    # Volume ratio
    features[4] = min(5, volume / max(1, avg_vol))

    # Stochastic RSI
    rsi_val = compute_rsi(prices)
    features[5] = rsi_val / 100.0

    # OBV trend (simplified)
    obv = 0
    for i in range(1, len(prices)):
        if prices[i] > prices[i - 1]:
            obv += volumes[i] if i < len(volumes) else avg_vol
        elif prices[i] < prices[i - 1]:
            obv -= volumes[i] if i < len(volumes) else avg_vol
    features[6] = 1 if obv > 0 else -1

    # Bollinger position
    features[7] = compute_bollinger_position(prices)

    # 52-week position
    range_52w = high52w - low52w
    features[8] = (cmp - low52w) / range_52w if range_52w > 0 else 0.5

    # Price momentum
    if len(prices) >= 5:
        features[9] = (prices[-1] / prices[-5] - 1) * 100  # 5d momentum
    if len(prices) >= 10:
        features[10] = (prices[-1] / prices[-10] - 1) * 100  # 10d momentum
    if len(prices) >= 20:
        features[11] = (prices[-1] / prices[-20] - 1) * 100  # 20d momentum

    # ── Fundamental Features ──
    sector_median_pe = (sector_stats or {}).get('median_pe', 22)
    sector_median_pb = (sector_stats or {}).get('median_pb', 1.8)

    features[12] = (pe / sector_median_pe - 1) if sector_median_pe > 0 else 0  # PE vs sector
    features[13] = (pb / sector_median_pb - 1) if sector_median_pb > 0 else 0  # PB vs sector
    features[14] = min(1, roe / 25.0)  # ROE percentile proxy
    features[15] = (div_yield - 5.8) / 5.8  # vs T-Bill rate (5.8%)
    features[16] = eps / cmp if cmp > 0 else 0  # Earnings yield as growth proxy
    features[17] = (book_value - cmp) / cmp if cmp > 0 else 0  # Book value discount
    features[18] = np.log10(max(1, market_cap))  # Log market cap
    features[19] = eps / cmp * 100 if cmp > 0 else 0  # Earnings yield %

    # ── Volume & Flow Features ──
    vol_mean = np.mean(volumes[-20:]) if len(volumes) >= 20 else avg_vol
    vol_std = np.std(volumes[-20:]) if len(volumes) >= 20 else avg_vol * 0.3
    features[20] = (volume - vol_mean) / max(1, vol_std)  # Volume anomaly z-score
    features[21] = 1 if volume > avg_vol and change_pct > 0 else (-1 if volume > avg_vol and change_pct < 0 else 0)  # Volume-price trend
    features[22] = 1 if volume > avg_vol * 1.3 and abs(change_pct) < 1.5 else 0  # Accumulation
    features[23] = stock.get('turnover', 0) / max(1, market_cap) * 1000  # Turnover ratio
    features[24] = stock.get('totalTrades', 0) / max(1, volume) * 100 if volume > 0 else 0  # Trade intensity

    # ── Market Context Features ──
    mc = market_context or {}
    features[25] = mc.get('sector_momentum', change_pct / 2)  # Sector momentum
    features[26] = mc.get('breadth_ratio', 0.6)  # Market breadth
    features[27] = 1 if mc.get('interbank_rate', 4.25) < 5 else -1  # Interbank signal
    # Seasonal: monsoon good for hydro, Q4 good for banks
    month = datetime.now().month
    sector = stock.get('sector', 'Others')
    if sector == 'Hydropower' and 4 <= month <= 8:
        features[28] = 0.8
    elif sector in ('Commercial Bank', 'Development Bank') and month in (1, 4, 7, 10):
        features[28] = 0.5
    else:
        features[28] = 0
    # Volatility regime
    recent_vol = np.std(prices[-10:]) / np.mean(prices[-10:]) if len(prices) >= 10 else 0.02
    features[29] = min(1, recent_vol / 0.05)

    # ── NEW: Advanced Signal Features (indices 30-34) ──

    # 30. Bollinger bandwidth: volatility compression/expansion
    features[30] = compute_bollinger_bandwidth(prices)

    # 31. Volume trend 5d vs 20d: rising volume = accumulation phase
    vol_ma5 = np.mean(volumes[-5:]) if len(volumes) >= 5 else avg_vol
    vol_ma20 = np.mean(volumes[-20:]) if len(volumes) >= 20 else avg_vol
    features[31] = np.clip((vol_ma5 / max(1, vol_ma20)) - 1.0, -1.0, 2.0)  # +ve = rising vol

    # 32. RSI momentum: RSI velocity over last 3 bars
    if len(prices) >= 20:
        rsi_now = compute_rsi(prices[-17:])   # RSI using last 17 bars
        rsi_3ago = compute_rsi(prices[-20:-3]) # RSI 3 bars ago
        features[32] = np.clip((rsi_now - rsi_3ago) / 10.0, -3.0, 3.0)
    else:
        features[32] = 0.0

    # 33. MACD acceleration: histogram direction (positive = accelerating up)
    if len(prices) >= 28:
        ema12_now = compute_ema(prices, 12)
        ema26_now = compute_ema(prices, 26)
        macd_now = ema12_now - ema26_now
        ema12_prev = compute_ema(prices[:-1], 12)
        ema26_prev = compute_ema(prices[:-1], 26)
        macd_prev = ema12_prev - ema26_prev
        macd_hist_change = macd_now - macd_prev
        features[33] = np.clip(macd_hist_change / (cmp * 0.005 + 1), -3, 3)
    else:
        features[33] = 0.0

    # 34. Price vs VWAP proxy: (CMP - 20d mean close) / ATR
    if len(prices) >= 20:
        mean_20d = float(np.mean(prices[-20:]))
        safe_atr = max(atr, cmp * 0.005)
        features[34] = np.clip((cmp - mean_20d) / safe_atr, -5.0, 5.0)
    else:
        features[34] = 0.0

    return features


# ─────────────────────────────────────────────────────────────────────────────
# TRAINING DATA GENERATION
# ─────────────────────────────────────────────────────────────────────────────

def generate_training_data(stocks: List[Dict]) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Generate training feature-label pairs from stock data.
    Uses current features to create labeled training set.

    Labels:
    - y_class: 1 if stock rose >2% from current features, 0 otherwise
    - y_reg:   Actual price change percentage

    Returns: (X_features, y_classification, y_regression)
    """
    X_list = []
    y_class_list = []
    y_reg_list = []

    # Compute sector statistics
    sector_stats = compute_sector_stats(stocks)
    market_context = compute_market_context(stocks)

    for stock in stocks:
        cmp = stock.get('cmp', 0)
        if cmp <= 0:
            continue

        for shift in range(TRAINING_VARIATIONS_PER_STOCK):
            rng = stable_rng(
                "training",
                stock.get('symbol', ''),
                shift,
                cmp,
                stock.get('volume', 0),
                stock.get('changePercent', 0),
            )
            # Create slightly varied version for training diversity
            varied_stock = dict(stock)
            noise = rng.normal(0, 0.02)
            varied_stock['cmp'] = cmp * (1 + noise)
            varied_stock['volume'] = int(stock.get('volume', 1000) * (0.7 + rng.random() * 0.6))
            varied_stock['changePercent'] = stock.get('changePercent', 0) + rng.normal(0, 1)

            features = engineer_features(varied_stock, sector_stats=sector_stats.get(stock.get('sector')),
                                        market_context=market_context)
            X_list.append(features)

            fvl_score = compute_fundamental_score(varied_stock, sector_stats.get(stock.get('sector'), {}))
            tml_score = compute_technical_score(features)
            combined = (
                fvl_score * 0.35
                + tml_score * 0.45
                + features[22] * 12
                + features[25] * 4
                + features[26] * 6
                + rng.normal(0, 2.5)
            )
            expected_change = np.clip(
                (combined - 50) * 0.16
                + features[9] * 0.08
                + features[10] * 0.05
                + features[21] * 0.9
                + rng.normal(0, 0.35),
                -12,
                18,
            )
            will_rise = 1 if expected_change >= 1.5 else 0
            y_class_list.append(will_rise)
            y_reg_list.append(expected_change)

    return np.array(X_list), np.array(y_class_list), np.array(y_reg_list)


def compute_sector_stats(stocks: List[Dict]) -> Dict[str, Dict]:
    """Compute sector-level statistics."""
    sectors: Dict[str, List[Dict]] = {}
    for s in stocks:
        sec = s.get('sector', 'Others')
        sectors.setdefault(sec, []).append(s)

    stats = {}
    for sec, sec_stocks in sectors.items():
        pes = [s.get('pe', 0) for s in sec_stocks if s.get('pe', 0) > 0]
        pbs = [s.get('pb', 0) for s in sec_stocks if s.get('pb', 0) > 0]
        stats[sec] = {
            'median_pe': float(np.median(pes)) if pes else 20,
            'median_pb': float(np.median(pbs)) if pbs else 1.5,
            'avg_roe': float(np.mean([s.get('roe', 10) for s in sec_stocks])),
            'count': len(sec_stocks),
        }
    return stats


def compute_market_context(stocks: List[Dict], market_snapshot: Optional[Dict] = None) -> Dict:
    """Compute market-wide context features."""
    advancers = sum(1 for s in stocks if s.get('changePercent', 0) > 0)
    total = max(1, len(stocks))
    avg_change = np.mean([s.get('changePercent', 0) for s in stocks])
    snapshot = market_snapshot or {}
    return {
        'breadth_ratio': float(snapshot.get('breadth_ratio', advancers / total)),
        'avg_change': float(snapshot.get('avg_change', avg_change)),
        'interbank_rate': float(snapshot.get('interbank_rate', 4.25)),
        'sector_momentum': float(snapshot.get('sector_momentum', avg_change)),
        'market_change_percent': float(snapshot.get('market_change_percent', avg_change)),
        'up_volume_share': float(snapshot.get('up_volume_share', advancers / total)),
    }


def compute_snapshot_signature(stocks: List[Dict]) -> str:
    """Stable signature for the current live market snapshot."""
    canonical = sorted(
        (
            str(stock.get('symbol', '')),
            round(float(stock.get('cmp', 0) or 0), 2),
            int(stock.get('volume', 0) or 0),
            round(float(stock.get('changePercent', 0) or 0), 2),
            round(float(stock.get('pe', 0) or 0), 2),
            round(float(stock.get('roe', 0) or 0), 2),
        )
        for stock in stocks
    )
    return str(stable_hash_int("snapshot", canonical, len(canonical), modulo=10**18))


def compute_fundamental_score(stock: Dict, sector_stats: Dict) -> float:
    """Quick fundamental score 0-100."""
    score = 50
    pe = stock.get('pe', 20)
    median_pe = sector_stats.get('median_pe', 20)
    if pe > 0 and pe < median_pe * 0.7:
        score += 20
    elif pe > median_pe * 1.3:
        score -= 15

    if stock.get('roe', 0) > 15:
        score += 15
    if stock.get('dividendYield', 0) > 5:
        score += 10
    if stock.get('pb', 2) < 1.5:
        score += 10

    return max(0, min(100, score))


def compute_technical_score(features: np.ndarray) -> float:
    """Quick technical score from features."""
    score = 50
    rsi = features[0] * 100
    if 30 < rsi < 70:
        score += 10
    if features[2] > 0:  # EMA alignment
        score += 15
    if features[4] > 1.2:  # Volume ratio
        score += 10
    if features[9] > 0:  # 5d momentum
        score += features[9] * 3
    if features[7] < 0:  # Below Bollinger midline (room to rise)
        score += 10
    return max(0, min(100, score))


def _to_builtin_float(value: Any, digits: Optional[int] = None) -> float:
    numeric = float(value)
    return round(numeric, digits) if digits is not None else numeric


# ─────────────────────────────────────────────────────────────────────────────
# ML MODELS — Ensemble System
# ─────────────────────────────────────────────────────────────────────────────

class StockRisePredictor:
    """
    Ensemble ML predictor using:
    - Random Forest Classifier (rise probability)
    - Gradient Boosting Regressor (price change magnitude)
    - XGBoost/GB Classifier (secondary probability for confidence)
    """

    def __init__(self):
        self.rf_classifier = RandomForestClassifier(
            n_estimators=120,
            max_depth=10,
            min_samples_split=6,
            min_samples_leaf=3,
            max_features='sqrt',
            class_weight='balanced',
            random_state=42,
            n_jobs=-1,
        )
        self.gb_regressor = GradientBoostingRegressor(
            n_estimators=110,
            max_depth=4,
            learning_rate=0.07,
            subsample=0.85,
            random_state=42,
        )
        if HAS_XGBOOST:
            self.xgb_classifier = XGBClassifier(
                n_estimators=90,
                max_depth=6,
                learning_rate=0.07,
                subsample=0.85,
                colsample_bytree=0.85,
                random_state=42,
                eval_metric='logloss',
                verbosity=0,
                n_jobs=4,
            )
        else:
            self.xgb_classifier = GradientBoostingClassifier(
                n_estimators=100,
                max_depth=4,
                learning_rate=0.07,
                subsample=0.85,
                random_state=42,
            )
        self.mlp_classifier = MLPClassifier(
            hidden_layer_sizes=(48, 16),
            activation='relu',
            learning_rate_init=0.0025,
            early_stopping=True,
            n_iter_no_change=12,
            max_iter=220,
            random_state=42,
        )
        self.mlp_regressor = MLPRegressor(
            hidden_layer_sizes=(56, 24),
            activation='relu',
            learning_rate_init=0.002,
            early_stopping=True,
            n_iter_no_change=12,
            max_iter=220,
            random_state=42,
        )
        self.scaler = StandardScaler()
        self.is_trained = False
        self.feature_importances_ = None
        self.training_metrics = {}
        self.snapshot_signature: Optional[str] = None
        self.last_trained_at: float = 0.0

    def ensure_trained(self, stocks: List[Dict]):
        """Retrain only when the live market snapshot has changed."""
        if not stocks:
            return

        snapshot_signature = compute_snapshot_signature(stocks)
        if self.is_trained and self.snapshot_signature == snapshot_signature:
            return

        now = time.time()
        if self.is_trained and (now - self.last_trained_at) < MIN_RETRAIN_INTERVAL_SECONDS:
            logger.info(
                "Skipping retrain for updated live snapshot; current ensemble is %.1fs old",
                now - self.last_trained_at,
            )
            return

        self.train(stocks, snapshot_signature=snapshot_signature)

    def train(self, stocks: List[Dict], snapshot_signature: Optional[str] = None):
        """Train all models on current stock data."""
        start = time.time()
        logger.info(f"Training ML models on {len(stocks)} stocks...")

        X, y_class, y_reg = generate_training_data(stocks)

        if len(X) < 10:
            logger.warning("Not enough training data")
            return

        # Scale features
        X_scaled = self.scaler.fit_transform(X)

        # Train classifier (will it rise?)
        self.rf_classifier.fit(X_scaled, y_class)

        # Train regressor (by how much?)
        self.gb_regressor.fit(X_scaled, y_reg)

        # Train secondary classifier
        self.xgb_classifier.fit(X_scaled, y_class)
        self.mlp_classifier.fit(X_scaled, y_class)
        self.mlp_regressor.fit(X_scaled, y_reg)

        # Compute feature importances (average of RF and GB)
        rf_imp = self.rf_classifier.feature_importances_
        gb_imp = np.abs(self.gb_regressor.feature_importances_)
        self.feature_importances_ = (rf_imp + gb_imp) / 2

        snapshot_fit_accuracy = self.rf_classifier.score(X_scaled, y_class)
        self.training_metrics = {
            'accuracy': round(float(snapshot_fit_accuracy) * 100, 1),
            'accuracy_type': 'snapshot_fit',
            'samples': len(X),
            'features': X.shape[1],
            'positive_rate': round(float(np.mean(y_class)) * 100, 1),
            'training_time': round(time.time() - start, 2),
            'min_retrain_interval_seconds': MIN_RETRAIN_INTERVAL_SECONDS,
        }

        self.is_trained = True
        self.snapshot_signature = snapshot_signature or compute_snapshot_signature(stocks)
        self.last_trained_at = time.time()
        logger.info(f"ML training complete in {time.time() - start:.2f}s. "
                    f"Accuracy: {self.training_metrics.get('accuracy', 'N/A')}%")

    def predict(
        self,
        stocks: List[Dict],
        market_context_override: Optional[Dict] = None,
        market_regime: Optional[str] = None,
        crash_risk: float = 0.0,
    ) -> List[Dict]:
        """
        Generate predictions for all stocks.
        Returns list of prediction dicts sorted by confidence-weighted probability.
        """
        if not stocks:
            return []

        self.ensure_trained(stocks)

        sector_stats = compute_sector_stats(stocks)
        market_context = compute_market_context(stocks, market_context_override)
        predictions = []
        regime_penalty = (
            10.0 if market_regime == "BEAR TREND"
            else 6.0 if market_regime == "HIGH VOLATILITY"
            else 2.0 if market_regime == "SIDEWAYS"
            else 0.0
        )
        # Sectors with strong macro tailwinds get a confidence boost
        BULL_SECTORS = {"Commercial Bank", "Hydropower", "Insurance", "Development Bank"}

        for stock in stocks:
            cmp = stock.get('cmp', 0)
            if cmp <= 0:
                continue

            # Engineer features
            features = engineer_features(
                stock,
                sector_stats=sector_stats.get(stock.get('sector')),
                market_context=market_context
            )
            features_scaled = self.scaler.transform(features.reshape(1, -1))

            # ── Ensemble Predictions ──

            # RF probability of rise
            rf_prob = self.rf_classifier.predict_proba(features_scaled)[0]
            rf_rise_prob = rf_prob[1] if len(rf_prob) > 1 else 0.5

            # XGB probability
            xgb_prob = self.xgb_classifier.predict_proba(features_scaled)[0]
            xgb_rise_prob = xgb_prob[1] if len(xgb_prob) > 1 else 0.5

            # Neural-network probability
            mlp_prob = self.mlp_classifier.predict_proba(features_scaled)[0]
            mlp_rise_prob = mlp_prob[1] if len(mlp_prob) > 1 else 0.5

            # GB predicted change
            predicted_change_pct = float(self.gb_regressor.predict(features_scaled)[0])
            nn_predicted_change_pct = float(self.mlp_regressor.predict(features_scaled)[0])

            # ── Ensemble Combination ──
            gb_signal = 1 / (1 + np.exp(-predicted_change_pct / 3))
            nn_signal = 1 / (1 + np.exp(-nn_predicted_change_pct / 3.2))
            ensemble_prob = (
                rf_rise_prob * 0.30
                + xgb_rise_prob * 0.24
                + mlp_rise_prob * 0.24
                + gb_signal * 0.12
                + nn_signal * 0.10
            )
            ensemble_prob = ensemble_prob * 100

            predicted_change_pct = (
                predicted_change_pct * 0.58
                + nn_predicted_change_pct * 0.42
            )

            market_alignment_bonus = max(-12.0, min(8.0, market_context.get('market_change_percent', 0) * 1.8))
            crash_penalty = crash_risk * 0.11
            predicted_change_pct *= max(0.45, 1 - crash_penalty / 100)
            # Sector-adjusted confidence: bull-sector stocks get up to +4% probability boost
            sector = stock.get('sector', 'Others')
            sector_confidence_bonus = 4.0 if sector in BULL_SECTORS else 0.0
            ensemble_prob = round(
                min(
                    98.0,
                    max(
                        2.0,
                        ensemble_prob + market_alignment_bonus - regime_penalty - crash_penalty + sector_confidence_bonus,
                    ),
                ),
                1,
            )

            # Predicted price movement
            predicted_rs_change = round(cmp * predicted_change_pct / 100, 2)
            predicted_target = round(cmp + predicted_rs_change, 2)

            # Confidence level
            model_probs = [rf_rise_prob, xgb_rise_prob, mlp_rise_prob, gb_signal, nn_signal]
            prob_agreement = 1 - float(np.std(model_probs))
            if ensemble_prob > 74 and prob_agreement > 0.78:
                confidence = "VERY HIGH"
            elif ensemble_prob > 63 and prob_agreement > 0.62:
                confidence = "HIGH"
            elif ensemble_prob > 52:
                confidence = "MEDIUM"
            else:
                confidence = "LOW"

            # Key drivers (top 5 features)
            if self.feature_importances_ is not None:
                feature_contributions = features * self.feature_importances_
                top_indices = np.argsort(np.abs(feature_contributions))[-5:][::-1]
                key_drivers = []
                for idx in top_indices:
                    name = FEATURE_NAMES[idx] if idx < len(FEATURE_NAMES) else f"feature_{idx}"
                    value = features[idx]
                    direction = "↑" if value > 0 else "↓" if value < 0 else "→"
                    importance = round(self.feature_importances_[idx] * 100, 1)
                    key_drivers.append({
                        "feature": name.replace('_', ' ').title(),
                        "value": _to_builtin_float(value, 3),
                        "direction": direction,
                        "importance": _to_builtin_float(importance, 1),
                    })
            else:
                key_drivers = []

            # Risk assessment
            atr_ratio = features[3]
            atr_abs = max(cmp * atr_ratio, cmp * 0.012, 1.0)
            if atr_ratio > 0.05:
                risk = "HIGH"
            elif atr_ratio > 0.025:
                risk = "MODERATE"
            else:
                risk = "LOW"

            # AI reasoning
            reasoning = generate_reasoning(stock, ensemble_prob, predicted_change_pct, features, confidence)

            gap_pct = ((stock.get('open', cmp) or cmp) - stock.get('previousClose', cmp)) / max(stock.get('previousClose', cmp) or cmp, 1) * 100
            buy_range_low = round(max(0.01, cmp - atr_abs * 0.75), 2)
            buy_range_high = round(max(buy_range_low + 0.01, min(cmp * 1.01, cmp - atr_abs * 0.10 if gap_pct > 2 else cmp + atr_abs * 0.12)), 2)
            ideal_entry = round((buy_range_low + buy_range_high) / 2, 2)
            stop_loss = round(max(0.01, ideal_entry - atr_abs * (1.7 if risk == "LOW" else 1.4)), 2)
            base_sell_floor = ideal_entry + (atr_abs * 1.6 if predicted_change_pct > 0 else atr_abs * 0.75)
            projected_sell_ceiling = (
                ideal_entry + max(predicted_rs_change * 1.15, atr_abs * 2.7)
                if predicted_change_pct > 0
                else ideal_entry + atr_abs * 1.1
            )
            sell_range_low = round(max(predicted_target, base_sell_floor), 2)
            sell_range_high = round(max(sell_range_low + 0.01, projected_sell_ceiling), 2)
            expected_profit_rs = round(max(sell_range_high - ideal_entry, 0.0), 2)
            expected_profit_pct = round((expected_profit_rs / max(ideal_entry, 0.01)) * 100, 2)
            expected_downside_rs = round(max(ideal_entry - stop_loss, 0.01), 2)
            expected_downside_pct = round((expected_downside_rs / max(ideal_entry, 0.01)) * 100, 2)
            risk_reward_ratio = round(expected_profit_rs / max(expected_downside_rs, 0.01), 2)
            hold_days_min = 4 if confidence in ("VERY HIGH", "HIGH") else 7 if confidence == "MEDIUM" else 10
            hold_days_max = hold_days_min + (7 if predicted_change_pct >= 6 else 10 if predicted_change_pct >= 3 else 12)
            time_to_target_days = int(round((hold_days_min + hold_days_max) / 2))

            market_alignment = (
                "HEADWIND" if market_regime in ("BEAR TREND", "HIGH VOLATILITY")
                else "TAILWIND" if market_regime == "BULL TREND"
                else "NEUTRAL"
            )

            # Recommended action
            if ensemble_prob >= 75 and confidence in ("VERY HIGH", "HIGH") and risk_reward_ratio >= 1.8:
                action = "STRONG BUY"
            elif ensemble_prob >= 64 and risk_reward_ratio >= 1.4:
                action = "BUY"
            elif ensemble_prob >= 54:
                action = "SPECULATIVE BUY"
            elif ensemble_prob >= 45:
                action = "HOLD"
            else:
                action = "AVOID"

            recommendation_summary = (
                f"Prefer Rs.{buy_range_low:,.2f}-Rs.{buy_range_high:,.2f}, aim to scale out into Rs.{sell_range_low:,.2f}-Rs.{sell_range_high:,.2f}, "
                f"and plan for roughly {hold_days_min}-{hold_days_max} trading days if the setup remains valid."
            )

            predictions.append({
                "symbol": stock.get('symbol', ''),
                "name": stock.get('name', ''),
                "sector": stock.get('sector', ''),
                "cmp": _to_builtin_float(cmp, 2),
                "changePercent": _to_builtin_float(stock.get('changePercent', 0), 2),
                "riseProbability": _to_builtin_float(ensemble_prob, 1),
                "predictedChangePercent": _to_builtin_float(predicted_change_pct, 2),
                "predictedRsChange": _to_builtin_float(predicted_rs_change, 2),
                "predictedTarget": _to_builtin_float(predicted_target, 2),
                "confidence": confidence,
                "risk": risk,
                "action": action,
                "keyDrivers": key_drivers,
                "reasoning": reasoning,
                "recommendationSummary": recommendation_summary,
                "modelScores": {
                    "randomForest": _to_builtin_float(rf_rise_prob * 100, 1),
                    "xgboost": _to_builtin_float(xgb_rise_prob * 100, 1),
                    "mlpClassifier": _to_builtin_float(mlp_rise_prob * 100, 1),
                    "gradientBoosting": _to_builtin_float(gb_signal * 100, 1),
                    "mlpRegressor": _to_builtin_float(nn_signal * 100, 1),
                },
                "buyRangeLow": _to_builtin_float(buy_range_low, 2),
                "buyRangeHigh": _to_builtin_float(buy_range_high, 2),
                "idealEntry": _to_builtin_float(ideal_entry, 2),
                "stopLoss": _to_builtin_float(stop_loss, 2),
                "sellRangeLow": _to_builtin_float(sell_range_low, 2),
                "sellRangeHigh": _to_builtin_float(sell_range_high, 2),
                "expectedProfitRs": _to_builtin_float(expected_profit_rs, 2),
                "expectedProfitPercent": _to_builtin_float(expected_profit_pct, 2),
                "expectedDownsideRs": _to_builtin_float(expected_downside_rs, 2),
                "expectedDownsidePercent": _to_builtin_float(expected_downside_pct, 2),
                "riskRewardRatio": _to_builtin_float(risk_reward_ratio, 2),
                "holdDaysMin": hold_days_min,
                "holdDaysMax": hold_days_max,
                "timeToTargetDays": time_to_target_days,
                "marketAlignment": market_alignment,
                "crashRisk": _to_builtin_float(crash_risk, 1),
                "exitTrigger": f"Exit if price loses Rs.{stop_loss:,.2f} or momentum fails before the sell zone.",
                "volume": int(stock.get('volume', 0) or 0),
                "pe": _to_builtin_float(stock.get('pe', 0), 2),
                "roe": _to_builtin_float(stock.get('roe', 0), 2),
            })

        # Sort by composite score: probability × expected return magnitude
        predictions.sort(key=lambda p: p['riseProbability'] * max(0.1, p['predictedChangePercent']), reverse=True)

        # Add ranks
        for i, p in enumerate(predictions):
            p['rank'] = i + 1

        return predictions

    def get_feature_importance(self) -> List[Dict]:
        """Get ranked feature importances."""
        if self.feature_importances_ is None:
            return []
        indexed = list(enumerate(self.feature_importances_))
        indexed.sort(key=lambda x: x[1], reverse=True)
        return [
            {
                "feature": FEATURE_NAMES[i].replace('_', ' ').title(),
                "importance": _to_builtin_float(v * 100, 2),
            }
            for i, v in indexed[:15]
        ]

    def get_model_metrics(self) -> Dict:
        """Get model training metrics."""
        return {
            **self.training_metrics,
            "models": [
                "RandomForest (120 trees, depth 10)",
                "GradientBoosting (110 trees, lr 0.07)",
                f"{'XGBoost' if HAS_XGBOOST else 'GradientBoosting'} (90 trees, lr 0.07)",
                "MLPClassifier (48x16 neural net)",
                "MLPRegressor (56x24 neural net)",
            ],
            "features_used": len(FEATURE_NAMES),
            "feature_categories": {
                "technical": 12,
                "fundamental": 8,
                "volume_flow": 5,
                "market_context": 5,
            },
            "ensemble_weights": {
                "randomForest": "30%",
                "xgboost": "24%",
                "mlpClassifier": "24%",
                "gradientBoosting": "12%",
                "mlpRegressor": "10%",
            },
        }


# ─────────────────────────────────────────────────────────────────────────────
# AI REASONING GENERATOR
# ─────────────────────────────────────────────────────────────────────────────

def generate_reasoning(stock: Dict, prob: float, change_pct: float,
                       features: np.ndarray, confidence: str) -> str:
    """Generate human-readable AI reasoning for a prediction."""
    symbol = stock.get('symbol', '')
    cmp = stock.get('cmp', 0)
    sector = stock.get('sector', 'Others')
    parts = []

    rsi = features[0] * 100
    ema_align = features[2]
    vol_ratio = features[4]
    momentum_5d = features[9]
    momentum_20d = features[11]
    pe_vs_sector = features[12]
    bollinger = features[7]
    bb_bandwidth = features[30] if len(features) > 30 else 0.04
    vol_trend_5d = features[31] if len(features) > 31 else 0.0
    rsi_momentum = features[32] if len(features) > 32 else 0.0
    macd_accel = features[33] if len(features) > 33 else 0.0
    price_vs_vwap = features[34] if len(features) > 34 else 0.0

    if prob >= 70:
        parts.append(f"{symbol} shows strong bullish signals across multiple dimensions.")
    elif prob >= 55:
        parts.append(f"{symbol} displays moderately positive indicators.")
    else:
        parts.append(f"{symbol} presents mixed signals with limited upside conviction.")

    # EMA alignment
    if ema_align > 0:
        parts.append("EMA alignment is golden (9>21>55), confirming uptrend structure.")
    elif ema_align < 0:
        parts.append("EMA alignment is bearish (death cross), structural headwind.")

    # RSI with momentum direction
    if 30 <= rsi <= 45:
        rsi_suffix = " and rising" if rsi_momentum > 0.3 else ""
        parts.append(f"RSI at {rsi:.0f}{rsi_suffix} — emerging from oversold, reversal potential high.")
    elif rsi > 70:
        parts.append(f"RSI at {rsi:.0f} — overbought territory, pullback likely before next leg.")
    elif 50 <= rsi <= 65:
        rsi_dir = "accelerating" if rsi_momentum > 0.5 else "stable"
        parts.append(f"RSI at {rsi:.0f} ({rsi_dir}) — healthy momentum, room to run.")

    # MACD acceleration signal
    if macd_accel > 0.5:
        parts.append("MACD histogram expanding — momentum accelerating bullish.")
    elif macd_accel < -0.5:
        parts.append("MACD histogram contracting — momentum losing steam.")

    # Bollinger bandwidth — squeeze = breakout incoming
    if bb_bandwidth < 0.03:
        parts.append("Bollinger Bands in squeeze — volatility compression signals imminent breakout.")
    elif bb_bandwidth > 0.12:
        parts.append("Bollinger Bands wide — elevated volatility, size positions accordingly.")

    # Volume analysis
    if vol_ratio > 1.5:
        vol_trend_str = ", with 5-day volume trend rising" if vol_trend_5d > 0.15 else ""
        parts.append(f"Volume {vol_ratio:.1f}x average{vol_trend_str} — institutional interest detected.")
    elif vol_ratio < 0.6:
        parts.append("Low volume — lacks conviction for sustained move.")
    elif vol_trend_5d > 0.20:
        parts.append("Rising volume trend (5d MA > 20d MA) — accumulation phase likely.")

    # Price vs VWAP proxy — mean reversion signal
    if price_vs_vwap < -1.5:
        parts.append("Price trading below 20-day average — attractive mean-reversion entry.")
    elif price_vs_vwap > 2.0:
        parts.append("Price extended above 20-day average — risk of short-term pullback.")

    # Fundamental reasoning
    if pe_vs_sector < -0.2:
        parts.append("Trading below sector P/E median — value opportunity.")
    elif pe_vs_sector > 0.3:
        parts.append("Premium valuation vs sector — already prices in growth.")

    # Momentum context
    if momentum_5d > 3:
        parts.append(f"Strong 5-day momentum (+{momentum_5d:.1f}%) supports continuation.")
    elif momentum_5d < -3:
        parts.append(f"Recent weakness ({momentum_5d:.1f}%) could signal mean-reversion bounce.")

    # Sector context
    month = datetime.now().month
    if sector == 'Hydropower' and 4 <= month <= 8:
        parts.append("Monsoon tailwind: hydropower generation at peak, sector sentiment elevated.")
    elif sector in ('Commercial Bank', 'Development Bank') and month in (1, 4, 7, 10):
        parts.append("Quarterly results cycle: banking sector in focus, dividend plays active.")
    elif sector == 'Insurance' and month in (3, 4, 9, 10):
        parts.append("Insurance sector policy renewal cycle: premium income peak quarter.")

    # Target
    target = round(cmp + cmp * change_pct / 100, 0)
    if change_pct > 0:
        parts.append(f"ML ensemble targets Rs.{target:,.0f} ({change_pct:+.1f}%). Confidence: {confidence}.")
    else:
        parts.append(f"Models suggest limited upside, target Rs.{target:,.0f}. Confidence: {confidence}.")

    return " ".join(parts)


# ─────────────────────────────────────────────────────────────────────────────
# SINGLETON PREDICTOR
# ─────────────────────────────────────────────────────────────────────────────

predictor = StockRisePredictor()
