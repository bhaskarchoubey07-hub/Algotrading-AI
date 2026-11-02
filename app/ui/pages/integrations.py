"""Integrations Dashboard — TradingView Webhooks, DhanHQ OpenAPI, Supabase DB."""

import json
from datetime import datetime, timezone
import pandas as pd
import streamlit as st
from app.brokers.dhan import (
    DhanClient,
    dhan_broker,
    instrument_manager,
)
from app.config import settings
from app.database import db_repo


from app.ui.components import render_global_header
from app.integrations.tradingview.webhook import tv_handler, TradingViewAlertPayload


def render_integrations_page() -> None:
    render_global_header()
    st.title("Integration Hub & Broker Connectivity")
    st.caption("TradingView Webhooks • DhanHQ Broker Adapter • Supabase PostgreSQL Sync")

    int_tab1, int_tab2, int_tab3 = st.tabs(["TradingView Webhook & Alerts", "DhanHQ Broker API & Market Data", "Supabase Database & Storage"])

    # TAB 1: TRADINGVIEW
    with int_tab1:
        st.subheader("TradingView Webhook Receiver & Alert Pipeline")
        st.markdown(
            """
            AlgoTrade AI receives and cryptographically authenticates TradingView alerts via an HTTPS webhook listener.
            Alerts pass through anti-replay deduplication, timestamp drift validation, and central risk checks before reaching the paper broker.
            """
        )

        masked_secret = f"{settings.tradingview_webhook_secret[:3]}****{settings.tradingview_webhook_secret[-2:]}" if len(settings.tradingview_webhook_secret) > 5 else "****"
        st.code(
            f"""
Webhook Endpoint: /integrations/tradingview/webhook
Authentication Header / Secret: {masked_secret}
Replay Window: 60s
Duplicate Prevention: Cache + DB Store
            """,
            language="text",
        )

        st.markdown("#### Webhook Operational Telemetry")
        tv_stats = tv_handler.get_stats()
        tv_c1, tv_c2, tv_c3, tv_c4 = st.columns(4)
        tv_c1.metric("Total Received", tv_stats["total_received"])
        tv_c2.metric("Accepted Events", tv_stats["accepted_events"])
        tv_c3.metric("Rejected Events", tv_stats["rejected_events"])
        tv_c4.metric("Duplicates Filtered", tv_stats["duplicate_events"])

        if tv_stats["last_success_ts"]:
            st.caption(f"Last successful alert processed: `{tv_stats['last_success_ts']}`")
        if tv_stats["last_error"]:
            st.warning(f"Last recorded error: `{tv_stats['last_error']}`")

        st.markdown("---")
        st.subheader("Simulated Test Alert Dispatcher")
        st.info("ℹ️ **Notice:** This test dispatches an in-process diagnostic event through the full validation, risk check, and audit pipeline. It tests parser correctness and risk rejection rules; it does **not** prove TradingView's cloud delivery.")

        with st.form("tv_test_form"):
            tv_sym = st.selectbox("Symbol", ["RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK"])
            tv_side = st.selectbox("Direction", ["long", "short"])
            tv_price = st.number_input("Reference Price (₹)", value=2840.0)
            tv_stop = st.number_input("Suggested Stop Loss (₹)", value=2810.0)
            tv_target = st.number_input("Suggested Take Profit (₹)", value=2900.0)
            tv_pass = st.text_input("Webhook Passphrase", value=settings.tradingview_webhook_secret, type="password")
            submit_tv = st.form_submit_button("Send Diagnostic Test Alert", type="primary")

        if submit_tv:
            payload = {
                "event_id": f"tv_manual_{int(datetime.now().timestamp())}",
                "strategy_id": "tv_trend",
                "symbol": tv_sym,
                "direction": tv_side,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "reference_price": tv_price,
                "suggested_stop": tv_stop,
                "suggested_target": tv_target,
                "passphrase": tv_pass,
                "rationale": "TradingView manual test alert",
            }
            res = tv_handler.send_test_alert(payload)
            if res.get("status") == "accepted":
                st.success(f"Alert Accepted by Pipeline! Event ID: `{res.get('event_id')}`. Order ID: `{res.get('order_id')}`")
            else:
                st.error(f"Alert Rejected: Reason: `{res.get('reason')}`")

    # TAB 2: DHANHQ
    with int_tab2:
        st.subheader("Official DhanHQ Python SDK (v2.3.0) Integration")
        d_status = dhan_broker.get_connection_status()
        client = getattr(dhan_broker, "client", None) or DhanClient()
        cred_status = client.auth.get_credential_status()

        col_st1, col_st2, col_st3 = st.columns(3)
        with col_st1:
            st.metric("Connection Mode", "LIVE CONNECTED" if d_status["is_connected"] else "SANDBOX SIMULATED")
        with col_st2:
            st.metric("Client ID", cred_status.client_id_masked)
        with col_st3:
            st.metric("Live Gate Status", "CLOSED (PAPER_ONLY)" if d_status["live_gate_closed"] else "OPEN")

        st.info("🛡️ **Safety Policy:** `PAPER_TRADING_ONLY` is hard-enforced. Real order submission to exchange is strictly gated in simulation mode.")

        st.markdown("---")
        # Sub-tabs for DhanHQ capabilities
        dhan_sub1, dhan_sub2, dhan_sub3, dhan_sub4, dhan_sub5 = st.tabs([
            "Funds & Portfolio",
            "Live Quotes & Staleness",
            "Market Data Verification",
            "Instrument Master",
            "Option Chains & Greeks",
        ])

        with dhan_sub1:
            st.markdown("#### Real-Time Margins & Ledger")
            funds = dhan_broker.get_fund_limits()
            f1, f2, f3, f4 = st.columns(4)
            f1.metric("Available Cash", f"₹{funds.available_cash:,.2f}")
            f2.metric("Collateral Amount", f"₹{funds.collateral_amount:,.2f}")
            f3.metric("Utilized Margin", f"₹{funds.margin_utilized:,.2f}")
            f4.metric("Net Account Equity", f"₹{funds.net_equity:,.2f}")

            st.markdown("#### Open Broker Positions")
            positions = dhan_broker.get_positions()
            if positions:
                st.dataframe(pd.DataFrame(positions), use_container_width=True)
            else:
                st.info("No open positions reported by broker.")

            st.markdown("#### Demat Holdings")
            holdings = dhan_broker.get_holdings()
            if holdings:
                st.dataframe(pd.DataFrame(holdings), use_container_width=True)
            else:
                st.info("No holdings reported by broker.")

        with dhan_sub2:
            st.markdown("#### Real-Time Quote & Data Freshness Inspector")
            q_col1, q_col2 = st.columns([2, 1])
            with q_col1:
                q_sym = st.selectbox("Inspect Symbol Quote", ["RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK", "NIFTY", "BANKNIFTY"])
            with q_col2:
                q_seg = st.selectbox("Exchange Segment", ["NSE_EQ", "IDX_I", "NSE_FNO"])

            if st.button("Fetch Live Normalized Quote", type="primary"):
                quote = client.market_data.get_quote(q_sym, exchange_segment=q_seg, force_fresh=True)
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Last Traded Price", f"₹{quote.last_price:,.2f}")
                m2.metric("Day High / Low", f"₹{quote.high_price:,.2f} / ₹{quote.low_price:,.2f}")
                m3.metric("Volume", f"{quote.volume:,}")
                m4.metric("Stale Flag", "STALE ⚠️" if quote.is_stale else "FRESH ✅")
                st.json(quote.to_dict())

        with dhan_sub3:
            st.markdown("#### Official Market-Data Connectivity & Schema Verification Test")
            st.markdown("Runs an end-to-end integration test validating authentication, quote retrieval, historical candle schema, and timestamp freshness.")
            test_sym = st.selectbox("Verification Test Symbol", ["RELIANCE", "INFY", "TCS"], key="dhan_test_sym")
            if st.button("Execute Verification Suite", type="primary"):
                with st.spinner("Executing DhanHQ Market Data Verification..."):
                    diag = client.market_data.verify_connectivity(test_sym)
                if diag["overall_status"] == "PASSED":
                    st.success(f"Verification PASSED! Data Source: `{diag['data_source']}` • Latency: `{diag['latency_ms']:.1f}ms`")
                elif diag["overall_status"] == "MOCK_VALIDATED":
                    st.info(f"Mock/Sandbox Environment Verified: `{diag['overall_status']}` • Schema Valid: `{diag['schema_valid']}`")
                else:
                    st.error(f"Verification Failed: {diag['errors']}")
                st.json(diag)

        with dhan_sub4:
            st.markdown("#### Scrip Master & Security Identifier Resolution")
            summary = instrument_manager.get_summary()
            st.write(f"**Loaded Instruments:** {summary['total_instruments']:,}")
            st.write(f"**Indices Sample:** {', '.join(summary['sample_indices'])}")

            search_sym = st.text_input("Test Symbol Resolution (e.g. RELIANCE, INFY, NIFTY):", value="RELIANCE")
            if search_sym:
                try:
                    sec_id = instrument_manager.resolve_security_id(search_sym)
                    st.success(f"Resolved **{search_sym.upper()}** -> Security ID: `{sec_id}` (Segment: NSE_EQ)")
                except Exception as err:
                    st.error(f"Resolution failed: {err}")

        with dhan_sub5:
            st.markdown("#### Real-Time Derivatives Option Chain & Greeks")
            opt_sym = st.selectbox("Underlying Index", ["NIFTY", "BANKNIFTY"], index=0)
            expiries = client.options.get_expiry_list(opt_sym)
            sel_exp = st.selectbox("Contract Expiry", expiries)

            if st.button("Load Option Chain Ladder", type="primary"):
                oc = client.options.get_option_chain(opt_sym, expiry=sel_exp)
                st.write(f"**Underlying Spot:** ₹{oc.underlying_price:,.2f} | **Expiry:** {oc.expiry_date}")
                strike_rows = [
                    {
                        "CE Delta": s.ce_delta,
                        "CE LTP": s.ce_ltp,
                        "CE OI": s.ce_oi,
                        "Strike": s.strike_price,
                        "PE OI": s.pe_oi,
                        "PE LTP": s.pe_ltp,
                        "PE Delta": s.pe_delta,
                    }
                    for s in oc.strikes
                ]
                st.dataframe(pd.DataFrame(strike_rows), use_container_width=True)

    # TAB 3: SUPABASE
    with int_tab3:
        st.subheader("Supabase PostgreSQL Persistence & Migrations")
        db_stat = db_repo.get_database_status()

        sc1, sc2 = st.columns(2)
        with sc1:
            st.markdown(f"**Active Mode:** `{db_stat['mode'].upper()}`")
            st.markdown(f"**Local SQLite Storage:** `{db_stat['local_db_path']}`")
        with sc2:
            st.markdown(f"**Supabase Cloud URL:** `{db_stat['supabase_url'] or 'Not Configured (Using Local SQLite)'}`")
            st.markdown(f"**Cloud Sync Active:** `{db_stat['is_cloud_connected']}`")

        st.markdown("---")
        st.subheader("Supabase Connection Health Check")
        if st.button("Check Connection Health", type="primary"):
            with st.spinner("Probing Supabase PostgreSQL Endpoint..."):
                health = db_repo.check_connection_health()
            if health["status"] == "connected":
                st.success(f"Supabase PostgreSQL connected! Response time: `{health['latency_ms']:.1f}ms` • Verified tables: {health['verified_tables']}")
            elif health["status"] == "unconfigured":
                st.info(f"Supabase credentials not configured in secrets. Local SQLite backend is active and durable.")
                st.markdown(f"**Action Required to Connect Supabase:** Set `SUPABASE_URL` and `SUPABASE_KEY` (or `SUPABASE_SERVICE_ROLE_KEY`) in `.env` or Streamlit Cloud Secrets.")
            else:
                st.error(f"Supabase Connection Failed: {health.get('error')}")
            st.json(health)

        st.subheader("Versioned SQL Migrations")
        st.code(
            """
-- Run migrations in Supabase SQL editor:
sql/migrations/001_core_schema.sql
sql/migrations/002_platform_tables.sql
sql/migrations/003_row_level_security.sql
sql/migrations/004_adaptive_intelligence.sql
            """,
            language="sql",
        )
