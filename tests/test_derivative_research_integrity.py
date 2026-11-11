"""Truthful, separately namespaced derivative research and release metadata."""
import json
from pathlib import Path
import re
import tomllib

ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / "docs/research"


def test_derivative_source_ledger_is_complete_and_honest_about_inspection():
    ledger = json.loads((RESEARCH / "sources_derivatives.json").read_text())
    rows = ledger["sources"]
    ids = [row["id"] for row in rows]
    assert len(ids) == len(set(ids)) == ledger["source_count"]
    assert set(ids) == {f"D{i}" for i in range(1, 13)}
    assert ledger["runtime_scope"] == "M1_offline_only"
    assert ledger["live_derivative_feeds"] == []
    assert ledger["performance_validated"] is False
    assert ledger["inspection_date"] == "2026-11-10"
    for row in rows:
        assert row["primary_source"] is True
        assert row["url"].startswith("https://")
        assert row["accessed_date"] == ledger["inspection_date"]
        assert row["inspection_status"] in {"direct_https", "indexed_primary_corroboration"}
        assert row["supports"]
        assert row["code_reused"] is False
    assert "prior" in ledger["inspection_note"].lower()


def test_every_derivative_citation_resolves_without_changing_equity_ledger():
    ledger = json.loads((RESEARCH / "sources_derivatives.json").read_text())
    body = (RESEARCH / "derivatives_strategy_library.md").read_text()
    citations = set(re.findall(r"\[(D[0-9]+)\]", body))
    assert citations == {row["id"] for row in ledger["sources"]}
    assert "performance-validated" in body and "No live derivative feed" in body
    equity = json.loads((RESEARCH / "sources_equity.json").read_text())
    assert all(type(row["id"]) is int for row in equity["sources"])


def test_derivatives_validation_protocol_does_not_claim_a_fitted_model():
    body = (RESEARCH / "derivatives_validation_protocol.md").read_text()
    for phrase in ("point-in-time", "untouched", "next tradable", "bid/ask", "margin", "NOT IMPLEMENTED"):
        assert phrase in body
    assert "equity ridge" in body


def test_package_and_plugin_versions_match_offline_m1_scope():
    package = tomllib.loads((ROOT / "pyproject.toml").read_text())
    manifest = (ROOT / "plugin.yaml").read_text()
    match = re.search(r'^version:\s*"([^"]+)"', manifest, re.M)
    assert match is not None
    version = match.group(1)
    from tradeguard import __version__
    assert version == package["project"]["version"] == __version__ == "0.2.0"
    assert "offline" in package["project"]["description"].lower()
    assert "derivative feeds unavailable" in manifest
    assert "provides_hooks: []" in manifest
    assert "requires_env: []" in manifest
