"""Tests for synthetic ground truth generation."""

from __future__ import annotations

import tempfile
from collections import Counter
from pathlib import Path

import pytest

from core.models import SignalType
from db.repository import RevWatchRepository
from simulation import GeneratorConfig, SyntheticUniverseGenerator
from simulation.revenue import RevenueEngine, RevenueEngineConfig


class TestRevenueEngine:
    def test_generates_24_months(self) -> None:
        from core.models import Business, BusinessCategory, SalesChannel, SizeTier
        from uuid import uuid4

        biz = Business(
            id=uuid4(),
            name="Test Co",
            category=BusinessCategory.RESTAURANT_CAFE,
            country="US",
            city="Austin",
            latitude=30.0,
            longitude=-97.0,
            size_tier=SizeTier.SMALL,
            channels=[SalesChannel.PHYSICAL],
        )
        engine = RevenueEngine(RevenueEngineConfig(months=24, seed=1))
        records = engine.generate_for_business(biz)
        assert len(records) == 24
        periods = [r.period for r in records]
        assert periods == sorted(periods)
        assert all(r.revenue >= 0 for r in records)

    def test_log_normal_spread(self) -> None:
        from core.models import Business, BusinessCategory, SalesChannel, SizeTier
        from uuid import uuid4

        engine = RevenueEngine(RevenueEngineConfig(months=1, seed=2))
        revenues = []
        for i in range(100):
            biz = Business(
                id=uuid4(),
                name=f"Biz {i}",
                category=BusinessCategory.GROCERY_SUPERMARKET,
                country="US",
                city="NYC",
                latitude=40.7,
                longitude=-74.0,
                size_tier=SizeTier.MEDIUM,
                channels=[SalesChannel.PHYSICAL],
            )
            revenues.append(engine.generate_for_business(biz)[0].revenue)
        assert max(revenues) > min(revenues) * 2


class TestSyntheticUniverseGenerator:
    def test_generates_expected_counts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "test.duckdb"
            config = GeneratorConfig(n_businesses=120, db_path=db, seed=99)
            result = SyntheticUniverseGenerator(config).run()

            assert len(result.businesses) == 120
            assert len(result.true_revenue) == 120 * 24
            assert result.signal_count > 0

            repo = RevWatchRepository(db)
            assert repo.count_businesses() == 120
            assert repo.count_true_revenue() == 120 * 24
            repo.close()

    def test_all_businesses_are_us(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "test.duckdb"
            config = GeneratorConfig(n_businesses=1000, db_path=db, seed=7)
            result = SyntheticUniverseGenerator(config).run()
            counts = Counter(b.country for b in result.businesses)
            assert counts == {"US": 1000}

    def test_informal_retail_has_sparser_payment_signals(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "test.duckdb"
            config = GeneratorConfig(n_businesses=300, db_path=db, seed=11)
            SyntheticUniverseGenerator(config).run()
            repo = RevWatchRepository(db)

            def payment_rate(category: str) -> float:
                row = repo.conn.execute(
                    """
                    SELECT
                        COUNT(DISTINCT CASE WHEN s.signal_type = 'payment_volume' THEN b.id END),
                        COUNT(DISTINCT b.id)
                    FROM businesses b
                    LEFT JOIN signal_observations s ON s.business_id = b.id
                    WHERE b.category = ?
                    """,
                    [category],
                ).fetchone()
                return row[0] / max(1, row[1])

            informal_rate = payment_rate("informal_retail")
            ecom_rate = payment_rate("ecommerce_pure_play")
            assert ecom_rate >= informal_rate
            repo.close()

    def test_true_revenue_persisted_separately(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "test.duckdb"
            config = GeneratorConfig(n_businesses=50, db_path=db, seed=3)
            result = SyntheticUniverseGenerator(config).run()
            repo = RevWatchRepository(db)
            biz_id = result.businesses[0].id
            history = repo.get_true_revenue(biz_id, limit=24)
            assert len(history) == 24
            assert history[0].revenue > 0
            repo.close()

    def test_signals_derived_from_revenue_not_latent(self) -> None:
        """Payment volume should correlate positively with true revenue."""
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "test.duckdb"
            config = GeneratorConfig(n_businesses=200, db_path=db, seed=5)
            SyntheticUniverseGenerator(config).run()
            repo = RevWatchRepository(db)
            corr = repo.conn.execute(
                """
                SELECT CORR(tr.revenue, s.value)
                FROM true_revenue tr
                JOIN signal_observations s
                  ON s.business_id = tr.business_id
                 AND strftime(s.timestamp, '%Y-%m') = tr.period
                WHERE s.signal_type = 'payment_volume'
                """
            ).fetchone()[0]
            assert corr is not None
            assert corr > 0.5
            repo.close()
