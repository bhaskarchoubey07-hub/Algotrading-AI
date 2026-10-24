"""Central Risk Authority — Safety, Exposure Caps & Kill Switch."""

import pandas as pd
import streamlit as st
from app.alerts.manager import alert_manager
from app.models import AlertCategory, AlertSeverity
from app.risk import risk_authority
from app.ui.components import render_global_header


def render_risk_page() -> None:
    render_global_header()

    st.markdown(
        """
        <div style="margin-bottom: 16px;">
            <h1 style="margin: 0; font-size: 2.1rem; font-weight: 800; color: #f8fafc; letter-spacing: -0.5px;">Central Risk Authority</h1>
            <p style="margin: 4px 0 0 0; color: #94a3b8; font-size: 0.95rem;">Pre-Trade Risk Inspection • Peak Drawdown Circuit Breakers • Emergency Kill Switch</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    snap = risk_authority.get_risk_snapshot()

    # Emergency Kill Switch Section
    st.markdown("### 🚨 Emergency Trading Kill-Switch")
    k_col1, k_col2 = st.columns([2.5, 1.5])
    with k_col1:
        if snap["kill_switch_active"]:
            st.error("🚨 EMERGENCY KILL SWITCH IS ACTIVE: All new orders and executions are strictly BLOCKED across the platform.")
        else:
            st.success("🛡️ Risk Authority is ARMED and operating normally. All proposed strategy orders pass through pre-trade inspection.")
    with k_col2:
        if snap["kill_switch_active"]:
            if st.button("RESET KILL-SWITCH", type="primary", use_container_width=True):
                risk_authority.reset_kill_switch()
                st.success("Kill switch reset. Normal operations resumed.")
                st.rerun()
        else:
            if st.button("TRIP KILL-SWITCH (HALT TRADING)", type="primary", use_container_width=True):
                risk_authority.trip_kill_switch("Manual emergency stop from Risk Center UI")
                alert_manager.dispatch(
                    AlertCategory.RISK,
                    AlertSeverity.CRITICAL,
                    "Emergency Kill Switch Activated",
                    "All new order flow halted immediately by user.",
                )
                st.rerun()

    st.markdown("---")

    # Risk Metrics Gauges
    st.subheader("Financial Exposure & Limit Tracking")
    r1, r2, r3, r4 = st.columns(4)
    with r1:
        dd = snap["drawdown_pct"] * 100.0
        st.metric(
            "Current Drawdown",
            f"{dd:.2f}%",
            delta=f"Limit: {snap['max_drawdown_limit'] * 100:.1f}%",
            delta_color="inverse",
            help="Peak-to-trough decline. System automatically halts if limit is reached.",
        )
    with r2:
        daily_loss = snap["daily_loss_pct"] * 100.0
        st.metric(
            "Daily Portfolio Loss",
            f"{daily_loss:.2f}%",
            delta=f"Limit: {snap['max_daily_loss_limit'] * 100:.1f}%",
            delta_color="inverse",
            help="Rolling 24h loss. Hard circuit breaker prevents further trading.",
        )
    with r3:
        st.metric("Max Open Positions", f"{snap['max_open_positions']}", help="Maximum allowed concurrent open market positions.")
    with r4:
        st.metric("Risk Budget / Trade", f"{risk_authority.config.risk_fraction * 100:.2f}%", help="Per-trade risk allocation budget.")

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
        {"Rule": "Market Data Staleness", "Value": "< 60 seconds", "Enforcement": "REJECT STALE TRADES"},
    ]
    st.dataframe(pd.DataFrame(guardrails_data), use_container_width=True, hide_index=True)
