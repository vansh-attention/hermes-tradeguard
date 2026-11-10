"""Opt-in public research data. No cookies, trading keys, or private accounts.

Yahoo's chart endpoint is UNOFFICIAL: no entitlement, real-time guarantee or
redistribution license is inferred. Only sessions BEFORE retrieval's exchange
calendar date are used. SEC errors stay errors; callers may import an official
companyfacts JSON offline. Standard US-GAAP annual 10-K data only, not TTM.
"""
from __future__ import annotations

import json
import math
import re
import ssl
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlparse
from urllib.request import HTTPRedirectHandler, HTTPSHandler, Request, build_opener
from zoneinfo import ZoneInfo

MAX_BYTES = 16_000_000
USER_AGENT = "HermesTradeGuard/0.1 research github.com/vansh-attention/hermes-tradeguard"
ALLOWED_HOSTS = {"query1.finance.yahoo.com", "data.sec.gov"}


def _tls_context() -> ssl.SSLContext:
    context = ssl.create_default_context()
    # Python.org macOS interpreters can lack their own CA bundle. Append the
    # public OS bundle, never disable verification or edit global TLS state.
    if sys.platform == "darwin" and Path("/etc/ssl/cert.pem").is_file():
        context.load_verify_locations(cafile="/etc/ssl/cert.pem")
    return context


class _FixedHostRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parsed = urlparse(newurl)
        if parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS:
            raise ValueError("provider redirect outside allowed HTTPS hosts")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _get_json(url: str) -> dict:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS:
        raise ValueError("provider host is not allowed")
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    try:
        with build_opener(_FixedHostRedirect(), HTTPSHandler(context=_tls_context())).open(req, timeout=20) as response:
            body = response.read(MAX_BYTES + 1)
        if len(body) > MAX_BYTES:
            raise ValueError("provider response exceeds size limit")
        value = json.loads(body)
        if not isinstance(value, dict):
            raise ValueError("provider response must be a JSON object")
        return value
    except HTTPError as exc:
        raise ValueError(f"provider HTTP {exc.code}; no fallback data invented") from exc
    except (URLError, TimeoutError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("provider unavailable or invalid JSON; retry later or use an authorized offline snapshot") from exc


def _symbol(symbol: str) -> None:
    if not isinstance(symbol, str) or re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,14}", symbol) is None:
        raise ValueError("symbol must be an exact uppercase US stock/ETF identifier, max 15 characters")


def parse_yahoo_chart(payload: dict, symbol: str, as_of: datetime) -> dict:
    _symbol(symbol)
    if not isinstance(as_of, datetime) or as_of.tzinfo is None:
        raise ValueError("retrieval timestamp must be timezone-aware")
    try:
        chart = payload["chart"]
        if chart.get("error") or not chart.get("result"):
            raise ValueError("provider returned an error or no data")
        result = chart["result"][0]
        meta = result["meta"]
        if meta.get("symbol") != symbol:
            raise ValueError("provider symbol mismatch")
        if meta.get("instrumentType") not in {"EQUITY", "ETF"}:
            raise ValueError("provider instrument is not a stock or ETF")
        if not isinstance(meta.get("currency"), str) or len(meta["currency"]) != 3:
            raise ValueError("provider currency unavailable")
        if meta.get("dataGranularity") != "1d":
            raise ValueError("provider daily granularity must be explicitly 1d")
        zone_name = meta.get("exchangeTimezoneName")
        if not isinstance(zone_name, str):
            raise ValueError("provider schema requires an exchange timezone")
        zone = ZoneInfo(zone_name)
        cutoff = as_of.astimezone(zone).date()
        quote_data = result["indicators"]["quote"][0]
        bars, skipped = [], 0
        stamps = result.get("timestamp", [])
        if len(stamps) > 10_000:
            raise ValueError("provider has too many bars")
        for i, stamp in enumerate(stamps):
            day = datetime.fromtimestamp(stamp, timezone.utc).astimezone(zone).date()
            if day >= cutoff:
                continue
            values = {key: quote_data[key][i] for key in ("open", "high", "low", "close", "volume")}
            if any(v is None for v in values.values()):
                skipped += 1
                continue
            bars.append({"date": day.isoformat(), **values})
        return {"symbol": symbol, "asset_type": "etf" if meta["instrumentType"] == "ETF" else "stock",
                "currency": meta["currency"], "source": "Yahoo Finance unofficial chart endpoint; historical research only",
                "exchange_timezone": zone_name,
                "retrieved_at": as_of.isoformat(), "data_mode": "historical", "adjustment": "split", "interval": "1d", "bars": bars,
                "provider_warnings": ["Unofficial personal-research source, not an entitled executable quote.",
                    "Chart OHLC is provider-reported split-adjusted; dividends NOT included. No total-return claim.",
                    "All candles on retrieval's exchange date excluded, even if that session may have closed.",
                    f"Incomplete provider rows skipped: {skipped}. Missing sessions are not filled."]}
    except (KeyError, TypeError, IndexError, AttributeError, OverflowError) as exc:
        raise ValueError("provider chart schema is malformed") from exc


def fetch_public_snapshot(symbol: str) -> dict:
    """Explicit network action. US instrument quotes/history, no fundamentals."""
    _symbol(symbol)
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{quote(symbol, safe='')}?range=5y&interval=1d"
    payload = _get_json(url)
    snapshot = parse_yahoo_chart(payload, symbol, datetime.now(timezone.utc))
    snapshot["source_url"] = url
    return snapshot


# Conservative aliases: if a firm only reports custom taxonomy tags, abstain.
_TAGS = {
    "revenue": ("RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues", "SalesRevenueNet"),
    "net_income": ("NetIncomeLoss", "ProfitLoss"),
    "operating_income": ("OperatingIncomeLoss",),
    "gross_profit": ("GrossProfit",),
    "operating_cash_flow": ("NetCashProvidedByUsedInOperatingActivities",),
    "capex": ("PaymentsToAcquirePropertyPlantAndEquipment",),
    "assets": ("Assets",),
    "equity": ("StockholdersEquity",),
    "cash": ("CashAndCashEquivalentsAtCarryingValue",),
    "interest_expense": ("InterestExpenseNonOperating", "InterestExpense"),
}


def normalize_sec_annual(payload: dict, as_of: str, cik: str) -> dict:
    """One accession and matching periods; filings after as_of cannot enter.

    Do not estimate market cap from diluted weighted-average annual shares.
    Missing total-debt aggregation is explicit (no dubious alias summation).
    Restatements within the latest eligible accession are allowed and labelled.
    This is not a complete point-in-time fundamentals/universe database.
    """
    if not isinstance(cik, str) or re.fullmatch(r"[0-9]{10}", cik) is None:
        raise ValueError("CIK must be exactly ten digits; not silently normalized")
    if not isinstance(payload, dict) or type(payload.get("cik")) is not int or payload["cik"] != int(cik):
        raise ValueError("SEC payload numeric issuer CIK must match the supplied ten-digit CIK")
    cutoff = date.fromisoformat(as_of)
    facts = payload.get("facts", {}).get("us-gaap", {})
    def records(field):
        for name in _TAGS[field]:
            for r in facts.get(name, {}).get("units", {}).get("USD", []):
                try:
                    if r.get("form") not in {"10-K", "10-K/A"} or date.fromisoformat(r["filed"]) > cutoff:
                        continue
                    if date.fromisoformat(r["end"]) > date.fromisoformat(r["filed"]):
                        continue
                    val = r.get("val")
                    if isinstance(val, bool) or not isinstance(val, (int, float)) or not math.isfinite(val):
                        continue
                    yield {**r, "_tag": name}
                except (ValueError, KeyError, TypeError):
                    continue
    def annual(r):
        try:
            return 330 <= (date.fromisoformat(r["end"]) - date.fromisoformat(r["start"])).days <= 380
        except (KeyError, TypeError, ValueError):
            return False
    revenue = [r for r in records("revenue") if annual(r)]
    if not revenue:
        raise ValueError("no eligible standard USD annual revenue context; custom/IFRS mappings unsupported")
    anchor = max(revenue, key=lambda r: (r["end"], r["filed"]))
    accession, end = anchor.get("accn"), anchor["end"]
    if not accession:
        raise ValueError("SEC accession missing")
    result = {"source": f"SEC companyfacts CIK{cik} accession {accession}",
              "issuer_cik": cik,
              "source_url": f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json",
              "filed_at": anchor["filed"], "period_start": anchor["start"], "period_end": end, "currency": "USD",
              "period_type": "annual_not_TTM", "field_provenance": {}, "missing_fields": [],
              "warnings": ["Standard USD US-GAAP annual 10-K fields only, not TTM. Custom taxonomy and consolidated debt mapping may be missing."]}
    instant = {"assets", "equity", "cash"}
    for field in _TAGS:
        candidates = [r for r in records(field) if r.get("accn") == accession and r["end"] == end
                      and (not r.get("start") if field in instant else r.get("start") == anchor["start"])]
        if candidates:
            item = candidates[0]
            result[field] = item["val"]
            result["field_provenance"][field] = {"tag": item["_tag"], "end": end, "filed": item["filed"], "accession": accession}
        else:
            result["missing_fields"].append(field)
    for field, output in (("revenue", "revenue_prev"), ("assets", "assets_prev")):
        candidates = [r for r in records(field) if r.get("accn") == accession and r["end"] < end
                      and 300 <= (date.fromisoformat(end) - date.fromisoformat(r["end"])).days <= 400
                      and (annual(r) if field == "revenue" else not r.get("start"))]
        if candidates:
            item = max(candidates, key=lambda r: r["end"])
            result[output] = item["val"]
            result["field_provenance"][output] = {"tag": item["_tag"], "end": item["end"], "filed": item["filed"], "accession": accession}
        else:
            result["missing_fields"].append(output)
    result["missing_fields"] += ["total_debt", "market_cap"]
    return result


def fetch_sec_fundamentals(cik: str) -> dict:
    if not isinstance(cik, str) or re.fullmatch(r"[0-9]{10}", cik) is None:
        raise ValueError("CIK must be exactly ten digits")
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
    return normalize_sec_annual(_get_json(url), datetime.now(timezone.utc).date().isoformat(), cik)
