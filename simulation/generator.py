"""Synthetic universe generator — businesses, true revenue, and derived signals."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from random import Random
from uuid import uuid4

from adapters import AdapterConfig, InMemoryBusinessCatalog, RegionFilter, create_default_adapters
from adapters.intensity import RevenueDrivenIntensityProvider
from core.models import (
    ALL_CATEGORIES,
    Business,
    BusinessCategory,
    SalesChannel,
    SizeTier,
    TrueRevenue,
)
from db.repository import RevenueLensRepository
from simulation.markets import (
    CATEGORY_CHANNELS,
    COUNTRY_CITIES,
    GH_CATEGORY_BOOST,
    MARKET_ADAPTER_PROFILES,
    MARKET_SHARES,
    NAME_CORES,
    NAME_PREFIXES,
    NAME_SUFFIXES,
    SIZE_TIER_WEIGHTS,
)
from simulation.revenue import RevenueEngine, RevenueEngineConfig


@dataclass
class GeneratorConfig:
    n_businesses: int = 5_000
    months: int = 24
    end_year: int = 2025
    end_month: int = 12
    seed: int = 42
    db_path: Path = field(default_factory=lambda: Path("data/revenuelens.duckdb"))
    clear_existing: bool = True


@dataclass
class GenerationResult:
    businesses: list[Business]
    true_revenue: list[TrueRevenue]
    signal_count: int
    db_path: Path


class SyntheticUniverseGenerator:
    """Generate businesses, hidden revenue, and adapter-derived signals."""

    def __init__(self, config: GeneratorConfig | None = None) -> None:
        self.config = config or GeneratorConfig()
        self._rng = Random(self.config.seed)
        self._revenue_config = RevenueEngineConfig(
            months=self.config.months,
            end_year=self.config.end_year,
            end_month=self.config.end_month,
            seed=self.config.seed,
        )
        self._revenue_engine = RevenueEngine(self._revenue_config)

    def _pick_size_tier(self) -> SizeTier:
        r = self._rng.random()
        cumulative = 0.0
        for tier, weight in SIZE_TIER_WEIGHTS:
            cumulative += weight
            if r <= cumulative:
                return tier
        return SizeTier.SMALL

    def _pick_category(self, country: str) -> BusinessCategory:
        categories = list(ALL_CATEGORIES)
        if country == "GH":
            weights = [1.8 if c in GH_CATEGORY_BOOST else 1.0 for c in categories]
        else:
            weights = [1.0] * len(categories)
        total = sum(weights)
        r = self._rng.random() * total
        cumulative = 0.0
        for cat, w in zip(categories, weights):
            cumulative += w
            if r <= cumulative:
                return cat
        return categories[0]

    def _pick_channels(self, category: BusinessCategory) -> list[SalesChannel]:
        if category in CATEGORY_CHANNELS:
            return list(CATEGORY_CHANNELS[category])
        r = self._rng.random()
        if category == BusinessCategory.ECOMMERCE_PURE_PLAY:
            return [SalesChannel.ECOMMERCE]
        if r < 0.55:
            return [SalesChannel.PHYSICAL]
        if r < 0.80:
            return [SalesChannel.HYBRID]
        return [SalesChannel.ECOMMERCE]

    def _make_name(self) -> str:
        return " ".join(
            filter(
                None,
                [
                    self._rng.choice(NAME_PREFIXES),
                    self._rng.choice(NAME_CORES),
                    self._rng.choice(NAME_SUFFIXES) or None,
                ],
            )
        )

    def generate_businesses(self) -> list[Business]:
        n = self.config.n_businesses
        counts = {c: int(n * share) for c, share in MARKET_SHARES.items()}
        remainder = n - sum(counts.values())
        for i, country in enumerate(MARKET_SHARES):
            if i < remainder:
                counts[country] += 1

        businesses: list[Business] = []
        for country, count in counts.items():
            cities = COUNTRY_CITIES[country]
            for _ in range(count):
                city, lat, lon = self._rng.choice(cities)
                jitter_lat = lat + self._rng.uniform(-0.08, 0.08)
                jitter_lon = lon + self._rng.uniform(-0.08, 0.08)
                category = self._pick_category(country)
                businesses.append(
                    Business(
                        id=uuid4(),
                        name=self._make_name(),
                        category=category,
                        country=country,
                        city=city,
                        latitude=round(jitter_lat, 6),
                        longitude=round(jitter_lon, 6),
                        size_tier=self._pick_size_tier(),
                        channels=self._pick_channels(category),
                    )
                )
        return businesses

    def _revenue_lookup(
        self, true_revenue: list[TrueRevenue]
    ) -> dict[tuple, float]:
        return {(r.business_id, r.period): r.revenue for r in true_revenue}

    def _adapter_config_for_country(self, country: str, adapter_key: str) -> AdapterConfig:
        profile = MARKET_ADAPTER_PROFILES[country]
        missingness = profile.missingness_rate
        if adapter_key == "digital_payments":
            missingness += profile.payment_missingness_boost
        end = datetime(
            self.config.end_year, self.config.end_month, 1, tzinfo=timezone.utc
        )
        return AdapterConfig(
            noise_std=0.14,
            missingness_rate=min(0.60, missingness),
            business_dropout_rate=profile.business_dropout_rate,
            base_reliability=profile.base_reliability,
            seed=self.config.seed,
            until=end,
        )

    def generate_signals(
        self,
        businesses: list[Business],
        true_revenue: list[TrueRevenue],
    ) -> list:
        from core.models import SignalObservation

        lookup = self._revenue_lookup(true_revenue)
        intensity = RevenueDrivenIntensityProvider(lookup)
        since_dt = RevenueEngine.period_start(
            RevenueEngine.first_period(self._revenue_config)
        )
        region = RegionFilter()

        all_obs: list[SignalObservation] = []
        by_country: dict[str, list[Business]] = {}
        for b in businesses:
            by_country.setdefault(b.country, []).append(b)

        for country, country_biz in by_country.items():
            catalog = InMemoryBusinessCatalog(country_biz)
            adapters = create_default_adapters(
                catalog,
                intensity=intensity,
                config=self._adapter_config_for_country(country, "default"),
                seed=self.config.seed,
            )
            # Apply per-adapter missingness overrides (esp. payments in GH)
            for adapter in adapters:
                adapter.config = self._adapter_config_for_country(
                    country, adapter.adapter_key
                )
            for adapter in adapters:
                all_obs.extend(adapter.fetch(region, since_dt))

        return all_obs

    def persist(
        self,
        businesses: list[Business],
        true_revenue: list[TrueRevenue],
        observations: list,
    ) -> RevenueLensRepository:
        repo = RevenueLensRepository(self.config.db_path)
        if self.config.clear_existing:
            for table in (
                "signal_observations",
                "true_revenue",
                "revenue_estimates",
                "source_mappings",
                "businesses",
            ):
                repo.conn.execute(f"DELETE FROM {table}")

        repo.upsert_businesses(businesses)
        repo.insert_true_revenue_batch(true_revenue)
        repo.insert_signal_observations(observations)
        return repo

    def run(self) -> GenerationResult:
        businesses = self.generate_businesses()
        true_revenue = self._revenue_engine.generate_all(businesses)
        observations = self.generate_signals(businesses, true_revenue)
        self.persist(businesses, true_revenue, observations)
        return GenerationResult(
            businesses=businesses,
            true_revenue=true_revenue,
            signal_count=len(observations),
            db_path=self.config.db_path,
        )


def generate_universe(
    n_businesses: int = 5_000,
    db_path: str | Path = "data/revenuelens.duckdb",
    seed: int = 42,
) -> GenerationResult:
    """Convenience entry point for full universe generation."""
    return SyntheticUniverseGenerator(
        GeneratorConfig(n_businesses=n_businesses, db_path=Path(db_path), seed=seed)
    ).run()
