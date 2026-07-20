"""Phase 2 demo: pluggable signal adapters."""

from __future__ import annotations

import tempfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from adapters import (
    AdapterConfig,
    InMemoryBusinessCatalog,
    RegionFilter,
    create_default_adapters,
    fetch_all_adapters,
)
from core.models import (
    Business,
    BusinessCategory,
    SalesChannel,
    SizeTier,
)
from db.repository import RevenueLensRepository


def _sample_businesses() -> list[Business]:
    """Diverse businesses across US, GH, UK for adapter demo."""
    specs = [
        ("Fresh Basket Market", BusinessCategory.GROCERY_SUPERMARKET, "US", "New York", 40.7128, -74.0060, SizeTier.MEDIUM, [SalesChannel.PHYSICAL, SalesChannel.HYBRID]),
        ("Kwame's Corner Shop", BusinessCategory.INFORMAL_RETAIL, "GH", "Accra", 5.6037, -0.1870, SizeTier.MICRO, [SalesChannel.PHYSICAL]),
        ("TechNova Online", BusinessCategory.ECOMMERCE_PURE_PLAY, "US", "Austin", 30.2672, -97.7431, SizeTier.SMALL, [SalesChannel.ECOMMERCE]),
        ("The Crown Pub", BusinessCategory.RESTAURANT_CAFE, "GB", "London", 51.5074, -0.1278, SizeTier.SMALL, [SalesChannel.PHYSICAL]),
        ("BuildRight Wholesale", BusinessCategory.WHOLESALE_DISTRIBUTION, "US", "Chicago", 41.8781, -87.6298, SizeTier.LARGE, [SalesChannel.HYBRID]),
        ("Accra Tech Hub", BusinessCategory.ELECTRONICS_RETAIL, "GH", "Accra", 5.5560, -0.1969, SizeTier.SMALL, [SalesChannel.HYBRID]),
    ]
    return [
        Business(
            id=uuid4(),
            name=name,
            category=cat,
            country=country,
            city=city,
            latitude=lat,
            longitude=lon,
            size_tier=tier,
            channels=channels,
        )
        for name, cat, country, city, lat, lon, tier, channels in specs
    ]


def main() -> None:
    print("=== Phase 2 Demo: Signal Adapters ===\n")

    businesses = _sample_businesses()
    catalog = InMemoryBusinessCatalog(businesses)
    config = AdapterConfig(noise_std=0.12, missingness_rate=0.10, seed=42)
    adapters = create_default_adapters(catalog, config=config, seed=42)

    since = datetime(2025, 1, 1, tzinfo=timezone.utc)
    region = RegionFilter()  # all businesses

    print(f"Adapters registered:       {len(adapters)}")
    for a in adapters:
        print(f"  • {a.source_name}")

    # Fetch per adapter
    print(f"\nFetching signals since {since.date()} …")
    per_adapter: dict[str, list] = {}
    for adapter in adapters:
        obs = adapter.fetch(region, since)
        per_adapter[adapter.source_name] = obs
        print(f"  {adapter.source_name:30s} → {len(obs):4d} observations")

    merged = fetch_all_adapters(adapters, region, since)
    print(f"\nTotal observations:        {len(merged.observations)}")

    # Coverage by business
    by_biz: dict = defaultdict(set)
    for o in merged.observations:
        by_biz[o.business_id].add(o.signal_type.value)

    print("\n--- Signal Coverage by Business ---")
    biz_map = {b.id: b for b in businesses}
    for bid, signals in sorted(by_biz.items(), key=lambda x: -len(x[1])):
        b = biz_map[bid]
        print(f"  {b.name:25s} ({b.country}) → {len(signals):2d} signal types")

    # Payment penetration comparison (GH informal vs US ecommerce)
    gh_informal = next(b for b in businesses if b.category == BusinessCategory.INFORMAL_RETAIL)
    us_ecom = next(b for b in businesses if b.category == BusinessCategory.ECOMMERCE_PURE_PLAY)

    def avg_payment(biz_id):
        vals = [
            o.value for o in merged.observations
            if o.business_id == biz_id and o.signal_type.value == "payment_volume"
        ]
        return sum(vals) / len(vals) if vals else 0

    print("\n--- Digital Payment Penetration (avg payment_volume) ---")
    print(f"  Kwame's Corner Shop (GH informal):  ${avg_payment(gh_informal.id):,.0f}/mo")
    print(f"  TechNova Online (US ecommerce):     ${avg_payment(us_ecom.id):,.0f}/mo")

    # Missingness demo with high missingness config
    sparse_config = AdapterConfig(missingness_rate=0.50, seed=99)
    sparse_adapter = adapters[0]  # payments
    sparse_adapter.config = sparse_config
    sparse_obs = sparse_adapter.fetch(region, since)
    full_obs = per_adapter["synthetic_digital_payments"]
    print("\n--- Missingness (payments adapter) ---")
    print(f"  Default (10% missing):  {len(full_obs)} observations")
    print(f"  Sparse (50% missing):   {len(sparse_obs)} observations")

    # Persist to DuckDB
    with tempfile.TemporaryDirectory() as tmp:
        repo = RevenueLensRepository(Path(tmp) / "phase2.duckdb")
        repo.upsert_businesses(businesses)
        repo.insert_signal_observations(merged.observations)

        stored = repo.conn.execute("SELECT COUNT(*) FROM signal_observations").fetchone()[0]
        sources = repo.conn.execute(
            "SELECT source, COUNT(*) FROM signal_observations GROUP BY source ORDER BY 2 DESC"
        ).fetchall()

        print("\n--- Persisted to DuckDB ---")
        print(f"  Total stored: {stored}")
        for src, cnt in sources:
            print(f"    {src}: {cnt}")

        # Reliability distribution
        rel_stats = repo.conn.execute(
            "SELECT MIN(reliability), AVG(reliability), MAX(reliability) FROM signal_observations"
        ).fetchone()
        print(f"\n  Reliability range: {rel_stats[0]:.3f} – {rel_stats[2]:.3f} (avg {rel_stats[1]:.3f})")

        repo.close()

    type_counts = Counter(o.signal_type.value for o in merged.observations)
    print("\n--- Signal Types Emitted ---")
    for st, cnt in type_counts.most_common():
        print(f"  {st}: {cnt}")

    print("\nPhase 2 complete ✓")


if __name__ == "__main__":
    main()
