"""Review velocity and rating proxies (foot-traffic / engagement)."""

from __future__ import annotations

from datetime import datetime

from adapters.config import DEFAULT_REVIEW_PROPENSITY, REVIEW_PROPENSITY
from adapters.synthetic.base import SyntheticSignalAdapter
from core.models import Business, SalesChannel, SignalType


class ReviewVelocityAdapter(SyntheticSignalAdapter):
    """Review counts, ratings, and velocity as foot-traffic proxy."""

    adapter_key = "review_velocity"

    def _signal_types(self) -> list[SignalType]:
        return [
            SignalType.REVIEW_COUNT,
            SignalType.REVIEW_RATING,
            SignalType.REVIEW_VELOCITY,
        ]

    def _compute_value(
        self,
        signal_type: SignalType,
        business: Business,
        period: datetime,
        activity: float,
    ) -> float | None:
        propensity = REVIEW_PROPENSITY.get(business.category, DEFAULT_REVIEW_PROPENSITY)
        if SalesChannel.PHYSICAL in business.channels:
            propensity *= 1.25
        if SalesChannel.ECOMMERCE in business.channels and SalesChannel.PHYSICAL not in business.channels:
            propensity *= 0.85

        base_reviews = (activity / 1000.0) * propensity

        if signal_type == SignalType.REVIEW_COUNT:
            return max(0.0, base_reviews)
        if signal_type == SignalType.REVIEW_VELOCITY:
            return max(0.0, base_reviews * 0.15)
        if signal_type == SignalType.REVIEW_RATING:
            # Rating 3.2–4.8 correlated weakly with activity tier
            tier_bonus = min(0.8, activity / 500_000)
            return min(5.0, max(2.5, 3.6 + tier_bonus + (propensity * 0.5)))
        return None
