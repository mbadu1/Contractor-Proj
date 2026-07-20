"""API response / request schemas for RevWatch."""

from __future__ import annotations

from datetime import datetime
from typing import Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel, Field

from core.models import (
    BusinessCategory,
    CalibrationBin,
    SalesChannel,
    SegmentMetrics,
    SignalType,
    SizeTier,
)

T = TypeVar("T")


class PageMeta(BaseModel):
    total: int
    limit: int
    offset: int


class PaginatedResponse(BaseModel, Generic[T]):
    data: list[T]
    meta: PageMeta


class EstimateOut(BaseModel):
    """Every estimate includes CI + confidence — never a bare number."""

    period: str
    point_estimate: float
    ci_low: float
    ci_high: float
    confidence_score: float
    signal_contributions: dict[str, float] = Field(default_factory=dict)
    model_version: str


class BusinessOut(BaseModel):
    id: UUID
    name: str
    category: BusinessCategory
    country: str
    city: str
    latitude: float
    longitude: float
    size_tier: SizeTier
    channels: list[SalesChannel]
    latest_estimate: EstimateOut | None = None


class BusinessEstimateDetail(BaseModel):
    business: BusinessOut
    current: EstimateOut | None
    history: list[EstimateOut]


class CategoryRevenue(BaseModel):
    category: str
    total_revenue: float
    business_count: int
    share: float


class CityDensity(BaseModel):
    city: str
    business_count: int
    total_revenue: float
    latitude: float
    longitude: float


class MarketSummary(BaseModel):
    country: str
    model_version: str
    period: str
    business_count: int
    total_estimated_revenue: float
    hhi: float = Field(description="Herfindahl-Hirschman Index (0–10,000) by category share")
    revenue_by_category: list[CategoryRevenue]
    commercial_density_by_city: list[CityDensity]


class RankingItem(BaseModel):
    key: str
    label: str
    value: float
    secondary: float | None = None


class RankingsResponse(BaseModel):
    model_version: str
    period: str
    top_categories_by_revenue: list[RankingItem]
    top_cities_by_revenue: list[RankingItem]
    growth_leaders: list[RankingItem]
    growth_decliners: list[RankingItem]


class ValidationLatestOut(BaseModel):
    model_version: str
    n_observations: int
    mape: float
    median_ape: float
    interval_coverage: float
    mean_confidence: float
    promoted: bool
    notes: str
    segment_metrics: list[SegmentMetrics]
    calibration: list[CalibrationBin]


class SignalIngestItem(BaseModel):
    business_id: UUID
    signal_type: SignalType
    value: float
    timestamp: datetime
    source: str = Field(min_length=1, max_length=128)
    reliability: float = Field(ge=0.0, le=1.0, default=0.75)


class SignalIngestRequest(BaseModel):
    observations: list[SignalIngestItem] = Field(min_length=1, max_length=10_000)


class SignalIngestResponse(BaseModel):
    inserted: int
    message: str


class HealthOut(BaseModel):
    status: str
    service: str = "revwatch-api"
    businesses: int
    promoted_model: str | None
