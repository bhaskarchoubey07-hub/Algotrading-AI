"""Tests for RiskManager and UnifiedExecutionEngine."""

import pytest
from app.brokers.base import (
    BrokerMode,
    ExchangeSegment,
    OrderPlacementRequest,
    OrderType,
    ProductType,
    TransactionType,
)
from app.services.execution_engine import UnifiedExecutionEngine
from app.services.risk_manager import RiskManager


def test_risk_manager_order_evaluation():
    rm = RiskManager(
        max_order_value=50_000.0,
        max_open_positions=5,
        max_position_fraction=0.10,
        max_daily_loss_fraction=0.01,
    )
    req = OrderPlacementRequest(
        symbol="RELIANCE",
        security_id="2885",
        transaction_type=TransactionType.BUY,
        order_type=OrderType.MARKET,
        quantity=10,
        price=2800.0,
    )

    # 1. Valid order passes (notional = 28,000 <= 50,000)
    res = rm.evaluate_order(req, account_equity=1_000_000.0, current_open_positions=2)
    assert res.is_approved is True

    # 2. Max order value breach (notional = 2800 * 25 = 70,000 > 50,000)
    req_large = OrderPlacementRequest(
        symbol="RELIANCE",
        security_id="2885",
        transaction_type=TransactionType.BUY,
        order_type=OrderType.MARKET,
        quantity=25,
        price=2800.0,
    )
    res_large = rm.evaluate_order(req_large, account_equity=1_000_000.0, current_open_positions=2)
    assert res_large.is_approved is False
    assert "exceeds limit" in res_large.rejection_reason

    # 3. Position concentration breach (e.g. existing 90,000 + 28,000 = 118,000 > 10% of 1M = 100k)
    res_conc = rm.evaluate_order(
        req,
        account_equity=1_000_000.0,
        current_open_positions=2,
        current_instrument_exposure=90_000.0,
    )
    assert res_conc.is_approved is False
    assert "concentration breach" in res_conc.rejection_reason.lower()

    # 4. Max open positions breach
    res_pos = rm.evaluate_order(req, account_equity=1_000_000.0, current_open_positions=5)
    assert res_pos.is_approved is False
    assert "max concurrent positions" in res_pos.rejection_reason.lower()


def test_risk_manager_kill_switch():
    rm = RiskManager()
    req = OrderPlacementRequest(
        symbol="INFY",
        security_id="1594",
        transaction_type=TransactionType.BUY,
        order_type=OrderType.MARKET,
        quantity=5,
        price=1750.0,
    )

    assert rm.is_kill_switch_active() is False
    rm.set_kill_switch(True)
    assert rm.is_kill_switch_active() is True

    res = rm.evaluate_order(req, account_equity=1_000_000.0, current_open_positions=0)
    assert res.is_approved is False
    assert "kill switch is active" in res.rejection_reason.lower()

    rm.set_kill_switch(False)
    res_cleared = rm.evaluate_order(req, account_equity=1_000_000.0, current_open_positions=0)
    assert res_cleared.is_approved is True


def test_unified_execution_engine_routing():
    engine = UnifiedExecutionEngine()

    # Paper mode execution
    paper_res = engine.execute_order(
        symbol="TCS",
        side="BUY",
        quantity=2,
        price=4100.0,
        mode=BrokerMode.PAPER,
    )
    assert paper_res.success is True
    assert paper_res.mode == BrokerMode.PAPER
    assert paper_res.order_id != ""
    assert paper_res.risk_approved is True

    # Live-gated mode execution (routes to Dhan mock adapter in TRANSIT_SANDBOX mode)
    live_res = engine.execute_order(
        symbol="RELIANCE",
        side="BUY",
        quantity=5,
        price=2840.0,
        mode=BrokerMode.LIVE_GATED,
    )
    assert live_res.success is True
    assert live_res.mode == BrokerMode.LIVE_GATED
    assert live_res.status == "TRANSIT_SANDBOX"
    assert "live execution gate is closed" in live_res.message
