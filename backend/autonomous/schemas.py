"""
Pydantic schemas for the autonomous research platform.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


SignalLabel = Literal["STRONG BUY", "BUY", "HOLD", "SELL", "STRONG SELL"]
RiskLevel = Literal["LOW", "MEDIUM", "HIGH", "VERY HIGH"]
RegimeLabel = Literal["BULL", "BEAR", "SIDEWAYS", "DISTRIBUTION", "CRISIS"]


class ArchitectureComponent(BaseModel):
    name: str
    layer: str
    description: str
    technologies: list[str] = Field(default_factory=list)


class PredictionTargets(BaseModel):
    target_7d: float
    target_30d: float
    target_90d: float


class TechnicalBreakdown(BaseModel):
    technical_score: float = Field(ge=0, le=100)
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
    detected_patterns: list[str] = Field(default_factory=list)


class FundamentalBreakdown(BaseModel):
    fundamental_score: float = Field(ge=0, le=100)
    eps: float = 0.0
    pe: float = 0.0
    pb: float = 0.0
    dividend_yield: float = 0.0
    revenue_growth_yoy: float = 0.0
    revenue_growth_qoq: float = 0.0
    net_profit_margin: float = 0.0
    roe: float = 0.0
    roa: float = 0.0
    debt_to_equity: float = 0.0
    current_ratio: float = 0.0
    quick_ratio: float = 0.0
    book_value_per_share: float = 0.0
    npl_ratio: Optional[float] = None
    casa_ratio: Optional[float] = None
    deterioration_flags: list[str] = Field(default_factory=list)


class CorrelationSignal(BaseModel):
    series: str
    lag_days: int
    correlation: float
    latest_direction: str
    impact: str


class GlobalBreakdown(BaseModel):
    global_sentiment_score: float = Field(ge=0, le=100)
    signals: list[CorrelationSignal] = Field(default_factory=list)
    macro_bias: str
    remittance_tailwind: float = 0.0
    policy_rate_trend: float = 0.0
    commodity_pressure: float = 0.0
    crypto_sentiment: float = 0.0


class ModelVote(BaseModel):
    model_name: str
    confidence: float = Field(ge=0, le=100)
    predicted_return_7d: float
    predicted_return_30d: float
    predicted_return_90d: float
    directional_bias: str
    rationale: str


class SectorRotationSignal(BaseModel):
    sector: str
    rotation_score: float = Field(ge=0, le=100)
    leadership_score: float = Field(ge=0, le=100)
    momentum_score: float = Field(ge=0, le=100)
    valuation_score: float = Field(ge=0, le=100)
    liquidity_score: float = Field(ge=0, le=100)
    signal: str
    commentary: str


class MarketRegimeSnapshot(BaseModel):
    regime: RegimeLabel
    confidence: float = Field(ge=0, le=100)
    trend_score: float = Field(ge=0, le=100)
    volatility_score: float = Field(ge=0, le=100)
    breadth_score: float = Field(ge=0, le=100)
    liquidity_score: float = Field(ge=0, le=100)
    explanation: str


class MonitoringMetric(BaseModel):
    horizon: str
    directional_accuracy: float = Field(ge=0, le=100)
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float = Field(ge=0, le=100)


class SystemStatus(BaseModel):
    as_of: datetime
    database_backend: str
    timescaledb_active: bool
    latest_ingestion_at: Optional[datetime] = None
    latest_training_at: Optional[datetime] = None
    latest_scoring_at: Optional[datetime] = None
    bootstrap_mode: bool = False
    symbols_covered: int = 0
    bars_loaded: int = 0
    fundamentals_loaded: int = 0
    macro_points_loaded: int = 0
    news_articles_loaded: int = 0
    retrain_required: bool = False


class SignalCard(BaseModel):
    as_of: datetime
    symbol: str
    company_name: str
    sector: str
    overall_signal: SignalLabel
    confidence_score: float = Field(ge=0, le=100)
    predicted_targets: PredictionTargets
    expected_return_percent: float
    risk_adjusted_return: float
    risk_level: RiskLevel
    technical: TechnicalBreakdown
    fundamentals: FundamentalBreakdown
    global_view: GlobalBreakdown
    top_reasons: list[str] = Field(default_factory=list)
    historical_accuracy: float = Field(ge=0, le=100)
    warnings: list[str] = Field(default_factory=list)
    model_votes: list[ModelVote] = Field(default_factory=list)
    liquidity_score: float = Field(ge=0, le=100)
    sentiment_score: float = Field(ge=0, le=100)
    regime_alignment_score: float = Field(ge=0, le=100)


class BacktestSummary(BaseModel):
    strategy_name: str
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    annualized_return: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    turnover: float


class AutonomousDashboardResponse(BaseModel):
    architecture: list[ArchitectureComponent]
    architecture_diagram: str
    status: SystemStatus
    regime: MarketRegimeSnapshot
    monitoring: list[MonitoringMetric]
    sector_rotation: list[SectorRotationSignal]
    top_buys: list[SignalCard]
    top_avoids: list[SignalCard]
    backtest: Optional[BacktestSummary] = None
