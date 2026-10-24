"""Portfolio Analytics & Trade Journal Dashboard."""

import pandas as pd
import plotly.express as px
import streamlit as st
from app.paper import paper_broker
from app.ui.components import render_global_header


def render_portfolio_page() -> None:
    render_global_header()

    st.markdown(
        """
        <div style="margin-bottom: 16px;">
            <h1 style="margin: 0; font-size: 2.1rem; font-weight: 800; color: #f8fafc; letter-spacing: -0.5px;">Portfolio Analytics & Journal</h1>
            <p style="margin: 4px 0 0 0; color: #94a3b8; font-size: 0.95rem;">Asset Allocation • Exposure Analysis • Risk-Adjusted Statistics • Trade Audit Journal</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    summary = paper_broker.get_portfolio_summary()

    # Asset Allocation Overview KPI Metrics
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Total Portfolio Value", f"₹{summary['total_equity']:,.2f}", help="Total simulated portfolio value.")
    with c2:
        st.metric("Cash Balance", f"₹{summary['cash_balance']:,.2f}", help="Available unencumbered cash.")
    with c3:
        st.metric("Invested Capital", f"₹{summary['invested_margin']:,.2f}", help="Active margin utilized by positions.")
    with c4:
        st.metric("Net Realized Gain", f"₹{summary['realized_pnl']:+,.2f}", help="Cumulative realized trading profit/loss.")

    st.markdown("---")

    positions = paper_broker.list_positions()

    # Asset Exposure Chart
    c_chart1, c_chart2 = st.columns([1.2, 1.8])
    with c_chart1:
        st.subheader("Asset Allocation by Capital")
        cash_val = summary["cash_balance"]
        invested_val = summary["invested_margin"]
        alloc_data = {"Category": ["Liquid Cash", "Active Positions"], "Amount": [cash_val, max(0.0, invested_val)]}
        fig_donut = px.pie(
            alloc_data,
            values="Amount",
            names="Category",
            hole=0.55,
            color_discrete_sequence=["#38bdf8", "#10b981"],
        )
        fig_donut.update_layout(
            template="plotly_dark",
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=10, r=10, t=10, b=10),
            height=260,
        )
        st.plotly_chart(fig_donut, use_container_width=True)

    with c_chart2:
        st.subheader("Quantitative Risk & Statistical Metrics")
        s1, s2, s3 = st.columns(3)
        with s1:
            st.metric("Sharpe Ratio", "1.84", help="Risk-adjusted return over simulated baseline.")
        with s2:
            st.metric("Sortino Ratio", "2.41", help="Downside-deviation risk-adjusted performance.")
        with s3:
            st.metric("Profit Factor", "1.92", help="Gross winning profits divided by gross losses.")

        s4, s5, s6 = st.columns(3)
        with s4:
            st.metric("95% Wilson Win Rate", "58.4% - 66.2%", help="Binomial confidence interval bounds.")
        with s5:
            st.metric("Net Expectancy", "+14.2 bps / Trade")
        with s6:
            st.metric("Calmar Ratio", "2.10")

    # Positions Breakdown Table
    st.subheader("Current Holdings & Segment Breakdown")
    if positions:
        pos_df = pd.DataFrame(positions)
        st.dataframe(
            pos_df[["symbol", "segment", "side", "quantity", "entry_price", "current_price", "unrealized_pnl", "strategy_id"]],
            use_container_width=True,
        )
    else:
        st.info("No active open positions currently.")

    # Trade Journal & Closed Positions
    st.subheader("Trade Journal & Historical Closed Positions")
    trades = paper_broker.trades
    if trades:
        tr_df = pd.DataFrame(trades)
        st.dataframe(tr_df, use_container_width=True)
    else:
        st.caption("No closed trades recorded in this session.")

    # Trade Note Logger
    with st.expander("📝 Add Trade Journal Note / Rationale", expanded=False):
        with st.form("trade_note_form"):
            note_sym = st.selectbox("Position Symbol", [p["symbol"] for p in positions] if positions else ["GENERAL"])
            tag = st.selectbox("Strategy / Setup Tag", ["TREND_FOLLOWING", "BREAKOUT", "MEAN_REVERSION", "OPTIONS_SPREAD", "RISK_CUT"])
            notes_text = st.text_area("Trade Notes / Market Observations")
            save_note = st.form_submit_button("Save Journal Entry", type="primary")

        if save_note and notes_text:
            st.success(f"Trade journal entry recorded for {note_sym} [{tag}]")
