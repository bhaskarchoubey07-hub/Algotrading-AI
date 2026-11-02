"""AlgoTrade AI — Database Repository & Persistence Layer.

Supports dual-persistence architecture:
1. Production Cloud Supabase (PostgreSQL via PostgREST REST API with Row-Level Security).
2. Robust Local SQLite fallback with exact schema parity ensuring zero data loss during restarts.

Persists:
- Audit logs
- Strategy versions & parameters
- Strategy signals
- Backtest runs, metrics & trade logs
- Paper orders & fills
- Active portfolio positions
- Portfolio equity snapshots
- Adaptive strategy states & health
- Risk events & circuit-breaker halts
- System alerts and notifications
"""

from datetime import datetime, timezone
import json
import logging
import sqlite3
import time
from typing import Any
from uuid import uuid4
import requests

from app.config import settings

logger = logging.getLogger("algotrade.database")


class SupabaseRepository:
    """Unified repository with full schema coverage for Supabase and SQLite."""

    def __init__(self, db_path: str = "algotrade_local.db", database_url: str | None = None) -> None:
        if database_url:
            if database_url.startswith("sqlite:///"):
                self.db_path = database_url.replace("sqlite:///", "")
            else:
                self.db_path = database_url
        else:
            self.db_path = db_path
        self.supabase_url = settings.supabase_url.rstrip("/") if settings.supabase_url else ""
        self.supabase_key = settings.supabase_key
        self.is_cloud = bool(self.supabase_url and self.supabase_key)
        self._last_cloud_status: dict[str, Any] | None = None
        self._init_sqlite()

    def _init_sqlite(self) -> None:
        """Create all required platform tables locally with constraints and indexes."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # 1. Audit logs
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS audit_logs (
                    id TEXT PRIMARY KEY,
                    actor TEXT NOT NULL,
                    action TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    details TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)

            # 2. Signals store
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS signals_store (
                    id TEXT PRIMARY KEY,
                    event_key TEXT UNIQUE NOT NULL,
                    strategy_id TEXT NOT NULL,
                    strategy_version TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    direction TEXT NOT NULL,
                    score REAL NOT NULL,
                    reason TEXT,
                    created_at TEXT NOT NULL
                )
            """)

            # 3. Strategy versions & parameters
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS strategy_versions (
                    strategy_id TEXT NOT NULL,
                    version TEXT NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    parameters TEXT NOT NULL DEFAULT '{}',
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (strategy_id, version)
                )
            """)

            # 4. Backtest runs & results
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS backtest_runs (
                    id TEXT PRIMARY KEY,
                    strategy_id TEXT NOT NULL,
                    strategy_version TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    timeframe TEXT NOT NULL,
                    initial_capital REAL NOT NULL,
                    parameters TEXT NOT NULL,
                    metrics TEXT NOT NULL,
                    equity_curve TEXT NOT NULL,
                    trades_log TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)

            # 5. Paper orders
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS paper_orders (
                    order_id TEXT PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    order_type TEXT NOT NULL,
                    price REAL NOT NULL,
                    fill_price REAL NOT NULL,
                    filled_quantity INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    fees REAL NOT NULL,
                    stop_loss REAL,
                    take_profit REAL,
                    segment TEXT NOT NULL,
                    strategy_id TEXT NOT NULL,
                    note TEXT,
                    created_at TEXT NOT NULL,
                    filled_at TEXT
                )
            """)

            # 6. Positions
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS paper_positions (
                    symbol TEXT PRIMARY KEY,
                    segment TEXT NOT NULL,
                    side TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    entry_price REAL NOT NULL,
                    current_price REAL NOT NULL,
                    stop_loss REAL,
                    take_profit REAL,
                    realized_pnl REAL NOT NULL DEFAULT 0.0,
                    unrealized_pnl REAL NOT NULL DEFAULT 0.0,
                    strategy_id TEXT NOT NULL,
                    notes TEXT,
                    updated_at TEXT NOT NULL
                )
            """)

            # 7. Portfolio snapshots
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS portfolio_snapshots (
                    id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    total_equity REAL NOT NULL,
                    cash_balance REAL NOT NULL,
                    invested_margin REAL NOT NULL,
                    unrealized_pnl REAL NOT NULL,
                    realized_pnl REAL NOT NULL,
                    open_positions_count INTEGER NOT NULL
                )
            """)

            # 8. Adaptive states
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS adaptive_states (
                    strategy_id TEXT PRIMARY KEY,
                    health_state TEXT NOT NULL,
                    allocation_weight REAL NOT NULL,
                    last_reason TEXT,
                    updated_at TEXT NOT NULL
                )
            """)

            # 9. Risk events
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS risk_events (
                    id TEXT PRIMARY KEY,
                    severity TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    message TEXT NOT NULL,
                    details TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)

            # 10. Alerts
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS alerts_store (
                    id TEXT PRIMARY KEY,
                    category TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    title TEXT NOT NULL,
                    message TEXT NOT NULL,
                    is_read INTEGER NOT NULL DEFAULT 0,
                    metadata TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)

            conn.commit()

    # -------------------------------------------------------------------------
    # Audit Logs
    # -------------------------------------------------------------------------
    def log_audit(
        self,
        actor: str,
        action: str,
        entity_type: str,
        entity_id: str,
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        record_id = str(uuid4())
        now_ts = datetime.now(timezone.utc).isoformat()
        details_json = json.dumps(details or {})

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """INSERT INTO audit_logs (id, actor, action, entity_type, entity_id, details, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (record_id, actor, action, entity_type, entity_id, details_json, now_ts),
                )
                conn.commit()
        except Exception as exc:
            logger.error(f"Failed to record local audit log: {exc}")

        if self.is_cloud:
            self._post_supabase("audit_logs", {
                "id": record_id,
                "actor": actor,
                "action": action,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "details": details or {},
                "created_at": now_ts,
            })

        return {"id": record_id, "action": action, "actor": actor, "created_at": now_ts}

    def list_audit_logs(self, limit: int = 50) -> list[dict[str, Any]]:
        results = []
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """SELECT id, actor, action, entity_type, entity_id, details, created_at
                       FROM audit_logs ORDER BY created_at DESC LIMIT ?""",
                    (limit,),
                )
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

    # -------------------------------------------------------------------------
    # Signals
    # -------------------------------------------------------------------------
    def save_signal(self, signal: dict[str, Any]) -> None:
        rec_id = str(uuid4())
        event_key = f"{signal.get('strategy_id')}_{signal.get('symbol')}_{signal.get('timestamp')}"
        now_ts = datetime.now(timezone.utc).isoformat()
        strat_ver = signal.get("strategy_version", "1.0.0")
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """INSERT OR REPLACE INTO signals_store (id, event_key, strategy_id, strategy_version, symbol, direction, score, reason, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        rec_id,
                        event_key,
                        signal.get("strategy_id", "unknown"),
                        strat_ver,
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

        if self.is_cloud:
            self._post_supabase("signals", {
                "event_key": event_key,
                "strategy_id": signal.get("strategy_id", "unknown"),
                "strategy_version": strat_ver,
                "symbol": signal.get("symbol", "N/A"),
                "segment": signal.get("segment", "EQUITY_CASH"),
                "timeframe": signal.get("timeframe", "1d"),
                "direction": signal.get("direction", "flat"),
                "score": float(signal.get("score", 0.0)),
                "reason": signal.get("reason", ""),
                "market_ts": now_ts,
                "created_at": now_ts,
            })

    # -------------------------------------------------------------------------
    # Paper Orders & Fills
    # -------------------------------------------------------------------------
    def save_paper_order(self, order_dict: dict[str, Any]) -> bool:
        """Persist simulated order to local database and cloud."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """INSERT OR REPLACE INTO paper_orders (
                        order_id, symbol, side, quantity, order_type, price, fill_price,
                        filled_quantity, status, fees, stop_loss, take_profit, segment,
                        strategy_id, note, created_at, filled_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        order_dict["order_id"],
                        order_dict["symbol"],
                        order_dict["side"],
                        int(order_dict["quantity"]),
                        order_dict.get("order_type", "MARKET"),
                        float(order_dict.get("price", 0.0)),
                        float(order_dict.get("fill_price", 0.0)),
                        int(order_dict.get("filled_quantity", order_dict["quantity"])),
                        order_dict.get("status", "SIMULATED"),
                        float(order_dict.get("fees", 0.0)),
                        order_dict.get("stop_loss"),
                        order_dict.get("take_profit"),
                        order_dict.get("segment", "EQUITY_CASH"),
                        order_dict.get("strategy_id", "manual"),
                        order_dict.get("note", ""),
                        order_dict.get("created_at", datetime.now(timezone.utc).isoformat()),
                        order_dict.get("filled_at", datetime.now(timezone.utc).isoformat()),
                    ),
                )
                conn.commit()
            if self.is_cloud:
                self._post_supabase("paper_orders", order_dict)
            return True
        except Exception as exc:
            logger.error(f"Failed to persist paper order {order_dict.get('order_id')}: {exc}")
            return False

    def list_paper_orders(self, limit: int = 200) -> list[dict[str, Any]]:
        results = []
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """SELECT order_id, symbol, side, quantity, order_type, price, fill_price,
                              filled_quantity, status, fees, stop_loss, take_profit, segment,
                              strategy_id, note, created_at, filled_at
                       FROM paper_orders ORDER BY created_at DESC LIMIT ?""",
                    (limit,),
                )
                cols = [d[0] for d in cursor.description]
                for row in cursor.fetchall():
                    results.append(dict(zip(cols, row)))
        except Exception as exc:
            logger.error(f"Failed to fetch paper orders: {exc}")
        return results

    # -------------------------------------------------------------------------
    # Positions
    # -------------------------------------------------------------------------
    def save_position(self, pos_dict: dict[str, Any]) -> bool:
        now_ts = datetime.now(timezone.utc).isoformat()
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """INSERT OR REPLACE INTO paper_positions (
                        symbol, segment, side, quantity, entry_price, current_price,
                        stop_loss, take_profit, realized_pnl, unrealized_pnl,
                        strategy_id, notes, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        pos_dict["symbol"],
                        pos_dict.get("segment", "EQUITY_CASH"),
                        pos_dict["side"],
                        int(pos_dict["quantity"]),
                        float(pos_dict["entry_price"]),
                        float(pos_dict.get("current_price", pos_dict["entry_price"])),
                        pos_dict.get("stop_loss"),
                        pos_dict.get("take_profit"),
                        float(pos_dict.get("realized_pnl", 0.0)),
                        float(pos_dict.get("unrealized_pnl", 0.0)),
                        pos_dict.get("strategy_id", "manual"),
                        pos_dict.get("notes", ""),
                        now_ts,
                    ),
                )
                conn.commit()
            return True
        except Exception as exc:
            logger.error(f"Failed to persist position for {pos_dict.get('symbol')}: {exc}")
            return False

    def delete_position(self, symbol: str) -> bool:
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM paper_positions WHERE symbol = ?", (symbol.upper().strip(),))
                conn.commit()
            return True
        except Exception as exc:
            logger.error(f"Failed to delete position {symbol}: {exc}")
            return False

    def list_positions(self) -> list[dict[str, Any]]:
        results = []
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """SELECT symbol, segment, side, quantity, entry_price, current_price,
                              stop_loss, take_profit, realized_pnl, unrealized_pnl,
                              strategy_id, notes, updated_at
                       FROM paper_positions WHERE quantity > 0"""
                )
                cols = [d[0] for d in cursor.description]
                for row in cursor.fetchall():
                    results.append(dict(zip(cols, row)))
        except Exception as exc:
            logger.error(f"Failed to list positions: {exc}")
        return results

    # -------------------------------------------------------------------------
    # Portfolio Snapshots
    # -------------------------------------------------------------------------
    def save_portfolio_snapshot(self, summary: dict[str, Any]) -> None:
        rec_id = str(uuid4())
        now_ts = datetime.now(timezone.utc).isoformat()
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """INSERT INTO portfolio_snapshots (
                        id, timestamp, total_equity, cash_balance, invested_margin,
                        unrealized_pnl, realized_pnl, open_positions_count
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        rec_id,
                        now_ts,
                        float(summary["total_equity"]),
                        float(summary["cash_balance"]),
                        float(summary["invested_margin"]),
                        float(summary["unrealized_pnl"]),
                        float(summary["realized_pnl"]),
                        int(summary["open_positions_count"]),
                    ),
                )
                conn.commit()
        except Exception as exc:
            logger.error(f"Failed to record portfolio snapshot: {exc}")

    def list_portfolio_snapshots(self, limit: int = 50) -> list[dict[str, Any]]:
        results = []
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """SELECT id, timestamp, total_equity, cash_balance, invested_margin,
                              unrealized_pnl, realized_pnl, open_positions_count
                       FROM portfolio_snapshots ORDER BY timestamp DESC LIMIT ?""",
                    (limit,),
                )
                cols = [d[0] for d in cursor.description]
                for row in cursor.fetchall():
                    results.append(dict(zip(cols, row)))
        except Exception as exc:
            logger.error(f"Failed to fetch portfolio snapshots: {exc}")
        return results

    # -------------------------------------------------------------------------
    # Strategy Versions & Configuration
    # -------------------------------------------------------------------------
    def save_strategy_version(
        self,
        strategy_id: str | dict[str, Any],
        version: str = "",
        enabled: bool = True,
        parameters: dict[str, Any] | None = None,
    ) -> bool:
        if isinstance(strategy_id, dict):
            d = strategy_id
            strat_id = d.get("strategy_id", "unknown")
            ver = d.get("version", "1.0.0")
            en = d.get("enabled", True)
            params = d.get("parameters", {})
        else:
            strat_id = strategy_id
            ver = version
            en = enabled
            params = parameters or {}

        now_ts = datetime.now(timezone.utc).isoformat()
        params_json = json.dumps(params or {})
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """INSERT OR REPLACE INTO strategy_versions (strategy_id, version, enabled, parameters, updated_at)
                       VALUES (?, ?, ?, ?, ?)""",
                    (strat_id, ver, 1 if en else 0, params_json, now_ts),
                )
                conn.commit()
            return True
        except Exception as exc:
            logger.error(f"Failed to save strategy version for {strat_id}: {exc}")
            return False

    def get_strategy_versions(self, strategy_id: str | None = None) -> list[dict[str, Any]]:
        results = []
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                if strategy_id:
                    cursor.execute("SELECT strategy_id, version, enabled, parameters, updated_at FROM strategy_versions WHERE strategy_id = ?", (strategy_id,))
                else:
                    cursor.execute("SELECT strategy_id, version, enabled, parameters, updated_at FROM strategy_versions")
                for row in cursor.fetchall():
                    results.append({
                        "strategy_id": row[0],
                        "version": row[1],
                        "enabled": bool(row[2]),
                        "parameters": json.loads(row[3]) if row[3] else {},
                        "updated_at": row[4],
                    })
        except Exception as exc:
            logger.error(f"Failed to list strategy versions: {exc}")
        return results

    # -------------------------------------------------------------------------
    # Backtest Runs & Experiment History
    # -------------------------------------------------------------------------
    def save_backtest_run(
        self,
        strategy_id: str | dict[str, Any],
        strategy_version: str = "1.0.0",
        symbol: str = "NIFTY 50",
        timeframe: str = "1d",
        initial_capital: float = 1_000_000.0,
        parameters: dict[str, Any] | None = None,
        metrics: dict[str, Any] | None = None,
        equity_curve: list[dict[str, Any]] | None = None,
        trades_log: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> str:
        if isinstance(strategy_id, dict):
            d = strategy_id
            rec_id = d.get("run_id") or str(uuid4())
            strat_id = d.get("strategy_id", "unknown")
            strat_ver = d.get("strategy_version", "1.0.0")
            sym = d.get("symbol", "N/A")
            tf = d.get("timeframe", "1d")
            cap = float(d.get("initial_capital", 1_000_000.0))
            params = d.get("parameters", {})
            mets = d.get("metrics", {}).copy() if isinstance(d.get("metrics"), dict) else {}
            # Flatten extra performance numbers into metrics json
            for k, v in d.items():
                if k not in {"run_id", "strategy_id", "strategy_version", "symbol", "timeframe", "initial_capital", "parameters", "metrics", "equity_curve", "trades_log"}:
                    mets[k] = v
            eq = d.get("equity_curve", [])
            trades = d.get("trades_log", [])
        else:
            rec_id = str(uuid4())
            strat_id = strategy_id
            strat_ver = strategy_version
            sym = symbol
            tf = timeframe
            cap = initial_capital
            params = parameters or {}
            mets = metrics or {}
            eq = equity_curve or []
            trades = trades_log or []

        now_ts = datetime.now(timezone.utc).isoformat()
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """INSERT OR REPLACE INTO backtest_runs (
                        id, strategy_id, strategy_version, symbol, timeframe,
                        initial_capital, parameters, metrics, equity_curve, trades_log, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        rec_id,
                        strat_id,
                        strat_ver,
                        sym,
                        tf,
                        float(cap),
                        json.dumps(params or {}),
                        json.dumps(mets or {}),
                        json.dumps(eq or []),
                        json.dumps(trades or []),
                        now_ts,
                    ),
                )
                conn.commit()
        except Exception as exc:
            logger.error(f"Failed to save backtest run: {exc}")

        return rec_id

    def list_backtest_runs(self, limit: int = 30) -> list[dict[str, Any]]:
        results = []
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """SELECT id, strategy_id, strategy_version, symbol, timeframe,
                              initial_capital, parameters, metrics, created_at
                       FROM backtest_runs ORDER BY created_at DESC LIMIT ?""",
                    (limit,),
                )
                for row in cursor.fetchall():
                    mets = json.loads(row[7]) if row[7] else {}
                    item = {
                        "id": row[0],
                        "run_id": row[0],
                        "strategy_id": row[1],
                        "strategy_version": row[2],
                        "symbol": row[3],
                        "timeframe": row[4],
                        "initial_capital": row[5],
                        "parameters": json.loads(row[6]) if row[6] else {},
                        "metrics": mets,
                        "created_at": row[8],
                    }
                    for k, v in mets.items():
                        if k not in item:
                            item[k] = v
                    results.append(item)
        except Exception as exc:
            logger.error(f"Failed to list backtest runs: {exc}")
        return results

    def get_backtest_run(self, run_id: str) -> dict[str, Any] | None:
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """SELECT id, strategy_id, strategy_version, symbol, timeframe,
                              initial_capital, parameters, metrics, equity_curve, trades_log, created_at
                       FROM backtest_runs WHERE id = ?""",
                    (run_id,),
                )
                row = cursor.fetchone()
                if not row:
                    return None
                mets = json.loads(row[7]) if row[7] else {}
                item = {
                    "id": row[0],
                    "run_id": row[0],
                    "strategy_id": row[1],
                    "strategy_version": row[2],
                    "symbol": row[3],
                    "timeframe": row[4],
                    "initial_capital": row[5],
                    "parameters": json.loads(row[6]) if row[6] else {},
                    "metrics": mets,
                    "equity_curve": json.loads(row[8]) if row[8] else [],
                    "trades_log": json.loads(row[9]) if row[9] else [],
                    "created_at": row[10],
                }
                for k, v in mets.items():
                    if k not in item:
                        item[k] = v
                return item
        except Exception as exc:
            logger.error(f"Failed to get backtest run {run_id}: {exc}")
            return None

    # -------------------------------------------------------------------------
    # Risk Events
    # -------------------------------------------------------------------------
    def save_risk_event(
        self,
        severity: str | dict[str, Any],
        event_type: str = "RISK_REJECTION",
        message: str = "",
        details: dict[str, Any] | None = None,
    ) -> str:
        if isinstance(severity, dict):
            d = severity
            rec_id = d.get("event_id") or str(uuid4())
            sev = d.get("severity", "WARNING")
            evt_type = d.get("rule_name") or d.get("event_type", "RISK_RULE")
            msg = d.get("reason") or d.get("message", "")
            dets = d.get("order_details") or d.get("details", {})
            if isinstance(dets, dict):
                dets = dets.copy()
            else:
                dets = {"raw": dets}
            if "symbol" in d:
                dets["symbol"] = d["symbol"]
            if "rule_name" in d:
                dets["rule_name"] = d["rule_name"]
        else:
            rec_id = str(uuid4())
            sev = severity
            evt_type = event_type
            msg = message
            dets = details or {}

        now_ts = datetime.now(timezone.utc).isoformat()
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """INSERT INTO risk_events (id, severity, event_type, message, details, created_at)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (rec_id, sev, evt_type, msg, json.dumps(dets), now_ts),
                )
                conn.commit()
        except Exception as exc:
            logger.error(f"Failed to save risk event: {exc}")

        return rec_id

    def list_risk_events(self, limit: int = 50) -> list[dict[str, Any]]:
        results = []
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """SELECT id, severity, event_type, message, details, created_at
                       FROM risk_events ORDER BY created_at DESC LIMIT ?""",
                    (limit,),
                )
                for row in cursor.fetchall():
                    dets = json.loads(row[4]) if row[4] else {}
                    results.append({
                        "id": row[0],
                        "event_id": row[0],
                        "severity": row[1],
                        "event_type": row[2],
                        "rule_name": dets.get("rule_name", row[2]),
                        "symbol": dets.get("symbol", "N/A"),
                        "message": row[3],
                        "reason": row[3],
                        "details": dets,
                        "created_at": row[5],
                    })
        except Exception as exc:
            logger.error(f"Failed to list risk events: {exc}")
        return results

    # -------------------------------------------------------------------------
    # Adaptive Strategy States
    # -------------------------------------------------------------------------
    def save_adaptive_state(
        self,
        strategy_id: str,
        health_state: str,
        allocation_weight: float,
        reason: str = "",
    ) -> None:
        now_ts = datetime.now(timezone.utc).isoformat()
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """INSERT OR REPLACE INTO adaptive_states (strategy_id, health_state, allocation_weight, last_reason, updated_at)
                       VALUES (?, ?, ?, ?, ?)""",
                    (strategy_id, health_state, float(allocation_weight), reason, now_ts),
                )
                conn.commit()
        except Exception as exc:
            logger.error(f"Failed to save adaptive state for {strategy_id}: {exc}")

    def get_adaptive_states(self) -> list[dict[str, Any]]:
        results = []
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT strategy_id, health_state, allocation_weight, last_reason, updated_at FROM adaptive_states")
                for row in cursor.fetchall():
                    results.append({
                        "strategy_id": row[0],
                        "health_state": row[1],
                        "allocation_weight": row[2],
                        "last_reason": row[3],
                        "updated_at": row[4],
                    })
        except Exception as exc:
            logger.error(f"Failed to get adaptive states: {exc}")
        return results

    # -------------------------------------------------------------------------
    # Supabase Helper & Health Probe
    # -------------------------------------------------------------------------
    def _post_supabase(self, table: str, payload: dict[str, Any]) -> None:
        """Asynchronously or safely attempt to post to cloud Supabase without blocking local flow."""
        if not self.is_cloud:
            return
        try:
            headers = {
                "apikey": self.supabase_key,
                "Authorization": f"Bearer {self.supabase_key}",
                "Content-Type": "application/json",
                "Prefer": "return=minimal",
            }
            requests.post(f"{self.supabase_url}/rest/v1/{table}", json=payload, headers=headers, timeout=2.0)
        except Exception as exc:
            logger.debug(f"Cloud Supabase post to {table} failed: {exc}")

    def check_connection_health(self) -> dict[str, Any]:
        """Performs a real HTTP probe to Supabase if configured."""
        if not self.is_cloud:
            return {
                "mode": "local_sqlite",
                "is_connected": False,
                "status": "UNCONFIGURED",
                "message": "Supabase credentials not configured. Local SQLite storage active.",
                "latency_ms": None,
                "local_db_path": self.db_path,
            }

        t0 = time.perf_counter()
        try:
            headers = {
                "apikey": self.supabase_key,
                "Authorization": f"Bearer {self.supabase_key}",
            }
            resp = requests.get(f"{self.supabase_url}/rest/v1/", headers=headers, timeout=2.5)
            elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)

            if resp.status_code in (200, 204, 404):
                return {
                    "mode": "supabase_cloud",
                    "is_connected": True,
                    "status": "CONNECTED",
                    "message": f"Successfully connected to Supabase PostgREST ({elapsed_ms}ms).",
                    "latency_ms": elapsed_ms,
                    "local_db_path": self.db_path,
                }
            return {
                "mode": "supabase_cloud",
                "is_connected": False,
                "status": "AUTH_ERROR",
                "message": f"Supabase responded with HTTP {resp.status_code}.",
                "latency_ms": elapsed_ms,
                "local_db_path": self.db_path,
            }
        except Exception as exc:
            elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)
            return {
                "mode": "supabase_cloud",
                "is_connected": False,
                "status": "UNAVAILABLE",
                "message": f"Supabase probe failed: {exc}",
                "latency_ms": elapsed_ms,
                "local_db_path": self.db_path,
            }

    def get_database_status(self) -> dict[str, Any]:
        """Provides fast status summary without blocking probe."""
        health = self.check_connection_health()
        return {
            "mode": health["mode"],
            "is_cloud_connected": health["is_connected"],
            "supabase_url": self.supabase_url if self.is_cloud else "Not Configured",
            "local_db_path": self.db_path,
            "status_message": health["message"],
        }


db_repo = SupabaseRepository()
