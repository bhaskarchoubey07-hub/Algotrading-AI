"""Backtesting Laboratory — Quantitative Validation & Risk Simulation."""

import io
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
from app.backtest import AdvancedBacktestEngine
from app.strategies import STRATEGIES
from app.ui.components import (
    generate_sample_market_data,
    render_global_header,
)


def render_backtest_page() -> None:
    render_global_header()

    st.markdown(
        """
        <div style="margin-bottom: 16px;">
            <h1 style="margin: 0; font-size: 2.1rem; font-weight: 800; color: #f8fafc; letter-spacing: -0.5px;">Backtesting Laboratory — Performance Validation</h1>
            <p style="margin: 4px 0 0 0; color: #94a3b8; font-size: 0.95rem;">Chronological Simulation • Zero Lookahead Bias • Indian Market Slippage & STT Charges</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 1. Parameter Configuration Panel
    c1, c2, c3, c4 = st.columns([1.5, 1.5, 1, 1])
    with c1:
        strat_key = st.selectbox(
            "Quantitative Strategy",
            list(STRATEGIES.keys()),
            format_func=lambda k: STRATEGIES[k].strategy_id.upper(),
        )
    with c2:
        symbol = st.selectbox("Instrument", ["NIFTY 50", "BANKNIFTY", "RELIANCE", "TCS", "INFY"])
    with c3:
        initial_cap = st.number_input(
            "Initial Capital (₹)",
            min_value=50_000.0,
            max_value=10_000_000.0,
            value=1_000_000.0,
            step=50_000.0,
        )
    with c4:
        slippage_bps = st.number_input(
            "Slippage (bps)",
            min_value=0.0,
            max_value=50.0,
            value=3.0,
            step=0.5,
        )

    # Data Source Options
    with st.expander("📁 Data Source Selection & CSV Upload", expanded=False):
        uploaded_file = st.file_uploader(
            "Upload Historical OHLCV CSV (Columns: timestamp, open, high, low, close, volume)",
            type=["csv"],
        )
        sim_bars = st.slider("Simulated Bars (if no CSV uploaded)", min_value=60, max_value=500, value=180)

    run_btn = st.button("▶ Run Chronological Backtest", type="primary")

    if run_btn:
        with st.spinner("Executing bar-by-bar chronological backtest with statutory Indian fees..."):
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
            engine = AdvancedBacktestEngine(
                initial_capital=initial_cap,
                slippage_bps=slippage_bps,
                enable_statutory_charges=True,
            )

            try:
                metrics = engine.run(df, strategy, symbol=symbol)
            except Exception as exc:
                st.error(f"Backtest execution error: {exc}")
                return

            st.markdown("---")

            # 2. Key Performance Metrics
            st.markdown("### Performance & Expectancy Summary")
            m1, m2, m3, m4, m5 = st.columns(5)
            with m1:
                st.metric("Net Profit / Loss", f"₹{metrics.net_pnl:,.2f}", delta=f"Gross: ₹{metrics.gross_pnl:,.2f}")
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
                st.metric("Total Statutory Fees", f"₹{metrics.total_fees:,.2f}")
            with m9:
                st.metric("CAGR Return", f"{metrics.cagr_pct:.2f}%")
            with m10:
                st.metric("Win / Loss Ratio", f"{metrics.win_loss_ratio:.2f}")

            # 3. High-Fidelity Equity Curve & Drawdown Chart
            st.subheader("Interactive Equity Trajectory & Peak Drawdown")
            eq_df = pd.DataFrame(metrics.equity_curve)
            if not eq_df.empty:
                fig = make_subplots(
                    rows=2,
                    cols=1,
                    shared_xaxes=True,
                    vertical_spacing=0.05,
                    row_heights=[0.75, 0.25],
                )

                # Equity Trace
                fig.add_trace(
                    go.Scatter(
                        x=eq_df["timestamp"],
                        y=eq_df["equity"],
                        mode="lines",
                        name="Portfolio Equity (₹)",
                        line=dict(color="#10b981", width=2),
                    ),
                    row=1,
                    col=1,
                )

                # Running Peak & Drawdown
                peaks = eq_df["equity"].cummax()
                drawdowns = ((eq_df["equity"] - peaks) / peaks) * 100.0

                fig.add_trace(
                    go.Scatter(
                        x=eq_df["timestamp"],
                        y=drawdowns,
                        mode="lines",
                        fill="tozeroy",
                        fillcolor="rgba(244, 63, 94, 0.25)",
                        name="Drawdown %",
                        line=dict(color="#f43f5e", width=1.5),
                    ),
                    row=2,
                    col=1,
                )

                fig.update_layout(
                    template="plotly_dark",
                    plot_bgcolor="rgba(11, 15, 25, 0.7)",
                    paper_bgcolor="rgba(11, 15, 25, 0)",
                    height=420,
                    margin=dict(l=40, r=40, t=20, b=20),
                    hovermode="x unified",
                )
                fig.update_yaxes(title_text="Equity (₹)", row=1, col=1)
                fig.update_yaxes(title_text="DD %", row=2, col=1)

                st.plotly_chart(fig, use_container_width=True)

            # 4. Trade-by-Trade Execution Log
            st.subheader("Trade-by-Trade Execution Log")
            if metrics.trades_log:
                trades_data = [t.to_dict() if hasattr(t, "to_dict") else t for t in metrics.trades_log]
                trade_df = pd.DataFrame(trades_data)
                st.dataframe(trade_df, use_container_width=True)

                csv_buffer = io.StringIO()
                trade_df.to_csv(csv_buffer, index=False)
                st.download_button(
                    label="📥 Download Detailed Trade Log (CSV)",
                    data=csv_buffer.getvalue(),
                    file_name=f"algotrade_backtest_{strat_key}_{symbol.replace(' ', '_')}.csv",
                    mime="text/csv",
                )
