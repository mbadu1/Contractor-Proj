"""US market definitions for synthetic business generation."""

from __future__ import annotations

from dataclasses import dataclass

from core.models import BusinessCategory, SalesChannel, SizeTier

# MVP scope: United States only
PRIMARY_MARKET = "US"

MARKET_SHARES: dict[str, float] = {
    "US": 1.0,
}

# Major US metros for geographic spread
US_CITIES: list[tuple[str, float, float]] = [
    ("New York", 40.7128, -74.0060),
    ("Los Angeles", 34.0522, -118.2437),
    ("Chicago", 41.8781, -87.6298),
    ("Houston", 29.7604, -95.3698),
    ("Phoenix", 33.4484, -112.0740),
    ("Philadelphia", 39.9526, -75.1652),
    ("San Antonio", 29.4241, -98.4936),
    ("San Diego", 32.7157, -117.1611),
    ("Dallas", 32.7767, -96.7970),
    ("Austin", 30.2672, -97.7431),
    ("Jacksonville", 30.3322, -81.6557),
    ("San Francisco", 37.7749, -122.4194),
    ("Columbus", 39.9612, -82.9988),
    ("Charlotte", 35.2271, -80.8431),
    ("Indianapolis", 39.7684, -86.1581),
    ("Seattle", 47.6062, -122.3321),
    ("Denver", 39.7392, -104.9903),
    ("Miami", 25.7617, -80.1918),
    ("Atlanta", 33.7490, -84.3880),
    ("Boston", 42.3601, -71.0589),
]

COUNTRY_CITIES: dict[str, list[tuple[str, float, float]]] = {
    "US": US_CITIES,
}

COUNTRY_REVENUE_SCALE: dict[str, float] = {
    "US": 1.0,
}

COUNTRY_GROWTH_RATE: dict[str, float] = {
    "US": 0.04,
}

SIZE_TIER_WEIGHTS: list[tuple[SizeTier, float]] = [
    (SizeTier.MICRO, 0.28),
    (SizeTier.SMALL, 0.35),
    (SizeTier.MEDIUM, 0.22),
    (SizeTier.LARGE, 0.11),
    (SizeTier.ENTERPRISE, 0.04),
]

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
    "Liberty", "Frontier", "Heritage", "Main Street", "Cornerstone",
]

NAME_CORES = [
    "Market", "Trading", "Supplies", "Services", "Shop", "Store", "Hub",
    "Bistro", "Kitchen", "Pharmacy", "Motors", "Build", "Tech", "Goods",
    "Fashion", "Fitness", "Logistics", "Wholesale", "Bakery", "Cafe",
]

NAME_SUFFIXES = ["Co", "Inc", "Group", "LLC", "Enterprises", ""]

# Slightly overweight common US small-business categories
US_CATEGORY_BOOST: frozenset[BusinessCategory] = frozenset(
    {
        BusinessCategory.RESTAURANT_CAFE,
        BusinessCategory.CONVENIENCE_STORE,
        BusinessCategory.PROFESSIONAL_SERVICES,
        BusinessCategory.HOME_IMPROVEMENT,
    }
)


@dataclass(frozen=True)
class MarketAdapterProfile:
    """Adapter noise/missingness for the US market."""

    missingness_rate: float
    business_dropout_rate: float
    base_reliability: float
    payment_missingness_boost: float = 0.0


MARKET_ADAPTER_PROFILES: dict[str, MarketAdapterProfile] = {
    "US": MarketAdapterProfile(0.10, 0.04, 0.78),
}
