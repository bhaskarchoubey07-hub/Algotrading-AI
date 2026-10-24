from dataclasses import asdict
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from app.options.chain import calculate_spread_payoff, generate_synthetic_option_chain
from app.options.greeks import calculate_greeks


def render_options_page() -> None:
    st.title("Options Analytics — NSE Derivatives Desk")
    st.caption("Live / Synthetic Option Chains • Black-Scholes Greeks Suite • Multi-Leg Spread Payoff Builder")

    opt_tab1, opt_tab2, opt_tab3 = st.tabs(["Option Chain (NSE)", "Greeks Calculator", "Strategy Payoff Builder"])

    # TAB 1: OPTION CHAIN
    with opt_tab1:
        oc1, oc2, oc3 = st.columns([1.5, 1, 1])
        with oc1:
            underlying = st.selectbox("Underlying Index / Stock", ["NIFTY 50", "BANKNIFTY", "RELIANCE", "TCS"])
        with oc2:
            dte = st.slider("Days to Expiry (DTE)", min_value=1, max_value=30, value=7)
        with oc3:
            spot = 24650.0 if "NIFTY" in underlying else (51200.0 if "BANK" in underlying else 2840.0)
            st.metric("Underlying Spot Price", f"₹{spot:,.2f}")

        step = 50.0 if "NIFTY" in underlying else (100.0 if "BANK" in underlying else 20.0)
        chain = generate_synthetic_option_chain(underlying=underlying, spot_price=spot, strike_step=step, num_strikes=10, days_to_expiry=dte)

        # PCR and Max Pain Banner
        st.markdown(
            f"**Put-Call Ratio (PCR):** `{chain.pcr:.2f}` • **Max Pain Strike:** `₹{chain.max_pain:,.0f}` • **ATM Strike:** `₹{chain.atm_strike:,.0f}`"
        )

        chain_rows = []
        for s in chain.strikes:
            chain_rows.append({
                "CE OI": f"{s.ce_oi:,}",
                "CE IV (%)": f"{s.ce_iv:.1f}",
                "CE Delta": f"{s.ce_delta:.2f}",
                "CE Price (₹)": f"{s.ce_price:.2f}",
                "Strike": f"{s.strike:,.0f}",
                "PE Price (₹)": f"{s.pe_price:.2f}",
                "PE Delta": f"{s.pe_delta:.2f}",
                "PE IV (%)": f"{s.pe_iv:.1f}",
                "PE OI": f"{s.pe_oi:,}",
            })
        st.dataframe(pd.DataFrame(chain_rows), use_container_width=True, hide_index=True)

    # TAB 2: GREEKS CALCULATOR
    with opt_tab2:
        st.subheader("Black-Scholes Options Greeks Pricing Model")
        gc1, gc2, gc3, gc4 = st.columns(4)
        with gc1:
            g_spot = st.number_input("Spot Price", value=24650.0, step=50.0)
            g_strike = st.number_input("Strike Price", value=24700.0, step=50.0)
        with gc2:
            g_dte = st.number_input("Days to Expiry", value=7, min_value=1, max_value=365)
            g_iv = st.number_input("Implied Volatility (%)", value=14.0, step=0.5) / 100.0
        with gc3:
            g_rate = st.number_input("Risk-Free Rate (%)", value=6.5, step=0.1) / 100.0
            g_type = st.radio("Option Type", ["CE (Call)", "PE (Put)"], horizontal=True)
        with gc4:
            st.write("")
            st.write("")
            calc_btn = st.button("Recalculate Greeks", type="primary")

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
            st.metric("Option Price", f"₹{greeks.price:,.2f}")
        with gm2:
            st.metric("Delta (Δ)", f"{greeks.delta:+.4f}")
        with gm3:
            st.metric("Gamma (Γ)", f"{greeks.gamma:.6f}")
        with gm4:
            st.metric("Theta (Θ / Day)", f"₹{greeks.theta:,.2f}")
        with gm5:
            st.metric("Vega (ν / 1% IV)", f"₹{greeks.vega:,.2f}")

    # TAB 3: STRATEGY PAYOFF BUILDER
    with opt_tab3:
        st.subheader("Multi-Leg Options Strategy Payoff Simulator")
        spread_type = st.selectbox(
            "Pre-Built Strategy Template",
            ["Bull Call Spread", "Bear Put Spread", "Long Straddle", "Iron Condor"],
        )

        atm = 24650.0
        if spread_type == "Bull Call Spread":
            legs = [
                {"type": "CE", "strike": atm, "action": "BUY", "premium": 150.0, "qty": 1},
                {"type": "CE", "strike": atm + 200.0, "action": "SELL", "premium": 60.0, "qty": 1},
            ]
        elif spread_type == "Bear Put Spread":
            legs = [
                {"type": "PE", "strike": atm, "action": "BUY", "premium": 140.0, "qty": 1},
                {"type": "PE", "strike": atm - 200.0, "action": "SELL", "premium": 50.0, "qty": 1},
            ]
        elif spread_type == "Long Straddle":
            legs = [
                {"type": "CE", "strike": atm, "action": "BUY", "premium": 150.0, "qty": 1},
                {"type": "PE", "strike": atm, "action": "BUY", "premium": 140.0, "qty": 1},
            ]
        else:
            legs = [
                {"type": "PE", "strike": atm - 400.0, "action": "BUY", "premium": 25.0, "qty": 1},
                {"type": "PE", "strike": atm - 200.0, "action": "SELL", "premium": 65.0, "qty": 1},
                {"type": "CE", "strike": atm + 200.0, "action": "SELL", "premium": 70.0, "qty": 1},
                {"type": "CE", "strike": atm + 400.0, "action": "BUY", "premium": 28.0, "qty": 1},
            ]

        # Calculate Payoff Curve across Spot Range
        spot_range = [atm - 800 + i * 20 for i in range(81)]
        payoff_data = calculate_spread_payoff(spread_type, spot_range, legs)
        p_df = pd.DataFrame(payoff_data)

        # Plot Payoff Diagram
        fig_payoff = go.Figure()
        fig_payoff.add_trace(
            go.Scatter(
                x=p_df["spot"],
                y=p_df["pnl"],
                mode="lines",
                line=dict(color="#38bdf8", width=3),
                name="Net Payoff (₹)",
            )
        )
        fig_payoff.add_hline(y=0, line_dash="dash", line_color="#94a3b8")
        fig_payoff.add_vline(x=atm, line_dash="dot", line_color="#f59e0b", annotation_text="Current Spot")

        fig_payoff.update_layout(
            title=f"<b>{spread_type}</b> — Expiry Payoff Curve (₹)",
            template="plotly_dark",
            plot_bgcolor="#0b0f19",
            paper_bgcolor="#0b0f19",
            xaxis_title="Underlying Price at Expiry",
            yaxis_title="Profit / Loss (₹)",
            height=380,
            margin=dict(l=40, r=40, t=40, b=30),
        )
        st.plotly_chart(fig_payoff, use_container_width=True)
