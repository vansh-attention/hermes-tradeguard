"""Synthetic unit inputs only: never evidence of investment performance."""

import importlib
from datetime import date, timedelta

import pytest


def analyze(snapshot, as_of="2026-11-09"):
    return importlib.import_module("tradeguard.equity").analyze_snapshot(snapshot, as_of)


def snapshot(count=260, asset_type="stock", mode="historical"):
    end = date(2026, 11, 9)
    dates = []
    while len(dates) < count:
        if end.weekday() < 5:
            dates.append(end.isoformat())
        end -= timedelta(days=1)
    dates.reverse()
    return {
        "symbol": "SYNTH", "asset_type": asset_type, "currency": "USD",
        "source": "synthetic unit test; not market evidence",
        "retrieved_at": "2026-11-09T22:00:00Z", "data_mode": mode,
        "exchange_timezone": "America/New_York", "session_close_at": "2026-11-09T21:00:00Z",
        "adjustment": "split", "interval": "1d",
        "bars": [
            {"date": day, "open": 100 + i, "high": 102 + i,
             "low": 98 + i, "close": 101 + i, "volume": 1_000_000}
            for i, day in enumerate(dates)
        ],
    }


def test_empty_input_cleanly_abstains_with_explicit_research_contract():
    result = analyze({})
    assert result["recommendation"]["action"] == "ABSTAIN"
    assert result["recommendation"]["score"] == 0
    assert result["research_only"] is True
    assert result["model_status"] == "unvalidated_heuristic"
    assert result["confidence"]["meaning"] == "evidence_coverage_not_win_probability"
    assert result["validation_errors"]
    assert result["missing_data"]


def test_valid_daily_metadata_preserves_provenance_without_input_mutation():
    import copy

    data = snapshot()
    before = copy.deepcopy(data)
    result = analyze(data)
    assert result["validation_errors"] == []
    assert result["symbol"] == "SYNTH"
    assert result["sources"]["prices"]["source"] == data["source"]
    assert result["sources"]["prices"]["data_mode"] == "historical"
    assert data == before


@pytest.mark.parametrize("field,value", [
    ("interval", "1h"), ("asset_type", "crypto"), ("data_mode", "guess"),
    ("adjustment", "unknown"), ("currency", ""), ("source", None),
    ("symbol", ""), ("retrieved_at", "not-a-timestamp"),
])
def test_invalid_metadata_abstains(field, value):
    data = snapshot()
    data[field] = value
    result = analyze(data)
    assert result["recommendation"]["action"] == "ABSTAIN"
    assert any(field in error for error in result["validation_errors"])


@pytest.mark.parametrize("field,value", [
    ("close", True), ("volume", False), ("open", 0), ("high", -1),
    ("low", float("nan")), ("close", float("inf")),
    ("close", "110"), ("high", 90), ("date", "2026-2-3"),
])
def test_invalid_bars_abstain_without_silently_dropping_rows(field, value):
    data = snapshot()
    data["bars"][0][field] = value
    result = analyze(data)
    assert result["validation_errors"]
    assert result["recommendation"]["action"] == "ABSTAIN"


@pytest.mark.parametrize("change", ["duplicate", "reversed", "future", "too_many"])
def test_date_order_future_and_resource_limits_are_explicit(change):
    data = snapshot()
    if change == "duplicate":
        data["bars"][1]["date"] = data["bars"][0]["date"]
    elif change == "reversed":
        data["bars"].reverse()
    elif change == "future":
        data["bars"][-1]["date"] = "2026-11-10"
    else:
        data["bars"] = [data["bars"][0]] * 10001
    result = analyze(data)
    assert result["recommendation"]["action"] == "ABSTAIN"
    assert result["validation_errors"]


def test_daily_technical_formulas_use_trading_observations_and_sample_volatility():
    import math
    import statistics

    data = snapshot()
    result = analyze(data)
    metrics = result["metrics"]["technical"]
    closes = [bar["close"] for bar in data["bars"]]
    assert metrics["sma20"] == pytest.approx(statistics.mean(closes[-20:]))
    assert metrics["sma50"] == pytest.approx(statistics.mean(closes[-50:]))
    assert metrics["sma200"] == pytest.approx(statistics.mean(closes[-200:]))
    assert metrics["rsi14"] == 100
    assert metrics["atr14"] == 4
    assert metrics["vol20"] == pytest.approx(statistics.stdev(
        [closes[i] / closes[i - 1] - 1 for i in range(len(closes) - 20, len(closes))]
    ) * math.sqrt(252))
    assert metrics["max_drawdown"] == 0
    for period in (21, 63, 252):
        assert metrics[f"return{period}"] == pytest.approx(closes[-1] / closes[-period - 1] - 1)
    assert metrics["momentum12_1"] == pytest.approx(closes[-22] / closes[-253] - 1)
    assert metrics["dollar_volume20"] == pytest.approx(statistics.mean(closes[-20:]) * 1_000_000)
    assert metrics["macd"] == pytest.approx(metrics["ema12"] - metrics["ema26"])
    assert result["coverage"]["technical"]["fraction"] == 1


@pytest.mark.parametrize("basis", ["split", "total_return", "raw", "partial"])
def test_adjustment_basis_never_mixes_raw_high_low_with_adjusted_close(basis):
    data = snapshot()
    for bar in data["bars"]:
        bar["adjusted_close"] = bar["close"]
        for field in ("open", "high", "low", "close"):
            bar[field] *= 2
    data["adjustment"] = "split" if basis == "partial" else basis
    if basis == "partial":
        del data["bars"][0]["adjusted_close"]
    result = analyze(data)
    if basis in ("partial", "raw"):
        assert result["validation_errors"]
        assert result["recommendation"]["action"] == "ABSTAIN"
    else:
        metrics = result["metrics"]["technical"]
        assert metrics["sma20"] == pytest.approx(350.5)
        assert metrics["dollar_volume20"] == pytest.approx(701_000_000)
        if basis == "split":
            assert metrics["atr14"] == 4
        else:
            assert metrics["atr14"] is None
            assert any("ATR" in warning for warning in result["warnings"])


def fundamentals():
    return {
        "source": "synthetic annual statement", "filed_at": "2026-02-01",
        "period_end": "2025-12-31", "currency": "USD", "revenue": 1000,
        "revenue_prev": 800, "net_income": 150, "operating_income": 200,
        "gross_profit": 600, "operating_cash_flow": 180, "capex": 30,
        "assets": 2000, "assets_prev": 1600, "equity": 1000,
        "total_debt": 200, "cash": 100, "interest_expense": 20, "market_cap": 2000,
    }


def test_stock_fundamentals_are_as_reported_ratios_not_guessed_ttm():
    data = snapshot()
    data["fundamentals"] = fundamentals()
    result = analyze(data)
    metrics = result["metrics"]["fundamentals"]
    expected = {
        "earnings_yield": .075, "fcf_yield": .075, "roe": .15, "roa": .075,
        "revenue_growth": .25, "operating_margin": .2, "gross_margin": .6,
        "net_debt_to_assets": .05, "interest_coverage": 10,
        "accrual_ratio": -30 / 1800,
    }
    assert metrics == pytest.approx(expected)
    coverage = result["coverage"]["fundamentals"]
    assert coverage["fraction"] == 1
    assert coverage["period_basis"] == "as_reported_not_ttm_not_annualized"
    assert coverage["annual_duration_verified"] is False
    assert coverage["period_end"] == "2025-12-31"
    assert result["sources"]["fundamentals"]["source"] == "synthetic annual statement"


@pytest.mark.parametrize("field,value", [
    ("filed_at", "2026-11-10"), ("period_end", "2026-02-02"),
    ("filed_at", "bad-date"), ("currency", "EUR"), ("source", ""),
    ("capex", -30), ("market_cap", True), ("cash", float("nan")),
    ("revenue", float("inf")), ("assets", "2000"), ("net_income", 10**400),
])
def test_invalid_or_future_fundamentals_are_never_used(field, value):
    data = snapshot()
    data["fundamentals"] = {**fundamentals(), field: value}
    result = analyze(data)
    assert result["recommendation"]["action"] == "ABSTAIN"
    assert any("fundamentals" in error for error in result["validation_errors"])
    assert result["metrics"]["fundamentals"].get("earnings_yield") is None


def test_missing_market_cap_and_nonpositive_denominators_do_not_become_safe_ratios():
    data = snapshot()
    data["fundamentals"] = {**fundamentals(), "equity": -100,
                            "assets": 0, "revenue_prev": 0, "interest_expense": 0}
    del data["fundamentals"]["market_cap"]
    result = analyze(data)
    metrics = result["metrics"]["fundamentals"]
    for field in ("earnings_yield", "fcf_yield", "roe", "roa", "revenue_growth",
                  "interest_coverage", "accrual_ratio", "net_debt_to_assets"):
        assert metrics[field] is None
        assert f"fundamentals.{field}" in result["missing_data"]
    assert result["coverage"]["fundamentals"]["fraction"] == .2


def etf_metadata():
    return {
        "source": "synthetic issuer metadata", "as_of": "2026-11-09",
        "expense_ratio": .001, "nav": 359, "nav_date": "2026-11-09",
        "holdings": [{"symbol": f"H{i}", "weight": .05} for i in range(20)],
    }


def test_etf_costs_nav_and_full_holdings_do_not_use_company_earnings():
    data = snapshot(asset_type="etf")
    data["etf"] = etf_metadata()
    data["fundamentals"] = fundamentals()
    result = analyze(data)
    metrics = result["metrics"]["etf"]
    assert metrics["expense_ratio"] == .001
    assert metrics["nav_premium"] == pytest.approx(360 / 359 - 1)
    assert metrics["holdings_weight_coverage"] == pytest.approx(1)
    assert metrics["hhi"] == pytest.approx(.05)
    assert metrics["top10_weight"] == pytest.approx(.5)
    assert metrics["hhi_observed"] == pytest.approx(.05)
    assert result["metrics"]["fundamentals"] == {}
    assert result["coverage"]["fundamentals"]["status"] == "not_applicable"
    assert result["sources"]["etf"]["source"] == "synthetic issuer metadata"


@pytest.mark.parametrize("field,value", [
    ("expense_ratio", 1.5), ("expense_ratio", True), ("nav", 0),
    ("nav", float("nan")), ("as_of", "2026-11-10"),
    ("nav_date", "2026-11-10"), ("as_of", None), ("currency", "EUR"),
    ("source", ""), ("holdings", "top ten"),
    ("holdings", [{"symbol": "X", "weight": 25}]),
    ("holdings", [{"symbol": "X", "weight": -.01}]),
    ("holdings", [{"symbol": "X", "weight": True}]),
    ("holdings", [{"symbol": "X", "weight": .6}, {"symbol": "Y", "weight": .5}]),
    ("holdings", [{"symbol": "X", "weight": .4}, {"symbol": "X", "weight": .4}]),
])
def test_etf_metadata_has_explicit_dates_types_and_fraction_units(field, value):
    data = snapshot(asset_type="etf")
    data["etf"] = {**etf_metadata(), field: value}
    result = analyze(data)
    assert result["recommendation"]["action"] == "ABSTAIN"
    assert any("etf" in error for error in result["validation_errors"])


def test_partial_holdings_are_not_rescaled_into_a_full_portfolio():
    data = snapshot(asset_type="etf")
    data["etf"] = {**etf_metadata(), "holdings": [
        {"symbol": "H1", "weight": .2}, {"symbol": "H2", "weight": .1}]}
    data["etf"]["nav_date"] = "2026-11-06"
    result = analyze(data)
    metrics = result["metrics"]["etf"]
    assert metrics["holdings_weight_coverage"] == pytest.approx(.3)
    assert metrics["hhi_observed"] == pytest.approx(.05)
    assert metrics["top10_weight_observed"] == pytest.approx(.3)
    assert metrics["hhi"] is None
    assert metrics["top10_weight"] is None
    assert metrics["nav_premium"] is None
    assert any("Partial holdings" in message for message in result["warnings"])


def test_aligned_benchmark_returns_report_tracking_error_without_inventing_benchmark():
    data = snapshot(asset_type="etf")
    data["etf"] = etf_metadata()
    data["etf"]["benchmark_returns"] = [
        {"date": bar["date"], "return": bar["close"] / data["bars"][i - 1]["close"] - 1}
        for i, bar in enumerate(data["bars"]) if i > 0]
    result = analyze(data)
    assert result["metrics"]["benchmark"]["tracking_error"] == 0
    assert result["metrics"]["benchmark"]["relative_return21"] == pytest.approx(0)
    assert result["coverage"]["benchmark"]["fraction"] == 1
    del data["etf"]["benchmark_returns"]
    result = analyze(data)
    assert result["metrics"]["benchmark"]["tracking_error"] is None
    assert "etf.benchmark_returns" in result["missing_data"]


@pytest.mark.parametrize("corruption", ["unmatched_date", "short", "bad_return", "not_dicts"])
def test_benchmark_returns_require_explicit_complete_alignment(corruption):
    data = snapshot(asset_type="etf", count=22)
    benchmark = [{"date": bar["date"], "return": .001} for bar in data["bars"][1:]]
    if corruption == "unmatched_date":
        benchmark[0]["date"] = "2020-01-01"
    elif corruption == "short":
        benchmark.pop()
    elif corruption == "bad_return":
        benchmark[0]["return"] = True
    else:
        benchmark = [.001] * 21
    data["etf"] = {**etf_metadata(), "benchmark_returns": benchmark}
    result = analyze(data)
    assert result["recommendation"]["action"] == "ABSTAIN"
    assert any("benchmark_returns" in error for error in result["validation_errors"])


def test_fixed_weight_research_strategies_separate_horizons_and_explain_both_sides():
    data = snapshot()
    data["fundamentals"] = {**fundamentals(), "symbol": data["symbol"],
                            "period_start": "2025-01-01", "market_cap_as_of": "2026-11-09"}
    result = analyze(data)
    strategies = result["strategies"]
    trend = strategies["trend_following"]
    value = strategies["value_quality"]
    reversion = strategies["mean_reversion"]
    assert trend["horizon"] == "technical_swing_weeks_to_months"
    assert value["horizon"] == "fundamental_investing_years"
    assert trend["score"] == 100
    assert value["score"] == 100
    assert reversion["score"] <= 60
    for strategy in (trend, value, reversion):
        assert strategy["weight_denominator"] == 100
        assert sum(check["weight"] for check in strategy["checks"]) == 100
        assert isinstance(strategy["bullish_reasons"], list)
        assert isinstance(strategy["bearish_reasons"], list)
    assert reversion["bearish_reasons"]
    assert result["recommendation"]["action"] == "RESEARCH_CANDIDATE"
    assert result["recommendation"]["score"] == 100
    assert result["recommendation"]["score_kind"] == "heuristic_uncalibrated_not_probability"
    assert result["confidence"]["label"] == "high_evidence_coverage"


def test_missing_evidence_does_not_renormalize_value_or_overall_score():
    data = snapshot()
    data["fundamentals"] = {key: value for key, value in fundamentals().items()
                            if key in {"source", "filed_at", "period_end", "currency", "net_income", "market_cap"}}
    result = analyze(data)
    assert result["strategies"]["value_quality"]["score"] == 15
    assert result["strategies"]["value_quality"]["weight_denominator"] == 100
    assert result["recommendation"]["score"] == 49
    assert result["recommendation"]["action"] == "ABSTAIN"


@pytest.mark.parametrize("problem", ["fixture", "stale_prices", "stale_fundamentals", "stale_etf", "sparse"])
def test_non_actionable_evidence_blocks_every_strategy_even_with_bullish_metrics(problem):
    data = snapshot(asset_type="etf" if problem == "stale_etf" else "stock")
    data["fundamentals"] = fundamentals()
    data["etf"] = etf_metadata()
    as_of = "2026-11-09"
    if problem == "fixture":
        data["data_mode"] = "fixture"
    elif problem == "stale_prices":
        as_of = "2026-11-20"
    elif problem == "stale_fundamentals":
        data["fundamentals"]["filed_at"] = "2025-01-01"
        data["fundamentals"]["period_end"] = "2024-12-31"
    elif problem == "stale_etf":
        data["etf"]["as_of"] = "2026-01-01"
    else:
        data["bars"][0]["date"] = "2020-01-01"
    result = analyze(data, as_of)
    assert result["recommendation"]["action"] == "ABSTAIN"
    assert result["recommendation"]["score"] == 0
    assert result["recommendation"]["blockers"]
    assert result["warnings"]
    assert result["confidence"]["label"] != "high_evidence_coverage"
    assert all(strategy.get("action") != "RESEARCH_CANDIDATE"
               for strategy in result["strategies"].values())


@pytest.mark.parametrize("component", ["fundamentals", "etf"])
def test_component_identity_must_match_snapshot_when_provided(component):
    data = snapshot(asset_type="etf" if component == "etf" else "stock")
    data[component] = {**(etf_metadata() if component == "etf" else fundamentals()), "symbol": "OTHER"}
    result = analyze(data)
    assert result["recommendation"]["action"] == "ABSTAIN"
    assert any(f"{component}.symbol" in error for error in result["validation_errors"])


def test_upstream_provider_caveats_survive_even_when_validation_abstains():
    data = snapshot()
    data["provider_warnings"] = ["provider does not verify vintage data"]
    data["fundamentals"] = {**fundamentals(), "warnings": ["Annual not TTM; no current market cap"]}
    data["etf"] = {**etf_metadata(), "warnings": ["Partial holdings provided by issuer"]}
    data["bars"][0]["close"] = float("nan")
    result = analyze(data)
    assert "provider does not verify vintage data" in result["warnings"]
    assert "Annual not TTM; no current market cap" in result["warnings"]
    assert "Partial holdings provided by issuer" in result["warnings"]


def test_retrieval_before_observed_prices_is_invalid_but_later_download_is_not_vintage():
    data = snapshot()
    data["retrieved_at"] = "2026-11-01T00:00:00Z"
    result = analyze(data)
    assert result["recommendation"]["action"] == "ABSTAIN"
    assert any("retrieved_at" in error for error in result["validation_errors"])
    data["retrieved_at"] = "2026-11-10T08:00:00+05:30"
    result = analyze(data)
    assert not result["validation_errors"]
    assert any("vintage" in warning for warning in result["warnings"])


@pytest.mark.parametrize("as_of", ["", "2026-2-3", "not-a-date", True, float("nan")])
def test_only_none_defaults_as_of_and_bad_dates_cleanly_abstain(as_of):
    import json

    result = analyze(snapshot(), as_of)
    assert result["recommendation"]["action"] == "ABSTAIN"
    assert any("as_of" in error for error in result["validation_errors"])
    assert result["metrics"]["fundamental"] == {}
    assert result["recommendation"]["evidence_coverage"] == 0
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize("count", [1, 14, 20, 21, 22, 50, 200, 252, 253])
def test_indicator_minimum_windows_are_explicit_and_short_history_cannot_recommend(count):
    data = snapshot(count=count)
    data["fundamentals"] = fundamentals()
    result = analyze(data)
    metrics = result["metrics"]["technical"]
    assert (metrics["sma20"] is not None) == (count >= 20)
    assert (metrics["rsi14"] is not None) == (count >= 15)
    assert (metrics["atr14"] is not None) == (count >= 15)
    assert (metrics["vol20"] is not None) == (count >= 21)
    assert (metrics["return21"] is not None) == (count >= 22)
    assert (metrics["momentum12_1"] is not None) == (count >= 253)
    if count < 253:
        assert result["recommendation"]["action"] == "ABSTAIN"
        assert result["recommendation"]["score"] == 0
        assert result["confidence"]["label"] != "high_evidence_coverage"


@pytest.mark.parametrize("component", ["prices", "fundamentals", "benchmark"])
def test_extreme_numeric_inputs_never_raise_or_emit_nonfinite_json(component):
    import json

    data = snapshot(asset_type="etf" if component == "benchmark" else "stock")
    if component == "prices":
        for field in ("open", "high", "low", "close"):
            data["bars"][0][field] = 5e-324
    elif component == "fundamentals":
        data["fundamentals"] = {**fundamentals(), "market_cap": 5e-324}
    else:
        data["etf"] = {**etf_metadata(), "benchmark_returns": [
            {"date": bar["date"], "return": -.999999} for bar in data["bars"][1:]]}
    result = analyze(data)
    assert result["recommendation"]["action"] == "ABSTAIN"
    assert result["validation_errors"]
    json.dumps(result, allow_nan=False)


def test_wilder_rsi_uses_seed_then_recursive_smoothing_not_a_rolling_mean():
    data = snapshot(count=17)
    closes = list(range(100, 115)) + [113, 110]
    for bar, close in zip(data["bars"], closes):
        bar.update(open=close, high=close + 2, low=close - 2, close=close)
    metrics = analyze(data)["metrics"]["technical"]
    assert metrics["rsi14"] == pytest.approx(100 * 169 / 224)
    assert metrics["atr14"] == pytest.approx((4 * 13 + 5) / 14)


def test_flat_series_has_neutral_rsi_zero_vol_and_drawdown_tracks_prior_peaks():
    data = snapshot()
    for bar in data["bars"]:
        bar.update(open=100, high=102, low=98, close=100)
    metrics = analyze(data)["metrics"]["technical"]
    assert metrics["rsi14"] == 50
    assert metrics["vol20"] == 0
    assert metrics["max_drawdown"] == 0
    for bar in data["bars"][-3:]:
        bar.update(open=75, high=77, low=73, close=75)
    metrics = analyze(data)["metrics"]["technical"]
    assert metrics["max_drawdown"] == -.25
    assert metrics["rsi14"] == 0


def test_partial_etf_evidence_caps_recommendation_not_diagnostic_score():
    data = snapshot(asset_type="etf")
    data["etf"] = etf_metadata()
    data["etf"]["nav_date"] = "2026-11-06"
    result = analyze(data)
    assert result["recommendation"]["action"] == "WATCHLIST"
    assert result["recommendation"]["score"] <= 69
    assert result["recommendation"]["diagnostic_score"] == 88


@pytest.mark.parametrize("bad", [None, [], {"source": float("nan"), "symbol": object()}])
def test_invalid_input_is_safe_to_serialize_and_exposes_all_integration_keys(bad):
    import json

    result = analyze(bad)
    for field in ("symbol", "asset_type", "currency", "as_of", "recommendation", "metrics"):
        assert field in result
    assert result["metrics"]["fundamental"] == {}
    json.dumps(result, allow_nan=False)


def test_unfavorable_stock_has_auditable_bearish_not_a_buy_signal():
    data = snapshot()
    for i, bar in enumerate(data["bars"]):
        close = 500 - i
        bar.update(open=close, high=close + 2, low=close - 2, close=close)
    data["fundamentals"] = {**fundamentals(), "net_income": -150,
        "operating_income": -200, "operating_cash_flow": -180,
        "revenue": 700, "total_debt": 1900}
    result = analyze(data)
    assert result["recommendation"]["action"] == "AVOID_OR_WAIT"
    assert result["strategies"]["trend_following"]["bearish_reasons"]
    assert result["strategies"]["value_quality"]["bearish_reasons"]
    assert result["metrics"]["fundamental"]["earnings_yield"] < 0


def test_missing_market_cap_cannot_make_value_quality_a_candidate():
    data = snapshot()
    data["fundamentals"] = fundamentals()
    del data["fundamentals"]["market_cap"]
    result = analyze(data)
    assert result["strategies"]["value_quality"]["action"] != "RESEARCH_CANDIDATE"
    assert result["recommendation"]["action"] != "RESEARCH_CANDIDATE"
    assert "fundamentals.market_cap" in result["missing_data"]


def test_default_analysis_date_is_current_utc_and_preserves_core_alias():
    from datetime import datetime, timezone

    result = analyze(snapshot(), None)
    assert result["as_of"] == datetime.now(timezone.utc).date().isoformat()
    assert result["metrics"]["fundamental"] == result["metrics"]["fundamentals"]


@pytest.mark.parametrize("start,verified", [("2025-01-01", True), ("2025-10-01", False)])
def test_optional_period_start_can_verify_annual_duration_without_inventing_ttm(start, verified):
    data = snapshot()
    data["fundamentals"] = {**fundamentals(), "period_start": start}
    result = analyze(data)
    coverage = result["coverage"]["fundamentals"]
    assert coverage["annual_duration_verified"] is verified
    assert coverage["period_start"] == start
    assert coverage["period_duration_days"] == (date(2025, 12, 31) - date.fromisoformat(start)).days + 1
    assert coverage["period_basis"] == "as_reported_not_ttm_not_annualized"
    assert not result["validation_errors"]


@pytest.mark.parametrize("start", ["2026-01-01", "not-a-date", True])
def test_optional_period_start_must_be_a_date_no_later_than_period_end(start):
    data = snapshot()
    data["fundamentals"] = {**fundamentals(), "period_start": start}
    result = analyze(data)
    assert result["recommendation"]["action"] == "ABSTAIN"
    assert any("period_start" in error for error in result["validation_errors"])
