"""Test suite for IntegrationHealthService and live subsystem probes."""

import pytest
from app.services.health import IntegrationHealthService, integration_health


def test_integration_health_service_structure():
    """Verify that IntegrationHealthService returns structured component diagnostics."""
    health = integration_health.get_system_health()

    assert "components" in health
    assert "supabase" in health
    assert "dhan" in health
    assert "tradingview" in health
    assert "risk_engine" in health
    assert "overall_status" in health

    assert health["overall_status"] in {"HEALTHY", "DEGRADED", "OFFLINE"}


def test_supabase_health_probe():
    """Test Supabase health probe reporting unconfigured/sqlite active or cloud connected."""
    service = IntegrationHealthService()
    sb_health = service.check_supabase_health()

    assert "status" in sb_health
    assert "badge" in sb_health
    assert "is_connected" in sb_health
    assert sb_health["status"] in {"SUPABASE_CONNECTED", "UNCONFIGURED_SQLITE_ACTIVE", "SUPABASE_ERROR"}


def test_dhan_health_probe():
    """Test DhanHQ health probe reporting either mock sandbox or authenticated connection."""
    service = IntegrationHealthService()
    dhan_health = service.check_dhan_health()

    assert "status" in dhan_health
    assert "badge" in dhan_health
    assert "is_connected" in dhan_health
    assert dhan_health["status"] in {"DHAN_CONNECTED", "DHAN_MOCK_SANDBOX", "DHAN_AUTH_FAILED"}


def test_tradingview_telemetry_probe():
    """Test TradingView health probe structure."""
    service = IntegrationHealthService()
    tv_health = service.check_tradingview_health()

    assert "status" in tv_health
    assert "accepted_events" in tv_health
    assert "rejected_events" in tv_health
    assert "duplicate_events" in tv_health
