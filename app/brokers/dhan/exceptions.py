"""DhanHQ Domain Exceptions for AlgoTrade AI."""


class DhanBrokerError(Exception):
    """Base exception for all DhanHQ integration errors."""

    def __init__(self, message: str, error_code: str | None = None, raw_response: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.raw_response = raw_response or {}


class DhanAuthenticationError(DhanBrokerError):
    """Raised when authentication fails, access token expires, or credentials are invalid."""
    pass


class DhanRateLimitError(DhanBrokerError):
    """Raised when API rate limits are exceeded."""
    pass


class DhanNetworkError(DhanBrokerError):
    """Raised on connection timeout, network failure, or broker endpoint unreachable."""
    pass


class DhanOrderRejectedError(DhanBrokerError):
    """Raised when an order placement or modification is rejected by Dhan or exchange."""
    pass


class DhanStaleDataError(DhanBrokerError):
    """Raised when market data feed exceeds maximum allowable staleness threshold."""
    pass


class DhanSecurityNotFoundError(DhanBrokerError):
    """Raised when a symbol or security ID cannot be mapped in the instrument master."""
    pass


class DhanLiveGateClosedError(DhanBrokerError):
    """Raised when an attempt is made to execute live orders while the platform live safety gate is closed."""
    pass
