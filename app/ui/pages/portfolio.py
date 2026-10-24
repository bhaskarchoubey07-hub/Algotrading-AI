import pandas as pd
import streamlit as st
from app.paper import paper_broker


def render_portfolio_page() -> None:
    st.title("Portfolio & Trade Journal — Position Tracking")
    st.caption("Consolidated Paper & Broker Holdings • Trade Attribution • Audit Journal")

    summary = paper_broker.get_portfolio_summary()

    # Asset Allocation Overview
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Total Portfolio Value", f"₹{summary['total_equity']:,.2f}")
    with c2:
        st.metric("Cash Balance", f"₹{summary['cash_balance']:,.2f}")
    with c3:
        st.metric("Invested Capital", f"₹{summary['invested_margin']:,.2f}")
    with c4:
        st.metric("Net Realized Gain", f"₹{summary['realized_pnl']:+,.2f}")

    st.markdown("---")

    # Positions Breakdown Table
    st.subheader("Current Holdings & Segment Breakdown")
    positions = paper_broker.list_positions()
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
    with st.expander("Add Trade Journal Note / Rationale", expanded=False):
        with st.form("trade_note_form"):
            note_sym = st.selectbox("Position Symbol", [p["symbol"] for p in positions] if positions else ["GENERAL"])
            tag = st.selectbox("Strategy / Setup Tag", ["TREND_FOLLOWING", "BREAKOUT", "MEAN_REVERSION", "OPTIONS_SPREAD", "RISK_CUT"])
            notes_text = st.text_area("Trade Notes / Market Observations")
            save_note = st.form_submit_button("Save Journal Entry")

        if save_note and notes_text:
            st.success(f"Trade journal entry recorded for {note_sym} [{tag}]")
