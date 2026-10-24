"""Market Terminal — NSE Multi-Timeframe Workstation & Charting Experience."""

import pandas as pd
import streamlit as st
from app.models import TradingSegment
from app.paper import paper_broker
from app.risk import risk_authority
from app.ui.components import (
    create_candlestick_chart,
    generate_sample_market_data,
    render_global_header,
)

INSTRUMENT_CATALOG = {
    "NIFTY 50": {"segment": "INDEX", "base": 24650.0, "lot_size": 25, "tick_size": 0.05},
    "BANKNIFTY": {"segment": "INDEX", "base": 51200.0, "lot_size": 15, "tick_size": 0.05},
    "FINNIFTY": {"segment": "INDEX", "base": 23410.0, "lot_size": 40, "tick_size": 0.05},
    "NIFTYBEES": {"segment": "EQUITY_CASH", "base": 265.0, "lot_size": 1, "tick_size": 0.01},
    "BANKBEES": {"segment": "EQUITY_CASH", "base": 520.0, "lot_size": 1, "tick_size": 0.01},
    "RELIANCE": {"segment": "EQUITY_CASH", "base": 2840.0, "lot_size": 1, "tick_size": 0.05},
    "TCS": {"segment": "EQUITY_CASH", "base": 4120.0, "lot_size": 1, "tick_size": 0.05},
    "HDFCBANK": {"segment": "EQUITY_CASH", "base": 1680.0, "lot_size": 1, "tick_size": 0.05},
    "INFY": {"segment": "EQUITY_CASH", "base": 1740.0, "lot_size": 1, "tick_size": 0.05},
    "ICICIBANK": {"segment": "EQUITY_CASH", "base": 1150.0, "lot_size": 1, "tick_size": 0.05},
}


def render_terminal_page() -> None:
    render_global_header()

    st.markdown(
        """
        <div style="margin-bottom: 14px;">
            <h1 style="margin: 0; font-size: 2.1rem; font-weight: 800; color: #f8fafc; letter-spacing: -0.5px;">Market Terminal — NSE Workstation</h1>
            <p style="margin: 4px 0 0 0; color: #94a3b8; font-size: 0.95rem;">Multi-Timeframe Charting • Technical Overlays • Level 2 Depth • Instant Paper Execution</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 1. Instrument & Chart Controls Bar
    c1, c2, c3, c4, c5 = st.columns([1.8, 1, 1, 1, 1.2])
    with c1:
        selected_symbol = st.selectbox("Instrument Watchlist", list(INSTRUMENT_CATALOG.keys()))
    with c2:
        selected_tf = st.selectbox("Timeframe", ["1m", "5m", "15m", "1h", "1d"], index=4)
    with c3:
        chart_type = st.selectbox("Chart Style", ["Candlestick", "Line", "Area"])
    with c4:
        chart_bars = st.slider("Bar Count", min_value=30, max_value=300, value=120)
    with c5:
        inst_info = INSTRUMENT_CATALOG[selected_symbol]
        st.markdown(
            f"""
            <div style="background: rgba(15, 23, 42, 0.7); border: 1px solid rgba(255,255,255,0.06); border-radius: 8px; padding: 8px 12px; font-size: 0.8rem;">
                <span class="badge-safe"><span class="pulse-dot-green"></span>FRESH (24ms)</span><br>
                <b>Lot:</b> {inst_info['lot_size']} • <b>Tick:</b> ₹{inst_info['tick_size']}
            </div>
            """,
            unsafe_allow_html=True,
        )

    # 2. Indicator Toolbar Expander
    with st.expander("🛠️ Technical Overlays & Oscillators Toolbar", expanded=False):
        ic1, ic2, ic3, ic4 = st.columns(4)
        with ic1:
            show_ema = st.checkbox("EMA (20 / 50 / 200)", value=True)
            show_bb = st.checkbox("Bollinger Bands (20, 2σ)", value=True)
        with ic2:
            show_supertrend = st.checkbox("Supertrend (10, 3)", value=False)
            show_vwap = st.checkbox("Session VWAP", value=True)
        with ic3:
            show_donchian = st.checkbox("Donchian Channels (20)", value=False)
            show_vol = st.checkbox("Volume Histogram", value=True)
        with ic4:
            show_rsi = st.checkbox("RSI (14) Oscillator", value=True)
            show_macd = st.checkbox("MACD (12, 26, 9)", value=True)

    # 3. Chart Rendering
    df = generate_sample_market_data(n_bars=chart_bars, symbol=selected_symbol, base_price=inst_info["base"])
    fig = create_candlestick_chart(
        df,
        symbol=selected_symbol,
        chart_type=chart_type,
        show_volume=show_vol,
        show_ema=show_ema,
        show_bb=show_bb,
        show_supertrend=show_supertrend,
        show_vwap=show_vwap,
        show_donchian=show_donchian,
        show_rsi=show_rsi,
        show_macd=show_macd,
    )
    st.plotly_chart(fig, use_container_width=True)

    # 4. Quantitative Indicators Matrix
    from app.indicators import indicator_pipeline

    feat_df = indicator_pipeline.compute_all_features(df, symbol=selected_symbol, timeframe=selected_tf)
    last_row = feat_df.iloc[-1]
    curr_price = float(df["close"].iloc[-1])

    st.subheader("Quantitative Indicator Matrix")
    m1, m2, m3, m4, m5, m6 = st.columns(6)
    with m1:
        st.metric("RSI (14)", f"{last_row.get('rsi_14', 50.0):.1f}")
    with m2:
        st.metric("ADX (14)", f"{last_row.get('adx', 20.0):.1f}")
    with m3:
        st.metric("ATR (14)", f"₹{last_row.get('atr_14', 0.0):.2f}")
    with m4:
        st.metric("MACD Hist", f"{last_row.get('macd_hist', 0.0):+.2f}")
    with m5:
        st.metric("BB Squeeze", "🚨 ACTIVE" if last_row.get("bb_squeeze", False) else "NORMAL")
    with m6:
        st.metric("Supertrend", "🟢 BULLISH" if last_row.get("supertrend_dir", 1) == 1 else "🔴 BEARISH")

    st.write("")

    # 5. Level 2 Market Depth & Quick Order Entry Ticket
    col_depth, col_order = st.columns([1, 1.2])

    with col_depth:
        st.subheader("Simulated Level 2 Order Depth (Bid / Ask)")
        tick = inst_info["tick_size"]
        bids = [
            {"Orders": 12 + i * 2, "Bid Qty": 1500 - i * 150, "Bid Price": round(curr_price - i * tick, 2)}
            for i in range(1, 6)
        ]
        asks = [
            {"Ask Price": round(curr_price + i * tick, 2), "Ask Qty": 1250 - i * 100, "Orders": 8 + i * 2}
            for i in range(1, 6)
        ]
        depth_df = pd.DataFrame(bids)
        depth_df["Ask Price"] = [a["Ask Price"] for a in asks]
        depth_df["Ask Qty"] = [a["Ask Qty"] for a in asks]
        depth_df["Ask Orders"] = [a["Orders"] for a in asks]
        st.dataframe(depth_df, use_container_width=True, hide_index=True)

    with col_order:
        st.subheader("⚡ Quick Paper Order Entry")
        with st.form("quick_terminal_order_form"):
            t_side = st.radio("Side", ["BUY", "SELL"], horizontal=True)
            o_c1, o_c2 = st.columns(2)
            with o_c1:
                t_qty = st.number_input("Quantity", min_value=1, max_value=10000, value=inst_info["lot_size"], step=inst_info["lot_size"])
            with o_c2:
                t_type = st.selectbox("Order Type", ["MARKET", "LIMIT"])
            t_price = st.number_input("Limit Price (₹)", min_value=0.0, value=curr_price, step=0.5) if t_type == "LIMIT" else curr_price

            # Dynamic margin and notional calculation
            is_derivative = (
                inst_info.get("segment") in {"INDEX", "INDEX_FUTURES", "EQUITY_FUTURES"}
                or selected_symbol in {"NIFTY 50", "BANKNIFTY", "FINNIFTY"}
            )
            est_notional = t_price * t_qty
            est_margin = est_notional * 0.15 if is_derivative else est_notional

            st.markdown(
                f"""
                <div style="background: rgba(30, 41, 59, 0.45); border: 1px solid rgba(255,255,255,0.06); border-radius: 6px; padding: 6px 10px; margin: 8px 0; font-size: 0.8rem; color: #cbd5e1;">
                    <b>Est. Notional:</b> ₹{est_notional:,.2f} &nbsp;|&nbsp; 
                    <b>Req. Margin:</b> <span style="color: {'#38bdf8' if is_derivative else '#10b981'}; font-weight: 600;">₹{est_margin:,.2f}</span>
                    <span style="color: #94a3b8; font-size: 0.75rem;">({'15% Derivative Margin' if is_derivative else '100% Cash Delivery'})</span>
                </div>
                """,
                unsafe_allow_html=True,
            )

            submit_quick_order = st.form_submit_button(f"Submit Paper {t_side} Order", type="primary", use_container_width=True)

        if submit_quick_order:
            summary = paper_broker.get_portfolio_summary()
            risk_authority.sync_equity_with_broker(summary["total_equity"])

            seg_str = inst_info.get("segment", "EQUITY_CASH")
            seg_enum = TradingSegment(seg_str) if seg_str in TradingSegment.__members__ else TradingSegment.INDEX

            risk_ok, risk_msg = risk_authority.validate_order(
                symbol=selected_symbol,
                side=t_side.lower(),
                quantity=t_qty,
                price=t_price,
                current_positions_count=len(paper_broker.positions),
                segment=seg_enum,
                lot_size=inst_info["lot_size"],
            )
            if not risk_ok:
                st.error(f"Order Rejected by Risk Authority: {risk_msg}")
            else:
                try:
                    order = paper_broker.place_order(
                        symbol=selected_symbol,
                        side=t_side.lower(),
                        quantity=t_qty,
                        price=t_price if t_type == "LIMIT" else 0.0,
                        order_type=t_type,
                        segment=seg_str,
                        strategy_id="terminal_quick",
                    )
                    st.success(f"Paper Order #{order.order_id[:8]} executed @ ₹{order.fill_price:,.2f}!")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Execution Error: {exc}")
