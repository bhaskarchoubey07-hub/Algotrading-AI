"""Tests for DhanOrderManager, Idempotency, and Lifecycle States."""

import pytest
from app.brokers.base import (
    ExchangeSegment,
    OrderModificationRequest,
    OrderPlacementRequest,
    OrderStatus,
    OrderType,
    ProductType,
    TransactionType,
)
from app.brokers.dhan.exceptions import DhanOrderRejectedError
from app.brokers.dhan.orders import DhanOrderManager


def test_dhan_order_placement_sandbox():
    om = DhanOrderManager()
    req = OrderPlacementRequest(
        symbol="RELIANCE",
        security_id="2885",
        transaction_type=TransactionType.BUY,
        order_type=OrderType.MARKET,
        quantity=15,
        price=2840.0,
        exchange_segment=ExchangeSegment.NSE_EQ,
        product_type=ProductType.CNC,
    )
    order = om.place_order(req)
    assert order.order_status == OrderStatus.TRANSIT_SANDBOX
    assert order.symbol == "RELIANCE"
    assert order.quantity == 15
    assert not order.is_live
    assert "live execution gate is closed" in order.message
    assert order.correlation_id.startswith("ALGO_")

    # Order lookup
    retrieved = om.get_order_by_id(order.order_id)
    assert retrieved is not None
    assert retrieved.order_id == order.order_id


def test_dhan_order_duplicate_protection():
    om = DhanOrderManager(idempotency_window_sec=5.0)
    req = OrderPlacementRequest(
        symbol="TCS",
        security_id="11536",
        transaction_type=TransactionType.BUY,
        order_type=OrderType.LIMIT,
        quantity=10,
        price=4100.0,
    )
    # First placement succeeds
    om.place_order(req)

    # Immediate duplicate submission should raise DhanOrderRejectedError
    with pytest.raises(DhanOrderRejectedError) as exc_info:
        om.place_order(req)
    assert "duplicate order rejected" in str(exc_info.value).lower()


def test_dhan_order_cancellation_and_modification():
    om = DhanOrderManager()
    req = OrderPlacementRequest(
        symbol="INFY",
        security_id="1594",
        transaction_type=TransactionType.BUY,
        order_type=OrderType.LIMIT,
        quantity=20,
        price=1750.0,
    )
    order = om.place_order(req)

    # Modify
    mod_req = OrderModificationRequest(
        order_id=order.order_id,
        order_type=OrderType.LIMIT,
        quantity=25,
        price=1755.0,
    )
    modified = om.modify_order(order.order_id, mod_req)
    assert modified.quantity == 25
    assert modified.price == 1755.0

    # Cancel
    cancel_res = om.cancel_order(order.order_id)
    assert cancel_res["orderStatus"] == "CANCELLED"
    cancelled_order = om.get_order_by_id(order.order_id)
    assert cancelled_order.order_status == OrderStatus.CANCELLED


def test_dhan_order_reconciliation():
    om = DhanOrderManager()
    res = om.reconcile_orders()
    assert res["status"] == "RECONCILED"
    assert "discrepancies" in res
