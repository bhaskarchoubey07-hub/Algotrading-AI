from datetime import datetime, timezone
import json
import logging
import sqlite3
from typing import Any
from uuid import uuid4
import requests
from app.config import settings

logger = logging.getLogger("algotrade.database")


class SupabaseRepository:
    """Database repository with dual support: Supabase PostgREST cloud and local SQLite fallback."""

    def __init__(self, db_path: str = "algotrade_local.db") -> None:
        self.db_path = db_path
        self.supabase_url = settings.supabase_url.rstrip("/") if settings.supabase_url else ""
        self.supabase_key = settings.supabase_key
        self.is_cloud = bool(self.supabase_url and self.supabase_key)
        self._init_sqlite()

    def _init_sqlite(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS audit_logs (
                    id TEXT PRIMARY KEY,
                    actor TEXT,
                    action TEXT,
                    entity_type TEXT,
                    entity_id TEXT,
                    details TEXT,
                    created_at TEXT
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS signals_store (
                    id TEXT PRIMARY KEY,
                    event_key TEXT UNIQUE,
                    strategy_id TEXT,
                    symbol TEXT,
                    direction TEXT,
                    score REAL,
                    reason TEXT,
                    created_at TEXT
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS backtest_runs (
                    id TEXT PRIMARY KEY,
                    strategy_id TEXT,
                    symbol TEXT,
                    timeframe TEXT,
                    metrics TEXT,
                    created_at TEXT
                )
            """)
            conn.commit()

    def log_audit(self, actor: str, action: str, entity_type: str, entity_id: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
        record_id = str(uuid4())
        now_ts = datetime.now(timezone.utc).isoformat()
        details_json = json.dumps(details or {})

        # 1. Local SQLite store
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO audit_logs (id, actor, action, entity_type, entity_id, details, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (record_id, actor, action, entity_type, entity_id, details_json, now_ts),
                )
                conn.commit()
        except Exception as exc:
            logger.error(f"Failed to record local audit log: {exc}")

        # 2. Cloud Supabase store if configured
        if self.is_cloud:
            try:
                headers = {
                    "apikey": self.supabase_key,
                    "Authorization": f"Bearer {self.supabase_key}",
                    "Content-Type": "application/json",
                    "Prefer": "return=minimal",
                }
                payload = {
                    "id": record_id,
                    "actor": actor,
                    "action": action,
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                    "details": details or {},
                    "created_at": now_ts,
                }
                requests.post(f"{self.supabase_url}/rest/v1/audit_logs", json=payload, headers=headers, timeout=3.0)
            except Exception as exc:
                logger.warning(f"Supabase audit log sync failed: {exc}")

        return {"id": record_id, "action": action, "actor": actor, "created_at": now_ts}

    def save_signal(self, signal: dict[str, Any]) -> None:
        rec_id = str(uuid4())
        event_key = f"{signal.get('strategy_id')}_{signal.get('symbol')}_{signal.get('timestamp')}"
        now_ts = datetime.now(timezone.utc).isoformat()
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """INSERT OR REPLACE INTO signals_store (id, event_key, strategy_id, symbol, direction, score, reason, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        rec_id,
                        event_key,
                        signal.get("strategy_id", "unknown"),
                        signal.get("symbol", "N/A"),
                        signal.get("direction", "flat"),
                        float(signal.get("score", 0.0)),
                        signal.get("reason", ""),
                        now_ts,
                    ),
                )
                conn.commit()
        except Exception as exc:
            logger.error(f"Failed to save signal to local db: {exc}")

    def list_audit_logs(self, limit: int = 50) -> list[dict[str, Any]]:
        results = []
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, actor, action, entity_type, entity_id, details, created_at FROM audit_logs ORDER BY created_at DESC LIMIT ?", (limit,))
                for row in cursor.fetchall():
                    results.append({
                        "id": row[0],
                        "actor": row[1],
                        "action": row[2],
                        "entity_type": row[3],
                        "entity_id": row[4],
                        "details": json.loads(row[5]) if row[5] else {},
                        "created_at": row[6],
                    })
        except Exception as exc:
            logger.error(f"Failed to fetch audit logs: {exc}")
        return results

    def get_database_status(self) -> dict[str, Any]:
        return {
            "mode": "supabase_cloud" if self.is_cloud else "local_sqlite",
            "is_cloud_connected": self.is_cloud,
            "supabase_url": self.supabase_url if self.is_cloud else "Not Configured",
            "local_db_path": self.db_path,
        }


db_repo = SupabaseRepository()
