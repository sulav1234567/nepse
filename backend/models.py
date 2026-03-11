"""
NEPSE-ALPHA ULTIMATE — Data Models
Pydantic models for the prediction system.
"""

from pydantic import BaseModel, Field
from typing import Literal, Optional
from enum import Enum


class Signal(str, Enum):
    STRONG_BUY = "STRONG BUY"
    BUY = "BUY"
    SPECULATIVE_BUY = "SPECULATIVE BUY"
    HOLD = "HOLD"
    AVOID = "AVOID"
    SHORT_ALERT = "SHORT ALERT"


class Regime(str, Enum):
    BULL = "BULL TREND"
    BEAR = "BEAR TREND"
    HIGH_VOLATILITY = "HIGH VOLATILITY"
    SIDEWAYS = "SIDEWAYS"
    POLITICAL_RISK = "POLITICAL RISK"


class Sector(str, Enum):
    COMMERCIAL_BANK = "Commercial Bank"
    DEVELOPMENT_BANK = "Development Bank"
    FINANCE = "Finance"
    HYDROPOWER = "Hydropower"
    INSURANCE = "Insurance"
    MICROFINANCE = "Microfinance"
    MANUFACTURING = "Manufacturing"
    HOTEL_TOURISM = "Hotel & Tourism"
    TRADING = "Trading"
    OTHERS = "Others"


class StockData(BaseModel):
    symbol: str
    name: str
    sector: str
    cmp: float
    previous_close: float
    change: float
    change_percent: float
    volume: int
    avg_volume_20d: int
    high_52w: float
    low_52w: float
    eps: float
    pe: float
    pb: float
    roe: float
    dividend_yield: float
    book_value: float
    market_cap: float


class HistoricalPrice(BaseModel):
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: int


class LayerScores(BaseModel):
    fvl: float = Field(ge=0, le=100)
    tml: float = Field(ge=0, le=100)
    ssil: float = Field(ge=0, le=100)
    gtbil: float = Field(ge=0, le=100)
    mrlll: float = Field(ge=0, le=100)


class LayerWeights(BaseModel):
    fvl: float = 0.25
    tml: float = 0.25
    ssil: float = 0.15
    gtbil: float = 0.25
    mrlll: float = 0.10


class TechnicalIndicators(BaseModel):
    ema9: float
    ema21: float
    ema55: float
    sma200: float
    rsi14: float
    macd_line: float
    macd_signal: float
    macd_histogram: float
    stoch_rsi: float
    obv: float
    atr14: float
    volume_ratio: float
    ema_alignment: str  # GOLDEN / MIXED / DEATH


class OverrideCondition(BaseModel):
    id: str
    name: str
    triggered: bool
    description: str


class PriceTargets(BaseModel):
    pt1: float
    pt2: float
    stop_loss: float
    trailing_stop_activation: float


class WarningFlags(BaseModel):
    sis_score: float
    sis_level: str
    bmr: float
    bmr_level: str
    circular_trading: bool = False
    right_share_phase: str = "N/A"
    tth_status: str = "SAFE"
    political_risk: str = "LOW"
    bsts_confidence: str = "NORMAL"
    data_stale: bool = False
    data_staleness_minutes: int = 0


class FCSResult(BaseModel):
    score: float
    signal: str
    layer_scores: LayerScores
    weights: LayerWeights
    overrides: list[OverrideCondition]
    active_override: Optional[str] = None


class FullAnalysis(BaseModel):
    stock: StockData
    indicators: TechnicalIndicators
    fcs: FCSResult
    price_targets: PriceTargets
    warning_flags: WarningFlags
    fvl_details: list[str]
    tml_details: list[str]
    ssil_details: list[str]
    gtbil_details: list[str]
    mrlll_details: list[str]
    overvaluation_percent: float
    bsts_fair_value: float
    retail_institutional_verdict: str
    kalman_state: Optional[dict] = None


class DailyPrediction(BaseModel):
    rank: int
    symbol: str
    name: str
    signal_type: str
    entry_zone: str
    target: float
    stop_loss: float
    confidence: float
    signal: str
    rationale: str


class WeeklyPrediction(BaseModel):
    symbol: str
    name: str
    entry_range: str
    target_week: float
    stop_loss: float
    fcs: float
    signal: str
    time_horizon: str
    key_driver: str


class MonthlyPrediction(BaseModel):
    symbol: str
    name: str
    entry_strategy: str
    target_1m: float
    target_3m: float
    stop_loss: float
    portfolio_weight: float
    signal: str
    thesis: str
    catalyst_calendar: str
    invalidation_conditions: list[str]


class MarketOverview(BaseModel):
    nepse_index: float
    nepse_change: float
    nepse_change_percent: float
    total_turnover: float
    total_volume: int
    total_transactions: int
    advancers: int
    decliners: int
    unchanged: int
    regime: str
    regime_confidence: float
    interbank_rate: float
    t_bill_yield: float


class SectorPerformance(BaseModel):
    sector: str
    index: float
    change: float
    change_percent: float
    volume: int


class RegimeDetection(BaseModel):
    regime: str
    confidence: float
    weights: LayerWeights
    position_multiplier: float
    cash_buffer: float
    description: str
    best_signals: list[str]


class PortfolioOptResult(BaseModel):
    weights: dict[str, float]
    expected_return: float
    expected_volatility: float
    sortino_ratio: float
    sharpe_ratio: float
