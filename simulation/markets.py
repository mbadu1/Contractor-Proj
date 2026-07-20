"""Market definitions for synthetic business generation."""

from __future__ import annotations

from dataclasses import dataclass

from core.models import BusinessCategory, SalesChannel, SizeTier

MARKET_SHARES: dict[str, float] = {
    "US": 0.55,
    "GH": 0.20,
    "GB": 0.25,
}

COUNTRY_CITIES: dict[str, list[tuple[str, float, float]]] = {
    "US": [
        ("New York", 40.7128, -74.0060),
        ("Los Angeles", 34.0522, -118.2437),
        ("Chicago", 41.8781, -87.6298),
        ("Houston", 29.7604, -95.3698),
        ("Phoenix", 33.4484, -112.0740),
        ("Austin", 30.2672, -97.7431),
        ("Miami", 25.7617, -80.1918),
        ("Seattle", 47.6062, -122.3321),
    ],
    "GH": [
        ("Accra", 5.6037, -0.1870),
        ("Kumasi", 6.6885, -1.6244),
        ("Tamale", 9.4035, -0.8424),
        ("Takoradi", 4.8845, -1.7554),
    ],
    "GB": [
        ("London", 51.5074, -0.1278),
        ("Manchester", 53.4808, -2.2426),
        ("Birmingham", 52.4862, -1.8904),
        ("Leeds", 53.8008, -1.5491),
        ("Glasgow", 55.8642, -4.2518),
        ("Bristol", 51.4545, -2.5879),
    ],
}

# Country-level revenue scale (applied to log-normal mu)
COUNTRY_REVENUE_SCALE: dict[str, float] = {
    "US": 1.0,
    "GB": 0.88,
    "GH": 0.38,
}

# Annual revenue growth by country
COUNTRY_GROWTH_RATE: dict[str, float] = {
    "US": 0.04,
    "GB": 0.03,
    "GH": 0.07,
}

SIZE_TIER_WEIGHTS: list[tuple[SizeTier, float]] = [
    (SizeTier.MICRO, 0.28),
    (SizeTier.SMALL, 0.35),
    (SizeTier.MEDIUM, 0.22),
    (SizeTier.LARGE, 0.11),
    (SizeTier.ENTERPRISE, 0.04),
]

# Category → default channel assignment weights
CATEGORY_CHANNELS: dict[BusinessCategory, list[SalesChannel]] = {
    BusinessCategory.ECOMMERCE_PURE_PLAY: [SalesChannel.ECOMMERCE],
    BusinessCategory.INFORMAL_RETAIL: [SalesChannel.PHYSICAL],
    BusinessCategory.LOGISTICS_DELIVERY: [SalesChannel.HYBRID],
    BusinessCategory.RESTAURANT_CAFE: [SalesChannel.PHYSICAL],
    BusinessCategory.FAST_FOOD: [SalesChannel.PHYSICAL],
}

NAME_PREFIXES = [
    "Golden", "Metro", "Prime", "Urban", "Royal", "Swift", "Bright", "Elite",
    "Summit", "Harbor", "Crown", "Valley", "Pacific", "Central", "Global",
    "Kwame", "Ama", "Kofi", "Nana", "Accra", "Ashanti",
]

NAME_CORES = [
    "Market", "Trading", "Supplies", "Services", "Shop", "Store", "Hub",
    "Bistro", "Kitchen", "Pharmacy", "Motors", "Build", "Tech", "Goods",
    "Fashion", "Fitness", "Logistics", "Wholesale", "Bakery", "Cafe",
]

NAME_SUFFIXES = ["Co", "Ltd", "Group", "Inc", "PLC", "Enterprises", ""]

# Categories with higher weight in emerging markets
GH_CATEGORY_BOOST: frozenset[BusinessCategory] = frozenset(
    {
        BusinessCategory.INFORMAL_RETAIL,
        BusinessCategory.AGRICULTURE,
        BusinessCategory.CONVENIENCE_STORE,
        BusinessCategory.CONSTRUCTION,
    }
)


@dataclass(frozen=True)
class MarketAdapterProfile:
    """Per-market adapter noise/missingness overrides."""

    missingness_rate: float
    business_dropout_rate: float
    base_reliability: float
    payment_missingness_boost: float = 0.0


MARKET_ADAPTER_PROFILES: dict[str, MarketAdapterProfile] = {
    "US": MarketAdapterProfile(0.10, 0.04, 0.78),
    "GB": MarketAdapterProfile(0.11, 0.05, 0.76),
    "GH": MarketAdapterProfile(0.22, 0.12, 0.55, payment_missingness_boost=0.18),
}
