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
from app.ui.components import generate_sample_market_data


def render_overview_page() -> None:
    st.markdown(
        """
        <div style="margin-bottom: 12px;">
            <h1 style="margin: 0; font-size: 2.1rem; font-weight: 800; color: #f8fafc; letter-spacing: -0.5px;">Executive Command Center</h1>
            <p style="margin: 4px 0 0 0; color: #94a3b8; font-size: 0.95rem;">Real-Time Portfolio Health • Multi-Strategy Algorithmic Execution • Indian Markets (NSE)</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Status Pill Bar with pulsing indicators
    col1, col2, col3, col4 = st.columns([1.6, 1.6, 1.6, 2])
    with col1:
        if settings.paper_trading_only:
            st.markdown('<div class="badge-paper"><span class="pulse-dot-blue"></span>PAPER TRADING ENFORCED</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="badge-live"><span class="pulse-dot-red"></span>LIVE EXECUTION ACTIVE</div>', unsafe_allow_html=True)
    with col2:
        m_open, m_msg = risk_authority.is_market_open()
        if m_open:
            st.markdown('<div class="badge-safe"><span class="pulse-dot-green"></span>NSE SESSION: OPEN</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="badge-paper">● NSE SESSION: CLOSED</div>', unsafe_allow_html=True)
    with col3:
        if risk_authority.kill_switch_active:
            st.markdown('<div class="badge-live"><span class="pulse-dot-red"></span>KILL-SWITCH: TRIPPED</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="badge-safe"><span class="pulse-dot-green"></span>RISK ENGINE: ARMED</div>', unsafe_allow_html=True)
    with col4:
        db_stat = db_repo.get_database_status()
        st.markdown(f"**Database:** `{db_stat['mode']}` • **Broker:** `DhanHQ Sandbox`")

    st.markdown("---")

    # Financial Performance Metrics
    summary = paper_broker.get_portfolio_summary()
    risk_snap = risk_authority.get_risk_snapshot()

    m1, m2, m3, m4, m5 = st.columns(5)
    with m1:
        st.metric(
            "Account Equity",
            f"₹{summary['total_equity']:,.2f}",
            delta=f"{summary['day_return_pct']:+.2f}% Day",
        )
    with m2:
        pnl_val = summary['total_pnl']
        st.metric(
            "Total P&L",
            f"₹{pnl_val:+,.2f}",
            delta=f"Realized: ₹{summary['realized_pnl']:+,.2f}",
        )
    with m3:
        st.metric(
            "Available Cash",
            f"₹{summary['cash_balance']:,.2f}",
            delta=f"Margin: ₹{summary['invested_margin']:,.2f}",
        )
    with m4:
        dd = risk_snap["drawdown_pct"] * 100.0
        st.metric(
            "Current Drawdown",
            f"{dd:.2f}%",
            delta=f"Limit: {risk_authority.config.max_drawdown_fraction * 100:.1f}%",
            delta_color="inverse",
        )
    with m5:
        st.metric(
            "Active Positions",
            f"{summary['open_positions_count']}",
            delta=f"{summary['total_orders_count']} total orders",
        )

    st.write("")

    # Market Regime & Strategy Health
    left_col, right_col = st.columns([2, 1])

    with left_col:
        st.subheader("Current Market Regime & Sector Health")
        df_sample = generate_sample_market_data(60, "NIFTY 50", 24500.0)
        regime, metrics = RegimeDetector.classify_regime(df_sample)

        r_col1, r_col2, r_col3 = st.columns(3)
        with r_col1:
            st.markdown(
                f"""
                <div style="background: linear-gradient(135deg, rgba(30, 41, 59, 0.8), rgba(15, 23, 42, 0.9)); border: 1px solid rgba(56, 189, 248, 0.3); border-radius: 10px; padding: 14px 16px;">
                    <div style="color: #94a3b8; font-size: 0.8rem; font-weight: 600; text-transform: uppercase;">Detected Regime</div>
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

        # Open Positions Table
        st.subheader("Active Portfolio Positions")
        positions = paper_broker.list_positions()
        if positions:
            pos_df = pd.DataFrame(positions)
            st.dataframe(
                pos_df[["symbol", "segment", "side", "quantity", "entry_price", "current_price", "unrealized_pnl"]],
                use_container_width=True,
            )
        else:
            st.info("ℹ️ No active positions open. Quantitative strategies are currently monitoring market feeds for qualified setups.")

    with right_col:
        st.subheader("Quantitative Strategy Status")
        strat_df = pd.DataFrame(
            [
                {
                    "Strategy": s.strategy_id,
                    "Category": getattr(s, "category", "trend").capitalize(),
                    "Status": "ACTIVE",
                }
                for s in STRATEGIES.values()
            ]
        )
        st.dataframe(strat_df, use_container_width=True, height=220)

        # Recent Alerts
        st.subheader("Real-Time Risk & Execution Feed")
        alerts = alert_manager.list_alerts(limit=5)
        if alerts:
            for a in alerts:
                sev_color = "red" if a["severity"] == "critical" else ("orange" if a["severity"] == "warning" else "blue")
                st.markdown(f":{sev_color}[**[{a['severity'].upper()}]**] {a['title']} — *{a['message']}*")
        else:
            st.success("All systems operating nominally. Zero limit breaches.")
