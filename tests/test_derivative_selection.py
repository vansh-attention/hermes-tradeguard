"""Pure metadata selection over conspicuously synthetic contract records."""

from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest


AS_OF = "2026-11-10T08:00:00Z"


def contract(identifier="SYNTHETIC:FUTURE", *, kind="futures", days=30, **changes):
    """Invent metadata, not quotes, a listing, or an entitlement assertion."""
    expiry = (datetime(2026, 11, 10, 8, tzinfo=timezone.utc) + timedelta(days=days)).isoformat()
    record = {
        "contract_id": identifier,
        "venue": "TEST",
        "root": "INDEX",
        "family": "index_future" if kind == "futures" else "index_option",
        "underlying_id": "SYNTHETIC:INDEX",
        "currency": "USD",
        "value_per_price_unit": "5",
        "tick_size": "0.25",
        "last_trade_at": expiry,
        "expiry_at": expiry,
        "settlement": "cash",
        "spec_source": "SYNTHETIC_FIXTURE_NOT_LIVE",
        "spec_effective_at": "2026-01-01T00:00:00Z",
        "standard_deliverable": True,
    }
    if kind == "options":
        record.update(right="call", strike="100", exercise="european", underlying_kind="cash_index")
    record.update(changes)
    return record


def select(records, *, kind="futures", request="TEST:INDEX", as_of=AS_OF, spot=None):
    from tradeguard.derivative_contracts import select_contracts

    return select_contracts(records, request, kind=kind, as_of=as_of, spot=spot)


def assert_counts(result, searched, selected):
    assert result["searched_count"] == searched
    assert result["selected_count"] == selected == len(result["selected"])
    assert result["excluded_count"] == searched - selected
    assert sum(result["exclusion_reasons"].values()) == result["excluded_count"]
    assert result["selection_only"] is True
    assert result["research_only"] is True
    assert result["policy_version"] == "derivatives_policy_v1"
    assert not {"score", "recommendation", "entitlement"} & result.keys()


def test_future_selects_earliest_eligible_exact_expiry():
    records = [
        contract("Z-not-ticker-order", days=50),
        contract("00000017", days=20),
        contract("too-soon", days=6),
        contract("too-late", days=121),
        contract("prefix-is-not-root", days=8, root="INDEXPLUS"),
        contract("other-venue", days=8, venue="OTHER"),
    ]
    before = deepcopy(records)
    result = select(records)
    assert [row["contract_id"] for row in result["selected"]] == ["00000017"]
    assert result["selected"][0] == records[1]
    assert result["selected"][0] is not records[1]
    assert records == before
    result["selected"][0]["contract_id"] = "changed"
    assert records == before
    assert_counts(result, 6, 1)
    assert result["exclusion_reasons"] == {
        "EXPIRY_NOT_SELECTED": 1,
        "OUTSIDE_SELECTION_WINDOW": 2,
        "ROOT_MISMATCH": 2,
    }
    assert result["selection_policy"]["expiry"] == "earliest_eligible_expiry"
    assert result["selection_policy"]["calendar_basis"] == "UTC_calendar_dates"
    assert result["selection_policy"]["min_days"] == 7
    assert result["selection_policy"]["max_days"] == 120


def test_options_choose_nearest_30_day_expiry_and_four_strikes_per_right():
    records = [
        contract(f"{right}-{strike}", kind="options", days=29, right=right, strike=str(strike))
        for right in ("call", "put") for strike in (95, 98, 99, 100, 101, 102, 105)
    ]
    records += [
        contract("later-tied-expiry", kind="options", days=31),
        contract("farther-expiry", kind="options", days=45),
        contract("outside-low", kind="options", days=29, strike="94.999999999999999999999999999999"),
        contract("outside-high", kind="options", days=29, strike="105.000000000000000000000000000001"),
        contract("too-soon", kind="options", days=13),
        contract("too-late", kind="options", days=61),
    ]
    result = select(records, kind="options", spot="100")
    expected = [f"{right}-{strike}" for right in ("call", "put") for strike in (100, 99, 101, 98)]
    assert [row["contract_id"] for row in result["selected"]] == expected
    assert select(records[::-1], kind="options", spot="100") == result
    assert_counts(result, len(records), 8)
    assert result["exclusion_reasons"] == {
        "EXPIRY_NOT_SELECTED": 2,
        "OUTSIDE_SELECTION_WINDOW": 2,
        "SELECTION_CAP": 6,
        "STRIKE_OUTSIDE_SPOT_BAND": 2,
    }
    policy = result["selection_policy"]
    assert policy["expiry"] == "nearest_30_calendar_days_tie_earlier"
    assert (policy["min_days"], policy["max_days"], policy["target_days"]) == (14, 60, 30)
    assert policy["strike_band_fraction"] == "0.05"
    assert policy["max_strikes_per_right"] == 4
    assert policy["max_selected"] == 8


def test_metadata_is_validated_directly_without_dummy_snapshot_quotes(monkeypatch):
    from decimal import Decimal
    from tradeguard import derivative_contracts

    def forbidden(*args, **kwargs):
        raise AssertionError("selection must not invent a quote or validate a snapshot")

    monkeypatch.setattr(derivative_contracts, "validate_snapshot", forbidden)
    malformed = [None, [], 17, "not a record", {}, contract("bad", unknown=1)]
    for index, (field, value) in enumerate((
        ("tick_size", 0.25), ("tick_size", True), ("tick_size", Decimal("0.25")),
        ("tick_size", "0"), ("value_per_price_unit", "-1"), ("currency", "usd"),
        ("currency", "USＤ"), ("root", "ＩNDEX"), ("venue", "ＴEST"),
        ("contract_id", "bad\u202eID"), ("underlying_id", "bad\x00ID"),
        ("spec_source", "x" * 257), ("family", []), ("expiry_at", "2026-12-10"),
    )):
        malformed.append({**contract(f"bad-{index}"), field: value})
    for field in contract():
        incomplete = contract("missing-" + field)
        del incomplete[field]
        malformed.append(incomplete)
    unsupported = [
        contract("physical", settlement="physical"),
        contract("nonstandard", standard_deliverable=1),
        contract("commodity", family="commodity_future"),
        contract("american", kind="options", exercise="american"),
        contract("future-underlier", kind="options", underlying_kind="future"),
    ]
    records = [contract("kept"), *malformed, *unsupported]
    result = select(records)
    assert [row["contract_id"] for row in result["selected"]] == ["kept"]
    assert result["exclusion_reasons"] == {
        "INVALID_CONTRACT_RECORD": len(malformed), "UNSUPPORTED_INSTRUMENT": len(unsupported),
    }
    assert_counts(result, len(records), 1)


@pytest.mark.parametrize("kind", ["futures", "options"])
def test_all_contract_clocks_are_explicit_effective_and_ordered(kind):
    records = [
        contract("kept", kind=kind, spec_effective_at=AS_OF),
        contract("last-trade-equals-cutoff", kind=kind, last_trade_at=AS_OF),
        contract("already-expired", kind=kind, days=-1),
        contract("last-trade-after-expiry", kind=kind, last_trade_at="2026-12-11T08:00:00Z"),
        contract("future-spec", kind=kind, spec_effective_at="2026-11-10T08:00:00.000001Z"),
        contract("naive-spec", kind=kind, spec_effective_at="2026-11-10T08:00:00"),
    ]
    result = select(records, kind=kind, spot="100" if kind == "options" else None)
    assert [row["contract_id"] for row in result["selected"]] == ["kept"]
    assert result["exclusion_reasons"] == {
        "EXPIRED_CONTRACT": 2,
        "FUTURE_SPEC_EFFECTIVE_AT": 1,
        "INVALID_CONTRACT_CLOCK_ORDER": 1,
        "INVALID_CONTRACT_RECORD": 1,
    }
    assert_counts(result, len(records), 1)


@pytest.mark.parametrize("root_request", [
    None, True, [], ["TEST:INDEX"], "", "INDEX", "TEＳT:INDEX", "TEST:ſPY", "TEST:INDEX\x00",
    "TEST:INDEX TEST:INDEX", "TEST:INDEX,TEST:OTHER", " TEST:INDEX", "TEST:INDEX ",
    "../TEST:INDEX", "https://TEST:INDEX", "TEST:INDEX;id", "TEST:INDEX\u00a0", "X" * 257,
])
def test_root_grammar_is_checked_before_accessing_the_records(root_request):
    from tradeguard.derivative_contracts import DerivativeInputError

    class UntouchedRecords:
        def __iter__(self):
            raise AssertionError("records accessed before root validation")

        def __len__(self):
            raise AssertionError("records accessed before root validation")

    with pytest.raises(DerivativeInputError):
        select(UntouchedRecords(), request=root_request)


@pytest.mark.parametrize("kind,spot,as_of", [
    ("future", None, AS_OF), (True, None, AS_OF), ([], None, AS_OF),
    ("futures", None, None), ("futures", None, "2026-11-10T08:00:00"),
    ("options", None, AS_OF), ("options", True, AS_OF), ("options", 100.0, AS_OF),
    ("options", "0", AS_OF), ("options", "-1", AS_OF), ("options", "NaN", AS_OF),
    ("options", "1e1000", AS_OF), ("options", "１００", AS_OF),
])
def test_preflight_rejects_invalid_kind_spot_and_cutoff(kind, spot, as_of):
    from tradeguard.derivative_contracts import DerivativeInputError

    with pytest.raises(DerivativeInputError):
        select([], kind=kind, spot=spot, as_of=as_of)


def test_input_is_a_bounded_materialized_list():
    from tradeguard.derivative_contracts import DerivativeInputError

    for records in (None, {}, (), "records", iter([]), [None] * 1001):
        with pytest.raises(DerivativeInputError):
            select(records)
    assert_counts(select([]), 0, 0)
    records = [contract(str(index).zfill(8)) for index in range(1000)]
    result = select(records)
    assert_counts(result, 1000, 1)
    assert result["selected"][0]["contract_id"] == "00000000"


def test_ascii_case_normalization_does_not_change_opaque_identity():
    record = contract(" 00017/cAsEé ", venue="test", root="Index", underlying_id=" 00é-Index ")
    result = select([record], request="tEsT:iNdEx")
    assert result["selected"] == [record]
    assert_counts(result, 1, 1)


@pytest.mark.parametrize("second_changes", [{}, {"tick_size": "0.5"}, {"tick_size": True}, {"root": "OTHER"}])
def test_duplicate_ids_exclude_every_copy_even_if_one_record_is_invalid(second_changes):
    records = [contract("same"), contract("same", **second_changes), contract("kept", days=45)]
    result = select(records)
    assert [row["contract_id"] for row in result["selected"]] == ["kept"]
    assert result["exclusion_reasons"] == {"DUPLICATE_CONTRACT_ID": 2}
    assert select(records[::-1]) == result
    assert_counts(result, 3, 1)


def test_opaque_ids_are_not_trimmed_casefolded_or_parsed_for_duplicates():
    records = [contract("00017"), contract("17"), contract(" 00017 "), contract("CaSe"), contract("case")]
    result = select(records)
    assert "DUPLICATE_CONTRACT_ID" not in result["exclusion_reasons"]
    assert result["selected"][0]["contract_id"] == " 00017 "
    assert_counts(result, 5, 1)


@pytest.mark.parametrize("kind", ["futures", "options"])
@pytest.mark.parametrize("field,value", [("currency", "INR"), ("underlying_id", "SYNTHETIC:OTHER")])
def test_eligible_mixed_currency_or_underlying_is_an_explicit_ambiguity(kind, field, value):
    from tradeguard.derivative_contracts import DerivativeInputError

    records = [contract("first", kind=kind), {**contract("later-expiry", kind=kind, days=45), field: value}]
    for ordering in (records, records[::-1]):
        with pytest.raises(DerivativeInputError) as caught:
            select(ordering, kind=kind, spot="100" if kind == "options" else None)
        assert caught.value.code == "AMBIGUOUS_CONTRACT_SELECTION"
        assert field in str(caught.value)


@pytest.mark.parametrize("kind,other_kind", [("futures", "options"), ("options", "futures")])
def test_only_exact_root_and_matching_kind_can_enter_selection(kind, other_kind):
    records = [
        contract("kept", kind=kind),
        contract("wrong-kind", kind=other_kind),
        contract("wrong-root", kind=kind, root="INDEXPLUS", currency="INR", underlying_id="WRONG"),
        contract("wrong-venue", kind=kind, venue="OTHER", currency="INR", underlying_id="WRONG"),
        contract("out-of-window", kind=kind, days=121, currency="INR", underlying_id="WRONG"),
    ]
    result = select(records, kind=kind, spot="100" if kind == "options" else None)
    assert [row["contract_id"] for row in result["selected"]] == ["kept"]
    assert result["exclusion_reasons"] == {"KIND_MISMATCH": 1, "ROOT_MISMATCH": 2, "OUTSIDE_SELECTION_WINDOW": 1}
    assert_counts(result, 5, 1)
