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


def test_derivative_error_renderer_is_structured_and_safe():
    from tradeguard.derivative_ui import render_derivative_results
    text = render_derivative_results({"success": False, "code": "UNAVAILABLE", "error": "bad\nnew\x1b[2J"})
    assert "UNAVAILABLE" in text
    assert "\x1b" not in text and "\nnew" not in text
