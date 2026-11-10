"""Synthetic policy mechanics, not trading-performance validation."""

from copy import deepcopy
from decimal import Decimal
from types import MappingProxyType

import pytest


BULLISH = {"last_close": 120, "sma20": 110, "sma50": 100, "sma200": 90}
ABSTAIN = {"score": None, "contract_quality": None, "verdict": "ABSTAIN",
           "strong_buy": False}


@pytest.mark.parametrize("metrics,side,expected", [
    (BULLISH, "long", 1),
    (BULLISH, "short", 0),
    ({"last_close": 90, "sma20": 100, "sma50": 110, "sma200": 120}, "long", 0),
    ({"last_close": 90, "sma20": 100, "sma50": 110, "sma200": 120}, "short", 1),
    ({"last_close": 100, "sma20": 100, "sma50": 100, "sma200": 100}, "long", .5),
    ({"last_close": 100, "sma20": 100, "sma50": 100, "sma200": 100}, "short", .5),
    ({"last_close": 105, "sma20": 100, "sma50": 110, "sma200": 100}, "long", .75),
    ({"last_close": 105, "sma20": 100, "sma50": 110, "sma200": 100}, "short", .25),
    ({"last_close": 110, "sma20": 110, "sma50": 100, "sma200": 90}, "long", .875),
    ({"last_close": 110, "sma20": 110, "sma50": 100, "sma200": 90}, "short", .125),
])
def test_directional_support_uses_all_four_comparisons_and_half_points_for_ties(
        metrics, side, expected):
    from tradeguard.derivative_policy import POLICY_VERSION, directional_support

    before = deepcopy(metrics)
    assert POLICY_VERSION == "derivatives_policy_v1"
    assert directional_support(metrics, side) == expected
    assert metrics == before


@pytest.mark.parametrize("key", BULLISH)
@pytest.mark.parametrize("absence", ["omitted", "null"])
@pytest.mark.parametrize("side", ["long", "short"])
def test_missing_required_directional_metric_abstains_without_denominator_repair(
        key, absence, side):
    from tradeguard.derivative_policy import directional_support

    metrics = dict(BULLISH)
    if absence == "omitted":
        del metrics[key]
    else:
        metrics[key] = None
    assert directional_support(metrics, side) is None


@pytest.mark.parametrize("side", [None, "", "LONG", "Short", "call", "put", True,
                                  1, [], {}, ["long"]])
def test_directional_side_is_explicit_even_when_metrics_are_missing(side):
    from tradeguard.derivative_policy import directional_support

    with pytest.raises(ValueError, match="side"):
        directional_support({}, side)


@pytest.mark.parametrize("metrics", [None, [], [BULLISH], "last_close", 0, False])
def test_directional_metrics_requires_a_mapping(metrics):
    from tradeguard.derivative_policy import directional_support

    with pytest.raises(ValueError, match="metrics"):
        directional_support(metrics, "long")


def test_directional_accepts_read_only_mapping_without_extra_signed_evidence():
    from tradeguard.derivative_policy import directional_support

    metrics = MappingProxyType({**BULLISH, "open_interest": -999, "volume": True})
    assert directional_support(metrics, "long") == 1
    assert directional_support(metrics, "short") == 0


@pytest.mark.parametrize("key", BULLISH)
@pytest.mark.parametrize("value", [True, False, float("nan"), float("inf"),
                                   -float("inf"), "100", Decimal("100"),
                                   100 + 0j, [], {}, 10**400])
def test_directional_metrics_reject_nonfinite_nonnumeric_and_booleans(key, value):
    from tradeguard.derivative_policy import directional_support

    metrics = {**BULLISH, key: value}
    with pytest.raises(ValueError, match="directional input"):
        directional_support(metrics, "long")


def test_directional_comparisons_do_not_overflow_by_subtracting_prices():
    from tradeguard.derivative_policy import directional_support

    metrics = {"last_close": 1e308, "sma20": 1e307,
               "sma50": 1e306, "sma200": 1e305}
    assert directional_support(metrics, "long") == 1


@pytest.mark.parametrize("direction,spread,quality,score,verdict", [
    (1, 0, 1, 1, "RESEARCH_CANDIDATE"),
    (0, 0, 1, 0, "LOW_INTEREST"),
    (.6, 0, 1, .6, "RESEARCH_CANDIDATE"),
    (.59994, 0, 1, .5999, "LOW_INTEREST"),
    (.59996, 0, 1, .6, "RESEARCH_CANDIDATE"),
    (1, .005, .75, .75, "RESEARCH_CANDIDATE"),
    (.8, .01, .5, .4, "LOW_INTEREST"),
    (1, .02, 0, 0, "LOW_INTEREST"),
    (1, .5, 0, 0, "LOW_INTEREST"),
    (1, 1e308, 0, 0, "LOW_INTEREST"),
    (.87654321, .003, .85, .7451, "RESEARCH_CANDIDATE"),
])
def test_research_interest_is_rounded_product_not_a_probability(
        direction, spread, quality, score, verdict):
    import json
    from tradeguard.derivative_policy import research_interest

    blockers = []
    result = research_interest(direction, spread, blockers=blockers)
    assert result == {"score": score, "contract_quality": quality,
                      "verdict": verdict, "strong_buy": False}
    assert blockers == []
    assert result["strong_buy"] is False
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize("blockers", [["STALE_QUOTE"], ["FIXTURE"],
                                      ["MISSING_MARGIN", "MISSING_COSTS"]])
def test_any_blocker_removes_score_and_quality_even_with_full_support(blockers):
    from tradeguard.derivative_policy import research_interest

    before = list(blockers)
    assert research_interest(1, 0, blockers=blockers) == ABSTAIN
    assert blockers == before


@pytest.mark.parametrize("direction,spread", [(None, 0), (1, None), (None, None)])
def test_missing_score_input_abstains_instead_of_renormalizing(direction, spread):
    from tradeguard.derivative_policy import research_interest

    assert research_interest(direction, spread, blockers=[]) == ABSTAIN


@pytest.mark.parametrize("direction", [True, False, float("nan"), float("inf"),
                                       -float("inf"), -1, -5e-324, 1.0000000000000002,
                                       2, 10**400, "1", Decimal("1"), 1 + 0j, [], {}])
def test_research_direction_requires_finite_native_number_in_unit_interval(direction):
    from tradeguard.derivative_policy import research_interest

    with pytest.raises(ValueError, match="directional support"):
        research_interest(direction, 0, blockers=[])


@pytest.mark.parametrize("spread", [True, False, float("nan"), float("inf"),
                                    -float("inf"), -1, -5e-324, 10**400,
                                    "0", Decimal("0"), 0 + 0j, [], {}])
def test_research_spread_requires_finite_native_nonnegative_fraction(spread):
    from tradeguard.derivative_policy import research_interest

    with pytest.raises(ValueError, match="spread fraction"):
        research_interest(1, spread, blockers=[])


@pytest.mark.parametrize("blockers", [None, False, True, 0, 1, "", "STALE_QUOTE",
                                      (), ("STALE_QUOTE",), {}, {"code": "STALE"},
                                      set(), iter(())])
@pytest.mark.parametrize("direction,spread", [(1, 0), (None, None)])
def test_blocker_container_must_be_an_explicit_list_even_when_inputs_missing(
        blockers, direction, spread):
    from tradeguard.derivative_policy import research_interest

    with pytest.raises(ValueError, match="blockers"):
        research_interest(direction, spread, blockers=blockers)


@pytest.mark.parametrize("blockers", [[None], [False], [0], [""], ["  "], [[]], [{}],
                                      ["STALE_QUOTE", None]])
def test_malformed_blocker_entries_cannot_act_as_valid_evidence_gates(blockers):
    from tradeguard.derivative_policy import research_interest

    with pytest.raises(ValueError, match="blockers"):
        research_interest(1, 0, blockers=blockers)
