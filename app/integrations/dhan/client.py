from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import logging
from typing import Any
import requests
from app.config import settings

logger = logging.getLogger("algotrade.dhan")


@dataclass
class DhanFundLimit:
    available_cash: float
    collateral_amount: float
    margin_utilized: float
    net_equity: float


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


class DhanHQBrokerAdapter:
    """Official DhanHQ v2 API adapter with mock sandbox mode and live execution safety gate."""

    BASE_URL = "https://api.dhan.co/v2"

    def __init__(
        self,
        client_id: str | None = None,
        access_token: str | None = None,
        env: str = "sandbox",
    ) -> None:
        self.client_id = client_id or settings.dhan_client_id
        self.access_token = access_token or settings.dhan_access_token
        self.env = env or settings.dhan_env
        self.is_connected = bool(self.client_id and self.access_token)
        self.mock_orders: dict[str, DhanOrderResponse] = {}

    def get_headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "client-id": self.client_id or "MOCK_CLIENT_ID",
            "access-token": self.access_token or "MOCK_ACCESS_TOKEN",
        }

    def get_fund_limits(self) -> DhanFundLimit:
        """Fetch cash margin and funds from DhanHQ."""
        if not self.is_connected:
            # Return realistic simulated funds in sandbox
            return DhanFundLimit(
                available_cash=850_000.0,
                collateral_amount=150_000.0,
                margin_utilized=75_000.0,
                net_equity=925_000.0,
            )

        try:
            resp = requests.get(f"{self.BASE_URL}/fundlimit", headers=self.get_headers(), timeout=5.0)
            if resp.status_code == 200:
                data = resp.json()
                return DhanFundLimit(
                    available_cash=float(data.get("availabelBalance", 0)),
                    collateral_amount=float(data.get("collateralAmount", 0)),
                    margin_utilized=float(data.get("utilisedAmount", 0)),
                    net_equity=float(data.get("netEquity", 0)),
                )
        except Exception as exc:
            logger.error(f"DhanHQ get_fund_limits failed: {exc}")

        return DhanFundLimit(0.0, 0.0, 0.0, 0.0)

    def get_positions(self) -> list[dict[str, Any]]:
        """Fetch open trading positions from DhanHQ."""
        if not self.is_connected:
            return [
                {
                    "tradingSymbol": "RELIANCE",
                    "exchangeSegment": "NSE_EQ",
                    "positionType": "LONG",
                    "netQty": 25,
                    "buyAvg": 2840.50,
                    "costPrice": 2840.50,
                    "realizedProfit": 0.0,
                    "unrealizedProfit": 350.0,
                    "crossCurrency": "INR",
                }
            ]

        try:
            resp = requests.get(f"{self.BASE_URL}/positions", headers=self.get_headers(), timeout=5.0)
            if resp.status_code == 200:
                return resp.json()
        except Exception as exc:
            logger.error(f"DhanHQ get_positions failed: {exc}")

        return []

    def get_holdings(self) -> list[dict[str, Any]]:
        """Fetch demat holdings from DhanHQ."""
        if not self.is_connected:
            return [
                {
                    "tradingSymbol": "INFY",
                    "isin": "INE009A01021",
                    "totalQty": 50,
                    "dpQty": 50,
                    "avgCostPrice": 1720.00,
                }
            ]

        try:
            resp = requests.get(f"{self.BASE_URL}/holdings", headers=self.get_headers(), timeout=5.0)
            if resp.status_code == 200:
                return resp.json()
        except Exception as exc:
            logger.error(f"DhanHQ get_holdings failed: {exc}")

        return []

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

        now_ts = datetime.now(timezone.utc).isoformat()
        order_id = f"DHAN_{int(datetime.now().timestamp() * 1000)}"

        # SAFETY BOUNDARY: Real live order placement is strictly absent from this platform.
        # This adapter operates exclusively in sandbox / mock simulation mode.
        order = DhanOrderResponse(
            order_id=order_id,
            order_status="TRANSIT_SANDBOX",
            symbol=symbol,
            transaction_type=trans_type,
            quantity=quantity,
            price=price,
            trigger_price=trigger_price,
            exchange_order_id=f"EXCH_MOCK_{order_id}",
            create_time=now_ts,
            is_live=False,
            message="Simulated by DhanHQ mock/sandbox adapter; live execution gate is closed.",
        )

        self.mock_orders[order_id] = order
        return order


    def cancel_order(self, order_id: str) -> dict[str, Any]:
        """Cancel an open order in mock sandbox mode (live execution strictly absent)."""
        if order_id in self.mock_orders:
            self.mock_orders[order_id].order_status = "CANCELLED"
        return {
            "orderId": order_id,
            "orderStatus": "CANCELLED",
            "message": "Order cancelled in mock sandbox. Real broker execution is disabled.",
        }


    def get_connection_status(self) -> dict[str, Any]:
        return {
            "is_connected": self.is_connected,
            "environment": self.env,
            "client_id_configured": bool(self.client_id),
            "access_token_configured": bool(self.access_token),
            "live_gate_closed": True,
            "live_execution_supported": False,
            "orders_processed": len(self.mock_orders),

        }


dhan_broker = DhanHQBrokerAdapter()
