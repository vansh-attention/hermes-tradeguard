"""The documented public batch API delegates to the offline batch engine."""
import sys
from types import ModuleType


def test_public_batch_api_keeps_exact_requested_inputs_and_provider(monkeypatch):
    from tradeguard.derivatives import recommend_derivatives

    module = ModuleType("tradeguard.derivative_batches")
    calls = []
    expected = {"success": True, "research_only": True, "marker": "offline-batch"}

    def execute(requests, **kwargs):
        calls.append((requests, kwargs))
        return expected

    setattr(module, "recommend_derivatives", execute)
    monkeypatch.setitem(sys.modules, module.__name__, module)
    provider = object()
    requests = ["test:index", "TEST:INDEX"]
    supplemental = {"TEST:INDEX": {}}
    result = recommend_derivatives(requests, kind="options", provider=provider,
                                  supplemental_by_root=supplemental,
                                  as_of="2026-11-10T08:00:00Z")
    assert result is expected
    assert calls == [(requests, {"kind": "options", "provider": provider,
                                "supplemental_by_root": supplemental,
                                "as_of": "2026-11-10T08:00:00Z"})]
