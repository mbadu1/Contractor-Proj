"""Synthetic signal adapters."""

from adapters.synthetic.hiring import HiringSignalAdapter
from adapters.synthetic.payments import DigitalPaymentAdapter
from adapters.synthetic.reviews import ReviewVelocityAdapter
from adapters.synthetic.supplier import SupplierFlowAdapter
from adapters.synthetic.utility import UtilityProxyAdapter
from adapters.synthetic.web import WebFootprintAdapter

__all__ = [
    "DigitalPaymentAdapter",
    "HiringSignalAdapter",
    "ReviewVelocityAdapter",
    "SupplierFlowAdapter",
    "UtilityProxyAdapter",
    "WebFootprintAdapter",
]
