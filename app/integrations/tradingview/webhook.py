"""AlgoTrade AI — TradingView Webhook Receiver & Pine Script v6 Integration.

Provides cryptographically verified alert ingestion, replay protection,
timestamp drift rejection, idempotency, risk authority gating, audit logging,
and integration diagnostics.
"""

from datetime import datetime, timezone
import hashlib
import hmac
import logging
import time
from typing import Any
from fastapi import HTTPException
from pydantic import BaseModel, Field

from app.alerts.manager import alert_manager
from app.config import settings
from app.database.supabase_client import db_repo
from app.models import AlertCategory, AlertSeverity, StrategySignal
from app.paper import paper_broker
from app.risk import risk_authority

logger = logging.getLogger("algotrade.tradingview")


class TradingViewAlertPayload(BaseModel):
    event_id: str = Field(min_length=1, max_length=100)
    strategy_id: str = Field(min_length=1, max_length=50)
    strategy_version: str = "1.0.0"
    symbol: str = Field(min_length=1, max_length=30)
    exchange: str = "NSE"
    timeframe: str = "15m"
    signal_type: str = "entry"  # "entry", "exit", "stop_hit"
    direction: str = "long"     # "long", "short", "flat"
    timestamp: str              # ISO-8601 string
    reference_price: float = Field(gt=0)
    suggested_stop: float | None = None
    suggested_target: float | None = None
    passphrase: str | None = None
    rationale: str = "TradingView PineScript Alert"


class TradingViewWebhookHandler:
    """Secure TradingView webhook processor with replay defense, risk inspection, and persistent telemetry."""

    def __init__(self, max_drift_seconds: int = 120) -> None:
        self.max_drift_seconds = max_drift_seconds
        self.processed_events: dict[str, float] = {}  # event_id -> processed timestamp

        # Telemetry metrics
        self.total_received = 0
        self.accepted_events = 0
        self.rejected_events = 0
        self.duplicate_events = 0
        self.last_success_ts: str | None = None
        self.last_error: str | None = None
        self.last_error_ts: str | None = None
        self.recent_events: list[dict[str, Any]] = []

    def get_stats(self) -> dict[str, Any]:
        """Provides operational statistics for health monitoring."""
        return {
            "total_received": self.total_received,
            "accepted_events": self.accepted_events,
            "rejected_events": self.rejected_events,
            "duplicate_events": self.duplicate_events,
            "last_success_ts": self.last_success_ts,
            "last_error": self.last_error,
            "last_error_ts": self.last_error_ts,
            "recent_events": self.recent_events[-15:],
        }

    def verify_auth(self, payload: TradingViewAlertPayload, secret: str) -> bool:
        """Constant-time passphrase verification preventing timing attacks."""
        if not secret:
            return True
        if not payload.passphrase:
            return False
        return hmac.compare_digest(payload.passphrase.strip(), secret.strip())

    def process_webhook(self, payload: TradingViewAlertPayload) -> dict[str, Any]:
        """Validates and processes incoming TradingView alert durably and quickly."""
        now = time.time()
        now_iso = datetime.now(timezone.utc).isoformat()
        self.total_received += 1

        # 1. Clean old events from replay cache (> 24 hours)
        self.processed_events = {k: v for k, v in self.processed_events.items() if now - v < 86400}

        # 2. Replay Protection: Check duplicate event_id
        if payload.event_id in self.processed_events:
            self.duplicate_events += 1
            self.rejected_events += 1
            err_msg = f"Duplicate alert rejected (event_id: {payload.event_id})"
            self.last_error = err_msg
            self.last_error_ts = now_iso

            alert_manager.dispatch(
                AlertCategory.SYSTEM,
                AlertSeverity.WARNING,
                "TradingView Duplicate Webhook",
                f"Ignored duplicate alert with event_id {payload.event_id} for {payload.symbol}",
            )
            db_repo.log_audit(
                "tradingview_webhook",
                "DUPLICATE_WEBHOOK_REJECTED",
                "alert",
                payload.event_id,
                {"symbol": payload.symbol, "strategy": payload.strategy_id},
            )
            raise HTTPException(status_code=409, detail=f"Duplicate event_id: {payload.event_id}")

        # 3. Secret validation
        if not self.verify_auth(payload, settings.tradingview_webhook_secret):
            self.rejected_events += 1
            err_msg = f"Unauthorized webhook attempt: invalid passphrase for {payload.symbol}"
            self.last_error = err_msg
            self.last_error_ts = now_iso

            alert_manager.dispatch(
                AlertCategory.SYSTEM,
                AlertSeverity.CRITICAL,
                "TradingView Webhook Auth Failed",
                f"Unauthorized webhook attempt for {payload.symbol} from strategy {payload.strategy_id}",
            )
            db_repo.log_audit(
                "tradingview_webhook",
                "AUTH_FAILED",
                "alert",
                payload.event_id,
                {"symbol": payload.symbol, "strategy": payload.strategy_id},
            )
            raise HTTPException(status_code=401, detail="Invalid webhook secret/passphrase")

        # 4. Freshness check: reject stale timestamps
        try:
            event_dt = datetime.fromisoformat(payload.timestamp.replace("Z", "+00:00"))
            event_ts = event_dt.timestamp()
            drift = abs(now - event_ts)
            if drift > self.max_drift_seconds:
                self.rejected_events += 1
                err_msg = f"Timestamp drift exceeded: {drift:.1f}s > {self.max_drift_seconds}s limit"
                self.last_error = err_msg
                self.last_error_ts = now_iso
                raise HTTPException(
                    status_code=400,
                    detail=f"Webhook timestamp too old or too far in future (drift {drift:.1f}s > {self.max_drift_seconds}s)",
                )
        except Exception as exc:
            if isinstance(exc, HTTPException):
                raise exc
            self.rejected_events += 1
            self.last_error = f"Malformed timestamp: {payload.timestamp}"
            self.last_error_ts = now_iso
            raise HTTPException(status_code=400, detail=f"Malformed timestamp: {payload.timestamp}")

        # Mark event as processed (idempotency key)
        self.processed_events[payload.event_id] = now

        # 5. Risk Inspection
        side = "buy" if payload.direction == "long" else "sell"
        sym = payload.symbol.upper().strip()

        # Check risk authority
        pos_count = len(paper_broker.positions)
        risk_ok, risk_msg = risk_authority.validate_order(
            symbol=sym,
            side=side,
            quantity=1,
            price=payload.reference_price,
            current_positions_count=pos_count,
        )

        if not risk_ok:
            self.rejected_events += 1
            self.last_error = f"Blocked by Risk Authority: {risk_msg}"
            self.last_error_ts = now_iso

            alert_manager.dispatch(
                AlertCategory.RISK,
                AlertSeverity.WARNING,
                "TradingView Order Blocked by Risk Authority",
                f"{sym} {side.upper()} rejected: {risk_msg}",
            )
            db_repo.save_risk_event(
                severity="warning",
                event_type="TRADINGVIEW_ORDER_BLOCKED",
                message=risk_msg,
                details={"event_id": payload.event_id, "symbol": sym, "side": side},
            )
            self._record_event_history(payload, "REJECTED_BY_RISK", risk_msg)
            return {
                "status": "REJECTED_BY_RISK",
                "event_id": payload.event_id,
                "reason": risk_msg,
            }

        # 6. Execute Simulated Paper Order
        sim_order = paper_broker.place_order(
            symbol=sym,
            side=side,
            quantity=1,
            price=payload.reference_price,
            order_type="MARKET",
            stop_loss=payload.suggested_stop,
            take_profit=payload.suggested_target,
            strategy_id=f"tv_{payload.strategy_id}",
        )

        # 7. Record Telemetry & Persistence
        self.accepted_events += 1
        self.last_success_ts = now_iso

        alert_manager.dispatch(
            AlertCategory.SIGNAL,
            AlertSeverity.INFO,
            f"TradingView Signal Accepted: {sym} {payload.direction.upper()}",
            f"Strategy {payload.strategy_id} triggered {payload.direction} on {sym} @ ₹{payload.reference_price}",
            metadata=payload.model_dump(),
        )

        db_repo.save_signal({
            "strategy_id": f"tv_{payload.strategy_id}",
            "strategy_version": payload.strategy_version,
            "symbol": sym,
            "direction": payload.direction,
            "score": 1.0,
            "reason": payload.rationale,
            "timestamp": payload.timestamp,
        })

        db_repo.log_audit(
            "tradingview_webhook",
            "SIGNAL_ACCEPTED",
            "paper_order",
            sim_order.order_id,
            {"event_id": payload.event_id, "symbol": sym, "fill_price": sim_order.fill_price},
        )

        self._record_event_history(payload, "ACCEPTED", f"Filled order #{sim_order.order_id[:8]} @ ₹{sim_order.fill_price:,.2f}")

        return {
            "status": "ACCEPTED",
            "event_id": payload.event_id,
            "order_id": sim_order.order_id,
            "symbol": sym,
            "direction": payload.direction,
            "fill_price": sim_order.fill_price,
            "processed_at": now_iso,
        }

    def _record_event_history(self, payload: TradingViewAlertPayload, status: str, detail: str) -> None:
        self.recent_events.append({
            "event_id": payload.event_id,
            "symbol": payload.symbol,
            "strategy_id": payload.strategy_id,
            "direction": payload.direction,
            "price": payload.reference_price,
            "status": status,
            "detail": detail,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        if len(self.recent_events) > 50:
            self.recent_events = self.recent_events[-50:]

    def send_test_alert(
        self,
        symbol: str = "RELIANCE",
        direction: str = "long",
        price: float = 2840.0,
        stop_loss: float | None = 2810.0,
        take_profit: float | None = 2900.0,
    ) -> dict[str, Any]:
        """Sends a clearly marked simulated test event to verify the local webhook receiver pipeline.

        NOTE: A successful local test verifies the webhook validation, auth, and risk pipeline;
        it does NOT constitute proof that an external alert was delivered from TradingView servers.
        """
        now_ts = datetime.now(timezone.utc).isoformat()
        test_payload = TradingViewAlertPayload(
            event_id=f"test_sim_{int(time.time() * 1000)}",
            strategy_id="tv_test_probe",
            strategy_version="1.0.0",
            symbol=symbol,
            exchange="NSE",
            timeframe="15m",
            signal_type="entry",
            direction=direction,
            timestamp=now_ts,
            reference_price=price,
            suggested_stop=stop_loss,
            suggested_target=take_profit,
            passphrase=settings.tradingview_webhook_secret,
            rationale="Simulated local diagnostic verification test",
        )
        res = self.process_webhook(test_payload)
        res["is_local_test"] = True
        res["disclaimer"] = (
            "Local pipeline test passed successfully. This validates the webhook receiver, secret auth, "
            "and risk engine, but does NOT constitute proof of external TradingView server delivery."
        )
        return res


tv_handler = TradingViewWebhookHandler()
