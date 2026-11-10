"""Walk-forward checks on explicitly synthetic daily observations."""

import importlib
import importlib.util
import math
from datetime import date, timedelta

import pytest


def module():
    assert importlib.util.find_spec("tradeguard.validation") is not None, (
        "the independent validation component is missing"
    )
    return importlib.import_module("tradeguard.validation")


def bars(count=520, growth=None):
    result = []
    price = 100.0
    for i in range(count):
        price *= 1 + (growth if growth is not None else 0.001 + 0.008 * math.sin(i / 11))
        result.append({
            "date": (date(2020, 1, 1) + timedelta(days=i)).isoformat(),
            "open": price, "high": price * 1.02, "low": price * 0.98,
            "close": price, "volume": 1000 + i,
        })
    return result


def test_walk_forward_purges_labels_and_fills_only_at_next_open():
    data = bars(230)
    report = module().walk_forward(data, min_train=10, adjustment="split")
    first = report["predictions"][0]
    assert first["prediction_date"] == data[211]["date"]
    assert first["entry_date"] == data[212]["date"]
    assert first["exit_date"] == data[213]["date"]
    assert first["max_train_label_date"] == data[210]["date"]
    assert first["train_count"] == 10
    assert first["entry_open"] == data[212]["open"]
    assert first["exit_open"] == data[213]["open"]
    assert first["actual_return"] == pytest.approx(data[213]["open"] / data[212]["open"] - 1)
    assert first["baseline_prediction"] == pytest.approx(sum(
        data[j + 2]["open"] / data[j + 1]["open"] - 1 for j in range(199, 209)
    ) / 10)
    assert report["model_status"] == "experimental_unvalidated"
    for prediction in report["predictions"]:
        assert prediction["max_train_label_date"] < prediction["prediction_date"]
        assert prediction["prediction_date"] < prediction["entry_date"] < prediction["exit_date"]
    assert report["summary"]["samples"] == 17


def feature_row(data, t):
    closes = [row["close"] for row in data]
    returns = [closes[j] / closes[j - 1] - 1 for j in range(t - 19, t + 1)]
    mean_return = sum(returns) / 20
    return [
        closes[t] / closes[t - lag] - 1 for lag in (5, 21, 63)
    ] + [
        math.sqrt(sum((value - mean_return) ** 2 for value in returns) / 19),
        closes[t] / (sum(closes[t - 199:t + 1]) / 200) - 1,
    ]


def test_ridge_uses_train_only_population_scaling_and_fixed_regularization():
    data = bars(250)
    report = module().walk_forward(data, min_train=10, retrain_every=7,
                                   ridge_alpha=10, adjustment="split")
    assert "fits" in report, "each train-only ridge fit must be auditable"
    fit = report["fits"][0]
    assert fit["prediction_date"] == data[211]["date"]
    assert [item["train_count"] for item in report["fits"]] == [10, 17, 24, 31, 38, 45]
    names = ["return5", "return21", "return63", "vol20", "close_ma200_gap"]
    x = [feature_row(data, j) for j in range(199, 209)]
    means = [sum(row[k] for row in x) / len(x) for k in range(5)]
    scales = [math.sqrt(sum((row[k] - means[k]) ** 2 for row in x) / len(x))
              for k in range(5)]
    assert fit["feature_means"] == pytest.approx(dict(zip(names, means)))
    assert fit["feature_scales"] == pytest.approx(dict(zip(names, scales)))
    z = [[(row[k] - means[k]) / scales[k] for k in range(5)] for row in x]
    y = [data[j + 2]["open"] / data[j + 1]["open"] - 1 for j in range(199, 209)]
    coefficients = [fit["coefficients"][name] for name in names]
    for k in range(5):
        lhs = sum(row[k] * sum(row[l] * coefficients[l] for l in range(5)) for row in z)
        lhs += 10 * coefficients[k]
        rhs = sum(row[k] * (target - fit["training_mean"]) for row, target in zip(z, y))
        assert lhs == pytest.approx(rhs, abs=1e-10)
    expected = fit["training_mean"] + sum(
        (value - means[k]) / scales[k] * coefficients[k]
        for k, value in enumerate(feature_row(data, 211))
    )
    assert report["predictions"][0]["prediction"] == pytest.approx(expected)
    assert abs(expected - report["predictions"][0]["baseline_prediction"]) > 1e-6


def test_future_perturbation_cannot_change_past_fits_or_predictions():
    data = bars(300)
    changed = [dict(row) for row in data]
    for row in changed[270:]:
        for key in ("open", "high", "low", "close"):
            row[key] *= 1.5
    original = module().walk_forward(data, min_train=10, retrain_every=7, adjustment="split")
    perturbed = module().walk_forward(changed, min_train=10, retrain_every=7, adjustment="split")
    assert "fits" in original, "train-only fit audit is missing"
    cutoff = data[268]["date"]
    assert [p for p in original["predictions"] if p["prediction_date"] < cutoff] == [
        p for p in perturbed["predictions"] if p["prediction_date"] < cutoff
    ]
    assert [f for f in original["fits"] if f["prediction_date"] < data[270]["date"]] == [
        f for f in perturbed["fits"] if f["prediction_date"] < data[270]["date"]
    ]


@pytest.mark.parametrize("t", [211, 218, 225])
def test_prediction_clock_open_is_purged_but_last_completed_label_is_eligible(t):
    data = bars(250)
    original = module().walk_forward(data, min_train=10, retrain_every=7, adjustment="split")
    original_fit = next(fit for fit in original["fits"] if fit["prediction_date"] == data[t]["date"])

    unavailable = [dict(row) for row in data]
    unavailable[t]["open"] *= 1.01  # The label ending at t must not enter a fit at t.
    purged = module().walk_forward(unavailable, min_train=10, retrain_every=7, adjustment="split")
    assert next(fit for fit in purged["fits"] if fit["prediction_date"] == data[t]["date"]) == original_fit
    assert purged["predictions"][t - 211]["prediction"] == original["predictions"][t - 211]["prediction"]

    available = [dict(row) for row in data]
    available[t - 1]["open"] *= 1.01
    eligible = module().walk_forward(available, min_train=10, retrain_every=7, adjustment="split")
    fit = next(fit for fit in eligible["fits"] if fit["prediction_date"] == data[t]["date"])
    expected_mean_change = (available[t - 1]["open"] - data[t - 1]["open"]) / data[t - 2]["open"]
    expected_mean_change /= original_fit["train_count"]
    assert fit["training_mean"] - original_fit["training_mean"] == pytest.approx(expected_mean_change)
    assert fit["max_train_label_date"] == data[t - 1]["date"]


@pytest.mark.parametrize("t", [211, 218, 225])
def test_next_open_outcome_changes_cannot_change_the_signal_or_fit(t):
    data = bars(250)
    changed = [dict(row) for row in data]
    for row in changed[t + 1:]:
        for key in ("open", "high", "low", "close"):
            row[key] *= 1.5
    original = module().walk_forward(data, min_train=10, retrain_every=7, adjustment="split")
    perturbed = module().walk_forward(changed, min_train=10, retrain_every=7, adjustment="split")
    cutoff = data[t]["date"]
    signal_fields = ("prediction_date", "prediction", "baseline_prediction", "train_count",
                     "max_train_label_date", "position")
    for left, right in zip(original["predictions"], perturbed["predictions"]):
        if left["prediction_date"] <= cutoff:
            assert {key: left[key] for key in signal_fields} == {key: right[key] for key in signal_fields}
    assert [fit for fit in original["fits"] if fit["prediction_date"] <= cutoff] == [
        fit for fit in perturbed["fits"] if fit["prediction_date"] <= cutoff
    ]


@pytest.mark.parametrize("count", [0, 199, 213])
def test_short_series_fails_instead_of_inventing_samples(count):
    with pytest.raises(ValueError, match="samples"):
        module().walk_forward(bars(count), min_train=10, adjustment="raw")


@pytest.mark.parametrize("field,value", [
    ("open", float("nan")), ("close", float("inf")), ("low", 0),
    ("high", -1), ("volume", -1), ("volume", float("nan")),
    ("open", True), ("close", "100"), ("adjusted_close", float("inf")),
    ("adjusted_close", 0), ("date", "not-a-date"), ("date", "2020-2-03"),
])
def test_nonfinite_or_invalid_bars_are_rejected(field, value):
    data = bars(230)
    data[7][field] = value
    with pytest.raises(ValueError):
        module().walk_forward(data, min_train=10, adjustment="split")


@pytest.mark.parametrize("change", ["duplicate", "reverse", "ohlc", "missing", "nondict"])
def test_chronological_unique_consistent_ohlcv_is_required(change):
    data = bars(230)
    if change == "duplicate":
        data[8]["date"] = data[7]["date"]
    elif change == "reverse":
        data.reverse()
    elif change == "ohlc":
        data[7]["high"] = data[7]["low"]
    elif change == "missing":
        del data[7]["volume"]
    else:
        data[7] = None
    with pytest.raises(ValueError):
        module().walk_forward(data, min_train=10, adjustment="split")


@pytest.mark.parametrize("kwargs", [
    {"min_train": 0}, {"min_train": True}, {"min_train": 1.5},
    {"retrain_every": 0}, {"retrain_every": True}, {"retrain_every": 1.5},
    {"cost_bps": -1}, {"cost_bps": float("nan")}, {"cost_bps": 10000},
    {"cost_bps": True}, {"ridge_alpha": 0}, {"ridge_alpha": -1},
    {"ridge_alpha": float("inf")}, {"ridge_alpha": True},
])
def test_model_configuration_is_bounded_finite_and_explicit(kwargs):
    with pytest.raises(ValueError):
        module().walk_forward(bars(230), adjustment="raw", **kwargs)


@pytest.mark.parametrize("adjustment", ["total_return", "unknown", None])
def test_total_return_or_unspecified_adjustment_cannot_mix_with_opens(adjustment):
    with pytest.raises(ValueError, match="adjustment"):
        module().walk_forward(bars(230), min_train=10, adjustment=adjustment)


def test_row_adjustment_metadata_cannot_contradict_series_basis():
    data = bars(230)
    data[2]["adjustment"] = "total_return"
    with pytest.raises(ValueError, match="adjustment"):
        module().walk_forward(data, min_train=10, adjustment="raw")


def test_row_limit_is_fixed_and_never_truncates_silently():
    with pytest.raises(ValueError, match="4000"):
        module().walk_forward(bars(4001), adjustment="raw")


def test_long_cash_costs_include_entry_changes_and_final_liquidation():
    data = bars(250, growth=0.005)
    report = module().walk_forward(data, min_train=10, cost_bps=5, adjustment="split")
    assert "strategy" in report["summary"], "self-financing cost accounting is missing"
    predictions = report["predictions"]
    strategy, benchmark = report["summary"]["strategy"], report["summary"]["buy_hold"]
    fee = 5 / 10000
    gross_wealth = data[-1]["open"] / data[212]["open"]
    assert all(row["position"] == 1 for row in predictions)
    assert strategy["gross_ending_wealth"] == pytest.approx(gross_wealth)
    assert strategy["ending_wealth"] == pytest.approx(gross_wealth * (1 - fee) ** 2)
    assert strategy["trade_count"] == 2
    assert strategy["turnover"] == 2
    assert strategy["completed_round_trips"] == 1
    assert strategy["total_cost"] == pytest.approx(fee + gross_wealth * (1 - fee) * fee)
    assert predictions[0]["entry_cost"] == pytest.approx(fee)
    assert predictions[-1]["liquidation_cost"] > 0
    assert benchmark["start_date"] == strategy["start_date"] == data[212]["date"]
    assert benchmark["end_date"] == strategy["end_date"] == data[-1]["date"]
    assert benchmark["ending_wealth"] == pytest.approx(strategy["ending_wealth"])
    assert strategy["ending_wealth"] == pytest.approx(math.prod(
        1 + row["net_return"] for row in predictions
    ))


@pytest.mark.parametrize("positions", [[0, 1, 1, 0, 1], [0, 1, 0, 1, 0]])
def test_switching_costs_match_independent_cash_and_share_ledger(positions):
    opens = [100.0, 110.0, 99.0, 99.0, 108.9, 98.01]
    predictions = [{
        "entry_date": f"2026-01-{i + 1:02d}", "exit_date": f"2026-01-{i + 2:02d}",
        "actual_return": opens[i + 1] / opens[i] - 1,
    } for i in range(len(positions))]
    fee = 0.01
    summary, rows = module()._portfolio(predictions, positions, fee)
    cash, shares, previous_wealth = 1.0, 0.0, 1.0
    total_cost = 0.0
    trades = 0
    for i, (position, row) in enumerate(zip(positions, rows)):
        rebalance = liquidation = 0.0
        if position and shares == 0:
            rebalance = cash * fee
            shares = (cash - rebalance) / opens[i]
            cash = 0.0
            trades += 1
        elif not position and shares:
            proceeds = shares * opens[i]
            rebalance = proceeds * fee
            cash, shares = proceeds - rebalance, 0.0
            trades += 1
        if i == len(positions) - 1 and shares:
            proceeds = shares * opens[i + 1]
            liquidation = proceeds * fee
            cash, shares = proceeds - liquidation, 0.0
            trades += 1
        wealth = cash + shares * opens[i + 1]
        total_cost += rebalance + liquidation
        assert row["rebalance_cost"] == pytest.approx(rebalance)
        assert row["liquidation_cost"] == pytest.approx(liquidation)
        assert row["ending_wealth"] == pytest.approx(wealth)
        assert row["net_return"] == pytest.approx(wealth / previous_wealth - 1)
        previous_wealth = wealth
    assert summary["ending_wealth"] == pytest.approx(cash)
    assert summary["total_cost"] == pytest.approx(total_cost)
    assert summary["trade_count"] == summary["turnover"] == trades == 4
    assert summary["completed_round_trips"] == 2
    assert summary["total_cost_rate"] == pytest.approx(trades * fee)
    assert rows[-1]["liquidation_cost"] > 0 if positions[-1] else rows[-1]["liquidation_cost"] == 0

    benchmark, _ = module()._portfolio(predictions, [1] * len(predictions), fee)
    assert benchmark["ending_wealth"] == pytest.approx(opens[-1] / opens[0] * (1 - fee) ** 2)
    assert benchmark["start_date"] == summary["start_date"] == predictions[0]["entry_date"]
    assert benchmark["end_date"] == summary["end_date"] == predictions[-1]["exit_date"]


def test_single_period_buyhold_charges_both_sides_and_has_no_sharpe():
    report = module().walk_forward(bars(214, growth=0.005), min_train=10,
                                   cost_bps=5, adjustment="split")
    summary = report["summary"]
    assert summary["samples"] == 1
    strategy, benchmark = summary["strategy"], summary["buy_hold"]
    assert strategy == benchmark
    assert strategy["sharpe"] is None
    assert strategy["trade_count"] == strategy["turnover"] == 2
    assert strategy["ending_wealth"] == pytest.approx(1.005 * (1 - 0.0005) ** 2)
    assert report["predictions"][0]["entry_cost"] > 0
    assert report["predictions"][0]["liquidation_cost"] > 0


def test_one_training_sample_has_constant_scaling_and_unpenalized_mean_prediction():
    report = module().walk_forward(bars(205), min_train=1, adjustment="raw")
    fit = report["fits"][0]
    assert fit["train_count"] == 1
    assert all(scale == 1 for scale in fit["feature_scales"].values())
    assert all(coefficient == 0 for coefficient in fit["coefficients"].values())
    assert report["predictions"][0]["prediction"] == fit["training_mean"]
    assert fit["max_train_label_date"] < fit["prediction_date"]


def test_roundtrip_fee_threshold_can_keep_strategy_in_cash():
    data = bars(250, growth=0.0005)
    no_fee = module().walk_forward(data, min_train=10, cost_bps=0, adjustment="raw")
    fee = module().walk_forward(data, min_train=10, cost_bps=5, adjustment="raw")
    assert "position" in fee["predictions"][0], "long/cash rule is missing"
    assert all(row["position"] == 0 for row in fee["predictions"])
    assert all(row["position"] == 1 for row in no_fee["predictions"])
    assert fee["summary"]["strategy"]["ending_wealth"] == 1
    assert no_fee["summary"]["strategy"]["ending_wealth"] > 1


def test_flat_market_has_no_strategy_trades_and_buyhold_fees_reduce_wealth():
    report = module().walk_forward(bars(230, growth=0), min_train=10,
                                   cost_bps=5, adjustment="raw")
    assert "buy_hold" in report["summary"], "same-date benchmark is missing"
    strategy, benchmark = report["summary"]["strategy"], report["summary"]["buy_hold"]
    assert strategy["trade_count"] == strategy["total_cost"] == 0
    assert strategy["ending_wealth"] == 1
    assert strategy["sharpe"] is None
    assert benchmark["gross_ending_wealth"] == 1
    assert benchmark["ending_wealth"] == pytest.approx((1 - 0.0005) ** 2)
    assert benchmark["max_drawdown"] == pytest.approx(1 - benchmark["ending_wealth"])


def test_oos_errors_compare_against_each_fold_training_mean_and_daily_metrics():
    report = module().walk_forward(bars(300), min_train=10, retrain_every=7,
                                   cost_bps=5, adjustment="split")
    summary = report["summary"]
    assert "mae" in summary, "out-of-sample error metrics are missing"
    rows = report["predictions"]
    errors = [row["actual_return"] - row["prediction"] for row in rows]
    baseline_errors = [row["actual_return"] - row["baseline_prediction"] for row in rows]
    assert summary["mae"] == pytest.approx(sum(abs(v) for v in errors) / len(rows))
    assert summary["baseline_mae"] == pytest.approx(sum(abs(v) for v in baseline_errors) / len(rows))
    assert summary["r2_oos_vs_training_mean"] == pytest.approx(
        1 - sum(v * v for v in errors) / sum(v * v for v in baseline_errors)
    )
    net_returns = [row["net_return"] for row in rows]
    mean = sum(net_returns) / len(rows)
    std = math.sqrt(sum((r - mean) ** 2 for r in net_returns) / (len(rows) - 1))
    strategy = summary["strategy"]
    assert strategy["sharpe"] == pytest.approx(mean / std * math.sqrt(252))
    assert strategy["annualization"] == 252
    assert strategy["riskfree"] == 0
    wealth = peak = 1.0
    drawdown = 0
    for row in rows:
        wealth *= 1 + row["net_return"]
        peak = max(peak, wealth)
        drawdown = max(drawdown, 1 - wealth / peak)
    assert strategy["max_drawdown"] == pytest.approx(drawdown)
    assert strategy["total_return"] == pytest.approx(wealth - 1)


def test_flat_and_one_sample_metrics_are_json_safe_not_fake_certainty():
    import json

    report = module().walk_forward(bars(214, growth=0), min_train=10, adjustment="raw")
    assert "r2_oos_vs_training_mean" in report["summary"], "undefined R2 must be explicit"
    assert report["summary"]["samples"] == 1
    assert report["summary"]["r2_oos_vs_training_mean"] is None
    assert report["summary"]["mae"] == report["summary"]["baseline_mae"] == 0
    assert report["summary"]["strategy"]["sharpe"] is None
    assert report["model_status"] == "experimental_unvalidated"
    assert report["methodology"]["roundtrip_threshold"] == "prediction > 2 * cost_bps / 10000"
    assert report["limitations"]
    assert report["data_requirements"]
    encoded = json.dumps(report, allow_nan=False)
    assert '"confidence"' not in encoded and '"probability"' not in encoded


def test_adjusted_close_is_never_mixed_with_raw_open_and_input_is_unchanged():
    from copy import deepcopy

    data = bars(230)
    for row in data:
        row["adjusted_close"] = row["close"] * 0.1
    before = deepcopy(data)
    with_adjusted = module().walk_forward(data, min_train=10, adjustment="raw")
    plain = module().walk_forward(bars(230), min_train=10, adjustment="raw")
    assert "adjusted_close_policy" in with_adjusted["methodology"], "price basis must be explicit"
    assert with_adjusted["predictions"] == plain["predictions"]
    assert with_adjusted["fits"] == plain["fits"]
    assert data == before


@pytest.mark.parametrize("basis", ["close", "open"])
def test_finite_input_overflow_or_return_rounding_cannot_escape_as_nan_or_crash(basis):
    data = bars(230)
    if basis == "close":
        for key in ("open", "high", "low", "close"):
            data[220][key] = 1e-308
            data[221][key] = 1e308
    else:
        data[220]["open"] = data[220]["high"] = 1e308
    with pytest.raises(ValueError, match="finite|numeric"):
        module().walk_forward(data, min_train=10, adjustment="raw")


@pytest.mark.parametrize("spacing", ["two_day", "sparse_oos", "long_gap"])
def test_sparse_histories_cannot_claim_daily_annualized_metrics(spacing):
    data = bars(250)
    start = date.fromisoformat(data[0]["date"])
    for i, row in enumerate(data):
        if spacing == "two_day":
            offset = 2 * i
        elif spacing == "sparse_oos":
            offset = i if i < 212 else 211 + 7 * (i - 211)
        else:
            offset = i + (8 if i >= 220 else 0)
        row["date"] = (start + timedelta(days=offset)).isoformat()
    with pytest.raises(ValueError, match="daily|session|gap"):
        module().walk_forward(data, min_train=10, adjustment="raw")


@pytest.mark.parametrize("count", [214, 230])
def test_business_day_weekend_gaps_are_not_sparse_even_with_one_sample(count):
    data = bars(count)
    current = date(2020, 1, 1)
    for row in data:
        while current.weekday() >= 5:
            current += timedelta(days=1)
        row["date"] = current.isoformat()
        current += timedelta(days=1)
    assert date.fromisoformat(data[212]["date"]).weekday() == 4
    report = module().walk_forward(data, min_train=10, adjustment="raw")
    assert report["summary"]["samples"] == count - 213


def test_default_minimum_and_fixed_maximum_produce_real_samples():
    report = module().walk_forward(bars(456), adjustment="raw")
    assert report["configuration"]["max_rows"] == 4000
    assert report["summary"]["samples"] == 1
    assert report["predictions"][0]["train_count"] == 252
    maximum = module().walk_forward(bars(4000), adjustment="raw")
    assert maximum["summary"]["samples"] == 3545
    assert maximum["predictions"][-1]["exit_date"] == bars(4000)[-1]["date"]
