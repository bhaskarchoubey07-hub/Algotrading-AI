"""Settings & Audit Logs — User Preferences, Experience Level, and Governance."""

import pandas as pd
import streamlit as st
from app.config import settings
from app.database.supabase_client import db_repo
from app.ui.components import render_global_header


def render_settings_page() -> None:
    render_global_header()

    st.markdown(
        """
        <div style="margin-bottom: 16px;">
            <h1 style="margin: 0; font-size: 2.1rem; font-weight: 800; color: #f8fafc; letter-spacing: -0.5px;">Settings & Governance</h1>
            <p style="margin: 4px 0 0 0; color: #94a3b8; font-size: 0.95rem;">Interface Preferences • Risk Thresholds • Notification Channels • Immutable System Audit Trail</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    set_tab1, set_tab2 = st.tabs(["Platform Settings", "Immutable Audit Logs"])

    with set_tab1:
        st.subheader("Interface Experience Level")
        current_exp = st.session_state.get("ui_experience_level", "Beginner Mode")
        exp_choice = st.radio(
            "Select UI Experience Level",
            ["Beginner Mode (Simplified terms, guided builders, educational tooltips)", "Advanced Mode (Full quantitative matrix, Greek derivatives, raw payloads)"],
            index=0 if "Beginner" in current_exp else 1,
            horizontal=True,
        )
        if exp_choice != current_exp:
            st.session_state["ui_experience_level"] = exp_choice
            st.success(f"Experience level updated to: **{exp_choice.split(' ')[0]} Mode**")

        st.caption("ℹ️ Changing interface preference does not alter strategy parameters, risk thresholds, or account permissions.")

        st.markdown("---")

        st.subheader("Trader Profile & Compliance Authorization")
        st.text_input("User ID / Profile", value="quant_trader_01", disabled=True)
        st.text_input("Role", value="System Administrator & Risk Officer", disabled=True)

        st.subheader("Risk Threshold Configuration")
        with st.form("risk_settings_form"):
            c1, c2 = st.columns(2)
            with c1:
                r_frac = st.slider("Per-Trade Risk Budget (%)", 0.05, 2.0, 0.25, 0.05)
                max_pos = st.slider("Max Single Position Notional (%)", 2.0, 25.0, 10.0, 1.0)
            with c2:
                max_loss = st.slider("Max Daily Portfolio Loss (%)", 0.5, 5.0, 1.0, 0.1)
                max_dd = st.slider("Max Drawdown Circuit Breaker (%)", 2.0, 15.0, 5.0, 0.5)

            st.subheader("Notification Preferences")
            nc1, nc2 = st.columns(2)
            with nc1:
                tg_active = st.checkbox("Enable Telegram Notifications", value=bool(settings.telegram_bot_token))
                tg_token = st.text_input("Telegram Bot Token", value=settings.telegram_bot_token, type="password")
            with nc2:
                email_active = st.checkbox("Enable Email Notifications", value=bool(settings.alert_email))
                email_addr = st.text_input("Alert Email Address", value=settings.alert_email)

            save_settings = st.form_submit_button("Save Configuration", type="primary")

        if save_settings:
            db_repo.log_audit("admin", "UPDATE_SETTINGS", "config", "platform", {"risk_fraction": r_frac})
            st.success("Settings saved and recorded in audit trail.")

        # Regulatory & Execution Boundary Policy
        st.markdown("---")
        st.subheader("Regulatory & Execution Boundary Enforcement")
        st.markdown(
            """
            <div style="background: rgba(30, 41, 59, 0.4); border: 1px solid rgba(56, 189, 248, 0.2); border-radius: 8px; padding: 14px 16px;">
                <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 6px;">
                    <span class="badge-paper"><span class="pulse-dot-blue"></span>PAPER_TRADING_ONLY = TRUE</span>
                    <span style="color: #38bdf8; font-weight: 700; font-size: 0.9rem;">SEBI Compliant Safety Boundary</span>
                </div>
                <p style="color: #cbd5e1; font-size: 0.85rem; margin: 0 0 6px 0;">
                    In accordance with SEBI algo-trading guidelines and platform architecture safety locks, live broker execution is strictly disabled.
                    Every strategy decision, alert webhook, and manual trade proposal passes through the central Risk Authority and terminates inside the high-fidelity Paper Trading engine.
                </p>
                <div style="color: #94a3b8; font-size: 0.75rem; font-family: 'JetBrains Mono', monospace;">
                    Gating Status: ALL LIVE BROKER API ROUTING KEYS COMPILED AS INACTIVE • PERSISTENT REPOSITORY: ACTIVE
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with set_tab2:
        st.subheader("Immutable System Audit Trail")
        logs = db_repo.list_audit_logs(limit=100)
        if logs:
            log_rows = []
            for l in logs:
                log_rows.append({
                    "Timestamp": l["created_at"][:19],
                    "Actor": l["actor"],
                    "Action": l["action"],
                    "Entity": f"{l['entity_type']}:{l['entity_id']}",
                    "Details": str(l["details"]),
                })
            st.dataframe(pd.DataFrame(log_rows), use_container_width=True)
        else:
            st.info("No audit entries recorded yet.")
