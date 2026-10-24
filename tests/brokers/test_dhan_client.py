"""Tests for DhanClient and Authentication Governance."""

import pytest
from app.brokers.dhan.auth import DhanAuthManager
from app.brokers.dhan.client import DhanClient, DhanHQBrokerAdapter, dhan_broker
from app.brokers.dhan.exceptions import DhanAuthenticationError
from app.brokers.dhan.normalizers import redact_sensitive_data


def test_dhan_auth_manager_redaction():
    auth = DhanAuthManager(client_id="1000123456", access_token="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.dummy_token_12345")
    status = auth.get_credential_status()
    assert status.client_id_configured is True
    assert status.access_token_configured is True
    assert "1000123456" not in status.client_id_masked
    assert "dummy_token_12345" not in status.access_token_masked
    assert status.client_id_masked.startswith("10")
    assert status.client_id_masked.endswith("56")
    assert status.live_gate_closed is True


def test_dhan_auth_manager_validation():
    auth_empty = DhanAuthManager(client_id="", access_token="")
    with pytest.raises(DhanAuthenticationError) as exc_info:
        auth_empty.validate_or_raise()
    assert "missing" in str(exc_info.value).lower()

    auth_short = DhanAuthManager(client_id="123", access_token="too_short")
    with pytest.raises(DhanAuthenticationError) as exc_info:
        auth_short.validate_or_raise()
    assert "truncated" in str(exc_info.value).lower() or "invalid" in str(exc_info.value).lower()


def test_redact_sensitive_data():
    raw_payload = {
        "client_id": "secret_id_123",
        "access_token": "secret_jwt_token",
        "symbol": "RELIANCE",
        "price": 2840.5,
        "nested": {
            "pan": "ABCDE1234F",
            "quantity": 10,
        },
    }
    redacted = redact_sensitive_data(raw_payload)
    assert redacted["client_id"] == "[REDACTED]"
    assert redacted["access_token"] == "[REDACTED]"
    assert redacted["symbol"] == "RELIANCE"
    assert redacted["price"] == 2840.5
    assert redacted["nested"]["pan"] == "[REDACTED]"
    assert redacted["nested"]["quantity"] == 10


def test_dhan_client_sandbox_fallback():
    client = DhanClient(client_id="", access_token="")
    assert client.is_connected is False
    status = client.get_account_status()
    assert status["broker"] == "DhanHQ"
    assert status["live_gate_closed"] is True
    assert status["live_execution_supported"] is False


def test_dhan_broker_legacy_singleton():
    status = dhan_broker.get_connection_status()
    assert "live_gate_closed" in status
    assert status["live_gate_closed"] is True
    funds = dhan_broker.get_fund_limits()
    assert funds.available_cash > 0
    assert funds.net_equity > 0
