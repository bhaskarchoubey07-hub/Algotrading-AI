"""Test suite for SupabaseRepository persistence operations (Orders, Positions, Runs, Audit)."""

import os
import tempfile
import pytest
from app.database.supabase_client import SupabaseRepository


@pytest.fixture
def temp_repo(tmp_path):
    """Create a temporary isolated SQLite repository."""
    db_path = str(tmp_path / "test_persistence.db")
    repo = SupabaseRepository(database_url=f"sqlite:///{db_path}")
    yield repo


def test_order_persistence_and_retrieval(temp_repo):
    """Verify that paper orders can be saved and listed from the repository."""
    order_data = {
        "order_id": "test_ord_101",
        "symbol": "RELIANCE",
        "side": "buy",
        "quantity": 10,
        "price": 2840.0,
        "order_type": "MARKET",
        "status": "FILLED",
        "fill_price": 2841.5,
        "fees": 20.0,
        "strategy_id": "ema_trend",
        "created_at": "2026-10-25T10:00:00Z",
    }
    saved = temp_repo.save_paper_order(order_data)
    assert saved is True

    orders = temp_repo.list_paper_orders(limit=10)
    assert len(orders) >= 1
    assert orders[0]["order_id"] == "test_ord_101"
    assert orders[0]["symbol"] == "RELIANCE"
    assert orders[0]["fill_price"] == 2841.5


def test_position_save_and_delete(temp_repo):
    """Verify position upsert and deletion on square-off."""
    pos_data = {
        "symbol": "TCS",
        "side": "buy",
        "quantity": 5,
        "entry_price": 4120.0,
        "current_price": 4150.0,
        "stop_loss": 4050.0,
        "take_profit": 4250.0,
        "unrealized_pnl": 150.0,
        "segment": "EQUITY_CASH",
        "strategy_id": "rsi_reversal",
        "created_at": "2026-10-25T10:00:00Z",
    }
    temp_repo.save_position(pos_data)
    positions = temp_repo.list_positions()
    assert len(positions) == 1
    assert positions[0]["symbol"] == "TCS"

    # Delete on position close
    temp_repo.delete_position("TCS")
    assert len(temp_repo.list_positions()) == 0


def test_strategy_version_persistence(temp_repo):
    """Verify strategy versioning can be saved and retrieved."""
    v_data = {
        "version_id": "v_ema_001",
        "strategy_id": "ema_trend",
        "version": "1.1.0",
        "parameters": {"fast_ema": 9, "slow_ema": 21},
        "description": "Updated fast EMA period",
        "created_by": "quant_trader",
        "created_at": "2026-10-25T10:00:00Z",
    }
    temp_repo.save_strategy_version(v_data)
    versions = temp_repo.get_strategy_versions("ema_trend")
    assert len(versions) == 1
    assert versions[0]["version"] == "1.1.0"
    assert versions[0]["parameters"]["fast_ema"] == 9


def test_backtest_run_persistence(temp_repo):
    """Verify backtest experiment runs can be saved and listed."""
    run_data = {
        "run_id": "run_test_001",
        "strategy_id": "donchian_breakout",
        "symbol": "NIFTY 50",
        "start_date": "2025-01-01",
        "end_date": "2025-12-31",
        "initial_capital": 500000.0,
        "final_equity": 585000.0,
        "total_return_pct": 17.0,
        "win_rate_pct": 58.5,
        "profit_factor": 1.85,
        "max_drawdown_pct": 4.2,
        "trades_count": 48,
        "metrics": {"sharpe": 1.7},
        "created_at": "2026-10-25T10:00:00Z",
    }
    temp_repo.save_backtest_run(run_data)
    runs = temp_repo.list_backtest_runs(limit=5)
    assert len(runs) == 1
    assert runs[0]["run_id"] == "run_test_001"
    assert runs[0]["total_return_pct"] == 17.0

    retrieved = temp_repo.get_backtest_run("run_test_001")
    assert retrieved is not None
    assert retrieved["profit_factor"] == 1.85


def test_risk_event_audit(temp_repo):
    """Verify that risk rejections are durably recorded."""
    event_data = {
        "event_id": "risk_rej_001",
        "rule_name": "MAX_CONCURRENT_POSITIONS",
        "severity": "WARNING",
        "symbol": "INFY",
        "order_details": {"qty": 100, "side": "buy"},
        "reason": "Max open positions limit (5) reached",
        "created_at": "2026-10-25T10:00:00Z",
    }
    temp_repo.save_risk_event(event_data)
    events = temp_repo.list_risk_events(limit=5)
    assert len(events) == 1
    assert events[0]["rule_name"] == "MAX_CONCURRENT_POSITIONS"
    assert events[0]["symbol"] == "INFY"
