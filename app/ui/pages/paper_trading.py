"""Paper Trading Workstation & Institutional Simulated Broker Execution."""

from datetime import datetime
import pandas as pd
import streamlit as st
from app.alerts.manager import alert_manager
from app.models import AlertCategory, AlertSeverity
from app.paper import paper_broker
from app.risk import risk_authority
from app.services.market_data import NSE_CATALOG, market_data_service
from app.ui.components import render_global_header


def render_paper_trading_page() -> None:
    render_global_header()

    st.markdown(
        """
        <div style="margin-bottom: 16px;">
            <div class="badge-paper" style="font-size: 0.85rem; padding: 6px 14px; margin-bottom: 8px;">
                <span class="pulse-dot-blue"></span> PAPER TRADING — REALISTIC EXECUTION ENGINE
            </div>
            <h1 style="margin: 0; font-size: 2.1rem; font-weight: 800; color: #f8fafc; letter-spacing: -0.5px;">Paper Trading Workstation</h1>
            <p style="margin: 4px 0 0 0; color: #94a3b8; font-size: 0.95rem;">Auditable Simulated Orders • Real-Time Stock Pricing • Realistic Slippage & Brokerage • Margin Accounting</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    summary = paper_broker.get_portfolio_summary()
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Total Equity", f"₹{summary['total_equity']:,.2f}", delta=f"{summary['day_return_pct']:+.2f}%")
    with c2:
        st.metric("Available Cash", f"₹{summary['cash_balance']:,.2f}")
    with c3:
        st.metric("Realized P&L", f"₹{summary['realized_pnl']:+,.2f}")
    with c4:
        st.metric("Unrealized P&L", f"₹{summary['unrealized_pnl']:+,.2f}")

    st.markdown("---")

    # Order Placement Ticket & Active Positions
    left_ticket, right_positions = st.columns([1.1, 1.7])

    with left_ticket:
        st.subheader("Manual Paper Order Ticket")
        sym_options = list(NSE_CATALOG.keys())
        selected_sym = st.selectbox("Symbol", sym_options, index=4)  # Default RELIANCE
        
        # Real-time quote preview for ticket
        live_q = market_data_service.get_realtime_quote(selected_sym)
        live_p = float(live_q["last_price"])
        q_chg = float(live_q["change"])
        q_pct = float(live_q["change_pct"])
        chg_col = "#10b981" if q_chg >= 0 else "#f43f5e"
        
        st.markdown(
            f"""
            <div style="background: rgba(15, 23, 42, 0.7); border: 1px solid rgba(255,255,255,0.06); border-radius: 8px; padding: 8px 12px; margin-bottom: 12px; font-family: 'JetBrains Mono', monospace; font-size: 0.85rem;">
                <span style="color: #94a3b8;">Live LTP:</span> <b style="color: #f8fafc; font-size: 1.05rem;">₹{live_p:,.2f}</b>
                <span style="color: {chg_col}; margin-left: 8px; font-weight: 600;">{q_chg:+.2f} ({q_pct:+.2f}%)</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        with st.form("manual_paper_order_form"):
            side = st.radio("Side", ["BUY", "SELL"], horizontal=True)
            lot_def = NSE_CATALOG.get(selected_sym, {}).get("lot_size", 1)
            qty = st.number_input("Quantity", min_value=1, max_value=50000, value=lot_def, step=lot_def)
            order_type = st.selectbox("Order Type", ["MARKET", "LIMIT", "STOP_LOSS"])
            limit_price = st.number_input("Limit Price (₹)", min_value=0.0, value=live_p, step=0.05) if order_type != "MARKET" else live_p
            sl_price = st.number_input("Optional Stop Loss (₹)", min_value=0.0, value=0.0, step=0.05)
            tp_price = st.number_input("Optional Target (₹)", min_value=0.0, value=0.0, step=0.05)

            submit_order = st.form_submit_button("Submit Paper Order", type="primary", use_container_width=True)

        if submit_order:
            pos_count = len(paper_broker.positions)
            ref_p = limit_price if order_type == "LIMIT" else live_p
            risk_ok, risk_msg = risk_authority.validate_order(
                symbol=selected_sym,
                side=side.lower(),
                quantity=qty,
                price=ref_p,
                current_positions_count=pos_count,
            )

            if not risk_ok:
                st.error(f"❌ Risk Authority Rejection: {risk_msg}")
                alert_manager.dispatch(AlertCategory.RISK, AlertSeverity.WARNING, "Paper Order Rejected", risk_msg)
            else:
                try:
                    order = paper_broker.place_order(
                        symbol=selected_sym,
                        side=side.lower(),
                        quantity=qty,
                        price=ref_p if order_type != "MARKET" else live_p,
                        order_type=order_type,
                        stop_loss=sl_price if sl_price > 0 else None,
                        take_profit=tp_price if tp_price > 0 else None,
                        strategy_id="manual_ui",
                    )
                    st.success(f"✅ Paper Order #{order.order_id[:8]} filled @ ₹{order.fill_price:,.2f}!")
                    alert_manager.dispatch(
                        AlertCategory.EXECUTION,
                        AlertSeverity.INFO,
                        f"Paper Order Executed: {selected_sym} {side}",
                        f"Filled {qty} shares @ ₹{order.fill_price} (Fees: ₹{order.fees})",
                    )
                    st.rerun()
                except Exception as exc:
                    st.error(f"Execution Error: {exc}")

    with right_positions:
        p_hdr1, p_hdr2 = st.columns([1.5, 1])
        with p_hdr1:
            st.subheader("Open Paper Positions")
        with p_hdr2:
            if paper_broker.positions:
                if st.button("🚨 Square Off All", key="close_all_pos", type="secondary"):
                    for s in list(paper_broker.positions.keys()):
                        paper_broker.close_position(s)
                    st.success("All positions squared off!")
                    st.rerun()

        positions = paper_broker.list_positions()
        if positions:
            for p in positions:
                # Live Mark-to-Market refresh
                try:
                    q = market_data_service.get_realtime_quote(p["symbol"])
                    live_ltp = float(q["last_price"])
                    paper_broker.update_market_price(p["symbol"], live_ltp)
                    p = paper_broker.positions.get(p["symbol"], p)
                    if hasattr(p, "to_dict"):
                        p = p.to_dict()
                except Exception:
                    pass

                p_col1, p_col2, p_col3, p_col4 = st.columns([2, 2, 2, 1])
                with p_col1:
                    st.markdown(f"**{p['symbol']}** `({p['side'].upper()})`")
                    st.caption(f"Qty: {p['quantity']} • Avg: ₹{p['entry_price']:,.2f}")
                with p_col2:
                    st.markdown(f"**LTP:** ₹{p['current_price']:,.2f}")
                    sl_str = f"SL: ₹{p['stop_loss']:,.2f}" if p.get('stop_loss') else "No SL"
                    st.caption(sl_str)
                with p_col3:
                    pnl = p["unrealized_pnl"]
                    color = "green" if pnl >= 0 else "red"
                    st.markdown(f":{color}[**₹{pnl:+,.2f}**]")
                with p_col4:
                    if st.button("Close", key=f"close_paper_{p['symbol']}"):
                        paper_broker.close_position(p["symbol"])
                        st.success(f"Position {p['symbol']} closed.")
                        st.rerun()
                st.divider()
        else:
            st.info("ℹ️ No open paper positions. Submit an order from the ticket to start tracking live P&L.")

    # Order History
    st.subheader("Paper Order Execution History")
    orders = paper_broker.list_orders()
    if orders:
        ord_df = pd.DataFrame(orders)
        st.dataframe(
            ord_df[["order_id", "symbol", "side", "quantity", "order_type", "fill_price", "fees", "status", "created_at"]],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.caption("No paper orders placed yet.")
