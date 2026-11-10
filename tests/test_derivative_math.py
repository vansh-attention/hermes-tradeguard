"""Offline oracle, identity, unit and adversarial tests for derivative math."""

import math
from decimal import Decimal, localcontext

import pytest


def test_bsm_reference_prices_and_put_call_parity():
    from tradeguard.derivative_math import bsm_price

    call = bsm_price(100, 100, 1, .05, 0, .2, right="call")
    put = bsm_price(100, 100, 1, .05, 0, .2, right="put")
    assert call == pytest.approx(10.450583572185565, abs=1e-12)
    assert put == pytest.approx(5.573526022256971, abs=1e-12)
    assert call - put == pytest.approx(100 - 100 * math.exp(-.05), abs=1e-12)


@pytest.mark.parametrize("index", range(6))
@pytest.mark.parametrize("bad", [True, False, None, float("nan"), float("inf"), float("-inf"), "NaN", "Infinity", {}, [], complex(1, 1)])
def test_bsm_rejects_nonfinite_and_non_model_values(index, bad):
    from tradeguard.derivative_math import bsm_price

    values = [100, 100, 1, .05, 0, .2]
    values[index] = bad
    with pytest.raises(ValueError):
        bsm_price(*values, right="call")


@pytest.mark.parametrize("index,bad", [
    (0, 0), (0, -1), (0, 1e12 + 1),
    (1, 0), (1, -1), (1, 1e12 + 1),
    (2, 0), (2, -1), (2, 10.01),
    (3, -1.01), (3, 1.01),
    (4, -.01), (4, 1.01),
    (5, 0), (5, -.1), (5, 5.01),
])
def test_bsm_rejects_expiry_and_outside_supported_domain(index, bad):
    from tradeguard.derivative_math import bsm_price

    values = [100, 100, 1, .05, 0, .2]
    values[index] = bad
    with pytest.raises(ValueError, match="domain"):
        bsm_price(*values, right="call")


@pytest.mark.parametrize("right", ["CALL", "american", "future", "", None, True, [], {}])
def test_bsm_right_must_be_explicit_call_or_put(right):
    from tradeguard.derivative_math import bsm_price

    with pytest.raises(ValueError, match="right"):
        bsm_price(100, 100, 1, .05, 0, .2, right=right)


def test_bsm_accepts_decimal_strings_and_requires_rate_and_yield():
    from tradeguard.derivative_math import bsm_price

    assert bsm_price("100", Decimal("100"), "1", ".05", "0", ".2", right="call") == pytest.approx(10.450583572185565)
    with pytest.raises(TypeError):
        bsm_price(100, 100, 1, volatility=.2, right="call")
    with pytest.raises(TypeError):
        bsm_price(100, 100, 1, .05, volatility=.2, right="call")


@pytest.mark.parametrize("right", ["call", "put"])
@pytest.mark.parametrize("spot,strike,years,rate,yield_", [
    (100, 110, .5, -.02, .03), (140, 100, 2, -.03, .07),
    (1, 1000, .01, .1, .2), (1000, 1, 10, -1, 1),
])
def test_bsm_yield_negative_rates_bounds_and_volatility_monotonicity(right, spot, strike, years, rate, yield_):
    from tradeguard.derivative_math import bsm_price

    prices = [bsm_price(spot, strike, years, rate, yield_, vol, right=right) for vol in (.01, .2, 1, 5)]
    assert prices == sorted(prices)
    discounted_spot = spot * math.exp(-yield_ * years)
    discounted_strike = strike * math.exp(-rate * years)
    lower = max(0, discounted_spot - discounted_strike) if right == "call" else max(0, discounted_strike - discounted_spot)
    upper = discounted_spot if right == "call" else discounted_strike
    for price in prices:
        assert math.isfinite(price)
        assert lower - 1e-9 <= price <= upper + 1e-9
    call = bsm_price(spot, strike, years, rate, yield_, .2, right="call")
    put = bsm_price(spot, strike, years, rate, yield_, .2, right="put")
    assert call - put == pytest.approx(discounted_spot - discounted_strike, abs=1e-9)


def test_greeks_reference_units():
    from tradeguard.derivative_math import bsm_greeks

    greeks = bsm_greeks(100, 100, 1, .05, 0, .2, right="call")
    assert greeks == pytest.approx({
        "delta": .6368306511756191,
        "gamma": .018762017345846895,
        "vega_per_vol_point": .3752403469169379,
        "theta_per_calendar_day": -.01757267820941972,
        "rho_per_rate_point": .5323248154537634,
    }, abs=1e-12)


@pytest.mark.parametrize("right", ["call", "put"])
@pytest.mark.parametrize("spot,strike,years,rate,yield_,vol", [
    (100, 100, 1, .05, 0, .2),
    (95, 100, .7, -.025, .04, .35),
    (125, 100, 1.8, .03, .08, .4),
])
def test_greeks_match_price_finite_differences(right, spot, strike, years, rate, yield_, vol):
    from tradeguard.derivative_math import bsm_greeks, bsm_price

    def price(s=spot, t=years, r=rate, v=vol):
        return bsm_price(s, strike, t, r, yield_, v, right=right)

    g = bsm_greeks(spot, strike, years, rate, yield_, vol, right=right)
    h = spot * 1e-4
    eps = 1e-5
    assert g["delta"] == pytest.approx((price(s=spot + h) - price(s=spot - h)) / (2 * h), rel=2e-7)
    assert g["gamma"] == pytest.approx((price(s=spot + h) - 2 * price() + price(s=spot - h)) / h**2, rel=2e-6)
    assert g["vega_per_vol_point"] == pytest.approx((price(v=vol + eps) - price(v=vol - eps)) / (2 * eps * 100), rel=2e-8)
    assert g["rho_per_rate_point"] == pytest.approx((price(r=rate + eps) - price(r=rate - eps)) / (2 * eps * 100), rel=2e-8)
    assert g["theta_per_calendar_day"] == pytest.approx((price(t=years - eps) - price(t=years + eps)) / (2 * eps * 365), rel=2e-8)
    assert g["gamma"] > 0
    assert g["vega_per_vol_point"] > 0
    assert all(math.isfinite(value) for value in g.values())


def test_greek_put_call_yield_and_rate_parities():
    from tradeguard.derivative_math import bsm_greeks

    s, k, t, r, q, v = 95, 100, .7, -.025, .04, .35
    call = bsm_greeks(s, k, t, r, q, v, right="call")
    put = bsm_greeks(s, k, t, r, q, v, right="put")
    assert call["delta"] - put["delta"] == pytest.approx(math.exp(-q * t))
    assert call["gamma"] == pytest.approx(put["gamma"])
    assert call["vega_per_vol_point"] == pytest.approx(put["vega_per_vol_point"])
    assert call["rho_per_rate_point"] - put["rho_per_rate_point"] == pytest.approx(k * t * math.exp(-r * t) / 100)
    assert call["theta_per_calendar_day"] - put["theta_per_calendar_day"] == pytest.approx((q * s * math.exp(-q * t) - r * k * math.exp(-r * t)) / 365)


@pytest.mark.parametrize("model", ["bsm_price", "bsm_greeks"])
def test_model_unrepresentable_standard_deviation_fails_explicitly(model):
    from tradeguard import derivative_math

    with pytest.raises(ValueError, match="NUMERICAL"):
        getattr(derivative_math, model)(100, 100, 5e-324, .05, 0, 5e-324, right="call")


def test_greek_unrepresentable_sensitivity_fails_explicitly():
    from tradeguard.derivative_math import bsm_greeks

    with pytest.raises(ValueError, match="NUMERICAL"):
        bsm_greeks(5e-324, 5e-324, 1, 0, 0, .2, right="put")


def test_futures_pnl_uses_multiplier_once_and_handles_negative_prices():
    from tradeguard.derivative_math import futures_pnl

    assert futures_pnl("100", "101", "5", side="long", contracts=2) == Decimal("10")
    assert futures_pnl("100", "101", "5", side="short") == Decimal("-5")
    assert futures_pnl("1", "-1", "5", side="long") == Decimal("-10")
    assert futures_pnl("-2", "1", "5", side="short") == Decimal("-15")
    assert futures_pnl(Decimal("100.1"), "100.3", "2.5", side="long", contracts=3) == Decimal("1.5")
    with pytest.raises(ValueError):
        futures_pnl("100", "101", "5", side="long", contracts=True)


def test_futures_long_precision_is_exact_and_context_independent():
    from tradeguard.derivative_math import futures_pnl

    entry = Decimal("1." + "0" * 95 + "1")
    exit_price = Decimal("2." + "0" * 95 + "3")
    multiplier = Decimal("3." + "1" * 96)
    with localcontext() as reference:
        reference.prec = 512
        expected = (exit_price - entry) * multiplier * 100
        extremes = (Decimal("1e-100") - Decimal("1e30")) * Decimal("1e-100")
    with localcontext() as caller:
        caller.prec = 5
        caller.Emax = 9
        caller.Emin = -9
        before = caller.copy()
        actual = futures_pnl(entry, exit_price, multiplier, side="long", contracts=100)
        assert actual == expected
        assert caller.prec == before.prec
        assert caller.Emax == before.Emax
        assert caller.Emin == before.Emin
        assert caller.flags == before.flags
    assert futures_pnl(Decimal("1e30"), Decimal("1e-100"), Decimal("1e-100"), side="long") == extremes


def test_long_option_expiry_payoff_and_quantity():
    from tradeguard.derivative_math import long_option_pnl

    assert long_option_pnl("110", "100", "3", "5", right="call") == Decimal("35")
    assert long_option_pnl("90", "100", "3", "5", right="put", contracts=2) == Decimal("70")
    assert long_option_pnl("100", "100", "3", "5", right="call") == Decimal("-15")
    assert long_option_pnl("0", "100", "3", "5", right="put") == Decimal("485")
    assert long_option_pnl("0", "100", "3", "5", right="call") == Decimal("-15")
    assert long_option_pnl("100", "100", 0, 5, right="put") == Decimal(0)


@pytest.mark.parametrize("index,bad", [(0, "-1"), (1, "0"), (1, "-1"), (2, "-0.01"), (3, "0"), (3, "-1")])
def test_long_option_rejects_invalid_payoff_domain(index, bad):
    from tradeguard.derivative_math import long_option_pnl

    values = ["110", "100", "3", "5"]
    values[index] = bad
    with pytest.raises(ValueError):
        long_option_pnl(*values, right="call")


@pytest.mark.parametrize("right", ["call", "put"])
def test_long_option_exact_precision_and_piecewise_expiry_bounds(right):
    from tradeguard.derivative_math import long_option_pnl

    strike = Decimal("100." + "1" * 90)
    premium = Decimal("3." + "9" * 90)
    multiplier = Decimal("5." + "3" * 90)
    terminal = Decimal("110." + "7" * 90) if right == "call" else Decimal("90." + "7" * 90)
    with localcontext() as reference:
        reference.prec = 512
        intrinsic = max(terminal - strike if right == "call" else strike - terminal, 0)
        expected = (intrinsic - premium) * multiplier * 100
    with localcontext() as caller:
        caller.prec = 6
        assert long_option_pnl(terminal, strike, premium, multiplier, right=right, contracts=100) == expected
        assert caller.prec == 6
    pnls = [long_option_pnl(str(spot), "100", "3", "5", right=right, contracts=2) for spot in (0, 90, 97, 100, 103, 110, 1000)]
    assert min(pnls) == Decimal("-30")
    assert pnls == sorted(pnls, reverse=right == "put")
    assert long_option_pnl("103" if right == "call" else "97", "100", "3", "5", right=right) == Decimal(0)


@pytest.mark.parametrize("right,long_strike,short_strike,breakeven", [
    ("call", "100", "110", "104"), ("put", "110", "100", "106"),
])
def test_debit_vertical_gross_bounds(right, long_strike, short_strike, breakeven):
    from tradeguard.derivative_math import debit_vertical

    assert debit_vertical(long_strike, short_strike, "6", "2", "5", right=right) == {
        "debit": Decimal("20"), "max_loss_gross": Decimal("20"),
        "max_profit_gross": Decimal("30"), "breakeven": Decimal(breakeven),
    }
    assert debit_vertical(long_strike, short_strike, "6", "2", "5", right=right, contracts=2) == {
        "debit": Decimal("40"), "max_loss_gross": Decimal("40"),
        "max_profit_gross": Decimal("60"), "breakeven": Decimal(breakeven),
    }


@pytest.mark.parametrize("right,kl,ks,ask,bid,multiplier", [
    ("call", "110", "100", "6", "2", "5"),
    ("put", "100", "110", "6", "2", "5"),
    ("call", "100", "100", "6", "2", "5"),
    ("call", "0", "10", "6", "2", "5"),
    ("call", "-10", "10", "6", "2", "5"),
    ("put", "10", "0", "6", "2", "5"),
    ("put", "10", "-10", "6", "2", "5"),
    ("call", "100", "110", "2", "2", "5"),
    ("call", "100", "110", "1", "2", "5"),
    ("call", "100", "110", "12", "2", "5"),
    ("call", "100", "110", "13", "2", "5"),
    ("call", "100", "110", "-1", "2", "5"),
    ("call", "100", "110", "6", "-1", "5"),
    ("call", "100", "110", "6", "2", "0"),
    ("call", "100", "110", "6", "2", "-5"),
    ("credit", "100", "110", "6", "2", "5"),
    (None, "100", "110", "6", "2", "5"),
])
def test_vertical_rejects_invalid_direction_price_or_debit(right, kl, ks, ask, bid, multiplier):
    from tradeguard.derivative_math import debit_vertical

    with pytest.raises(ValueError):
        debit_vertical(kl, ks, ask, bid, multiplier, right=right)


@pytest.mark.parametrize("right", ["call", "put"])
def test_vertical_exact_precision_and_piecewise_bounds(right):
    from tradeguard.derivative_math import debit_vertical, long_option_pnl

    kl = Decimal(("100." if right == "call" else "110.") + "1" * 90)
    ks = Decimal(("110." if right == "call" else "100.") + "2" * 90)
    ask, bid, multiplier = Decimal("6." + "9" * 90), Decimal("2." + "3" * 90), Decimal("5." + "7" * 90)
    with localcontext() as reference:
        reference.prec = 512
        debit_points = ask - bid
        expected = {
            "debit": debit_points * multiplier * 100,
            "max_loss_gross": debit_points * multiplier * 100,
            "max_profit_gross": (abs(ks - kl) - debit_points) * multiplier * 100,
            "breakeven": kl + debit_points if right == "call" else kl - debit_points,
        }
    with localcontext() as caller:
        caller.prec = 5
        before = caller.copy()
        assert debit_vertical(kl, ks, ask, bid, multiplier, right=right, contracts=100) == expected
        assert caller.prec == before.prec
        assert caller.flags == before.flags
    kl, ks = ("100", "110") if right == "call" else ("110", "100")
    bounds = debit_vertical(kl, ks, "6", "2", "5", right=right)
    pnls = [long_option_pnl(str(spot), kl, "6", "5", right=right) - long_option_pnl(str(spot), ks, "2", "5", right=right) for spot in (0, 90, 100, 104, 106, 110, 120, 1000)]
    assert min(pnls) == -bounds["max_loss_gross"]
    assert max(pnls) == bounds["max_profit_gross"]
    assert long_option_pnl(bounds["breakeven"], kl, "6", "5", right=right) - long_option_pnl(bounds["breakeven"], ks, "2", "5", right=right) == 0


@pytest.mark.parametrize("right", ["call", "put"])
@pytest.mark.parametrize("s,k,t,r,q,vol", [(100, 100, 1, .05, 0, .2), (100, 110, .7, -.01, .03, .35), (110, 100, .8, .02, .05, .45)])
def test_implied_volatility_round_trip(right, s, k, t, r, q, vol):
    from tradeguard.derivative_math import bsm_price, implied_volatility
    premium = bsm_price(s, k, t, r, q, vol, right=right)
    actual = implied_volatility(premium, s, k, t, r, q, right=right)
    assert actual == pytest.approx(vol, abs=1e-7)
    assert bsm_price(s, k, t, r, q, actual, right=right) == pytest.approx(premium, abs=1e-8)


@pytest.mark.parametrize("premium", [True, False, 0, -1, None, {}, [], float("nan"), float("inf"), "NaN", "Infinity", 100, 101])
def test_implied_volatility_rejects_bad_or_outside_bracket_quotes(premium):
    from tradeguard.derivative_math import implied_volatility
    with pytest.raises(ValueError):
        implied_volatility(premium, 100, 100, 1, .05, 0, right="call")


def test_implied_volatility_has_bounded_nonconvergence_not_a_clipped_answer(monkeypatch):
    from tradeguard import derivative_math
    calls = []
    def discontinuous(*args, **kwargs):
        vol = args[-1]
        calls.append(vol)
        return 0.0 if vol < 1 else 1.0
    monkeypatch.setattr(derivative_math, "bsm_price", discontinuous)
    with pytest.raises(ValueError, match="NO_CONVERGENCE"):
        derivative_math.implied_volatility(.5, 100, 100, 1, .05, 0, right="call")
    assert len(calls) <= 100 + 2


def test_implied_volatility_requires_conventions_and_supported_right():
    from tradeguard.derivative_math import implied_volatility
    with pytest.raises(TypeError):
        implied_volatility(10, 100, 100, 1, .05, right="call")
    with pytest.raises(ValueError):
        implied_volatility(10, 100, 100, 1, .05, 0, right="american")
