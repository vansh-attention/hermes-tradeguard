"""Pure European cash-index mathematics, never American or futures-option pricing.

Model time is ACT/365F years and both rate inputs are continuously compounded
fractions, explicitly supplied by the caller. Model prices are per premium unit,
not contract cash values; no multiplier is applied by the BSM functions.
"""

import math
from decimal import Context, Decimal, localcontext

from .derivative_contracts import contract_quantity, decimal_value

# Canonical inputs have <=100 coefficient digits, exponents -100..30 and
# magnitude <=1e30. Sums/differences span <=132 places; multiplying by another
# input and <=100 contracts needs <256 digits. 512 is a conservative exact
# budget, not a money quantization. Copy this context; never mutate the caller's.
_MONEY_CONTEXT = Context(prec=512)


def futures_pnl(entry, exit_price, value_per_price_unit, *, side, contracts=1):
    """Gross linear cash P&L; the multiplier already includes the lot size.

    Negative entry/exit prices are mathematically valid; this does not expand
    the index-only recommendation universe. Margin is never a loss bound.
    """
    if side not in ("long", "short"):
        raise ValueError("side must be long or short")
    multiplier = decimal_value(value_per_price_unit)
    if multiplier <= 0:
        raise ValueError("positive multiplier required")
    quantity = contract_quantity(contracts)
    direction = 1 if side == "long" else -1
    with localcontext(_MONEY_CONTEXT):
        return (decimal_value(exit_price) - decimal_value(entry)) * multiplier * quantity * direction


def long_option_pnl(terminal_underlying, strike, premium, value_per_price_unit, *, right, contracts=1):
    """Gross long-option cash P&L at expiry, excluding fees and execution risk."""
    if right not in ("call", "put"):
        raise ValueError("right must be call or put")
    spot, strike, premium, multiplier = map(
        decimal_value, (terminal_underlying, strike, premium, value_per_price_unit),
    )
    if spot < 0 or strike <= 0 or premium < 0 or multiplier <= 0:
        raise ValueError("invalid option payoff inputs")
    quantity = contract_quantity(contracts)
    with localcontext(_MONEY_CONTEXT):
        intrinsic = max(spot - strike if right == "call" else strike - spot, Decimal(0))
        return (intrinsic - premium) * multiplier * quantity


def debit_vertical(long_strike, short_strike, long_ask, short_bid, value_per_price_unit, *, right, contracts=1):
    """Price-only bull-call / bear-put gross expiry bounds; no atomic-fill claim.

    The engine must separately bind expiry, underlier, right, currency,
    multiplier, deliverable and equal quantities of both European cash legs.
    """
    kl, ks, ask, bid, multiplier = map(
        decimal_value, (long_strike, short_strike, long_ask, short_bid, value_per_price_unit),
    )
    quantity = contract_quantity(contracts)
    if right not in ("call", "put"):
        raise ValueError("right must be call or put")
    if kl <= 0 or ks <= 0 or multiplier <= 0 or ask < 0 or bid < 0:
        raise ValueError("invalid debit spread inputs")
    if not (kl < ks if right == "call" else kl > ks):
        raise ValueError("unsupported vertical direction")
    with localcontext(_MONEY_CONTEXT):
        width, debit_points = abs(ks - kl), ask - bid
        if not 0 < debit_points < width:
            raise ValueError("debit must be between zero and strike width")
        scale = multiplier * quantity
        debit = debit_points * scale
        return {
            "debit": debit,
            "max_loss_gross": debit,
            "max_profit_gross": (width - debit_points) * scale,
            "breakeven": kl + debit_points if right == "call" else kl - debit_points,
        }


def _normal_cdf(value):
    return .5 * math.erfc(-value / math.sqrt(2))


def _bsm_inputs(spot, strike, years, rate, dividend_yield, volatility, right):
    values = (spot, strike, years, rate, dividend_yield, volatility)
    if any(isinstance(value, bool) for value in values):
        raise ValueError("boolean is not a model input")
    try:
        s, k, t, r, q, v = map(float, values)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("invalid model input") from exc
    if not all(math.isfinite(value) for value in (s, k, t, r, q, v)):
        raise ValueError("finite model inputs required")
    if not (0 < s <= 1e12 and 0 < k <= 1e12 and 0 < t <= 10
            and -1 <= r <= 1 and 0 <= q <= 1 and 0 < v <= 5):
        raise ValueError("model input outside supported domain")
    if right not in ("call", "put"):
        raise ValueError("right must be call or put")
    if v * math.sqrt(t) == 0:
        raise ValueError("MODEL_NUMERICAL_UNAVAILABLE: standard deviation underflow")
    return s, k, t, r, q, v


def bsm_price(spot, strike, years, rate, dividend_yield, volatility, *, right):
    """Return European cash-index premium units, not a fill or exercise model.

    Supported domain: spot/strike in (0, 1e12], ACT/365F years in (0, 10],
    continuous rate in [-1, 1], continuous yield in [0, 1], volatility in (0, 5].
    Expired/zero-volatility contracts deliberately have no model valuation here.
    """
    spot, strike, years, rate, dividend_yield, volatility = _bsm_inputs(
        spot, strike, years, rate, dividend_yield, volatility, right,
    )
    root_t = math.sqrt(years)
    d1 = (math.log(spot) - math.log(strike) + (rate - dividend_yield + volatility**2 / 2) * years) / (volatility * root_t)
    d2 = d1 - volatility * root_t
    sign = 1 if right == "call" else -1
    return sign * (
        spot * math.exp(-dividend_yield * years) * _normal_cdf(sign * d1)
        - strike * math.exp(-rate * years) * _normal_cdf(sign * d2)
    )


def bsm_greeks(spot, strike, years, rate, dividend_yield, volatility, *, right):
    """Return premium-unit sensitivities for the European cash-index model.

    Delta/gamma are per underlying point / point squared; vega and rho are per
    one percentage-point change (0.01); theta is per ACT/365F calendar day of
    elapsed time, not per year remaining. Contract cash scaling is caller-owned.
    """
    s, k, t, r, q, v = _bsm_inputs(spot, strike, years, rate, dividend_yield, volatility, right)
    root_t = math.sqrt(t)
    d1 = (math.log(s) - math.log(k) + (r - q + v * v / 2) * t) / (v * root_t)
    d2 = d1 - v * root_t
    dq, dr = math.exp(-q * t), math.exp(-r * t)
    density = math.exp(-d1 * d1 / 2) / math.sqrt(2 * math.pi)
    sign = 1 if right == "call" else -1
    theta = (
        -s * dq * density * v / (2 * root_t)
        + sign * (q * s * dq * _normal_cdf(sign * d1) - r * k * dr * _normal_cdf(sign * d2))
    ) / 365
    gamma_denominator = s * v * root_t
    if gamma_denominator == 0:
        raise ValueError("MODEL_NUMERICAL_UNAVAILABLE: gamma denominator underflow")
    greeks = {
        "delta": sign * dq * _normal_cdf(sign * d1),
        "gamma": dq * density / gamma_denominator,
        "vega_per_vol_point": s * dq * density * root_t / 100,
        "theta_per_calendar_day": theta,
        "rho_per_rate_point": sign * k * t * dr * _normal_cdf(sign * d2) / 100,
    }
    if not all(math.isfinite(value) for value in greeks.values()):
        raise ValueError("MODEL_NUMERICAL_UNAVAILABLE: nonfinite sensitivity")
    return greeks


def implied_volatility(price, spot, strike, years, rate, dividend_yield, *, right):
    """Invert a European premium in a fixed [1e-8, 5] volatility bracket.

    Returns an uncalibrated model parameter, not a forecast or independent
    valuation. A boundary/out-of-bracket quote, invalid convention, numerical
    failure or 100-step nonconvergence is explicitly unavailable, never clipped.
    Premium residual tolerance is max(1e-9 premium units, eight float ULPs).
    """
    if isinstance(price, bool):
        raise ValueError("invalid premium")
    try:
        target = float(price)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("invalid premium") from exc
    if not math.isfinite(target) or target <= 0:
        raise ValueError("positive finite premium required")
    low, high = 1e-8, 5.0
    _bsm_inputs(spot, strike, years, rate, dividend_yield, low, right)
    lower = bsm_price(spot, strike, years, rate, dividend_yield, low, right=right)
    upper = bsm_price(spot, strike, years, rate, dividend_yield, high, right=right)
    if not all(math.isfinite(value) for value in (lower, upper)):
        raise ValueError("IV_UNAVAILABLE_NUMERICAL_BOUNDS")
    if not lower < target < upper:
        raise ValueError("IV_UNAVAILABLE_OUTSIDE_SUPPORTED_BRACKET")
    tolerance = max(1e-9, 8 * math.ulp(target))
    for _ in range(100):
        mid = (low + high) / 2
        estimate = bsm_price(spot, strike, years, rate, dividend_yield, mid, right=right)
        if not math.isfinite(estimate):
            raise ValueError("IV_UNAVAILABLE_NUMERICAL_PRICE")
        if abs(estimate - target) <= tolerance:
            return mid
        if estimate < target:
            low = mid
        else:
            high = mid
    raise ValueError("IV_UNAVAILABLE_NO_CONVERGENCE")
