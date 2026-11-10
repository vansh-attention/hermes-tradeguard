"""Provider contracts use deliberately synthetic transport fixtures."""
from datetime import datetime, timezone

import pytest


def test_chart_parser_discards_in_progress_daily_candle():
    from tradeguard.providers import parse_yahoo_chart
    ts = [int(datetime(2026, 11, d, 14, 30, tzinfo=timezone.utc).timestamp()) for d in (6, 9)]
    payload = {"chart": {"result": [{"meta": {"symbol": "AAPL", "currency": "USD", "instrumentType": "EQUITY", "exchangeTimezoneName": "America/New_York", "dataGranularity": "1d"}, "timestamp": ts, "indicators": {"quote": [{"open": [100, 101], "high": [102, 103], "low": [99, 100], "close": [101, 102], "volume": [1000, 1200]}]}}], "error": None}}
    s = parse_yahoo_chart(payload, "AAPL", datetime(2026, 11, 9, 17, tzinfo=timezone.utc))
    assert s["bars"] == [{"date": "2026-11-06", "open": 100, "high": 102, "low": 99, "close": 101, "volume": 1000}]
    assert s["asset_type"] == "stock"
    assert s["data_mode"] == "historical"
    assert s["currency"] == "USD"
    assert "unofficial" in s["source"].lower()


def test_chart_wrong_symbol_rejected_before_any_analysis():
    from tradeguard.providers import parse_yahoo_chart
    payload = {"chart": {"result": [{"meta": {"symbol": "WRONG", "currency": "USD", "instrumentType": "EQUITY"}, "timestamp": [], "indicators": {"quote": [{}]}}]}}
    with pytest.raises(ValueError, match="symbol"):
        parse_yahoo_chart(payload, "AAPL", datetime.now(timezone.utc))


@pytest.mark.parametrize("symbol", ["aapl", "../AAPL", "https://bad", "AAPL?x=1", "", "A" * 16, True])
def test_network_symbol_rejects_invalid_identifiers(symbol):
    from tradeguard.providers import fetch_public_snapshot
    with pytest.raises(ValueError, match="symbol"):
        fetch_public_snapshot(symbol)


def test_explicit_provider_error_not_empty_success():
    from tradeguard.providers import parse_yahoo_chart
    with pytest.raises(ValueError, match="provider"):
        parse_yahoo_chart({"chart": {"result": None, "error": {"code": "Not Found"}}}, "MSFT", datetime.now(timezone.utc))


def test_sec_annual_context_uses_filed_date_and_same_accession():
    from tradeguard.providers import normalize_sec_annual
    def f(value, end="2025-06-30", filed="2025-07-30", accn="annual", start="2024-07-01"):
        return {"val": value, "start": start, "end": end, "filed": filed, "form": "10-K", "accn": accn}
    def tag(*items): return {"units": {"USD": list(items)}}
    facts = {"cik": 789019, "facts": {"us-gaap": {
        "RevenueFromContractWithCustomerExcludingAssessedTax": tag(f(100), f(90, "2024-06-30", start="2023-07-01"), f(999, filed="2027-07-30")),
        "NetIncomeLoss": tag(f(20), f(777, accn="unrelated")),
        "Assets": tag(f(300, start=None), f(250, "2024-06-30", start=None)),
        "PaymentsToAcquirePropertyPlantAndEquipment": tag(f(10)),
    }}}
    r = normalize_sec_annual(facts, "2026-11-09", "0000789019")
    assert r["revenue"] == 100
    assert r["revenue_prev"] == 90
    assert r["net_income"] == 20
    assert r["assets"] == 300
    assert r["assets_prev"] == 250
    assert r["capex"] == 10
    assert r["filed_at"] == "2025-07-30"
    assert "market_cap" not in r
    assert r["period_end"] == "2025-06-30"
    assert "interest_expense" in r["missing_fields"]


def test_tls_context_never_disables_peer_or_hostname_verification():
    from tradeguard.providers import _tls_context
    import ssl
    context = _tls_context()
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname is True


def test_sec_requires_explicit_ten_digit_cik():
    from tradeguard.providers import fetch_sec_fundamentals
    with pytest.raises(ValueError, match="CIK"):
        fetch_sec_fundamentals("789019")
