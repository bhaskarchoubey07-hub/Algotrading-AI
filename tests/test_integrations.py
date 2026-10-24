from datetime import datetime, timezone
import pytest
from fastapi import HTTPException
from app.config import settings
from app.integrations.dhan.client import DhanHQBrokerAdapter
from app.integrations.tradingview.webhook import TradingViewAlertPayload, TradingViewWebhookHandler


def test_dhan_adapter_sandbox_mode():
    adapter = DhanHQBrokerAdapter(client_id="", access_token="")
    assert not adapter.is_connected

    funds = adapter.get_fund_limits()
    assert funds.available_cash > 0
    assert funds.net_equity > 0

    positions = adapter.get_positions()
    assert len(positions) > 0
    assert positions[0]["tradingSymbol"] == "RELIANCE"

    holdings = adapter.get_holdings()
    assert len(holdings) > 0


def test_dhan_adapter_safety_gate():
    adapter = DhanHQBrokerAdapter()
    # Placing an order when live gate is closed returns simulated sandbox order
    order = adapter.place_order(
        security_id="1333",
        symbol="HDFCBANK",
        transaction_type="BUY",
        order_type="MARKET",
        quantity=10,
    )
    assert order.order_status == "TRANSIT_SANDBOX"
    assert not order.is_live
    assert "live execution gate is closed" in order.message


def test_tradingview_webhook_valid_payload():
    handler = TradingViewWebhookHandler()
    payload = TradingViewAlertPayload(
        event_id="test_ev_01",
        strategy_id="tv_trend",
        symbol="RELIANCE",
        direction="long",
        timestamp=datetime.now(timezone.utc).isoformat(),
        reference_price=2840.0,
        passphrase=settings.tradingview_webhook_secret,
    )
    res = handler.process_webhook(payload)
    assert res["status"] == "ACCEPTED"
    assert res["symbol"] == "RELIANCE"


def test_tradingview_webhook_replay_protection():
    handler = TradingViewWebhookHandler()
    payload = TradingViewAlertPayload(
        event_id="test_replay_02",
        strategy_id="tv_trend",
        symbol="TCS",
        direction="long",
        timestamp=datetime.now(timezone.utc).isoformat(),
        reference_price=4100.0,
        passphrase=settings.tradingview_webhook_secret,
    )
    handler.process_webhook(payload)

    # Replay same event_id
    with pytest.raises(HTTPException) as exc:
        handler.process_webhook(payload)
    assert exc.value.status_code == 409


def test_tradingview_webhook_auth_failure():
    handler = TradingViewWebhookHandler()
    payload = TradingViewAlertPayload(
        event_id="test_auth_03",
        strategy_id="tv_trend",
        symbol="INFY",
        direction="short",
        timestamp=datetime.now(timezone.utc).isoformat(),
        reference_price=1750.0,
        passphrase="wrong_secret_123",
    )
    with pytest.raises(HTTPException) as exc:
        handler.process_webhook(payload)
    assert exc.value.status_code == 401


def test_tradingview_webhook_stale_timestamp():
    handler = TradingViewWebhookHandler(max_drift_seconds=60)
    # 5 minutes in past
    past_ts = "2024-01-01T00:00:00Z"
    payload = TradingViewAlertPayload(
        event_id="test_stale_04",
        strategy_id="tv_trend",
        symbol="INFY",
        direction="long",
        timestamp=past_ts,
        reference_price=1750.0,
        passphrase=settings.tradingview_webhook_secret,
    )
    with pytest.raises(HTTPException) as exc:
        handler.process_webhook(payload)
    assert exc.value.status_code == 400
