"""DhanHQ Integration Client - Backward Compatible Façade.

Exposes DhanHQBrokerAdapter, dhan_broker, DhanOrderResponse, and DhanFundLimit
from the unified app.brokers.dhan module.
"""

from app.brokers.dhan.client import (
    DhanClient,
    DhanFundLimit,
    DhanHQBrokerAdapter,
    DhanOrderResponse,
    dhan_broker,
)

__all__ = [
    "DhanClient",
    "DhanHQBrokerAdapter",
    "dhan_broker",
    "DhanFundLimit",
    "DhanOrderResponse",
]
