"""Market and category parameters for synthetic signal generation."""

from __future__ import annotations

from core.models import BusinessCategory, SalesChannel, SizeTier

# Digital payment penetration by category (share of revenue visible digitally)
DIGITAL_PENETRATION: dict[BusinessCategory, float] = {
    BusinessCategory.ECOMMERCE_PURE_PLAY: 0.95,
    BusinessCategory.ELECTRONICS_RETAIL: 0.82,
    BusinessCategory.APPAREL_RETAIL: 0.78,
    BusinessCategory.JEWELRY_LUXURY: 0.75,
    BusinessCategory.FURNITURE_HOME_GOODS: 0.70,
    BusinessCategory.GROCERY_SUPERMARKET: 0.55,
    BusinessCategory.RESTAURANT_CAFE: 0.62,
    BusinessCategory.FAST_FOOD: 0.68,
    BusinessCategory.HOTEL_LODGING: 0.72,
    BusinessCategory.PHARMACY_HEALTH: 0.58,
    BusinessCategory.PROFESSIONAL_SERVICES: 0.65,
    BusinessCategory.FINANCIAL_SERVICES: 0.88,
    BusinessCategory.CONVENIENCE_STORE: 0.45,
    BusinessCategory.INFORMAL_RETAIL: 0.20,
    BusinessCategory.AGRICULTURE: 0.25,
    BusinessCategory.WHOLESALE_DISTRIBUTION: 0.50,
    BusinessCategory.MANUFACTURING: 0.40,
    BusinessCategory.CONSTRUCTION: 0.35,
    BusinessCategory.LOGISTICS_DELIVERY: 0.60,
}

DEFAULT_DIGITAL_PENETRATION = 0.50

# Country-level payment infrastructure multiplier
COUNTRY_PAYMENT_FACTOR: dict[str, float] = {
    "US": 1.0,
    "GB": 0.95,
    "UK": 0.95,
    "GH": 0.45,
}

# Signal coverage by country (probability adapter has any data for a business)
COUNTRY_SIGNAL_COVERAGE: dict[str, float] = {
    "US": 0.92,
    "GB": 0.90,
    "UK": 0.90,
    "GH": 0.58,
}

DEFAULT_COUNTRY_COVERAGE = 0.75

# Size tier → base monthly activity scale (USD-equivalent latent intensity)
SIZE_TIER_SCALE: dict[SizeTier, float] = {
    SizeTier.MICRO: 8_000,
    SizeTier.SMALL: 35_000,
    SizeTier.MEDIUM: 120_000,
    SizeTier.LARGE: 450_000,
    SizeTier.ENTERPRISE: 2_500_000,
}

# Category revenue multiplier vs baseline
CATEGORY_MULTIPLIER: dict[BusinessCategory, float] = {
    BusinessCategory.ECOMMERCE_PURE_PLAY: 1.4,
    BusinessCategory.GROCERY_SUPERMARKET: 1.2,
    BusinessCategory.HOTEL_LODGING: 1.5,
    BusinessCategory.MANUFACTURING: 1.6,
    BusinessCategory.INFORMAL_RETAIL: 0.35,
    BusinessCategory.FAST_FOOD: 0.9,
    BusinessCategory.RESTAURANT_CAFE: 0.85,
    BusinessCategory.FINANCIAL_SERVICES: 1.8,
    BusinessCategory.JEWELRY_LUXURY: 1.3,
}

DEFAULT_CATEGORY_MULTIPLIER = 1.0

# Review propensity by category (reviews per $1k latent activity)
REVIEW_PROPENSITY: dict[BusinessCategory, float] = {
    BusinessCategory.RESTAURANT_CAFE: 0.45,
    BusinessCategory.FAST_FOOD: 0.35,
    BusinessCategory.HOTEL_LODGING: 0.55,
    BusinessCategory.ENTERTAINMENT_VENUE: 0.40,
    BusinessCategory.FITNESS_GYM: 0.30,
    BusinessCategory.INFORMAL_RETAIL: 0.05,
    BusinessCategory.ECOMMERCE_PURE_PLAY: 0.25,
}

DEFAULT_REVIEW_PROPENSITY = 0.15

# Web footprint applicability
WEB_CHANNEL_BOOST = {
    SalesChannel.ECOMMERCE: 1.0,
    SalesChannel.HYBRID: 0.65,
    SalesChannel.PHYSICAL: 0.15,
}

# Hiring intensity by size tier (job postings per month at baseline activity)
HIRING_BY_SIZE: dict[SizeTier, float] = {
    SizeTier.MICRO: 0.2,
    SizeTier.SMALL: 0.8,
    SizeTier.MEDIUM: 2.5,
    SizeTier.LARGE: 8.0,
    SizeTier.ENTERPRISE: 25.0,
}

# Supplier flow categories
SUPPLIER_HEAVY_CATEGORIES: frozenset[BusinessCategory] = frozenset(
    {
        BusinessCategory.WHOLESALE_DISTRIBUTION,
        BusinessCategory.MANUFACTURING,
        BusinessCategory.GROCERY_SUPERMARKET,
        BusinessCategory.CONVENIENCE_STORE,
        BusinessCategory.LOGISTICS_DELIVERY,
        BusinessCategory.CONSTRUCTION,
    }
)

# Utility / opening hours by category
PHYSICAL_INTENSITY: dict[BusinessCategory, float] = {
    BusinessCategory.GAS_STATION: 0.95,
    BusinessCategory.CONVENIENCE_STORE: 0.90,
    BusinessCategory.FAST_FOOD: 0.88,
    BusinessCategory.GROCERY_SUPERMARKET: 0.85,
    BusinessCategory.RESTAURANT_CAFE: 0.80,
    BusinessCategory.ECOMMERCE_PURE_PLAY: 0.20,
    BusinessCategory.PROFESSIONAL_SERVICES: 0.50,
    BusinessCategory.INFORMAL_RETAIL: 0.70,
}

DEFAULT_PHYSICAL_INTENSITY = 0.60


def digital_penetration(category: BusinessCategory, channels: list[SalesChannel]) -> float:
    base = DIGITAL_PENETRATION.get(category, DEFAULT_DIGITAL_PENETRATION)
    if SalesChannel.ECOMMERCE in channels:
        base = min(0.98, base + 0.15)
    elif SalesChannel.PHYSICAL in channels and SalesChannel.ECOMMERCE not in channels:
        base *= 0.85
    return base


def country_factor(country: str) -> float:
    return COUNTRY_PAYMENT_FACTOR.get(country.upper(), 0.70)


def country_coverage(country: str) -> float:
    return COUNTRY_SIGNAL_COVERAGE.get(country.upper(), DEFAULT_COUNTRY_COVERAGE)
