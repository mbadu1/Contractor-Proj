"""Supplier / shipment flow proxies."""

from __future__ import annotations

from datetime import datetime

from adapters.config import SUPPLIER_HEAVY_CATEGORIES
from adapters.synthetic.base import SyntheticSignalAdapter
from core.models import Business, SignalType


class SupplierFlowAdapter(SyntheticSignalAdapter):
    """Inferred procurement volume from shipment/manifest-style records."""

    adapter_key = "supplier_flow"

    def _signal_types(self) -> list[SignalType]:
        return [SignalType.SUPPLIER_SHIPMENT_VOLUME]

    def _compute_value(
        self,
        signal_type: SignalType,
        business: Business,
        period: datetime,
        activity: float,
    ) -> float | None:
        if signal_type != SignalType.SUPPLIER_SHIPMENT_VOLUME:
            return None

        if business.category not in SUPPLIER_HEAVY_CATEGORIES:
            # Light retail still has some supplier signal but weaker
            weight = 0.25
        else:
            weight = 1.0

        volume = activity * 0.4 * weight
        if volume < 500:
            return None
        return volume
