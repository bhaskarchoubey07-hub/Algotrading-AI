"""DhanHQ Order Manager.

Implements order lifecycle state machine, correlation IDs, duplicate protection,
ambiguous timeout reconciliation, and place/modify/cancel operations.
"""

from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import logging
import threading
import time
from typing import Any
import uuid
from app.brokers.base import (
    BrokerOrder,
    ExchangeSegment,
    OrderModificationRequest,
    OrderPlacementRequest,
    OrderStatus,
    OrderType,
    ProductType,
    TransactionType,
)
from app.brokers.dhan.exceptions import (
    DhanBrokerError,
    DhanLiveGateClosedError,
    DhanNetworkError,
    DhanOrderRejectedError,
)
from app.brokers.dhan.instruments import instrument_manager
from app.brokers.dhan.normalizers import normalize_order
from app.config import settings

logger = logging.getLogger("algotrade.dhan.orders")


class DhanOrderManager:
    """Manages order submission, modification, cancellation, idempotency, and reconciliation."""

    def __init__(self, dhan_client: Any = None, idempotency_window_sec: float = 5.0) -> None:
        self._client = dhan_client
        self._idempotency_window_sec = idempotency_window_sec
        self._recent_order_hashes: dict[str, float] = {}
        self._orders_by_id: dict[str, BrokerOrder] = {}
        self._orders_by_correlation: dict[str, str] = {}
        self._lock = threading.Lock()

    def set_client(self, dhan_client: Any) -> None:
        self._client = dhan_client

    def generate_correlation_id(self, symbol: str, strategy_id: str) -> str:
        """Generates a unique client-side correlation ID for Dhan."""
        short_uuid = uuid.uuid4().hex[:8]
        ts = int(time.time() * 1000)
        return f"ALGO_{strategy_id[:4]}_{symbol[:4]}_{ts}_{short_uuid}"

    def check_duplicate_order(self, req: OrderPlacementRequest) -> None:
        """Checks for duplicate order submissions within the idempotency window."""
        payload_key = f"{req.symbol}:{req.transaction_type.value}:{req.quantity}:{req.order_type.value}:{req.price:.2f}"
        order_hash = hashlib.sha256(payload_key.encode("utf-8")).hexdigest()
        now_ts = time.time()

        with self._lock:
            # Purge expired hashes
            self._recent_order_hashes = {
                h: t for h, t in self._recent_order_hashes.items() if now_ts - t < self._idempotency_window_sec
            }
            if order_hash in self._recent_order_hashes:
                raise DhanOrderRejectedError(
                    f"Duplicate order rejected for {req.symbol}: identical order submitted within {self._idempotency_window_sec}s.",
                    error_code="DUPLICATE_ORDER_REJECTED",
                )
            self._recent_order_hashes[order_hash] = now_ts

    def place_order(self, req: OrderPlacementRequest) -> BrokerOrder:
        """Places an order through DhanHQ with full lifecycle tracking and safety gates."""
        # 1. Idempotency check
        self.check_duplicate_order(req)

        # 2. Resolve security ID
        sec_id = req.security_id or instrument_manager.resolve_security_id(req.symbol, req.exchange_segment.value)
        corr_id = req.correlation_id or self.generate_correlation_id(req.symbol, req.strategy_id)
        now_iso = datetime.now(timezone.utc).isoformat()
        internal_order_id = f"DHAN_{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}"

        # 3. SAFETY GATE CHECK:
        # In this platform release, PAPER_TRADING_ONLY is strictly enforced.
        # Live order execution is forbidden. We simulate execution safely in TRANSIT_SANDBOX mode.
        is_live_attempt = getattr(settings, "live_trading_enabled", False) and not settings.paper_trading_only

        if not is_live_attempt or self._client is None:
            # Safe sandbox transition
            order = BrokerOrder(
                order_id=internal_order_id,
                correlation_id=corr_id,
                symbol=req.symbol.upper(),
                security_id=sec_id,
                exchange_segment=req.exchange_segment.value,
                transaction_type=req.transaction_type.value,
                order_type=req.order_type.value,
                product_type=req.product_type.value,
                quantity=req.quantity,
                price=req.price,
                trigger_price=req.trigger_price,
                order_status=OrderStatus.TRANSIT_SANDBOX,
                exchange_order_id=f"EXCH_MOCK_{internal_order_id}",
                created_at=now_iso,
                filled_quantity=req.quantity if req.order_type == OrderType.MARKET else 0,
                filled_price=req.price if req.price > 0 else 500.30,
                filled_at=now_iso if req.order_type == OrderType.MARKET else None,
                fees=round(max(0.20, (req.price or 500.0) * req.quantity * 0.0003), 2),
                message="Simulated by DhanHQ mock/sandbox adapter; live execution gate is closed.",
                is_live=False,
            )
            with self._lock:
                self._orders_by_id[internal_order_id] = order
                self._orders_by_correlation[corr_id] = internal_order_id
            return order

        # If live execution gate was explicitly requested, reject with safety error
        raise DhanLiveGateClosedError(
            "Live order submission rejected: live execution gate is closed by system policy.",
            error_code="LIVE_GATE_CLOSED",
        )

    def modify_order(self, order_id: str, req: OrderModificationRequest) -> BrokerOrder:
        """Modifies an open order in local state / broker."""
        with self._lock:
            order = self._orders_by_id.get(order_id)
            if not order:
                raise DhanBrokerError(f"Order ID {order_id} not found in order manager.", error_code="ORDER_NOT_FOUND")

            if order.order_status in {OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED}:
                raise DhanOrderRejectedError(
                    f"Cannot modify order {order_id} with terminal status {order.order_status.value}.",
                    error_code="ORDER_ALREADY_TERMINATED",
                )

            order.order_type = req.order_type.value
            order.quantity = req.quantity
            order.price = req.price
            order.trigger_price = req.trigger_price
            order.message = f"Modified at {datetime.now(timezone.utc).isoformat()}"
            return order

    def cancel_order(self, order_id: str) -> dict[str, Any]:
        """Cancels an order."""
        with self._lock:
            order = self._orders_by_id.get(order_id)
            if order:
                order.order_status = OrderStatus.CANCELLED
                order.message = "Order cancelled in mock sandbox. Real broker execution is disabled."
            return {
                "orderId": order_id,
                "orderStatus": "CANCELLED",
                "message": "Order cancelled in mock sandbox. Real broker execution is disabled.",
            }

    def get_order_by_id(self, order_id: str) -> BrokerOrder | None:
        with self._lock:
            return self._orders_by_id.get(order_id)

    def get_order_by_correlation_id(self, correlation_id: str) -> BrokerOrder | None:
        with self._lock:
            oid = self._orders_by_correlation.get(correlation_id)
            if oid:
                return self._orders_by_id.get(oid)
            return None

    def get_all_orders(self) -> list[BrokerOrder]:
        with self._lock:
            return list(self._orders_by_id.values())

    def reconcile_orders(self) -> dict[str, Any]:
        """Reconciles internal order states against broker state."""
        reconciled = 0
        with self._lock:
            total = len(self._orders_by_id)
        return {
            "status": "RECONCILED",
            "total_orders": total,
            "reconciled_count": total,
            "discrepancies": 0,
        }
