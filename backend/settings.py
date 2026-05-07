"""
Application settings shared by the autonomous research platform.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the application and autonomous engine."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "NEPSE Autonomous Intelligence Platform"
    environment: str = "development"
    database_url: str = "sqlite:///./backend/autonomous_nepse.db"
    redis_url: str = "redis://localhost:6379/0"
    mlflow_tracking_uri: str = "file:./mlruns"
    model_artifact_dir: str = "./backend/model_artifacts"

    historical_data_dir: str = "./data/market"
    fundamental_data_dir: str = "./data/fundamentals"
    macro_data_dir: str = "./data/macro"
    news_data_dir: str = "./data/news"

    market_open_hour: int = 11
    market_close_hour: int = 15
    market_rescore_minutes: int = 15
    off_hours_rescore_hours: int = 6
    retrain_accuracy_floor: float = 65.0
    transaction_cost_bps: float = 75.0
    bootstrap_sequence_days: int = 260
    default_history_lookback_days: int = 520
    scheduler_timezone: str = "Asia/Kathmandu"
    timescaledb_enabled: bool = True
    allow_bootstrap_simulation: bool = True

    default_macro_series: list[str] = Field(
        default_factory=lambda: [
            "NIFTY50",
            "SENSEX",
            "INDIA_VIX",
            "SP500",
            "NASDAQ",
            "DXY",
            "SHANGHAI",
            "HANG_SENG",
            "CRUDE_OIL",
            "GOLD_USD",
            "GOLD_NPR",
            "NRB_POLICY_RATE",
            "REMITTANCE_GROWTH",
            "BTC_SENTIMENT",
        ]
    )

    def ensure_directories(self) -> None:
        """Create runtime directories used by the platform when missing."""
        for path_value in (
            self.model_artifact_dir,
            self.historical_data_dir,
            self.fundamental_data_dir,
            self.macro_data_dir,
            self.news_data_dir,
        ):
            Path(path_value).mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_directories()
    return settings
