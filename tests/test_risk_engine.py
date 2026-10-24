from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import pytest
from app.models import AlertSeverity, OrderSide, TradingSegment
from app.risk import NSE_MARKET_OPEN, NSE_MARKET_CLOSE, RiskAuthority, RiskConfig, calculate_quantity

IST = ZoneInfo("Asia/Kolkata")


def test_calculate_quantity_preserves_behaviour():
    qty = calculate_quantity(equity=100000, entry=500, stop=495)
    assert qty == 20  # capped by 10% max position value = 10,000 / 500 = 20

    qty_risk = calculate_quantity(equity=100000, entry=500, stop=475)
    # risk budget = 100000 * 0.0025 = 250; per share risk = 25; qty = 10
    assert qty_risk == 10


def test_calculate_quantity_validation():
    with pytest.raises(ValueError):
        calculate_quantity(equity=-100, entry=500, stop=495)
    with pytest.raises(ValueError):
        calculate_quantity(equity=100000, entry=500, stop=500)


def test_risk_authority_kill_switch():
    auth = RiskAuthority()
    assert not auth.kill_switch_active

    auth.trip_kill_switch("Testing manual trip")
    assert auth.kill_switch_active

    ok, msg = auth.validate_order("RELIANCE", "buy", 10, 2800.0, 0)
    assert not ok
    assert "kill-switch" in msg.lower()

    auth.reset_kill_switch()
    assert not auth.kill_switch_active
    ok, msg = auth.validate_order("RELIANCE", "buy", 10, 2800.0, 0)
    assert ok


def test_risk_authority_drawdown_circuit_breaker():
    auth = RiskAuthority(config=RiskConfig(max_drawdown_fraction=0.05), initial_equity=1_000_000.0)
    # 6% drop
    auth.update_equity(940_000.0)
    assert auth.circuit_breaker_tripped
    assert auth.kill_switch_active

    ok, msg = auth.validate_order("TCS", "buy", 5, 4000.0, 0)
    assert not ok


def test_risk_authority_daily_loss_limit():
    auth = RiskAuthority(config=RiskConfig(max_daily_loss_fraction=0.01), initial_equity=1_000_000.0)
    # 1.5% drop from start
    auth.update_equity(985_000.0)
    assert auth.circuit_breaker_tripped
    assert auth.kill_switch_active


def test_risk_authority_max_positions():
    auth = RiskAuthority(config=RiskConfig(max_open_positions=3))
    ok, msg = auth.validate_order("INFY", "buy", 10, 1700.0, current_positions_count=3)
    assert not ok
    assert "maximum open positions" in msg.lower()


def test_risk_authority_lot_size_validation():
    auth = RiskAuthority()
    # NIFTY lot size 25
    ok, msg = auth.validate_order("NIFTY_FUT", "buy", 30, 24500.0, 0, lot_size=25)
    assert not ok
    assert "multiple of lot size" in msg.lower()

    ok, msg = auth.validate_order("NIFTY_FUT", "buy", 50, 24500.0, 0, lot_size=25)
    # 50 * 24500 = 1,225,000 exceeds 10% notional cap of 1,000,000 equity (even with 15% margin = 183,750 > 100,000)
    assert not ok
    assert "exceeds max allowed" in msg.lower()

    # 1 lot of NIFTY (25 * 24500 = 612,500 * 0.15 = 91,875 <= 100,000) passes derivative margin
    ok, msg = auth.validate_order("NIFTY_FUT", "buy", 25, 24500.0, 0, segment=TradingSegment.INDEX_FUTURES, lot_size=25)
    assert ok
    assert "passed all risk authority checks" in msg.lower()


def test_risk_authority_market_hours_check():
    auth = RiskAuthority()
    # Weekend
    saturday_noon = datetime(2026, 10, 24, 12, 0, tzinfo=IST)
    is_open, msg = auth.is_market_open(saturday_noon)
    assert not is_open
    assert "Weekend" in msg

    # Weekday regular trading hours
    friday_noon = datetime(2026, 10, 23, 12, 30, tzinfo=IST)
    is_open, msg = auth.is_market_open(friday_noon)
    assert is_open
    assert "OPEN" in msg
