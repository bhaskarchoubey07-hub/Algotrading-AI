import pandas as pd
import streamlit as st
from app.alerts.manager import alert_manager
from app.models import AlertCategory, AlertSeverity
from app.ui.components import render_global_header


def render_alerts_page() -> None:
    render_global_header()

    st.title("Alert & Notification Center")
    st.caption("Real-Time Event Stream • Multi-Channel Dispatch (In-App, Telegram, Email) • Acknowledgment")

    # Filter Controls
    c1, c2, c3, c4 = st.columns([1.5, 1.5, 1, 1])
    with c1:
        cat_filter = st.selectbox("Category", ["ALL", "signal", "execution", "risk", "system"])
    with c2:
        sev_filter = st.selectbox("Severity", ["ALL", "info", "warning", "critical"])
    with c3:
        unread_only = st.checkbox("Unread Only", value=False)
    with c4:
        st.metric("Unread Alerts", str(alert_manager.get_unread_count()))

    cat_arg = None if cat_filter == "ALL" else cat_filter
    sev_arg = None if sev_filter == "ALL" else sev_filter

    alerts = alert_manager.list_alerts(category=cat_arg, severity=sev_arg, unread_only=unread_only, limit=50)

    # Trigger Test Alert
    with st.expander("Dispatch Test Alert", expanded=False):
        with st.form("test_alert_form"):
            t_cat = st.selectbox("Test Category", ["signal", "execution", "risk", "system"])
            t_sev = st.selectbox("Test Severity", ["info", "warning", "critical"])
            t_title = st.text_input("Title", value="Manual Test Event")
            t_msg = st.text_area("Message", value="Testing the real-time alerting pipeline.")
            btn_send = st.form_submit_button("Send Alert")

        if btn_send:
            alert_manager.dispatch(t_cat, t_sev, t_title, t_msg)
            st.success("Test alert dispatched.")
            st.rerun()

    # Alerts Display List
    st.markdown("---")
    if alerts:
        for a in alerts:
            col_icon, col_content, col_action = st.columns([0.5, 5, 1])
            with col_icon:
                if a["severity"] == "critical":
                    st.error("🚨")
                elif a["severity"] == "warning":
                    st.warning("⚠️")
                else:
                    st.info("ℹ️")

            with col_content:
                ack_badge = "✅ Read" if a["acknowledged"] else "🔴 Unread"
                st.markdown(
                    f"**{a['title']}** `{a['category'].upper()}` • `{ack_badge}` • *{a['timestamp'][:19]}*"
                )
                st.write(a["message"])
                if a.get("metadata"):
                    st.caption(f"Details: {a['metadata']}")

            with col_action:
                if not a["acknowledged"]:
                    if st.button("Acknowledge", key=f"ack_{a['alert_id']}"):
                        alert_manager.acknowledge(a["alert_id"])
                        st.rerun()

            st.divider()
    else:
        st.info("No alerts match the selected criteria.")
