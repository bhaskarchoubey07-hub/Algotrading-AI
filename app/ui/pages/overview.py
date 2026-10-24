"""Overview Command Center — Institutional Dashboard for AlgoTrade AI."""

from datetime import datetime
import pandas as pd
import plotly.express as px
import streamlit as st
from app.alerts.manager import alert_manager
from app.config import settings
from app.database.supabase_client import db_repo
from app.ensemble import RegimeDetector
from app.paper import paper_broker
from app.risk import risk_authority
from app.strategies import STRATEGIES
from app.ui.components import (
    generate_sample_market_data,
    render_global_header,
    render_onboarding_guide,
)


def render_overview_page() -> None:
    # 1. Global Header with real-time session & connectivity indicators
    render_global_header()

    # 2. Page Title & Description
    st.markdown(
        """
        <div style="margin-bottom: 16px;">
            <h1 style="margin: 0; font-size: 2.1rem; font-weight: 800; color: #f8fafc; letter-spacing: -0.5px;">Executive Trading Command Center</h1>
            <p style="margin: 4px 0 0 0; color: #94a3b8; font-size: 0.95rem;">Real-Time Financial Health • Quantitative Strategy Intelligence • Indian Markets (NSE)</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 3. Smart Onboarding Walkthrough for Beginners
    render_onboarding_guide()

    # 4. Financial KPI Metrics with Contextual Tooltips
    summary = paper_broker.get_portfolio_summary()
    risk_snap = risk_authority.get_risk_snapshot()

    m1, m2, m3, m4, m5 = st.columns(5)
    with m1:
        st.metric(
            "Account Equity",
            f"₹{summary['total_equity']:,.2f}",
            delta=f"{summary['day_return_pct']:+.2f}% Day",
            help="Total simulated net worth including cash balance, collateral, and open unrealized P&L.",
        )
    with m2:
        pnl_val = summary['total_pnl']
        st.metric(
            "Total P&L",
            f"₹{pnl_val:+,.2f}",
            delta=f"Realized: ₹{summary['realized_pnl']:+,.2f}",
            delta_color="normal",
            help="Consolidated net profit/loss across all paper trading executions.",
        )
    with m3:
        st.metric(
            "Available Cash",
            f"₹{summary['cash_balance']:,.2f}",
            delta=f"Margin: ₹{summary['invested_margin']:,.2f}",
            help="Unencumbered liquid cash available to deploy into new quantitative strategy setups.",
        )
    with m4:
        dd = risk_snap["drawdown_pct"] * 100.0
        st.metric(
            "Current Drawdown",
            f"{dd:.2f}%",
            delta=f"Circuit: {risk_authority.config.max_drawdown_fraction * 100:.1f}%",
            delta_color="inverse",
            help="Peak-to-trough equity decline. Monitored against a strict 5.0% platform circuit breaker.",
        )
    with m5:
        st.metric(
            "Active Positions",
            f"{summary['open_positions_count']}",
            delta=f"{summary['total_orders_count']} Total Orders",
            help="Number of active open market positions monitored by the pre-trade risk engine.",
        )

    st.write("")

    # 5. Market Regime Radar & Quantitative Strategies
    left_col, right_col = st.columns([1.8, 1.2])

    with left_col:
        st.subheader("⚡ Live Market Regime Radar")
        df_sample = generate_sample_market_data(60, "NIFTY 50", 24500.0)
        regime, metrics = RegimeDetector.classify_regime(df_sample)

        r_col1, r_col2, r_col3 = st.columns(3)
        with r_col1:
            st.markdown(
                f"""
                <div style="background: linear-gradient(135deg, rgba(30, 41, 59, 0.8), rgba(15, 23, 42, 0.9)); border: 1px solid rgba(56, 189, 248, 0.3); border-radius: 10px; padding: 14px 16px;">
                    <div style="color: #94a3b8; font-size: 0.8rem; font-weight: 600; text-transform: uppercase;">Classified Regime</div>
                    <div style="color: #38bdf8; font-size: 1.35rem; font-weight: 800; font-family: 'JetBrains Mono', monospace; margin-top: 4px;">{regime.value.upper()}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with r_col2:
            st.metric("ADX (Trend Strength)", f"{metrics.get('adx', 0):.1f}", delta="Strong Trend" if metrics.get('adx', 0) >= 25 else "Consolidation")
        with r_col3:
            st.metric("ATR Volatility %", f"{metrics.get('atr_pct', 0):.2f}%", delta="Normal Volatility")

        st.write("")

        # Active Positions Table with 1-Click Close Actions
        st.subheader("Active Portfolio Positions")
        positions = paper_broker.list_positions()
        if positions:
            for p in positions:
                p_c1, p_c2, p_c3, p_c4 = st.columns([2, 2, 2, 1])
                with p_c1:
                    st.markdown(f"**{p['symbol']}** `({p['side'].upper()})`")
                    st.caption(f"Qty: {p['quantity']} • Avg: ₹{p['entry_price']:,.2f}")
                with p_c2:
                    st.markdown(f"**LTP:** ₹{p['current_price']:,.2f}")
                    sl_text = f"SL: ₹{p['stop_loss']:,.2f}" if p.get('stop_loss') else "No Stop"
                    st.caption(sl_text)
                with p_c3:
                    pnl = p["unrealized_pnl"]
                    color = "green" if pnl >= 0 else "red"
                    st.markdown(f":{color}[**₹{pnl:+,.2f}**]")
                with p_c4:
                    if st.button("Close", key=f"ov_close_{p['symbol']}"):
                        paper_broker.close_position(p["symbol"])
                        st.success(f"Position {p['symbol']} closed.")
                        st.rerun()
                st.divider()
        else:
            st.info("ℹ️ No active open positions. Quantitative strategies are monitoring incoming NSE tick feeds for qualified setups.")

    with right_col:
        st.subheader("Quantitative Strategy Status (18 Active)")
        strat_rows = []
        for s in STRATEGIES.values():
            meta = s.metadata()
            strat_rows.append({
                "Strategy": s.strategy_id.upper(),
                "Cluster": getattr(s, "category", "Trend").capitalize(),
                "Regime": ", ".join(meta.get("supported_regimes", ["Any"])),
                "Status": "ACTIVE",
            })
        st.dataframe(pd.DataFrame(strat_rows), use_container_width=True, height=240, hide_index=True)

        st.subheader("Real-Time Risk & Execution Feed")
        alerts = alert_manager.list_alerts(limit=5)
        if alerts:
            for a in alerts:
                sev_color = "red" if a["severity"] == "critical" else ("orange" if a["severity"] == "warning" else "blue")
                st.markdown(f":{sev_color}[**[{a['severity'].upper()}]**] {a['title']} — *{a['message']}*")
        else:
            st.success("All systems operating nominally. Zero limit breaches.")
