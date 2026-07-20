"""Job posting signals as headcount / growth proxy."""

from __future__ import annotations

from datetime import datetime

from adapters.config import HIRING_BY_SIZE
from adapters.synthetic.base import SyntheticSignalAdapter
from core.models import Business, SignalType, SizeTier


class HiringSignalAdapter(SyntheticSignalAdapter):
    """Job posting counts correlated with size tier and activity."""

    adapter_key = "hiring_signals"

    def _signal_types(self) -> list[SignalType]:
        return [SignalType.JOB_POSTING_COUNT]

    def _compute_value(
        self,
        signal_type: SignalType,
        business: Business,
        period: datetime,
        activity: float,
    ) -> float | None:
        if signal_type != SignalType.JOB_POSTING_COUNT:
            return None

        base = HIRING_BY_SIZE.get(business.size_tier, 1.0)
        activity_factor = activity / SIZE_TIER_BASELINE.get(business.size_tier, 100_000)
        growth = 1.0 + 0.1 * (period.month % 4)  # mild quarterly cycle

        # Micro businesses rarely post jobs online
        if business.size_tier == SizeTier.MICRO and self._rng.random() > 0.3:
            return None

        return max(0.0, base * activity_factor * growth)


SIZE_TIER_BASELINE: dict[SizeTier, float] = {
    SizeTier.MICRO: 8_000,
    SizeTier.SMALL: 35_000,
    SizeTier.MEDIUM: 120_000,
    SizeTier.LARGE: 450_000,
    SizeTier.ENTERPRISE: 2_500_000,
}
