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


def render_integrations_page() -> None:
    st.title("Integration Hub & Broker Connectivity")
    st.caption("TradingView Webhooks • DhanHQ Broker Adapter • Supabase PostgreSQL Sync")

    int_tab1, int_tab2, int_tab3 = st.tabs(["TradingView Webhook", "DhanHQ Broker API", "Supabase Database"])

    # TAB 1: TRADINGVIEW
    with int_tab1:
        st.subheader("TradingView Webhook Receiver")
        st.markdown(
            """
            AlgoTrade AI receives and cryptographically authenticates TradingView alerts.
            Incoming alerts pass through anti-replay deduplication and timestamp drift validation.
            """
        )

        st.code(
            f"""
            Webhook URL: https://<YOUR_DEPLOYED_DOMAIN>/integrations/tradingview/webhook
            Passphrase: {settings.tradingview_webhook_secret}
            """,
            language="text",
        )

        st.subheader("Test Webhook Alert Dispatcher")
        with st.form("tv_test_form"):
            tv_sym = st.selectbox("Symbol", ["RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK"])
            tv_side = st.selectbox("Direction", ["long", "short"])
            tv_price = st.number_input("Reference Price", value=2840.0)
            tv_stop = st.number_input("Suggested Stop Loss", value=2810.0)
            tv_target = st.number_input("Suggested Take Profit", value=2900.0)
            tv_pass = st.text_input("Webhook Passphrase", value=settings.tradingview_webhook_secret, type="password")
            submit_tv = st.form_submit_button("Send Simulated Alert", type="primary")

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
        dhan_sub1, dhan_sub2, dhan_sub3, dhan_sub4 = st.tabs([
            "Funds & Portfolio",
            "Live Quotes & Staleness",
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

        with dhan_sub4:
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
            st.markdown(f"**Supabase Cloud URL:** `{db_stat['supabase_url']}`")
            st.markdown(f"**Cloud Sync Active:** `{db_stat['is_cloud_connected']}`")

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
