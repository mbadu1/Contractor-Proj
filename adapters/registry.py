"""Signal adapter registry and factory."""

from __future__ import annotations

from adapters.base import AdapterConfig, BusinessCatalog, SignalAdapter
from adapters.intensity import LatentActivityProvider, SignalIntensityProvider
from adapters.synthetic import (
    DigitalPaymentAdapter,
    HiringSignalAdapter,
    ReviewVelocityAdapter,
    SupplierFlowAdapter,
    UtilityProxyAdapter,
    WebFootprintAdapter,
)


def create_default_adapters(
    catalog: BusinessCatalog,
    intensity: SignalIntensityProvider | None = None,
    config: AdapterConfig | None = None,
    seed: int = 42,
) -> list[SignalAdapter]:
    """
    Build all six synthetic adapters with shared catalog and intensity provider.

    Swap intensity provider in Phase 3 for revenue-driven signals without
    changing adapter or estimation code.
    """
    cfg = config or AdapterConfig(seed=seed)
    provider = intensity or LatentActivityProvider(seed=seed)
    kwargs = {"catalog": catalog, "intensity": provider, "config": cfg}

    return [
        DigitalPaymentAdapter(**kwargs),
        ReviewVelocityAdapter(**kwargs),
        WebFootprintAdapter(**kwargs),
        HiringSignalAdapter(**kwargs),
        SupplierFlowAdapter(**kwargs),
        UtilityProxyAdapter(**kwargs),
    ]


ADAPTER_TYPES: dict[str, type[SignalAdapter]] = {
    "digital_payments": DigitalPaymentAdapter,
    "review_velocity": ReviewVelocityAdapter,
    "web_footprint": WebFootprintAdapter,
    "hiring_signals": HiringSignalAdapter,
    "supplier_flow": SupplierFlowAdapter,
    "utility_proxy": UtilityProxyAdapter,
}
