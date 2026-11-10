"""Adversarial recommendation tests use synthetic fixtures, not trading evidence."""
from copy import deepcopy

import pytest

from test_equity import snapshot, fundamentals, etf_metadata, analyze


def eligible_stock():
    data = snapshot()
    data["fundamentals"] = {
        **fundamentals(), "symbol": data["symbol"], "period_start": "2025-01-01",
        "market_cap_as_of": data["bars"][-1]["date"],
    }
    return data


def test_dated_annual_symbol_bound_statement_can_be_research_candidate():
    result = analyze(eligible_stock())
    assert result["recommendation"]["action"] == "RESEARCH_CANDIDATE"
    assert result["recommendation"]["validation_status"] == "heuristic_only_not_performance_validated"
    assert result["recommendation"]["strong_recommendation_eligible"] is False


@pytest.mark.parametrize("problem", ["quarterly", "missing_period", "missing_symbol", "missing_cap_clock", "stale_cap"])
def test_attractive_ratios_do_not_override_statement_or_valuation_provenance(problem):
    data = eligible_stock()
    f = data["fundamentals"]
    if problem == "quarterly":
        f["period_start"] = "2025-10-01"
    elif problem == "missing_period":
        del f["period_start"]
    elif problem == "missing_symbol":
        del f["symbol"]
    elif problem == "missing_cap_clock":
        del f["market_cap_as_of"]
    else:
        f["market_cap_as_of"] = "2025-12-31"
    before = deepcopy(data)
    result = analyze(data)
    assert result["recommendation"]["action"] != "RESEARCH_CANDIDATE"
    assert result["recommendation"]["score"] <= 69
    assert result["recommendation"]["evidence_limitations"]
    assert result["strategies"]["value_quality"]["action"] != "RESEARCH_CANDIDATE"
    assert result["recommendation"]["strong_recommendation_eligible"] is False
    assert data == before


@pytest.mark.parametrize("value", ["2026-11-10", "2026-2-3", True, None])
def test_explicit_invalid_market_cap_clock_cannot_be_used(value):
    data = eligible_stock()
    data["fundamentals"]["market_cap_as_of"] = value
    result = analyze(data)
    assert result["recommendation"]["action"] == "ABSTAIN"
    assert any("market_cap_as_of" in e for e in result["validation_errors"])


def test_partial_etf_disclosure_overrides_near_complete_weight_sum():
    data = snapshot(asset_type="etf")
    data["etf"] = {**etf_metadata(), "symbol": "SYNTH", "currency": "USD", "holdings_complete": False}
    result = analyze(data)
    assert result["metrics"]["etf"]["hhi"] is None
    assert result["metrics"]["etf"]["top10_weight"] is None
    assert result["recommendation"]["action"] != "RESEARCH_CANDIDATE"


def test_etf_metadata_is_bound_to_symbol_currency_before_top_label():
    data = snapshot(asset_type="etf")
    data["etf"] = etf_metadata()
    result = analyze(data)
    assert result["recommendation"]["action"] != "RESEARCH_CANDIDATE"
    assert result["recommendation"]["evidence_limitations"]


def test_failure_result_also_explicitly_refuses_strong_recommendation():
    result = analyze({})
    assert result["recommendation"]["strong_recommendation_eligible"] is False
    assert result["recommendation"]["validation_status"] == "heuristic_only_not_performance_validated"
