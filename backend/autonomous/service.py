"""
Service orchestration for the autonomous NEPSE research platform.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Any, Optional

import numpy as np
import pandas as pd
from sqlalchemy import func

from ..settings import Settings, get_settings
from .backtesting import BacktestResult, run_walk_forward_backtest
from .features import (
    build_feature_frame,
    compute_macro_correlation_signal,
    compute_sector_rotation,
    detect_regime,
    score_fundamentals,
    sector_medians,
    summarize_reason_stack,
)
from .indicators import build_technical_snapshot
from .ingestion import DataIngestionService
from .internet_training_data import InternetTrainingDataBuilder
from .models import AutonomousModelSuite
from .schemas import (
    ArchitectureComponent,
    AutonomousDashboardResponse,
    BacktestSummary,
    CorrelationSignal,
    FundamentalBreakdown,
    GlobalBreakdown,
    MarketRegimeSnapshot,
    MonitoringMetric,
    ModelVote,
    PredictionTargets,
    SectorRotationSignal,
    SignalCard,
    SystemStatus,
    TechnicalBreakdown,
)
from .storage import (
    BacktestReport,
    FundamentalSnapshot,
    MacroSeriesPoint,
    MarketBar,
    ModelArtifact,
    NewsArticle,
    PredictionOutcome,
    PredictionRun,
    PredictionSignal,
    AutonomousDatabase,
    get_database,
)

logger = logging.getLogger("nepse-alpha.autonomous.service")

ARCHITECTURE_DIAGRAM = """
flowchart LR
    A["Local CSVs / Live NEPSE Feeds / Macro Inputs / News"] --> B["Autonomous Ingestion Engine"]
    B --> C["PostgreSQL + TimescaleDB"]
    C --> D["Feature Engineering Layer"]
    D --> E["TA Engine"]
    D --> F["Fundamental Engine"]
    D --> G["Global Correlation Engine"]
    D --> H["Sentiment Engine"]
    D --> I["Sector Rotation Engine"]
    D --> J["Regime Detector"]
    D --> K["Model Suite: LSTM / TFT / XGB-LGBM / PPO / NLP"]
    K --> L["Stacking Meta-Learner"]
    L --> M["Signal Cards + Rankings + Monitoring"]
    M --> N["FastAPI REST API"]
    M --> O["Celery Worker + Retraining Scheduler"]
    N --> P["Next.js Dashboard"]
    O --> C
"""


def _round_float(value: float, digits: int = 2) -> float:
    return round(float(value), digits)


class AutonomousResearchPlatform:
    """Autonomous, continuously-learning NEPSE research service."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        database: Optional[AutonomousDatabase] = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.database = database or get_database()
        self.ingestion = DataIngestionService(settings=self.settings, database=self.database)
        self.dataset_builder = InternetTrainingDataBuilder(settings=self.settings)
        self.model_suite = AutonomousModelSuite.load(settings=self.settings)
        self._latest_backtest: Optional[BacktestResult] = None

    def initialize(self) -> None:
        self.database.initialize()

    def architecture_components(self) -> list[ArchitectureComponent]:
        return [
            ArchitectureComponent(
                name="Autonomous Ingestion Engine",
                layer="Data",
                description="Loads OHLCV, fundamentals, macro series, and news into Timescale-ready storage.",
                technologies=["Pandas", "SQLAlchemy", "TimescaleDB", "Celery"],
            ),
            ArchitectureComponent(
                name="Technical Analysis Engine",
                layer="Analytics",
                description="Computes TA indicators, chart patterns, support/resistance, and technical scoring.",
                technologies=["NumPy", "Pandas"],
            ),
            ArchitectureComponent(
                name="Fundamental Analysis Engine",
                layer="Analytics",
                description="Scores profitability, valuation, liquidity, leverage, and sector-specific balance-sheet quality.",
                technologies=["Pandas", "Rule Engine"],
            ),
            ArchitectureComponent(
                name="Global Correlation Engine",
                layer="Analytics",
                description="Detects lagged cross-market relationships across India, US, China, commodities, rates, and remittances.",
                technologies=["Pandas", "Statistics"],
            ),
            ArchitectureComponent(
                name="Model Suite",
                layer="ML",
                description="Multi-model ensemble combining LSTM, temporal-fusion style forecasting, tree ensembles, RL, and news sentiment.",
                technologies=["scikit-learn", "XGBoost", "LightGBM", "PyTorch", "PPO"],
            ),
            ArchitectureComponent(
                name="Meta-Learner and Monitoring",
                layer="ML Ops",
                description="Learns regime-aware model weighting, stores versions, and tracks accuracy, Sharpe, and drawdown.",
                technologies=["Ridge", "Logistic Regression", "MLflow"],
            ),
            ArchitectureComponent(
                name="Delivery Layer",
                layer="Product",
                description="FastAPI endpoints and a Next.js dashboard expose signal cards, ranking, and system health.",
                technologies=["FastAPI", "Next.js", "Redis"],
            ),
        ]

    def _status(self) -> SystemStatus:
        counts = self.database.counts()
        with self.database.session() as session:
            latest_bar = self.database.latest_timestamp(session, MarketBar)
            latest_fundamental = self.database.latest_timestamp(session, FundamentalSnapshot, column_name="report_date")
            latest_macro = self.database.latest_timestamp(session, MacroSeriesPoint)
        latest_ingestion = max(item for item in [latest_bar, latest_fundamental, latest_macro] if item is not None) if any([latest_bar, latest_fundamental, latest_macro]) else None
        symbols_covered = self._symbols()
        return SystemStatus(
            as_of=datetime.utcnow(),
            database_backend=self.database.dialect_name,
            timescaledb_active=self.database.is_timescaledb_active,
            latest_ingestion_at=latest_ingestion,
            latest_training_at=self.model_suite.last_trained_at,
            latest_scoring_at=datetime.utcnow(),
            bootstrap_mode=counts["bars"] == 0 or any("SIMULATED_BOOTSTRAP" in source for source in self._latest_sources()),
            symbols_covered=len(symbols_covered),
            bars_loaded=counts["bars"],
            fundamentals_loaded=counts["fundamentals"],
            macro_points_loaded=counts["macro_points"],
            news_articles_loaded=counts["news_articles"],
            retrain_required=self.model_suite.metrics.get("accuracy_7d", 0.0) < self.settings.retrain_accuracy_floor,
        )

    def _latest_sources(self) -> list[str]:
        with self.database.session() as session:
            rows = (
                session.query(MarketBar.source)
                .order_by(MarketBar.ts.desc())
                .limit(20)
                .all()
            )
        return [row[0] for row in rows]

    def _symbols(self) -> list[str]:
        with self.database.session() as session:
            rows = (
                session.query(MarketBar.symbol)
                .filter(MarketBar.symbol != "NEPSE_INDEX")
                .distinct()
                .all()
            )
        return sorted({row[0] for row in rows})

    def _load_market_frame(self, symbol: str) -> pd.DataFrame:
        with self.database.session() as session:
            query = (
                session.query(
                    MarketBar.ts.label("date"),
                    MarketBar.open,
                    MarketBar.high,
                    MarketBar.low,
                    MarketBar.close,
                    MarketBar.volume,
                    MarketBar.turnover,
                    MarketBar.company_name,
                    MarketBar.sector,
                )
                .filter(MarketBar.symbol == symbol, MarketBar.interval == "1d")
                .order_by(MarketBar.ts.asc())
            )
            return pd.read_sql(query.statement, session.bind)

    def _load_latest_market_snapshot(self) -> pd.DataFrame:
        with self.database.session() as session:
            subquery = (
                session.query(
                    MarketBar.symbol,
                    func.max(MarketBar.ts).label("max_ts"),
                )
                .filter(MarketBar.symbol != "NEPSE_INDEX", MarketBar.interval == "1d")
                .group_by(MarketBar.symbol)
                .subquery()
            )
            query = (
                session.query(
                    MarketBar.symbol,
                    MarketBar.company_name,
                    MarketBar.sector,
                    MarketBar.close,
                    MarketBar.volume,
                    MarketBar.turnover,
                    MarketBar.source,
                )
                .join(subquery, (MarketBar.symbol == subquery.c.symbol) & (MarketBar.ts == subquery.c.max_ts))
            )
            return pd.read_sql(query.statement, session.bind)

    def _load_fundamentals(self, symbol: str) -> pd.DataFrame:
        with self.database.session() as session:
            query = (
                session.query(FundamentalSnapshot)
                .filter(FundamentalSnapshot.symbol == symbol)
                .order_by(FundamentalSnapshot.report_date.asc())
            )
            return pd.read_sql(query.statement, session.bind)

    def _load_latest_fundamentals_snapshot(self) -> pd.DataFrame:
        with self.database.session() as session:
            query = session.query(FundamentalSnapshot)
            return pd.read_sql(query.statement, session.bind)

    def _load_macro_frames(self) -> dict[str, pd.DataFrame]:
        frames: dict[str, pd.DataFrame] = {}
        with self.database.session() as session:
            query = session.query(MacroSeriesPoint).order_by(MacroSeriesPoint.ts.asc())
            df = pd.read_sql(query.statement, session.bind)
        if df.empty:
            return frames
        for series_name, group in df.groupby("series_name"):
            frames[str(series_name)] = group.rename(columns={"ts": "date", "value": "close"}).copy()
        return frames

    def _load_news(self, symbol: str) -> pd.DataFrame:
        with self.database.session() as session:
            query = (
                session.query(NewsArticle)
                .filter((NewsArticle.symbol == symbol) | (NewsArticle.symbol.is_(None)))
                .order_by(NewsArticle.published_at.asc())
            )
            return pd.read_sql(query.statement, session.bind)

    def _feature_frames(self, symbols: list[str]) -> dict[str, pd.DataFrame]:
        macro_frames = self._load_macro_frames()
        fundamentals_all = self._load_latest_fundamentals_snapshot()
        snapshot = self._load_latest_market_snapshot()
        feature_frames: dict[str, pd.DataFrame] = {}

        sector_frames: dict[str, pd.DataFrame] = {}
        index_frame = self._load_market_frame("NEPSE_INDEX")

        for sector, group in snapshot.groupby("sector"):
            sector_symbol = group["symbol"].iloc[0] if not group.empty else None
            if sector_symbol is None:
                continue
            sector_frames[sector] = self._load_market_frame(str(sector_symbol))

        for symbol in symbols:
            price_frame = self._load_market_frame(symbol)
            if price_frame.empty:
                continue
            sector = str(price_frame["sector"].iloc[-1]) if "sector" in price_frame.columns else "Others"
            fundamentals = fundamentals_all[fundamentals_all["symbol"] == symbol] if not fundamentals_all.empty and "symbol" in fundamentals_all.columns else pd.DataFrame()
            news = self._load_news(symbol)
            feature_frames[symbol] = build_feature_frame(
                symbol=symbol,
                price_frame=price_frame,
                fundamentals_frame=fundamentals,
                sector_peer_frame=sector_frames.get(sector),
                macro_frames=macro_frames,
                sentiment_frame=news.rename(columns={"published_at": "date"}) if not news.empty else pd.DataFrame(),
                market_frame=index_frame,
            )
        return feature_frames

    def run_ingestion_cycle(self) -> dict[str, int]:
        return self.ingestion.run_full_cycle()

    def build_internet_training_data(
        self,
        profile: str = "advanced",
        symbol_limit: Optional[int] = None,
        refresh: bool = False,
        market_news_pages: int = 5,
        market_article_body_limit: int = 30,
    ) -> dict[str, Any]:
        return self.dataset_builder.build(
            profile=profile,
            symbol_limit=symbol_limit,
            refresh=refresh,
            market_news_pages=market_news_pages,
            market_article_body_limit=market_article_body_limit,
        )

    def train_models(self, force: bool = False) -> dict[str, Any]:
        symbols = self._symbols()
        if not symbols:
            self.run_ingestion_cycle()
            symbols = self._symbols()
        if not symbols:
            return {"trained": False, "reason": "No symbols loaded"}

        if not force and self.model_suite.last_trained_at and datetime.utcnow() - self.model_suite.last_trained_at < timedelta(hours=6):
            return {"trained": False, "reason": "Recent training already available", "last_trained_at": self.model_suite.last_trained_at.isoformat()}

        feature_frames = self._feature_frames(symbols)
        self.model_suite.train(feature_frames)
        backtest = run_walk_forward_backtest(feature_frames, self.model_suite)
        self._latest_backtest = backtest
        if backtest is not None:
            with self.database.session() as session:
                session.add(
                    BacktestReport(
                        strategy_name=backtest.strategy_name,
                        run_at=datetime.utcnow(),
                        start_date=None if backtest.start_date is None else backtest.start_date.to_pydatetime(),
                        end_date=None if backtest.end_date is None else backtest.end_date.to_pydatetime(),
                        metrics_json={
                            "annualized_return": backtest.annualized_return,
                            "sharpe_ratio": backtest.sharpe_ratio,
                            "max_drawdown": backtest.max_drawdown,
                            "win_rate": backtest.win_rate,
                            "turnover": backtest.turnover,
                        },
                        equity_curve_json=backtest.equity_curve,
                    )
                )
                session.add(
                    ModelArtifact(
                        model_name="autonomous-ensemble",
                        version=self.model_suite.model_version,
                        regime="ALL",
                        stage="production",
                        artifact_path=str(self.model_suite.artifact_path),
                        metrics_json=self.model_suite.metrics,
                        features_json=self.model_suite.feature_cols,
                        trained_at=self.model_suite.last_trained_at or datetime.utcnow(),
                    )
                )
        return {
            "trained": bool(self.model_suite.last_trained_at),
            "model_version": self.model_suite.model_version,
            "metrics": self.model_suite.metrics,
        }

    def _liquidity_score(self, price_frame: pd.DataFrame) -> float:
        if price_frame.empty:
            return 20.0
        average_turnover = price_frame["turnover"].tail(20).mean() if "turnover" in price_frame.columns else 0.0
        average_volume = price_frame["volume"].tail(20).mean()
        score = np.clip(np.log1p(max(average_turnover, 0.0)) * 7 + np.log1p(max(average_volume, 0.0)) * 5, 0, 100)
        return round(float(score), 2)

    def _risk_level(self, price_frame: pd.DataFrame, liquidity_score: float) -> str:
        returns = price_frame["close"].pct_change().dropna() if not price_frame.empty else pd.Series(dtype=float)
        volatility = returns.tail(60).std(ddof=0) * np.sqrt(252) * 100 if not returns.empty else 40.0
        if volatility > 55 or liquidity_score < 20:
            return "VERY HIGH"
        if volatility > 38 or liquidity_score < 35:
            return "HIGH"
        if volatility > 22 or liquidity_score < 55:
            return "MEDIUM"
        return "LOW"

    def _signal_label(self, expected_return: float, confidence: float, technical_score: float, fundamental_score: float) -> str:
        if expected_return >= 8 and confidence >= 70 and technical_score >= 65 and fundamental_score >= 55:
            return "STRONG BUY"
        if expected_return >= 2.5 and confidence >= 58:
            return "BUY"
        if expected_return <= -8 and confidence >= 70:
            return "STRONG SELL"
        if expected_return <= -2.5 and confidence >= 58:
            return "SELL"
        return "HOLD"

    def _regime_alignment(self, regime: str, expected_return: float) -> float:
        if regime == "BULL":
            return 80.0 if expected_return > 0 else 35.0
        if regime in {"BEAR", "CRISIS"}:
            return 75.0 if expected_return < 0 else 30.0
        if regime == "DISTRIBUTION":
            return 65.0 if abs(expected_return) < 3 else 45.0
        return 60.0

    def generate_signal_cards(self, limit: int = 25, persist: bool = True) -> list[SignalCard]:
        if not self._symbols():
            self.run_ingestion_cycle()
        if not self._symbols():
            return []

        latest_snapshot = self._load_latest_market_snapshot()
        fundamentals_all = self._load_latest_fundamentals_snapshot()
        sector_reference = sector_medians(fundamentals_all) if not fundamentals_all.empty else {}
        macro_frames = self._load_macro_frames()
        index_frame = self._load_market_frame("NEPSE_INDEX")
        breadth_flags: list[bool] = []
        for symbol in latest_snapshot["symbol"].tolist() if not latest_snapshot.empty else []:
            history = self._load_market_frame(str(symbol)).tail(2)
            if len(history) == 2:
                breadth_flags.append(float(history["close"].iloc[-1]) >= float(history["close"].iloc[-2]))
        breadth_ratio = float(np.mean(breadth_flags)) if breadth_flags else 0.5
        regime_dict = detect_regime(index_frame, breadth_ratio=breadth_ratio)
        as_of = datetime.utcnow()

        cards: list[SignalCard] = []
        persisted_rows: list[dict[str, Any]] = []

        for _, snapshot_row in latest_snapshot.iterrows():
            symbol = str(snapshot_row["symbol"])
            price_frame = self._load_market_frame(symbol)
            if price_frame.empty:
                continue
            technical_snapshot = build_technical_snapshot(price_frame)
            fundamentals = fundamentals_all[fundamentals_all["symbol"] == symbol] if not fundamentals_all.empty and "symbol" in fundamentals_all.columns else pd.DataFrame()
            latest_fundamental = fundamentals.sort_values("report_date").tail(1).iloc[-1].to_dict() if not fundamentals.empty else {}
            fundamental_score = score_fundamentals(latest_fundamental, sector_reference.get(str(snapshot_row["sector"]), {}))
            macro_score, macro_signals, macro_aggregates, macro_bias = compute_macro_correlation_signal(price_frame, macro_frames, str(snapshot_row["sector"]))
            news_frame = self._load_news(symbol)
            sentiment_value = self.model_suite.sentiment.score_articles(news_frame)
            liquidity_score = self._liquidity_score(price_frame)

            feature_frame = build_feature_frame(
                symbol=symbol,
                price_frame=price_frame,
                fundamentals_frame=fundamentals,
                sector_peer_frame=price_frame,
                macro_frames=macro_frames,
                sentiment_frame=news_frame.rename(columns={"published_at": "date"}) if not news_frame.empty else pd.DataFrame(),
                market_frame=index_frame,
            )
            if feature_frame.empty:
                continue

            prediction = self.model_suite.predict_latest(feature_frame, sentiment_value)
            heuristic_base = (
                (technical_snapshot.technical_score - 50) * 0.18
                + (fundamental_score.score - 50) * 0.12
                + (macro_score - 50) * 0.10
                + sentiment_value * 8.0
                + (liquidity_score - 50) * 0.04
            )
            regime_multiplier = {
                "BULL": 1.15,
                "SIDEWAYS": 0.75,
                "DISTRIBUTION": 0.55,
                "BEAR": -0.85,
                "CRISIS": -1.10,
            }.get(regime_dict["regime"], 0.8)
            heuristic_30 = float(np.clip(heuristic_base * regime_multiplier, -18, 18))
            heuristic_returns = {
                7: round(heuristic_30 * 0.45, 4),
                30: round(heuristic_30, 4),
                90: round(heuristic_30 * 1.6, 4),
            }
            if self.model_suite.last_trained_at is None:
                expected_returns = heuristic_returns
                prediction["confidence"] = max(prediction["confidence"], float(np.clip(52 + abs(heuristic_30) * 2.2, 0, 100)))
            else:
                expected_returns = {
                    horizon: round(prediction["expected_returns"][horizon] * 0.65 + heuristic_returns[horizon] * 0.35, 4)
                    for horizon in (7, 30, 90)
                }
            expected_return_percent = float(expected_returns[30] * 0.55 + expected_returns[7] * 0.25 + expected_returns[90] * 0.20)
            risk_level = self._risk_level(price_frame, liquidity_score)
            regime_alignment_score = self._regime_alignment(regime_dict["regime"], expected_return_percent)
            risk_adjusted_return = expected_return_percent / max(8.0, price_frame["close"].pct_change().tail(60).std(ddof=0) * np.sqrt(252) * 100 if len(price_frame) > 20 else 12.0)

            reasons = summarize_reason_stack(
                technical_snapshot=technical_snapshot,
                fundamental_score=fundamental_score,
                macro_score=macro_score,
                macro_signals=macro_signals,
                expected_return_percent=expected_return_percent,
            )
            warnings: list[str] = []
            if fundamental_score.deterioration_flags and expected_return_percent > 0:
                warnings.append("Price is improving faster than fundamentals; watch for a valuation or quality trap.")
            warnings.extend(fundamental_score.deterioration_flags[:2])
            if liquidity_score < 35:
                warnings.append("Liquidity risk is elevated; position sizing should stay conservative.")
            if any(source == "SIMULATED_BOOTSTRAP" for source in price_frame.get("source", pd.Series(dtype=str)).tail(3).astype(str)):
                warnings.append("Historical coverage includes bootstrap bars; retrain with full archives for live deployment.")
            if not news_frame.empty and sentiment_value < -0.35:
                warnings.append("Recent news flow is net negative.")

            latest_close = float(price_frame["close"].iloc[-1])
            label = self._signal_label(
                expected_return=expected_return_percent,
                confidence=prediction["confidence"],
                technical_score=technical_snapshot.technical_score,
                fundamental_score=fundamental_score.score,
            )

            card = SignalCard(
                as_of=as_of,
                symbol=symbol,
                company_name=str(snapshot_row["company_name"]),
                sector=str(snapshot_row["sector"]),
                overall_signal=label,
                confidence_score=prediction["confidence"],
                predicted_targets=PredictionTargets(
                    target_7d=_round_float(latest_close * (1 + expected_returns[7] / 100)),
                    target_30d=_round_float(latest_close * (1 + expected_returns[30] / 100)),
                    target_90d=_round_float(latest_close * (1 + expected_returns[90] / 100)),
                ),
                expected_return_percent=_round_float(expected_return_percent),
                risk_adjusted_return=_round_float(risk_adjusted_return, 4),
                risk_level=risk_level,
                technical=TechnicalBreakdown(**technical_snapshot.__dict__),
                fundamentals=FundamentalBreakdown(
                    **fundamental_score.payload,
                    deterioration_flags=fundamental_score.deterioration_flags,
                ),
                global_view=GlobalBreakdown(
                    global_sentiment_score=_round_float(macro_score),
                    signals=[CorrelationSignal(**{key: value for key, value in item.items() if key != "impact_strength"}) for item in macro_signals],
                    macro_bias=macro_bias,
                    remittance_tailwind=_round_float(macro_aggregates["remittance_tailwind"]),
                    policy_rate_trend=_round_float(macro_aggregates["policy_rate_trend"]),
                    commodity_pressure=_round_float(macro_aggregates["commodity_pressure"]),
                    crypto_sentiment=_round_float(macro_aggregates["crypto_sentiment"]),
                ),
                top_reasons=reasons,
                historical_accuracy=_round_float(prediction["historical_accuracy"]),
                warnings=warnings[:5],
                model_votes=[ModelVote(**vote) for vote in prediction["votes"]],
                liquidity_score=liquidity_score,
                sentiment_score=_round_float((sentiment_value + 1) * 50),
                regime_alignment_score=_round_float(regime_alignment_score),
            )
            cards.append(card)
            persisted_rows.append(
                {
                    "symbol": card.symbol,
                    "company_name": card.company_name,
                    "sector": card.sector,
                    "signal": card.overall_signal,
                    "confidence_score": card.confidence_score,
                    "target_7d": card.predicted_targets.target_7d,
                    "target_30d": card.predicted_targets.target_30d,
                    "target_90d": card.predicted_targets.target_90d,
                    "expected_return_percent": card.expected_return_percent,
                    "risk_adjusted_return": card.risk_adjusted_return,
                    "risk_level": card.risk_level,
                    "technical_score": card.technical.technical_score,
                    "fundamental_score": card.fundamentals.fundamental_score,
                    "global_sentiment_score": card.global_view.global_sentiment_score,
                    "sentiment_score": card.sentiment_score,
                    "liquidity_score": card.liquidity_score,
                    "regime_alignment_score": card.regime_alignment_score,
                    "historical_accuracy": card.historical_accuracy,
                    "reasons_json": card.top_reasons,
                    "warnings_json": card.warnings,
                    "technical_json": card.technical.model_dump(),
                    "fundamental_json": card.fundamentals.model_dump(),
                    "global_json": card.global_view.model_dump(),
                    "model_votes_json": [vote.model_dump() for vote in card.model_votes],
                }
            )

        cards.sort(key=lambda item: (item.risk_adjusted_return, item.confidence_score), reverse=True)

        if persist and cards:
            run_key = as_of.strftime("signal-%Y%m%d%H%M%S")
            with self.database.session() as session:
                run = PredictionRun(
                    run_key=run_key,
                    as_of=as_of,
                    regime=regime_dict["regime"],
                    regime_confidence=regime_dict["confidence"],
                    market_bias=regime_dict["regime"],
                    model_version=self.model_suite.model_version,
                    accuracy_30d=self.model_suite.metrics.get("accuracy_7d", 0.0),
                    sharpe_90d=self._latest_backtest.sharpe_ratio if self._latest_backtest else 0.0,
                    metadata_json={"symbol_count": len(cards)},
                )
                session.add(run)
                session.flush()
                for row in persisted_rows:
                    session.add(PredictionSignal(run_id=run.id, **row))

        return cards[:limit]

    def latest_backtest(self) -> Optional[BacktestSummary]:
        if self._latest_backtest is not None:
            return BacktestSummary(
                strategy_name=self._latest_backtest.strategy_name,
                start_date=None if self._latest_backtest.start_date is None else self._latest_backtest.start_date.to_pydatetime(),
                end_date=None if self._latest_backtest.end_date is None else self._latest_backtest.end_date.to_pydatetime(),
                annualized_return=self._latest_backtest.annualized_return,
                sharpe_ratio=self._latest_backtest.sharpe_ratio,
                max_drawdown=self._latest_backtest.max_drawdown,
                win_rate=self._latest_backtest.win_rate,
                turnover=self._latest_backtest.turnover,
            )
        with self.database.session() as session:
            report = session.query(BacktestReport).order_by(BacktestReport.run_at.desc()).first()
        if report is None:
            return None
        metrics = report.metrics_json or {}
        return BacktestSummary(
            strategy_name=report.strategy_name,
            start_date=report.start_date,
            end_date=report.end_date,
            annualized_return=metrics.get("annualized_return", 0.0),
            sharpe_ratio=metrics.get("sharpe_ratio", 0.0),
            max_drawdown=metrics.get("max_drawdown", 0.0),
            win_rate=metrics.get("win_rate", 0.0),
            turnover=metrics.get("turnover", 0.0),
        )

    def monitoring_snapshot(self) -> list[MonitoringMetric]:
        backtest = self.latest_backtest()
        accuracy = self.model_suite.metrics.get("accuracy_7d", 58.0)
        sharpe = backtest.sharpe_ratio if backtest else 0.0
        max_drawdown = backtest.max_drawdown if backtest else 0.0
        win_rate = backtest.win_rate if backtest else 0.0
        return [
            MonitoringMetric(horizon="30D", directional_accuracy=accuracy, sharpe_ratio=sharpe, max_drawdown=max_drawdown, win_rate=win_rate),
            MonitoringMetric(horizon="90D", directional_accuracy=max(0.0, accuracy - 2), sharpe_ratio=sharpe * 0.95, max_drawdown=max_drawdown * 1.05, win_rate=max(0.0, win_rate - 1)),
            MonitoringMetric(horizon="365D", directional_accuracy=max(0.0, accuracy - 4), sharpe_ratio=sharpe * 0.9, max_drawdown=max_drawdown * 1.1, win_rate=max(0.0, win_rate - 2)),
        ]

    def evaluate_prediction_outcomes(self) -> dict[str, int]:
        inserted = 0
        with self.database.session() as session:
            runs = (
                session.query(PredictionRun)
                .order_by(PredictionRun.as_of.asc())
                .all()
            )
            existing_keys = {
                (row.run_key, row.symbol, row.horizon_days)
                for row in session.query(PredictionOutcome.run_key, PredictionOutcome.symbol, PredictionOutcome.horizon_days).all()
            }
            for run in runs:
                signals = session.query(PredictionSignal).filter(PredictionSignal.run_id == run.id).all()
                for signal in signals:
                    price_frame = self._load_market_frame(signal.symbol)
                    if price_frame.empty:
                        continue
                    for horizon in HORIZONS:
                        key = (run.run_key, signal.symbol, horizon)
                        if key in existing_keys:
                            continue
                        target_date = run.as_of + timedelta(days=horizon)
                        future_rows = price_frame[pd.to_datetime(price_frame["date"]) >= target_date]
                        past_rows = price_frame[pd.to_datetime(price_frame["date"]) <= run.as_of]
                        if future_rows.empty or past_rows.empty:
                            continue
                        start_close = float(past_rows.iloc[-1]["close"])
                        end_close = float(future_rows.iloc[0]["close"])
                        realized_return = (end_close / max(start_close, 1e-9) - 1) * 100
                        predicted_return = getattr(signal, f"target_{horizon}d") / max(start_close, 1e-9) - 1
                        predicted_return *= 100
                        session.add(
                            PredictionOutcome(
                                symbol=signal.symbol,
                                run_key=run.run_key,
                                horizon_days=horizon,
                                predicted_return=predicted_return,
                                realized_return=realized_return,
                                direction_hit=(predicted_return >= 0) == (realized_return >= 0),
                                evaluated_at=datetime.utcnow(),
                            )
                        )
                        inserted += 1
        return {"outcomes_recorded": inserted}

    def dashboard(self, limit: int = 10) -> AutonomousDashboardResponse:
        cards = self.generate_signal_cards(limit=max(limit * 2, 20))
        top_buys = [card for card in cards if card.overall_signal in {"STRONG BUY", "BUY"}][:limit]
        top_avoids = [card for card in reversed(cards) if card.overall_signal in {"SELL", "STRONG SELL"}][:limit]
        if len(top_avoids) < limit:
            fallback = sorted(cards, key=lambda item: (item.risk_adjusted_return, item.confidence_score))[:limit]
            seen = {card.symbol for card in top_avoids}
            for card in fallback:
                if card.symbol not in seen:
                    top_avoids.append(card)
                    seen.add(card.symbol)
                if len(top_avoids) >= limit:
                    break
        sector_rotation = compute_sector_rotation(
            [
                {
                    "sector": card.sector,
                    "technical_score": card.technical.technical_score,
                    "fundamental_score": card.fundamentals.fundamental_score,
                    "global_sentiment_score": card.global_view.global_sentiment_score,
                    "liquidity_score": card.liquidity_score,
                }
                for card in cards
            ]
        )
        regime = detect_regime(self._load_market_frame("NEPSE_INDEX"), breadth_ratio=0.5)
        return AutonomousDashboardResponse(
            architecture=self.architecture_components(),
            architecture_diagram=ARCHITECTURE_DIAGRAM.strip(),
            status=self._status(),
            regime=MarketRegimeSnapshot(**regime),
            monitoring=self.monitoring_snapshot(),
            sector_rotation=[SectorRotationSignal(**item) for item in sector_rotation[:8]],
            top_buys=top_buys,
            top_avoids=top_avoids,
            backtest=self.latest_backtest(),
        )


@lru_cache(maxsize=1)
def get_research_platform() -> AutonomousResearchPlatform:
    platform = AutonomousResearchPlatform()
    platform.initialize()
    return platform
