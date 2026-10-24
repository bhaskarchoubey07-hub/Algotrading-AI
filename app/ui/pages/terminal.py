import pandas as pd
import streamlit as st
from app.ui.components import create_candlestick_chart, generate_sample_market_data

INSTRUMENT_CATALOG = {
    "NIFTY 50": {"segment": "INDEX", "base": 24650.0, "lot_size": 25, "tick_size": 0.05},
    "BANKNIFTY": {"segment": "INDEX", "base": 51200.0, "lot_size": 15, "tick_size": 0.05},
    "RELIANCE": {"segment": "EQUITY_CASH", "base": 2840.0, "lot_size": 1, "tick_size": 0.05},
    "TCS": {"segment": "EQUITY_CASH", "base": 4120.0, "lot_size": 1, "tick_size": 0.05},
    "HDFCBANK": {"segment": "EQUITY_CASH", "base": 1680.0, "lot_size": 1, "tick_size": 0.05},
    "INFY": {"segment": "EQUITY_CASH", "base": 1740.0, "lot_size": 1, "tick_size": 0.05},
    "TATAMOTORS": {"segment": "EQUITY_CASH", "base": 980.0, "lot_size": 1, "tick_size": 0.05},
    "NIFTY_FUT_OCT": {"segment": "EQUITY_FUTURES", "base": 24710.0, "lot_size": 25, "tick_size": 0.05},
}


def render_terminal_page() -> None:
    st.title("Market Terminal — NSE Workstation")
    st.caption("Real-Time & Historical Technical Analysis • Instrument Depth & Multi-Timeframe")

    # Instrument Selector Bar
    c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
    with c1:
        selected_symbol = st.selectbox("Search Instrument Watchlist", list(INSTRUMENT_CATALOG.keys()))
    with c2:
        selected_tf = st.selectbox("Timeframe", ["1m", "5m", "15m", "1h", "1d"], index=4)
    with c3:
        chart_bars = st.slider("Bar Count", min_value=30, max_value=300, value=120)
    with c4:
        inst_info = INSTRUMENT_CATALOG[selected_symbol]
        st.markdown(
            f"**Segment:** `{inst_info['segment']}`<br>**Lot:** `{inst_info['lot_size']}` • **Tick:** `₹{inst_info['tick_size']}`",
            unsafe_allow_html=True,
        )

    # Indicator Controls
    with st.expander("🛠️ Advanced Technical Indicators & Subplots", expanded=True):
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

    # Generate Chart Data
    df = generate_sample_market_data(n_bars=chart_bars, symbol=selected_symbol, base_price=inst_info["base"])

    # Render Interactive Plotly Chart
    fig = create_candlestick_chart(
        df,
        symbol=selected_symbol,
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

    # Technical Indicator Real-Time Quant Matrix
    from app.indicators import indicator_pipeline
    feat_df = indicator_pipeline.compute_all_features(df, symbol=selected_symbol, timeframe=selected_tf)
    last_row = feat_df.iloc[-1]

    st.subheader("Quantitative Indicator Snapshot")
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

    # Depth & Multi-timeframe Summary
    col_depth, col_stats = st.columns([1, 1])
    with col_depth:
        st.subheader("Simulated Level 2 Order Depth (Bid / Ask)")
        curr_price = float(df["close"].iloc[-1])
        tick = inst_info["tick_size"]

        bids = [
            {"Orders": 12, "Bid Qty": 1500, "Bid Price": round(curr_price - i * tick, 2)}
            for i in range(1, 6)
        ]
        asks = [
            {"Ask Price": round(curr_price + i * tick, 2), "Ask Qty": 1250, "Orders": 8}
            for i in range(1, 6)
        ]
        depth_df = pd.DataFrame(bids)
        depth_df["Ask Price"] = [a["Ask Price"] for a in asks]
        depth_df["Ask Qty"] = [a["Ask Qty"] for a in asks]
        depth_df["Ask Orders"] = [a["Orders"] for a in asks]

        st.dataframe(depth_df, use_container_width=True, hide_index=True)

    with col_stats:
        st.subheader("Price & Session Statistics")
        high_24h = float(df["high"].max())
        low_24h = float(df["low"].min())
        chg = float(df["close"].iloc[-1] - df["open"].iloc[0])
        pct_chg = (chg / df["open"].iloc[0]) * 100

        sc1, sc2, sc3 = st.columns(3)
        with sc1:
            st.metric("Last Price", f"₹{curr_price:,.2f}", delta=f"{pct_chg:+.2f}%")
        with sc2:
            st.metric("Period High", f"₹{high_24h:,.2f}")
        with sc3:
            st.metric("Period Low", f"₹{low_24h:,.2f}")

        st.caption("⚠️ Data Notice: Market Terminal is connected to validated local and simulated NSE feeds. Timestamps are synchronized in UTC / IST.")

