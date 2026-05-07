"""
Celery tasks and schedules for the autonomous NEPSE platform.
"""

from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from ..settings import get_settings
from .service import get_research_platform

settings = get_settings()

celery_app = Celery(
    "nepse_autonomous",
    broker=settings.redis_url,
    backend=settings.redis_url,
)
celery_app.conf.timezone = settings.scheduler_timezone
celery_app.conf.beat_schedule = {
    "market-hours-research-cycle": {
        "task": "backend.autonomous.tasks.run_market_hours_cycle",
        "schedule": crontab(minute=f"*/{settings.market_rescore_minutes}", hour=f"{settings.market_open_hour}-{settings.market_close_hour}"),
    },
    "off-hours-refresh-cycle": {
        "task": "backend.autonomous.tasks.run_off_hours_cycle",
        "schedule": crontab(minute=0, hour=f"*/{settings.off_hours_rescore_hours}"),
    },
    "daily-outcome-evaluation": {
        "task": "backend.autonomous.tasks.evaluate_prediction_outcomes",
        "schedule": crontab(minute=20, hour=18),
    },
    "monthly-full-retrain": {
        "task": "backend.autonomous.tasks.run_monthly_retraining",
        "schedule": crontab(minute=15, hour=2, day_of_month="1"),
    },
}


@celery_app.task(name="backend.autonomous.tasks.run_market_hours_cycle")
def run_market_hours_cycle() -> dict:
    platform = get_research_platform()
    ingestion = platform.run_ingestion_cycle()
    training = platform.train_models(force=False)
    dashboard = platform.dashboard(limit=10)
    return {
        "ingestion": ingestion,
        "training": training,
        "signals": len(dashboard.top_buys) + len(dashboard.top_avoids),
    }


@celery_app.task(name="backend.autonomous.tasks.run_off_hours_cycle")
def run_off_hours_cycle() -> dict:
    platform = get_research_platform()
    ingestion = platform.run_ingestion_cycle()
    signals = platform.generate_signal_cards(limit=20)
    return {"ingestion": ingestion, "signals": len(signals)}


@celery_app.task(name="backend.autonomous.tasks.run_monthly_retraining")
def run_monthly_retraining() -> dict:
    platform = get_research_platform()
    return platform.train_models(force=True)


@celery_app.task(name="backend.autonomous.tasks.evaluate_prediction_outcomes")
def evaluate_prediction_outcomes() -> dict:
    platform = get_research_platform()
    return platform.evaluate_prediction_outcomes()
