import pandas as pd
import streamlit as st
from app.alerts.manager import alert_manager
from app.models import AlertCategory, AlertSeverity
from app.risk import risk_authority


def render_risk_page() -> None:
    st.title("Central Risk Authority — Safety & Guardrails")
    st.caption("Pre-Trade Risk Inspection • Peak Drawdown Circuit Breakers • Emergency Kill Switch")

    snap = risk_authority.get_risk_snapshot()

    # Emergency Kill Switch Section
    st.markdown("### Emergency System Kill-Switch")
    k_col1, k_col2 = st.columns([3, 1])
    with k_col1:
        if snap["kill_switch_active"]:
            st.error("🚨 EMERGENCY KILL SWITCH IS ACTIVE: All new orders and executions are strictly BLOCKED.")
        else:
            st.success("🛡️ Risk Authority is ARMED and operating normally.")
    with k_col2:
        if snap["kill_switch_active"]:
            if st.button("RESET KILL-SWITCH", type="primary"):
                risk_authority.reset_kill_switch()
                st.success("Kill switch reset.")
                st.rerun()
        else:
            if st.button("TRIP KILL-SWITCH (HALT TRADING)", type="primary"):
                risk_authority.trip_kill_switch("Manual emergency stop from Risk Center UI")
                alert_manager.dispatch(AlertCategory.RISK, AlertSeverity.CRITICAL, "Emergency Kill Switch Activated", "All new order flow halted immediately.")
                st.rerun()

    st.markdown("---")

    # Risk Metrics Gauges
    st.subheader("Financial Exposure & Limits Tracking")
    r1, r2, r3, r4 = st.columns(4)
    with r1:
        dd = snap["drawdown_pct"] * 100.0
        st.metric(
            "Current Drawdown",
            f"{dd:.2f}%",
            delta=f"Limit: {snap['max_drawdown_limit'] * 100:.1f}%",
            delta_color="inverse",
        )
    with r2:
        daily_loss = snap["daily_loss_pct"] * 100.0
        st.metric(
            "Daily Portfolio Loss",
            f"{daily_loss:.2f}%",
            delta=f"Limit: {snap['max_daily_loss_limit'] * 100:.1f}%",
            delta_color="inverse",
        )
    with r3:
        st.metric("Max Open Positions", f"{snap['max_open_positions']}")
    with r4:
        st.metric("Risk Budget / Trade", f"{risk_authority.config.risk_fraction * 100:.2f}%")

    # Guardrails Table
    st.subheader("Configured Production Guardrails")
    guardrails_data = [
        {"Rule": "Per-Trade Risk Budget", "Value": f"{risk_authority.config.risk_fraction * 100:.2f}%", "Enforcement": "STRICT PRE-TRADE"},
        {"Rule": "Max Single Position Value", "Value": f"{risk_authority.config.max_position_value_fraction * 100:.1f}%", "Enforcement": "STRICT PRE-TRADE"},
        {"Rule": "Max Daily Loss Circuit Breaker", "Value": f"{risk_authority.config.max_daily_loss_fraction * 100:.1f}%", "Enforcement": "HALT SYSTEM"},
        {"Rule": "Max Peak-to-Trough Drawdown", "Value": f"{risk_authority.config.max_drawdown_fraction * 100:.1f}%", "Enforcement": "HALT SYSTEM"},
        {"Rule": "NSE Regular Market Hours", "Value": "09:15 - 15:30 IST", "Enforcement": "PRE-TRADE SESSION CHECK"},
        {"Rule": "Tick Size Precision", "Value": "₹0.05", "Enforcement": "ROUND TO VALID TICK"},
        {"Rule": "Lot Size Multiples", "Value": "Valid Contract Multiples", "Enforcement": "LOT VALIDATION"},
    ]
    st.dataframe(pd.DataFrame(guardrails_data), use_container_width=True, hide_index=True)

    # Risk Event Log
    st.subheader("Historical Risk Events Log")
    if risk_authority.events:
        rev_data = [e.to_dict() for e in risk_authority.events]
        st.dataframe(pd.DataFrame(rev_data), use_container_width=True)
    else:
        st.info("No risk limit breach events recorded.")
