"""Backtesting and model health validation."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from core.models import CalibrationBin, SegmentMetrics, ValidationReport
from db.repository import RevWatchRepository

# Absolute percentage error cap to avoid extreme outliers dominating MAPE
_APE_CAP = 5.0  # 500%


@dataclass
class ValidationConfig:
    """Controls how validation compares estimates to ground truth."""

    # Exclude labeled training businesses from holdout metrics when provided
    exclude_business_ids: set[str] | None = None
    confidence_bins: int = 5
    mape_regression_tolerance: float = 0.05  # promote if new_mape <= old * 1.05


def _ape(estimate: float, truth: float) -> float:
    if truth <= 0:
        return float("nan")
    return min(abs(estimate - truth) / truth, _APE_CAP)


def load_joined_frame(
    repo: RevWatchRepository,
    model_version: str,
    exclude_business_ids: set[str] | None = None,
) -> pd.DataFrame:
    """Join estimates to true revenue (and business attributes) for validation."""
    rows = repo.conn.execute(
        """
        SELECT
            e.business_id,
            e.period,
            e.point_estimate,
            e.ci_low,
            e.ci_high,
            e.confidence_score,
            tr.revenue AS true_revenue,
            b.category,
            b.country,
            b.city,
            b.size_tier
        FROM revenue_estimates e
        JOIN true_revenue tr
          ON tr.business_id = e.business_id AND tr.period = e.period
        JOIN businesses b ON b.id = e.business_id
        WHERE e.model_version = ?
        """,
        [model_version],
    ).fetchall()

    df = pd.DataFrame(
        rows,
        columns=[
            "business_id",
            "period",
            "point_estimate",
            "ci_low",
            "ci_high",
            "confidence_score",
            "true_revenue",
            "category",
            "country",
            "city",
            "size_tier",
        ],
    )
    if df.empty:
        return df

    if exclude_business_ids:
        df = df[~df["business_id"].isin(exclude_business_ids)].copy()

    df["ape"] = [
        _ape(float(e), float(t))
        for e, t in zip(df["point_estimate"], df["true_revenue"])
    ]
    df["in_interval"] = (
        (df["true_revenue"] >= df["ci_low"]) & (df["true_revenue"] <= df["ci_high"])
    ).astype(float)
    return df.dropna(subset=["ape"])


def _segment_metrics(df: pd.DataFrame, segment_col: str) -> list[SegmentMetrics]:
    out: list[SegmentMetrics] = []
    for value, group in df.groupby(segment_col):
        if len(group) == 0:
            continue
        out.append(
            SegmentMetrics(
                segment_type=segment_col,
                segment_value=str(value),
                n_observations=len(group),
                mape=round(float(group["ape"].mean()) * 100, 2),
                interval_coverage=round(float(group["in_interval"].mean()) * 100, 2),
                median_ape=round(float(group["ape"].median()) * 100, 2),
                mean_confidence=round(float(group["confidence_score"].mean()), 2),
            )
        )
    return sorted(out, key=lambda m: m.mape)


def _calibration_bins(df: pd.DataFrame, n_bins: int) -> list[CalibrationBin]:
    if df.empty:
        return []
    edges = np.linspace(0, 100, n_bins + 1)
    bins: list[CalibrationBin] = []
    for i in range(n_bins):
        low, high = float(edges[i]), float(edges[i + 1])
        if i == n_bins - 1:
            mask = (df["confidence_score"] >= low) & (df["confidence_score"] <= high)
        else:
            mask = (df["confidence_score"] >= low) & (df["confidence_score"] < high)
        group = df[mask]
        if group.empty:
            continue
        bins.append(
            CalibrationBin(
                confidence_bin_low=low,
                confidence_bin_high=high,
                n_observations=len(group),
                mean_confidence=round(float(group["confidence_score"].mean()), 2),
                mape=round(float(group["ape"].mean()) * 100, 2),
                interval_coverage=round(float(group["in_interval"].mean()) * 100, 2),
            )
        )
    return bins


def run_validation(
    repo: RevWatchRepository,
    model_version: str,
    config: ValidationConfig | None = None,
) -> ValidationReport:
    """
    Backtest estimates against hidden true revenue.

    Reports overall MAPE, interval coverage, calibration, and
    segments by category / size_tier / city.
    """
    cfg = config or ValidationConfig()
    df = load_joined_frame(repo, model_version, cfg.exclude_business_ids)

    if df.empty:
        return ValidationReport(
            model_version=model_version,
            n_observations=0,
            mape=0.0,
            median_ape=0.0,
            interval_coverage=0.0,
            mean_confidence=0.0,
            notes="No joined estimate/truth rows for validation",
        )

    segments = (
        _segment_metrics(df, "category")
        + _segment_metrics(df, "size_tier")
        + _segment_metrics(df, "city")
    )

    return ValidationReport(
        model_version=model_version,
        n_observations=len(df),
        mape=round(float(df["ape"].mean()) * 100, 2),
        median_ape=round(float(df["ape"].median()) * 100, 2),
        interval_coverage=round(float(df["in_interval"].mean()) * 100, 2),
        mean_confidence=round(float(df["confidence_score"].mean()), 2),
        segment_metrics=segments,
        calibration=_calibration_bins(df, cfg.confidence_bins),
        notes="Holdout validation vs true_revenue",
    )


def should_promote(
    new_report: ValidationReport,
    previous_mape: float | None,
    tolerance: float = 0.05,
) -> tuple[bool, str]:
    """
    Promotion gate: promote only if MAPE does not regress more than tolerance.

    Relative rule: new_mape <= previous_mape * (1 + tolerance).
    First model always promotes when it has observations.
    """
    if new_report.n_observations == 0:
        return False, "No validation observations — reject"

    if previous_mape is None:
        return True, f"First model — promote (MAPE={new_report.mape:.1f}%)"

    ceiling = previous_mape * (1.0 + tolerance)
    if new_report.mape <= ceiling:
        return (
            True,
            f"MAPE {new_report.mape:.1f}% within {tolerance*100:.0f}% of "
            f"previous {previous_mape:.1f}% (ceiling {ceiling:.1f}%) — promote",
        )
    return (
        False,
        f"MAPE regressed from {previous_mape:.1f}% to {new_report.mape:.1f}% "
        f"(ceiling {ceiling:.1f}%) — reject",
    )
