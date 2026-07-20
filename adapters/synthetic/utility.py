"""Utility and operational intensity proxies."""

from __future__ import annotations

from datetime import datetime

from adapters.config import DEFAULT_PHYSICAL_INTENSITY, PHYSICAL_INTENSITY
from adapters.synthetic.base import SyntheticSignalAdapter
from core.models import Business, SalesChannel, SignalType


class UtilityProxyAdapter(SyntheticSignalAdapter):
    """Opening hours and energy-band utility intensity."""

    adapter_key = "utility_proxy"

    def _signal_types(self) -> list[SignalType]:
        return [SignalType.UTILITY_INTENSITY, SignalType.OPENING_HOURS]

    def _physical_weight(self, business: Business) -> float:
        intensity = PHYSICAL_INTENSITY.get(business.category, DEFAULT_PHYSICAL_INTENSITY)
        if SalesChannel.ECOMMERCE in business.channels and SalesChannel.PHYSICAL not in business.channels:
            intensity *= 0.25
        elif SalesChannel.HYBRID in business.channels:
            intensity *= 0.85
        return intensity

    def _compute_value(
        self,
        signal_type: SignalType,
        business: Business,
        period: datetime,
        activity: float,
    ) -> float | None:
        weight = self._physical_weight(business)
        if weight < 0.15:
            return None

        if signal_type == SignalType.UTILITY_INTENSITY:
            # Normalized 0–100 operational intensity index
            idx = min(100.0, (activity / 50_000) * weight * 40)
            return max(1.0, idx)
        if signal_type == SignalType.OPENING_HOURS:
            # Weekly hours open (e.g. 40–168)
            base_hours = 45.0 + weight * 80
            return min(168.0, base_hours)
        return None
