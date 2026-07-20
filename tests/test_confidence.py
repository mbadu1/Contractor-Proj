"""Unit tests for confidence scoring."""

from __future__ import annotations

import pytest

from engine.confidence import (
    compute_confidence_score,
    interval_width_ratio,
    signal_agreement,
)


class TestConfidenceScore:
    def test_high_quality_inputs_score_high(self) -> None:
        score = compute_confidence_score(
            signal_coverage=0.9,
            signal_agreement=0.85,
            interval_width_ratio=0.3,
            avg_reliability=0.8,
        )
        assert score >= 70.0

    def test_sparse_signals_score_low(self) -> None:
        score = compute_confidence_score(
            signal_coverage=0.1,
            signal_agreement=0.2,
            interval_width_ratio=1.5,
            avg_reliability=0.3,
        )
        assert score <= 40.0

    def test_score_bounded_0_100(self) -> None:
        score = compute_confidence_score(
            signal_coverage=1.5,
            signal_agreement=-0.5,
            interval_width_ratio=5.0,
            avg_reliability=2.0,
        )
        assert 0.0 <= score <= 100.0


class TestSignalAgreement:
    def test_identical_estimates_high_agreement(self) -> None:
        assert signal_agreement([100_000, 100_000, 102_000]) > 0.8

    def test_divergent_estimates_low_agreement(self) -> None:
        assert signal_agreement([10_000, 500_000, 50_000]) < 0.5

    def test_single_estimate_returns_moderate(self) -> None:
        assert signal_agreement([50_000]) == 0.5


class TestIntervalWidth:
    def test_narrow_interval_low_ratio(self) -> None:
        ratio = interval_width_ratio(90_000, 110_000, 100_000)
        assert ratio == pytest.approx(0.2)

    def test_zero_point_returns_one(self) -> None:
        assert interval_width_ratio(0, 100, 0) == 1.0
