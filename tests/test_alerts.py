import pytest
from app.alerts.manager import AlertManager
from app.models import AlertCategory, AlertSeverity


def test_alert_manager_dispatch():
    mgr = AlertManager()
    alert = mgr.dispatch(
        category=AlertCategory.SIGNAL,
        severity=AlertSeverity.INFO,
        title="Signal Generated",
        message="EMA trend strategy triggered long",
    )
    assert alert.alert_id is not None
    assert alert.category == AlertCategory.SIGNAL
    assert not alert.acknowledged


def test_alert_manager_filtering():
    mgr = AlertManager()
    mgr.dispatch(AlertCategory.RISK, AlertSeverity.CRITICAL, "Drawdown Alert", "Drawdown limit reached")
    mgr.dispatch(AlertCategory.EXECUTION, AlertSeverity.INFO, "Order Filled", "Order 123 filled")

    risk_alerts = mgr.list_alerts(category="risk")
    assert len(risk_alerts) == 1
    assert risk_alerts[0]["title"] == "Drawdown Alert"

    crit_alerts = mgr.list_alerts(severity="critical")
    assert len(crit_alerts) == 1


def test_alert_acknowledgment():
    mgr = AlertManager()
    alert = mgr.dispatch(AlertCategory.SYSTEM, AlertSeverity.WARNING, "Connection Lost", "Retrying...")
    assert mgr.get_unread_count() >= 1

    ok = mgr.acknowledge(alert.alert_id)
    assert ok
    unread = mgr.list_alerts(unread_only=True)
    assert not any(a["alert_id"] == alert.alert_id for a in unread)
