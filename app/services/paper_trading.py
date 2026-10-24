"""Paper Trading Service Façade for AlgoTrade AI."""

from typing import Any
from app.models import Position
from app.paper import (
    PaperBroker,
    PaperOrder,
    paper_broker,
)


class PaperTradingService:
    """Service facade for durable paper trading engine."""

    def __init__(self, engine: PaperBroker | None = None) -> None:
        self.engine = engine or paper_broker

    def create_order(
        self,
        symbol: str,
        side: str,
        quantity: int,
        price: float = 0.0,
        order_type: str = "MARKET",
        stop_loss: float | None = None,
        take_profit: float | None = None,
        segment: str = "EQUITY_CASH",
        strategy_id: str = "manual",
    ) -> PaperOrder:
        return self.engine.place_order(
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=price,
            order_type=order_type,
            stop_loss=stop_loss,
            take_profit=take_profit,
            segment=segment,
            strategy_id=strategy_id,
        )

    def cancel_order(self, order_id: str) -> bool:
        return self.engine.cancel_order(order_id)

    def get_portfolio_summary(self) -> dict[str, Any]:
        return self.engine.get_portfolio_summary()

    def get_positions(self) -> list[Position]:
        return list(self.engine.positions.values())

    def get_orders(self) -> list[PaperOrder]:
        return list(self.engine.orders.values())


paper_service = PaperTradingService()
