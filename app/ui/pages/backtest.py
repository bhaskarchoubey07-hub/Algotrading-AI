import io
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from app.backtest import AdvancedBacktestEngine
from app.strategies import STRATEGIES
from app.ui.components import generate_sample_market_data


def render_backtest_page() -> None:
    st.title("Backtesting Laboratory — Performance Validation")
    st.caption("Event-Driven Chronological Backtesting • Realistic Indian Taxes & Slippage • Walk-Forward Validation")

    # Configuration Controls
    c1, c2, c3, c4 = st.columns([1.5, 1.5, 1, 1])
    with c1:
        strat_key = st.selectbox("Select Strategy", list(STRATEGIES.keys()), format_func=lambda k: STRATEGIES[k].strategy_id.upper())
    with c2:
        symbol = st.selectbox("Symbol", ["NIFTY 50", "BANKNIFTY", "RELIANCE", "TCS", "INFY"])
    with c3:
        initial_cap = st.number_input("Capital (₹)", min_value=50_000.0, max_value=10_000_000.0, value=1_000_000.0, step=50_000.0)
    with c4:
        slippage_bps = st.number_input("Slippage (bps)", min_value=0.0, max_value=50.0, value=3.0, step=0.5)

    # Data Source Selection (Upload CSV or Simulated Historical)
    with st.expander("Data Source & Upload CSV", expanded=False):
        uploaded_file = st.file_uploader("Upload Historical OHLCV CSV (Columns: timestamp, open, high, low, close, volume)", type=["csv"])
        sim_bars = st.slider("Simulated Bars (if no CSV uploaded)", min_value=60, max_value=500, value=180)

    run_btn = st.button("Run Comprehensive Backtest", type="primary")

    if run_btn:
        with st.spinner("Executing bar-by-bar chronological backtest..."):
            if uploaded_file is not None:
                try:
                    df = pd.read_csv(uploaded_file)
                except Exception as exc:
                    st.error(f"Error reading CSV: {exc}")
                    return
            else:
                base = 24500.0 if "NIFTY" in symbol else 2800.0
                df = generate_sample_market_data(n_bars=sim_bars, symbol=symbol, base_price=base)

            strategy = STRATEGIES[strat_key]
            engine = AdvancedBacktestEngine(initial_capital=initial_cap, slippage_bps=slippage_bps, enable_statutory_charges=True)

            try:
                metrics = engine.run(df, strategy, symbol=symbol)
            except Exception as exc:
                st.error(f"Backtest execution error: {exc}")
                return

            # Display Key Metrics Cards
            st.markdown("### Backtest Performance Summary")
            m1, m2, m3, m4, m5 = st.columns(5)
            with m1:
                st.metric("Net P&L", f"₹{metrics.net_pnl:,.2f}", delta=f"Gross: ₹{metrics.gross_pnl:,.2f}")
            with m2:
                st.metric("Win Rate", f"{metrics.win_rate_pct:.1f}%", delta=f"{metrics.winning_trades}W / {metrics.losing_trades}L")
            with m3:
                st.metric("Profit Factor", f"{metrics.profit_factor:.2f}" if metrics.profit_factor else "N/A")
            with m4:
                st.metric("Max Drawdown", f"{metrics.max_drawdown_pct:.2f}%", delta=f"-₹{metrics.max_drawdown_amount:,.2f}", delta_color="inverse")
            with m5:
                st.metric("Sharpe Ratio", f"{metrics.sharpe_ratio:.2f}", delta=f"Sortino: {metrics.sortino_ratio:.2f}")

            m6, m7, m8, m9, m10 = st.columns(5)
            with m6:
                st.metric("Total Trades", f"{metrics.total_trades}")
            with m7:
                st.metric("Net Expectancy", f"₹{metrics.expectancy:,.2f}")
            with m8:
                st.metric("Total Taxes & Fees", f"₹{metrics.total_fees:,.2f}")
            with m9:
                st.metric("CAGR %", f"{metrics.cagr_pct:.2f}%")
            with m10:
                st.metric("Win/Loss Ratio", f"{metrics.win_loss_ratio:.2f}")

            # Equity Curve & Drawdown Chart
            st.subheader("Equity Curve & Peak-to-Trough Drawdown")
            eq_df = pd.DataFrame(metrics.equity_curve)
            if not eq_df.empty:
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=eq_df["timestamp"], y=eq_df["equity"], name="Equity (₹)", line=dict(color="#10b981", width=2)))
                fig.update_layout(template="plotly_dark", plot_bgcolor="#0b0f19", paper_bgcolor="#0b0f19", height=380, margin=dict(l=40, r=40, t=20, b=20))
                st.plotly_chart(fig, use_container_width=True)

            # Trade-by-trade log
            st.subheader("Trade-by-Trade Execution Log")
            if metrics.trades_log:
                trades_data = [t.to_dict() if hasattr(t, "to_dict") else t for t in metrics.trades_log]
                trade_df = pd.DataFrame(trades_data)
                st.dataframe(trade_df, use_container_width=True)

                # CSV Download Button
                csv_buffer = io.StringIO()
                trade_df.to_csv(csv_buffer, index=False)
                st.download_button(
                    label="Download Trade Log (CSV)",
                    data=csv_buffer.getvalue(),
                    file_name=f"algotrade_{strat_key}_{symbol}_backtest.csv",
                    mime="text/csv",
                )
            else:
                st.info("No trades triggered under current parameter thresholds.")

            # Walk-forward validation section
            st.subheader("Walk-Forward Validation (70% In-Sample / 30% Out-of-Sample)")
            wf = engine.walk_forward_validation(df, strategy, symbol=symbol)
            wfc1, wfc2, wfc3 = st.columns(3)
            with wfc1:
                st.metric("In-Sample Win Rate", f"{wf['in_sample']['win_rate_pct']:.1f}%")
            with wfc2:
                st.metric("Out-of-Sample Win Rate", f"{wf['out_of_sample']['win_rate_pct']:.1f}%")
            with wfc3:
                st.metric("Out-of-Sample Degradation", f"{wf['degradation_pct']:+.1f}%")
