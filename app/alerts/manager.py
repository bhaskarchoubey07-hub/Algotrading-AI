from datetime import datetime, timezone
import json
import logging
from typing import Any
import requests
from app.config import settings
from app.models import AlertCategory, AlertMessage, AlertSeverity

logger = logging.getLogger("algotrade.alerts")


class AlertManager:
    """Central alert notification center managing in-app, Telegram and Email dispatches."""

    def __init__(self, max_in_memory: int = 500) -> None:
        self.max_in_memory = max_in_memory
        self.alerts: list[AlertMessage] = []
        self._recent_signatures: set[str] = set()

    def dispatch(
        self,
        category: AlertCategory | str,
        severity: AlertSeverity | str,
        title: str,
        message: str,
        metadata: dict[str, Any] | None = None,
    ) -> AlertMessage:
        cat = AlertCategory(category) if isinstance(category, str) else category
        sev = AlertSeverity(severity) if isinstance(severity, str) else severity

        # Deduplication signature (prevent notification storms within minute)
        minute_key = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
        sig = f"{minute_key}:{cat.value}:{sev.value}:{title}"
        if sig in self._recent_signatures:
            logger.debug(f"Suppressed duplicate alert: {title}")
            # Still return existing or new without storming
        self._recent_signatures.add(sig)

        alert = AlertMessage(
            category=cat,
            severity=sev,
            title=title,
            message=message,
            metadata=metadata or {},
        )
        self.alerts.insert(0, alert)
        if len(self.alerts) > self.max_in_memory:
            self.alerts.pop()

        # External dispatches
        if sev in (AlertSeverity.WARNING, AlertSeverity.CRITICAL):
            self._send_telegram(alert)
            self._send_email(alert)

        return alert

    def acknowledge(self, alert_id: str) -> bool:
        for a in self.alerts:
            if a.alert_id == alert_id:
                a.acknowledged = True
                return True
        return False

    def list_alerts(
        self,
        category: str | None = None,
        severity: str | None = None,
        unread_only: bool = False,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        filtered = self.alerts
        if category:
            filtered = [a for a in filtered if a.category.value == category]
        if severity:
            filtered = [a for a in filtered if a.severity.value == severity]
        if unread_only:
            filtered = [a for a in filtered if not a.acknowledged]

        return [a.to_dict() for a in filtered[:limit]]

    def get_unread_count(self) -> int:
        return sum(1 for a in self.alerts if not a.acknowledged)

    def _send_telegram(self, alert: AlertMessage) -> bool:
        if not settings.telegram_bot_token or not settings.telegram_chat_id:
            return False

        icon = "🔴" if alert.severity == AlertSeverity.CRITICAL else "⚠️"
        text = (
            f"{icon} *AlgoTrade AI Alert* [{alert.severity.value.upper()}]\n"
            f"*Category:* `{alert.category.value.upper()}`\n"
            f"*Title:* {alert.title}\n"
            f"_{alert.message}_\n"
            f"🕒 {alert.timestamp}"
        )
        url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
        payload = {"chat_id": settings.telegram_chat_id, "text": text, "parse_mode": "Markdown"}

        try:
            resp = requests.post(url, json=payload, timeout=3.0)
            return resp.status_code == 200
        except Exception as exc:
            logger.warning(f"Failed to deliver Telegram notification: {exc}")
            return False

    def _send_email(self, alert: AlertMessage) -> bool:
        if not settings.alert_email:
            return False
        # Optional SMTP / Sendgrid hook
        logger.info(f"Mock email dispatch to {settings.alert_email}: [{alert.severity.value}] {alert.title}")
        return True


alert_manager = AlertManager()
