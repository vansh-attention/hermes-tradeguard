"""Human payoff claims must expose analyzer inputs, units and evidence clocks."""
from copy import deepcopy

import pytest

from derivative_cases import AS_OF, snapshot
from test_derivatives import _vertical
from tradeguard.derivative_ui import render_derivative_results
from tradeguard.derivatives import analyze_debit_vertical, analyze_derivative_snapshot


def _single_result(kind="option", *, right="call"):
    contract = {"contract_id": "opaque-17"}
    quote = {"contract_id": "opaque-17", "observed_at": "2026-11-10T07:59:57Z",
             "received_at": "2026-11-10T07:59:58Z"}
    if kind == "option":
        contract.update(right=right, strike="117.25", value_per_price_unit="12.5")
        quote.update(bid="7", ask="7.25")
    data = snapshot(kind=kind, contract=contract, quote=quote,
                    margin={"contract_id": "opaque-17"},
                    costs={"contract_id": "opaque-17"},
                    underlying={"spot_observed_at": "2026-11-10T07:59:56Z"})
    result = analyze_derivative_snapshot(data, as_of=AS_OF)
    assert result["success"] is True
    return result


def _value(result, path):
    for key in path:
        result = result[key]
    return result


def _vertical_result(*, right="call"):
    long, short = _vertical()
    for data, contract_id, observed, received, spot_at in (
        (long, "opaque-21", "55", "56", "54"),
        (short, "opaque-39", "57", "58", "53"),
    ):
        data["contract"].update(contract_id=contract_id, right=right)
        data["quote"].update(contract_id=contract_id,
                             observed_at=f"2026-11-10T07:59:{observed}Z",
                             received_at=f"2026-11-10T07:59:{received}Z")
        data["underlying"]["spot_observed_at"] = f"2026-11-10T07:59:{spot_at}Z"
        for key in ("margin", "costs"):
            data[key]["contract_id"] = contract_id
    if right == "put":
        long["contract"]["strike"], short["contract"]["strike"] = "110", "100"
    result = analyze_debit_vertical(long, short, as_of=AS_OF)
    assert result["success"] is True
    return result


def _leg_text(text, leg):
    header = f"  Leg ({leg['role']}): {leg['contract_id']}\n"
    assert header in text
    return text.split(header, 1)[1].split("  Leg (", 1)[0]


@pytest.mark.parametrize("right", ["call", "put"])
@pytest.mark.parametrize(("label", "path", "units"), [
    ("Right", ("contract", "right"), ""),
    ("Strike", ("contract", "strike"), " index points"),
    ("Multiplier", ("contract", "value_per_price_unit"), " USD per index point per contract"),
    ("Quantity", ("metrics", "option", "contracts"), " contracts"),
    ("Entry premium (ask)", ("metrics", "option", "entry_premium_ask"), " index points"),
    ("Gross premium outlay", ("metrics", "option", "gross_premium_outlay"), " USD"),
    ("Gross expiry breakeven", ("metrics", "option", "breakeven_gross"), " underlying index points"),
])
def test_option_payoff_inputs_have_labels_and_units(right, label, path, units):
    result = _single_result(right=right)
    text = render_derivative_results(result)
    assert f"{label}: {_value(result, path)}{units}" in text.splitlines()
    assert "Contract: opaque-17" in text
    assert f"Gross expiry max loss: {result['metrics']['option']['gross_max_loss']} USD" in text
    assert "Expiry: " + result["contract"]["expiry_at"] in text


@pytest.mark.parametrize(("label", "path", "units"), [
    ("Multiplier", ("contract", "value_per_price_unit"), " USD per index point per contract"),
    ("Tick size", ("contract", "tick_size"), " index points"),
    ("Quantity", ("metrics", "futures", "contracts"), " contracts"),
    ("Long entry (ask)", ("metrics", "futures", "long_entry_ask"), " index points"),
    ("Short entry (bid)", ("metrics", "futures", "short_entry_bid"), " index points"),
    ("Tick value", ("metrics", "futures", "tick_value"), " USD per tick per contract"),
    ("Gross notional at bid", ("metrics", "futures", "gross_notional_at_bid"), " USD"),
])
def test_futures_quote_sides_and_scale_have_labels_and_units(label, path, units):
    result = _single_result(kind="future")
    text = render_derivative_results(result)
    assert f"{label}: {_value(result, path)}{units}" in text.splitlines()
    assert "Gross notional at ask: " + result["metrics"]["futures"]["gross_notional_at_ask"] + " USD" in text
    assert "not capped by margin or a stop" in text
    assert "Account affordability: UNVERIFIED" in text


@pytest.mark.parametrize("kind", ["option", "future"])
@pytest.mark.parametrize(("label", "key"), [
    ("Quote observed at", "quote_observed_at"),
    ("Quote received at", "quote_received_at"),
    ("Underlying spot at", "underlying_spot_at"),
])
def test_single_contract_shows_each_evidence_clock_not_just_cutoff(kind, label, key):
    result = _single_result(kind=kind)
    assert f"{label}: {result['source_clocks'][key]}" in render_derivative_results(result).splitlines()


@pytest.mark.parametrize("right", ["call", "put"])
@pytest.mark.parametrize(("label", "key", "units"), [
    ("Quantity per leg", "contracts_each_leg", " contracts"),
    ("Gross debit", "gross_debit", " USD"),
    ("Gross expiry breakeven", "breakeven_gross", " underlying index points"),
])
def test_vertical_payoff_basis_is_visible_before_bounded_risk_claims(right, label, key, units):
    result = _vertical_result(right=right)
    text = render_derivative_results(result)
    vertical = result["metrics"]["vertical"]
    assert f"{label}: {vertical[key]}{units}" in text.splitlines()
    assert f"Gross expiry max loss: {vertical['gross_max_loss']} USD" in text
    assert f"Gross expiry max profit: {vertical['gross_max_profit']} USD" in text
    assert "Leg estimates are not an atomic executable spread quote." in text


@pytest.mark.parametrize("right", ["call", "put"])
@pytest.mark.parametrize("leg_index", [0, 1])
@pytest.mark.parametrize(("label", "path", "units"), [
    ("Right", ("contract", "right"), ""),
    ("Strike", ("contract", "strike"), " index points"),
    ("Multiplier", ("contract", "value_per_price_unit"), " USD per index point per contract"),
    ("Expiry", ("contract", "expiry_at"), ""),
])
def test_vertical_leg_role_and_contract_inputs_cannot_be_inferred_from_opaque_ids(
    right, leg_index, label, path, units,
):
    result = _vertical_result(right=right)
    leg = result["legs"][leg_index]
    section = _leg_text(render_derivative_results(result), leg)
    assert f"    {label}: {_value(leg, path)}{units}" in section.splitlines()


@pytest.mark.parametrize("leg_index", [0, 1])
@pytest.mark.parametrize(("label", "key"), [
    ("Quote observed at", "quote_observed_at"),
    ("Quote received at", "quote_received_at"),
    ("Underlying spot at", "underlying_spot_at"),
])
def test_vertical_quotes_show_each_legs_own_clock(leg_index, label, key):
    result = _vertical_result()
    leg = result["legs"][leg_index]
    section = _leg_text(render_derivative_results(result), leg)
    expected = result["source_clocks"][leg["role"]][key]
    assert f"    {label}: {expected}" in section.splitlines()


@pytest.mark.parametrize("build", [_single_result, _vertical_result])
def test_fixture_banner_is_a_caller_declaration_not_a_certificate(build):
    text = render_derivative_results(build())
    assert "CALLER-DECLARED SYNTHETIC / UNVERIFIED / NOT LIVE" in text.splitlines()


_UNAVAILABLE_FIELDS = [
    ("option", ("contract", "contract_id"), "Contract: N/A"),
    ("option", ("contract", "expiry_at"), "Expiry: N/A"),
    ("option", ("as_of",), "Cutoff: N/A"),
    ("option", ("strategy",), "Strategy: N/A"),
    ("option", ("contract", "right"), "Right: N/A"),
    ("option", ("contract", "strike"), "Strike: N/A index points"),
    ("option", ("contract", "value_per_price_unit"), "Multiplier: N/A USD per index point per contract"),
    ("option", ("metrics", "option", "contracts"), "Quantity: N/A contracts"),
    ("option", ("metrics", "option", "entry_premium_ask"), "Entry premium (ask): N/A index points"),
    ("option", ("metrics", "option", "gross_premium_outlay"), "Gross premium outlay: N/A USD"),
    ("option", ("metrics", "option", "breakeven_gross"), "Gross expiry breakeven: N/A underlying index points"),
    ("option", ("metrics", "option", "gross_max_loss"), "Gross expiry max loss: N/A USD"),
    ("option", ("metrics", "option", "pricing", "status"), "European model/Greeks: N/A; not independent fair-value evidence."),
    ("future", ("contract", "value_per_price_unit"), "Multiplier: N/A USD per index point per contract"),
    ("future", ("contract", "tick_size"), "Tick size: N/A index points"),
    ("future", ("metrics", "futures", "contracts"), "Quantity: N/A contracts"),
    ("future", ("metrics", "futures", "long_entry_ask"), "Long entry (ask): N/A index points"),
    ("future", ("metrics", "futures", "short_entry_bid"), "Short entry (bid): N/A index points"),
    ("future", ("metrics", "futures", "tick_value"), "Tick value: N/A USD per tick per contract"),
    ("future", ("metrics", "futures", "gross_notional_at_ask"), "Gross notional at ask: N/A USD"),
    ("future", ("metrics", "futures", "gross_notional_at_bid"), "Gross notional at bid: N/A USD"),
    ("vertical", ("metrics", "vertical", "contracts_each_leg"), "Quantity per leg: N/A contracts"),
    ("vertical", ("metrics", "vertical", "gross_debit"), "Gross debit: N/A USD"),
    ("vertical", ("metrics", "vertical", "breakeven_gross"), "Gross expiry breakeven: N/A underlying index points"),
    ("vertical", ("metrics", "vertical", "gross_max_loss"), "Gross expiry max loss: N/A USD"),
    ("vertical", ("metrics", "vertical", "gross_max_profit"), "Gross expiry max profit: N/A USD"),
] + [
    (kind, ("source_clocks", key), label + ": N/A")
    for kind in ("option", "future")
    for label, key in (("Quote observed at", "quote_observed_at"),
                       ("Quote received at", "quote_received_at"),
                       ("Underlying spot at", "underlying_spot_at"))
] + [
    ("vertical", ("legs", index, "contract", key), f"    {label}: N/A{units}")
    for index in (0, 1)
    for label, key, units in (("Right", "right", ""), ("Strike", "strike", " index points"),
                              ("Multiplier", "value_per_price_unit", " USD per index point per contract"),
                              ("Expiry", "expiry_at", ""))
] + [
    ("vertical", ("source_clocks", role, key), "    " + label + ": N/A")
    for role in ("long", "short")
    for label, key in (("Quote observed at", "quote_observed_at"),
                       ("Quote received at", "quote_received_at"),
                       ("Underlying spot at", "underlying_spot_at"))
]


def _result(kind):
    return _vertical_result() if kind == "vertical" else _single_result(kind=kind)


@pytest.mark.parametrize("absent", [False, True], ids=["null", "absent"])
@pytest.mark.parametrize(("kind", "path", "expected_line"), _UNAVAILABLE_FIELDS)
def test_missing_payoff_inputs_are_na_not_zero_or_none(kind, path, expected_line, absent):
    result = _result(kind)
    parent = _value(result, path[:-1])
    if absent:
        parent.pop(path[-1])
    else:
        parent[path[-1]] = None
    assert expected_line in render_derivative_results(result).splitlines()


@pytest.mark.parametrize("kind", ["option", "future", "vertical"])
@pytest.mark.parametrize("absent", [False, True], ids=["null", "absent"])
def test_missing_currency_is_na_not_an_invented_unit(kind, absent):
    result = _result(kind)
    if absent:
        result["contract"].pop("currency")
    else:
        result["contract"]["currency"] = None
    metric = "futures" if kind == "future" else kind
    key, label = ("gross_notional_at_ask", "Gross notional at ask") if kind == "future" else ("gross_max_loss", "Gross expiry max loss")
    expected = f"{label}: {result['metrics'][metric][key]} N/A"
    assert expected in render_derivative_results(result).splitlines()


# Mutate real reports only at the renderer boundary: even unexpected provider text
# must remain inert data rather than terminal instructions, bidi state or new rows.
_MALICIOUS_TEXT = (
    "RENDER-PAYLOAD\x1b[31m\n\r\t\x00\x7f\x85"
    "\u061c\u200e\u200f\u202a\u202b\u202c\u202d\u202e"
    "\u2066\u2067\u2068\u2069\u200b\u200c\u200d\u2060\ufeff"
    "\u2028\u2029\ud800END"
)
_CONTROLLED_FIELDS = [(kind, path) for kind, path, _ in _UNAVAILABLE_FIELDS] + [
    (kind, ("contract", "currency")) for kind in ("option", "future", "vertical")
] + [
    ("vertical", ("legs", index, key))
    for index in (0, 1) for key in ("role", "contract_id")
] + [
    ("vertical", ("legs", index, "contract", "currency")) for index in (0, 1)
] + [
    (kind, ("recommendation", key))
    for kind in ("option", "vertical") for key in ("scope", "verdict")
] + [
    ("future", ("recommendations", side, key))
    for side in ("long", "short") for key in ("scope", "verdict")
] + [
    ("option", (key, 0)) for key in ("blockers", "missing_data", "warnings")
]


@pytest.mark.parametrize(("kind", "path"), _CONTROLLED_FIELDS)
def test_every_provider_controlled_display_field_is_control_sanitized(kind, path):
    result = _result(kind)
    # missing_data may legitimately be empty in a complete synthetic report.
    if path[0] in ("blockers", "missing_data", "warnings"):
        result[path[0]] = ["source text"]
    before = render_derivative_results(result)
    parent = _value(result, path[:-1])
    parent[path[-1]] = str(parent[path[-1]]) + _MALICIOUS_TEXT
    text = render_derivative_results(result)
    assert "RENDER-PAYLOAD" in text and "END" in text
    assert len(text.splitlines()) == len(before.splitlines())
    assert all(char == "\n" or char.isprintable() for char in text)


@pytest.mark.parametrize("key", ["code", "error"])
def test_error_fields_also_sanitize_unicode_format_controls(key):
    result = analyze_derivative_snapshot({}, as_of=AS_OF)
    assert result["success"] is False
    before = render_derivative_results(result)
    result[key] += _MALICIOUS_TEXT
    text = render_derivative_results(result)
    assert "RENDER-PAYLOAD" in text and "END" in text
    assert len(text.splitlines()) == len(before.splitlines())
    assert all(char == "\n" or char.isprintable() for char in text)


@pytest.mark.parametrize("empty", ["", " \t", "\u200b"])
def test_empty_or_invisible_payoff_fields_are_na(empty):
    result = _single_result()
    result["metrics"]["option"]["entry_premium_ask"] = empty
    assert "Entry premium (ask): N/A index points" in render_derivative_results(result).splitlines()


def test_sanitization_preserves_printable_non_ascii_provider_text():
    result = _single_result()
    result["contract"]["contract_id"] = "OPAQUE:分析-€"
    assert "Contract: OPAQUE:分析-€" in render_derivative_results(result).splitlines()


@pytest.mark.parametrize("kind", ["option", "future", "vertical"])
def test_rendering_does_not_mutate_the_analyzer_report(kind):
    result = _result(kind)
    original = deepcopy(result)
    render_derivative_results(result)
    assert result == original


@pytest.mark.parametrize("kind", ["option", "future", "vertical"])
def test_missing_clock_objects_leave_clocks_explicitly_unavailable(kind):
    result = _result(kind)
    result["source_clocks"] = None
    text = render_derivative_results(result)
    expected_count = 2 if kind == "vertical" else 1
    for label in ("Quote observed at", "Quote received at", "Underlying spot at"):
        assert text.count(label + ": N/A") == expected_count


@pytest.mark.parametrize("role", ["long", "short"])
def test_missing_vertical_leg_clock_object_does_not_borrow_the_other_leg(role):
    result = _vertical_result()
    result["source_clocks"][role] = None
    leg = next(leg for leg in result["legs"] if leg["role"] == role)
    section = _leg_text(render_derivative_results(result), leg)
    for label in ("Quote observed at", "Quote received at", "Underlying spot at"):
        assert "    " + label + ": N/A" in section.splitlines()


def test_missing_pricing_object_leaves_model_status_unavailable():
    result = _single_result()
    result["metrics"]["option"]["pricing"] = None
    assert "European model/Greeks: N/A; not independent fair-value evidence." in render_derivative_results(result).splitlines()
