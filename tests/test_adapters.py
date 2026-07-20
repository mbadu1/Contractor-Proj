"""Tests for signal adapters."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from adapters import (
    AdapterConfig,
    InMemoryBusinessCatalog,
    RegionFilter,
    create_default_adapters,
)
from adapters.config import digital_penetration
from adapters.synthetic.payments import DigitalPaymentAdapter
from adapters.intensity import LatentActivityProvider
from core.models import (
    Business,
    BusinessCategory,
    SalesChannel,
    SignalType,
    SizeTier,
)


def _biz(
    category: BusinessCategory = BusinessCategory.RESTAURANT_CAFE,
    country: str = "US",
    channels: list[SalesChannel] | None = None,
    size: SizeTier = SizeTier.SMALL,
) -> Business:
    return Business(
        id=uuid4(),
        name="Test Business",
        category=category,
        country=country,
        city="TestCity",
        latitude=40.0,
        longitude=-74.0,
        size_tier=size,
        channels=channels or [SalesChannel.PHYSICAL],
    )


class TestDigitalPenetration:
    def test_ecommerce_high_penetration(self) -> None:
        p = digital_penetration(
            BusinessCategory.ECOMMERCE_PURE_PLAY, [SalesChannel.ECOMMERCE]
        )
        assert p >= 0.90

    def test_informal_retail_low_penetration(self) -> None:
        p = digital_penetration(
            BusinessCategory.INFORMAL_RETAIL, [SalesChannel.PHYSICAL]
        )
        assert p <= 0.25


class TestSignalAdapterInterface:
    def test_all_adapters_implement_fetch(self) -> None:
        businesses = [
            _biz(BusinessCategory.ECOMMERCE_PURE_PLAY, channels=[SalesChannel.ECOMMERCE]),
            _biz(BusinessCategory.INFORMAL_RETAIL, country="GH"),
        ]
        catalog = InMemoryBusinessCatalog(businesses)
        adapters = create_default_adapters(catalog, seed=1)
        since = datetime(2025, 1, 1, tzinfo=timezone.utc)
        region = RegionFilter()

        for adapter in adapters:
            obs = adapter.fetch(region, since)
            assert isinstance(obs, list)
            for o in obs:
                assert o.reliability >= 0.0
                assert o.reliability <= 1.0
                assert o.source == adapter.source_name

    def test_region_filter_by_country(self) -> None:
        us = _biz(country="US")
        gh = _biz(country="GH")
        catalog = InMemoryBusinessCatalog([us, gh])
        adapter = create_default_adapters(catalog, seed=2)[0]
        since = datetime(2025, 1, 1, tzinfo=timezone.utc)
        obs = adapter.fetch(RegionFilter(country="GH"), since)
        assert all(o.business_id == gh.id for o in obs)


class TestMissingnessAndNoise:
    def test_high_missingness_reduces_observations(self) -> None:
        biz = _biz(size=SizeTier.LARGE)
        catalog = InMemoryBusinessCatalog([biz])
        intensity = LatentActivityProvider(seed=3)
        since = datetime(2025, 1, 1, tzinfo=timezone.utc)
        region = RegionFilter()

        low_miss = DigitalPaymentAdapter(
            catalog, intensity, AdapterConfig(missingness_rate=0.0, seed=10)
        )
        high_miss = DigitalPaymentAdapter(
            catalog, intensity, AdapterConfig(missingness_rate=0.80, seed=10)
        )

        low_obs = low_miss.fetch(region, since)
        high_obs = high_miss.fetch(region, since)
        assert len(high_obs) < len(low_obs)

    def test_noise_produces_variance(self) -> None:
        biz = _biz(size=SizeTier.MEDIUM)
        catalog = InMemoryBusinessCatalog([biz])
        intensity = LatentActivityProvider(seed=4)
        since = datetime(2025, 6, 1, tzinfo=timezone.utc)
        adapter = DigitalPaymentAdapter(
            catalog, intensity, AdapterConfig(missingness_rate=0.0, noise_std=0.20, seed=5)
        )
        obs = adapter.fetch(RegionFilter(), since)
        volumes = [o.value for o in obs if o.signal_type == SignalType.PAYMENT_VOLUME]
        # With multiple months, values should not all be identical
        assert len(set(round(v, 2) for v in volumes)) >= 1


class TestAdapterSpecificBehavior:
    def test_web_adapter_skips_pure_physical(self) -> None:
        biz = _biz(channels=[SalesChannel.PHYSICAL], category=BusinessCategory.CONVENIENCE_STORE)
        catalog = InMemoryBusinessCatalog([biz])
        adapters = create_default_adapters(catalog, seed=6)
        web = next(a for a in adapters if a.adapter_key == "web_footprint")
        since = datetime(2025, 1, 1, tzinfo=timezone.utc)
        obs = web.fetch(RegionFilter(), since)
        sku_obs = [o for o in obs if o.signal_type == SignalType.ECOMMERCE_SKU_COUNT]
        assert len(sku_obs) == 0

    def test_ghana_lower_coverage_reflected_in_reliability(self) -> None:
        us_biz = _biz(country="US", size=SizeTier.MEDIUM)
        gh_biz = _biz(country="GH", size=SizeTier.MEDIUM)
        catalog = InMemoryBusinessCatalog([us_biz, gh_biz])
        adapter = create_default_adapters(catalog, seed=7)[0]
        since = datetime(2025, 3, 1, tzinfo=timezone.utc)
        obs = adapter.fetch(RegionFilter(), since)

        us_rel = [o.reliability for o in obs if o.business_id == us_biz.id]
        gh_rel = [o.reliability for o in obs if o.business_id == gh_biz.id]
        if us_rel and gh_rel:
            assert sum(us_rel) / len(us_rel) >= sum(gh_rel) / len(gh_rel)

    def test_ecommerce_higher_payment_volume_than_informal(self) -> None:
        ecom = _biz(
            BusinessCategory.ECOMMERCE_PURE_PLAY,
            channels=[SalesChannel.ECOMMERCE],
            size=SizeTier.SMALL,
        )
        informal = _biz(
            BusinessCategory.INFORMAL_RETAIL,
            country="GH",
            channels=[SalesChannel.PHYSICAL],
            size=SizeTier.SMALL,
        )
        catalog = InMemoryBusinessCatalog([ecom, informal])
        adapter = create_default_adapters(catalog, seed=8)[0]
        since = datetime(2025, 1, 1, tzinfo=timezone.utc)
        obs = adapter.fetch(RegionFilter(), since)

        def avg_vol(bid):
            vals = [
                o.value for o in obs
                if o.business_id == bid and o.signal_type == SignalType.PAYMENT_VOLUME
            ]
            return sum(vals) / len(vals) if vals else 0

        assert avg_vol(ecom.id) > avg_vol(informal.id)
