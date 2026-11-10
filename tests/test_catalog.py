"""Offline research-family directory; status is capability, never profitability."""
import pytest


def test_catalog_separates_screen_features_experiment_and_unimplemented():
    from tradeguard.catalog import strategy_catalog
    result = strategy_catalog()
    assert result["exhaustive"] is False
    rows = result["strategies"]
    assert result["count"] == len(rows)
    assert len({x["id"] for x in rows}) == len(rows)
    assert len(rows) >= 18
    assert all(x["performance_validated"] is False for x in rows)
    assert all(x["source_ids"] and x["required_data"] and x["failure_modes"] for x in rows)
    by_id = {x["id"]: x for x in rows}
    assert by_id["value_quality"]["implementation_status"] == "heuristic_screen"
    assert by_id["market_making"]["implementation_status"] == "researched_only"
    assert by_id["technical_ridge"]["implementation_status"] == "experimental_baseline"


def test_catalog_filter_and_resource_contract():
    from tradeguard.catalog import strategy_catalog
    etfs = strategy_catalog(asset_type="etf")
    assert all("etf" in x["asset_types"] for x in etfs["strategies"])
    one = strategy_catalog(strategy_id="trend_following")
    assert one["count"] == 1
    one["strategies"][0]["source_ids"].clear()
    assert strategy_catalog(strategy_id="trend_following")["strategies"][0]["source_ids"]
    for kw in ({"strategy_id": "made_up"}, {"strategy_id": []}, {"asset_type": "future"}):
        with pytest.raises(ValueError):
            strategy_catalog(**kw)


def test_every_catalog_source_id_resolves_to_the_appropriate_ledger():
    import json
    from pathlib import Path
    from tradeguard.catalog import strategy_catalog
    root = Path(__file__).resolve().parents[1] / "docs" / "research"
    ids = {prefix: {str(x["id"]) for x in json.loads((root / file).read_text())["sources"]}
           for prefix, file in (("eq", "sources_equity.json"), ("micro", "sources_microstructure.json"))}
    for family in strategy_catalog()["strategies"]:
        for source_id in family["source_ids"]:
            prefix, number = source_id.split(":")
            assert number in ids[prefix], (family["id"], source_id)
