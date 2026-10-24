import pandas as pd
import streamlit as st
from app.alerts.manager import alert_manager
from app.models import AlertCategory, AlertSeverity
from app.paper import paper_broker
from app.risk import risk_authority


def render_paper_trading_page() -> None:
    st.title("Paper Trading Workstation — Simulated Broker")
    st.caption("Realistic Order Execution • Spread & Slippage Modeling • Transaction Cost Accounting")

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
    left_ticket, right_positions = st.columns([1, 2])

    with left_ticket:
        st.subheader("Manual Order Ticket")
        with st.form("manual_paper_order_form"):
            sym = st.selectbox("Symbol", ["RELIANCE", "TCS", "HDFCBANK", "INFY", "TATAMOTORS", "NIFTY 50", "BANKNIFTY"])
            side = st.radio("Side", ["BUY", "SELL"], horizontal=True)
            qty = st.number_input("Quantity", min_value=1, max_value=50000, value=10, step=1)
            order_type = st.selectbox("Order Type", ["MARKET", "LIMIT", "STOP_LOSS"])
            limit_price = st.number_input("Price (₹)", min_value=0.0, value=2800.0, step=0.5) if order_type != "MARKET" else 0.0
            sl_price = st.number_input("Optional Stop Loss (₹)", min_value=0.0, value=0.0, step=0.5)
            tp_price = st.number_input("Optional Target (₹)", min_value=0.0, value=0.0, step=0.5)

            submit_order = st.form_submit_button("Submit Paper Order", type="primary")

        if submit_order:
            # Risk check
            pos_count = len(paper_broker.positions)
            ref_p = limit_price if limit_price > 0 else (2800.0 if "RELIANCE" in sym else 500.0)
            risk_ok, risk_msg = risk_authority.validate_order(
                symbol=sym,
                side=side.lower(),
                quantity=qty,
                price=ref_p,
                current_positions_count=pos_count,
            )

            if not risk_ok:
                st.error(f"Risk Authority Rejection: {risk_msg}")
                alert_manager.dispatch(AlertCategory.RISK, AlertSeverity.WARNING, "Paper Order Rejected", risk_msg)
            else:
                try:
                    order = paper_broker.place_order(
                        symbol=sym,
                        side=side.lower(),
                        quantity=qty,
                        price=limit_price,
                        order_type=order_type,
                        stop_loss=sl_price if sl_price > 0 else None,
                        take_profit=tp_price if tp_price > 0 else None,
                        strategy_id="manual_ui",
                    )
                    st.success(f"Paper Order #{order.order_id[:8]} executed @ ₹{order.fill_price:,.2f}!")
                    alert_manager.dispatch(
                        AlertCategory.EXECUTION,
                        AlertSeverity.INFO,
                        f"Paper Order Executed: {sym} {side}",
                        f"Filled {qty} shares @ ₹{order.fill_price} (Fees: ₹{order.fees})",
                    )
                    st.rerun()
                except Exception as exc:
                    st.error(f"Execution Error: {exc}")

    with right_positions:
        st.subheader("Open Paper Positions")
        positions = paper_broker.list_positions()
        if positions:
            for p in positions:
                p_col1, p_col2, p_col3, p_col4 = st.columns([2, 2, 2, 1])
                with p_col1:
                    st.markdown(f"**{p['symbol']}** ({p['side'].upper()})")
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
                    if st.button("Close", key=f"close_{p['symbol']}"):
                        paper_broker.close_position(p["symbol"])
                        st.success(f"Position {p['symbol']} closed.")
                        st.rerun()
                st.divider()
        else:
            st.info("No open paper positions. Submit an order from the ticket.")

    # Order History
    st.subheader("Paper Order Execution History")
    orders = paper_broker.list_orders()
    if orders:
        ord_df = pd.DataFrame(orders)
        st.dataframe(
            ord_df[["order_id", "symbol", "side", "quantity", "order_type", "fill_price", "fees", "status", "created_at"]],
            use_container_width=True,
        )
    else:
        st.caption("No paper orders placed yet.")
