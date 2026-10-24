import pandas as pd
import streamlit as st
from app.ensemble import RegimeDetector, regime_ensemble
from app.strategies import STRATEGIES
from app.ui.components import generate_sample_market_data


def render_ensemble_page() -> None:
    st.title("Ensemble Monitor — Central Consensus Engine")
    st.caption("Regime-Aware Strategy Coordination • Conflict Resolution • Net Edge Estimation")

    c1, c2 = st.columns([2, 1])
    with c1:
        symbol = st.selectbox("Market Feed Symbol", ["NIFTY 50", "BANKNIFTY", "RELIANCE", "TCS"])
    with c2:
        bars_count = st.slider("Historical Lookback (Bars)", 40, 150, 80)

    # Fetch data and evaluate
    df = generate_sample_market_data(bars_count, symbol, 24500.0 if "NIFTY" in symbol else 2800.0)
    regime, regime_metrics = RegimeDetector.classify_regime(df)

    # Strategy signals evaluation
    signals = []
    signals_data = []
    for s in STRATEGIES.values():
        try:
            sig = s.generate(df, symbol)
            signals.append(sig)
            signals_data.append({
                "Strategy ID": sig.strategy_id,
                "Category": getattr(s, "category", "trend").capitalize(),
                "Direction": sig.direction.upper(),
                "Score": f"{sig.score:.2f}",
                "Stop Loss": f"₹{sig.suggested_stop:,.2f}" if sig.suggested_stop else "-",
                "Target": f"₹{sig.suggested_target:,.2f}" if sig.suggested_target else "-",
                "Rationale": sig.reason,
            })
        except Exception:
            pass

    # Ensemble consensus evaluation
    decision = regime_ensemble.evaluate(signals, df, symbol)

    # Decision Banner
    st.markdown("### Ensemble Consensus Trade Proposal")
    dec_col1, dec_col2, dec_col3, dec_col4 = st.columns(4)
    with dec_col1:
        color = "green" if decision.direction == "long" else ("red" if decision.direction == "short" else "gray")
        st.markdown(f"**Final Proposal:** :{color}[### {decision.decision}]")
    with dec_col2:
        st.metric("Detected Regime", decision.regime.upper())
    with dec_col3:
        st.metric("Votes (Long / Short)", f"{decision.long_votes} Long / {decision.short_votes} Short")
    with dec_col4:
        st.metric("Estimated Net Edge", f"{decision.estimated_edge_bps:+.1f} bps", delta="After 8 bps charges")

    st.info(f"**Consensus Rationale:** {decision.rationale}")
    if decision.note:
        st.caption(f"ℹ️ Engine Notes: {decision.note}")

    st.markdown("---")

    # Strategy Voting Matrix
    st.subheader("Strategy Voting Matrix & Conviction Breakdown")
    sig_df = pd.DataFrame(signals_data)
    st.dataframe(sig_df, use_container_width=True)

    # Detailed Regime Diagnostic Metrics
    with st.expander("Regime Classifier Diagnostics", expanded=False):
        rm_cols = st.columns(len(regime_metrics))
        for i, (k, v) in enumerate(regime_metrics.items()):
            with rm_cols[i % len(rm_cols)]:
                st.metric(k.upper(), str(v))
