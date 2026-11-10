"""Buy-interest formatting must never bypass evidence gates or imply calibration."""
from copy import deepcopy
import json
import subprocess
import sys

import pytest

from test_equity import analyze, snapshot
from test_evidence_gates import eligible_stock
from test_plugin import FakeContext, load_plugin


def test_candidate_buy_interest_is_normalized_not_a_probability():
    data = eligible_stock()
    before = deepcopy(data)
    result = analyze(data)
    buying = result["buy_recommendation"]
    assert buying["score"] == 1.0
    assert buying["verdict"] == "BUY_RESEARCH_CANDIDATE"
    assert buying["score_type"] == "uncalibrated_buy_interest_not_profit_probability"
    assert buying["strong_buy"] is False
    assert buying["conclusion"]
    assert list(result)[-1] == "buy_recommendation"
    assert data == before


def test_constructive_watchlist_uses_capped_not_optimistically_inflated_score():
    data = eligible_stock()
    del data["fundamentals"]["market_cap_as_of"]
    result = analyze(data)
    assert result["recommendation"]["diagnostic_score"] == 100
    assert result["recommendation"]["score"] == 69
    buying = result["buy_recommendation"]
    assert buying["score"] == .69
    assert buying["verdict"] == "CONSTRUCTIVE_WATCHLIST"
    assert buying["cautions"]
    assert buying["strong_buy"] is False


@pytest.mark.parametrize("problem", ["invalid", "fixture", "short", "stale", "future", "missing_fundamentals"])
def test_abstention_has_null_buy_interest_not_false_zero_or_positive(problem):
    data, as_of = eligible_stock(), "2026-11-09"
    if problem == "invalid":
        data = {}
    elif problem == "fixture":
        data["data_mode"] = "fixture"
    elif problem == "short":
        data["bars"] = data["bars"][-20:]
    elif problem == "stale":
        as_of = "2026-12-01"
    elif problem == "future":
        data["fundamentals"]["filed_at"] = "2027-01-01"
    else:
        del data["fundamentals"]
    result = analyze(data, as_of)
    assert result["recommendation"]["action"] == "ABSTAIN"
    assert result["buy_recommendation"]["score"] is None
    assert result["buy_recommendation"]["verdict"] == "ABSTAIN"
    assert result["buy_recommendation"]["strong_buy"] is False
    json.dumps(result, allow_nan=False)


def test_weak_evidence_is_not_relabelled_as_optimistic_buy():
    data = eligible_stock()
    for i, bar in enumerate(data["bars"]):
        close = 500 - i
        bar.update(open=close, high=close + 2, low=close - 2, close=close)
    data["fundamentals"].update(net_income=-150, operating_income=-200,
                                operating_cash_flow=-180, revenue=700, total_debt=1900)
    result = analyze(data)
    assert result["recommendation"]["action"] == "AVOID_OR_WAIT"
    assert 0 <= result["buy_recommendation"]["score"] < .45
    assert result["buy_recommendation"]["verdict"] == "WAIT_FOR_BETTER_SETUP"


def test_same_buy_conclusion_is_last_in_actual_cli_and_registered_handler(tmp_path):
    data = eligible_stock()
    path = tmp_path / "input.json"
    path.write_text(json.dumps(data))
    completed = subprocess.run([sys.executable, "-m", "tradeguard", "analyze", "--snapshot", str(path),
                                "--as-of", "2026-11-09"], capture_output=True, text=True, timeout=15)
    assert completed.returncode == 0
    command = json.loads(completed.stdout)
    context = FakeContext()
    load_plugin().register(context)
    native = json.loads(context.tools["tradeguard_equity_research"]({"snapshot": data, "as_of": "2026-11-09"}))
    assert command == native
    assert list(command)[-1] == "buy_recommendation"
    assert command["buy_recommendation"]["score"] == 1.0
