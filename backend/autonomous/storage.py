"""
Persistence layer for the autonomous research platform.
"""

from __future__ import annotations

import json
import logging
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Iterable, Iterator, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    func,
    select,
)
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, declarative_base, relationship, sessionmaker

from ..settings import Settings, get_settings

logger = logging.getLogger("nepse-alpha.autonomous.storage")

Base = declarative_base()


class MarketBar(Base):
    __tablename__ = "market_bars"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(24), nullable=False, index=True)
    company_name = Column(String(255), nullable=False, default="")
    sector = Column(String(80), nullable=False, default="Others")
    interval = Column(String(12), nullable=False, default="1d")
    ts = Column(DateTime, nullable=False, index=True)
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(Float, nullable=False, default=0.0)
    turnover = Column(Float, nullable=False, default=0.0)
    source = Column(String(40), nullable=False, default="IMPORT")
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("symbol", "interval", "ts", name="uq_market_bars_symbol_interval_ts"),
        Index("ix_market_bars_symbol_ts", "symbol", "ts"),
    )


class FundamentalSnapshot(Base):
    __tablename__ = "fundamental_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(24), nullable=False, index=True)
    company_name = Column(String(255), nullable=False, default="")
    sector = Column(String(80), nullable=False, default="Others")
    fiscal_period = Column(String(40), nullable=False, default="")
    report_date = Column(DateTime, nullable=False, index=True)
    eps = Column(Float, nullable=False, default=0.0)
    pe = Column(Float, nullable=False, default=0.0)
    pb = Column(Float, nullable=False, default=0.0)
    dividend_yield = Column(Float, nullable=False, default=0.0)
    revenue = Column(Float, nullable=False, default=0.0)
    revenue_growth_yoy = Column(Float, nullable=False, default=0.0)
    revenue_growth_qoq = Column(Float, nullable=False, default=0.0)
    net_profit = Column(Float, nullable=False, default=0.0)
    net_profit_margin = Column(Float, nullable=False, default=0.0)
    roe = Column(Float, nullable=False, default=0.0)
    roa = Column(Float, nullable=False, default=0.0)
    debt_to_equity = Column(Float, nullable=False, default=0.0)
    current_ratio = Column(Float, nullable=False, default=0.0)
    quick_ratio = Column(Float, nullable=False, default=0.0)
    book_value_per_share = Column(Float, nullable=False, default=0.0)
    npl_ratio = Column(Float, nullable=True)
    casa_ratio = Column(Float, nullable=True)
    raw_payload = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("symbol", "report_date", "fiscal_period", name="uq_fundamentals_symbol_period"),
        Index("ix_fundamentals_symbol_report_date", "symbol", "report_date"),
    )


class MacroSeriesPoint(Base):
    __tablename__ = "macro_series_points"

    id = Column(Integer, primary_key=True, autoincrement=True)
    series_name = Column(String(80), nullable=False, index=True)
    ts = Column(DateTime, nullable=False, index=True)
    value = Column(Float, nullable=False)
    units = Column(String(40), nullable=False, default="")
    source = Column(String(40), nullable=False, default="IMPORT")
    metadata_json = Column(JSON, nullable=False, default=dict)

    __table_args__ = (
        UniqueConstraint("series_name", "ts", name="uq_macro_series_name_ts"),
        Index("ix_macro_series_name_ts", "series_name", "ts"),
    )


class NewsArticle(Base):
    __tablename__ = "news_articles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String(80), nullable=False, default="")
    source_url = Column(String(500), nullable=False, unique=True)
    symbol = Column(String(24), nullable=True, index=True)
    language = Column(String(16), nullable=False, default="en")
    title = Column(Text, nullable=False, default="")
    body = Column(Text, nullable=False, default="")
    published_at = Column(DateTime, nullable=False, index=True)
    sentiment_score = Column(Float, nullable=False, default=0.0)
    entities_json = Column(JSON, nullable=False, default=list)
    created_at = Column(DateTime, nullable=False, server_default=func.now())


class ModelArtifact(Base):
    __tablename__ = "model_artifacts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    model_name = Column(String(80), nullable=False, index=True)
    version = Column(String(80), nullable=False, index=True)
    regime = Column(String(32), nullable=False, default="ALL")
    stage = Column(String(32), nullable=False, default="production")
    artifact_path = Column(String(500), nullable=False)
    metrics_json = Column(JSON, nullable=False, default=dict)
    features_json = Column(JSON, nullable=False, default=list)
    trained_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class PredictionRun(Base):
    __tablename__ = "prediction_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_key = Column(String(80), nullable=False, unique=True, index=True)
    as_of = Column(DateTime, nullable=False, index=True)
    regime = Column(String(32), nullable=False, default="SIDEWAYS")
    regime_confidence = Column(Float, nullable=False, default=50.0)
    market_bias = Column(String(32), nullable=False, default="NEUTRAL")
    model_version = Column(String(80), nullable=False, default="bootstrap")
    accuracy_30d = Column(Float, nullable=False, default=0.0)
    sharpe_90d = Column(Float, nullable=False, default=0.0)
    metadata_json = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    signals = relationship("PredictionSignal", back_populates="run")


class PredictionSignal(Base):
    __tablename__ = "prediction_signals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(Integer, ForeignKey("prediction_runs.id"), nullable=False, index=True)
    symbol = Column(String(24), nullable=False, index=True)
    company_name = Column(String(255), nullable=False, default="")
    sector = Column(String(80), nullable=False, default="Others")
    signal = Column(String(20), nullable=False)
    confidence_score = Column(Float, nullable=False, default=0.0)
    target_7d = Column(Float, nullable=False, default=0.0)
    target_30d = Column(Float, nullable=False, default=0.0)
    target_90d = Column(Float, nullable=False, default=0.0)
    expected_return_percent = Column(Float, nullable=False, default=0.0)
    risk_adjusted_return = Column(Float, nullable=False, default=0.0)
    risk_level = Column(String(20), nullable=False, default="MEDIUM")
    technical_score = Column(Float, nullable=False, default=0.0)
    fundamental_score = Column(Float, nullable=False, default=0.0)
    global_sentiment_score = Column(Float, nullable=False, default=0.0)
    sentiment_score = Column(Float, nullable=False, default=0.0)
    liquidity_score = Column(Float, nullable=False, default=0.0)
    regime_alignment_score = Column(Float, nullable=False, default=0.0)
    historical_accuracy = Column(Float, nullable=False, default=0.0)
    reasons_json = Column(JSON, nullable=False, default=list)
    warnings_json = Column(JSON, nullable=False, default=list)
    technical_json = Column(JSON, nullable=False, default=dict)
    fundamental_json = Column(JSON, nullable=False, default=dict)
    global_json = Column(JSON, nullable=False, default=dict)
    model_votes_json = Column(JSON, nullable=False, default=list)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    run = relationship("PredictionRun", back_populates="signals")


class BacktestReport(Base):
    __tablename__ = "backtest_reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    strategy_name = Column(String(80), nullable=False, index=True)
    run_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    start_date = Column(DateTime, nullable=True)
    end_date = Column(DateTime, nullable=True)
    metrics_json = Column(JSON, nullable=False, default=dict)
    equity_curve_json = Column(JSON, nullable=False, default=list)


class PredictionOutcome(Base):
    __tablename__ = "prediction_outcomes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(24), nullable=False, index=True)
    run_key = Column(String(80), nullable=False, index=True)
    horizon_days = Column(Integer, nullable=False)
    predicted_return = Column(Float, nullable=False)
    realized_return = Column(Float, nullable=False, default=0.0)
    direction_hit = Column(Boolean, nullable=False, default=False)
    evaluated_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)


class AutonomousDatabase:
    """Database manager with TimescaleDB-aware initialization."""

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or get_settings()
        connect_args = {"check_same_thread": False} if self.settings.database_url.startswith("sqlite") else {}
        self.engine: Engine = create_engine(
            self.settings.database_url,
            future=True,
            pool_pre_ping=True,
            connect_args=connect_args,
        )
        self.SessionLocal = sessionmaker(
            bind=self.engine,
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
            future=True,
        )

    @property
    def dialect_name(self) -> str:
        return self.engine.dialect.name

    @property
    def is_timescaledb_active(self) -> bool:
        return self.dialect_name == "postgresql" and self.settings.timescaledb_enabled

    def initialize(self) -> None:
        Base.metadata.create_all(self.engine)
        if not self.is_timescaledb_active:
            return

        try:
            with self.engine.begin() as conn:
                conn.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS timescaledb")
                conn.exec_driver_sql(
                    "SELECT create_hypertable('market_bars', 'ts', if_not_exists => TRUE)"
                )
                conn.exec_driver_sql(
                    "SELECT create_hypertable('macro_series_points', 'ts', if_not_exists => TRUE)"
                )
        except Exception as exc:
            logger.warning("TimescaleDB activation skipped: %s", exc)

    @contextmanager
    def session(self) -> Iterator[Session]:
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def bulk_upsert(
        self,
        session: Session,
        model: type[Base],
        records: Iterable[dict[str, Any]],
        key_columns: list[str],
    ) -> None:
        records = list(records)
        if not records:
            return

        table = model.__table__
        update_columns = [
            column.name
            for column in table.columns
            if column.name not in key_columns and column.name not in {"id", "created_at"}
        ]
        chunk_size = 250 if self.dialect_name == "sqlite" else 1000

        for start in range(0, len(records), chunk_size):
            chunk = records[start:start + chunk_size]
            self._execute_upsert(session, model, table, chunk, key_columns, update_columns)

    def _execute_upsert(
        self,
        session: Session,
        model: type[Base],
        table: Any,
        records: list[dict[str, Any]],
        key_columns: list[str],
        update_columns: list[str],
    ) -> None:
        if self.dialect_name == "postgresql":
            statement = pg_insert(table).values(records)
            excluded = statement.excluded
            session.execute(
                statement.on_conflict_do_update(
                    index_elements=key_columns,
                    set_={column: getattr(excluded, column) for column in update_columns},
                )
            )
            return

        if self.dialect_name == "sqlite":
            statement = sqlite_insert(table).values(records)
            excluded = statement.excluded
            session.execute(
                statement.on_conflict_do_update(
                    index_elements=key_columns,
                    set_={column: getattr(excluded, column) for column in update_columns},
                )
            )
            return

        for record in records:
            session.merge(model(**record))

    def latest_timestamp(self, session: Session, table: type[Base], column_name: str = "ts") -> Optional[datetime]:
        column = getattr(table, column_name)
        return session.execute(select(func.max(column))).scalar_one_or_none()

    def counts(self) -> dict[str, int]:
        with self.session() as session:
            return {
                "bars": session.query(MarketBar).count(),
                "fundamentals": session.query(FundamentalSnapshot).count(),
                "macro_points": session.query(MacroSeriesPoint).count(),
                "news_articles": session.query(NewsArticle).count(),
                "prediction_runs": session.query(PredictionRun).count(),
            }


_database: Optional[AutonomousDatabase] = None


def get_database() -> AutonomousDatabase:
    global _database
    if _database is None:
        _database = AutonomousDatabase()
    return _database
