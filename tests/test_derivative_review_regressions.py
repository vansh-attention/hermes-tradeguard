"""Review regressions: coherent spread evidence and honest offline provenance."""
from copy import deepcopy

import pytest

from derivative_cases import AS_OF, snapshot
from test_derivatives import _vertical
from test_plugin import FakeContext, load_plugin


def test_vertical_rejects_opposite_histories_with_same_spot_and_identity():
    from tradeguard.derivatives import analyze_debit_vertical

    long, short = _vertical()
    for bar in short["underlying"]["bars"]:
        close = 200 - bar["close"]
        bar.update(open=close, high=close + 1, low=close - 1, close=close)
    assert long["underlying"]["spot"] == short["underlying"]["spot"]
    before = deepcopy((long, short))
    report = analyze_debit_vertical(long, short, as_of=AS_OF)
    assert report["success"] is False
    assert report["code"] == "MISMATCHED_SPREAD_EVIDENCE"
    assert report["recommendation"]["directional_support"] is None
    assert (long, short) == before


@pytest.mark.parametrize("field,value", [
    ("source", "OTHER_CALLER_SUPPLIED_HISTORY"),
    ("last_bar_finalized_at", "2026-11-09T21:00:01Z"),
])
def test_vertical_requires_one_coherent_underlying_history_attestation(field, value):
    from tradeguard.derivatives import analyze_debit_vertical

    long, short = _vertical()
    short["underlying"][field] = value
    if field == "source":
        for bar in short["underlying"]["bars"]:
            bar["source"] = value
    report = analyze_debit_vertical(long, short, as_of=AS_OF)
    assert report["success"] is False
    assert report["code"] == "MISMATCHED_SPREAD_EVIDENCE"


def test_equivalent_finalization_offsets_are_not_a_history_conflict():
    from tradeguard.derivatives import analyze_debit_vertical

    long, short = _vertical()
    short["underlying"]["last_bar_finalized_at"] = "2026-11-10T02:30:00+05:30"
    report = analyze_debit_vertical(long, short, as_of=AS_OF)
    assert report["success"] is True
    assert report["recommendation"]["score"] is None


def test_fixture_label_is_only_a_caller_declaration_not_ingress_verification():
    from tradeguard.derivatives import analyze_derivative_snapshot

    data = snapshot()
    data["source"]["provider"] = "ARBITRARY_CALLER_ASSERTION"
    report = analyze_derivative_snapshot(data, as_of=AS_OF)
    assert report["success"] is True
    assert report["data_mode"] == "fixture"
    assert report["provenance"] == {
        "ingress": "user_supplied_snapshot",
        "data_mode_is_caller_declared": True,
        "independently_verified": False,
        "trusted_live_source": False,
    }
    assert report["source"]["entitlement"] == "unverified"
    assert report["recommendation"]["score"] is None


@pytest.mark.parametrize("fixture_leg", ["long", "short"])
def test_mixed_vertical_is_not_labeled_wholly_synthetic(fixture_leg):
    from tradeguard.derivatives import analyze_debit_vertical

    long, short = _vertical()
    supplied = short if fixture_leg == "long" else long
    supplied["source"]["data_mode"] = "user_supplied"
    report = analyze_debit_vertical(long, short, as_of=AS_OF)
    assert report["success"] is True
    assert report["data_mode"] == "user_supplied"
    assert report["source"]["data_mode"] == "user_supplied"
    assert report["provenance"]["mixed_declared_modes"] is True
    assert report["provenance"]["independently_verified"] is False
    assert report["source"]["legs"][fixture_leg]["data_mode"] == "fixture"
    assert report["recommendation"]["score"] is None


def test_native_fixture_assertion_never_claims_verified_origin():
    import json

    context = FakeContext()
    load_plugin().register(context)
    result = json.loads(context.tools["tradeguard_derivatives_research"]({
        "snapshot": snapshot(), "as_of": AS_OF,
    }))
    assert result["provenance"]["ingress"] == "user_supplied_snapshot"
    assert result["provenance"]["independently_verified"] is False
    assert result["recommendation"]["score"] is None


@pytest.mark.parametrize("kind", ["future", "option"])
def test_unusable_history_cannot_show_current_directional_support(kind):
    from tradeguard.derivatives import analyze_derivative_snapshot

    result = analyze_derivative_snapshot(snapshot(kind=kind), as_of="2026-11-18T08:00:00Z")
    assert result["success"] is True
    assert result["evidence_coverage"]["checks"]["underlying_history"] is False
    assert result["recommendation"]["directional_support"] is None
    assert result["metrics"]["technical_observation_status"] == "descriptive_only_unusable_history"


@pytest.mark.parametrize("quote_changes", [
    {"observed_at": "2026-11-10T07:59:00Z", "received_at": "2026-11-10T07:59:00Z"},
    {"delay_seconds": None},
    {"market_state": "closed"},
])
def test_unusable_quote_cannot_become_available_current_iv_or_greeks(quote_changes):
    from tradeguard.derivatives import analyze_derivative_snapshot

    data = snapshot(kind="option", quote=quote_changes)
    report = analyze_derivative_snapshot(data, as_of=AS_OF)
    assert report["success"] is True
    assert report["evidence_coverage"]["checks"]["quote_evidence"] is False
    pricing = report["metrics"]["option"]["pricing"]
    assert pricing["status"] == "unavailable"
    assert pricing["iv_midpoint"] is None
    assert pricing["greeks_per_contract"] is None
    assert "DATED_MATCHING_QUOTE_UNAVAILABLE" in pricing["reason_codes"]
