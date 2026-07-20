"""Unit tests for entity resolution."""

from uuid import UUID

import pytest

from core.entity_resolution import (
    EntityResolutionConfig,
    haversine_km,
    name_similarity,
    normalize_name,
    resolve_entities,
)
from core.models import (
    BusinessCategory,
    RawBusinessRecord,
    SalesChannel,
    SizeTier,
)


def _record(
    source: str,
    source_id: str,
    name: str,
    lat: float = 40.7128,
    lon: float = -74.0060,
    country: str = "US",
    city: str = "New York",
) -> RawBusinessRecord:
    return RawBusinessRecord(
        source=source,
        source_id=source_id,
        name=name,
        category=BusinessCategory.RESTAURANT_CAFE,
        country=country,
        city=city,
        latitude=lat,
        longitude=lon,
        size_tier=SizeTier.SMALL,
        channels=[SalesChannel.PHYSICAL],
    )


class TestNormalizeName:
    def test_strips_legal_suffixes(self) -> None:
        assert normalize_name("Acme Coffee LLC") == "acme coffee"
        assert normalize_name("Global Foods, Inc.") == "global foods"

    def test_case_and_punctuation_insensitive(self) -> None:
        assert normalize_name("Joe's Pizza!") == normalize_name("JOES PIZZA")

    def test_empty_after_strip_returns_empty(self) -> None:
        assert normalize_name("Inc.") == ""


class TestNameSimilarity:
    def test_similar_names_score_high(self) -> None:
        score = name_similarity("Starbucks Coffee", "Starbucks Coffee LLC")
        assert score >= 85.0

    def test_different_names_score_low(self) -> None:
        score = name_similarity("McDonald's", "Burger King")
        assert score < 70.0


class TestHaversine:
    def test_same_point_zero_distance(self) -> None:
        assert haversine_km(40.0, -74.0, 40.0, -74.0) == pytest.approx(0.0, abs=0.01)

    def test_known_distance_reasonable(self) -> None:
        # NYC to Philadelphia ~130 km
        dist = haversine_km(40.7128, -74.0060, 39.9526, -75.1652)
        assert 100 < dist < 160


class TestResolveEntities:
    def test_empty_input(self) -> None:
        result = resolve_entities([])
        assert result.canonical_businesses == []
        assert result.source_to_canonical == {}

    def test_unique_records_stay_separate(self) -> None:
        records = [
            _record("src_a", "1", "Alpha Cafe", lat=40.71, lon=-74.01),
            _record("src_b", "2", "Beta Bakery", lat=40.80, lon=-73.95),
        ]
        result = resolve_entities(records)
        assert len(result.canonical_businesses) == 2
        assert len(result.merge_groups) == 0

    def test_duplicate_records_merged(self) -> None:
        records = [
            _record("google", "g1", "Joe's Pizza", lat=40.7500, lon=-73.9900),
            _record("yelp", "y1", "Joes Pizza Inc", lat=40.7501, lon=-73.9901),
        ]
        result = resolve_entities(records)
        assert len(result.canonical_businesses) == 1
        assert len(result.merge_groups) == 1
        canonical_id = result.canonical_businesses[0].id
        assert result.source_to_canonical[("google", "g1")] == canonical_id
        assert result.source_to_canonical[("yelp", "y1")] == canonical_id

    def test_different_country_not_merged(self) -> None:
        records = [
            _record("a", "1", "Global Mart", lat=51.5074, lon=-0.1278, country="GB", city="London"),
            _record("b", "2", "Global Mart", lat=51.5075, lon=-0.1279, country="US", city="London"),
        ]
        result = resolve_entities(records)
        assert len(result.canonical_businesses) == 2

    def test_far_apart_same_name_not_merged(self) -> None:
        records = [
            _record("a", "1", "City Pharmacy", lat=40.71, lon=-74.01),
            _record("b", "2", "City Pharmacy", lat=34.05, lon=-118.24),
        ]
        config = EntityResolutionConfig(merge_geo_radius_km=0.5)
        result = resolve_entities(records, config)
        assert len(result.canonical_businesses) == 2

    def test_canonical_picks_richest_metadata(self) -> None:
        records = [
            RawBusinessRecord(
                source="a",
                source_id="1",
                name="Quick Stop",
                category=None,
                country="US",
                city="Chicago",
                latitude=41.8781,
                longitude=-87.6298,
                size_tier=None,
                channels=None,
            ),
            RawBusinessRecord(
                source="b",
                source_id="2",
                name="Quick Stop Convenience Store",
                category=BusinessCategory.CONVENIENCE_STORE,
                country="US",
                city="Chicago",
                latitude=41.8782,
                longitude=-87.6299,
                size_tier=SizeTier.MEDIUM,
                channels=[SalesChannel.HYBRID],
            ),
        ]
        result = resolve_entities(records)
        biz = result.canonical_businesses[0]
        assert biz.category == BusinessCategory.CONVENIENCE_STORE
        assert biz.size_tier == SizeTier.MEDIUM
        assert SalesChannel.HYBRID in biz.channels
        assert "Quick Stop Convenience" in biz.name

    def test_all_mappings_are_valid_uuids(self) -> None:
        records = [
            _record("s", "1", "Test Shop A", lat=40.0, lon=-74.0),
            _record("s", "2", "Test Shop B", lat=41.0, lon=-75.0),
        ]
        result = resolve_entities(records)
        for canonical_id in result.source_to_canonical.values():
            assert isinstance(canonical_id, UUID)
