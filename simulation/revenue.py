"""Ground-truth revenue time-series generation."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone
from random import Random
from uuid import UUID

import numpy as np

from core.models import Business, BusinessCategory, TrueRevenue
from simulation.markets import COUNTRY_GROWTH_RATE, COUNTRY_REVENUE_SCALE

from adapters.config import CATEGORY_MULTIPLIER, DEFAULT_CATEGORY_MULTIPLIER, SIZE_TIER_SCALE


@dataclass
class RevenueEngineConfig:
    months: int = 24
    end_year: int = 2025
    end_month: int = 12
    seed: int = 42
    shock_probability: float = 0.02
    lognormal_sigma: float = 0.35


def _period_list(config: RevenueEngineConfig) -> list[str]:
    periods: list[str] = []
    y, m = config.end_year, config.end_month
    for _ in range(config.months):
        periods.append(f"{y:04d}-{m:02d}")
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    return list(reversed(periods))


def _seasonal_factor(month: int, category: BusinessCategory) -> float:
    """Monthly seasonality multiplier."""
    base = 1.0 + 0.08 * math.sin(2 * math.pi * (month - 1) / 12)
    if month == 12:
        base += 0.10
    elif month == 1:
        base -= 0.08
    if category in (
        BusinessCategory.HOTEL_LODGING,
        BusinessCategory.ENTERTAINMENT_VENUE,
    ):
        if month in (6, 7, 8):
            base += 0.12
    if category == BusinessCategory.AGRICULTURE:
        if month in (9, 10, 11):
            base += 0.15
    return max(0.5, base)


def _business_lognormal_mu(business: Business) -> float:
    """Log-mean of monthly revenue for a business."""
    base = SIZE_TIER_SCALE[business.size_tier]
    cat = CATEGORY_MULTIPLIER.get(business.category, DEFAULT_CATEGORY_MULTIPLIER)
    country = COUNTRY_REVENUE_SCALE.get(business.country.upper(), 0.6)
    return math.log(max(500.0, base * cat * country))


class RevenueEngine:
    """Generate hidden true monthly revenue with trend, seasonality, and shocks."""

    def __init__(self, config: RevenueEngineConfig | None = None) -> None:
        self.config = config or RevenueEngineConfig()
        self._rng = Random(self.config.seed)
        self._np_rng = np.random.default_rng(self.config.seed)

    def _business_effects(self, business_id: UUID) -> tuple[float, float]:
        """Stable per-business level effect and annual growth offset."""
        h = hash(str(business_id))
        level = 0.85 + (h % 300) / 1000.0  # 0.85 – 1.15
        growth = -0.02 + (h % 80) / 1000.0  # -0.02 – +0.06 annual
        return level, growth

    def generate_for_business(self, business: Business) -> list[TrueRevenue]:
        periods = _period_list(self.config)
        level, growth_offset = self._business_effects(business.id)
        mu = _business_lognormal_mu(business)
        sigma = self.config.lognormal_sigma

        # Draw baseline monthly revenue from log-normal (business-specific)
        baseline = float(self._np_rng.lognormal(mean=mu + math.log(level), sigma=sigma))

        country_growth = COUNTRY_GROWTH_RATE.get(business.country.upper(), 0.03)
        annual_growth = country_growth + growth_offset

        records: list[TrueRevenue] = []
        for i, period in enumerate(periods):
            year, month = int(period[:4]), int(period[5:7])
            trend = (1 + annual_growth) ** (i / 12.0)
            seasonal = _seasonal_factor(month, business.category)

            shock = 1.0
            if self._rng.random() < self.config.shock_probability:
                shock = 1.0 + self._rng.uniform(-0.35, 0.20)

            revenue = max(0.0, baseline * trend * seasonal * shock)
            records.append(
                TrueRevenue(
                    business_id=business.id,
                    period=period,
                    revenue=round(revenue, 2),
                    trend_factor=round(trend, 4),
                    seasonal_factor=round(seasonal, 4),
                    shock_factor=round(shock, 4),
                )
            )
        return records

    def generate_all(self, businesses: list[Business]) -> list[TrueRevenue]:
        out: list[TrueRevenue] = []
        for biz in businesses:
            out.extend(self.generate_for_business(biz))
        return out

    @staticmethod
    def period_start(period: str) -> datetime:
        y, m = int(period[:4]), int(period[5:7])
        return datetime(y, m, 1, tzinfo=timezone.utc)

    @staticmethod
    def first_period(config: RevenueEngineConfig) -> str:
        return _period_list(config)[0]

    @staticmethod
    def last_period(config: RevenueEngineConfig) -> str:
        return _period_list(config)[-1]
