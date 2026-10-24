import os
import pytest
from app.database.supabase_client import SupabaseRepository


def test_supabase_repository_local_sqlite(tmp_path):
    db_file = str(tmp_path / "test_algotrade.db")
    repo = SupabaseRepository(db_path=db_file)
    assert os.path.exists(db_file)

    # Test audit logging
    audit = repo.log_audit("system", "TEST_ACTION", "strategy", "ema_trend", {"param": 12})
    assert audit["id"] is not None
    assert audit["action"] == "TEST_ACTION"

    # Test listing audit logs
    logs = repo.list_audit_logs()
    assert len(logs) == 1
    assert logs[0]["action"] == "TEST_ACTION"
    assert logs[0]["details"]["param"] == 12


def test_supabase_repository_save_signal(tmp_path):
    db_file = str(tmp_path / "test_sig_db.db")
    repo = SupabaseRepository(db_path=db_file)

    sig_data = {
        "strategy_id": "supertrend",
        "symbol": "NIFTY",
        "timestamp": "2024-01-01T00:00:00Z",
        "direction": "long",
        "score": 0.85,
        "reason": "Bullish supertrend",
    }
    repo.save_signal(sig_data)
    status = repo.get_database_status()
    assert status["mode"] == "local_sqlite"
