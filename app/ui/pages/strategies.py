"""Strategy Laboratory & Guided Quantitative Studio for AlgoTrade AI.

Provides:
- 5-Step Guided Strategy Builder with direct Paper & Backtest deployment.
- Production Strategy Registry across 18 systematic quantitative models.
- Interactive Parameter Configuration.
- Statistical Validation Gates & Wilson Confidence Intervals.
- Live Signal Explanation & Execution Rationale.
- One-Click Backtest Execution directly within the Laboratory.
- Durable Paper Trading Eligibility Controls.
"""

from datetime import datetime, timezone
import pandas as pd
import streamlit as st

from app.adaptive import health_manager
from app.alerts.manager import alert_manager
from app.backtest import AdvancedBacktestEngine
from app.database.supabase_client import db_repo
from app.ensemble import AdaptiveStrategyEvaluator, get_strategy_cluster
from app.models import AlertCategory, AlertSeverity, MarketRegime
from app.strategies import STRATEGIES
from app.ui.components import (
    generate_sample_market_data,
    render_global_header,
)

ARCHETYPE_MAP = {
    "EMA 12/26 Trend Following": "ema_trend",
    "RSI (14) Mean Reversion": "rsi_mean_reversion",
    "Donchian 20-Bar Breakout": "donchian_breakout",
    "Supertrend Trend Continuation": "supertrend",
    "Bollinger Squeeze Breakout": "bollinger_squeeze_breakout",
    "VWAP & Volume Intraday": "vwap_volume_intraday",
    "EMA 200 Long-Term Trend": "ema200_macd_trend",
    "ADX Trend Continuation": "adx_trend_continuation",
    "RSI & Bollinger Range": "rsi_bollinger_range",
    "ATR Breakout Exit System": "atr_breakout_exit",
    "Multi-Timeframe Swing": "mtf_swing_trading",
    "Options Vertical Spread": "options_vertical_spread",
}


def render_strategies_page() -> None:
    render_global_header()

    st.markdown(
        """
        <div style="margin-bottom: 16px;">
            <h1 style="margin: 0; font-size: 2.1rem; font-weight: 800; color: #f8fafc; letter-spacing: -0.5px;">Strategy Laboratory & Builder</h1>
            <p style="margin: 4px 0 0 0; color: #94a3b8; font-size: 0.95rem;">Quantitative Model Studio • Production Registry (18 Models) • Statistical Gates & Paper Controls</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    tab_builder, tab_registry = st.tabs(["🛠️ Guided Strategy Builder", "📚 Production Strategy Registry (18 Models)"])

    # =========================================================================
    # TAB 1: GUIDED 5-STEP STRATEGY BUILDER
    # =========================================================================
    with tab_builder:
        st.subheader("Guided Strategy Studio — 5 Step Systematic Workflow")
        st.caption("Construct, parameterize, validate, and launch quantitative trading rules with verifiable execution.")

        # Step 1: Base Strategy Selection
        st.markdown("### Step 1: Select Strategy Archetype")
        s_c1, s_c2 = st.columns([1.5, 2])
        with s_c1:
            archetype_label = st.selectbox("Strategy Family", list(ARCHETYPE_MAP.keys()))
            target_symbol = st.selectbox("Target Instrument", ["NIFTY 50", "BANKNIFTY", "RELIANCE", "TCS", "INFY"])
            timeframe = st.selectbox("Execution Timeframe", ["5m", "15m", "1h", "1d"], index=1)
        with s_c2:
            arch_key = ARCHETYPE_MAP[archetype_label]
            selected_strat_obj = STRATEGIES.get(arch_key, STRATEGIES["ema_trend"])
            st.markdown(
                f"""
                <div style="background: rgba(15, 23, 42, 0.85); border: 1px solid rgba(56, 189, 248, 0.25); border-radius: 10px; padding: 14px 16px;">
                    <div style="color: #38bdf8; font-weight: 700; font-size: 1.05rem; margin-bottom: 6px;">Archetype: {archetype_label}</div>
                    <div style="color: #cbd5e1; font-size: 0.88rem; line-height: 1.5;">
                        <b>Description:</b> {selected_strat_obj.description}<br>
                        <b>Target Instrument:</b> {target_symbol} • <b>Timeframe:</b> {timeframe}<br>
                        <b>Regime Suitability:</b> {', '.join(selected_strat_obj.metadata().get('supported_regimes', ['any']))}
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
            fast_period = st.number_input("Fast Signal Period", min_value=3, max_value=50, value=12)
        with e_c2:
            slow_period = st.number_input("Slow Filter Period", min_value=10, max_value=200, value=26)
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
                    <li><b>Strategy Archetype:</b> {archetype_label} on <b>{target_symbol} ({timeframe})</b></li>
                    <li><b>Entry Parameters:</b> Fast Period: {fast_period}, Slow Period: {slow_period} {'(ADX trend filter required)' if filter_regime else '(No ADX filter)'}</li>
                    <li><b>Risk Parameters:</b> Stop Loss: {sl_pct}%, Profit Target: {tp_pct}% {'(Trailing ATR active)' if enable_trailing else ''}</li>
                    <li><b>Position Sizing:</b> {sizing_mode} capped at ₹{max_capital:,.2f}</li>
                    <li><b>Execution Boundary:</b> Runs strictly in <b>Paper Trading Mode</b> (Simulated Fills).</li>
                </ul>
            </div>
            """,
            unsafe_allow_html=True,
        )

        b_c1, b_c2 = st.columns(2)
        with b_c1:
            if st.button("🚀 Deploy to Paper Trading Engine", type="primary", use_container_width=True):
                # Save strategy version & parameters to persistent storage
                configured_params = {
                    "fast_period": fast_period,
                    "slow_period": slow_period,
                    "require_adx": filter_regime,
                    "stop_loss_pct": sl_pct,
                    "take_profit_pct": tp_pct,
                    "max_capital": max_capital,
                    "target_symbol": target_symbol,
                    "timeframe": timeframe,
                }
                db_repo.save_strategy_version(
                    strategy_id=arch_key,
                    version=selected_strat_obj.version,
                    enabled=True,
                    parameters=configured_params,
                )
                db_repo.log_audit(
                    "trader",
                    "DEPLOY_STRATEGY_TO_PAPER",
                    "strategy",
                    arch_key,
                    configured_params,
                )
                alert_manager.dispatch(
                    AlertCategory.STRATEGY,
                    AlertSeverity.INFO,
                    f"Strategy Deployed: {archetype_label}",
                    f"Activated on {target_symbol} ({timeframe}) in Paper Trading engine.",
                )
                st.session_state["deployed_paper_strategy"] = arch_key
                st.success(f"Strategy '{archetype_label}' successfully registered and deployed to persistent Paper Trading engine!")

        with b_c2:
            if st.button("📊 Open in Backtest Laboratory", type="secondary", use_container_width=True):
                st.session_state["backtest_prefill"] = {
                    "strategy_id": arch_key,
                    "symbol": target_symbol,
                    "initial_capital": max_capital,
                    "parameters": {
                        "fast_period": fast_period,
                        "slow_period": slow_period,
                    },
                }
                st.info(f"Configuration for '{archetype_label}' prefilled! Navigate to 'Backtesting Laboratory' to execute.")

    # =========================================================================
    # TAB 2: PRODUCTION STRATEGY REGISTRY (18 MODELS)
    # =========================================================================
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
        strat_cluster = get_strategy_cluster(strategy.strategy_id)
        current_health = health_manager.get_state(strategy.strategy_id)

        # 1. Strategy Specifications Card
        st.markdown(
            f"""
            <div style="background: rgba(15, 23, 42, 0.7); border: 1px solid rgba(255,255,255,0.08); border-radius: 10px; padding: 16px; margin-bottom: 16px;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                    <span style="font-size: 1.25rem; font-weight: 700; color: #f8fafc;">{strategy.strategy_id.upper()}</span>
                    <span class="badge-safe"><span class="pulse-dot-green"></span>HEALTH: {current_health.value.upper()}</span>
                </div>
                <div style="color: #cbd5e1; font-size: 0.9rem; line-height: 1.5; margin-bottom: 12px;">
                    {strategy.description}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # 2. Metadata Columns
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(f"**Strategy ID:** `{strategy.strategy_id}`")
            st.markdown(f"**Version:** `{strategy.version}`")
            st.markdown(f"**Cluster / Family:** `{strat_cluster.capitalize()}`")
        with c2:
            st.markdown(f"**Supported Segments:** `{', '.join(meta.get('supported_segments', ['EQUITY_CASH', 'INDEX']))}`")
            st.markdown(f"**Supported Timeframes:** `{', '.join(meta.get('supported_timeframes', ['5m', '15m', '1h', '1d']))}`")
            st.markdown(f"**Regime Eligibility:** `{', '.join(meta.get('supported_regimes', ['any']))}`")
        with c3:
            st.markdown(f"**Required Data:** `{', '.join(meta.get('required_data', ['OHLCV bars']))}`")
            st.markdown(f"**Entry / Exit Logic:** `{meta.get('entry_exit_logic', 'Systematic indicator signals')}`")
            st.markdown(f"**Validation Status:** `{meta.get('validation_status', 'active').upper()}`")

        st.markdown("---")

        # 3. Paper Trading Eligibility Toggle & Parameter Tuner
        st.subheader("Execution Controls & Dynamic Parameters")
        p_col1, p_col2 = st.columns([1, 1])

        with p_col1:
            st.markdown("#### Paper Trading Eligibility")
            is_enabled = st.checkbox(
                f"Enable {strategy.strategy_id} for Automated Paper Trading",
                value=True,
                key=f"paper_enable_{strategy.strategy_id}",
            )
            if st.button("Save Eligibility State", key=f"btn_save_elig_{strategy.strategy_id}"):
                db_repo.save_strategy_version(
                    strategy_id=strategy.strategy_id,
                    version=strategy.version,
                    enabled=is_enabled,
                )
                db_repo.log_audit("trader", "UPDATE_STRATEGY_ELIGIBILITY", "strategy", strategy.strategy_id, {"enabled": is_enabled})
                status_txt = "ENABLED" if is_enabled else "DISABLED"
                st.success(f"Strategy {strategy.strategy_id} paper trading status set to {status_txt}.")

        with p_col2:
            st.markdown("#### Parameter Configuration")
            with st.expander("🛠️ Inspect / Tune Model Parameters", expanded=False):
                current_params = meta.get("parameters", {})
                param_updates = {}
                if current_params:
                    for p_name, p_val in current_params.items():
                        if isinstance(p_val, int):
                            param_updates[p_name] = st.number_input(f"{p_name}", value=p_val, key=f"p_{strategy.strategy_id}_{p_name}")
                        elif isinstance(p_val, float):
                            param_updates[p_name] = st.number_input(f"{p_name}", value=p_val, step=0.1, key=f"p_{strategy.strategy_id}_{p_name}")
                        elif isinstance(p_val, bool):
                            param_updates[p_name] = st.checkbox(f"{p_name}", value=p_val, key=f"p_{strategy.strategy_id}_{p_name}")
                        else:
                            param_updates[p_name] = st.text_input(f"{p_name}", value=str(p_val), key=f"p_{strategy.strategy_id}_{p_name}")
                else:
                    st.caption("No tunable parameters exposed for this model.")

                if st.button("Apply Parameter Updates", key=f"btn_tune_{strategy.strategy_id}"):
                    if hasattr(strategy, "set_parameters"):
                        strategy.set_parameters(param_updates)
                    db_repo.save_strategy_version(strategy.strategy_id, strategy.version, enabled=True, parameters=param_updates)
                    st.success("Parameters updated successfully.")

        st.markdown("---")

        # 4. Statistical Validation Gates & Confidence Intervals
        validation = AdaptiveStrategyEvaluator.evaluate_strategy_eligibility(
            strategy_id=strategy.strategy_id,
            current_regime=MarketRegime.TRENDING_UP,
            eligible_regimes=meta.get("regimes", ["any"]),
        )

        st.subheader("Statistical Validation & Promotion Gates")
        v1, v2, v3, v4, v5 = st.columns(5)
        with v1:
            st.metric("Primary Cluster", strat_cluster.upper())
        with v2:
            status_text = "🟢 PROMOTED" if validation.is_promoted else "🔴 DEMOTED"
            st.metric("Validation Gate", status_text)
        with v3:
            st.metric("OOS Expectancy", f"+{validation.out_of_sample_expectancy_bps:.1f} bps")
        with v4:
            st.metric("Profit Factor", f"{validation.profit_factor:.2f}")
        with v5:
            st.metric("Sample Size", f"{validation.sample_size} trades")

        st.markdown("---")

        # 5. One-Click Strategy Backtest Launch
        st.subheader(f"Launch Chronological Backtest: {strategy.strategy_id.upper()}")
        bk_c1, bk_c2, bk_c3 = st.columns([1.5, 1, 1])
        with bk_c1:
            bk_sym = st.selectbox("Backtest Instrument", ["NIFTY 50", "BANKNIFTY", "RELIANCE", "TCS", "INFY"], key="lab_bk_sym")
        with bk_c2:
            bk_bars = st.slider("Simulation Bars", min_value=60, max_value=400, value=150, key="lab_bk_bars")
        with bk_c3:
            st.write("")
            st.write("")
            run_lab_bk = st.button("▶ Run Strategy Backtest", type="primary", use_container_width=True)

        if run_lab_bk:
            with st.spinner(f"Simulating bar-by-bar backtest for {strategy.strategy_id} on {bk_sym}..."):
                base_p = 24500.0 if "NIFTY" in bk_sym else 2800.0
                df_bk = generate_sample_market_data(n_bars=bk_bars, symbol=bk_sym, base_price=base_p)
                engine = AdvancedBacktestEngine(initial_capital=1_000_000.0, slippage_bps=3.0, enable_statutory_charges=True)
                metrics = engine.run(df_bk, strategy, symbol=bk_sym)

                st.markdown("##### Backtest Results Summary")
                res1, res2, res3, res4, res5 = st.columns(5)
                res1.metric("Net Profit / Loss", f"₹{metrics.net_pnl:+,.2f}")
                res2.metric("Win Rate", f"{metrics.win_rate_pct:.1f}%", delta=f"{metrics.winning_trades}W / {metrics.losing_trades}L")
                res3.metric("Profit Factor", f"{metrics.profit_factor:.2f}" if metrics.profit_factor else "N/A")
                res4.metric("Max Drawdown", f"{metrics.max_drawdown_pct:.2f}%", delta_color="inverse")
                res5.metric("Sharpe Ratio", f"{metrics.sharpe_ratio:.2f}")

                # Save backtest run to db_repo
                db_repo.save_backtest_run(
                    strategy_id=strategy.strategy_id,
                    strategy_version=strategy.version,
                    symbol=bk_sym,
                    timeframe="1d",
                    initial_capital=1_000_000.0,
                    parameters=strategy.metadata().get("parameters", {}),
                    metrics=metrics.to_dict() if hasattr(metrics, "to_dict") else {},
                    equity_curve=metrics.equity_curve,
                    trades_log=[t.to_dict() if hasattr(t, "to_dict") else t for t in metrics.trades_log],
                )
                st.caption("✅ Backtest run persisted to experiment history.")

        st.markdown("---")

        # 6. Test Signal Generation & Explanation
        st.subheader(f"Generate & Explain Signal: {strategy.strategy_id.upper()}")
        t_col1, t_col2 = st.columns([1.5, 1])
        with t_col1:
            test_sym = st.selectbox("Signal Symbol", ["NIFTY 50", "BANKNIFTY", "RELIANCE", "TCS", "INFY"], key="reg_sig_sym")
        with t_col2:
            st.write("")
            st.write("")
            gen_sig_btn = st.button("Generate Normalized Signal", type="secondary", use_container_width=True)

        if gen_sig_btn:
            df_test = generate_sample_market_data(80, test_sym, 24500.0 if "NIFTY" in test_sym else 2800.0)
            sig = strategy.generate(df_test, test_sym)
            color = "green" if sig.direction == "long" else ("red" if sig.direction == "short" else "gray")

            st.markdown(f"**Signal Direction:** :{color}[### {sig.direction.upper()}] (Score: {sig.score:.2f})")
            st.markdown(
                f"""
                <div style="background: rgba(30, 41, 59, 0.45); border: 1px solid rgba(255,255,255,0.06); border-radius: 8px; padding: 12px; margin-top: 8px;">
                    <div style="color: #94a3b8; font-size: 0.8rem; font-weight: 600;">TECHNICAL RATIONALE:</div>
                    <div style="color: #cbd5e1; font-size: 0.9rem; margin-top: 4px;">{sig.reason}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
