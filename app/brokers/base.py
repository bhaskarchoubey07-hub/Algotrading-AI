"""Unified Broker Interface and Domain Models for AlgoTrade AI.

Provides an abstract broker boundary ensuring that strategies, risk checks,
and execution routing are fully decoupled from specific broker implementations.
"""

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
import pandas as pd


class BrokerMode(str, Enum):
    BACKTEST = "BACKTEST"
    PAPER = "PAPER"
    LIVE_GATED = "LIVE_GATED"


class OrderStatus(str, Enum):
    CREATED = "CREATED"
    VALIDATED = "VALIDATED"
    SUBMITTED = "SUBMITTED"
    PENDING = "PENDING"
    TRANSIT_SANDBOX = "TRANSIT_SANDBOX"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class TransactionType(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP_LOSS = "STOP_LOSS"
    STOP_LOSS_MARKET = "STOP_LOSS_MARKET"


class ProductType(str, Enum):
    CNC = "CNC"
    INTRADAY = "INTRADAY"
    MARGIN = "MARGIN"
    MTF = "MTF"
    CO = "CO"
    BO = "BO"


class ExchangeSegment(str, Enum):
    NSE_EQ = "NSE_EQ"
    BSE_EQ = "BSE_EQ"
    NSE_FNO = "NSE_FNO"
    BSE_FNO = "BSE_FNO"
    MCX_COMM = "MCX_COMM"
    IDX_I = "IDX_I"


@dataclass
class BrokerFundLimit:
    available_cash: float
    collateral_amount: float
    margin_utilized: float
    net_equity: float
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class BrokerPosition:
    symbol: str
    exchange_segment: str
    position_type: str  # "LONG" or "SHORT"
    net_quantity: int
    buy_average: float
    cost_price: float
    current_price: float = 0.0
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    cross_currency: str = "INR"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class BrokerHolding:
    symbol: str
    isin: str
    total_quantity: int
    dp_quantity: int
    average_cost_price: float
    current_market_price: float = 0.0
    pnl: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class BrokerQuote:
    symbol: str
    security_id: str
    exchange_segment: str
    last_price: float
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    volume: int
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    is_stale: bool = False
    depth: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class OrderPlacementRequest:
    symbol: str
    security_id: str
    transaction_type: TransactionType
    order_type: OrderType
    quantity: int
    price: float = 0.0
    trigger_price: float = 0.0
    product_type: ProductType = ProductType.CNC
    exchange_segment: ExchangeSegment = ExchangeSegment.NSE_EQ
    validity: str = "DAY"
    disclosed_quantity: int = 0
    tag: str | None = None
    correlation_id: str | None = None
    strategy_id: str = "manual"

    def to_dict(self) -> dict[str, Any]:
        res = asdict(self)
        res["transaction_type"] = self.transaction_type.value
        res["order_type"] = self.order_type.value
        res["product_type"] = self.product_type.value
        res["exchange_segment"] = self.exchange_segment.value
        return res


@dataclass
class OrderModificationRequest:
    order_id: str
    order_type: OrderType
    quantity: int
    price: float = 0.0
    trigger_price: float = 0.0
    leg_name: str = "ENTRY_LEG"
    validity: str = "DAY"


@dataclass
class BrokerOrder:
    order_id: str
    correlation_id: str
    symbol: str
    security_id: str
    exchange_segment: str
    transaction_type: str
    order_type: str
    product_type: str
    quantity: int
    price: float
    trigger_price: float
    order_status: OrderStatus
    exchange_order_id: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    filled_quantity: int = 0
    filled_price: float = 0.0
    filled_at: str | None = None
    fees: float = 0.0
    message: str = ""
    is_live: bool = False

    def to_dict(self) -> dict[str, Any]:
        res = asdict(self)
        res["order_status"] = self.order_status.value if isinstance(self.order_status, OrderStatus) else str(self.order_status)
        return res


class BaseBroker(ABC):
    """Abstract interface for all broker adapters in AlgoTrade AI."""

    @abstractmethod
    def connect(self) -> bool:
        """Connect to broker and validate credentials."""
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Disconnect and clean up resources."""
        pass

    @abstractmethod
    def get_account_status(self) -> dict[str, Any]:
        """Return connectivity, mode, and account readiness."""
        pass

    @abstractmethod
    def get_fund_limits(self) -> BrokerFundLimit:
        """Fetch normalized fund limits and margins."""
        pass

    @abstractmethod
    def get_positions(self) -> list[BrokerPosition]:
        """Fetch open positions."""
        pass

    @abstractmethod
    def get_holdings(self) -> list[BrokerHolding]:
        """Fetch long-term portfolio demat holdings."""
        pass

    @abstractmethod
    def get_quote(self, symbol_or_security_id: str, exchange_segment: str = "NSE_EQ") -> BrokerQuote:
        """Fetch real-time normalized quote."""
        pass

    @abstractmethod
    def get_historical_data(
        self,
        security_id: str,
        exchange_segment: str,
        instrument_type: str,
        from_date: str,
        to_date: str,
        interval: str = "1",
    ) -> pd.DataFrame:
        """Fetch historical OHLCV data."""
        pass

    @abstractmethod
    def get_orders(self) -> list[BrokerOrder]:
        """Fetch current order book."""
        pass

    @abstractmethod
    def get_order_by_id(self, order_id: str) -> BrokerOrder | None:
        """Fetch specific order details."""
        pass

    @abstractmethod
    def place_order(self, request: OrderPlacementRequest) -> BrokerOrder:
        """Place an order through the broker adapter."""
        pass

    @abstractmethod
    def modify_order(self, order_id: str, request: OrderModificationRequest) -> BrokerOrder:
        """Modify an existing open order."""
        pass

    @abstractmethod
    def cancel_order(self, order_id: str) -> dict[str, Any]:
        """Cancel an open order."""
        pass

    @abstractmethod
    def reconcile_orders(self) -> dict[str, Any]:
        """Reconcile local order states against broker order book."""
        pass
