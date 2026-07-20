"""Entity resolution: deduplicate businesses across sources."""

from __future__ import annotations

import math
import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field
from uuid import UUID, uuid4

from rapidfuzz import fuzz

from core.models import (
    Business,
    BusinessCategory,
    RawBusinessRecord,
    SalesChannel,
    SizeTier,
)

# Legal / noise tokens stripped during name normalization
_LEGAL_SUFFIXES = frozenset(
    {
        "inc",
        "incorporated",
        "llc",
        "ltd",
        "limited",
        "corp",
        "corporation",
        "co",
        "company",
        "plc",
        "gmbh",
        "sa",
        "bv",
        "pty",
        "lp",
        "llp",
    }
)

# Approximate km per degree latitude
_KM_PER_DEG_LAT = 111.0


@dataclass
class EntityResolutionConfig:
    """Tunable thresholds for matching."""

    name_similarity_threshold: float = 85.0
    geo_block_radius_km: float = 2.0
    merge_geo_radius_km: float = 0.5
    merge_name_threshold: float = 90.0


@dataclass
class EntityResolutionResult:
    """Output of entity resolution pass."""

    canonical_businesses: list[Business] = field(default_factory=list)
    source_to_canonical: dict[tuple[str, str], UUID] = field(default_factory=dict)
    merge_groups: list[list[tuple[str, str]]] = field(default_factory=list)


def normalize_name(name: str) -> str:
    """Normalize a business name for fuzzy comparison."""
    text = unicodedata.normalize("NFKD", name)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"[''`]", "", text)
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    tokens = [t for t in text.split() if t and t not in _LEGAL_SUFFIXES]
    return " ".join(tokens)


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in kilometers."""
    r = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    return 2 * r * math.asin(math.sqrt(min(1.0, a)))


def _geo_block_key(lat: float, lon: float, block_km: float) -> tuple[str, int, int]:
    """Grid cell key for geo proximity blocking."""
    lat_step = block_km / _KM_PER_DEG_LAT
    lon_step = block_km / (
        _KM_PER_DEG_LAT * max(math.cos(math.radians(lat)), 0.01)
    )
    return ("cell", int(lat / lat_step), int(lon / lon_step))


def _neighbor_block_keys(
    lat: float, lon: float, block_km: float
) -> list[tuple[str, int, int]]:
    """Return cell and adjacent cells for blocking lookup."""
    lat_step = block_km / _KM_PER_DEG_LAT
    lon_step = block_km / (
        _KM_PER_DEG_LAT * max(math.cos(math.radians(lat)), 0.01)
    )
    ci, cj = int(lat / lat_step), int(lon / lon_step)
    return [
        ("cell", ci + di, cj + dj)
        for di in (-1, 0, 1)
        for dj in (-1, 0, 1)
    ]


def name_similarity(a: str, b: str) -> float:
    """Token-set ratio fuzzy name similarity (0–100)."""
    norm_a, norm_b = normalize_name(a), normalize_name(b)
    if not norm_a or not norm_b:
        return 0.0
    return float(fuzz.token_set_ratio(norm_a, norm_b))


def _pick_category(records: list[RawBusinessRecord]) -> BusinessCategory:
    for r in records:
        if r.category is not None:
            return r.category
    return BusinessCategory.INFORMAL_RETAIL


def _pick_size_tier(records: list[RawBusinessRecord]) -> SizeTier:
    for r in records:
        if r.size_tier is not None:
            return r.size_tier
    return SizeTier.SMALL


def _pick_channels(records: list[RawBusinessRecord]) -> list[SalesChannel]:
    seen: set[SalesChannel] = set()
    for r in records:
        if r.channels:
            seen.update(r.channels)
    if seen:
        return sorted(seen, key=lambda c: c.value)
    return [SalesChannel.PHYSICAL]


def _pick_name(records: list[RawBusinessRecord]) -> str:
    """Prefer the longest normalized name as the canonical display name."""
    return max(records, key=lambda r: len(r.name.strip())).name.strip()


def _pick_location(records: list[RawBusinessRecord]) -> tuple[str, str, float, float]:
    """Average coordinates; mode-like pick for city/country."""
    country = records[0].country.strip().upper()
    city_counts: dict[str, int] = defaultdict(int)
    for r in records:
        city_counts[r.city.strip()] += 1
    city = max(city_counts, key=city_counts.get)
    lat = sum(r.latitude for r in records) / len(records)
    lon = sum(r.longitude for r in records) / len(records)
    return country, city, lat, lon


class UnionFind:
    """Disjoint-set for clustering duplicate records."""

    def __init__(self, n: int) -> None:
        self.parent = list(range(n))
        self.rank = [0] * n

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return
        if self.rank[ra] < self.rank[rb]:
            ra, rb = rb, ra
        self.parent[rb] = ra
        if self.rank[ra] == self.rank[rb]:
            self.rank[ra] += 1


def resolve_entities(
    records: list[RawBusinessRecord],
    config: EntityResolutionConfig | None = None,
) -> EntityResolutionResult:
    """
    Deduplicate raw business records into canonical Business entities.

    Pipeline:
    1. Geo proximity blocking to limit pairwise comparisons
    2. Fuzzy name match + tight geo distance to union duplicates
    3. Emit canonical businesses and source→canonical ID map
    """
    if config is None:
        config = EntityResolutionConfig()

    if not records:
        return EntityResolutionResult()

    n = len(records)
    uf = UnionFind(n)

    # Index records into geo blocks
    blocks: dict[tuple[str, int, int], list[int]] = defaultdict(list)
    for idx, rec in enumerate(records):
        for key in _neighbor_block_keys(
            rec.latitude, rec.longitude, config.geo_block_radius_km
        ):
            blocks[key].append(idx)

    compared: set[tuple[int, int]] = set()
    for indices in blocks.values():
        for i in range(len(indices)):
            for j in range(i + 1, len(indices)):
                a, b = indices[i], indices[j]
                pair = (min(a, b), max(a, b))
                if pair in compared:
                    continue
                compared.add(pair)

                ra, rb = records[a], records[b]
                if ra.country.strip().upper() != rb.country.strip().upper():
                    continue

                dist = haversine_km(
                    ra.latitude, ra.longitude, rb.latitude, rb.longitude
                )
                if dist > config.merge_geo_radius_km:
                    continue

                sim = name_similarity(ra.name, rb.name)
                if sim >= config.merge_name_threshold:
                    uf.union(a, b)

    # Build clusters
    clusters: dict[int, list[int]] = defaultdict(list)
    for idx in range(n):
        clusters[uf.find(idx)].append(idx)

    result = EntityResolutionResult()
    for cluster_indices in clusters.values():
        cluster_records = [records[i] for i in cluster_indices]
        canonical_id = uuid4()
        country, city, lat, lon = _pick_location(cluster_records)
        business = Business(
            id=canonical_id,
            name=_pick_name(cluster_records),
            category=_pick_category(cluster_records),
            country=country,
            city=city,
            latitude=lat,
            longitude=lon,
            size_tier=_pick_size_tier(cluster_records),
            channels=_pick_channels(cluster_records),
        )
        result.canonical_businesses.append(business)

        merge_group: list[tuple[str, str]] = []
        for rec in cluster_records:
            key = (rec.source, rec.source_id)
            result.source_to_canonical[key] = canonical_id
            merge_group.append(key)
        if len(merge_group) > 1:
            result.merge_groups.append(merge_group)

    return result


def find_canonical_id(
    source: str,
    source_id: str,
    mapping: dict[tuple[str, str], UUID],
) -> UUID | None:
    """Look up canonical business ID for a source record."""
    return mapping.get((source, source_id))
