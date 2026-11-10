"""Offline derivative reports: synthetic observations are never live entries."""
from copy import deepcopy
from decimal import Decimal
import json

import pytest

AS_OF = "2026-11-10T08:00:00Z"


def _snapshot(kind="future"):
    from derivative_cases import snapshot
    return snapshot(kind=kind)


def test_futures_snapshot_is_compact_and_fixture_abstains():
    from tradeguard.derivatives import analyze_derivative_snapshot
    data = _snapshot()
    original = deepcopy(data)
    result = analyze_derivative_snapshot(data, as_of=AS_OF)
    assert result["success"] is True
    assert result["research_only"] is True
    assert result["data_mode"] == "fixture"
    assert result["recommendation"]["score"] is None
    assert result["recommendation"]["strong_buy"] is False
    assert result["recommendation"]["verdict"] == "ABSTAIN"
    assert result["metrics"]["futures"]["maximum_loss"] is None
    assert result["metrics"]["futures"]["account_affordability"] == "unverified"
    assert result["metrics"]["futures"]["tick_value"] == "1.25"
    assert len(result["metrics"]["futures"]["scenarios"]) == 5
    assert "bars" not in result and "bars" not in result["metrics"]
    assert len(json.dumps(result, allow_nan=False)) < 30000
    assert data == original


def test_futures_scenarios_use_each_actual_quote_side():
    from tradeguard.derivatives import analyze_derivative_snapshot
    s = _snapshot()
    result = analyze_derivative_snapshot(s, as_of=AS_OF)
    first = result["metrics"]["futures"]["scenarios"][0]
    price = Decimal(first["future_price"])
    multiplier = Decimal(s["contract"]["value_per_price_unit"])
    assert Decimal(first["long_gross_pnl"]) == (price - Decimal(s["quote"]["ask"])) * multiplier
    assert Decimal(first["short_gross_pnl"]) == (Decimal(s["quote"]["bid"]) - price) * multiplier
    assert result["recommendations"]["long"]["scope"] == "future_long"
    assert result["recommendations"]["short"]["scope"] == "future_short"


def test_option_pricing_has_explicit_model_and_greek_units():
    from tradeguard.derivatives import analyze_derivative_snapshot
    s = _snapshot("option")
    result = analyze_derivative_snapshot(s, as_of=AS_OF)
    assert result["success"] is True
    option = result["metrics"]["option"]
    assert Decimal(option["gross_max_loss"]) == Decimal(s["quote"]["ask"]) * Decimal(s["contract"]["value_per_price_unit"])
    assert option["max_profit_status"] == "unbounded"
    pricing = option["pricing"]
    assert pricing["status"] == "available"
    assert pricing["model"] == "BSM_EUROPEAN_CASH_INDEX_ACT365F"
    assert pricing["independent_valuation"] is False
    assert pricing["iv_bid"] <= pricing["iv_ask"]
    assert "theta_per_calendar_day" in pricing["greeks_per_premium_unit"]
    assert "vega_per_vol_point" in pricing["greeks_per_contract"]
    assert result["recommendation"]["score"] is None


def test_option_missing_rates_preserves_payoff_but_never_invents_greeks():
    from tradeguard.derivatives import analyze_derivative_snapshot
    s = _snapshot("option")
    s.pop("rates", None)
    r = analyze_derivative_snapshot(s, as_of=AS_OF)
    assert r["success"] is True
    assert r["metrics"]["option"]["gross_max_loss"] is not None
    assert r["metrics"]["option"]["pricing"]["status"] == "unavailable"
    assert r["metrics"]["option"]["pricing"]["greeks_per_premium_unit"] is None
    assert r["recommendation"]["score"] is None
    assert any("rates" in str(x).lower() for x in r["missing_data"])


def test_missing_costs_never_claim_net_risk_or_futures_affordability():
    from tradeguard.derivatives import analyze_derivative_snapshot
    s = _snapshot("option")
    s.pop("costs", None)
    r = analyze_derivative_snapshot(s, as_of=AS_OF)
    assert r["metrics"]["option"]["estimated_max_loss_including_supplied_costs"] is None
    assert r["recommendation"]["score"] is None


@pytest.mark.parametrize("style", ["american", "bermudan"])
def test_option_unsupported_exercise_is_not_silently_european(style):
    from tradeguard.derivatives import analyze_derivative_snapshot
    s = _snapshot("option")
    s["contract"]["exercise"] = style
    r = analyze_derivative_snapshot(s, as_of=AS_OF)
    assert r["success"] is False
    assert r["code"] == "UNSUPPORTED_INSTRUMENT"


def test_imported_provider_assertions_do_not_create_entry_score():
    from tradeguard.derivatives import analyze_derivative_snapshot
    s = _snapshot()
    s["source"]["data_mode"] = "provider"
    s["source"]["entitlement"] = "confirmed"
    r = analyze_derivative_snapshot(s, as_of=AS_OF)
    assert r["success"] is True
    assert r["data_mode"] == "user_supplied"
    assert r["recommendation"]["score"] is None
    assert r["source"]["entitlement"] == "unverified"


@pytest.mark.parametrize("value", [None, [], "bad", {}, {"contract": []}])
def test_malformed_snapshot_is_structured_not_a_traceback(value):
    from tradeguard.derivatives import analyze_derivative_snapshot
    r = analyze_derivative_snapshot(value, as_of=AS_OF)
    assert r["success"] is False
    assert r["research_only"] is True
    assert isinstance(r["code"], str)
    json.dumps(r, allow_nan=False)


def test_current_cutoff_does_not_hide_fixture_or_stale_quote():
    from tradeguard.derivatives import analyze_derivative_snapshot
    r = analyze_derivative_snapshot(_snapshot(), as_of="2026-11-10T09:00:00Z")
    assert r["success"] is True
    assert r["recommendation"]["score"] is None
    assert r["blockers"]


def _vertical():
    long = _snapshot("option")
    short = deepcopy(long)
    short["contract"]["contract_id"] += "-SHORT"
    short["quote"]["contract_id"] = short["contract"]["contract_id"]
    short["contract"]["strike"] = "110"
    short["quote"]["bid"], short["quote"]["ask"] = "2", "2.25"
    for field in ("margin", "costs"):
        if field in short:
            short[field]["contract_id"] = short["contract"]["contract_id"]
    return long, short


def test_matched_vertical_reports_both_ids_and_no_atomic_fill_claim():
    from tradeguard.derivatives import analyze_debit_vertical
    long, short = _vertical()
    r = analyze_debit_vertical(long, short, as_of=AS_OF)
    assert r["success"] is True
    assert r["strategy"] == "bull_call_debit"
    assert r["atomic_fill_guaranteed"] is False
    assert len(r["legs"]) == 2
    assert r["metrics"]["vertical"]["gross_max_loss"] == "20"
    assert r["metrics"]["vertical"]["gross_max_profit"] == "30"
    assert r["recommendation"]["score"] is None
    assert r["data_mode"] == "fixture"


@pytest.mark.parametrize("field,value", [("expiry_at", "2027-01-15T14:30:00Z"), ("value_per_price_unit", "10"), ("underlying_id", "TEST:WRONG"), ("right", "put")])
def test_vertical_rejects_mismatched_contract_legs(field, value):
    from tradeguard.derivatives import analyze_debit_vertical
    long, short = _vertical()
    short["contract"][field] = value
    r = analyze_debit_vertical(long, short, as_of=AS_OF)
    assert r["success"] is False
    assert r["research_only"] is True


def test_stale_option_rates_leave_all_model_outputs_unavailable():
    from tradeguard.derivatives import analyze_derivative_snapshot
    s = _snapshot("option")
    s["rates"]["as_of"] = "2026-10-01T08:00:00Z"
    r = analyze_derivative_snapshot(s, as_of=AS_OF)
    assert r["success"] is True
    assert r["metrics"]["option"]["pricing"]["status"] == "unavailable"
    assert r["recommendation"]["score"] is None


def test_request_wrapper_dispatches_single_and_two_leg_inputs():
    from tradeguard.derivatives import analyze_derivative_request
    long, short = _vertical()
    single = analyze_derivative_request(long, as_of=AS_OF)
    spread = analyze_derivative_request(long, short_leg=short, as_of=AS_OF)
    assert single["strategy"] == "long_call"
    assert spread["strategy"] == "bull_call_debit"
