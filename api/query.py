"""Shared helpers for API query layer."""

from __future__ import annotations

from uuid import UUID

from core.models import Business, BusinessCategory, SalesChannel, SizeTier
from db.repository import RevWatchRepository

from api.schemas import BusinessOut, EstimateOut


def estimate_from_row(row: tuple) -> EstimateOut:
    """Map estimate query row → EstimateOut.

    Expected columns:
    period, point_estimate, ci_low, ci_high, confidence_score,
    signal_contributions (dict|str), model_version
    """
    import json

    contributions = row[5]
    if isinstance(contributions, str):
        contributions = json.loads(contributions)
    return EstimateOut(
        period=row[0],
        point_estimate=float(row[1]),
        ci_low=float(row[2]),
        ci_high=float(row[3]),
        confidence_score=float(row[4]),
        signal_contributions=contributions or {},
        model_version=str(row[6]),
    )


def business_to_out(biz: Business, latest: EstimateOut | None = None) -> BusinessOut:
    return BusinessOut(
        id=biz.id,
        name=biz.name,
        category=biz.category,
        country=biz.country,
        city=biz.city,
        latitude=biz.latitude,
        longitude=biz.longitude,
        size_tier=biz.size_tier,
        channels=biz.channels,
        latest_estimate=latest,
    )


def latest_period(repo: RevWatchRepository, model_version: str) -> str | None:
    row = repo.conn.execute(
        """
        SELECT period FROM revenue_estimates
        WHERE model_version = ?
        ORDER BY period DESC
        LIMIT 1
        """,
        [model_version],
    ).fetchone()
    return str(row[0]) if row else None


def get_latest_estimate_out(
    repo: RevWatchRepository,
    business_id: UUID,
    model_version: str,
) -> EstimateOut | None:
    row = repo.conn.execute(
        """
        SELECT period, point_estimate, ci_low, ci_high,
               confidence_score, signal_contributions, model_version
        FROM revenue_estimates
        WHERE business_id = ? AND model_version = ?
        ORDER BY period DESC
        LIMIT 1
        """,
        [str(business_id), model_version],
    ).fetchone()
    return estimate_from_row(row) if row else None
