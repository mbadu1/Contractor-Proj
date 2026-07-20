"""Unit tests for validation metrics and promotion gate."""

from __future__ import annotations

from engine.validation import should_promote
from core.models import ValidationReport


def _report(mape: float, n: int = 100) -> ValidationReport:
    return ValidationReport(
        model_version="test",
        n_observations=n,
        mape=mape,
        median_ape=mape * 0.8,
        interval_coverage=80.0,
        mean_confidence=70.0,
    )


class TestShouldPromote:
    def test_first_model_promotes(self) -> None:
        ok, reason = should_promote(_report(28.0), previous_mape=None)
        assert ok is True
        assert "First model" in reason

    def test_small_regression_within_tolerance_promotes(self) -> None:
        # 28 → 29 is ~3.6% relative regression (< 5%)
        ok, reason = should_promote(_report(29.0), previous_mape=28.0, tolerance=0.05)
        assert ok is True
        assert "promote" in reason.lower()

    def test_large_regression_rejects(self) -> None:
        # 28 → 35 is 25% relative regression
        ok, reason = should_promote(_report(35.0), previous_mape=28.0, tolerance=0.05)
        assert ok is False
        assert "reject" in reason.lower()

    def test_improvement_promotes(self) -> None:
        ok, _ = should_promote(_report(22.0), previous_mape=28.0)
        assert ok is True

    def test_empty_observations_rejects(self) -> None:
        ok, reason = should_promote(_report(10.0, n=0), previous_mape=None)
        assert ok is False
        assert "No validation" in reason
