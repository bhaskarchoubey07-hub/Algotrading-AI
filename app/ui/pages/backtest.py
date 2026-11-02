"""Backtesting Laboratory — Quantitative Validation, Fee Accounting & Risk Simulation."""

from datetime import datetime, timedelta, timezone
import io
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from app.backtest import AdvancedBacktestEngine
from app.database.supabase_client import db_repo
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
            <p style="margin: 4px 0 0 0; color: #94a3b8; font-size: 0.95rem;">Chronological Simulation • Zero Lookahead Bias • Indian Market Slippage & Statutory STT Charges</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Check for prefill from Strategy Laboratory
    prefill = st.session_state.get("backtest_prefill", {})
    default_strat_idx = 0
    if prefill.get("strategy_id") in STRATEGIES:
        default_strat_idx = list(STRATEGIES.keys()).index(prefill["strategy_id"])

    # 1. Parameter Configuration Panel
    st.subheader("Simulation Parameters")
    c1, c2, c3, c4 = st.columns([1.5, 1.2, 1, 1])
    with c1:
        strat_key = st.selectbox(
            "Quantitative Strategy",
            list(STRATEGIES.keys()),
            index=default_strat_idx,
            format_func=lambda k: f"{STRATEGIES[k].strategy_id.upper()} ({getattr(STRATEGIES[k], 'category', 'general').capitalize()})",
        )
    with c2:
        from app.services.market_data import NSE_CATALOG, market_data_service
        inst_options = list(NSE_CATALOG.keys())
        default_inst_idx = inst_options.index(prefill["symbol"]) if prefill.get("symbol") in inst_options else 0
        symbol = st.selectbox("Instrument", inst_options, index=default_inst_idx)
    with c3:
        initial_cap = st.number_input(
            "Initial Capital (₹)",
            min_value=50_000.0,
            max_value=50_000_000.0,
            value=float(prefill.get("initial_capital", 1_000_000.0)),
            step=50_000.0,
        )
    with c4:
        slippage_bps = st.number_input(
            "Slippage (bps)",
            min_value=0.0,
            max_value=50.0,
            value=3.0,
            step=0.5,
            help="Simulated price impact and execution friction in basis points (1 bps = 0.01%).",
        )

    # Historical Date Range & Data Source Options
    with st.expander("📁 Date Range, Data Source & CSV Upload", expanded=False):
        d_c1, d_c2, d_c3 = st.columns([1, 1, 1.5])
        with d_c1:
            start_date = st.date_input("Start Date", value=datetime.now() - timedelta(days=365))
        with d_c2:
            end_date = st.date_input("End Date", value=datetime.now())
        with d_c3:
            data_source_mode = st.selectbox(
                "Data Source",
                ["🟢 Live NSE Real Historical Market Data", "🎲 Simulated Historical Walk", "📁 Custom CSV Upload"],
                index=0,
            )

        uploaded_file = None
        if "CSV" in data_source_mode:
            uploaded_file = st.file_uploader(
                "Upload Historical OHLCV CSV (Required columns: timestamp, open, high, low, close, volume)",
                type=["csv"],
            )

    run_btn = st.button("▶ Run Chronological Backtest", type="primary")

    if run_btn:
        with st.spinner("Executing bar-by-bar chronological backtest with statutory Indian fees..."):
            try:
                df = None
                if "CSV" in data_source_mode and uploaded_file is not None:
                    raw_df = pd.read_csv(uploaded_file)
                    req_cols = {"timestamp", "open", "high", "low", "close", "volume"}
                    if not req_cols.issubset(set(raw_df.columns)):
                        missing = req_cols - set(raw_df.columns)
                        raise ValueError(f"Uploaded CSV missing required columns: {sorted(missing)}")
                    df = raw_df
                elif "Live" in data_source_mode:
                    df = market_data_service.get_historical_ohlcv(
                        symbol=symbol,
                        timeframe="1d",
                        start_date=str(start_date),
                        end_date=str(end_date),
                    )
                    st.info(f"📊 Downloaded {len(df)} real historical trading bars for **{symbol}** from stock exchange.")
                else:
                    days_count = max(30, min(500, (end_date - start_date).days))
                    base_p = 24500.0 if "NIFTY" in symbol else (51500.0 if "BANKNIFTY" in symbol else 2800.0)
                    df = generate_sample_market_data(n_bars=days_count, symbol=symbol, base_price=base_p)

                strategy = STRATEGIES[strat_key]
                engine = AdvancedBacktestEngine(
                    initial_capital=initial_cap,
                    slippage_bps=slippage_bps,
                    enable_statutory_charges=True,
                )

                metrics = engine.run(df, strategy, symbol=symbol)

                # Persist result into session state
                st.session_state["last_backtest_result"] = metrics
                st.session_state["last_backtest_meta"] = {
                    "strategy_id": strat_key,
                    "symbol": symbol,
                    "initial_capital": initial_cap,
                    "slippage_bps": slippage_bps,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

                # Save experiment to database repository
                run_id = db_repo.save_backtest_run(
                    strategy_id=strat_key,
                    strategy_version=strategy.version,
                    symbol=symbol,
                    timeframe="1d",
                    initial_capital=initial_cap,
                    parameters=strategy.metadata().get("parameters", {}),
                    metrics=metrics.to_dict() if hasattr(metrics, "to_dict") else {},
                    equity_curve=metrics.equity_curve,
                    trades_log=[t.to_dict() if hasattr(t, "to_dict") else t for t in metrics.trades_log],
                )
                st.success(f"Backtest completed successfully! Experiment ID: `{run_id[:8]}`")

            except Exception as exc:
                st.error(f"Backtest execution error: {exc}")
                # "Preserve the previous valid results if a new run fails."
                if "last_backtest_result" in st.session_state:
                    st.warning("⚠️ Retaining previous valid backtest results.")

    # Render previous or current valid results if available
    metrics = st.session_state.get("last_backtest_result")
    meta_info = st.session_state.get("last_backtest_meta", {})

    if metrics is not None:
        st.markdown("---")
        st.markdown(
            f"### Performance & Expectancy Summary: `{meta_info.get('strategy_id', '').upper()}` on `{meta_info.get('symbol', '')}`"
        )

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

        # High-Fidelity Equity Curve & Drawdown Chart (No legend overlap)
        st.subheader("Interactive Equity Trajectory & Peak Drawdown")
        eq_df = pd.DataFrame(metrics.equity_curve)
        if not eq_df.empty:
            fig = make_subplots(
                rows=2,
                cols=1,
                shared_xaxes=True,
                vertical_spacing=0.06,
                row_heights=[0.72, 0.28],
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
                margin=dict(l=45, r=45, t=30, b=50),
                legend=dict(
                    orientation="h",
                    yanchor="top",
                    y=-0.12,
                    xanchor="center",
                    x=0.5,
                    font=dict(size=11, color="#94a3b8"),
                ),
                hovermode="x unified",
            )
            fig.update_yaxes(title_text="Equity (₹)", row=1, col=1)
            fig.update_yaxes(title_text="DD %", row=2, col=1)

            st.plotly_chart(fig, use_container_width=True)

        # Trade Execution Log
        st.subheader("Detailed Trade Execution History")
        if metrics.trades_log:
            trades_data = [t.to_dict() if hasattr(t, "to_dict") else t for t in metrics.trades_log]
            trade_df = pd.DataFrame(trades_data)
            st.dataframe(trade_df, use_container_width=True)

            csv_buffer = io.StringIO()
            trade_df.to_csv(csv_buffer, index=False)
            st.download_button(
                label="📥 Download Detailed Trade Log (CSV)",
                data=csv_buffer.getvalue(),
                file_name=f"algotrade_backtest_{meta_info.get('strategy_id', 'strat')}_{meta_info.get('symbol', 'sym').replace(' ', '_')}.csv",
                mime="text/csv",
            )

    # Saved Experiment History Section
    st.markdown("---")
    st.subheader("Saved Experiment History")
    past_runs = db_repo.list_backtest_runs(limit=15)
    if past_runs:
        history_rows = []
        for r in past_runs:
            met = r.get("metrics", {})
            history_rows.append({
                "Run ID": r["id"][:8],
                "Timestamp": r["created_at"][:19],
                "Strategy": r["strategy_id"].upper(),
                "Symbol": r["symbol"],
                "Capital": f"₹{r['initial_capital']:,.0f}",
                "Net PnL": f"₹{met.get('net_pnl', 0.0):+,.2f}",
                "Win Rate": f"{met.get('win_rate_pct', 0.0):.1f}%",
                "Profit Factor": f"{met.get('profit_factor', 0.0):.2f}" if met.get("profit_factor") else "N/A",
                "Max DD": f"{met.get('max_drawdown_pct', 0.0):.1f}%",
            })
        st.dataframe(pd.DataFrame(history_rows), use_container_width=True, hide_index=True)
    else:
        st.info("No saved backtest experiments recorded yet.")
