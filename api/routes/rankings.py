"""Rankings endpoint — top categories/geos and growth leaders/decliners."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from db.repository import RevWatchRepository

from api.auth import require_api_key
from api.deps import get_repo, resolve_model_version
from api.query import latest_period
from api.schemas import RankingItem, RankingsResponse

router = APIRouter(tags=["rankings"])


def _prev_period(period: str) -> str:
    y, m = int(period[:4]), int(period[5:7])
    m -= 1
    if m == 0:
        m = 12
        y -= 1
    return f"{y:04d}-{m:02d}"


@router.get("/rankings", response_model=RankingsResponse)
def rankings(
    period: str | None = Query(None, pattern=r"^\d{4}-\d{2}$"),
    model_version: str | None = None,
    limit: int = Query(10, ge=1, le=50),
    repo: RevWatchRepository = Depends(get_repo),
    _key: str | None = Depends(require_api_key),
) -> RankingsResponse:
    """Top categories/cities by estimated revenue; MoM growth leaders and decliners."""
    version = resolve_model_version(repo, model_version)
    use_period = period or latest_period(repo, version)
    if not use_period:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No estimates available",
        )
    prev = _prev_period(use_period)

    cat_rows = repo.conn.execute(
        """
        SELECT b.category, SUM(e.point_estimate) AS total_rev
        FROM revenue_estimates e
        JOIN businesses b ON b.id = e.business_id
        WHERE e.model_version = ? AND e.period = ?
        GROUP BY b.category
        ORDER BY total_rev DESC
        LIMIT ?
        """,
        [version, use_period, limit],
    ).fetchall()

    city_rows = repo.conn.execute(
        """
        SELECT b.city, SUM(e.point_estimate) AS total_rev
        FROM revenue_estimates e
        JOIN businesses b ON b.id = e.business_id
        WHERE e.model_version = ? AND e.period = ?
        GROUP BY b.city
        ORDER BY total_rev DESC
        LIMIT ?
        """,
        [version, use_period, limit],
    ).fetchall()

    growth_rows = repo.conn.execute(
        """
        SELECT b.id, b.name,
               cur.point_estimate AS cur_rev,
               prev.point_estimate AS prev_rev,
               (cur.point_estimate - prev.point_estimate)
                   / NULLIF(prev.point_estimate, 0) AS growth
        FROM revenue_estimates cur
        JOIN revenue_estimates prev
          ON prev.business_id = cur.business_id
         AND prev.model_version = cur.model_version
         AND prev.period = ?
        JOIN businesses b ON b.id = cur.business_id
        WHERE cur.model_version = ? AND cur.period = ?
          AND prev.point_estimate > 0
        ORDER BY growth DESC
        LIMIT ?
        """,
        [prev, version, use_period, limit],
    ).fetchall()

    decline_rows = repo.conn.execute(
        """
        SELECT b.id, b.name,
               cur.point_estimate AS cur_rev,
               prev.point_estimate AS prev_rev,
               (cur.point_estimate - prev.point_estimate)
                   / NULLIF(prev.point_estimate, 0) AS growth
        FROM revenue_estimates cur
        JOIN revenue_estimates prev
          ON prev.business_id = cur.business_id
         AND prev.model_version = cur.model_version
         AND prev.period = ?
        JOIN businesses b ON b.id = cur.business_id
        WHERE cur.model_version = ? AND cur.period = ?
          AND prev.point_estimate > 0
        ORDER BY growth ASC
        LIMIT ?
        """,
        [prev, version, use_period, limit],
    ).fetchall()

    return RankingsResponse(
        model_version=version,
        period=use_period,
        top_categories_by_revenue=[
            RankingItem(key=str(r[0]), label=str(r[0]), value=round(float(r[1]), 2))
            for r in cat_rows
        ],
        top_cities_by_revenue=[
            RankingItem(key=str(r[0]), label=str(r[0]), value=round(float(r[1]), 2))
            for r in city_rows
        ],
        growth_leaders=[
            RankingItem(
                key=str(r[0]),
                label=str(r[1]),
                value=round(float(r[4]) * 100, 2),
                secondary=round(float(r[2]), 2),
            )
            for r in growth_rows
        ],
        growth_decliners=[
            RankingItem(
                key=str(r[0]),
                label=str(r[1]),
                value=round(float(r[4]) * 100, 2),
                secondary=round(float(r[2]), 2),
            )
            for r in decline_rows
        ],
    )
