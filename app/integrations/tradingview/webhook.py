from datetime import datetime, timezone
import hashlib
import hmac
import time
from typing import Any
from fastapi import HTTPException
from pydantic import BaseModel, Field
from app.alerts.manager import alert_manager
from app.config import settings
from app.models import AlertCategory, AlertSeverity, StrategySignal
from app.paper import paper_broker
from app.risk import risk_authority


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
    """Secure TradingView webhook processor with replay defense and risk inspection."""

    def __init__(self, max_drift_seconds: int = 120) -> None:
        self.max_drift_seconds = max_drift_seconds
        self.processed_events: dict[str, float] = {}  # event_id -> processed timestamp

    def verify_auth(self, payload: TradingViewAlertPayload, secret: str) -> bool:
        if not secret:
            return True
        if payload.passphrase and payload.passphrase == secret:
            return True
        return False

    def process_webhook(self, payload: TradingViewAlertPayload) -> dict[str, Any]:
        now = time.time()

        # 1. Clean old events from replay cache (> 24 hours)
        self.processed_events = {k: v for k, v in self.processed_events.items() if now - v < 86400}

        # 2. Replay Protection: Check duplicate event_id
        if payload.event_id in self.processed_events:
            alert_manager.dispatch(
                AlertCategory.SYSTEM,
                AlertSeverity.WARNING,
                "TradingView Duplicate Webhook",
                f"Ignored duplicate alert with event_id {payload.event_id} for {payload.symbol}",
            )
            raise HTTPException(status_code=409, detail=f"Duplicate event_id: {payload.event_id}")

        # 3. Secret validation
        if not self.verify_auth(payload, settings.tradingview_webhook_secret):
            alert_manager.dispatch(
                AlertCategory.SYSTEM,
                AlertSeverity.CRITICAL,
                "TradingView Webhook Auth Failed",
                f"Unauthorized webhook attempt for {payload.symbol} from strategy {payload.strategy_id}",
            )
            raise HTTPException(status_code=401, detail="Invalid webhook secret/passphrase")

        # 4. Freshness check: reject stale timestamps
        try:
            event_dt = datetime.fromisoformat(payload.timestamp.replace("Z", "+00:00"))
            event_ts = event_dt.timestamp()
            drift = abs(now - event_ts)
            if drift > self.max_drift_seconds:
                raise HTTPException(
                    status_code=400,
                    detail=f"Webhook timestamp too old or too far in future (drift {drift:.1f}s > {self.max_drift_seconds}s)",
                )
        except Exception as exc:
            if isinstance(exc, HTTPException):
                raise exc
            raise HTTPException(status_code=400, detail=f"Malformed timestamp: {payload.timestamp}")

        # Mark event as processed
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
            alert_manager.dispatch(
                AlertCategory.RISK,
                AlertSeverity.WARNING,
                f"TradingView Order Blocked by Risk Authority",
                f"{sym} {side.upper()} rejected: {risk_msg}",
            )
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

        alert_manager.dispatch(
            AlertCategory.SIGNAL,
            AlertSeverity.INFO,
            f"TradingView Signal Accepted: {sym} {payload.direction.upper()}",
            f"Strategy {payload.strategy_id} triggered {payload.direction} on {sym} @ ₹{payload.reference_price}",
            metadata=payload.model_dump(),
        )

        return {
            "status": "ACCEPTED",
            "event_id": payload.event_id,
            "order_id": sim_order.order_id,
            "symbol": sym,
            "direction": payload.direction,
            "fill_price": sim_order.fill_price,
        }


tv_handler = TradingViewWebhookHandler()
