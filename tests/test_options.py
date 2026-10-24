import pytest
from app.options.chain import calculate_spread_payoff, generate_synthetic_option_chain
from app.options.greeks import black_scholes_price, calculate_greeks, implied_volatility


def test_black_scholes_call_and_put():
    # Spot 100, Strike 100, 1 Year, 5% rate, 20% vol
    call_p = black_scholes_price(100.0, 100.0, 1.0, 0.05, 0.20, "CE")
    put_p = black_scholes_price(100.0, 100.0, 1.0, 0.05, 0.20, "PE")
    assert round(call_p, 1) == 10.5
    assert round(put_p, 1) == 5.6


def test_calculate_greeks():
    g = calculate_greeks(spot=24500.0, strike=24500.0, expiry_years=7 / 365.0, iv=0.15, option_type="CE")
    # ATM call delta ~0.50
    assert 0.45 <= g.delta <= 0.55
    assert g.gamma > 0
    assert g.theta < 0  # theta decay is negative
    assert g.vega > 0


def test_implied_volatility_solver():
    target_price = 280.0
    iv = implied_volatility(market_price=target_price, spot=24500.0, strike=24500.0, expiry_years=7 / 365.0, option_type="CE")
    assert 0.10 <= iv <= 0.30


def test_option_chain_generation():
    chain = generate_synthetic_option_chain("NIFTY", 24500.0, strike_step=50.0, num_strikes=5, days_to_expiry=7)
    assert chain.underlying == "NIFTY"
    assert len(chain.strikes) == 11
    assert chain.atm_strike == 24500.0
    assert chain.pcr > 0
    assert chain.max_pain > 0


def test_spread_payoff():
    legs = [
        {"type": "CE", "strike": 24500.0, "action": "BUY", "premium": 150.0, "qty": 1},
        {"type": "CE", "strike": 24700.0, "action": "SELL", "premium": 50.0, "qty": 1},
    ]
    # Net debit = 100
    payoff = calculate_spread_payoff("Bull Call Spread", [24000.0, 24500.0, 24700.0, 25000.0], legs)
    assert len(payoff) == 4
    # Max loss = -100
    assert payoff[0]["pnl"] == -100.0
    # Max profit = 200 spread - 100 debit = 100
    assert payoff[3]["pnl"] == 100.0
