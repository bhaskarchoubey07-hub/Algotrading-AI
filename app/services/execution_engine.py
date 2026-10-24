"""Unified Multi-Mode Execution Engine for AlgoTrade AI.

Routes orders across BACKTEST, PAPER, and LIVE_GATED execution modes with
mandatory pre-trade risk evaluation and strict live-trading safety gating.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
from typing import Any
from app.brokers.base import (
    BrokerMode,
    BrokerOrder,
    ExchangeSegment,
    OrderPlacementRequest,
    OrderStatus,
    OrderType,
    ProductType,
    TransactionType,
)
from app.brokers.dhan.client import DhanClient, dhan_broker
from app.config import settings
from app.services.paper_trading import PaperTradingService, paper_service
from app.services.risk_manager import RiskManager, risk_manager

logger = logging.getLogger("algotrade.services.execution")


@dataclass
class ExecutionResult:
    success: bool
    mode: BrokerMode
    order_id: str
    status: str
    message: str
    symbol: str
    side: str
    quantity: int
    price: float
    fees: float = 0.0
    filled_price: float = 0.0
    filled_quantity: int = 0
    risk_approved: bool = True
    rejection_reason: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "mode": self.mode.value,
            "order_id": self.order_id,
            "status": self.status,
            "message": self.message,
            "symbol": self.symbol,
            "side": self.side,
            "quantity": self.quantity,
            "price": self.price,
            "fees": self.fees,
            "filled_price": self.filled_price,
            "filled_quantity": self.filled_quantity,
            "risk_approved": self.risk_approved,
            "rejection_reason": self.rejection_reason,
            "timestamp": self.timestamp,
        }


class UnifiedExecutionEngine:
    """Coordinates risk checks and order routing across execution modes."""

    def __init__(
        self,
        risk_engine: RiskManager | None = None,
        paper_engine: PaperTradingService | None = None,
        broker_client: Any = None,
    ) -> None:
        self.risk_engine = risk_engine or risk_manager
        self.paper_engine = paper_engine or paper_service
        self.broker_client = broker_client or dhan_broker

    def get_execution_mode(self) -> BrokerMode:
        """Determines the active execution mode. Defaults safely to PAPER."""
        if settings.paper_trading_only:
            return BrokerMode.PAPER
        return BrokerMode.LIVE_GATED

    def execute_order(
        self,
        symbol: str,
        side: str,
        quantity: int,
        price: float = 0.0,
        order_type: str = "MARKET",
        product_type: str = "CNC",
        exchange_segment: str = "NSE_EQ",
        strategy_id: str = "manual",
        mode: BrokerMode | None = None,
    ) -> ExecutionResult:
        """Evaluates risk and routes order to the active execution target."""
        active_mode = mode or self.get_execution_mode()

        # 1. Build normalized order request
        trans_type = TransactionType.BUY if side.upper() == "BUY" else TransactionType.SELL
        o_type = OrderType(order_type.upper()) if order_type.upper() in OrderType.__members__ else OrderType.MARKET
        p_type = ProductType(product_type.upper()) if product_type.upper() in ProductType.__members__ else ProductType.CNC
        ex_seg = ExchangeSegment(exchange_segment.upper()) if exchange_segment.upper() in ExchangeSegment.__members__ else ExchangeSegment.NSE_EQ

        req = OrderPlacementRequest(
            symbol=symbol.upper(),
            security_id="",
            transaction_type=trans_type,
            order_type=o_type,
            quantity=quantity,
            price=price,
            product_type=p_type,
            exchange_segment=ex_seg,
            strategy_id=strategy_id,
        )

        # 2. Get current account state for pre-trade risk evaluation
        portfolio_summary = self.paper_engine.get_portfolio_summary()
        account_equity = float(portfolio_summary.get("net_worth") or settings.default_account_equity)
        open_positions = len(self.paper_engine.get_positions())

        # 3. Pre-Trade Risk Evaluation
        risk_res = self.risk_engine.evaluate_order(
            request=req,
            account_equity=account_equity,
            current_open_positions=open_positions,
        )

        if not risk_res.is_approved:
            logger.warning(f"Order for {symbol} rejected by RiskManager: {risk_res.rejection_reason}")
            return ExecutionResult(
                success=False,
                mode=active_mode,
                order_id="",
                status="REJECTED_BY_RISK",
                message=risk_res.rejection_reason,
                symbol=symbol,
                side=side,
                quantity=quantity,
                price=price,
                risk_approved=False,
                rejection_reason=risk_res.rejection_reason,
            )

        # 4. Route according to mode
        if active_mode == BrokerMode.PAPER:
            paper_order = self.paper_engine.create_order(
                symbol=symbol,
                side=side.lower(),
                quantity=quantity,
                price=price,
                order_type=order_type.upper(),
                segment="EQUITY_CASH" if exchange_segment == "NSE_EQ" else exchange_segment,
                strategy_id=strategy_id,
            )
            return ExecutionResult(
                success=True,
                mode=BrokerMode.PAPER,
                order_id=paper_order.order_id,
                status=paper_order.status,
                message="Executed in persistent paper trading engine.",
                symbol=paper_order.symbol,
                side=paper_order.side,
                quantity=paper_order.quantity,
                price=paper_order.price,
                fees=paper_order.fees,
                filled_price=paper_order.fill_price or paper_order.price,
                filled_quantity=paper_order.filled_quantity,
                risk_approved=True,
            )

        elif active_mode == BrokerMode.LIVE_GATED:
            # Route to Dhan broker adapter (which strictly runs in TRANSIT_SANDBOX mode)
            dhan_order = self.broker_client.place_order(
                security_id="",
                symbol=symbol,
                transaction_type=trans_type.value,
                order_type=o_type.value,
                quantity=quantity,
                price=price,
                exchange_segment=ex_seg.value,
                product_type=p_type.value,
            )
            return ExecutionResult(
                success=True,
                mode=BrokerMode.LIVE_GATED,
                order_id=dhan_order.order_id,
                status=dhan_order.order_status,
                message=dhan_order.message,
                symbol=dhan_order.symbol,
                side=dhan_order.transaction_type,
                quantity=dhan_order.quantity,
                price=dhan_order.price,
                risk_approved=True,
            )

        else:
            return ExecutionResult(
                success=False,
                mode=active_mode,
                order_id="",
                status="UNSUPPORTED_MODE",
                message=f"Mode {active_mode} not supported for real-time execution.",
                symbol=symbol,
                side=side,
                quantity=quantity,
                price=price,
            )


execution_engine = UnifiedExecutionEngine()
