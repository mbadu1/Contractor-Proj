"""Core domain models for RevenueLens."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator


class BusinessCategory(str, Enum):
    """~30-category business taxonomy used across estimation and reporting."""

    GROCERY_SUPERMARKET = "grocery_supermarket"
    CONVENIENCE_STORE = "convenience_store"
    RESTAURANT_CAFE = "restaurant_cafe"
    FAST_FOOD = "fast_food"
    APPAREL_RETAIL = "apparel_retail"
    ELECTRONICS_RETAIL = "electronics_retail"
    HOME_IMPROVEMENT = "home_improvement"
    PHARMACY_HEALTH = "pharmacy_health"
    BEAUTY_PERSONAL_CARE = "beauty_personal_care"
    AUTOMOTIVE_RETAIL = "automotive_retail"
    AUTOMOTIVE_SERVICE = "automotive_service"
    GAS_STATION = "gas_station"
    HOTEL_LODGING = "hotel_lodging"
    ENTERTAINMENT_VENUE = "entertainment_venue"
    FITNESS_GYM = "fitness_gym"
    PROFESSIONAL_SERVICES = "professional_services"
    FINANCIAL_SERVICES = "financial_services"
    HEALTHCARE_PROVIDER = "healthcare_provider"
    EDUCATION_TRAINING = "education_training"
    WHOLESALE_DISTRIBUTION = "wholesale_distribution"
    MANUFACTURING = "manufacturing"
    CONSTRUCTION = "construction"
    AGRICULTURE = "agriculture"
    INFORMAL_RETAIL = "informal_retail"
    ECOMMERCE_PURE_PLAY = "ecommerce_pure_play"
    LOGISTICS_DELIVERY = "logistics_delivery"
    REAL_ESTATE_SERVICES = "real_estate_services"
    TELECOM_UTILITIES_RETAIL = "telecom_utilities_retail"
    FURNITURE_HOME_GOODS = "furniture_home_goods"
    JEWELRY_LUXURY = "jewelry_luxury"


ALL_CATEGORIES: tuple[BusinessCategory, ...] = tuple(BusinessCategory)


class SizeTier(str, Enum):
    MICRO = "micro"
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"
    ENTERPRISE = "enterprise"


class SalesChannel(str, Enum):
    PHYSICAL = "physical"
    ECOMMERCE = "ecommerce"
    HYBRID = "hybrid"


class SignalType(str, Enum):
    """Observable proxy signal types ingested via adapters."""

    PAYMENT_TRANSACTION_COUNT = "payment_transaction_count"
    PAYMENT_VOLUME = "payment_volume"
    REVIEW_COUNT = "review_count"
    REVIEW_RATING = "review_rating"
    REVIEW_VELOCITY = "review_velocity"
    WEB_TRAFFIC_RANK = "web_traffic_rank"
    ECOMMERCE_SKU_COUNT = "ecommerce_sku_count"
    AVG_PRICE_POINT = "avg_price_point"
    JOB_POSTING_COUNT = "job_posting_count"
    SUPPLIER_SHIPMENT_VOLUME = "supplier_shipment_volume"
    UTILITY_INTENSITY = "utility_intensity"
    OPENING_HOURS = "opening_hours"


class Business(BaseModel):
    """Canonical business entity after entity resolution."""

    id: UUID = Field(default_factory=uuid4)
    name: str = Field(min_length=1, max_length=512)
    category: BusinessCategory
    country: str = Field(min_length=2, max_length=3, description="ISO 3166-1 alpha-2/3")
    city: str = Field(min_length=1, max_length=256)
    latitude: float = Field(ge=-90.0, le=90.0)
    longitude: float = Field(ge=-180.0, le=180.0)
    size_tier: SizeTier
    channels: list[SalesChannel] = Field(min_length=1)

    @field_validator("country")
    @classmethod
    def normalize_country(cls, v: str) -> str:
        return v.strip().upper()

    @field_validator("name", "city")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        return v.strip()


class SignalObservation(BaseModel):
    """Single proxy signal observation for a business at a point in time."""

    business_id: UUID
    signal_type: SignalType
    value: float
    timestamp: datetime
    source: str = Field(min_length=1, max_length=128)
    reliability: float = Field(ge=0.0, le=1.0, description="Adapter-assigned reliability 0–1")


class RevenueEstimate(BaseModel):
    """Estimated revenue for a business over a period with uncertainty."""

    business_id: UUID
    period: str = Field(
        pattern=r"^\d{4}-\d{2}$",
        description="Monthly period as YYYY-MM",
    )
    point_estimate: float = Field(ge=0.0)
    ci_low: float = Field(ge=0.0)
    ci_high: float = Field(ge=0.0)
    confidence_score: float = Field(ge=0.0, le=100.0)
    signal_contributions: dict[str, float] = Field(default_factory=dict)
    model_version: str = Field(min_length=1, max_length=64)

    @field_validator("ci_high")
    @classmethod
    def ci_high_gte_low(cls, v: float, info: Any) -> float:
        ci_low = info.data.get("ci_low")
        if ci_low is not None and v < ci_low:
            raise ValueError("ci_high must be >= ci_low")
        return v


class BusinessCreate(BaseModel):
    """Input model for creating a business (id optional)."""

    id: UUID | None = None
    name: str
    category: BusinessCategory
    country: str
    city: str
    latitude: float
    longitude: float
    size_tier: SizeTier
    channels: list[SalesChannel]

    def to_business(self) -> Business:
        data = self.model_dump()
        if data.pop("id") is None:
            return Business(**data)
        return Business(id=self.id, **{k: v for k, v in data.items() if k != "id"})


class RawBusinessRecord(BaseModel):
    """Unresolved business record as ingested from an external source."""

    source: str
    source_id: str
    name: str
    category: BusinessCategory | None = None
    country: str
    city: str
    latitude: float
    longitude: float
    size_tier: SizeTier | None = None
    channels: list[SalesChannel] | None = None
