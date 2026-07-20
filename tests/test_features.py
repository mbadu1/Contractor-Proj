"""Unit tests for feature builder."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pandas as pd

from core.models import (
    Business,
    BusinessCategory,
    SalesChannel,
    SignalType,
    SizeTier,
)
from engine.features import FeatureBuilder


def _business() -> Business:
    return Business(
        id=uuid4(),
        name="Test Shop",
        category=BusinessCategory.RESTAURANT_CAFE,
        country="US",
        city="Austin",
        latitude=30.27,
        longitude=-97.74,
        size_tier=SizeTier.SMALL,
        channels=[SalesChannel.PHYSICAL],
    )


def _signals(biz_id, period: str, payment: float) -> pd.DataFrame:
    ts = datetime(int(period[:4]), int(period[5:7]), 1, tzinfo=timezone.utc)
    return pd.DataFrame(
        [
            {
                "business_id": str(biz_id),
                "signal_type": SignalType.PAYMENT_VOLUME.value,
                "value": payment,
                "timestamp": ts,
                "source": "test",
                "reliability": 0.8,
            },
            {
                "business_id": str(biz_id),
                "signal_type": SignalType.REVIEW_VELOCITY.value,
                "value": 12.0,
                "timestamp": ts,
                "source": "test",
                "reliability": 0.7,
            },
        ]
    )


class TestFeatureBuilder:
    def test_builds_business_month_rows(self) -> None:
        biz = _business()
        signals = pd.concat(
            [
                _signals(biz.id, "2025-01", 10000),
                _signals(biz.id, "2025-02", 12000),
            ],
            ignore_index=True,
        )
        builder = FeatureBuilder()
        result = builder.build(signals, [biz])

        assert len(result.features) == 2
        assert "signal_coverage" in result.features.columns
        assert "mom_payment_volume" in result.features.columns
        assert result.features["business_id"].iloc[0] == str(biz.id)

    def test_coverage_reflects_missing_signals(self) -> None:
        biz = _business()
        signals = _signals(biz.id, "2025-01", 5000)
        builder = FeatureBuilder()
        result = builder.build(signals, [biz])
        row = result.features.iloc[0]
        assert 0 < row["signal_coverage"] < 1.0
        assert row["signals_present"] >= 2

    def test_category_dummies_created(self) -> None:
        biz = _business()
        signals = _signals(biz.id, "2025-01", 8000)
        result = FeatureBuilder().build(signals, [biz])
        cat_cols = [c for c in result.feature_columns if c.startswith("cat_")]
        assert len(cat_cols) >= 1

    def test_empty_signals_returns_empty(self) -> None:
        biz = _business()
        result = FeatureBuilder().build(pd.DataFrame(), [biz])
        assert result.features.empty
