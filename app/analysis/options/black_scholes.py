"""Black-Scholes-Merton pricing, greeks and implied volatility.

All functions use years-denominated time to expiry.
"""

from __future__ import annotations

import math

from app.models.enums import OptionType

#: Assume a risk-free rate if none is provided (INR ~6.5%).
DEFAULT_RISK_FREE_RATE = 0.065
#: Calendar days per year for theta/vega annualisation.
DAYS_PER_YEAR = 365.0


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _norm_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def d1_d2(
    spot: float,
    strike: float,
    time_to_expiry_years: float,
    sigma: float,
    risk_free_rate: float = DEFAULT_RISK_FREE_RATE,
) -> tuple[float, float]:
    if spot <= 0 or strike <= 0 or time_to_expiry_years <= 0 or sigma <= 0:
        raise ValueError(
            "spot/strike/T/vol must be positive for d1/d2"
        )
    sqrt_t = math.sqrt(time_to_expiry_years)
    d1 = (
        math.log(spot / strike)
        + (risk_free_rate + 0.5 * sigma**2) * time_to_expiry_years
    ) / (sigma * sqrt_t)
    d2 = d1 - sigma * sqrt_t
    return d1, d2


def bsm_price(
    spot: float,
    strike: float,
    time_to_expiry_years: float,
    sigma: float,
    risk_free_rate: float = DEFAULT_RISK_FREE_RATE,
    option_type: OptionType = OptionType.CALL,
) -> float:
    d1, d2 = d1_d2(spot, strike, time_to_expiry_years, sigma, risk_free_rate)
    disc = math.exp(-risk_free_rate * time_to_expiry_years)
    if option_type == OptionType.CALL:
        return spot * _norm_cdf(d1) - strike * disc * _norm_cdf(d2)
    return strike * disc * _norm_cdf(-d2) - spot * _norm_cdf(-d1)


def greeks(
    spot: float,
    strike: float,
    time_to_expiry_years: float,
    sigma: float,
    risk_free_rate: float = DEFAULT_RISK_FREE_RATE,
    option_type: OptionType = OptionType.CALL,
) -> dict[str, float]:
    """Return delta, gamma, theta_daily, vega for one option."""
    d1, d2 = d1_d2(spot, strike, time_to_expiry_years, sigma, risk_free_rate)
    sqrt_t = math.sqrt(time_to_expiry_years)
    pdf = _norm_pdf(d1)
    disc = math.exp(-risk_free_rate * time_to_expiry_years)

    if option_type == OptionType.CALL:
        delta = _norm_cdf(d1)
        theta = -(spot * pdf * sigma) / (2.0 * sqrt_t) - risk_free_rate * strike * disc * _norm_cdf(d2)
    else:
        delta = _norm_cdf(d1) - 1.0
        theta = -(spot * pdf * sigma) / (2.0 * sqrt_t) + risk_free_rate * strike * disc * _norm_cdf(-d2)

    gamma = pdf / (spot * sigma * sqrt_t)
    vega = spot * pdf * sqrt_t / 100.0  # per 1 vol point (as 0.01)

    return {
        "delta": delta,
        "gamma": gamma,
        "theta": theta / DAYS_PER_YEAR,  # daily
        "vega": vega,
    }


def implied_volatility(
    spot: float,
    strike: float,
    time_to_expiry_years: float,
    market_price: float,
    risk_free_rate: float = DEFAULT_RISK_FREE_RATE,
    option_type: OptionType = OptionType.CALL,
    lo: float = 0.001,
    hi: float = 5.0,
    tolerance: float = 1e-8,
    max_iter: int = 200,
) -> float | None:
    """Bisection implied volatility (decimal) or None when unmodelable."""
    if market_price <= 0:
        return None
    intrinsic = (
        max(0.0, spot - strike)
        if option_type == OptionType.CALL
        else max(0.0, strike - spot)
    )
    if market_price < intrinsic - 1e-9:
        return None  # arbitrage; no IV
    if lo >= hi:
        return None
    for _ in range(max_iter):
        mid = 0.5 * (lo + hi)
        try:
            price = bsm_price(
                spot, strike, time_to_expiry_years, mid, risk_free_rate, option_type
            )
        except ValueError:
            return None
        if abs(price - market_price) < tolerance:
            return mid
        if price < market_price:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)