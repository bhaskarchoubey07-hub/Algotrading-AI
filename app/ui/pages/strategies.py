"""Strategy Laboratory & Guided 5-Step Strategy Builder for AlgoTrade AI."""

import pandas as pd
import streamlit as st
from app.ensemble import AdaptiveStrategyEvaluator, get_strategy_cluster
from app.models import MarketRegime
from app.strategies import STRATEGIES
from app.ui.components import (
    generate_sample_market_data,
    render_global_header,
)


def render_strategies_page() -> None:
    render_global_header()

    st.markdown(
        """
        <div style="margin-bottom: 16px;">
            <h1 style="margin: 0; font-size: 2.1rem; font-weight: 800; color: #f8fafc; letter-spacing: -0.5px;">Strategy Laboratory & Builder</h1>
            <p style="margin: 4px 0 0 0; color: #94a3b8; font-size: 0.95rem;">Guided Strategy Studio • Quantitative Registry (18 Models) • Adaptive Validation Gates</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    tab_builder, tab_registry = st.tabs(["🛠️ Guided Strategy Builder", "📚 Production Strategy Registry (18)"])

    # TAB 1: GUIDED 5-STEP STRATEGY BUILDER
    with tab_builder:
        st.subheader("Guided Strategy Studio — 5 Step Workflow")
        st.caption("Construct, parameterize, validate, and launch systematic trading rules without coding.")

        # Step 1: Base Strategy Selection
        st.markdown("### Step 1: Select Strategy Archetype")
        s_c1, s_c2 = st.columns([1.5, 2])
        with s_c1:
            archetype = st.selectbox(
                "Strategy Family",
                [
                    "EMA 12/26 Trend Following",
                    "RSI (14) Mean Reversion",
                    "Donchian 20-Bar Channel Breakout",
                    "Supertrend Trend Continuation",
                    "Bollinger Band Squeeze Breakout",
                    "VWAP & Volume Intraday Reversal",
                    "Options Defined-Risk Vertical Spread",
                ],
            )
            target_symbol = st.selectbox("Target Instrument", ["NIFTY 50", "BANKNIFTY", "RELIANCE", "TCS", "INFY"])
            timeframe = st.selectbox("Execution Timeframe", ["1m", "5m", "15m", "1h", "1D"], index=2)
        with s_c2:
            st.markdown(
                f"""
                <div style="background: rgba(15, 23, 42, 0.85); border: 1px solid rgba(56, 189, 248, 0.2); border-radius: 10px; padding: 16px;">
                    <div style="color: #38bdf8; font-weight: 700; font-size: 1.05rem; margin-bottom: 6px;">Archetype Rationale: {archetype}</div>
                    <div style="color: #cbd5e1; font-size: 0.88rem; line-height: 1.5;">
                        Mathematically defined rules that trigger normalized trading signals. 
                        Targeted for <b>{target_symbol}</b> on <b>{timeframe}</b> timeframe.
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.markdown("---")

        # Step 2: Entry Rules
        st.markdown("### Step 2: Configure Entry Conditions")
        e_c1, e_c2, e_c3 = st.columns(3)
        with e_c1:
            fast_period = st.number_input("Fast Indicator Period", min_value=3, max_value=50, value=12)
        with e_c2:
            slow_period = st.number_input("Slow Indicator Period", min_value=10, max_value=200, value=26)
        with e_c3:
            filter_regime = st.checkbox("Require Trend Confirmation (ADX >= 25)", value=True)

        st.markdown("---")

        # Step 3: Exit & Risk Rules
        st.markdown("### Step 3: Configure Exit & Risk Rules")
        x_c1, x_c2, x_c3 = st.columns(3)
        with x_c1:
            sl_pct = st.number_input("Stop Loss (% of Price)", min_value=0.2, max_value=10.0, value=1.5, step=0.1)
        with x_c2:
            tp_pct = st.number_input("Take Profit (% of Price)", min_value=0.5, max_value=25.0, value=3.0, step=0.5)
        with x_c3:
            enable_trailing = st.checkbox("Enable Trailing ATR Stop", value=True)

        st.markdown("---")

        # Step 4: Position Sizing & Allocation
        st.markdown("### Step 4: Position Sizing & Risk Budget")
        p_c1, p_c2 = st.columns(2)
        with p_c1:
            sizing_mode = st.radio("Sizing Model", ["Fixed Quantity", "Risk Budget (% of Equity)"], horizontal=True)
            if sizing_mode == "Fixed Quantity":
                alloc_qty = st.number_input("Order Quantity", min_value=1, max_value=5000, value=25)
            else:
                alloc_risk = st.number_input("Max Risk per Trade (% Equity)", min_value=0.1, max_value=2.0, value=0.5, step=0.1)
        with p_c2:
            max_capital = st.number_input("Max Capital Allocation (₹)", min_value=10_000.0, max_value=1_000_000.0, value=100_000.0, step=10_000.0)

        st.markdown("---")

        # Step 5: Review, Validation & Launch Mode
        st.markdown("### Step 5: Plain-Language Summary & Launch")
        st.markdown(
            f"""
            <div style="background: rgba(17, 24, 39, 0.9); border: 1px solid rgba(255,255,255,0.08); border-radius: 10px; padding: 16px; margin-bottom: 16px;">
                <div style="font-weight: 700; color: #f8fafc; font-size: 1.05rem; margin-bottom: 8px;">Execution Manifesto:</div>
                <ul style="color: #cbd5e1; font-size: 0.9rem; line-height: 1.6; margin: 0; padding-left: 20px;">
                    <li><b>Strategy:</b> {archetype} on <b>{target_symbol} ({timeframe})</b></li>
                    <li><b>Entry Filter:</b> Periods ({fast_period}, {slow_period}) {'with ADX trend filter' if filter_regime else 'without ADX filter'}</li>
                    <li><b>Risk Control:</b> Stop Loss at {sl_pct}%, Profit Target at {tp_pct}% {'(Trailing ATR active)' if enable_trailing else ''}</li>
                    <li><b>Position Sizing:</b> {sizing_mode} capped at ₹{max_capital:,.2f} max capital</li>
                    <li><b>Compliance Boundary:</b> Runs exclusively in <b>Paper Trading Mode</b> (Simulated).</li>
                </ul>
            </div>
            """,
            unsafe_allow_html=True,
        )

        b_c1, b_c2 = st.columns(2)
        with b_c1:
            if st.button("🚀 Launch in Paper Trading", type="primary", use_container_width=True):
                st.success(f"Strategy '{archetype}' deployed to persistent Paper Trading engine!")
        with b_c2:
            if st.button("📊 Open in Backtest Laboratory", type="secondary", use_container_width=True):
                st.info("Configuration transferred to Backtesting Laboratory.")

    # TAB 2: PRODUCTION STRATEGY REGISTRY (18 MODELS)
    with tab_registry:
        st.subheader("Production Quantitative Strategies (18 Total)")
        strat_keys = list(STRATEGIES.keys())
        selected_key = st.selectbox(
            "Inspect Quantitative Model",
            strat_keys,
            format_func=lambda k: f"{STRATEGIES[k].strategy_id.upper()} ({getattr(STRATEGIES[k], 'category', 'general').capitalize()}) — v{STRATEGIES[k].version}",
        )

        strategy = STRATEGIES[selected_key]
        meta = strategy.metadata()

        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(f"**Strategy ID:** `{strategy.strategy_id}`")
            st.markdown(f"**Version:** `{strategy.version}`")
        with c2:
            st.markdown(f"**Category:** `{meta.get('category', 'trend').capitalize()}`")
            st.markdown(f"**Regime Suitability:** `{', '.join(meta.get('supported_regimes', ['any']))}`")
        with c3:
            st.markdown(f"**Execution Mode:** `Simulated Signals Only`")
            st.markdown(f"**Order Authority:** `Emits Normalized Signal Proposals`")

        st.info(f"**Description:** {strategy.description}")

        # Adaptive Validation Gates
        strat_cluster = get_strategy_cluster(strategy.strategy_id)
        validation = AdaptiveStrategyEvaluator.evaluate_strategy_eligibility(
            strategy_id=strategy.strategy_id,
            current_regime=MarketRegime.TRENDING_UP,
            eligible_regimes=meta.get("regimes", ["any"]),
        )

        st.subheader("Statistical Validation & Promotion Gates")
        v1, v2, v3, v4, v5 = st.columns(5)
        with v1:
            st.metric("Cluster", strat_cluster.upper())
        with v2:
            status_color = "🟢 PROMOTED" if validation.is_promoted else "🔴 DEMOTED"
            st.metric("Promotion Status", status_color)
        with v3:
            st.metric("OOS Expectancy", f"+{validation.out_of_sample_expectancy_bps:.1f} bps")
        with v4:
            st.metric("Profit Factor", f"{validation.profit_factor:.2f}")
        with v5:
            st.metric("Sample Size", f"{validation.sample_size} trades")

        # Test Signal Generation
        st.subheader(f"Generate Test Signal: {strategy.strategy_id}")
        t_col1, t_col2 = st.columns([1, 1])
        with t_col1:
            test_sym = st.selectbox("Test Symbol", ["NIFTY 50", "BANKNIFTY", "RELIANCE", "TCS", "INFY"], key="reg_sym")
        with t_col2:
            st.write("")
            st.write("")
            if st.button("Generate Strategy Signal", type="primary"):
                df_test = generate_sample_market_data(80, test_sym, 24500.0 if "NIFTY" in test_sym else 2800.0)
                sig = strategy.generate(df_test, test_sym)
                color = "green" if sig.direction == "long" else ("red" if sig.direction == "short" else "gray")
                st.markdown(f"**Signal Direction:** :{color}[### {sig.direction.upper()}] (Score: {sig.score:.2f})")
                st.write(f"**Rationale:** {sig.reason}")
