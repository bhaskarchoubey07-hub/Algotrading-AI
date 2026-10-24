"""AlgoTrade AI — Adaptive Strategy Center UI
Self-evaluating quantitative strategy lifecycle management, rolling performance tracking,
deterioration detection, shadow evaluation, and dynamic ensemble weighting.
"""

import pandas as pd
import plotly.express as px
import streamlit as st
from app.adaptive import (
    StrategyHealthState,
    health_manager,
    performance_tracker,
    weight_engine,
)
from app.models import MarketRegime
from app.strategies import STRATEGIES


def render_adaptive_page() -> None:
    st.title("Adaptive Strategy Center — Self-Evaluating Quant Intelligence")
    st.caption("Autonomous Strategy Lifecycle Management • Deterioration Diagnostics • Dynamic Regime Weighting")

    # Ensure all registered strategies exist in health manager
    for sid in STRATEGIES.keys():
        health_manager.register_strategy(sid, StrategyHealthState.ACTIVE)

    # Top Level Overview Cards
    states = [health_manager.get_state(s) for s in STRATEGIES.keys()]
    active_cnt = sum(s == StrategyHealthState.ACTIVE for s in states)
    degraded_cnt = sum(s == StrategyHealthState.DEGRADED for s in states)
    shadow_cnt = sum(s == StrategyHealthState.SHADOW for s in states)
    paused_cnt = sum(s in {StrategyHealthState.PAUSED, StrategyHealthState.RETIRED} for s in states)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Active Paper Strategies", f"{active_cnt}", delta="Primary Voting Pool")
    with c2:
        st.metric("Degraded Strategies", f"{degraded_cnt}", delta="-Review Needed" if degraded_cnt else "Healthy", delta_color="inverse")
    with c3:
        st.metric("Shadow Mode Candidates", f"{shadow_cnt}", delta="Awaiting Validation")
    with c4:
        st.metric("Paused / Retired", f"{paused_cnt}")

    st.markdown("---")

    # Tab 1: Strategy Lifecycle & Health Matrix
    tab_lifecycle, tab_performance, tab_weights, tab_audit = st.tabs([
        "🛡️ Strategy Lifecycle & State Management",
        "📊 Statistical Quality & Confidence Intervals",
        "⚖️ Dynamic Ensemble Weights",
        "📝 Lifecycle Audit Trail",
    ])

    with tab_lifecycle:
        st.subheader("Strategy Health Matrix")
        st.caption("Manage formal strategy transitions across the finite-state machine lifecycle.")

        lifecycle_data = []
        for sid, strat in STRATEGIES.items():
            curr_st = health_manager.get_state(sid)
            meta = strat.metadata()
            lifecycle_data.append({
                "Strategy ID": sid,
                "Current Health State": curr_st.value,
                "Category": meta.get("category", "trend").capitalize(),
                "Regime Support": ", ".join(meta.get("regimes", ["any"])),
                "Version": strat.version,
            })

        df_life = pd.DataFrame(lifecycle_data)
        st.dataframe(df_life, use_container_width=True, hide_index=True)

        # Transition Control Form
        with st.expander("Execute Strategy State Transition", expanded=False):
            tc1, tc2 = st.columns(2)
            with tc1:
                sel_strat = st.selectbox("Select Strategy", list(STRATEGIES.keys()), key="trans_strat")
                curr_state = health_manager.get_state(sel_strat)
                st.info(f"Current State: **{curr_state.value}**")
            with tc2:
                all_states = [s for s in StrategyHealthState if s != curr_state]
                sel_target = st.selectbox("Target State", all_states, key="trans_target")
                reason_txt = st.text_input("Formal Audit Reason", value="Routine adaptive rebalance", key="trans_reason")

            if st.button("Apply State Transition", type="primary"):
                success = health_manager.transition_state(
                    strategy_id=sel_strat,
                    target_state=sel_target,
                    reason=reason_txt,
                )
                if success:
                    st.success(f"Successfully transitioned {sel_strat} to {sel_target.value}!")
                    st.rerun()
                else:
                    st.error(f"Illegal state transition from {curr_state.value} to {sel_target.value}. Transition rejected.")

    with tab_performance:
        st.subheader("Statistical Performance & Wilson Score Confidence Bounds")
        st.caption("Tracks closed trades with 95% Wilson binomial confidence intervals to prevent sample-size illusion.")

        perf_rows = []
        for sid in STRATEGIES.keys():
            snap = performance_tracker.evaluate_strategy(sid)
            perf_rows.append({
                "Strategy ID": sid,
                "Trades": snap.trade_count,
                "Net PnL": f"₹{snap.net_pnl:,.2f}",
                "Expectancy (bps)": f"{snap.rolling_expectancy_bps:+.1f}",
                "Win Rate %": f"{snap.win_rate_pct:.1f}%",
                "95% CI Bounds": f"[{snap.win_rate_ci_lower:.1f}%, {snap.win_rate_ci_upper:.1f}%]",
                "Profit Factor": f"{snap.profit_factor:.2f}",
                "Max DD %": f"{snap.max_drawdown_pct:.1f}%",
                "Sharpe": f"{snap.sharpe_ratio:.2f}",
                "Health Flag": "⚠️ DEGRADED" if snap.is_deteriorating else "✅ STABLE",
            })

        df_perf = pd.DataFrame(perf_rows)
        st.dataframe(df_perf, use_container_width=True, hide_index=True)

        st.caption("Wilson Score interval calculates the true binomial confidence band: small sample sizes yield wider bands, preventing overconfidence.")

    with tab_weights:
        st.subheader("Dynamic Ensemble Weights by Market Regime")
        st.caption("Adaptive allocation shifts capital to strategies matching the prevailing market regime with strict single-strategy caps.")

        wc1, wc2 = st.columns([1, 2])
        with wc1:
            sel_regime_str = st.selectbox(
                "Simulated Market Regime",
                ["TRENDING_UP", "TRENDING_DOWN", "RANGE_BOUND", "HIGH_VOLATILITY", "LOW_LIQUIDITY"],
                index=0,
            )
            sim_regime = MarketRegime(sel_regime_str.lower())
            weight_scheme = st.selectbox(
                "Weighting Scheme",
                ["performance_regime", "equal", "drawdown_constrained"],
            )

            weights = weight_engine.calculate_weights(
                strategy_ids=list(STRATEGIES.keys()),
                current_regime=sim_regime,
                scheme=weight_scheme,
            )

        with wc2:
            df_w = pd.DataFrame([
                {"Strategy": sid, "Weight %": round(w * 100, 2)}
                for sid, w in weights.items() if w > 0
            ]).sort_values("Weight %", ascending=False)

            fig = px.bar(
                df_w,
                x="Strategy",
                y="Weight %",
                color="Weight %",
                color_continuous_scale="Viridis",
                title=f"Ensemble Allocation ({sel_regime_str} — {weight_scheme})",
            )
            fig.update_layout(template="plotly_dark", plot_bgcolor="rgba(11, 15, 25, 0.7)", paper_bgcolor="rgba(11, 15, 25, 0)")
            st.plotly_chart(fig, use_container_width=True)

    with tab_audit:
        st.subheader("Strategy Adaptation Audit History")
        st.caption("Immutable record of all lifecycle state transitions, reasons, and evidence.")

        history = health_manager.get_transition_history()
        if history:
            hist_rows = [
                {
                    "Timestamp (UTC)": h.timestamp,
                    "Strategy ID": h.strategy_id,
                    "Previous State": h.from_state.value,
                    "New State": h.to_state.value,
                    "Audit Rationale": h.reason,
                }
                for h in reversed(history)
            ]
            st.dataframe(pd.DataFrame(hist_rows), use_container_width=True, hide_index=True)
        else:
            st.info("No lifecycle transition events recorded yet.")
