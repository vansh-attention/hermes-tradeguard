"""Ticker-only orchestration uses synthetic transport fixtures in unit tests."""
from copy import deepcopy
import json

import pytest

from test_equity import snapshot, fundamentals


def history(symbol):
    data = snapshot(asset_type="etf" if symbol == "SPY" else "stock")
    data["symbol"] = symbol
    return data


def test_ticker_ui_accepts_declared_case_insensitive_syntax_preserving_inputs():
    from tradeguard.tickers import parse_tickers
    parsed = parse_tickers("msft, AAPL MSFT")
    assert parsed["requested"] == ["msft", "AAPL", "MSFT"]
    assert parsed["symbols"] == ["MSFT", "AAPL"]
    assert parse_tickers(["SPY", "qqq"])["symbols"] == ["SPY", "QQQ"]
    assert parse_tickers("BRK-B")["symbols"] == ["BRK-B"]


@pytest.mark.parametrize("value", [None, True, [], "", "MSFT https://bad", "MSFT;rm", "AAPL?x=1", "../MSFT", ["AAPL", 1], "A" * 16, ["AAPL"] * 11, "ſPY", "ＭSFT", "$MSFT", ["MSFT AAPL"]])
def test_bad_or_excessive_input_fails_before_any_network(value):
    from tradeguard.tickers import recommend_tickers
    calls = []
    with pytest.raises(ValueError):
        recommend_tickers(value, allow_public_data=True, fetcher=lambda symbol: calls.append(symbol))
    assert calls == []


def test_network_requires_literal_boolean_opt_in():
    from tradeguard.tickers import recommend_tickers
    calls = []
    for flag in (False, "true", 1, None):
        with pytest.raises(ValueError, match="disabled|opt.in|allow_public_data"):
            recommend_tickers("MSFT", allow_public_data=flag, fetcher=lambda s: calls.append(s))
    assert calls == []


def test_tickers_only_returns_compact_technical_score_not_fake_fundamentals():
    from tradeguard.tickers import recommend_tickers
    result = recommend_tickers("MSFT AAPL SPY", allow_public_data=True, fetcher=history, as_of="2026-11-09")
    assert [r["symbol"] for r in result["results"]] == ["MSFT", "AAPL", "SPY"]
    assert result["count"] == result["succeeded"] == 3
    assert result["failed"] == 0
    assert result["success"] is True
    assert len(json.dumps(result)) < 24000
    for row in result["results"]:
        assert row["status"] == "ok"
        assert "bars" not in row
        assert 0 <= row["technical_recommendation"]["score"] <= 1
        assert row["technical_recommendation"]["scope"] == "technical_only"
        assert row["technical_recommendation"]["horizon"] == "technical_swing_weeks_to_months"
        assert row["combined_recommendation"]["score"] is None
        assert row["metadata_status"] == "not_supplied"
        assert row["buy_recommendation"]["scope"] == "technical_only"
        assert row["buy_recommendation"]["strong_buy"] is False
        assert "fundamental" in row["buy_recommendation"]["conclusion"].lower() or "valuation" in row["buy_recommendation"]["conclusion"].lower()


def test_optional_metadata_is_explicit_bound_and_not_mutated():
    from tradeguard.tickers import recommend_tickers
    meta = {"MSFT": {**fundamentals(), "symbol": "MSFT", "period_start": "2025-01-01", "market_cap_as_of": "2026-11-09"}}
    before = deepcopy(meta)
    result = recommend_tickers("MSFT", allow_public_data=True, fetcher=history,
                               fundamentals_by_symbol=meta, as_of="2026-11-09")
    row = result["results"][0]
    assert row["metadata_status"] == "supplied_unverified"
    assert row["combined_recommendation"]["score"] == 1.0
    assert row["buy_recommendation"]["scope"] == "combined"
    assert meta == before


@pytest.mark.parametrize("metadata", [{"AAPL": {"symbol": "AAPL"}}, {"MSFT": {"symbol": "OTHER"}}, {"MSFT": []}])
def test_metadata_identity_errors_fail_before_fetch(metadata):
    from tradeguard.tickers import recommend_tickers
    calls = []
    with pytest.raises(ValueError):
        recommend_tickers("MSFT", allow_public_data=True, fetcher=lambda s: calls.append(s), fundamentals_by_symbol=metadata)
    assert calls == []


@pytest.mark.parametrize("problem", ["stale", "fixture", "sparse", "wrong_symbol"])
def test_ticker_shortcut_does_not_rescue_unusable_market_data(problem):
    from tradeguard.tickers import recommend_tickers
    def bad(symbol):
        data = history(symbol)
        if problem == "fixture":
            data["data_mode"] = "fixture"
        elif problem == "sparse":
            data["bars"] = data["bars"][::5]
        elif problem == "wrong_symbol":
            data["symbol"] = "OTHER"
        return data
    result = recommend_tickers("MSFT", allow_public_data=True, fetcher=bad,
                               as_of="2026-12-01" if problem == "stale" else "2026-11-09")
    row = result["results"][0]
    assert row["buy_recommendation"]["score"] is None
    assert row["combined_recommendation"]["score"] is None


def test_provider_failure_is_per_symbol_and_counts_and_order_are_exact():
    from tradeguard.tickers import recommend_tickers
    def fetch(symbol):
        if symbol == "BAD":
            raise ValueError("provider HTTP 404; no fallback data invented")
        return history(symbol)
    result = recommend_tickers("MSFT BAD SPY MSFT", allow_public_data=True, fetcher=fetch, as_of="2026-11-09")
    assert result["input_count"] == 4
    assert result["count"] == 3
    assert result["succeeded"] == 2
    assert result["failed"] == 1
    assert [r["symbol"] for r in result["results"]] == ["MSFT", "BAD", "SPY"]
    assert result["results"][1]["status"] == "unavailable"
    assert result["results"][1]["buy_recommendation"]["score"] is None
    assert result["results"][0]["requested_as"] == ["MSFT", "MSFT"]


def test_all_failed_fetches_never_report_success():
    from tradeguard.tickers import recommend_tickers
    def failed(symbol):
        raise ValueError("HTTP 429")
    result = recommend_tickers("MSFT SPY", allow_public_data=True, fetcher=failed)
    assert result["success"] is False
    assert result["succeeded"] == 0
    assert result["failed"] == result["count"] == 2


def test_invalid_supplied_fundamentals_do_not_fall_back_to_a_buy_score():
    from tradeguard.tickers import recommend_tickers
    meta = {"MSFT": {**fundamentals(), "symbol": "MSFT", "filed_at": "2027-01-01"}}
    row = recommend_tickers("MSFT", allow_public_data=True, fetcher=history,
                            fundamentals_by_symbol=meta, as_of="2026-11-09")["results"][0]
    assert row["technical_recommendation"]["score"] is not None
    assert row["technical_metrics"]["sma200"] is not None
    assert row["combined_recommendation"]["score"] is None
    assert row["buy_recommendation"]["score"] is None
    assert row["buy_recommendation"]["scope"] == "combined"
    assert row["validation_errors"]


def test_short_history_cannot_expose_an_abstained_raw_trend_score():
    from tradeguard.tickers import recommend_tickers
    def short(symbol):
        data = history(symbol)
        data["bars"] = data["bars"][-252:]
        return data
    row = recommend_tickers("MSFT", allow_public_data=True, fetcher=short,
                            as_of="2026-11-09")["results"][0]
    assert row["technical_recommendation"]["score"] is None
    assert row["buy_recommendation"]["score"] is None


def test_stale_explicit_metadata_cannot_select_a_better_technical_buy():
    from tradeguard.tickers import recommend_tickers
    meta = {"MSFT": {**fundamentals(), "symbol": "MSFT", "period_end": "2024-01-01", "filed_at": "2024-02-01"}}
    row = recommend_tickers("MSFT", allow_public_data=True, fetcher=history,
                            fundamentals_by_symbol=meta, as_of="2026-11-09")["results"][0]
    assert row["buy_recommendation"]["scope"] == "combined"
    assert row["buy_recommendation"]["score"] is None
    assert any("Stale" in c for c in row["buy_recommendation"]["cautions"])
