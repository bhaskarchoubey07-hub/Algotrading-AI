import pandas as pd
import streamlit as st
from app.strategies import STRATEGIES
from app.ui.components import generate_sample_market_data


def render_strategies_page() -> None:
    st.title("Strategy Laboratory — Algorithm Registry")
    st.caption("Inspect, Configure, Parameterize, and Test Independent Quantitative Trading Strategies")

    # Strategy Catalog Filter
    strat_keys = list(STRATEGIES.keys())
    selected_key = st.selectbox(
        "Select Strategy to Inspect / Test",
        strat_keys,
        format_func=lambda k: f"{STRATEGIES[k].strategy_id.upper()} ({getattr(STRATEGIES[k], 'category', 'general').capitalize()}) — v{STRATEGIES[k].version}",
    )

    strategy = STRATEGIES[selected_key]
    meta = strategy.metadata()

    # Strategy Details Cards
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(f"**Strategy ID:** `{strategy.strategy_id}`")
        st.markdown(f"**Version:** `{strategy.version}`")
    with c2:
        st.markdown(f"**Category:** `{meta.get('category', 'trend').capitalize()}`")
        st.markdown(f"**Regime Suitability:** `{', '.join(meta.get('supported_regimes', ['all']))}`")
    with c3:
        st.markdown(f"**Execution Mode:** `Simulated Signals Only`")
        st.markdown(f"**Order Authority:** `None (Emits Normalized Signals)`")

    st.info(f"**Description:** {strategy.description}")

    # Parameter Inspection
    params = getattr(strategy, "parameters", {})
    if params:
        st.subheader("Configurable Strategy Parameters")
        param_cols = st.columns(len(params))
        for i, (p_name, p_val) in enumerate(params.items()):
            with param_cols[i % len(param_cols)]:
                st.text_input(f"Parameter: {p_name}", value=str(p_val), disabled=True)

    st.markdown("---")

    # Signal Testing Workbench
    st.subheader(f"Test Signal Generation: {strategy.strategy_id}")
    tc1, tc2, tc3 = st.columns([1, 1, 1])
    with tc1:
        test_sym = st.selectbox("Test Symbol", ["NIFTY 50", "BANKNIFTY", "RELIANCE", "TCS", "INFY"])
    with tc2:
        test_bars = st.slider("Historical Bar Warmup", min_value=30, max_value=200, value=80)
    with tc3:
        st.write("")
        st.write("")
        run_signal_btn = st.button("Generate Strategy Signal", type="primary")

    if run_signal_btn:
        df_test = generate_sample_market_data(test_bars, test_sym, 24500.0 if "NIFTY" in test_sym else 2800.0)
        try:
            sig = strategy.generate(df_test, test_sym)
            res1, res2, res3 = st.columns(3)
            with res1:
                color = "green" if sig.direction == "long" else ("red" if sig.direction == "short" else "gray")
                st.markdown(f"**Signal Direction:** :{color}[### {sig.direction.upper()}]")
            with res2:
                st.metric("Signal Conviction Score", f"{sig.score:.2f} / 1.00")
            with res3:
                st.metric("Suggested Stop Loss", f"₹{sig.suggested_stop:,.2f}" if sig.suggested_stop else "None")

            st.success(f"**Strategy Rationale:** {sig.reason}")
        except Exception as exc:
            st.error(f"Signal Generation Error: {exc}")

    # Complete Registry Overview Table
    st.subheader("All Registered Production Strategies")
    all_strats = [s.metadata() for s in STRATEGIES.values()]
    df_all = pd.DataFrame(all_strats)
    st.dataframe(df_all[["strategy_id", "version", "category", "description"]], use_container_width=True)
