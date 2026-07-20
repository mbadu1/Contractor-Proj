"""Abstract signal adapter interface and shared types."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol
from uuid import UUID

from core.models import Business, SignalObservation


@dataclass(frozen=True)
class RegionFilter:
    """Geographic / business scope for adapter fetch calls."""

    country: str | None = None
    city: str | None = None
    business_ids: frozenset[UUID] | None = None

    def matches(self, business: Business) -> bool:
        if self.business_ids is not None and business.id not in self.business_ids:
            return False
        if self.country is not None and business.country.upper() != self.country.upper():
            return False
        if self.city is not None and business.city.lower() != self.city.lower():
            return False
        return True


@dataclass
class AdapterConfig:
    """Configurable noise, missingness, and reliability for synthetic adapters."""

    noise_std: float = 0.15
    missingness_rate: float = 0.12
    base_reliability: float = 0.75
    seed: int | None = None
    # Per-business signal absence: if True, a business may miss ALL signals from this adapter
    business_dropout_rate: float = 0.05


class BusinessCatalog(Protocol):
    """Read-only business registry queried by adapters."""

    def list_businesses(self, region: RegionFilter | None = None) -> list[Business]:
        ...


class InMemoryBusinessCatalog:
    """Simple catalog backed by an in-memory business list."""

    def __init__(self, businesses: list[Business]) -> None:
        self._businesses = list(businesses)

    def list_businesses(self, region: RegionFilter | None = None) -> list[Business]:
        if region is None:
            return list(self._businesses)
        return [b for b in self._businesses if region.matches(b)]


class SignalAdapter(ABC):
    """
    Pluggable signal source.

    Real-world implementations (payments, logistics, etc.) and synthetic
    implementations both implement this interface. The estimation engine
    depends only on SignalObservation outputs, never on adapter internals.
    """

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Provenance label stored on each SignalObservation."""

    @abstractmethod
    def fetch(
        self,
        region: RegionFilter,
        since: datetime,
    ) -> list[SignalObservation]:
        """Return observations for businesses in region with timestamp >= since."""


@dataclass
class AdapterRunStats:
    """Summary stats from a single adapter fetch pass."""

    adapter: str
    businesses_scanned: int = 0
    businesses_with_signals: int = 0
    observations_emitted: int = 0
    observations_skipped_missing: int = 0
    observations_skipped_dropout: int = 0


@dataclass
class MultiAdapterResult:
    observations: list[SignalObservation] = field(default_factory=list)
    stats: list[AdapterRunStats] = field(default_factory=list)


def fetch_all_adapters(
    adapters: list[SignalAdapter],
    region: RegionFilter,
    since: datetime,
) -> MultiAdapterResult:
    """Run multiple adapters and merge observations (estimation engine entry point)."""
    result = MultiAdapterResult()
    for adapter in adapters:
        obs = adapter.fetch(region, since)
        result.observations.extend(obs)
    return result
