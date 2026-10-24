from dataclasses import asdict, dataclass
from typing import Any
import numpy as np
from app.options.greeks import calculate_greeks


@dataclass
class OptionStrikeData:
    strike: float
    ce_price: float
    ce_oi: int
    ce_volume: int
    ce_delta: float
    ce_iv: float
    pe_price: float
    pe_oi: int
    pe_volume: int
    pe_delta: float
    pe_iv: float


@dataclass
class OptionChain:
    underlying: str
    spot_price: float
    expiry_date: str
    strikes: list[OptionStrikeData]
    atm_strike: float
    pcr: float
    max_pain: float


def generate_synthetic_option_chain(
    underlying: str = "NIFTY",
    spot_price: float = 24500.0,
    strike_step: float = 50.0,
    num_strikes: int = 15,
    days_to_expiry: int = 7,
    base_iv: float = 0.14,
) -> OptionChain:
    """Generate realistic NSE-style option chain with realistic volatility smile and open interest."""
    expiry_years = max(days_to_expiry / 365.0, 1e-4)
    atm_strike = round(spot_price / strike_step) * strike_step

    strikes_list = []
    total_ce_oi = 0
    total_pe_oi = 0
    strike_range = [atm_strike + i * strike_step for i in range(-num_strikes, num_strikes + 1)]

    for strike in strike_range:
        # Volatility smile: IV higher OTM
        moneyness = (strike - spot_price) / spot_price
        strike_iv = base_iv + 0.15 * (moneyness ** 2)

        ce_greeks = calculate_greeks(spot_price, strike, expiry_years, iv=strike_iv, option_type="CE")
        pe_greeks = calculate_greeks(spot_price, strike, expiry_years, iv=strike_iv, option_type="PE")

        # Realistic OI distribution: peaks around key round strikes
        dist_factor = np.exp(-0.5 * (moneyness / 0.03) ** 2)
        base_oi = int(100_000 * dist_factor) + 5_000
        ce_oi = int(base_oi * (1.2 if strike > spot_price else 0.8))
        pe_oi = int(base_oi * (1.2 if strike < spot_price else 0.8))

        total_ce_oi += ce_oi
        total_pe_oi += pe_oi

        strikes_list.append(
            OptionStrikeData(
                strike=strike,
                ce_price=ce_greeks.price,
                ce_oi=ce_oi,
                ce_volume=int(ce_oi * 0.4),
                ce_delta=ce_greeks.delta,
                ce_iv=round(strike_iv * 100, 1),
                pe_price=pe_greeks.price,
                pe_oi=pe_oi,
                pe_volume=int(pe_oi * 0.4),
                pe_delta=pe_greeks.delta,
                pe_iv=round(strike_iv * 100, 1),
            )
        )

    pcr = round(total_pe_oi / total_ce_oi, 2) if total_ce_oi > 0 else 1.0

    # Max Pain calculation: strike where option writers lose the least
    pain_by_strike = []
    for test_strike in strike_range:
        total_loss = 0.0
        for s in strikes_list:
            ce_loss = max(0.0, test_strike - s.strike) * s.ce_oi
            pe_loss = max(0.0, s.strike - test_strike) * s.pe_oi
            total_loss += ce_loss + pe_loss
        pain_by_strike.append((total_loss, test_strike))

    max_pain = min(pain_by_strike, key=lambda x: x[0])[1]

    return OptionChain(
        underlying=underlying,
        spot_price=spot_price,
        expiry_date=f"{days_to_expiry}D DTE",
        strikes=strikes_list,
        atm_strike=atm_strike,
        pcr=pcr,
        max_pain=max_pain,
    )


def calculate_spread_payoff(
    strategy_type: str,
    spot_range: list[float],
    legs: list[dict[str, Any]],
) -> list[dict[str, float]]:
    """Calculate multi-leg option spread payoff across underlying prices.
    
    Each leg: {"type": "CE"|"PE", "strike": float, "action": "BUY"|"SELL", "premium": float, "qty": int}
    """
    payoff_curve = []
    for price in spot_range:
        pnl = 0.0
        for leg in legs:
            is_call = leg["type"].upper() == "CE"
            action = leg["action"].upper()
            strike = leg["strike"]
            premium = leg["premium"]
            qty = leg.get("qty", 1)

            intrinsic = max(0.0, price - strike) if is_call else max(0.0, strike - price)
            leg_pnl = (intrinsic - premium) if action == "BUY" else (premium - intrinsic)
            pnl += leg_pnl * qty

        payoff_curve.append({"spot": price, "pnl": round(pnl, 2)})

    return payoff_curve
