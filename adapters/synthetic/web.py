"""Web footprint and ecommerce catalog proxies."""

from __future__ import annotations

from datetime import datetime

from adapters.config import WEB_CHANNEL_BOOST
from adapters.synthetic.base import SyntheticSignalAdapter
from core.models import Business, SalesChannel, SignalType


class WebFootprintAdapter(SyntheticSignalAdapter):
    """Site traffic rank, SKU counts, and average price points."""

    adapter_key = "web_footprint"

    def _signal_types(self) -> list[SignalType]:
        return [
            SignalType.WEB_TRAFFIC_RANK,
            SignalType.ECOMMERCE_SKU_COUNT,
            SignalType.AVG_PRICE_POINT,
        ]

    def _web_boost(self, business: Business) -> float:
        boost = 0.0
        for ch in business.channels:
            boost = max(boost, WEB_CHANNEL_BOOST.get(ch, 0.1))
        return boost

    def _compute_value(
        self,
        signal_type: SignalType,
        business: Business,
        period: datetime,
        activity: float,
    ) -> float | None:
        boost = self._web_boost(business)
        if boost < 0.1:
            return None

        if signal_type == SignalType.WEB_TRAFFIC_RANK:
            # Lower rank = more traffic (Alexa-style). Scale inversely with activity.
            rank = max(1_000, 2_000_000 / (1 + activity / 10_000) / boost)
            return rank
        if signal_type == SignalType.ECOMMERCE_SKU_COUNT:
            if SalesChannel.ECOMMERCE not in business.channels and SalesChannel.HYBRID not in business.channels:
                return None
            return max(5.0, (activity / 2000.0) * boost * 12)
        if signal_type == SignalType.AVG_PRICE_POINT:
            if boost < 0.3:
                return None
            base = 35.0
            cat = business.category.value
            if cat in ("jewelry_luxury", "electronics_retail"):
                base = 120.0
            elif cat in ("grocery_supermarket", "convenience_store", "fast_food"):
                base = 15.0
            return base * (1 + boost * 0.3)
        return None
