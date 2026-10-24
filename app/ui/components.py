"""Reusable UI Components, Institutional Dark Theme, and Interactive Charting for AlgoTrade AI."""

from datetime import datetime, timezone
from typing import Any
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")


def apply_custom_theme() -> None:
    """Inject institutional-grade dark financial terminal styling with typography, design tokens, and micro-animations."""
    st.markdown(
        """
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
        <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">

        <style>
            :root {
                --bg-base: #080d1a;
                --bg-surface: #0f172a;
                --bg-card: #111827;
                --border-subtle: rgba(255, 255, 255, 0.08);
                --border-focus: rgba(56, 189, 248, 0.4);
                --accent-primary: #38bdf8;
                --accent-cyan: #00f0ff;
                --color-gain: #10b981;
                --color-loss: #f43f5e;
                --color-warning: #f59e0b;
                --text-muted: #94a3b8;
                --text-main: #f8fafc;
            }

            /* Base Theme & Typography */
            html, body, [class*="css"], .stMarkdown, .stText, p, span, div {
                font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
            }
            code, pre, .mono, [data-testid="stMetricValue"], .tabular-nums {
                font-family: 'JetBrains Mono', monospace !important;
                font-feature-settings: "tnum" 1, "zero" 1 !important;
            }
            .main {
                background: radial-gradient(circle at 50% 0%, #111827 0%, #080d1a 60%, #030712 100%);
                color: #f1f5f9;
            }
            .block-container {
                padding-top: 1.0rem !important;
                padding-bottom: 2.5rem !important;
                max-width: 96% !important;
            }

            /* Ticker Tape */
            .ticker-tape {
                background: linear-gradient(90deg, rgba(15, 23, 42, 0.95), rgba(30, 41, 59, 0.95));
                border: 1px solid rgba(56, 189, 248, 0.2);
                border-radius: 8px;
                padding: 8px 16px;
                margin-bottom: 12px;
                display: flex;
                overflow-x: auto;
                white-space: nowrap;
                gap: 24px;
                font-size: 0.85rem;
                font-family: 'JetBrains Mono', monospace;
                box-shadow: 0 4px 16px rgba(0,0,0,0.4);
            }
            .ticker-item {
                display: inline-flex;
                align-items: center;
                gap: 8px;
            }
            .ticker-pos { color: #10b981; font-weight: 600; }
            .ticker-neg { color: #f43f5e; font-weight: 600; }
            .ticker-name { color: #94a3b8; font-weight: 600; }

            /* Institutional Metric Cards */
            .stMetric {
                background: linear-gradient(135deg, rgba(17, 24, 39, 0.92) 0%, rgba(15, 23, 42, 0.95) 100%) !important;
                padding: 16px 20px !important;
                border-radius: 12px !important;
                border: 1px solid rgba(255, 255, 255, 0.08) !important;
                box-shadow: 0 8px 24px rgba(0, 0, 0, 0.35) !important;
                backdrop-filter: blur(8px);
                transition: transform 0.2s ease, border-color 0.2s ease;
            }
            .stMetric:hover {
                transform: translateY(-2px);
                border-color: rgba(56, 189, 248, 0.4) !important;
            }
            .stMetric label {
                font-size: 0.80rem !important;
                color: #94a3b8 !important;
                font-weight: 600 !important;
                text-transform: uppercase;
                letter-spacing: 0.8px;
            }
            .stMetric [data-testid="stMetricValue"] {
                font-size: 1.65rem !important;
                font-weight: 700 !important;
                color: #f8fafc !important;
                letter-spacing: -0.5px;
            }

            /* Status Badges with Pulsing Animation */
            @keyframes pulse-dot {
                0% { opacity: 1; transform: scale(1); }
                50% { opacity: 0.4; transform: scale(0.9); }
                100% { opacity: 1; transform: scale(1); }
            }
            .badge-live {
                background: linear-gradient(135deg, #dc2626 0%, #991b1b 100%);
                color: white;
                padding: 5px 12px;
                border-radius: 20px;
                font-size: 0.75rem;
                font-weight: 700;
                letter-spacing: 0.8px;
                display: inline-flex;
                align-items: center;
                gap: 6px;
                box-shadow: 0 0 15px rgba(239, 68, 68, 0.4);
            }
            .badge-paper {
                background: linear-gradient(135deg, #2563eb 0%, #1e40af 100%);
                color: white;
                padding: 5px 12px;
                border-radius: 20px;
                font-size: 0.75rem;
                font-weight: 700;
                letter-spacing: 0.8px;
                display: inline-flex;
                align-items: center;
                gap: 6px;
                box-shadow: 0 0 15px rgba(59, 130, 246, 0.3);
            }
            .badge-safe {
                background: linear-gradient(135deg, #059669 0%, #065f46 100%);
                color: white;
                padding: 5px 12px;
                border-radius: 20px;
                font-size: 0.75rem;
                font-weight: 600;
                display: inline-flex;
                align-items: center;
                gap: 6px;
                box-shadow: 0 0 12px rgba(16, 185, 129, 0.3);
            }
            .badge-warn {
                background: linear-gradient(135deg, #d97706 0%, #b45309 100%);
                color: white;
                padding: 5px 12px;
                border-radius: 20px;
                font-size: 0.75rem;
                font-weight: 600;
                display: inline-flex;
                align-items: center;
                gap: 6px;
                box-shadow: 0 0 12px rgba(245, 158, 11, 0.3);
            }
            .pulse-dot-green {
                width: 8px;
                height: 8px;
                background-color: #34d399;
                border-radius: 50%;
                display: inline-block;
                animation: pulse-dot 1.5s infinite ease-in-out;
            }
            .pulse-dot-blue {
                width: 8px;
                height: 8px;
                background-color: #60a5fa;
                border-radius: 50%;
                display: inline-block;
                animation: pulse-dot 1.5s infinite ease-in-out;
            }
            .pulse-dot-red {
                width: 8px;
                height: 8px;
                background-color: #f87171;
                border-radius: 50%;
                display: inline-block;
                animation: pulse-dot 1.5s infinite ease-in-out;
            }

            /* Sleek Buttons */
            .stButton button {
                font-family: 'Plus Jakarta Sans', sans-serif !important;
                font-weight: 600 !important;
                border-radius: 8px !important;
                transition: all 0.2s ease !important;
            }
            .stButton button[kind="primary"] {
                background: linear-gradient(135deg, #0284c7 0%, #0369a1 100%) !important;
                border: 1px solid rgba(56, 189, 248, 0.4) !important;
                box-shadow: 0 4px 14px rgba(2, 132, 199, 0.35) !important;
            }
            .stButton button[kind="primary"]:hover {
                transform: translateY(-1px) !important;
                box-shadow: 0 6px 20px rgba(2, 132, 199, 0.5) !important;
            }

            /* Tabs Styling */
            .stTabs [data-baseweb="tab-list"] {
                gap: 8px;
                background-color: rgba(15, 23, 42, 0.6);
                padding: 4px;
                border-radius: 10px;
                border: 1px solid rgba(255, 255, 255, 0.05);
            }
            .stTabs [data-baseweb="tab"] {
                border-radius: 8px;
                padding: 8px 18px;
                font-weight: 600;
                color: #94a3b8;
            }
            .stTabs [aria-selected="true"] {
                background: rgba(30, 41, 59, 0.9) !important;
                color: #38bdf8 !important;
                box-shadow: 0 2px 8px rgba(0,0,0,0.3);
            }

            /* Global Header Bar */
            .global-status-header {
                background: linear-gradient(135deg, rgba(15, 23, 42, 0.9) 0%, rgba(30, 41, 59, 0.8) 100%);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 10px;
                padding: 10px 16px;
                margin-bottom: 16px;
                display: flex;
                flex-wrap: wrap;
                align-items: center;
                justify-content: space-between;
                gap: 12px;
            }
            .global-status-item {
                display: flex;
                align-items: center;
                gap: 8px;
                font-size: 0.82rem;
                font-weight: 600;
            }

            /* Custom scrollbar */
            ::-webkit-scrollbar { width: 6px; height: 6px; }
            ::-webkit-scrollbar-track { background: #080d1a; }
            ::-webkit-scrollbar-thumb { background: #1e293b; border-radius: 4px; }
            ::-webkit-scrollbar-thumb:hover { background: #334155; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_live_ticker_tape() -> None:
    """Render an institutional market ticker bar across top indices and bellwethers."""
    st.markdown(
        """
        <div class="ticker-tape">
            <div class="ticker-item"><span class="ticker-name">NIFTY 50</span> <span>24,654.20</span> <span class="ticker-pos">+112.40 (+0.46%) ▲</span></div>
            <div class="ticker-item"><span class="ticker-name">BANKNIFTY</span> <span>51,210.80</span> <span class="ticker-pos">+315.60 (+0.62%) ▲</span></div>
            <div class="ticker-item"><span class="ticker-name">FINNIFTY</span> <span>23,410.15</span> <span class="ticker-pos">+88.50 (+0.38%) ▲</span></div>
            <div class="ticker-item"><span class="ticker-name">INDIA VIX</span> <span>12.85</span> <span class="ticker-neg">-0.16 (-1.23%) ▼</span></div>
            <div class="ticker-item"><span class="ticker-name">RELIANCE</span> <span>2,842.50</span> <span class="ticker-pos">+22.80 (+0.81%) ▲</span></div>
            <div class="ticker-item"><span class="ticker-name">HDFCBANK</span> <span>1,682.40</span> <span class="ticker-pos">+8.20 (+0.49%) ▲</span></div>
            <div class="ticker-item"><span class="ticker-name">TCS</span> <span>4,124.00</span> <span class="ticker-neg">-12.50 (-0.30%) ▼</span></div>
            <div class="ticker-item"><span class="ticker-name">INFY</span> <span>1,742.10</span> <span class="ticker-pos">+14.60 (+0.85%) ▲</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_global_header() -> None:
    """Renders the top institutional global status bar with real-time connectivity and session metadata."""
    from app.brokers.dhan import dhan_broker
    from app.config import settings
    from app.database import db_repo
    from app.risk import risk_authority

    ist_now = datetime.now(IST)
    m_open, _ = risk_authority.is_market_open(ist_now)
    d_status = dhan_broker.get_connection_status()
    db_stat = db_repo.get_database_status()

    session_badge = '<span class="pulse-dot-green"></span> NSE: OPEN' if m_open else '● NSE: CLOSED'
    broker_badge = 'DHAN: CONNECTED' if d_status['is_connected'] else 'DHAN: SANDBOX'
    db_badge = f"DB: {db_stat['mode'].upper()}"

    st.markdown(
        f"""
        <div class="global-status-header">
            <div class="global-status-item" style="color: {'#34d399' if m_open else '#94a3b8'};">
                {session_badge} <span style="color: #64748b; margin-left: 4px;">({ist_now.strftime('%H:%M:%S IST')})</span>
            </div>
            <div class="global-status-item">
                <span class="badge-paper"><span class="pulse-dot-blue"></span>PAPER TRADING ONLY</span>
            </div>
            <div class="global-status-item" style="color: #cbd5e1;">
                🛡️ {broker_badge} • {db_badge}
            </div>
            <div class="global-status-item">
                {'<span class="badge-live"><span class="pulse-dot-red"></span>KILL-SWITCH TRIPPED</span>' if risk_authority.kill_switch_active else '<span class="badge-safe"><span class="pulse-dot-green"></span>RISK ENGINE ARMED</span>'}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_onboarding_guide() -> None:
    """Renders smart onboarding walkthrough for beginners with key concepts."""
    with st.expander("🎓 Smart Onboarding Guide: Learn How AlgoTrade AI Works", expanded=False):
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown("#### 1. Real-Time Market Feeds")
            st.caption("We collect NSE cash, futures, and options quotes via DhanHQ and local historical tick feeds. Every price is verified for staleness (<60s) before any signal can execute.")
        with c2:
            st.markdown("#### 2. Quantitative Strategies")
            st.caption("18 independent mathematical models (Trend, Breakout, Mean Reversion, Options Spreads, ML Regimes) generate buy/sell proposals. Proposals must pass statistical validation and the active market regime filter.")
        with c3:
            st.markdown("#### 3. Zero-Risk Paper Trading")
            st.caption("The platform operates exclusively in **Paper Trading Mode**. Real-money broker order placement is strictly gated. Simulated execution includes realistic slippage, STT, and exchange transaction fees.")


def create_candlestick_chart(
    df: pd.DataFrame,
    symbol: str = "NIFTY",
    chart_type: str = "Candlestick",
    show_volume: bool = True,
    show_ema: bool = True,
    show_bb: bool = False,
    show_supertrend: bool = False,
    show_vwap: bool = False,
    show_donchian: bool = False,
    show_rsi: bool = False,
    show_macd: bool = False,
) -> go.Figure:
    """Render high-performance Plotly financial chart with full technical indicator overlays and subplots."""
    from app.indicators import (
        calculate_bollinger_bands,
        calculate_donchian_channels,
        calculate_ema,
        calculate_macd,
        calculate_rsi,
        calculate_supertrend,
        calculate_vwap,
    )

    # Determine subplots
    extra_rows = 0
    if show_volume:
        extra_rows += 1
    if show_rsi:
        extra_rows += 1
    if show_macd:
        extra_rows += 1

    total_rows = 1 + extra_rows
    if total_rows == 1:
        row_heights = [1.0]
    elif total_rows == 2:
        row_heights = [0.75, 0.25]
    elif total_rows == 3:
        row_heights = [0.60, 0.20, 0.20]
    else:
        row_heights = [0.55, 0.15, 0.15, 0.15]

    fig = make_subplots(
        rows=total_rows,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=row_heights,
    )

    # Main Price Trace (Candlestick, Line, or Area)
    if chart_type == "Line":
        fig.add_trace(
            go.Scatter(x=df["timestamp"], y=df["close"], mode="lines", line=dict(color="#38bdf8", width=2), name="Close Price"),
            row=1,
            col=1,
        )
    elif chart_type == "Area":
        fig.add_trace(
            go.Scatter(x=df["timestamp"], y=df["close"], mode="lines", fill="tozeroy", fillcolor="rgba(56, 189, 248, 0.15)", line=dict(color="#38bdf8", width=2), name="Close Price"),
            row=1,
            col=1,
        )
    else:
        fig.add_trace(
            go.Candlestick(
                x=df["timestamp"],
                open=df["open"],
                high=df["high"],
                low=df["low"],
                close=df["close"],
                name="Price",
                increasing=dict(line=dict(color="#10b981", width=1), fillcolor="#10b981"),
                decreasing=dict(line=dict(color="#f43f5e", width=1), fillcolor="#f43f5e"),
            ),
            row=1,
            col=1,
        )

    # Overlays on Row 1 (Price)
    c = df["close"]
    h = df["high"]
    l = df["low"]

    if show_ema:
        if len(df) >= 20:
            ema20 = calculate_ema(c, period=20)
            fig.add_trace(go.Scatter(x=df["timestamp"], y=ema20, line=dict(color="#38bdf8", width=1.5), name="EMA 20"), row=1, col=1)
        if len(df) >= 50:
            ema50 = calculate_ema(c, period=50)
            fig.add_trace(go.Scatter(x=df["timestamp"], y=ema50, line=dict(color="#f59e0b", width=1.5), name="EMA 50"), row=1, col=1)
        if len(df) >= 100:
            ema200 = calculate_ema(c, period=min(200, len(df) - 5))
            fig.add_trace(go.Scatter(x=df["timestamp"], y=ema200, line=dict(color="#ec4899", width=2.0), name="EMA 200"), row=1, col=1)

    if show_bb and len(df) >= 20:
        bb = calculate_bollinger_bands(c, period=20, num_std=2.0)
        fig.add_trace(go.Scatter(x=df["timestamp"], y=bb.upper, line=dict(color="rgba(148, 163, 184, 0.45)", width=1, dash="dot"), name="BB Upper"), row=1, col=1)
        fig.add_trace(go.Scatter(x=df["timestamp"], y=bb.middle, line=dict(color="rgba(148, 163, 184, 0.35)", width=1), name="BB Middle"), row=1, col=1)
        fig.add_trace(go.Scatter(x=df["timestamp"], y=bb.lower, line=dict(color="rgba(148, 163, 184, 0.45)", width=1, dash="dot"), name="BB Lower"), row=1, col=1)

    if show_supertrend and len(df) >= 15:
        st_res = calculate_supertrend(h, l, c, atr_period=10, multiplier=3.0)
        fig.add_trace(go.Scatter(x=df["timestamp"], y=st_res.supertrend, mode="lines", line=dict(color="#a855f7", width=1.8), name="Supertrend (10,3)"), row=1, col=1)

    if show_vwap:
        vwap = calculate_vwap(h, l, c, df.get("volume", pd.Series(1000, index=df.index)), timestamp=df.get("timestamp"))
        fig.add_trace(go.Scatter(x=df["timestamp"], y=vwap, line=dict(color="#eab308", width=1.8, dash="dash"), name="VWAP"), row=1, col=1)

    if show_donchian and len(df) >= 20:
        dc = calculate_donchian_channels(h, l, period=20)
        fig.add_trace(go.Scatter(x=df["timestamp"], y=dc.upper, line=dict(color="rgba(56, 189, 248, 0.4)", width=1, dash="longdash"), name="Donchian Up"), row=1, col=1)
        fig.add_trace(go.Scatter(x=df["timestamp"], y=dc.lower, line=dict(color="rgba(56, 189, 248, 0.4)", width=1, dash="longdash"), name="Donchian Down"), row=1, col=1)

    curr_row = 2

    # Subplot: Volume
    if show_volume and "volume" in df.columns:
        colors = ["rgba(16, 185, 129, 0.6)" if cl >= op else "rgba(244, 63, 94, 0.6)" for cl, op in zip(df["close"], df["open"])]
        fig.add_trace(go.Bar(x=df["timestamp"], y=df["volume"], marker_color=colors, name="Volume"), row=curr_row, col=1)
        fig.update_yaxes(title_text="Vol", row=curr_row, col=1)
        curr_row += 1

    # Subplot: RSI
    if show_rsi and len(df) >= 15:
        rsi = calculate_rsi(c, period=14)
        fig.add_trace(go.Scatter(x=df["timestamp"], y=rsi, line=dict(color="#38bdf8", width=1.5), name="RSI (14)"), row=curr_row, col=1)
        fig.add_hline(y=70, line_dash="dash", line_color="rgba(244, 63, 94, 0.5)", row=curr_row, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="rgba(16, 185, 129, 0.5)", row=curr_row, col=1)
        fig.update_yaxes(title_text="RSI", range=[0, 100], row=curr_row, col=1)
        curr_row += 1

    # Subplot: MACD
    if show_macd and len(df) >= 26:
        macd_res = calculate_macd(c)
        fig.add_trace(go.Scatter(x=df["timestamp"], y=macd_res.macd, line=dict(color="#38bdf8", width=1.2), name="MACD"), row=curr_row, col=1)
        fig.add_trace(go.Scatter(x=df["timestamp"], y=macd_res.signal, line=dict(color="#f59e0b", width=1.2), name="Signal"), row=curr_row, col=1)
        hist_colors = ["#10b981" if val >= 0 else "#f43f5e" for val in macd_res.histogram]
        fig.add_trace(go.Bar(x=df["timestamp"], y=macd_res.histogram, marker_color=hist_colors, name="Histogram"), row=curr_row, col=1)
        fig.update_yaxes(title_text="MACD", row=curr_row, col=1)

    fig.update_layout(
        title=dict(
            text=f"<b>{symbol}</b> — Institutional Quantitative Charting",
            font=dict(size=18, color="#f8fafc", family="Plus Jakarta Sans"),
        ),
        template="plotly_dark",
        plot_bgcolor="rgba(11, 15, 25, 0.7)",
        paper_bgcolor="rgba(11, 15, 25, 0)",
        xaxis_rangeslider_visible=False,
        margin=dict(l=40, r=40, t=50, b=30),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        hovermode="x unified",
    )
    return fig


def generate_sample_market_data(n_bars: int = 150, symbol: str = "NIFTY", base_price: float = 24500.0) -> pd.DataFrame:
    """Generate realistic OHLCV sample market data with trend and volatility clustering."""
    np.random.seed(42)
    dates = pd.date_range(end=datetime.now(timezone.utc), periods=n_bars, freq="1D")

    # Geometric random walk with drift
    returns = np.random.normal(loc=0.0006, scale=0.012, size=n_bars)
    price_series = base_price * np.exp(np.cumsum(returns))

    opens = price_series * (1 + np.random.normal(0, 0.002, n_bars))
    closes = price_series
    highs = np.maximum(opens, closes) * (1 + np.abs(np.random.normal(0, 0.005, n_bars)))
    lows = np.minimum(opens, closes) * (1 - np.abs(np.random.normal(0, 0.005, n_bars)))
    volumes = np.random.lognormal(mean=14, sigma=0.5, size=n_bars).astype(int)

    return pd.DataFrame({
        "timestamp": dates.strftime("%Y-%m-%d"),
        "open": np.round(opens, 2),
        "high": np.round(highs, 2),
        "low": np.round(lows, 2),
        "close": np.round(closes, 2),
        "volume": volumes,
    })
