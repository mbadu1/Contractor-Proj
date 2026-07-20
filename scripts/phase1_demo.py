"""Integration demo for Phase 1: core domain + data layer."""

from __future__ import annotations

import tempfile
from datetime import datetime, timezone
from pathlib import Path

from core.entity_resolution import resolve_entities
from core.models import (
    BusinessCategory,
    RawBusinessRecord,
    RevenueEstimate,
    SalesChannel,
    SignalObservation,
    SignalType,
    SizeTier,
)
from db.repository import RevenueLensRepository


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "phase1.duckdb"
        repo = RevenueLensRepository(db_path)

        # Simulate ingesting duplicate records from two sources
        raw_records = [
            RawBusinessRecord(
                source="google_places",
                source_id="gp-101",
                name="Joe's Fresh Market",
                category=BusinessCategory.GROCERY_SUPERMARKET,
                country="US",
                city="Chicago",
                latitude=41.8781,
                longitude=-87.6298,
                size_tier=SizeTier.MEDIUM,
                channels=[SalesChannel.PHYSICAL],
            ),
            RawBusinessRecord(
                source="openstreetmap",
                source_id="osm-8821",
                name="Joes Fresh Market",
                category=BusinessCategory.GROCERY_SUPERMARKET,
                country="US",
                city="Chicago",
                latitude=41.8782,
                longitude=-87.6299,
                size_tier=SizeTier.MEDIUM,
                channels=[SalesChannel.PHYSICAL],
            ),
            RawBusinessRecord(
                source="google_places",
                source_id="gp-202",
                name="TechHub Electronics",
                category=BusinessCategory.ELECTRONICS_RETAIL,
                country="US",
                city="Austin",
                latitude=30.2672,
                longitude=-97.7431,
                size_tier=SizeTier.SMALL,
                channels=[SalesChannel.HYBRID],
            ),
        ]

        print("=== Phase 1 Demo: Core Domain + Data Layer ===\n")

        # Entity resolution
        resolution = resolve_entities(raw_records)
        print(f"Raw records ingested:        {len(raw_records)}")
        print(f"Canonical businesses:        {len(resolution.canonical_businesses)}")
        print(f"Merge groups:                {len(resolution.merge_groups)}")
        for group in resolution.merge_groups:
            print(f"  Merged: {group}")

        # Persist
        repo.upsert_businesses(resolution.canonical_businesses)
        repo.upsert_source_mappings(resolution.source_to_canonical)

        # Insert sample signals and an estimate for the Chicago grocery business
        grocery_biz = next(
            b for b in resolution.canonical_businesses
            if b.category == BusinessCategory.GROCERY_SUPERMARKET
        )
        now = datetime(2025, 6, 1, tzinfo=timezone.utc)

        signals = [
            SignalObservation(
                business_id=grocery_biz.id,
                signal_type=SignalType.PAYMENT_TRANSACTION_COUNT,
                value=1240.0,
                timestamp=now,
                source="synthetic_payments",
                reliability=0.72,
            ),
            SignalObservation(
                business_id=grocery_biz.id,
                signal_type=SignalType.REVIEW_VELOCITY,
                value=18.5,
                timestamp=now,
                source="synthetic_reviews",
                reliability=0.65,
            ),
        ]
        repo.insert_signal_observations(signals)

        estimate = RevenueEstimate(
            business_id=grocery_biz.id,
            period="2025-06",
            point_estimate=185_000.0,
            ci_low=142_000.0,
            ci_high=238_000.0,
            confidence_score=68.5,
            signal_contributions={
                "payment_transaction_count": 0.42,
                "review_velocity": 0.31,
                "category_prior": 0.27,
            },
            model_version="demo-v0",
        )
        repo.upsert_revenue_estimate(estimate)

        # Read back
        print("\n--- Stored Businesses ---")
        for biz in repo.list_businesses():
            print(
                f"  {biz.name} | {biz.category.value} | {biz.city}, {biz.country} "
                f"| tier={biz.size_tier.value} | channels={[c.value for c in biz.channels]}"
            )

        print("\n--- Source → Canonical Mapping ---")
        for (source, sid), cid in resolution.source_to_canonical.items():
            resolved = repo.resolve_business_id(source, sid)
            print(f"  ({source}, {sid}) → {resolved}")

        print("\n--- Signals for Chicago Grocery Business ---")
        for sig in repo.get_signals_for_business(grocery_biz.id):
            print(
                f"  {sig.signal_type.value}: {sig.value} "
                f"(reliability={sig.reliability}, source={sig.source})"
            )

        latest = repo.get_latest_estimate(grocery_biz.id)
        assert latest is not None
        print("\n--- Latest Revenue Estimate ---")
        print(
            f"  Period: {latest.period} | Point: ${latest.point_estimate:,.0f} "
            f"| CI: [${latest.ci_low:,.0f}, ${latest.ci_high:,.0f}] "
            f"| Confidence: {latest.confidence_score:.1f}/100"
        )
        print(f"  Contributions: {latest.signal_contributions}")

        print(f"\nDatabase file: {db_path}")
        print(f"Business count: {repo.count_businesses()}")
        print("\nPhase 1 complete ✓")

        repo.close()


if __name__ == "__main__":
    main()
