"""Feature engineering for revenue estimation."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import numpy as np
import pandas as pd

from core.models import Business, SignalType, SizeTier

SIGNAL_TYPES: tuple[str, ...] = tuple(st.value for st in SignalType)

SIZE_TIER_ORD: dict[str, int] = {
    SizeTier.MICRO.value: 1,
    SizeTier.SMALL.value: 2,
    SizeTier.MEDIUM.value: 3,
    SizeTier.LARGE.value: 4,
    SizeTier.ENTERPRISE.value: 5,
}

GROWTH_SIGNALS: tuple[str, ...] = (
    SignalType.PAYMENT_VOLUME.value,
    SignalType.PAYMENT_TRANSACTION_COUNT.value,
    SignalType.REVIEW_VELOCITY.value,
    SignalType.SUPPLIER_SHIPMENT_VOLUME.value,
)


@dataclass
class FeatureBuildResult:
    features: pd.DataFrame
    feature_columns: list[str]


class FeatureBuilder:
    """Aggregate signals per business-month and engineer model features."""

    def __init__(self, total_signal_types: int = len(SIGNAL_TYPES)) -> None:
        self.total_signal_types = total_signal_types

    @staticmethod
    def _period_from_timestamp(ts: pd.Series) -> pd.Series:
        return pd.to_datetime(ts, utc=True).dt.strftime("%Y-%m")

    def build_signal_frame(self, signals: pd.DataFrame) -> pd.DataFrame:
        """Pivot raw signal observations to business-month rows."""
        if signals.empty:
            return pd.DataFrame(
                columns=["business_id", "period", *SIGNAL_TYPES, *{f"rel_{s}" for s in SIGNAL_TYPES}]
            )

        df = signals.copy()
        df["period"] = self._period_from_timestamp(df["timestamp"])
        df["business_id"] = df["business_id"].astype(str)

        agg = df.groupby(
            ["business_id", "period", "signal_type"], as_index=False
        ).agg(value=("value", "mean"), reliability=("reliability", "mean"))

        values = agg.pivot_table(
            index=["business_id", "period"],
            columns="signal_type",
            values="value",
            aggfunc="first",
        )
        reliabilities = agg.pivot_table(
            index=["business_id", "period"],
            columns="signal_type",
            values="reliability",
            aggfunc="first",
        )

        values = values.reindex(columns=SIGNAL_TYPES)
        reliabilities = reliabilities.reindex(columns=SIGNAL_TYPES)
        reliabilities = reliabilities.add_prefix("rel_")
        values.columns = list(SIGNAL_TYPES)

        out = values.join(reliabilities, how="outer").reset_index()
        return out

    def enrich(
        self,
        signal_frame: pd.DataFrame,
        businesses: list[Business],
    ) -> FeatureBuildResult:
        """Add coverage, growth, benchmark, and business attribute features."""
        if signal_frame.empty:
            return FeatureBuildResult(features=pd.DataFrame(), feature_columns=[])

        biz_df = pd.DataFrame(
            [
                {
                    "business_id": str(b.id),
                    "category": b.category.value,
                    "country": b.country,
                    "city": b.city,
                    "size_tier": b.size_tier.value,
                    "size_tier_ord": SIZE_TIER_ORD[b.size_tier.value],
                    "channel_count": len(b.channels),
                }
                for b in businesses
            ]
        )

        df = signal_frame.merge(biz_df, on="business_id", how="left")
        df = df.sort_values(["business_id", "period"]).reset_index(drop=True)

        # Signal coverage
        value_cols = list(SIGNAL_TYPES)
        present = df[value_cols].notna().sum(axis=1)
        df["signal_coverage"] = present / self.total_signal_types
        df["signals_present"] = present
        df["avg_reliability"] = df[[f"rel_{c}" for c in SIGNAL_TYPES]].mean(axis=1, skipna=True).fillna(0)

        # Month-over-month growth for key signals
        for sig in GROWTH_SIGNALS:
            if sig in df.columns:
                prev = df.groupby("business_id")[sig].shift(1)
                growth = (df[sig] - prev) / prev.replace(0, np.nan)
                df[f"mom_{sig}"] = growth.replace([np.inf, -np.inf], np.nan).fillna(0)

        # Category benchmark ratios (signal vs category-period median)
        for sig in (
            SignalType.PAYMENT_VOLUME.value,
            SignalType.REVIEW_VELOCITY.value,
            SignalType.SUPPLIER_SHIPMENT_VOLUME.value,
        ):
            if sig not in df.columns:
                continue
            bench = df.groupby(["category", "period"])[sig].transform("median")
            df[f"bench_{sig}"] = (df[sig] / bench.replace(0, np.nan)).replace(
                [np.inf, -np.inf], np.nan
            ).fillna(1.0)

        # City density proxy: businesses per city in sample
        city_map = biz_df.set_index("business_id")["city"].map(
            biz_df.groupby("city")["business_id"].count().to_dict()
        )
        df["city_business_density"] = df["business_id"].map(city_map).fillna(1)

        # Category dummies
        cat_dummies = pd.get_dummies(df["category"], prefix="cat")
        df = pd.concat([df, cat_dummies], axis=1)

        meta = {"business_id", "period", "category", "country", "city", "size_tier"}
        feature_columns = [
            c
            for c in df.columns
            if c not in meta and not c.startswith("rel_")
        ]

        return FeatureBuildResult(features=df, feature_columns=feature_columns)

    def build(
        self,
        signals: pd.DataFrame,
        businesses: list[Business],
    ) -> FeatureBuildResult:
        signal_frame = self.build_signal_frame(signals)
        return self.enrich(signal_frame, businesses)

    @staticmethod
    def to_matrix(df: pd.DataFrame, feature_columns: list[str]) -> pd.DataFrame:
        return df[feature_columns].fillna(0).astype(float)
