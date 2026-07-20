"""Market summary endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from db.repository import RevWatchRepository

from api.auth import require_api_key
from api.deps import get_repo, resolve_model_version
from api.query import latest_period
from api.schemas import CategoryRevenue, CityDensity, MarketSummary

router = APIRouter(prefix="/markets", tags=["markets"])


def _hhi(shares: list[float]) -> float:
    """Herfindahl-Hirschman Index on 0–10,000 scale from share fractions."""
    return round(sum((s * 100) ** 2 for s in shares), 2)


@router.get("/{country}/summary", response_model=MarketSummary)
def market_summary(
    country: str,
    period: str | None = Query(None, pattern=r"^\d{4}-\d{2}$"),
    model_version: str | None = None,
    repo: RevWatchRepository = Depends(get_repo),
    _key: str | None = Depends(require_api_key),
) -> MarketSummary:
    """Revenue by category, HHI concentration, and commercial density by city."""
    version = resolve_model_version(repo, model_version)
    country = country.upper()
    use_period = period or latest_period(repo, version)
    if not use_period:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No estimates available for this model version",
        )

    biz_count_row = repo.conn.execute(
        "SELECT COUNT(*) FROM businesses WHERE country = ?", [country]
    ).fetchone()
    business_count = int(biz_count_row[0]) if biz_count_row else 0
    if business_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No businesses found for country {country}",
        )

    cat_rows = repo.conn.execute(
        """
        SELECT b.category,
               SUM(e.point_estimate) AS total_rev,
               COUNT(DISTINCT b.id) AS n_biz
        FROM businesses b
        JOIN revenue_estimates e
          ON e.business_id = b.id
         AND e.model_version = ?
         AND e.period = ?
        WHERE b.country = ?
        GROUP BY b.category
        ORDER BY total_rev DESC
        """,
        [version, use_period, country],
    ).fetchall()

    total_rev = sum(float(r[1]) for r in cat_rows) or 1.0
    shares = [float(r[1]) / total_rev for r in cat_rows]
    categories = [
        CategoryRevenue(
            category=str(r[0]),
            total_revenue=round(float(r[1]), 2),
            business_count=int(r[2]),
            share=round(float(r[1]) / total_rev, 4),
        )
        for r in cat_rows
    ]

    city_rows = repo.conn.execute(
        """
        SELECT b.city,
               COUNT(DISTINCT b.id) AS n_biz,
               COALESCE(SUM(e.point_estimate), 0) AS total_rev,
               AVG(b.latitude) AS lat,
               AVG(b.longitude) AS lon
        FROM businesses b
        LEFT JOIN revenue_estimates e
          ON e.business_id = b.id
         AND e.model_version = ?
         AND e.period = ?
        WHERE b.country = ?
        GROUP BY b.city
        ORDER BY n_biz DESC
        """,
        [version, use_period, country],
    ).fetchall()

    cities = [
        CityDensity(
            city=str(r[0]),
            business_count=int(r[1]),
            total_revenue=round(float(r[2]), 2),
            latitude=float(r[3]),
            longitude=float(r[4]),
        )
        for r in city_rows
    ]

    return MarketSummary(
        country=country,
        model_version=version,
        period=use_period,
        business_count=business_count,
        total_estimated_revenue=round(sum(float(r[1]) for r in cat_rows), 2),
        hhi=_hhi(shares),
        revenue_by_category=categories,
        commercial_density_by_city=cities,
    )
