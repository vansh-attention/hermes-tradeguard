"""Synthetic top-of-book arithmetic tests; no live-feed or predictive claim."""

import importlib
import importlib.util

import pytest


def module():
    assert importlib.util.find_spec("tradeguard.microstructure") is not None, (
        "the independent microstructure component is missing"
    )
    return importlib.import_module("tradeguard.microstructure")


def test_book_features_are_descriptive_not_calibrated_microprice():
    result = module().book_features(99, 101, 30, 10)
    assert result["quoted_spread"] == 2
    assert result["mid"] == 100
    assert result["spread_bps"] == 200
    assert result["queue_imbalance"] == 0.5
    assert result["weighted_midpoint"] == 100.5
    assert result["model_status"] == "unvalidated"
    assert result["data_requirements"]
    assert "microprice" not in result
    assert "recommendation" not in result


@pytest.mark.parametrize("values", [
    (102, 101, 1, 1), (0, 101, 1, 1), (99, -1, 1, 1),
    (99, 101, -1, 1), (99, 101, 1, -1), (99, 101, 0, 0),
    (float("nan"), 101, 1, 1), (99, float("inf"), 1, 1),
    (99, 101, float("nan"), 1), (99, 101, 1, float("inf")),
    (True, 101, 1, 1), ("99", 101, 1, 1),
])
def test_book_rejects_invalid_snapshots(values):
    with pytest.raises(ValueError):
        module().book_features(*values)


def test_one_empty_queue_and_locked_book_are_defined():
    result = module().book_features(100, 100, 0, 20)
    assert result["quoted_spread"] == 0
    assert result["queue_imbalance"] == -1
    assert result["weighted_midpoint"] == 100


@pytest.mark.parametrize("new,expected", [
    ({"bid": 99, "ask": 101, "bid_size": 35, "ask_size": 12}, 3),
    ({"bid": 100, "ask": 101, "bid_size": 35, "ask_size": 10}, 35),
    ({"bid": 98, "ask": 101, "bid_size": 35, "ask_size": 10}, -30),
    ({"bid": 99, "ask": 100, "bid_size": 30, "ask_size": 12}, -12),
    ({"bid": 99, "ask": 102, "bid_size": 30, "ask_size": 12}, 10),
    ({"bid": 100, "ask": 102, "bid_size": 35, "ask_size": 12}, 45),
])
def test_ofi_cont_signed_quote_changes(new, expected):
    component = module()
    assert hasattr(component, "order_flow_imbalance"), "OFI component is missing"
    events = [
        {"timestamp": 1, "bid": 99, "ask": 101, "bid_size": 30, "ask_size": 10},
        {"timestamp": 2, **new},
    ]
    result = component.order_flow_imbalance(events)
    assert result["total_ofi"] == expected
    assert result["contributions"] == [{"timestamp": 2, "ofi": expected}]
    assert result["transition_count"] == 1
    assert result["model_status"] == "unvalidated"
    assert result["data_requirements"]


@pytest.mark.parametrize("events", [
    [], [{"timestamp": 1, "bid": 99, "ask": 101, "bid_size": 1, "ask_size": 1}],
    [{"timestamp": 2, "bid": 99, "ask": 101, "bid_size": 1, "ask_size": 1},
     {"timestamp": 2, "bid": 99, "ask": 101, "bid_size": 1, "ask_size": 1}],
    [{"timestamp": 2, "bid": 99, "ask": 101, "bid_size": 1, "ask_size": 1},
     {"timestamp": 1, "bid": 99, "ask": 101, "bid_size": 1, "ask_size": 1}],
    [{"timestamp": 1, "bid": 102, "ask": 101, "bid_size": 1, "ask_size": 1},
     {"timestamp": 2, "bid": 99, "ask": 101, "bid_size": 1, "ask_size": 1}],
    [{"timestamp": float("nan"), "bid": 99, "ask": 101, "bid_size": 1, "ask_size": 1},
     {"timestamp": 2, "bid": 99, "ask": 101, "bid_size": 1, "ask_size": 1}],
    [{"timestamp": 1}, {"timestamp": 2}],
])
def test_ofi_requires_two_valid_strictly_ordered_events(events):
    with pytest.raises(ValueError):
        module().order_flow_imbalance(events)


def test_ofi_uses_utc_time_not_lexicographic_offset_order():
    events = [
        {"timestamp": "2026-01-01T10:00:00+02:00", "bid": 99, "ask": 101,
         "bid_size": 30, "ask_size": 10},
        {"timestamp": "2026-01-01T09:00:00Z", "bid": 99, "ask": 101,
         "bid_size": 40, "ask_size": 10},
        {"timestamp": "2026-01-01T09:00:01Z", "bid": 99, "ask": 101,
         "bid_size": 40, "ask_size": 15},
    ]
    result = module().order_flow_imbalance(events)
    assert result["total_ofi"] == 5
    assert [item["ofi"] for item in result["contributions"]] == [10, -5]
    events[1]["timestamp"] = "2026-01-01T08:00:00Z"
    with pytest.raises(ValueError, match="increasing"):
        module().order_flow_imbalance(events)


def test_book_arithmetic_stays_finite_for_large_finite_common_units():
    result = module().book_features(1e308, 1e308, 1e308, 1e308)
    assert result["mid"] == 1e308
    assert result["weighted_midpoint"] == 1e308
    assert result["queue_imbalance"] == 0
    assert result["spread_bps"] == 0


def test_ofi_preserves_nanosecond_integer_timestamp_order():
    events = [
        {"timestamp": 1800000000000000000, "bid": 99, "ask": 101,
         "bid_size": 30, "ask_size": 10},
        {"timestamp": 1800000000000000001, "bid": 99, "ask": 101,
         "bid_size": 40, "ask_size": 10},
    ]
    assert module().order_flow_imbalance(events)["total_ofi"] == 10


def test_unrepresentable_ofi_fails_instead_of_returning_infinity():
    events = [
        {"timestamp": 1, "bid": 99, "ask": 101, "bid_size": 1e308, "ask_size": 1e308},
        {"timestamp": 2, "bid": 100, "ask": 102, "bid_size": 1e308, "ask_size": 1e308},
    ]
    with pytest.raises(ValueError, match="finite"):
        module().order_flow_imbalance(events)


def test_large_integer_ticks_do_not_collapse_the_spread():
    tick = 2 ** 60
    result = module().book_features(tick, tick + 1, 1, 1)
    assert result["quoted_spread"] == 1
    assert result["spread_bps"] > 0
    with pytest.raises(ValueError, match="crossed"):
        module().book_features(tick + 1, tick, 1, 1)


def test_large_integer_queue_difference_is_not_rounded_away():
    size = 2 ** 60
    result = module().book_features(99, 101, size + 1, size)
    assert result["queue_imbalance"] == pytest.approx(1 / (2 * size + 1), rel=1e-15, abs=0)


def test_book_mixed_numeric_types_preserve_exact_differences():
    integer = 2 ** 60
    result = module().book_features(float(integer), integer + 1, integer + 1, float(integer))
    assert result["quoted_spread"] == 1
    assert result["queue_imbalance"] == pytest.approx(1 / (2 * integer + 1), rel=1e-15, abs=0)


@pytest.mark.parametrize("field", ["bid", "ask", "bid_size", "ask_size"])
def test_ofi_preserves_single_integer_ticks_and_queue_units(field):
    integer = 2 ** 60
    old = {"timestamp": 1, "bid": 99, "ask": 101, "bid_size": 30, "ask_size": 10}
    if field in ("bid", "ask"):
        old.update(bid=integer, ask=integer + 10)
    else:
        old[field] = integer
    new = {**old, "timestamp": 2, field: old[field] + 1}
    expected = {"bid": 30, "ask": 10, "bid_size": 1, "ask_size": -1}[field]
    report = module().order_flow_imbalance([old, new])
    assert report["total_ofi"] == expected
    assert report["contributions"][0]["ofi"] == expected


def test_ofi_integer_totals_above_float_precision_remain_exact():
    size = 2 ** 60 + 1
    quote = {"bid": 99, "ask": 103, "bid_size": size, "ask_size": 1}
    events = [
        {"timestamp": 1, **quote},
        {"timestamp": 2, **{**quote, "bid": 100}},
        {"timestamp": 3, **{**quote, "bid": 101}},
    ]
    result = module().order_flow_imbalance(events)
    assert result["total_ofi"] == 2 * size
    assert all(row["ofi"] == size for row in result["contributions"])


@pytest.mark.parametrize("old_bid_size,new_bid_size", [
    (2 ** 60, 2 ** 60 + 1),
    (float(2 ** 60), 2 ** 60 + 1),
])
def test_ofi_mixed_numeric_types_do_not_erase_integer_queue_changes(old_bid_size, new_bid_size):
    quote = {"bid": 99, "ask": 101, "ask_size": 10.0}
    events = [
        {"timestamp": 1, "bid_size": old_bid_size, **quote},
        {"timestamp": 2, "bid_size": new_bid_size, **quote},
    ]
    assert module().order_flow_imbalance(events)["total_ofi"] == 1


def test_finite_float_ofi_total_survives_intermediate_summation_overflow():
    quote = {"ask": 103.0, "bid_size": 1e308, "ask_size": 1.0}
    events = [{"timestamp": index, "bid": bid, **quote}
              for index, bid in enumerate((99.0, 100.0, 101.0, 100.0))]
    result = module().order_flow_imbalance(events)
    assert [row["ofi"] for row in result["contributions"]] == [1e308, 1e308, -1e308]
    assert result["total_ofi"] == 1e308


def test_iso_timestamp_order_does_not_round_through_epoch_floats():
    quote = {"bid": 99, "ask": 101, "bid_size": 30, "ask_size": 10}
    events = [
        {"timestamp": "2500-01-01T00:00:00.000001Z", **quote},
        {"timestamp": "2500-01-01T00:00:00.000002Z", **{**quote, "bid_size": 31}},
    ]
    result = module().order_flow_imbalance(events)
    assert result["total_ofi"] == 1
    assert result["contributions"][0]["timestamp"] == events[-1]["timestamp"]


@pytest.mark.parametrize("timestamp", [
    "2026-01-01T09:00:00.000000001Z",
    "2026-01-01T09:00:00.1234567+02:00",
    "2026-01-01T09:00:00+00:00:00.0000001",
])
def test_submicrosecond_iso_precision_must_not_be_silently_truncated(timestamp):
    quote = {"bid": 99, "ask": 101, "bid_size": 30, "ask_size": 10}
    events = [
        {"timestamp": "2020-01-01T00:00:00Z", **quote},
        {"timestamp": timestamp, **quote},
    ]
    with pytest.raises(ValueError, match="precision|microsecond|integer"):
        module().order_flow_imbalance(events)


@pytest.mark.parametrize("timestamp", [-1, True, float("inf"), None, "2026-01-01T09:00:00"])
def test_ofi_timestamp_must_be_nonnegative_finite_or_timezone_aware(timestamp):
    events = [
        {"timestamp": timestamp, "bid": 99, "ask": 101, "bid_size": 30, "ask_size": 10},
        {"timestamp": 2, "bid": 99, "ask": 101, "bid_size": 40, "ask_size": 10},
    ]
    with pytest.raises(ValueError):
        module().order_flow_imbalance(events)
