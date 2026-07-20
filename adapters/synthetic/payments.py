"""Digital payment proxy signals."""

from __future__ import annotations

from datetime import datetime

from adapters.config import country_factor, digital_penetration
from adapters.synthetic.base import SyntheticSignalAdapter
from core.models import Business, SalesChannel, SignalType


class DigitalPaymentAdapter(SyntheticSignalAdapter):
    """
    Transaction count and volume proxies with category-dependent digital penetration.

    Ecommerce ~95% visible digitally; informal retail ~20%.
    """

    adapter_key = "digital_payments"

    def _signal_types(self) -> list[SignalType]:
        return [SignalType.PAYMENT_TRANSACTION_COUNT, SignalType.PAYMENT_VOLUME]

    def _compute_value(
        self,
        signal_type: SignalType,
        business: Business,
        period: datetime,
        activity: float,
    ) -> float | None:
        penetration = digital_penetration(business.category, business.channels)
        cf = country_factor(business.country)
        effective = activity * penetration * cf

        if effective < 100:
            return None

        avg_ticket = 28.0
        if SalesChannel.ECOMMERCE in business.channels:
            avg_ticket = 45.0
        elif business.category.value in ("grocery_supermarket", "convenience_store"):
            avg_ticket = 18.0

        if signal_type == SignalType.PAYMENT_TRANSACTION_COUNT:
            return max(1.0, effective / avg_ticket)
        if signal_type == SignalType.PAYMENT_VOLUME:
            return effective * 0.85
        return None
