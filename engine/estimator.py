"""Revenue estimation engine — LightGBM quantile ensemble with hierarchical shrinkage."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import UUID

import lightgbm as lgb
import numpy as np
import pandas as pd

from core.models import RevenueEstimate, SignalType
from engine.confidence import (
    compute_confidence_score,
    interval_width_ratio,
    signal_agreement,
)
from engine.features import FeatureBuilder, SIGNAL_TYPES

QUANTILES = (0.1, 0.5, 0.9)

# Map signal feature columns to contribution groups
SIGNAL_FEATURE_GROUPS: dict[str, str] = {
    st.value: st.value for st in SignalType
}


@dataclass
class EstimatorConfig:
    model_version: str = "v0.1.0"
    labeled_fraction: float = 0.08
    shrinkage_strength: float = 0.35
    seed: int = 42
    n_estimators: int = 200
    learning_rate: float = 0.05
    max_depth: int = 6
    num_leaves: int = 31


@dataclass
class TrainingResult:
    n_labeled_rows: int
    n_predicted_rows: int
    segment_priors: dict[str, float]


class RevenueEstimator:
    """
    Estimates business revenue from signal features only.

    Fully decoupled from signal adapters — consumes pre-built feature matrices.
    Training labels are injected externally (public filings analog).
    """

    def __init__(self, config: EstimatorConfig | None = None) -> None:
        self.config = config or EstimatorConfig()
        self.feature_builder = FeatureBuilder()
        self.models: dict[float, lgb.LGBMRegressor] = {}
        self.feature_columns: list[str] = []
        self.segment_priors: dict[str, float] = {}
        self.global_prior: float = 0.0
        self._is_fitted = False

    @staticmethod
    def _segment_key(row: pd.Series) -> str:
        return f"{row['category']}|{row['country']}|{row['size_tier']}"

    def _make_model(self, alpha: float) -> lgb.LGBMRegressor:
        return lgb.LGBMRegressor(
            objective="quantile",
            alpha=alpha,
            n_estimators=self.config.n_estimators,
            learning_rate=self.config.learning_rate,
            max_depth=self.config.max_depth,
            num_leaves=self.config.num_leaves,
            random_state=self.config.seed,
            verbose=-1,
            n_jobs=-1,
        )

    def _compute_priors(self, train_df: pd.DataFrame, log_labels: np.ndarray) -> None:
        """Hierarchical priors: category × country × size tier."""
        tmp = train_df.copy()
        tmp["log_revenue"] = log_labels
        tmp["segment"] = tmp.apply(self._segment_key, axis=1)

        self.global_prior = float(tmp["log_revenue"].median())
        self.segment_priors = (
            tmp.groupby("segment")["log_revenue"].median().to_dict()
        )

    def _prior_log_revenue(self, row: pd.Series) -> float:
        key = self._segment_key(row)
        return self.segment_priors.get(key, self.global_prior)

    def _shrinkage_weight(self, coverage: float) -> float:
        """More shrinkage when signal coverage is sparse."""
        base = self.config.shrinkage_strength
        return base * max(0.0, 1.0 - coverage)

    def _apply_shrinkage(
        self,
        raw_log_preds: dict[float, np.ndarray],
        rows: pd.DataFrame,
    ) -> dict[float, np.ndarray]:
        n = len(rows)
        shrunk: dict[float, np.ndarray] = {}
        for q, preds in raw_log_preds.items():
            out = np.zeros(n)
            for i in range(n):
                prior = self._prior_log_revenue(rows.iloc[i])
                w = self._shrinkage_weight(float(rows.iloc[i].get("signal_coverage", 0)))
                out[i] = (1 - w) * preds[i] + w * prior
            shrunk[q] = out
        return shrunk

    def _per_signal_sub_estimates(self, row: pd.Series) -> list[float]:
        """Rough per-signal revenue proxies for agreement scoring."""
        estimates: list[float] = []
        payment = row.get(SignalType.PAYMENT_VOLUME.value)
        if payment and not np.isnan(payment) and payment > 0:
            estimates.append(float(payment) / 0.85)
        supplier = row.get(SignalType.SUPPLIER_SHIPMENT_VOLUME.value)
        if supplier and not np.isnan(supplier) and supplier > 0:
            estimates.append(float(supplier) / 0.4)
        reviews = row.get(SignalType.REVIEW_VELOCITY.value)
        if reviews and not np.isnan(reviews) and reviews > 0:
            estimates.append(float(reviews) * 5000)
        return estimates

    def _extract_contributions(
        self,
        X: pd.DataFrame,
        row_idx: int,
        feature_columns: list[str],
    ) -> dict[str, float]:
        """Gain-based contributions from median model SHAP values."""
        if 0.5 not in self.models:
            return {}

        contribs = self.models[0.5].predict(
            X.iloc[row_idx : row_idx + 1], pred_contrib=True
        )[0]
        # Last element is bias
        abs_contribs = np.abs(contribs[:-1])

        grouped: dict[str, float] = {}
        for col, val in zip(feature_columns, abs_contribs):
            group = col
            for sig in SIGNAL_TYPES:
                if col == sig or col.startswith(f"mom_{sig}") or col.startswith(f"bench_{sig}"):
                    group = sig
                    break
            if col in ("signal_coverage", "signals_present", "avg_reliability"):
                group = "signal_quality"
            elif col.startswith("cat_"):
                group = "category_prior"
            elif col in ("size_tier_ord", "channel_count", "city_business_density"):
                group = "business_profile"

            grouped[group] = grouped.get(group, 0.0) + float(val)

        total = sum(grouped.values()) or 1.0
        return {k: round(v / total, 3) for k, v in grouped.items()}

    def fit(
        self,
        features: pd.DataFrame,
        labels: pd.Series,
        sample_weight: pd.Series | None = None,
    ) -> TrainingResult:
        """
        Train quantile regressors on labeled business-months.

        labels: log-scale revenue (log1p) indexed aligned with features rows.
        """
        self.feature_columns = [
            c
            for c in features.columns
            if c
            not in {
                "business_id",
                "period",
                "category",
                "country",
                "city",
                "size_tier",
            }
            and not c.startswith("rel_")
        ]

        X = FeatureBuilder.to_matrix(features, self.feature_columns)
        y = labels.values.astype(float)
        weights = sample_weight.values.astype(float) if sample_weight is not None else None

        self._compute_priors(features, y)

        for q in QUANTILES:
            model = self._make_model(q)
            model.fit(X, y, sample_weight=weights)
            self.models[q] = model

        self._is_fitted = True
        return TrainingResult(
            n_labeled_rows=len(features),
            n_predicted_rows=0,
            segment_priors=self.segment_priors,
        )

    def predict(self, features: pd.DataFrame) -> list[RevenueEstimate]:
        """Generate revenue estimates with uncertainty and explainability."""
        if not self._is_fitted:
            raise RuntimeError("Estimator must be fitted before predict()")

        X = FeatureBuilder.to_matrix(features, self.feature_columns)
        raw_log: dict[float, np.ndarray] = {}
        for q, model in self.models.items():
            raw_log[q] = model.predict(X)

        shrunk = self._apply_shrinkage(raw_log, features)
        estimates: list[RevenueEstimate] = []

        for i in range(len(features)):
            row = features.iloc[i]
            log_p10 = shrunk[0.1][i]
            log_p50 = shrunk[0.5][i]
            log_p90 = shrunk[0.9][i]

            p50 = max(0.0, float(np.expm1(log_p50)))
            p10 = max(0.0, float(np.expm1(log_p10)))
            p90 = max(0.0, float(np.expm1(log_p90)))
            p10 = min(p10, p50)
            p90 = max(p90, p50)

            sub_ests = self._per_signal_sub_estimates(row)
            agreement = signal_agreement(sub_ests)
            width_ratio = interval_width_ratio(p10, p90, p50)
            coverage = float(row.get("signal_coverage", 0))
            reliability = float(row.get("avg_reliability", 0.5))

            confidence = compute_confidence_score(
                signal_coverage=coverage,
                signal_agreement=agreement,
                interval_width_ratio=width_ratio,
                avg_reliability=reliability,
            )

            contributions = self._extract_contributions(X, i, self.feature_columns)

            estimates.append(
                RevenueEstimate(
                    business_id=UUID(str(row["business_id"])),
                    period=str(row["period"]),
                    point_estimate=round(p50, 2),
                    ci_low=round(p10, 2),
                    ci_high=round(p90, 2),
                    confidence_score=confidence,
                    signal_contributions=contributions,
                    model_version=self.config.model_version,
                )
            )

        return estimates

    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)
        meta = {
            "config": self.config.__dict__,
            "feature_columns": self.feature_columns,
            "segment_priors": self.segment_priors,
            "global_prior": self.global_prior,
        }
        (path / "meta.json").write_text(json.dumps(meta, indent=2))
        for q, model in self.models.items():
            model.booster_.save_model(str(path / f"model_q{int(q*100)}.txt"))

    def load(self, path: str | Path) -> None:
        path = Path(path)
        meta = json.loads((path / "meta.json").read_text())
        self.config = EstimatorConfig(**meta["config"])
        self.feature_columns = meta["feature_columns"]
        self.segment_priors = meta["segment_priors"]
        self.global_prior = meta["global_prior"]
        self.models = {}
        for q in QUANTILES:
            model = self._make_model(q)
            model._Booster = lgb.Booster(model_file=str(path / f"model_q{int(q*100)}.txt"))
            self.models[q] = model
        self._is_fitted = True
