"""Actual native derivative handler, manifest, isolation and CLI parity."""
import json
from pathlib import Path
import socket
import subprocess
import urllib.request

from test_plugin import FakeContext, load_plugin

AS_OF = "2026-11-10T08:00:00Z"


def test_derivative_tool_registers_inertly_without_live_surface(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("offline native registration touched an external capability")
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(urllib.request, "urlopen", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(Path, "read_text", forbidden)
    monkeypatch.setattr(Path, "read_bytes", forbidden)
    ctx = FakeContext()
    load_plugin().register(ctx)
    assert "tradeguard_derivatives_research" in ctx.tools
    assert len(ctx.tools) == 8
    assert "tradeguard_recommend_derivatives" not in ctx.tools


def test_actual_derivative_handler_matches_pure_offline_analysis():
    from derivative_cases import snapshot
    from tradeguard.derivatives import analyze_derivative_request
    s = snapshot(kind="option")
    ctx = FakeContext()
    load_plugin().register(ctx)
    actual = json.loads(ctx.tools["tradeguard_derivatives_research"]({"snapshot": s, "as_of": AS_OF}))
    assert actual == analyze_derivative_request(s, as_of=AS_OF)
    assert actual["data_mode"] == "fixture"
    assert actual["recommendation"]["score"] is None
    assert actual["success"] is True


def test_native_derivative_bad_arguments_always_return_json():
    ctx = FakeContext()
    load_plugin().register(ctx)
    handler = ctx.tools["tradeguard_derivatives_research"]
    for arguments in (None, [], {}, {"snapshot": []}, {"snapshot": None}, {"snapshot": {}, "trusted_provider": True}):
        result = json.loads(handler(arguments))
        assert result["success"] is False
        assert result["research_only"] is True


def test_native_derivative_handler_cannot_assert_live_provenance():
    from derivative_cases import snapshot
    s = snapshot()
    s["source"]["data_mode"] = "provider"
    s["source"]["entitlement"] = "confirmed"
    ctx = FakeContext()
    load_plugin().register(ctx)
    result = json.loads(ctx.tools["tradeguard_derivatives_research"]({"snapshot": s, "as_of": AS_OF}))
    assert result["success"] is True
    assert result["source"]["entitlement"] == "unverified"
    assert result["recommendation"]["score"] is None
