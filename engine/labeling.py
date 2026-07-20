"""Labeled training subset selection (public filings analog)."""

from __future__ import annotations

from dataclasses import dataclass
from random import Random
from uuid import UUID

from core.models import Business, SizeTier

# Selection bias: public filings disproportionately cover large firms
SIZE_SELECTION_WEIGHT: dict[SizeTier, float] = {
    SizeTier.MICRO: 0.3,
    SizeTier.SMALL: 0.6,
    SizeTier.MEDIUM: 1.2,
    SizeTier.LARGE: 2.5,
    SizeTier.ENTERPRISE: 4.0,
}

CATEGORY_SELECTION_BOOST: frozenset[str] = frozenset(
    {
        "financial_services",
        "manufacturing",
        "wholesale_distribution",
        "healthcare_provider",
    }
)


@dataclass
class LabelingResult:
    """Businesses selected as having known revenue (training labels)."""

    labeled_business_ids: set[UUID]
    selection_probability: dict[UUID, float]
    sample_weights: dict[UUID, float]


def _selection_probability(business: Business) -> float:
    w = SIZE_SELECTION_WEIGHT.get(business.size_tier, 1.0)
    if business.category.value in CATEGORY_SELECTION_BOOST:
        w *= 1.5
    return w


def select_labeled_businesses(
    businesses: list[Business],
    fraction: float = 0.08,
    seed: int = 42,
) -> LabelingResult:
    """
    Select ~8% of businesses as having known revenue (public filings analog).

    Biased toward large firms and certain categories — bias is explicit
    and corrected via inverse-propensity reweighting during training.
    """
    if not businesses:
        return LabelingResult(set(), {}, {})

    rng = Random(seed)
    probs = {b.id: _selection_probability(b) for b in businesses}
    total_w = sum(probs.values())
    norm_probs = {bid: w / total_w for bid, w in probs.items()}

    n_select = max(1, int(len(businesses) * fraction))
    ids = [b.id for b in businesses]
    weights = [norm_probs[bid] for bid in ids]

    # Weighted sample without replacement
    selected: set[UUID] = set()
    pool_ids = list(ids)
    pool_weights = list(weights)
    for _ in range(min(n_select, len(pool_ids))):
        total = sum(pool_weights)
        r = rng.random() * total
        cumulative = 0.0
        for i, w in enumerate(pool_weights):
            cumulative += w
            if r <= cumulative:
                selected.add(pool_ids[i])
                del pool_ids[i]
                del pool_weights[i]
                break

    # Inverse propensity weights: correct for size/category selection bias
    sample_weights: dict[UUID, float] = {}
    for b in businesses:
        p = norm_probs[b.id]
        sample_weights[b.id] = (1.0 / p) if b.id in selected else 0.0

    # Normalize selected weights to mean 1.0
    selected_w = [sample_weights[bid] for bid in selected]
    if selected_w:
        mean_w = sum(selected_w) / len(selected_w)
        for bid in selected:
            sample_weights[bid] /= mean_w

    return LabelingResult(
        labeled_business_ids=selected,
        selection_probability=norm_probs,
        sample_weights=sample_weights,
    )
