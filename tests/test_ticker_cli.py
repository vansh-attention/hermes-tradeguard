"""Exercise ticker-only command, interactive input and native one-call handler."""
import importlib
import io
import json

import pytest

from test_tickers import history
from test_plugin import FakeContext, load_plugin


def test_ticker_command_defaults_to_human_table(monkeypatch, capsys):
    from tradeguard.__main__ import main
    monkeypatch.setattr("tradeguard.providers.fetch_public_snapshot", history)
    assert main(["recommend", "msft,AAPL", "SPY", "--allow-public-data", "--as-of", "2026-11-09"]) == 0
    text = capsys.readouterr().out
    assert all(symbol in text for symbol in ("MSFT", "AAPL", "SPY"))
    assert "Technical" in text and "Combined" in text
    assert "technical_only" in text
    assert "not" in text.lower() and "probabilit" in text.lower()


def test_ticker_command_json_stays_machine_readable(monkeypatch, capsys):
    from tradeguard.__main__ import main
    monkeypatch.setattr("tradeguard.providers.fetch_public_snapshot", history)
    assert main(["recommend", "MSFT", "--allow-public-data", "--json", "--as-of", "2026-11-09"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["count"] == 1
    assert result["results"][0]["buy_recommendation"]["scope"] == "technical_only"


def test_ticker_command_never_implicitly_enables_network(monkeypatch, capsys):
    from tradeguard.__main__ import main
    calls = []
    monkeypatch.setattr("tradeguard.providers.fetch_public_snapshot", lambda s: calls.append(s))
    assert main(["recommend", "MSFT"]) == 2
    assert calls == []
    assert json.loads(capsys.readouterr().out)["success"] is False


def test_interactive_session_takes_only_ticker_lines_and_exits(monkeypatch, capsys):
    from tradeguard.__main__ import main
    monkeypatch.setattr("tradeguard.providers.fetch_public_snapshot", history)
    monkeypatch.setattr("sys.stdin", io.StringIO("msft\n\nAAPL SPY\nquit\n"))
    assert main(["recommend", "--interactive", "--allow-public-data", "--json", "--as-of", "2026-11-09"]) == 0
    captured = capsys.readouterr()
    results = [json.loads(line) for line in captured.out.splitlines()]
    assert [r["symbols"] for r in results] == [["MSFT"], ["AAPL", "SPY"]]
    assert "Tickers>" in captured.err


def test_interactive_invalid_line_cannot_fetch_and_does_not_break_next_line(monkeypatch, capsys):
    from tradeguard.__main__ import main
    calls = []
    def fetch(symbol):
        calls.append(symbol)
        return history(symbol)
    monkeypatch.setattr("tradeguard.providers.fetch_public_snapshot", fetch)
    monkeypatch.setattr("sys.stdin", io.StringIO("MSFT;bad\nMSFT\nquit\n"))
    assert main(["recommend", "--interactive", "--allow-public-data", "--json", "--as-of", "2026-11-09"]) == 0
    results = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert results[0]["success"] is False
    assert results[1]["success"] is True
    assert calls == ["MSFT"]


def test_no_tickers_without_interactive_fails_cleanly(capsys):
    from tradeguard.__main__ import main
    assert main(["recommend", "--allow-public-data"]) == 2
    assert json.loads(capsys.readouterr().out)["success"] is False


def test_all_provider_failures_have_nonzero_cli_exit(monkeypatch, capsys):
    from tradeguard.__main__ import main
    def failed(symbol):
        raise ValueError("HTTP 429")
    monkeypatch.setattr("tradeguard.providers.fetch_public_snapshot", failed)
    assert main(["recommend", "MSFT", "--allow-public-data", "--json"]) == 1
    assert json.loads(capsys.readouterr().out)["success"] is False


def test_native_ticker_tool_disabled_by_default_and_accepts_one_call_when_enabled(monkeypatch):
    plugin = load_plugin()
    disabled = FakeContext()
    plugin.register(disabled)
    handler = disabled.tools["tradeguard_recommend_tickers"]
    assert json.loads(handler({"tickers": "MSFT"}))["code"] == "PUBLIC_DATA_DISABLED"
    class Enabled(FakeContext):
        def get_config(self, key, default=None):
            return True if key == "allow_public_data" else default
    enabled = Enabled()
    plugin.register(enabled)
    providers = importlib.import_module(plugin.__name__ + ".tradeguard.providers")
    monkeypatch.setattr(providers, "fetch_public_snapshot", history)
    result = json.loads(enabled.tools["tradeguard_recommend_tickers"]({"tickers": "MSFT AAPL", "as_of": "2026-11-09"}))
    assert result["success"] is True
    assert result["count"] == 2
    assert "bars" not in result["results"][0]
    assert result["results"][0]["combined_recommendation"]["score"] is None


@pytest.mark.parametrize("flag", [False, "false", 1])
def test_native_request_cannot_override_disabled_or_nonboolean_config(flag, monkeypatch):
    plugin = load_plugin()
    class Disabled(FakeContext):
        def get_config(self, key, default=None):
            return flag
    ctx = Disabled()
    plugin.register(ctx)
    calls = []
    providers = importlib.import_module(plugin.__name__ + ".tradeguard.providers")
    monkeypatch.setattr(providers, "fetch_public_snapshot", lambda s: calls.append(s))
    response = json.loads(ctx.tools["tradeguard_recommend_tickers"]({"tickers": "MSFT", "allow_public_data": True}))
    assert response["code"] == "PUBLIC_DATA_DISABLED"
    assert calls == []


@pytest.mark.parametrize("cancel", [False, True])
def test_prompt_eof_and_cancellation_do_not_fetch(cancel, monkeypatch, capsys):
    from tradeguard.__main__ import main
    class ClosedInput:
        def readline(self):
            if cancel:
                raise KeyboardInterrupt
            return ""
    calls = []
    monkeypatch.setattr("sys.stdin", ClosedInput())
    monkeypatch.setattr("tradeguard.providers.fetch_public_snapshot", lambda s: calls.append(s))
    assert main(["recommend", "--interactive", "--allow-public-data", "--json"]) == (130 if cancel else 0)
    assert calls == []
    assert capsys.readouterr().out == ""
