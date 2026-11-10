"""Provider regressions: fixtures are synthetic, not external market results."""
from copy import deepcopy
from datetime import datetime, timezone
from unittest.mock import patch
import json

import pytest


def chart_fixture():
    return {"chart": {"error": None, "result": [{
        "meta": {"symbol": "AAPL", "currency": "USD", "instrumentType": "EQUITY",
                 "exchangeTimezoneName": "America/New_York", "dataGranularity": "1d"},
        "timestamp": [1793975400],
        "indicators": {"quote": [{"open": [100], "high": [102], "low": [99],
                                   "close": [101], "volume": [1000]}]},
    }]}}


@pytest.mark.parametrize("mutation", ["chart", "row", "meta", "indicators", "granularity", "missing_granularity"])
def test_provider_types_and_daily_frequency_are_enforced(mutation):
    from tradeguard.providers import parse_yahoo_chart
    payload = chart_fixture()
    if mutation == "chart":
        payload["chart"] = []
    elif mutation == "row":
        payload["chart"]["result"] = [None]
    elif mutation == "meta":
        payload["chart"]["result"][0]["meta"] = None
    elif mutation == "indicators":
        payload["chart"]["result"][0]["indicators"] = []
    elif mutation == "granularity":
        payload["chart"]["result"][0]["meta"]["dataGranularity"] = "1wk"
    else:
        del payload["chart"]["result"][0]["meta"]["dataGranularity"]
    with pytest.raises(ValueError, match="schema|granularity|daily"):
        parse_yahoo_chart(payload, "AAPL", datetime(2026, 11, 10, 8, tzinfo=timezone.utc))


def test_provider_schema_failure_is_structured_at_cli(capsys):
    from tradeguard.__main__ import main
    with patch("tradeguard.providers._get_json", return_value={"chart": []}):
        assert main(["analyze", "--symbol", "AAPL", "--allow-public-data"]) == 2
    assert json.loads(capsys.readouterr().out)["success"] is False


def sec_fixture():
    row = {"val": 100, "start": "2025-01-01", "end": "2025-12-31", "filed": "2026-02-01",
           "form": "10-K", "accn": "0000789019-26-000001"}
    return {"cik": 789019, "entityName": "MICROSOFT CORPORATION", "facts": {
        "us-gaap": {"Revenues": {"units": {"USD": [row]}}}}}


@pytest.mark.parametrize("cik", [320193, None, "789019", True, 789019.0])
def test_sec_payload_must_bind_numeric_issuer_identity(cik):
    from tradeguard.providers import normalize_sec_annual
    payload = sec_fixture()
    if cik is None:
        del payload["cik"]
    else:
        payload["cik"] = cik
    with pytest.raises(ValueError, match="issuer|CIK|cik"):
        normalize_sec_annual(payload, "2026-11-10", "0000789019")


def test_sec_matching_numeric_payload_does_not_repair_malformed_caller_cik():
    from tradeguard.providers import normalize_sec_annual
    payload = sec_fixture()
    before = deepcopy(payload)
    result = normalize_sec_annual(payload, "2026-11-10", "0000789019")
    assert result["revenue"] == 100
    assert result["issuer_cik"] == "0000789019"
    assert payload == before
    with pytest.raises(ValueError, match="ten digits"):
        normalize_sec_annual(payload, "2026-11-10", "789019")
