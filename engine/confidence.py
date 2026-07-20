"""Confidence scoring for revenue estimates."""

from __future__ import annotations

import math


def compute_confidence_score(
    signal_coverage: float,
    signal_agreement: float,
    interval_width_ratio: float,
    avg_reliability: float = 0.5,
) -> float:
    """
    Compute 0–100 confidence score from observable quality metrics.

    Components:
    - signal_coverage: share of signal types present (0–1)
    - signal_agreement: 1 - normalized variance across per-signal sub-estimates (0–1)
    - interval_width_ratio: (ci_high - ci_low) / point_estimate — lower is better
    - avg_reliability: mean adapter reliability for the business-month
    """
    coverage = max(0.0, min(1.0, signal_coverage))
    agreement = max(0.0, min(1.0, signal_agreement))
    reliability = max(0.0, min(1.0, avg_reliability))

    # Narrow intervals → higher confidence; cap ratio influence
    interval_penalty = max(0.0, min(1.0, interval_width_ratio / 2.0))
    interval_score = 1.0 - interval_penalty

    score = (
        0.35 * coverage
        + 0.25 * agreement
        + 0.25 * interval_score
        + 0.15 * reliability
    ) * 100.0

    return round(max(0.0, min(100.0, score)), 1)


def signal_agreement(sub_estimates: list[float]) -> float:
    """
    Agreement across per-signal sub-estimates (0–1, higher = more agreement).

    Uses coefficient of variation inverted.
    """
    if len(sub_estimates) < 2:
        return 0.5 if sub_estimates else 0.0

    vals = [v for v in sub_estimates if v > 0]
    if len(vals) < 2:
        return 0.5

    mean = sum(vals) / len(vals)
    if mean <= 0:
        return 0.0

    variance = sum((v - mean) ** 2 for v in vals) / len(vals)
    cv = math.sqrt(variance) / mean
    return max(0.0, min(1.0, 1.0 - cv))


def interval_width_ratio(ci_low: float, ci_high: float, point: float) -> float:
    if point <= 0:
        return 1.0
    return max(0.0, (ci_high - ci_low) / point)
