"""DhanHQ Official Broker Module for AlgoTrade AI."""

from app.brokers.dhan.auth import DhanAuthManager, DhanCredentialStatus
from app.brokers.dhan.client import (
    DhanClient,
    DhanFundLimit,
    DhanHQBrokerAdapter,
    DhanOrderResponse,
    dhan_broker,
)
from app.brokers.dhan.exceptions import (
    DhanAuthenticationError,
    DhanBrokerError,
    DhanLiveGateClosedError,
    DhanNetworkError,
    DhanOrderRejectedError,
    DhanRateLimitError,
    DhanSecurityNotFoundError,
    DhanStaleDataError,
)
from app.brokers.dhan.instruments import DhanInstrumentManager, instrument_manager
from app.brokers.dhan.market_data import DhanMarketDataManager
from app.brokers.dhan.options import DhanOptionsManager, OptionChainResult, OptionStrikeData
from app.brokers.dhan.orders import DhanOrderManager
from app.brokers.dhan.portfolio import DhanPortfolioManager, MarginCalculationResult
from app.brokers.dhan.streaming import DhanStreamingManager, StreamingStatus

__all__ = [
    "DhanClient",
    "DhanHQBrokerAdapter",
    "dhan_broker",
    "DhanFundLimit",
    "DhanOrderResponse",
    "DhanAuthManager",
    "DhanCredentialStatus",
    "DhanInstrumentManager",
    "instrument_manager",
    "DhanMarketDataManager",
    "DhanOrderManager",
    "DhanPortfolioManager",
    "MarginCalculationResult",
    "DhanOptionsManager",
    "OptionChainResult",
    "OptionStrikeData",
    "DhanStreamingManager",
    "StreamingStatus",
    "DhanBrokerError",
    "DhanAuthenticationError",
    "DhanRateLimitError",
    "DhanNetworkError",
    "DhanOrderRejectedError",
    "DhanStaleDataError",
    "DhanSecurityNotFoundError",
    "DhanLiveGateClosedError",
]
