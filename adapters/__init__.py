"""Signal adapter package — pluggable proxy signal sources."""

from adapters.base import (
    AdapterConfig,
    BusinessCatalog,
    InMemoryBusinessCatalog,
    RegionFilter,
    SignalAdapter,
    fetch_all_adapters,
)
from adapters.registry import create_default_adapters

__all__ = [
    "AdapterConfig",
    "BusinessCatalog",
    "InMemoryBusinessCatalog",
    "RegionFilter",
    "SignalAdapter",
    "create_default_adapters",
    "fetch_all_adapters",
]
