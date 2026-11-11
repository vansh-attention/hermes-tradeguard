"""Offline derivatives CLI/table contract; no authorized provider exists in M1."""
import io
import json

import pytest


def test_derivative_table_labels_fixture_and_na_without_terminal_controls():
    from tradeguard.derivative_ui import render_derivative_results
    result = {
        "success": True, "data_mode": "fixture", "strategy": "long_call",
        "contract": {"contract_id": "TEST:CALL\x1b[31m\nINJECT", "currency": "USD", "expiry_at": "2026-12-18T14:30:00Z"},
        "recommendation": {"score": None, "verdict": "ABSTAIN", "scope": "long_call", "directional_support": 1.0},
        "metrics": {"option": {"gross_max_loss": "30", "pricing": {"status": "unavailable"}}},
        "blockers": ["OFFLINE_PROVENANCE_UNVERIFIED"], "missing_data": ["rates"],
        "warnings": ["SOURCE\rCONTROL"], "as_of": "2026-11-10T08:00:00Z",
    }
    text = render_derivative_results(result)
    assert "SYNTHETIC" in text and "NOT LIVE" in text
    assert "N/A" in text and "ABSTAIN" in text
    assert "probabilit" in text.lower()
    assert "\x1b" not in text and "\r" not in text
    assert "\nINJECT" not in text
    assert "30 USD" in text


def test_derivative_snapshot_cli_has_no_network_or_credential_path(monkeypatch, capsys, tmp_path):
    from derivative_cases import snapshot
    from tradeguard.__main__ import main
    import socket
    import urllib.request
    path = tmp_path / "future.json"
    path.write_text(json.dumps(snapshot()))
    def forbidden(*args, **kwargs):
        raise AssertionError("offline derivative analysis attempted network access")
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(urllib.request, "urlopen", forbidden)
    assert main(["derivatives", "--snapshot", str(path), "--as-of", "2026-11-10T08:00:00Z", "--json"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["data_mode"] == "fixture"
    assert result["recommendation"]["score"] is None
    assert result["metrics"]["futures"]["maximum_loss"] is None


def test_derivative_cli_vertical_and_native_share_the_engine(capsys, tmp_path):
    from test_derivatives import _vertical
    from test_plugin import FakeContext, load_plugin
    from tradeguard.__main__ import main
    long, short = _vertical()
    lp, sp = tmp_path / "long.json", tmp_path / "short.json"
    lp.write_text(json.dumps(long))
    sp.write_text(json.dumps(short))
    assert main(["derivatives", "--snapshot", str(lp), "--short-leg", str(sp), "--as-of", "2026-11-10T08:00:00Z", "--json"]) == 0
    actual = json.loads(capsys.readouterr().out)
    ctx = FakeContext()
    load_plugin().register(ctx)
    native = json.loads(ctx.tools["tradeguard_derivatives_research"]({"snapshot": long, "short_leg": short, "as_of": "2026-11-10T08:00:00Z"}))
    assert actual == native
    assert actual["strategy"] == "bull_call_debit"


def test_explicit_invalid_short_leg_never_falls_back_to_single(capsys, tmp_path):
    from derivative_cases import snapshot
    from tradeguard.__main__ import main
    lp, sp = tmp_path / "long.json", tmp_path / "bad.json"
    lp.write_text(json.dumps(snapshot(kind="option")))
    sp.write_text("null")
    assert main(["derivatives", "--snapshot", str(lp), "--short-leg", str(sp), "--json"]) == 2
    assert json.loads(capsys.readouterr().out)["success"] is False


@pytest.mark.parametrize("consent", [[], ["--allow-derivatives-data"]])
def test_m1_root_cli_reports_unavailable_even_with_consent(consent, monkeypatch, capsys):
    from tradeguard.__main__ import main
    import socket
    def forbidden(*args, **kwargs):
        raise AssertionError("M1 root request cannot fetch anything")
    monkeypatch.setattr(socket, "create_connection", forbidden)
    assert main(["derivatives", "NFO:NIFTY", "--kind", "options", "--json"] + consent) == 1
    result = json.loads(capsys.readouterr().out)
    assert result["code"] == "DERIVATIVES_PROVIDER_NOT_IMPLEMENTED"
    assert result["roots"] == ["NFO:NIFTY"]


@pytest.mark.parametrize("roots", [[], ["NIFTY"], ["NFO:NIFTY;id"], ["NFO:NIFTY"] * 4])
def test_root_input_errors_are_structured(capsys, roots):
    from tradeguard.__main__ import main
    assert main(["derivatives", "--json"] + roots) == 2
    assert json.loads(capsys.readouterr().out)["success"] is False


def test_derivative_prompt_keeps_json_lines_and_unavailable_status(monkeypatch, capsys):
    from tradeguard.__main__ import main
    monkeypatch.setattr("sys.stdin", io.StringIO("NFO:NIFTY;bad\nNFO:NIFTY\nquit\n"))
    assert main(["derivatives", "--interactive", "--kind", "options", "--json"]) == 0
    out = capsys.readouterr()
    rows = [json.loads(line) for line in out.out.splitlines()]
    assert len(rows) == 2
    assert rows[0]["success"] is False
    assert rows[1]["code"] == "DERIVATIVES_PROVIDER_NOT_IMPLEMENTED"
    assert "Derivatives>" in out.err
    assert "NOT LIVE" in out.err


@pytest.mark.parametrize("cancel", [False, True])
def test_derivative_prompt_eof_and_cancel(monkeypatch, capsys, cancel):
    from tradeguard.__main__ import main
    class Input:
        def readline(self):
            if cancel:
                raise KeyboardInterrupt
            return ""
    monkeypatch.setattr("sys.stdin", Input())
    assert main(["derivatives", "--interactive", "--json"]) == (130 if cancel else 0)
    assert capsys.readouterr().out == ""


def test_derivative_error_renderer_is_structured_and_safe():
    from tradeguard.derivative_ui import render_derivative_results
    text = render_derivative_results({"success": False, "code": "UNAVAILABLE", "error": "bad\nnew\x1b[2J"})
    assert "UNAVAILABLE" in text
    assert "\x1b" not in text and "\nnew" not in text
