"""Tests for Dhan Portfolio, Margin Calculator, and Options Chains."""

import pytest
from app.brokers.dhan.options import DhanOptionsManager
from app.brokers.dhan.portfolio import DhanPortfolioManager


def test_dhan_portfolio_funds_positions_holdings():
    pm = DhanPortfolioManager()
    funds = pm.get_fund_limits()
    assert funds.available_cash > 0
    assert funds.net_equity >= funds.available_cash

    positions = pm.get_positions()
    assert len(positions) > 0
    assert positions[0].symbol == "RELIANCE"
    assert positions[0].net_quantity > 0

    holdings = pm.get_holdings()
    assert len(holdings) > 0
    assert holdings[0].symbol == "INFY"
    assert holdings[0].total_quantity > 0


def test_dhan_margin_calculator():
    pm = DhanPortfolioManager()
    # CNC delivery margin (100%)
    res_cnc = pm.calculate_margin(
        security_id="2885",
        exchange_segment="NSE_EQ",
        transaction_type="BUY",
        quantity=10,
        product_type="CNC",
        price=2800.0,
    )
    assert res_cnc.total_margin_required == 28000.0
    assert res_cnc.sufficient_funds is True

    # INTRADAY margin (20% with 5x leverage)
    res_intra = pm.calculate_margin(
        security_id="2885",
        exchange_segment="NSE_EQ",
        transaction_type="BUY",
        quantity=10,
        product_type="INTRADAY",
        price=2800.0,
    )
    assert res_intra.total_margin_required == 5600.0


def test_dhan_options_expiry_and_chain():
    om = DhanOptionsManager()
    expiries = om.get_expiry_list("NIFTY")
    assert len(expiries) > 0
    assert "2026-" in expiries[0]

    chain = om.get_option_chain("NIFTY", expiry=expiries[0])
    assert chain.underlying_symbol == "NIFTY"
    assert len(chain.strikes) > 0

    atm_strike = chain.strikes[len(chain.strikes) // 2]
    assert atm_strike.strike_price > 0
    assert atm_strike.ce_ltp > 0
    assert atm_strike.pe_ltp > 0
    # Greeks presence
    assert 0.0 <= atm_strike.ce_delta <= 1.0
    assert -1.0 <= atm_strike.pe_delta <= 0.0
