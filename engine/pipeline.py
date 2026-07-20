"""Training and inference orchestration for the revenue estimator."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import numpy as np
import pandas as pd

from core.models import Business, RevenueEstimate
from db.repository import RevWatchRepository
from engine.estimator import EstimatorConfig, RevenueEstimator
from engine.features import FeatureBuilder
from engine.labeling import LabelingResult, select_labeled_businesses


@dataclass
class EstimationPipelineResult:
    estimates: list[RevenueEstimate]
    labeling: LabelingResult
    n_train_rows: int
    n_predict_rows: int


def load_signals_dataframe(repo: RevWatchRepository) -> pd.DataFrame:
    rows = repo.conn.execute(
        """
        SELECT business_id, signal_type, value, timestamp, source, reliability
        FROM signal_observations
        """
    ).fetchall()
    return pd.DataFrame(
        rows,
        columns=["business_id", "signal_type", "value", "timestamp", "source", "reliability"],
    )


def load_businesses(repo: RevWatchRepository) -> list[Business]:
    """Load all businesses (paginated)."""
    all_biz: list[Business] = []
    offset = 0
    batch = 1000
    while True:
        chunk = repo.list_businesses(limit=batch, offset=offset)
        if not chunk:
            break
        all_biz.extend(chunk)
        offset += batch
    return all_biz


def load_training_labels(
    repo: RevWatchRepository,
    labeled_business_ids: set[UUID],
) -> pd.DataFrame:
    """
    Load true revenue for labeled businesses only.

    This is the ONE place training pipeline touches ground truth.
    The RevenueEstimator class itself never reads true_revenue.
    """
    if not labeled_business_ids:
        return pd.DataFrame(columns=["business_id", "period", "revenue"])

    ids = [str(bid) for bid in labeled_business_ids]
    placeholders = ",".join("?" * len(ids))
    rows = repo.conn.execute(
        f"""
        SELECT business_id, period, revenue
        FROM true_revenue
        WHERE business_id IN ({placeholders})
        """,
        ids,
    ).fetchall()
    return pd.DataFrame(rows, columns=["business_id", "period", "revenue"])


def run_estimation_pipeline(
    repo: RevWatchRepository,
    config: EstimatorConfig | None = None,
) -> EstimationPipelineResult:
    """End-to-end: features → labeled training → predict all business-months."""
    cfg = config or EstimatorConfig()
    businesses = load_businesses(repo)
    signals_df = load_signals_dataframe(repo)

    builder = FeatureBuilder()
    result = builder.build(signals_df, businesses)
    features = result.features

    if features.empty:
        raise ValueError("No features built — run Phase 3 data generation first")

    labeling = select_labeled_businesses(
        businesses, fraction=cfg.labeled_fraction, seed=cfg.seed
    )

    labels_df = load_training_labels(repo, labeling.labeled_business_ids)
    train = features[features["business_id"].isin(
        {str(bid) for bid in labeling.labeled_business_ids}
    )].copy()
    train = train.merge(labels_df, on=["business_id", "period"], how="inner")

    if train.empty:
        raise ValueError("No training rows after merging labels")

    train["log_revenue"] = np.log1p(train["revenue"])
    train["sample_weight"] = train["business_id"].map(
        lambda bid: labeling.sample_weights.get(UUID(bid), 1.0)
    )

    estimator = RevenueEstimator(cfg)
    estimator.fit(
        train.drop(columns=["revenue", "log_revenue", "sample_weight"]),
        train["log_revenue"],
        sample_weight=train["sample_weight"],
    )

    estimates = estimator.predict(features)
    repo.upsert_revenue_estimates(estimates)

    return EstimationPipelineResult(
        estimates=estimates,
        labeling=labeling,
        n_train_rows=len(train),
        n_predict_rows=len(estimates),
    )
