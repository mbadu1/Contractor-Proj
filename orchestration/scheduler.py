"""APScheduler-based autonomous RevWatch loop."""

from __future__ import annotations

import logging
from pathlib import Path

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from db.repository import RevWatchRepository
from orchestration.jobs import (
    job_daily_signal_ingestion,
    job_monthly_retrain_and_validate,
    job_weekly_reestimation,
)

logger = logging.getLogger("revwatch.scheduler")


def create_scheduler(
    db_path: str | Path = "data/revwatch.duckdb",
) -> BlockingScheduler:
    """
    Build the autonomous job schedule:

    - Daily 02:00 UTC  — signal ingestion
    - Weekly Mon 03:00 — re-estimation with promoted model
    - Monthly 1st 04:00 — retrain + validation gate (promote if MAPE OK)
    """
    repo = RevWatchRepository(db_path)
    scheduler = BlockingScheduler(timezone="UTC")

    scheduler.add_job(
        lambda: job_daily_signal_ingestion(repo),
        CronTrigger(hour=2, minute=0),
        id="daily_signal_ingestion",
        name="Daily signal ingestion",
        replace_existing=True,
    )
    scheduler.add_job(
        lambda: job_weekly_reestimation(repo),
        CronTrigger(day_of_week="mon", hour=3, minute=0),
        id="weekly_reestimation",
        name="Weekly re-estimation",
        replace_existing=True,
    )
    scheduler.add_job(
        lambda: job_monthly_retrain_and_validate(repo),
        CronTrigger(day=1, hour=4, minute=0),
        id="monthly_retrain_validate",
        name="Monthly retrain + validation gate",
        replace_existing=True,
    )

    logger.info(
        "Scheduler configured: daily ingestion @02:00, "
        "weekly re-estimation Mon@03:00, monthly retrain 1st@04:00 UTC"
    )
    return scheduler


def run_scheduler(db_path: str | Path = "data/revwatch.duckdb") -> None:
    """Start the blocking scheduler (long-running process)."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    scheduler = create_scheduler(db_path)
    logger.info("RevWatch autonomous scheduler starting …")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped")
        scheduler.shutdown(wait=False)
