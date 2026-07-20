"""Activity intensity providers — Phase 3 will supply revenue-driven values."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

from adapters.config import (
    CATEGORY_MULTIPLIER,
    DEFAULT_CATEGORY_MULTIPLIER,
    SIZE_TIER_SCALE,
)
from core.models import Business


class SignalIntensityProvider(Protocol):
    """
    Maps business + time to latent activity scale.

    Phase 3 implements this from hidden true revenue. Phase 2 uses
    attribute-based latent activity for adapter demos.
    """

    def monthly_intensity(self, business: Business, period: datetime) -> float:
        ...


class LatentActivityProvider:
    """
    Attribute-based activity proxy for Phase 2 adapter testing.

    Not ground truth — replaced by revenue-driven provider in Phase 3.
    """

    def __init__(self, seed: int | None = None) -> None:
        self._seed = seed

    def _business_factor(self, business: Business) -> float:
        import hashlib

        h = hashlib.md5(str(business.id).encode(), usedforsecurity=False).hexdigest()
        jitter = (int(h[:8], 16) % 1000) / 1000.0  # 0..0.999 stable per business
        jitter = 0.7 + 0.6 * jitter  # 0.7 .. 1.3
        cat = CATEGORY_MULTIPLIER.get(business.category, DEFAULT_CATEGORY_MULTIPLIER)
        size = SIZE_TIER_SCALE[business.size_tier]
        return size * cat * jitter

    def monthly_intensity(self, business: Business, period: datetime) -> float:
        base = self._business_factor(business)
        # Mild seasonality: Dec +15%, Jan -10%
        month = period.month
        seasonal = 1.0
        if month == 12:
            seasonal = 1.15
        elif month == 1:
            seasonal = 0.90
        elif month in (6, 7):
            seasonal = 1.05
        return base * seasonal


class RevenueDrivenIntensityProvider:
    """
    Stub for Phase 3 — looks up true monthly revenue by business + period.

    Phase 2 defines the interface; implementation added in simulation/generator.
    """

    def __init__(self, revenue_lookup: dict[tuple[UUID, str], float]) -> None:
        self._lookup = revenue_lookup

    def monthly_intensity(self, business: Business, period: datetime) -> float:
        key = (business.id, period.strftime("%Y-%m"))
        if key not in self._lookup:
            raise KeyError(f"No revenue for {business.id} @ {key}")
        return self._lookup[key]
