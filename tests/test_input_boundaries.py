"""Malformed/weekly input must not masquerade as daily usable evidence."""
import json
import subprocess
import sys
from datetime import date, timedelta

import pytest

from test_equity import snapshot, analyze, etf_metadata


def test_weekly_equity_history_cannot_emit_daily_annualized_volatility():
    data = snapshot()
    end = date(2026, 11, 9)
    for i, bar in enumerate(reversed(data["bars"])):
        bar["date"] = (end - timedelta(days=7 * i)).isoformat()
    result = analyze(data)
    assert result["recommendation"]["action"] == "ABSTAIN"
    assert result["validation_errors"]
    assert result["metrics"]["technical"].get("vol20") is None


def test_explicit_holdings_completeness_is_not_a_truthy_string():
    data = snapshot(asset_type="etf")
    data["etf"] = {**etf_metadata(), "holdings_complete": "false"}
    result = analyze(data)
    assert any("holdings_complete" in x for x in result["validation_errors"])


@pytest.mark.parametrize("mode", ["live", "delayed", "historical"])
def test_retrieval_day_candle_without_session_finalization_is_invalid(mode):
    data = snapshot(mode=mode)
    data.pop("session_close_at", None)
    result = analyze(data)
    assert result["recommendation"]["action"] == "ABSTAIN"
    assert any("session" in x for x in result["validation_errors"])


def test_session_close_clock_must_not_exceed_retrieval_and_must_match_last_date():
    data = snapshot(mode="live")
    data.update(exchange_timezone="America/New_York", session_close_at="2026-11-09T21:00:00Z",
                retrieved_at="2026-11-09T15:00:00Z")
    result = analyze(data)
    assert any("session" in x for x in result["validation_errors"])
    data["retrieved_at"] = "2026-11-09T22:00:00Z"
    result = analyze(data)
    assert not result["validation_errors"]
    data["session_close_at"] = "2026-11-06T21:00:00Z"
    assert any("session" in x for x in analyze(data)["validation_errors"])


@pytest.mark.parametrize("command,body", [("walk-forward", []), ("microstructure", []), ("microstructure", {"quote": {}, "events": []})])
def test_cli_rejects_malformed_shapes_without_traceback(tmp_path, command, body):
    path = tmp_path / "input.json"
    path.write_text(json.dumps(body))
    flag = "--snapshot" if command == "walk-forward" else "--input"
    result = subprocess.run([sys.executable, "-m", "tradeguard", command, flag, str(path)],
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 2
    assert json.loads(result.stdout)["success"] is False
    assert "Traceback" not in result.stderr


def test_cli_rejects_non_object_snapshot_with_attached_metadata(tmp_path):
    path, meta = tmp_path / "input.json", tmp_path / "meta.json"
    path.write_text("[]")
    meta.write_text('{"symbol":"MSFT"}')
    result = subprocess.run([sys.executable, "-m", "tradeguard", "analyze", "--snapshot", str(path),
                             "--fundamentals", str(meta)], capture_output=True, text=True, timeout=10)
    assert result.returncode == 2
    assert json.loads(result.stdout)["success"] is False
    assert "Traceback" not in result.stderr
