from datetime import datetime, timezone
import requests
import streamlit as st
from app.config import settings
from app.database.supabase_client import db_repo
from app.integrations.dhan.client import dhan_broker


def render_integrations_page() -> None:
    st.title("Integrations Center — Broker, Webhooks & Database")
    st.caption("TradingView Alerts • DhanHQ OpenAPI v2 • Supabase PostgreSQL Cloud")

    int_tab1, int_tab2, int_tab3 = st.tabs(["TradingView Webhook", "DhanHQ Broker", "Supabase Cloud Database"])

    # TAB 1: TRADINGVIEW
    with int_tab1:
        st.subheader("TradingView Webhook Receiver Configuration")
        st.markdown(
            """
            Connect your TradingView PineScript alerts directly to AlgoTrade AI.
            - **Webhook URL:** `https://your-domain.com/webhooks/tradingview`
            - **HTTP Method:** `POST`
            - **Content-Type:** `application/json`
            """
        )
        st.text_input("Webhook Passphrase / Secret", value=settings.tradingview_webhook_secret, type="password")

        st.subheader("Test Webhook Dispatch Simulator")
        with st.form("tv_sim_form"):
            tv_sym = st.selectbox("Symbol", ["RELIANCE", "TCS", "NIFTY 50"])
            tv_dir = st.selectbox("Direction", ["long", "short"])
            tv_price = st.number_input("Reference Price (₹)", value=2840.0, step=1.0)
            tv_stop = st.number_input("Stop Loss (₹)", value=2780.0, step=1.0)
            tv_target = st.number_input("Target Price (₹)", value=2960.0, step=1.0)
            tv_pass = st.text_input("Passphrase", value=settings.tradingview_webhook_secret)

            tv_submit = st.form_submit_button("Simulate TradingView Alert Post")

        if tv_submit:
            payload = {
                "event_id": f"TV_TEST_{int(datetime.now().timestamp())}",
                "strategy_id": "pinescript_breakout",
                "strategy_version": "1.0.0",
                "symbol": tv_sym,
                "exchange": "NSE",
                "timeframe": "15m",
                "signal_type": "entry",
                "direction": tv_dir,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "reference_price": tv_price,
                "suggested_stop": tv_stop,
                "suggested_target": tv_target,
                "passphrase": tv_pass,
                "rationale": "TradingView simulated signal test",
            }
            try:
                from app.integrations.tradingview.webhook import TradingViewAlertPayload, tv_handler
                res = tv_handler.process_webhook(TradingViewAlertPayload(**payload))
                st.success(f"Webhook Accepted! Result: {res}")
            except Exception as exc:
                st.error(f"Webhook Rejected: {exc}")

    # TAB 2: DHANHQ
    with int_tab2:
        st.subheader("DhanHQ OpenAPI v2 Broker Connection")
        d_status = dhan_broker.get_connection_status()

        dc1, dc2 = st.columns(2)
        with dc1:
            st.markdown(f"**Connection Mode:** `{'LIVE CONNECTED' if d_status['is_connected'] else 'SANDBOX SIMULATED'}`")
            st.markdown(f"**Client ID Configured:** `{d_status['client_id_configured']}`")
            st.markdown(f"**Access Token Configured:** `{d_status['access_token_configured']}`")
        with dc2:
            funds = dhan_broker.get_fund_limits()
            st.metric("Dhan Available Cash", f"₹{funds.available_cash:,.2f}")
            st.metric("Dhan Utilized Margin", f"₹{funds.margin_utilized:,.2f}")

        st.info("ℹ️ Live order execution is guarded by the compliance safety gate. Real orders are not sent to exchange without explicit token activation.")

    # TAB 3: SUPABASE
    with int_tab3:
        st.subheader("Supabase PostgreSQL Persistence & Migrations")
        db_stat = db_repo.get_database_status()

        sc1, sc2 = st.columns(2)
        with sc1:
            st.markdown(f"**Active Mode:** `{db_stat['mode'].upper()}`")
            st.markdown(f"**Local SQLite Storage:** `{db_stat['local_db_path']}`")
        with sc2:
            st.markdown(f"**Supabase Cloud URL:** `{db_stat['supabase_url']}`")
            st.markdown(f"**Cloud Sync Active:** `{db_stat['is_cloud_connected']}`")

        st.subheader("Versioned SQL Migrations")
        st.code(
            """
            -- Run migrations in Supabase SQL editor:
            sql/migrations/001_core_schema.sql
            sql/migrations/002_platform_tables.sql
            sql/migrations/003_row_level_security.sql
            """,
            language="sql",
        )
