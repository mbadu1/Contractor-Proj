"""Shared synthetic adapter machinery."""

from __future__ import annotations

import math
from abc import abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from random import Random
from uuid import UUID

from adapters.base import AdapterConfig, BusinessCatalog, RegionFilter, SignalAdapter
from adapters.config import country_coverage
from adapters.intensity import SignalIntensityProvider
from core.models import Business, SignalObservation, SignalType


@dataclass
class SignalSpec:
    """One signal type emitted by an adapter."""

    signal_type: SignalType
    compute: str  # method name on adapter subclass


class SyntheticSignalAdapter(SignalAdapter):
    """
    Base for synthetic adapters with configurable noise, missingness, reliability.

    Subclasses define which signals they emit and how values derive from
    business attributes + latent activity intensity.
    """

    def __init__(
        self,
        catalog: BusinessCatalog,
        intensity: SignalIntensityProvider,
        config: AdapterConfig | None = None,
    ) -> None:
        self.catalog = catalog
        self.intensity = intensity
        self.config = config or AdapterConfig()
        self._rng = Random(self.config.seed)

    @property
    @abstractmethod
    def adapter_key(self) -> str:
        ...

    @abstractmethod
    def _signal_types(self) -> list[SignalType]:
        ...

    @abstractmethod
    def _compute_value(
        self,
        signal_type: SignalType,
        business: Business,
        period: datetime,
        activity: float,
    ) -> float | None:
        """Return raw signal value before noise, or None to skip this signal."""

    def _periods_since(self, since: datetime) -> list[datetime]:
        """Monthly period anchors from since through now (UTC)."""
        since = since.astimezone(timezone.utc)
        now = datetime.now(timezone.utc)
        periods: list[datetime] = []
        year, month = since.year, since.month
        while True:
            period = datetime(year, month, 1, tzinfo=timezone.utc)
            if period > now:
                break
            if period >= datetime(since.year, since.month, 1, tzinfo=timezone.utc):
                periods.append(period)
            month += 1
            if month > 12:
                month = 1
                year += 1
        return periods

    def _business_dropout(self, business_id: UUID) -> bool:
        """Entire adapter absent for this business."""
        h = hash(f"{self.adapter_key}:{business_id}") % 10_000
        threshold = self.config.business_dropout_rate * 10_000
        return h < threshold

    def _is_missing(self, business_id: UUID, signal_type: SignalType, period: datetime) -> bool:
        """Per-signal missingness."""
        h = hash(f"{self.adapter_key}:{business_id}:{signal_type.value}:{period:%Y-%m}") % 10_000
        threshold = self.config.missingness_rate * 10_000
        return h < threshold

    def _apply_noise(self, value: float, business_id: UUID, signal_type: SignalType) -> float:
        """Multiplicative log-normal noise."""
        h = hash(f"noise:{business_id}:{signal_type.value}") % 10_000
        self._rng.seed(h + (self.config.seed or 0))
        z = self._rng.gauss(0, self.config.noise_std)
        return max(0.0, value * math.exp(z))

    def _reliability(
        self,
        business: Business,
        signal_type: SignalType,
        coverage_factor: float = 1.0,
    ) -> float:
        h = hash(f"rel:{business.id}:{signal_type.value}") % 1000
        jitter = 0.9 + 0.2 * (h / 1000.0)
        rel = self.config.base_reliability * coverage_factor * jitter
        return round(min(1.0, max(0.05, rel)), 3)

    def _coverage_factor(self, business: Business) -> float:
        return country_coverage(business.country)

    def fetch(self, region: RegionFilter, since: datetime) -> list[SignalObservation]:
        observations: list[SignalObservation] = []
        businesses = self.catalog.list_businesses(region)

        for business in businesses:
            if self._business_dropout(business.id):
                continue

            coverage = self._coverage_factor(business)
            for period in self._periods_since(since):
                activity = self.intensity.monthly_intensity(business, period)

                for signal_type in self._signal_types():
                    if self._is_missing(business.id, signal_type, period):
                        continue

                    raw = self._compute_value(signal_type, business, period, activity)
                    if raw is None:
                        continue

                    value = self._apply_noise(raw, business.id, signal_type)
                    rel = self._reliability(business, signal_type, coverage)

                    observations.append(
                        SignalObservation(
                            business_id=business.id,
                            signal_type=signal_type,
                            value=round(value, 4),
                            timestamp=period,
                            source=self.source_name,
                            reliability=rel,
                        )
                    )

        return observations

    @property
    def source_name(self) -> str:
        return f"synthetic_{self.adapter_key}"
