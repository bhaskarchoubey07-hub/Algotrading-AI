import math
from dataclasses import asdict, dataclass
from scipy.stats import norm


@dataclass
class OptionGreeks:
    price: float
    delta: float
    gamma: float
    theta: float  # daily theta decay
    vega: float   # 1% IV change sensitivity
    rho: float
    iv: float

    def to_dict(self) -> dict:
        return asdict(self)


def black_scholes_price(
    spot: float,
    strike: float,
    expiry_years: float,
    rate: float,
    iv: float,
    option_type: str = "CE",
) -> float:
    """Calculate Black-Scholes price for European option (CE = Call, PE = Put)."""
    if expiry_years <= 0:
        return max(0.0, spot - strike) if option_type.upper() == "CE" else max(0.0, strike - spot)
    if iv <= 0:
        return max(0.0, spot - strike) if option_type.upper() == "CE" else max(0.0, strike - spot)

    d1 = (math.log(spot / strike) + (rate + 0.5 * iv * iv) * expiry_years) / (iv * math.sqrt(expiry_years))
    d2 = d1 - iv * math.sqrt(expiry_years)

    if option_type.upper() == "CE":
        price = spot * norm.cdf(d1) - strike * math.exp(-rate * expiry_years) * norm.cdf(d2)
    else:
        price = strike * math.exp(-rate * expiry_years) * norm.cdf(-d2) - spot * norm.cdf(-d1)

    return max(0.0, price)


def calculate_greeks(
    spot: float,
    strike: float,
    expiry_years: float,
    rate: float = 0.07,  # RBI repo rate proxy ~6.5-7%
    iv: float = 0.15,    # 15% annualized volatility default
    option_type: str = "CE",
) -> OptionGreeks:
    """Calculate Black-Scholes option price and full Greeks suite."""
    is_call = option_type.upper() == "CE"

    if expiry_years <= 0 or iv <= 0:
        intrinsic = max(0.0, spot - strike) if is_call else max(0.0, strike - spot)
        delta = (1.0 if spot > strike else 0.0) if is_call else (-1.0 if spot < strike else 0.0)
        return OptionGreeks(price=intrinsic, delta=delta, gamma=0.0, theta=0.0, vega=0.0, rho=0.0, iv=iv)

    sqrt_t = math.sqrt(expiry_years)
    d1 = (math.log(spot / strike) + (rate + 0.5 * iv * iv) * expiry_years) / (iv * sqrt_t)
    d2 = d1 - iv * sqrt_t

    pdf_d1 = norm.pdf(d1)
    cdf_d1 = norm.cdf(d1)
    cdf_d2 = norm.cdf(d2)
    discount = math.exp(-rate * expiry_years)

    if is_call:
        price = spot * cdf_d1 - strike * discount * cdf_d2
        delta = cdf_d1
        theta = (- (spot * pdf_d1 * iv) / (2 * sqrt_t) - rate * strike * discount * cdf_d2) / 365.0
        rho = (strike * expiry_years * discount * cdf_d2) / 100.0
    else:
        price = strike * discount * norm.cdf(-d2) - spot * norm.cdf(-d1)
        delta = cdf_d1 - 1.0
        theta = (- (spot * pdf_d1 * iv) / (2 * sqrt_t) + rate * strike * discount * norm.cdf(-d2)) / 365.0
        rho = (- strike * expiry_years * discount * norm.cdf(-d2)) / 100.0

    gamma = pdf_d1 / (spot * iv * sqrt_t) if spot > 0 else 0.0
    vega = (spot * sqrt_t * pdf_d1) / 100.0  # scaled to 1% move in IV

    return OptionGreeks(
        price=round(max(0.0, price), 2),
        delta=round(delta, 4),
        gamma=round(gamma, 6),
        theta=round(theta, 2),
        vega=round(vega, 2),
        rho=round(rho, 4),
        iv=round(iv, 4),
    )


def implied_volatility(
    market_price: float,
    spot: float,
    strike: float,
    expiry_years: float,
    rate: float = 0.07,
    option_type: str = "CE",
    tol: float = 1e-4,
    max_iter: int = 100,
) -> float:
    """Solve for implied volatility using Newton-Raphson with bisection fallback."""
    if expiry_years <= 0 or market_price <= 0:
        return 0.0

    # Initial guess
    low, high = 0.01, 3.0
    vol = 0.20

    for _ in range(max_iter):
        p = black_scholes_price(spot, strike, expiry_years, rate, vol, option_type)
        diff = p - market_price
        if abs(diff) < tol:
            return round(vol, 4)

        # Vega for derivative
        g = calculate_greeks(spot, strike, expiry_years, rate, vol, option_type)
        v = g.vega * 100.0
        if v > 1e-4:
            new_vol = vol - diff / v
            if low <= new_vol <= high:
                vol = new_vol
                continue

        # Fallback to bisection
        if diff > 0:
            high = vol
        else:
            low = vol
        vol = 0.5 * (low + high)

    return round(vol, 4)
