"""Autonomous pipeline jobs — ingestion, re-estimation, retrain + validation gate."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from adapters import (
    AdapterConfig,
    InMemoryBusinessCatalog,
    RegionFilter,
    create_default_adapters,
)
from adapters.intensity import LatentActivityProvider
from db.repository import RevWatchRepository
from engine.estimator import EstimatorConfig
from engine.pipeline import load_businesses, run_estimation_pipeline
from engine.validation import ValidationConfig, run_validation, should_promote

logger = logging.getLogger("revwatch.jobs")

MODELS_DIR = Path("data/models")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _log_run(
    repo: RevWatchRepository,
    job_name: str,
    started: datetime,
    status: str,
    details: dict | None = None,
    error: str | None = None,
) -> None:
    repo.log_pipeline_run(
        job_name=job_name,
        status=status,
        started_at=started,
        finished_at=_now(),
        details=details,
        error_message=error,
    )


def job_daily_signal_ingestion(repo: RevWatchRepository) -> dict:
    """
    Fetch latest signals from all adapters and persist.

    Uses true-revenue intensity when available (synthetic universe);
    otherwise falls back to latent activity.
    """
    started = _now()
    job = "daily_signal_ingestion"
    try:
        businesses = load_businesses(repo)
        if not businesses:
            details = {"observations": 0, "note": "no businesses"}
            _log_run(repo, job, started, "success", details)
            return details

        # Live ingestion uses attribute-based intensity — adapters stay
        # decoupled from ground truth (true_revenue is validation-only).
        intensity = LatentActivityProvider(seed=42)

        catalog = InMemoryBusinessCatalog(businesses)
        # Ingest recent window ending at current month
        until = datetime(_now().year, _now().month, 1, tzinfo=timezone.utc)
        since = datetime(until.year - 1 if until.month == 1 else until.year,
                         12 if until.month == 1 else until.month - 1,
                         1, tzinfo=timezone.utc)
        config = AdapterConfig(
            noise_std=0.14,
            missingness_rate=0.10,
            seed=42,
            until=until,
        )
        adapters = create_default_adapters(
            catalog, intensity=intensity, config=config, seed=42
        )
        observations = []
        for adapter in adapters:
            observations.extend(adapter.fetch(RegionFilter(), since))

        # Avoid duplicates: delete overlapping window then insert
        repo.conn.execute(
            "DELETE FROM signal_observations WHERE timestamp >= ? AND timestamp <= ?",
            [since, until],
        )
        n = repo.insert_signal_observations(observations)
        details = {
            "observations": n,
            "since": since.strftime("%Y-%m"),
            "until": until.strftime("%Y-%m"),
            "businesses": len(businesses),
        }
        _log_run(repo, job, started, "success", details)
        logger.info("daily_signal_ingestion: %s", details)
        return details
    except Exception as exc:
        _log_run(repo, job, started, "failed", error=str(exc))
        logger.exception("daily_signal_ingestion failed")
        raise


def job_weekly_reestimation(repo: RevWatchRepository) -> dict:
    """Re-run estimation with the current promoted model version (or default)."""
    started = _now()
    job = "weekly_reestimation"
    try:
        version = repo.get_promoted_model_version() or "v0.1.0"
        result = run_estimation_pipeline(
            repo,
            EstimatorConfig(model_version=version, seed=42),
        )
        details = {
            "model_version": version,
            "n_train_rows": result.n_train_rows,
            "n_estimates": result.n_predict_rows,
            "n_labeled": len(result.labeling.labeled_business_ids),
        }
        _log_run(repo, job, started, "success", details)
        logger.info("weekly_reestimation: %s", details)
        return details
    except Exception as exc:
        _log_run(repo, job, started, "failed", error=str(exc))
        logger.exception("weekly_reestimation failed")
        raise


def job_monthly_retrain_and_validate(
    repo: RevWatchRepository,
    *,
    candidate_version: str | None = None,
    mape_tolerance: float = 0.05,
) -> dict:
    """
    Retrain a candidate model, validate against true revenue, promote only if
    MAPE does not regress more than mape_tolerance (default 5% relative).
    """
    started = _now()
    job = "monthly_retrain_validate"
    try:
        stamp = started.strftime("%Y%m%d")
        version = candidate_version or f"v0.2.{stamp}"

        # Train candidate
        result = run_estimation_pipeline(
            repo,
            EstimatorConfig(model_version=version, seed=42),
        )
        labeled_ids = {str(bid) for bid in result.labeling.labeled_business_ids}

        # Holdout validation (exclude training businesses)
        report = run_validation(
            repo,
            version,
            ValidationConfig(exclude_business_ids=labeled_ids),
        )

        previous_mape = repo.get_promoted_model_mape()
        promote, reason = should_promote(report, previous_mape, mape_tolerance)
        report.promoted = promote
        report.notes = f"{report.notes}; {reason}"

        repo.insert_validation_report(report)
        repo.register_model(
            version,
            status="promoted" if promote else "rejected",
            mape=report.mape,
            notes=reason,
        )
        if promote:
            repo.demote_other_models(version)
            MODELS_DIR.mkdir(parents=True, exist_ok=True)

        details = {
            "candidate_version": version,
            "mape": report.mape,
            "interval_coverage": report.interval_coverage,
            "n_observations": report.n_observations,
            "previous_mape": previous_mape,
            "promoted": promote,
            "reason": reason,
            "n_estimates": result.n_predict_rows,
        }
        _log_run(repo, job, started, "success", details)
        logger.info("monthly_retrain_validate: %s", details)
        return details
    except Exception as exc:
        _log_run(repo, job, started, "failed", error=str(exc))
        logger.exception("monthly_retrain_validate failed")
        raise


def run_autonomous_cycle_once(
    repo: RevWatchRepository,
    *,
    candidate_version: str = "v0.2.demo",
) -> dict:
    """Run all three jobs once — used by demo / make phase5-demo."""
    return {
        "ingestion": job_daily_signal_ingestion(repo),
        "reestimation": job_weekly_reestimation(repo),
        "retrain_validate": job_monthly_retrain_and_validate(
            repo, candidate_version=candidate_version
        ),
    }
