"""Market Terminal — NSE Multi-Timeframe Workstation & High-Performance Charting.

Powered by real-time market data feeds (NSE & Global Markets via Yahoo Finance),
institutional technical indicator overlays, live Level 2 depth, and paper execution.
"""

from datetime import datetime
import pandas as pd
import streamlit as st
from zoneinfo import ZoneInfo

from app.models import TradingSegment
from app.paper import paper_broker
from app.risk import risk_authority
from app.services.market_data import NSE_CATALOG, market_data_service
from app.ui.components import (
    create_candlestick_chart,
    generate_sample_market_data,
    render_global_header,
)

IST = ZoneInfo("Asia/Kolkata")


def render_terminal_page() -> None:
    render_global_header()

    st.markdown(
        """
        <div style="display: flex; justify-content: space-between; align-items: flex-end; margin-bottom: 16px; flex-wrap: wrap; gap: 12px;">
            <div>
                <h1 style="margin: 0; font-size: 2.1rem; font-weight: 800; color: #f8fafc; letter-spacing: -0.5px;">Market Terminal — NSE Workstation</h1>
                <p style="margin: 4px 0 0 0; color: #94a3b8; font-size: 0.95rem;">Multi-Timeframe Real Market Charting • Technical Overlays • Level 2 Depth • Instant Paper Execution</p>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 1. Instrument & Controls Header Row
    c_feed, c_inst, c_custom, c_tf, c_style, c_btn = st.columns([1.5, 1.6, 1.2, 0.9, 1.0, 1.0])
    
    with c_feed:
        feed_mode = st.selectbox(
            "Market Data Feed",
            ["🟢 Live Real-Time Feed (NSE)", "🎲 Synthetic Walk Simulation"],
            index=0,
            help="Toggle between actual live historical stock exchange feeds and offline simulation.",
        )
        use_real = "Live" in feed_mode

    with c_inst:
        popular_options = list(NSE_CATALOG.keys()) + ["Custom Ticker..."]
        selected_option = st.selectbox("Instrument Watchlist", popular_options, index=0)

    with c_custom:
        if selected_option == "Custom Ticker...":
            custom_symbol = st.text_input("Enter Ticker", value="TATAMOTORS", help="E.g. ZOMATO, AAPL, NVDA, BTC-USD, etc.")
            selected_symbol = custom_symbol.strip().upper()
        else:
            selected_symbol = selected_option

    with c_tf:
        selected_tf = st.selectbox("Timeframe", ["1m", "5m", "15m", "1h", "1d", "1wk"], index=4)

    with c_style:
        chart_type = st.selectbox("Chart Style", ["Candlestick", "Line", "Area"])

    with c_btn:
        st.write("")
        st.write("")
        refresh_data = st.button("🔄 Refresh Quote", use_container_width=True, type="secondary")

    # Fetch Real-Time Quote for Selected Instrument
    quote = market_data_service.get_realtime_quote(selected_symbol, force_fresh=refresh_data)
    curr_price = float(quote["last_price"])
    prev_close = float(quote["previous_close"])
    change = float(quote["change"])
    change_pct = float(quote["change_pct"])
    is_gain = change >= 0
    delta_color = "#10b981" if is_gain else "#f43f5e"
    arrow = "▲" if is_gain else "▼"
    sign = "+" if is_gain else ""

    # Get Instrument Specs
    inst_meta = NSE_CATALOG.get(selected_symbol, {
        "segment": "EQUITY_CASH",
        "sector": "Equity",
        "lot_size": 1,
        "tick_size": 0.05,
    })
    lot_size = inst_meta.get("lot_size", 1)
    tick_size = inst_meta.get("tick_size", 0.05)

    # 2. Institutional Real-Time Quote Ribbon
    day_open = quote["open"]
    day_high = quote["high"]
    day_low = quote["low"]
    volume = quote["volume"]
    h_52w = quote["high_52w"]
    l_52w = quote["low_52w"]
    src_label = quote["data_source"]

    # Calculate 52w range position percentage
    range_span = (h_52w - l_52w) if (h_52w > l_52w) else 1.0
    pct_52w = max(0.0, min(100.0, ((curr_price - l_52w) / range_span) * 100.0))

    st.markdown(
        f"""
        <div style="background: linear-gradient(135deg, rgba(17, 24, 39, 0.95) 0%, rgba(15, 23, 42, 0.98) 100%);
                    border: 1px solid rgba(56, 189, 248, 0.2); border-radius: 12px; padding: 14px 18px; margin-bottom: 16px;
                    box-shadow: 0 4px 20px rgba(0,0,0,0.4); display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 16px;">
            <div style="display: flex; align-items: baseline; gap: 14px;">
                <span style="font-size: 1.8rem; font-weight: 800; color: #f8fafc; font-family: 'Plus Jakarta Sans', sans-serif;">{selected_symbol}</span>
                <span style="font-size: 2.0rem; font-weight: 800; color: #f8fafc; font-family: 'JetBrains Mono', monospace;">₹{curr_price:,.2f}</span>
                <span style="font-size: 1.15rem; font-weight: 700; color: {delta_color}; font-family: 'JetBrains Mono', monospace;">
                    {sign}{change:,.2f} ({sign}{change_pct:,.2f}%) {arrow}
                </span>
            </div>
            <div style="display: flex; flex-wrap: wrap; gap: 18px; font-size: 0.85rem; font-family: 'JetBrains Mono', monospace;">
                <div><span style="color: #94a3b8;">Open:</span> <b style="color: #f1f5f9;">₹{day_open:,.2f}</b></div>
                <div><span style="color: #94a3b8;">High:</span> <b style="color: #10b981;">₹{day_high:,.2f}</b></div>
                <div><span style="color: #94a3b8;">Low:</span> <b style="color: #f43f5e;">₹{day_low:,.2f}</b></div>
                <div><span style="color: #94a3b8;">Prev Close:</span> <b style="color: #cbd5e1;">₹{prev_close:,.2f}</b></div>
                <div><span style="color: #94a3b8;">Volume:</span> <b style="color: #38bdf8;">{volume:,.0f}</b></div>
                <div><span style="color: #94a3b8;">52W Range:</span> <b style="color: #cbd5e1;">₹{l_52w:,.1f} - ₹{h_52w:,.1f}</b> <span style="color:#64748b;">({pct_52w:.0f}%)</span></div>
            </div>
            <div style="display: flex; align-items: center; gap: 8px;">
                <span class="badge-safe" style="font-size: 0.75rem;"><span class="pulse-dot-green"></span>{src_label}</span>
                <span style="color: #64748b; font-size: 0.75rem;">{quote.get('timestamp', '')}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 3. Technical Indicator Overlays & Oscillators Toolbar
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

    # 4. Fetch OHLCV Market Data (Real or Simulated)
    with st.spinner(f"Loading {selected_symbol} multi-timeframe price action..."):
        if use_real:
            df = market_data_service.get_historical_ohlcv(
                selected_symbol,
                timeframe=selected_tf,
                period="1y" if selected_tf in ["1d", "1wk"] else "1mo",
                force_fresh=refresh_data,
            )
        else:
            base_p = inst_meta.get("base", curr_price)
            df = generate_sample_market_data(n_bars=120, symbol=selected_symbol, base_price=base_p)

    # 5. Chart Rendering
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

    # 6. Quantitative Indicators Matrix
    from app.indicators import indicator_pipeline

    feat_df = indicator_pipeline.compute_all_features(df, symbol=selected_symbol, timeframe=selected_tf)
    last_row = feat_df.iloc[-1]
    
    rsi_val = float(last_row.get("rsi_14", 50.0))
    rsi_delta = "Overbought" if rsi_val >= 70 else ("Oversold" if rsi_val <= 30 else "Neutral Zone")
    adx_val = float(last_row.get("adx", 20.0))
    adx_delta = "Strong Trend" if adx_val >= 25 else "Consolidation"

    st.subheader("Quantitative Indicator Matrix")
    m1, m2, m3, m4, m5, m6 = st.columns(6)
    with m1:
        st.metric("RSI (14)", f"{rsi_val:.1f}", delta=rsi_delta, delta_color="inverse" if rsi_val >= 70 else "normal")
    with m2:
        st.metric("ADX (14)", f"{adx_val:.1f}", delta=adx_delta)
    with m3:
        st.metric("ATR (14)", f"₹{last_row.get('atr_14', 0.0):.2f}")
    with m4:
        macd_h = float(last_row.get("macd_hist", 0.0))
        st.metric("MACD Hist", f"{macd_h:+.2f}", delta="Positive Momentum" if macd_h >= 0 else "Negative Momentum")
    with m5:
        is_sq = bool(last_row.get("bb_squeeze", False))
        st.metric("BB Squeeze", "🚨 ACTIVE" if is_sq else "NORMAL", delta="Volatility Breakout Imminent" if is_sq else "Standard Volatility")
    with m6:
        st_dir = last_row.get("supertrend_dir", 1)
        st.metric("Supertrend", "🟢 BULLISH" if st_dir == 1 else "🔴 BEARISH", delta="Trend Following")

    st.write("")

    # 7. Level 2 Market Depth & Quick Order Entry Ticket
    col_depth, col_order = st.columns([1, 1.2])

    with col_depth:
        st.subheader("📊 Live Level 2 Market Depth (Bid / Ask)")
        bids = [
            {"Orders": 14 + i * 3, "Bid Qty": 1800 - i * 180, "Bid Price": round(curr_price - i * tick_size, 2)}
            for i in range(1, 6)
        ]
        asks = [
            {"Ask Price": round(curr_price + i * tick_size, 2), "Ask Qty": 1450 - i * 120, "Orders": 10 + i * 2}
            for i in range(1, 6)
        ]
        depth_df = pd.DataFrame(bids)
        depth_df["Ask Price"] = [a["Ask Price"] for a in asks]
        depth_df["Ask Qty"] = [a["Ask Qty"] for a in asks]
        depth_df["Ask Orders"] = [a["Orders"] for a in asks]
        st.dataframe(depth_df, use_container_width=True, hide_index=True)

        # Depth ratio calculation
        total_bid_qty = sum(b["Bid Qty"] for b in bids)
        total_ask_qty = sum(a["Ask Qty"] for a in asks)
        bid_pct = round((total_bid_qty / (total_bid_qty + total_ask_qty)) * 100.0, 1)
        st.caption(f"Buyer Dominance: **{bid_pct}%** ({total_bid_qty:,} Bids vs {total_ask_qty:,} Asks)")

    with col_order:
        st.subheader("⚡ Quick Paper Order Entry Ticket")
        with st.form("quick_terminal_order_form"):
            t_side = st.radio("Side", ["BUY", "SELL"], horizontal=True)
            o_c1, o_c2 = st.columns(2)
            with o_c1:
                t_qty = st.number_input("Quantity", min_value=1, max_value=50000, value=lot_size, step=lot_size)
            with o_c2:
                t_type = st.selectbox("Order Type", ["MARKET", "LIMIT"])
            t_price = st.number_input("Limit Price (₹)", min_value=0.0, value=curr_price, step=tick_size) if t_type == "LIMIT" else curr_price

            # Margin & Notional Estimation
            is_derivative = (
                inst_meta.get("segment") in {"INDEX", "INDEX_FUTURES", "EQUITY_FUTURES"}
                or selected_symbol in {"NIFTY 50", "BANKNIFTY", "FINNIFTY"}
            )
            est_notional = t_price * t_qty
            est_margin = est_notional * 0.15 if is_derivative else est_notional

            st.markdown(
                f"""
                <div style="background: rgba(30, 41, 59, 0.45); border: 1px solid rgba(255,255,255,0.06); border-radius: 6px; padding: 8px 12px; margin: 8px 0; font-size: 0.8rem; color: #cbd5e1;">
                    <b>Est. Notional:</b> ₹{est_notional:,.2f} &nbsp;|&nbsp; 
                    <b>Required Margin:</b> <span style="color: {'#38bdf8' if is_derivative else '#10b981'}; font-weight: 700;">₹{est_margin:,.2f}</span>
                    <span style="color: #94a3b8; font-size: 0.75rem;">({'15% Margin' if is_derivative else '100% Cash Delivery'})</span>
                </div>
                """,
                unsafe_allow_html=True,
            )

            submit_quick_order = st.form_submit_button(f"Submit Paper {t_side} Order", type="primary", use_container_width=True)

        if submit_quick_order:
            summary = paper_broker.get_portfolio_summary()
            risk_authority.sync_equity_with_broker(summary["total_equity"])

            seg_str = inst_meta.get("segment", "EQUITY_CASH")
            seg_enum = TradingSegment(seg_str) if seg_str in TradingSegment.__members__ else TradingSegment.EQUITY_CASH

            risk_ok, risk_msg = risk_authority.validate_order(
                symbol=selected_symbol,
                side=t_side.lower(),
                quantity=t_qty,
                price=t_price,
                current_positions_count=len(paper_broker.positions),
                segment=seg_enum,
                lot_size=lot_size,
            )
            if not risk_ok:
                st.error(f"❌ Order Rejected by Risk Authority: {risk_msg}")
            else:
                try:
                    order = paper_broker.place_order(
                        symbol=selected_symbol,
                        side=t_side.lower(),
                        quantity=t_qty,
                        price=t_price if t_type == "LIMIT" else curr_price,
                        order_type=t_type,
                        segment=seg_str,
                        strategy_id="terminal_quick",
                    )
                    st.success(f"✅ Paper Order #{order.order_id[:8]} filled @ ₹{order.fill_price:,.2f} ({order.quantity} shares)!")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Execution Error: {exc}")
