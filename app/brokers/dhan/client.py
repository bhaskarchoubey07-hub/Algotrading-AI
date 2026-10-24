"""DhanHQ Unified Broker Client and Legacy Adapter.

Integrates the official DhanHQ Python SDK (v2.3.0) with modular market data,
orders, portfolio, options, streaming, and safety gates.
"""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import logging
from typing import Any
import pandas as pd
from app.brokers.base import (
    BaseBroker,
    BrokerFundLimit,
    BrokerHolding,
    BrokerOrder,
    BrokerPosition,
    BrokerQuote,
    ExchangeSegment,
    OrderModificationRequest,
    OrderPlacementRequest,
    OrderStatus,
    OrderType,
    ProductType,
    TransactionType,
)
from app.brokers.dhan.auth import DhanAuthManager
from app.brokers.dhan.exceptions import DhanAuthenticationError, DhanBrokerError
from app.brokers.dhan.instruments import DhanInstrumentManager, instrument_manager
from app.brokers.dhan.market_data import DhanMarketDataManager
from app.brokers.dhan.normalizers import redact_sensitive_data
from app.brokers.dhan.orders import DhanOrderManager
from app.brokers.dhan.options import DhanOptionsManager
from app.brokers.dhan.portfolio import DhanPortfolioManager
from app.brokers.dhan.streaming import DhanStreamingManager
from app.config import settings

logger = logging.getLogger("algotrade.dhan.client")


# ============================================================================
# Legacy Dataclasses for 100% Backward Compatibility with Existing Code/Tests
# ============================================================================

@dataclass
class DhanFundLimit:
    available_cash: float
    collateral_amount: float
    margin_utilized: float
    net_equity: float

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class DhanOrderResponse:
    order_id: str
    order_status: str
    symbol: str
    transaction_type: str
    quantity: int
    price: float
    trigger_price: float
    exchange_order_id: str
    create_time: str
    is_live: bool = False
    message: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


# ============================================================================
# Main Unified DhanClient (Implements BaseBroker)
# ============================================================================

class DhanClient(BaseBroker):
    """Production-grade unified broker implementation using official DhanHQ SDK."""

    def __init__(
        self,
        client_id: str | None = None,
        access_token: str | None = None,
        env: str | None = None,
    ) -> None:
        self.auth = DhanAuthManager(client_id, access_token, env)
        self.instruments = instrument_manager
        self.dhan_context = None
        self.dhan_sdk = None
        self.is_connected = False

        # Initialize subsystem managers
        self.market_data = DhanMarketDataManager()
        self.orders = DhanOrderManager()
        self.portfolio = DhanPortfolioManager()
        self.options = DhanOptionsManager()
        self.streaming = DhanStreamingManager()

        # Connect if configured
        if self.auth.is_configured():
            self.connect()

    def connect(self) -> bool:
        """Initializes DhanContext and SDK instance if credentials are valid."""
        try:
            self.auth.validate_or_raise()
            from dhanhq import DhanContext, dhanhq

            self.dhan_context = DhanContext(self.auth.client_id, self.auth.access_token)
            self.dhan_sdk = dhanhq(self.dhan_context)

            # Wire SDK to managers
            self.market_data.set_client(self.dhan_sdk)
            self.orders.set_client(self.dhan_sdk)
            self.portfolio.set_client(self.dhan_sdk)
            self.options.set_client(self.dhan_sdk)
            self.streaming.set_context(self.dhan_context)

            self.is_connected = True
            logger.info("DhanHQ SDK initialized successfully.")
            return True
        except Exception as exc:
            logger.warning(f"DhanHQ connection in sandbox/mock fallback mode: {exc}")
            self.is_connected = False
            return False

    def disconnect(self) -> None:
        self.streaming.stop()
        self.is_connected = False

    def get_account_status(self) -> dict[str, Any]:
        cred_status = self.auth.get_credential_status()
        stream_status = self.streaming.get_status()
        return {
            "broker": "DhanHQ",
            "is_connected": self.is_connected,
            "environment": self.auth.environment,
            "credentials": cred_status.to_dict(),
            "streaming": stream_status,
            "live_gate_closed": True,
            "live_execution_supported": False,
            "orders_processed": len(self.orders.get_all_orders()),
        }

    def get_fund_limits(self) -> BrokerFundLimit:
        return self.portfolio.get_fund_limits()

    def get_positions(self) -> list[BrokerPosition]:
        return self.portfolio.get_positions()

    def get_holdings(self) -> list[BrokerHolding]:
        return self.portfolio.get_holdings()

    def get_quote(self, symbol_or_security_id: str, exchange_segment: str = "NSE_EQ") -> BrokerQuote:
        return self.market_data.get_quote(symbol_or_security_id, exchange_segment)

    def get_historical_data(
        self,
        security_id: str,
        exchange_segment: str,
        instrument_type: str,
        from_date: str,
        to_date: str,
        interval: str = "1",
    ) -> pd.DataFrame:
        if interval == "D":
            return self.market_data.get_historical_daily(security_id, from_date, to_date, exchange_segment, instrument_type)
        return self.market_data.get_intraday_minute(
            security_id, from_date, to_date, interval=int(interval), exchange_segment=exchange_segment, instrument_type=instrument_type
        )

    def get_orders(self) -> list[BrokerOrder]:
        return self.orders.get_all_orders()

    def get_order_by_id(self, order_id: str) -> BrokerOrder | None:
        return self.orders.get_order_by_id(order_id)

    def place_order(self, request: OrderPlacementRequest) -> BrokerOrder:
        return self.orders.place_order(request)

    def modify_order(self, order_id: str, request: OrderModificationRequest) -> BrokerOrder:
        return self.orders.modify_order(order_id, request)

    def cancel_order(self, order_id: str) -> dict[str, Any]:
        return self.orders.cancel_order(order_id)

    def reconcile_orders(self) -> dict[str, Any]:
        return self.orders.reconcile_orders()


# ============================================================================
# Backward-Compatible Adapter Layer (Matches original starter method signatures)
# ============================================================================

class DhanHQBrokerAdapter:
    """Official DhanHQ v2 API adapter with mock sandbox mode and live execution safety gate.

    100% backward compatible with existing AlgoTrade AI callers and tests.
    """

    BASE_URL = "https://api.dhan.co/v2"

    def __init__(
        self,
        client_id: str | None = None,
        access_token: str | None = None,
        env: str = "sandbox",
    ) -> None:
        self.client_id = client_id if client_id is not None else settings.dhan_client_id
        self.access_token = access_token if access_token is not None else settings.dhan_access_token
        self.env = env or settings.dhan_env
        self.client = DhanClient(client_id=self.client_id, access_token=self.access_token, env=self.env)
        self.is_connected = self.client.is_connected
        self.mock_orders: dict[str, DhanOrderResponse] = {}

    def get_headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "client-id": self.client_id or "MOCK_CLIENT_ID",
            "access-token": self.access_token or "MOCK_ACCESS_TOKEN",
        }

    def get_fund_limits(self) -> DhanFundLimit:
        limits = self.client.get_fund_limits()
        return DhanFundLimit(
            available_cash=limits.available_cash,
            collateral_amount=limits.collateral_amount,
            margin_utilized=limits.margin_utilized,
            net_equity=limits.net_equity,
        )

    def get_positions(self) -> list[dict[str, Any]]:
        positions = self.client.get_positions()
        return [
            {
                "tradingSymbol": p.symbol,
                "exchangeSegment": p.exchange_segment,
                "positionType": p.position_type,
                "netQty": p.net_quantity,
                "buyAvg": p.buy_average,
                "costPrice": p.cost_price,
                "realizedProfit": p.realized_pnl,
                "unrealizedProfit": p.unrealized_pnl,
                "crossCurrency": p.cross_currency,
            }
            for p in positions
        ]

    def get_holdings(self) -> list[dict[str, Any]]:
        holdings = self.client.get_holdings()
        return [
            {
                "tradingSymbol": h.symbol,
                "isin": h.isin,
                "totalQty": h.total_quantity,
                "dpQty": h.dp_quantity,
                "avgCostPrice": h.average_cost_price,
            }
            for h in holdings
        ]

    def place_order(
        self,
        security_id: str,
        symbol: str,
        transaction_type: str,  # BUY or SELL
        order_type: str,        # MARKET, LIMIT, STOP_LOSS, STOP_LOSS_MARKET
        quantity: int,
        price: float = 0.0,
        trigger_price: float = 0.0,
        exchange_segment: str = "NSE_EQ",
        product_type: str = "CNC",  # CNC, INTRADAY, MARGIN
    ) -> DhanOrderResponse:
        """Place order via DhanHQ, guarded by strict live execution safety gate."""
        trans_type = transaction_type.upper()
        if trans_type not in {"BUY", "SELL"}:
            raise ValueError("transaction_type must be BUY or SELL")
        if quantity <= 0:
            raise ValueError("quantity must be strictly positive")

        order_req = OrderPlacementRequest(
            symbol=symbol,
            security_id=security_id,
            transaction_type=TransactionType(trans_type),
            order_type=OrderType(order_type.upper()),
            quantity=quantity,
            price=price,
            trigger_price=trigger_price,
            exchange_segment=ExchangeSegment(exchange_segment),
            product_type=ProductType(product_type.upper()),
        )

        broker_order = self.client.place_order(order_req)
        resp = DhanOrderResponse(
            order_id=broker_order.order_id,
            order_status=broker_order.order_status.value,
            symbol=broker_order.symbol,
            transaction_type=broker_order.transaction_type,
            quantity=broker_order.quantity,
            price=broker_order.price,
            trigger_price=broker_order.trigger_price,
            exchange_order_id=broker_order.exchange_order_id,
            create_time=broker_order.created_at,
            is_live=broker_order.is_live,
            message=broker_order.message,
        )
        self.mock_orders[resp.order_id] = resp
        return resp

    def cancel_order(self, order_id: str) -> dict[str, Any]:
        if order_id in self.mock_orders:
            self.mock_orders[order_id].order_status = "CANCELLED"
        return self.client.cancel_order(order_id)

    def get_connection_status(self) -> dict[str, Any]:
        status = self.client.get_account_status()
        return {
            "is_connected": self.client.is_connected,
            "environment": self.env,
            "client_id_configured": bool(self.client_id),
            "access_token_configured": bool(self.access_token),
            "live_gate_closed": True,
            "live_execution_supported": False,
            "orders_processed": len(self.mock_orders) + status["orders_processed"],
        }


# Module Singleton
dhan_broker = DhanHQBrokerAdapter()
