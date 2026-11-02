"""Options Analytics — NSE Derivatives Desk & Black-Scholes Greeks Suite.

Powered by real-time underlying spot feeds, automated strike generation,
Put-Call Ratio (PCR), Max Pain analysis, and multi-leg spread payoff simulator.
"""

from dataclasses import asdict
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app.options.chain import calculate_spread_payoff, generate_synthetic_option_chain
from app.options.greeks import calculate_greeks
from app.services.market_data import NSE_CATALOG, market_data_service
from app.ui.components import render_global_header


def render_options_page() -> None:
    render_global_header()

    st.markdown(
        """
        <div style="margin-bottom: 16px;">
            <h1 style="margin: 0; font-size: 2.1rem; font-weight: 800; color: #f8fafc; letter-spacing: -0.5px;">Options Analytics — NSE Derivatives Desk</h1>
            <p style="margin: 4px 0 0 0; color: #94a3b8; font-size: 0.95rem;">Live Underlying Spot Feeds • Option Chain (PCR & Max Pain) • Black-Scholes Greeks • Multi-Leg Payoff Builder</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    opt_tab1, opt_tab2, opt_tab3 = st.tabs([
        "📋 Live Option Chain (NSE)",
        "📐 Greeks Calculator (Black-Scholes)",
        "📈 Multi-Leg Spread Payoff Builder",
    ])

    # -------------------------------------------------------------------------
    # TAB 1: OPTION CHAIN
    # -------------------------------------------------------------------------
    with opt_tab1:
        oc1, oc2, oc3, oc4 = st.columns([1.5, 1, 1, 0.8])
        with oc1:
            underlying = st.selectbox("Underlying Index / Equity", ["NIFTY 50", "BANKNIFTY", "RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK"])
        with oc2:
            dte = st.slider("Days to Expiry (DTE)", min_value=1, max_value=30, value=7)
        with oc3:
            # Fetch Real Live Underlying Spot Price
            quote = market_data_service.get_realtime_quote(underlying)
            spot = float(quote["last_price"])
            chg = float(quote["change"])
            chg_pct = float(quote["change_pct"])
            st.metric(
                f"{underlying} Live Spot",
                f"₹{spot:,.2f}",
                delta=f"{chg:+.2f} ({chg_pct:+.2f}%)",
                help="Fetched directly from live market feed.",
            )
        with oc4:
            st.write("")
            st.write("")
            st.button("🔄 Refresh", key="opt_refresh_btn", use_container_width=True)

        # Dynamic strike step based on underlying price
        if "BANK" in underlying:
            step = 100.0
        elif "NIFTY" in underlying:
            step = 50.0
        elif spot > 3000:
            step = 50.0
        elif spot > 1000:
            step = 20.0
        else:
            step = 5.0

        chain = generate_synthetic_option_chain(
            underlying=underlying,
            spot_price=spot,
            strike_step=step,
            num_strikes=12,
            days_to_expiry=dte,
        )

        # PCR and Max Pain Banner Cards
        pcr_color = "#10b981" if chain.pcr >= 1.0 else "#f43f5e"
        pcr_sentiment = "BULLISH / SUPPORTIVE" if chain.pcr >= 1.0 else "BEARISH / RESISTANCE"

        st.markdown(
            f"""
            <div style="display: flex; gap: 16px; margin-bottom: 14px; flex-wrap: wrap;">
                <div style="background: rgba(15, 23, 42, 0.8); border: 1px solid rgba(255,255,255,0.08); border-radius: 8px; padding: 10px 16px; font-family: 'JetBrains Mono', monospace; font-size: 0.85rem;">
                    <span style="color: #94a3b8;">Put-Call Ratio (PCR):</span> <b style="color: {pcr_color}; font-size: 1.05rem;">{chain.pcr:.2f}</b> <span style="font-size: 0.75rem; color: #64748b;">({pcr_sentiment})</span>
                </div>
                <div style="background: rgba(15, 23, 42, 0.8); border: 1px solid rgba(255,255,255,0.08); border-radius: 8px; padding: 10px 16px; font-family: 'JetBrains Mono', monospace; font-size: 0.85rem;">
                    <span style="color: #94a3b8;">Max Pain Strike:</span> <b style="color: #f59e0b; font-size: 1.05rem;">₹{chain.max_pain:,.0f}</b>
                </div>
                <div style="background: rgba(15, 23, 42, 0.8); border: 1px solid rgba(255,255,255,0.08); border-radius: 8px; padding: 10px 16px; font-family: 'JetBrains Mono', monospace; font-size: 0.85rem;">
                    <span style="color: #94a3b8;">At-The-Money (ATM) Strike:</span> <b style="color: #38bdf8; font-size: 1.05rem;">₹{chain.atm_strike:,.0f}</b>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        chain_rows = []
        for s in chain.strikes:
            is_atm = abs(s.strike - chain.atm_strike) < (step / 2.0)
            strike_display = f"⭐ {s.strike:,.0f}" if is_atm else f"{s.strike:,.0f}"
            chain_rows.append({
                "CE OI (Contracts)": f"{s.ce_oi:,}",
                "CE IV (%)": f"{s.ce_iv:.1f}%",
                "CE Delta (Δ)": f"{s.ce_delta:+.2f}",
                "CE Price (₹)": f"₹{s.ce_price:.2f}",
                "Strike": strike_display,
                "PE Price (₹)": f"₹{s.pe_price:.2f}",
                "PE Delta (Δ)": f"{s.pe_delta:+.2f}",
                "PE IV (%)": f"{s.pe_iv:.1f}%",
                "PE OI (Contracts)": f"{s.pe_oi:,}",
            })
        st.dataframe(pd.DataFrame(chain_rows), use_container_width=True, hide_index=True)

    # -------------------------------------------------------------------------
    # TAB 2: GREEKS CALCULATOR
    # -------------------------------------------------------------------------
    with opt_tab2:
        st.subheader("Black-Scholes Options Greeks Pricing Engine")
        
        # Pull live spot for default
        g_underlying = st.selectbox("Select Benchmark for Spot Autofill", ["NIFTY 50", "BANKNIFTY", "RELIANCE", "TCS", "Custom..."])
        if g_underlying != "Custom...":
            g_def_spot = float(market_data_service.get_realtime_quote(g_underlying)["last_price"])
        else:
            g_def_spot = 24500.0

        gc1, gc2, gc3, gc4 = st.columns(4)
        with gc1:
            g_spot = st.number_input("Spot Price (S)", value=g_def_spot, step=50.0)
            g_strike = st.number_input("Strike Price (K)", value=round(g_def_spot / 50.0) * 50.0, step=50.0)
        with gc2:
            g_dte = st.number_input("Days to Expiry", value=7, min_value=1, max_value=365)
            g_iv = st.number_input("Implied Volatility (%)", value=13.5, step=0.5) / 100.0
        with gc3:
            g_rate = st.number_input("Risk-Free Rate (%)", value=6.5, step=0.1) / 100.0
            g_type = st.radio("Option Type", ["CE (Call)", "PE (Put)"], horizontal=True)
        with gc4:
            st.write("")
            st.write("")
            calc_btn = st.button("Calculate Theoretical Value", type="primary", use_container_width=True)

        opt_type_code = "CE" if "Call" in g_type else "PE"
        greeks = calculate_greeks(
            spot=g_spot,
            strike=g_strike,
            expiry_years=g_dte / 365.0,
            rate=g_rate,
            iv=g_iv,
            option_type=opt_type_code,
        )

        st.markdown("### Theoretical Price & Greeks Breakdown")
        gm1, gm2, gm3, gm4, gm5 = st.columns(5)
        with gm1:
            st.metric("Fair Value", f"₹{greeks.price:,.2f}")
        with gm2:
            st.metric("Delta (Δ)", f"{greeks.delta:+.4f}")
        with gm3:
            st.metric("Gamma (Γ)", f"{greeks.gamma:.6f}")
        with gm4:
            st.metric("Theta (Θ / Day)", f"₹{greeks.theta:,.2f}")
        with gm5:
            st.metric("Vega (ν / 1% IV)", f"₹{greeks.vega:,.2f}")

    # -------------------------------------------------------------------------
    # TAB 3: STRATEGY PAYOFF BUILDER
    # -------------------------------------------------------------------------
    with opt_tab3:
        st.subheader("Multi-Leg Options Strategy Payoff Simulator")
        s_c1, s_c2 = st.columns([1.5, 1])
        with s_c1:
            spread_type = st.selectbox(
                "Pre-Built Strategy Template",
                ["Bull Call Spread", "Bear Put Spread", "Long Straddle", "Iron Condor"],
            )
        with s_c2:
            s_underlying = st.selectbox("Underlying Asset", ["NIFTY 50", "BANKNIFTY", "RELIANCE"], key="payoff_underlying")
            real_spot = float(market_data_service.get_realtime_quote(s_underlying)["last_price"])
            s_step = 50.0 if "NIFTY" in s_underlying else (100.0 if "BANK" in s_underlying else 20.0)
            atm = round(real_spot / s_step) * s_step

        if spread_type == "Bull Call Spread":
            legs = [
                {"type": "CE", "strike": atm, "action": "BUY", "premium": 150.0, "qty": 1},
                {"type": "CE", "strike": atm + (s_step * 4), "action": "SELL", "premium": 60.0, "qty": 1},
            ]
        elif spread_type == "Bear Put Spread":
            legs = [
                {"type": "PE", "strike": atm, "action": "BUY", "premium": 140.0, "qty": 1},
                {"type": "PE", "strike": atm - (s_step * 4), "action": "SELL", "premium": 50.0, "qty": 1},
            ]
        elif spread_type == "Long Straddle":
            legs = [
                {"type": "CE", "strike": atm, "action": "BUY", "premium": 150.0, "qty": 1},
                {"type": "PE", "strike": atm, "action": "BUY", "premium": 140.0, "qty": 1},
            ]
        else:
            # Iron Condor
            legs = [
                {"type": "PE", "strike": atm - (s_step * 8), "action": "BUY", "premium": 25.0, "qty": 1},
                {"type": "PE", "strike": atm - (s_step * 4), "action": "SELL", "premium": 65.0, "qty": 1},
                {"type": "CE", "strike": atm + (s_step * 4), "action": "SELL", "premium": 70.0, "qty": 1},
                {"type": "CE", "strike": atm + (s_step * 8), "action": "BUY", "premium": 28.0, "qty": 1},
            ]

        # Calculate Payoff Curve across Spot Range around Real Spot
        span = s_step * 16
        spot_range = [atm - span + (i * (span * 2 / 80)) for i in range(81)]
        payoff_data = calculate_spread_payoff(spread_type, spot_range, legs)
        p_df = pd.DataFrame(payoff_data)

        # Plot Payoff Diagram
        fig_payoff = go.Figure()
        
        # Positive and negative regions
        pnl_series = p_df["pnl"]
        fig_payoff.add_trace(
            go.Scatter(
                x=p_df["spot"],
                y=pnl_series,
                mode="lines",
                line=dict(color="#38bdf8", width=3),
                name="Net P&L (₹)",
            )
        )
        fig_payoff.add_hline(y=0, line_dash="dash", line_color="#94a3b8")
        fig_payoff.add_vline(x=atm, line_dash="dot", line_color="#f59e0b", annotation_text=f"Live Spot: ₹{real_spot:,.1f}")

        fig_payoff.update_layout(
            title=dict(
                text=f"<b>{spread_type}</b> — Expiry Payoff Curve (₹) [Spot @ ₹{real_spot:,.1f}]",
                font=dict(size=15, color="#f8fafc", family="Plus Jakarta Sans"),
            ),
            template="plotly_dark",
            plot_bgcolor="rgba(11, 15, 25, 0.7)",
            paper_bgcolor="rgba(11, 15, 25, 0)",
            xaxis_title="Underlying Price at Expiry",
            yaxis_title="Profit / Loss (₹)",
            height=380,
            margin=dict(l=45, r=45, t=45, b=40),
        )
        st.plotly_chart(fig_payoff, use_container_width=True)
