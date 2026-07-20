"""Business listing and estimate detail endpoints."""

from __future__ import annotations

import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from core.models import BusinessCategory
from db.repository import RevWatchRepository

from api.auth import require_api_key
from api.deps import get_repo, resolve_model_version
from api.query import business_to_out, estimate_from_row, get_latest_estimate_out
from api.schemas import (
    BusinessEstimateDetail,
    BusinessOut,
    EstimateOut,
    PageMeta,
    PaginatedResponse,
)

router = APIRouter(prefix="/businesses", tags=["businesses"])


@router.get("", response_model=PaginatedResponse[BusinessOut])
def list_businesses(
    country: str | None = Query(None, description="ISO country code, e.g. US"),
    city: str | None = None,
    category: BusinessCategory | None = None,
    revenue_min: float | None = Query(None, ge=0, description="Min latest point estimate"),
    revenue_max: float | None = Query(None, ge=0, description="Max latest point estimate"),
    confidence_min: float | None = Query(None, ge=0, le=100),
    model_version: str | None = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    repo: RevWatchRepository = Depends(get_repo),
    _key: str | None = Depends(require_api_key),
) -> PaginatedResponse[BusinessOut]:
    """List businesses with optional filters. Latest estimate always includes CI + confidence."""
    version = resolve_model_version(repo, model_version)

    clauses = ["1=1"]
    params: list[object] = [version]
    if country:
        clauses.append("b.country = ?")
        params.append(country.upper())
    if city:
        clauses.append("LOWER(b.city) = LOWER(?)")
        params.append(city)
    if category:
        clauses.append("b.category = ?")
        params.append(category.value)
    if revenue_min is not None:
        clauses.append("e.point_estimate >= ?")
        params.append(revenue_min)
    if revenue_max is not None:
        clauses.append("e.point_estimate <= ?")
        params.append(revenue_max)
    if confidence_min is not None:
        clauses.append("e.confidence_score >= ?")
        params.append(confidence_min)

    where = " AND ".join(clauses)

    # Latest estimate per business for the model version
    count_row = repo.conn.execute(
        f"""
        WITH latest AS (
            SELECT business_id, MAX(period) AS period
            FROM revenue_estimates
            WHERE model_version = ?
            GROUP BY business_id
        )
        SELECT COUNT(*)
        FROM businesses b
        LEFT JOIN latest l ON l.business_id = b.id
        LEFT JOIN revenue_estimates e
          ON e.business_id = l.business_id
         AND e.period = l.period
         AND e.model_version = ?
        WHERE {where}
        """,
        [version, *params],
    ).fetchone()
    total = int(count_row[0]) if count_row else 0

    rows = repo.conn.execute(
        f"""
        WITH latest AS (
            SELECT business_id, MAX(period) AS period
            FROM revenue_estimates
            WHERE model_version = ?
            GROUP BY business_id
        )
        SELECT
            b.id, b.name, b.category, b.country, b.city,
            b.latitude, b.longitude, b.size_tier, b.channels,
            e.period, e.point_estimate, e.ci_low, e.ci_high,
            e.confidence_score, e.signal_contributions, e.model_version
        FROM businesses b
        LEFT JOIN latest l ON l.business_id = b.id
        LEFT JOIN revenue_estimates e
          ON e.business_id = l.business_id
         AND e.period = l.period
         AND e.model_version = ?
        WHERE {where}
        ORDER BY b.name
        LIMIT ? OFFSET ?
        """,
        [version, *params, limit, offset],
    ).fetchall()

    data: list[BusinessOut] = []
    for r in rows:
        channels_raw = r[8]
        if isinstance(channels_raw, str):
            channels_raw = json.loads(channels_raw)
        latest = None
        if r[9] is not None:
            latest = EstimateOut(
                period=r[9],
                point_estimate=float(r[10]),
                ci_low=float(r[11]),
                ci_high=float(r[12]),
                confidence_score=float(r[13]),
                signal_contributions=(
                    json.loads(r[14]) if isinstance(r[14], str) else (r[14] or {})
                ),
                model_version=str(r[15]),
            )
        from core.models import Business, SalesChannel, SizeTier

        biz = Business(
            id=UUID(r[0]),
            name=r[1],
            category=BusinessCategory(r[2]),
            country=r[3],
            city=r[4],
            latitude=r[5],
            longitude=r[6],
            size_tier=SizeTier(r[7]),
            channels=[SalesChannel(c) for c in channels_raw],
        )
        data.append(business_to_out(biz, latest))

    return PaginatedResponse(
        data=data,
        meta=PageMeta(total=total, limit=limit, offset=offset),
    )


@router.get("/{business_id}/estimate", response_model=BusinessEstimateDetail)
def get_business_estimate(
    business_id: UUID,
    model_version: str | None = None,
    history_limit: int = Query(24, ge=1, le=60),
    repo: RevWatchRepository = Depends(get_repo),
    _key: str | None = Depends(require_api_key),
) -> BusinessEstimateDetail:
    """Current estimate + up to 24 months of history with signal contributions."""
    biz = repo.get_business(business_id)
    if biz is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business not found")

    version = resolve_model_version(repo, model_version)
    current = get_latest_estimate_out(repo, business_id, version)

    rows = repo.conn.execute(
        """
        SELECT period, point_estimate, ci_low, ci_high,
               confidence_score, signal_contributions, model_version
        FROM revenue_estimates
        WHERE business_id = ? AND model_version = ?
        ORDER BY period DESC
        LIMIT ?
        """,
        [str(business_id), version, history_limit],
    ).fetchall()
    history = [estimate_from_row(r) for r in rows]
    # Chronological for charting
    history_asc = list(reversed(history))

    return BusinessEstimateDetail(
        business=business_to_out(biz, current),
        current=current,
        history=history_asc,
    )
