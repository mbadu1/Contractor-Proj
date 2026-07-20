"""Validation health endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from db.repository import RevWatchRepository

from api.auth import require_api_key
from api.deps import get_repo
from api.schemas import ValidationLatestOut

router = APIRouter(tags=["validation"])


@router.get("/validation/latest", response_model=ValidationLatestOut)
def validation_latest(
    repo: RevWatchRepository = Depends(get_repo),
    _key: str | None = Depends(require_api_key),
) -> ValidationLatestOut:
    """Latest model health metrics (MAPE, coverage, calibration, segments)."""
    report = repo.get_latest_validation_report()
    if report is None:
        promoted = repo.get_promoted_model_version()
        if promoted:
            report = repo.get_latest_validation_report(promoted)
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No validation reports yet — run phase5-demo first",
        )
    return ValidationLatestOut(
        model_version=report.model_version,
        n_observations=report.n_observations,
        mape=report.mape,
        median_ape=report.median_ape,
        interval_coverage=report.interval_coverage,
        mean_confidence=report.mean_confidence,
        promoted=report.promoted,
        notes=report.notes,
        segment_metrics=report.segment_metrics,
        calibration=report.calibration,
    )
