"""Offline derivatives contract boundaries; fixtures are not market evidence."""

from decimal import Decimal

import pytest


def test_decimal_rejects_boolean_nonfinite_and_float():
    from tradeguard.derivative_contracts import DerivativeInputError, decimal_value

    assert decimal_value("0.25") == Decimal("0.25")
    assert str(decimal_value("1.123456789012345678901234567890")) == "1.123456789012345678901234567890"
    assert decimal_value(10**30) == Decimal("1e30")
    assert decimal_value(Decimal("0.2500")) == Decimal("0.25")
    for value in (True, 1.2, "NaN", "Infinity", " 1", None, "1e3", "1" * 101,
                  10**31, Decimal("1e-100000"), Decimal("0e999999"), Decimal("NaN")):
        with pytest.raises(DerivativeInputError) as caught:
            decimal_value(value)
        assert caught.value.code == "INVALID_DERIVATIVE_SNAPSHOT"
        assert isinstance(caught.value, ValueError)
        assert str(caught.value)


def test_timestamp_requires_offset():
    from tradeguard.derivative_contracts import aware_time

    assert aware_time("2026-11-10T13:30:00+05:30") == aware_time("2026-11-10T08:00:00Z")
    for value in ("2026-11-10T08:00:00", "2026-11-10", "bad", None, True,
                  "2026-11-10T08:00:00+25:00", "x" * 41):
        with pytest.raises(ValueError):
            aware_time(value)


@pytest.mark.parametrize("value", [True, False, 0, -1, 101, 1.0, "1", None])
def test_contract_quantity_rejects_non_integer_or_out_of_range(value):
    from tradeguard.derivative_contracts import contract_quantity

    with pytest.raises(ValueError):
        contract_quantity(value)


def test_contract_quantity_accepts_inclusive_bounds():
    from tradeguard.derivative_contracts import contract_quantity

    assert contract_quantity(1) == 1
    assert contract_quantity(100) == 100


def test_root_grammar_validates_before_case_normalization():
    from tradeguard.derivative_contracts import parse_root_requests

    assert parse_root_requests("nfo:nifty NFO:NIFTY") == {
        "requested": ["nfo:nifty", "NFO:NIFTY"], "roots": ["NFO:NIFTY"]}
    assert parse_root_requests(["TEST:A", "nfo:nifty", "TEST:A"])["roots"] == ["TEST:A", "NFO:NIFTY"]
    for value in ("ＮFO:NIFTY", "NFO:ſPY", "ES=F", "NIFTY", "../NFO:NIFTY", "NFO:NIFTY;id",
                  "", [], [1], None, True, ["TEST:A"] * 4, "TEST:A," * 4, " " * 257,
                  ["TEST:" + "X" * 251], "TEST:A\u00a0TEST:B", "TEST:A\x00"):
        with pytest.raises(ValueError):
            parse_root_requests(value)


def test_synthetic_factory_is_fresh_and_not_live():
    from derivative_cases import AS_OF, snapshot

    first = snapshot()
    second = snapshot(kind="option", quote={"ask": "6.25"})
    assert AS_OF == "2026-11-10T08:00:00Z"
    assert first["source"]["data_mode"] == "fixture"
    assert "SYNTHETIC" in first["source"]["provider"]
    assert first["contract"]["contract_id"] == "TEST:FUTURE"
    assert first["quote"]["observed_at"] == "2026-11-10T07:59:59Z"
    assert first["quote"]["received_at"] == "2026-11-10T07:59:59Z"
    assert second["contract"]["contract_id"] == "TEST:CALL"
    assert second["contract"]["strike"] == "100"
    assert second["quote"]["bid"] == "5.75"
    assert second["quote"]["ask"] == "6.25"
    assert len(first["underlying"]["bars"]) == 200
    assert first["underlying"]["bars"][-1]["close"] == 100
    assert all("SYNTHETIC" in row["source"] for row in first["underlying"]["bars"])
    first["underlying"]["bars"][0]["close"] = 999
    assert second["underlying"]["bars"][0]["close"] != 999
    with pytest.raises(ValueError):
        snapshot(kind="stock")


def test_contract_identity_and_unknown_fields():
    import copy
    import json
    from derivative_cases import AS_OF, snapshot
    from tradeguard.derivative_contracts import DerivativeInputError, validate_snapshot

    original = snapshot(contract={"contract_id": "00000017"}, quote={"contract_id": "00000017"},
                        margin={"contract_id": "00000017"}, costs={"contract_id": "00000017"})
    before = copy.deepcopy(original)
    normalized = validate_snapshot(original, as_of=AS_OF)
    assert normalized["contract"]["contract_id"] == "00000017"
    assert original == before
    assert set(normalized["_validation"]) == {"blockers", "missing_data", "warnings", "usable"}
    json.dumps(normalized, allow_nan=False)
    normalized["underlying"]["bars"][0]["source"] = "modified"
    assert original == before
    cases = [snapshot(extra=1), snapshot(_validation={}), snapshot(schema_version=True), snapshot(schema_version=2),
             snapshot(contract=[]), snapshot(quote=[]), snapshot(underlying=[]), snapshot(source=[]),
             snapshot(contract={"contract_id": ""}), snapshot(contract={"contract_id": "X" * 257}),
             snapshot(contract={"contract_id": "bad\x1b[31m"}), snapshot(quote={"contract_id": "other"}),
             snapshot(underlying={"underlying_id": "other"}), {}, [], None]
    for case in cases:
        with pytest.raises(DerivativeInputError) as caught:
            validate_snapshot(case, as_of=AS_OF)
        assert caught.value.code == "INVALID_DERIVATIVE_SNAPSHOT"


def test_multiplier_currency_and_tick_grid():
    from derivative_cases import AS_OF, snapshot
    from tradeguard.derivative_contracts import DerivativeInputError, validate_snapshot

    for field in ("value_per_price_unit", "tick_size"):
        for value in ("0", "-1", True, 0.25, "NaN", "1e99"):
            with pytest.raises(DerivativeInputError):
                validate_snapshot(snapshot(contract={field: value}), as_of=AS_OF)
    for obj in ("underlying", "rates", "margin", "costs"):
        with pytest.raises(DerivativeInputError):
            validate_snapshot(snapshot(**{obj: {"currency": "INR"}}), as_of=AS_OF)
    for obj, identity in (("rates", "underlying_id"), ("margin", "contract_id"), ("costs", "contract_id")):
        with pytest.raises(DerivativeInputError):
            validate_snapshot(snapshot(**{obj: {identity: "wrong"}}), as_of=AS_OF)
    with pytest.raises(DerivativeInputError):
        validate_snapshot(snapshot(quote={"ask": "100.10"}), as_of=AS_OF)
    assert validate_snapshot(snapshot(), as_of=AS_OF)["contract"]["value_per_price_unit"] == "5"
    exact = snapshot(contract={"tick_size": "0.00000000000000000000000000001"},
                     quote={"bid": "100.00000000000000000000000000001"})
    assert "QUOTE_OFF_TICK" not in validate_snapshot(exact, as_of=AS_OF)["_validation"]["blockers"]


def test_expiry_and_style_are_explicit():
    from derivative_cases import AS_OF, snapshot
    from tradeguard.derivative_contracts import DerivativeInputError, validate_snapshot

    cases = [{"family": "commodity_future"}, {"settlement": "physical"}, {"standard_deliverable": False}]
    cases += [{"exercise": "american"}, {"underlying_kind": "future"}]
    for changes in cases:
        with pytest.raises(DerivativeInputError) as caught:
            validate_snapshot(snapshot(kind="option", contract=changes), as_of=AS_OF)
        assert caught.value.code == "UNSUPPORTED_INSTRUMENT"
    for changes in ({"expiry_at": "2026-11-10T08:00:00"}, {"right": "CALL"}, {"strike": "0"},
                    {"last_trade_at": "2027-01-01T00:00:00Z"}):
        with pytest.raises(DerivativeInputError):
            validate_snapshot(snapshot(kind="option", contract=changes), as_of=AS_OF)
    expired = snapshot(contract={"expiry_at": AS_OF, "last_trade_at": AS_OF})
    assert "EXPIRED_CONTRACT" in validate_snapshot(expired, as_of=AS_OF)["_validation"]["blockers"]
    effective_later = snapshot(contract={"spec_effective_at": "2026-11-11T00:00:00Z"})
    assert "FUTURE_SPEC_EFFECTIVE_AT" in validate_snapshot(effective_later, as_of=AS_OF)["_validation"]["blockers"]


def test_quote_clocks_and_depth():
    from derivative_cases import AS_OF, snapshot
    from tradeguard.derivative_contracts import DerivativeInputError, validate_snapshot

    assert validate_snapshot(snapshot(), as_of=AS_OF)["_validation"]["usable"]["quote"] is True
    for changes in ({"bid": "101"}, {"bid": "0"}, {"ask": "-1"}, {"bid": None},
                    {"bid_contracts": True}, {"ask_contracts": -1}, {"delay_seconds": False},
                    {"delay_seconds": -1}, {"market_state": "preopen"}, {"observed_at": "naive"}):
        with pytest.raises(DerivativeInputError):
            validate_snapshot(snapshot(quote=changes), as_of=AS_OF)
    cases = [({"bid_contracts": 0}, "INSUFFICIENT_DEPTH"),
             ({"delay_seconds": None}, "QUOTE_DELAY_UNKNOWN"),
             ({"delay_seconds": 1}, "DELAYED_QUOTE"),
             ({"market_state": "closed"}, "MARKET_CLOSED"),
             ({"market_state": "unknown"}, "MARKET_STATE_UNKNOWN"),
             ({"observed_at": "2026-11-10T07:59:44Z"}, "STALE_QUOTE"),
             ({"received_at": "2026-11-10T07:59:58Z"}, "QUOTE_CLOCK_ORDER"),
             ({"received_at": "2026-11-10T08:00:01Z"}, "FUTURE_QUOTE_CLOCK")]
    for changes, blocker in cases:
        validation = validate_snapshot(snapshot(quote=changes), as_of=AS_OF)["_validation"]
        assert blocker in validation["blockers"]
        assert validation["usable"]["quote"] is False
    skewed = snapshot(underlying={"spot_observed_at": "2026-11-10T07:59:53Z"})
    assert "SPOT_QUOTE_SKEW" in validate_snapshot(skewed, as_of=AS_OF)["_validation"]["blockers"]
    boundary = snapshot(quote={"observed_at": "2026-11-10T07:59:45Z", "received_at": "2026-11-10T07:59:45Z"},
                        underlying={"spot_observed_at": "2026-11-10T07:59:45Z"})
    assert validate_snapshot(boundary, as_of=AS_OF)["_validation"]["usable"]["quote"] is True


def test_underlying_completed_daily_price_index():
    from derivative_cases import AS_OF, snapshot
    from tradeguard.derivative_contracts import DerivativeInputError, validate_snapshot

    assert validate_snapshot(snapshot(), as_of=AS_OF)["_validation"]["usable"]["history"] is True
    cases = []
    for changes in ({"adjustment": "split"}, {"price_basis": "total_return_index"}, {"interval": "1wk"},
                    {"spot": "0"}, {"retrieved_at": "bad"}, {"source": ""},
                    {"last_bar_finalized_at": "2026-11-11T00:00:00Z"}):
        cases.append(snapshot(underlying=changes))
    for changes in ({"close": True}, {"high": 1}, {"low": 0}, {"open": float("nan")},
                    {"volume": -1}, {"date": "20261109"}, {"source": "different"}):
        case = snapshot()
        case["underlying"]["bars"][-1].update(changes)
        cases.append(case)
    case = snapshot()
    case["underlying"]["bars"][-1]["date"] = case["underlying"]["bars"][-2]["date"]
    cases.append(case)
    case = snapshot()
    case["underlying"]["bars"].reverse()
    cases.append(case)
    case = snapshot()
    case["underlying"]["bars"] = case["underlying"]["bars"][::5]
    cases.append(case)
    for case in cases:
        with pytest.raises(DerivativeInputError):
            validate_snapshot(case, as_of=AS_OF)
    for length in (0, 1, 199):
        case = snapshot()
        case["underlying"]["bars"] = case["underlying"]["bars"][-length:] if length else []
        validation = validate_snapshot(case, as_of=AS_OF)["_validation"]
        assert validation["usable"]["history"] is False
        assert "INSUFFICIENT_HISTORY" in validation["blockers"]


def test_import_cannot_claim_verified_provider_provenance():
    from derivative_cases import AS_OF, snapshot
    from tradeguard.derivative_contracts import DerivativeInputError, validate_snapshot

    for mode in ("provider", "user_supplied", "fixture"):
        original = snapshot(source={"data_mode": mode, "entitlement": "confirmed"})
        result = validate_snapshot(original, as_of=AS_OF)
        assert result["source"]["data_mode"] == ("fixture" if mode == "fixture" else "user_supplied")
        assert result["source"]["entitlement"] == "unverified"
        assert original["source"]["entitlement"] == "confirmed"
        assert "OFFLINE_PROVENANCE_UNVERIFIED" in result["_validation"]["blockers"]
    for changes in ({"data_mode": "live"}, {"provider": ""}, {"retrieved_at": "bad"}):
        with pytest.raises(DerivativeInputError):
            validate_snapshot(snapshot(source=changes), as_of=AS_OF)
    result = validate_snapshot(snapshot(source={"retrieved_at": "2026-11-10T08:00:01Z"}), as_of=AS_OF)
    assert "FUTURE_SOURCE_CLOCK" in result["_validation"]["blockers"]
    assert result["_validation"]["usable"]["quote"] is False


@pytest.mark.parametrize("name,boundary,stale", [
    ("rates", "2026-11-03T08:00:00Z", "2026-11-03T07:59:59Z"),
    ("costs", "2026-11-09T08:00:00Z", "2026-11-09T07:59:59Z"),
    ("margin", "2026-11-10T07:00:00Z", "2026-11-10T06:59:59Z"),
])
def test_optional_evidence_exact_ttl_and_missing_values(name, boundary, stale):
    from derivative_cases import AS_OF, snapshot
    from tradeguard.derivative_contracts import validate_snapshot

    assert validate_snapshot(snapshot(**{name: {"as_of": boundary}}), as_of=AS_OF)["_validation"]["usable"][name] is True
    for clock, reason in ((stale, "STALE_" + name.upper()),
                          ("2026-11-10T08:00:01Z", "FUTURE_" + name.upper() + "_CLOCK")):
        result = validate_snapshot(snapshot(**{name: {"as_of": clock}}), as_of=AS_OF)
        assert result["_validation"]["usable"][name] is False
        assert reason in result["_validation"]["missing_data"]
        assert result[name]["as_of"] == clock
    for missing in (None, "omit"):
        case = snapshot()
        if missing is None:
            case[name] = None
        else:
            del case[name]
        result = validate_snapshot(case, as_of=AS_OF)
        assert result["_validation"]["usable"][name] is False
        assert name.upper() in result["_validation"]["missing_data"]
        assert result.get(name) is None


def test_optional_evidence_shape_and_no_zero_rate_defaults():
    from derivative_cases import AS_OF, snapshot
    from tradeguard.derivative_contracts import DerivativeInputError, validate_snapshot

    for name, changes in (("rates", {"risk_free": True}), ("rates", {"risk_free": "1.01"}),
                          ("rates", {"dividend_yield": "-0.1"}), ("rates", {"compounding": "simple"}),
                          ("rates", {"day_count": "ACT/360"}), ("costs", {"round_trip_per_contract": "-1"}),
                          ("costs", {"excludes": "none"}), ("margin", {"amount_per_contract": "0"}),
                          ("margin", {"account_specific": 0}), ("margin", {"scope": "account"}),
                          ("margin", {"source": ""}), ("costs", {"as_of": "naive"})):
        with pytest.raises(DerivativeInputError):
            validate_snapshot(snapshot(**{name: changes}), as_of=AS_OF)
    case = snapshot(kind="option")
    del case["rates"]["risk_free"]
    result = validate_snapshot(case, as_of=AS_OF)
    assert result["_validation"]["usable"]["rates"] is False
    assert "RISK_FREE_RATE" in result["_validation"]["missing_data"]
    assert "risk_free" not in result["rates"]
    assert validate_snapshot(snapshot(rates={"risk_free": "0", "dividend_yield": "0"}), as_of=AS_OF)["_validation"]["usable"]["rates"] is True


@pytest.mark.parametrize("object_name", ["contract", "quote", "underlying", "source", "rates", "costs", "margin"])
def test_nested_schema_rejects_missing_and_unknown_fields(object_name):
    from derivative_cases import AS_OF, snapshot
    from tradeguard.derivative_contracts import DerivativeInputError, validate_snapshot

    for field in ("_trusted_adapter", "unexpected"):
        case = snapshot()
        case[object_name][field] = True
        with pytest.raises(DerivativeInputError):
            validate_snapshot(case, as_of=AS_OF)
    for field in list(snapshot()[object_name]):
        if field in ("risk_free", "dividend_yield"):
            continue  # Optional values remain missing rather than defaulting to zero.
        case = snapshot()
        del case[object_name][field]
        with pytest.raises(DerivativeInputError):
            validate_snapshot(case, as_of=AS_OF)


@pytest.mark.parametrize("section,field,value", [
    ("contract", "venue", "../TEST"), ("contract", "root", "ＩNDEX"),
    ("contract", "contract_id", "hidden\u202eID"), ("contract", "tick_size", Decimal("0.25")),
    ("underlying", "bars", [None]), ("underlying", "spot", float("inf")),
    ("source", "provider", "X" * 257), ("source", "historical_vintage", "X" * 2049),
    ("costs", "excludes", ["x"] * 33), ("costs", "excludes", ["x" * 257]),
])
def test_adversarial_nested_values_fail_explicitly(section, field, value):
    from derivative_cases import AS_OF, snapshot
    from tradeguard.derivative_contracts import DerivativeInputError, validate_snapshot

    case = snapshot()
    case[section][field] = value
    with pytest.raises(DerivativeInputError):
        validate_snapshot(case, as_of=AS_OF)


def test_json_resource_limits_are_bounded_before_copying():
    from derivative_cases import AS_OF, snapshot
    from tradeguard.derivative_contracts import DerivativeInputError, validate_snapshot

    cases = []
    case = snapshot()
    case["underlying"]["bars"] *= 11
    cases.append(case)
    case = snapshot()
    case["source"]["historical_vintage"] = "X" * (16 * 1024 * 1024 + 1)
    cases.append(case)
    case = snapshot()
    case["source"]["historical_vintage"] = case
    cases.append(case)
    case = snapshot()
    case["source"]["historical_vintage"] = [[[[[[[[[["too deep"]]]]]]]]]]
    cases.append(case)
    case = snapshot()
    case["contract"]["contract_id"] = {"not": "text"}
    cases.append(case)
    for case in cases:
        with pytest.raises(DerivativeInputError):
            validate_snapshot(case, as_of=AS_OF)


def test_clock_and_root_preflight_rejects_controls():
    from tradeguard.derivative_contracts import aware_time, parse_root_requests

    for value in ("2026-11-10\t08:00:00+00:00", "20261110T080000+00:00", "2026-11-10❤08:00:00+00:00"):
        with pytest.raises(ValueError):
            aware_time(value)
    with pytest.raises(ValueError):
        parse_root_requests("TEST:A\x1cTEST:B")


def test_raw_bar_schema_cannot_smuggle_adjusted_prices():
    from derivative_cases import AS_OF, snapshot
    from tradeguard.derivative_contracts import DerivativeInputError, validate_snapshot

    for changes in ({"adjusted_close": 999}, {"surprise": True}):
        case = snapshot()
        case["underlying"]["bars"][-1].update(changes)
        with pytest.raises(DerivativeInputError):
            validate_snapshot(case, as_of=AS_OF)


def test_matching_opaque_ids_still_reject_bidi_controls():
    from derivative_cases import AS_OF, snapshot
    from tradeguard.derivative_contracts import DerivativeInputError, validate_snapshot

    identifier = "hidden\u202eID"
    case = snapshot(contract={"contract_id": identifier}, quote={"contract_id": identifier},
                    margin={"contract_id": identifier}, costs={"contract_id": identifier})
    with pytest.raises(DerivativeInputError):
        validate_snapshot(case, as_of=AS_OF)


def test_malformed_family_is_invalid_not_an_unsupported_instrument():
    from derivative_cases import AS_OF, snapshot
    from tradeguard.derivative_contracts import DerivativeInputError, validate_snapshot

    for value in (None, {}, [], True, ""):
        case = snapshot(contract={"family": value})
        with pytest.raises(DerivativeInputError) as caught:
            validate_snapshot(case, as_of=AS_OF)
        assert caught.value.code == "INVALID_DERIVATIVE_SNAPSHOT"
    case = snapshot()
    del case["contract"]["family"]
    with pytest.raises(DerivativeInputError) as caught:
        validate_snapshot(case, as_of=AS_OF)
    assert caught.value.code == "INVALID_DERIVATIVE_SNAPSHOT"


def test_underlying_receipt_clocks_cannot_postdate_source_or_precede_spot():
    from derivative_cases import AS_OF, snapshot
    from tradeguard.derivative_contracts import validate_snapshot

    case = snapshot(underlying={"retrieved_at": "2026-11-10T07:59:58Z"})
    validation = validate_snapshot(case, as_of=AS_OF)["_validation"]
    assert "UNDERLYING_CLOCK_ORDER" in validation["blockers"]
    assert validation["usable"]["quote"] is False
    case = snapshot(quote={"received_at": "2026-11-10T07:59:59Z"},
                    source={"retrieved_at": "2026-11-10T07:59:59Z"})
    validation = validate_snapshot(case, as_of=AS_OF)["_validation"]
    assert "SOURCE_CLOCK_ORDER" in validation["blockers"]
    assert validation["usable"]["history"] is False


def test_optional_quote_statistics_are_source_and_unit_bound():
    from derivative_cases import AS_OF, SYNTHETIC, snapshot
    from tradeguard.derivative_contracts import DerivativeInputError, validate_snapshot

    statistic = {"value": 123, "unit": "contracts", "source": SYNTHETIC, "as_of": AS_OF}
    case = snapshot(quote={"volume": statistic, "open_interest": statistic})
    result = validate_snapshot(case, as_of=AS_OF)
    assert result["quote"]["volume"] == statistic
    assert result["quote"]["open_interest"] == statistic
    for changes in ({"value": True}, {"value": -1}, {"unit": "shares"}, {"source": ""},
                    {"as_of": "naive"}, {"unlabelled": 1}):
        bad = {**statistic, **changes}
        with pytest.raises(DerivativeInputError):
            validate_snapshot(snapshot(quote={"volume": bad}), as_of=AS_OF)
    future = {**statistic, "as_of": "2026-11-10T08:00:01Z"}
    validation = validate_snapshot(snapshot(quote={"volume": future}), as_of=AS_OF)["_validation"]
    assert "FUTURE_QUOTE_STATISTIC_CLOCK" in validation["blockers"]
    assert validation["usable"]["quote"] is False


def test_timestamp_rejects_normalized_overflowing_offset_minutes():
    from tradeguard.derivative_contracts import aware_time

    for suffix in ("+00:60", "+05:99", "-00:60"):
        with pytest.raises(ValueError):
            aware_time("2026-11-10T08:00:00" + suffix)


def test_future_underlying_receipt_cannot_be_usable_quote_evidence():
    from derivative_cases import AS_OF, snapshot
    from tradeguard.derivative_contracts import validate_snapshot

    validation = validate_snapshot(snapshot(underlying={"retrieved_at": "2026-11-10T08:00:01Z"}), as_of=AS_OF)["_validation"]
    assert "FUTURE_UNDERLYING_CLOCK" in validation["blockers"]
    assert validation["usable"]["history"] is False
    assert validation["usable"]["quote"] is False


def test_exact_maximum_history_and_serialized_byte_guard(monkeypatch):
    from datetime import date, timedelta
    from derivative_cases import AS_OF, snapshot
    from tradeguard import derivative_contracts as contracts

    case = snapshot()
    day, rows = date(2026, 11, 9), []
    while len(rows) < 2000:
        if day.weekday() < 5:
            rows.append({**case["underlying"]["bars"][-1], "date": day.isoformat()})
        day -= timedelta(days=1)
    case["underlying"]["bars"] = rows[::-1]
    assert len(contracts.validate_snapshot(case, as_of=AS_OF)["underlying"]["bars"]) == 2000
    assert contracts.MAX_SNAPSHOT_BYTES == 16 * 1024 * 1024
    oversized = snapshot()
    oversized["underlying"]["bars"] = [{"source": "ह" * 2048, "date": "ह" * 2048}] * 2000
    with pytest.raises(contracts.DerivativeInputError, match="16 MiB"):
        contracts.validate_snapshot(oversized, as_of=AS_OF)
    monkeypatch.setattr(contracts, "MAX_SNAPSHOT_BYTES", 1)
    with pytest.raises(contracts.DerivativeInputError, match="16 MiB"):
        contracts.validate_snapshot(snapshot(), as_of=AS_OF)


@pytest.mark.parametrize("value", [10**31, {1: "bad key"}, ("tuple",), [{"x": 0}] * 2001])
def test_non_json_or_excessive_nested_values(value):
    from derivative_cases import AS_OF, snapshot
    from tradeguard.derivative_contracts import DerivativeInputError, validate_snapshot

    case = snapshot()
    case["source"]["historical_vintage"] = value
    with pytest.raises(DerivativeInputError):
        validate_snapshot(case, as_of=AS_OF)
