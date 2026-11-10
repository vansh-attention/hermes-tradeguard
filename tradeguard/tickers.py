"""Bounded ticker-only research orchestration, not an automatic valuation feed.

UI grammar is explicitly case-insensitive; validate first, then uppercase for the
provider while preserving requested tokens. One opt-in request per unique ticker,
up to ten input tokens and three joined fetch workers. No files, account reads,
persistent jobs, implicit examples, orders or raw-history output.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import date, datetime, timezone
import re

from .equity import analyze_snapshot, _buy_recommendation

MAX_TICKERS = 10
_UI_TICKER = re.compile(r"[A-Za-z][A-Za-z0-9.\-]{0,14}")


def parse_tickers(value: str | list[str]) -> dict:
    """Accept declared UI syntax; never repair punctuation or change share class."""
    if isinstance(value, str):
        if len(value) > 512:
            raise ValueError("ticker input exceeds 512 characters")
        tokens = re.split(r"[\s,]+", value.strip()) if value.strip() else []
    elif isinstance(value, list):
        tokens = list(value)
    else:
        raise ValueError("tickers must be a string or list of strings")
    if not 1 <= len(tokens) <= MAX_TICKERS:
        raise ValueError("provide 1..10 ticker tokens; separate with spaces or commas")
    for token in tokens:
        if not isinstance(token, str) or _UI_TICKER.fullmatch(token) is None:
            raise ValueError("invalid ticker; use 1..15 case-insensitive letters/digits/dot/hyphen, starting with a letter")
    return {"requested": tokens, "symbols": list(dict.fromkeys(token.upper() for token in tokens))}


def _metadata_map(value, symbols, field):
    if value is None:
        return {}
    if not isinstance(value, dict) or len(value) > MAX_TICKERS:
        raise ValueError(f"{field} must be an object with at most ten symbol keys")
    for symbol, metadata in value.items():
        if symbol not in symbols or not isinstance(metadata, dict) or metadata.get("symbol") != symbol:
            raise ValueError(f"{field} must explicitly bind metadata to an exact requested canonical symbol")
    return value


def _unavailable(message, scope="unavailable"):
    return {"score": None, "verdict": "ABSTAIN", "scope": scope,
            "conclusion": message, "score_type": "uncalibrated_buy_interest_not_profit_probability",
            "strong_buy": False, "cautions": [message]}


def _technical_view(report):
    trend = report["strategies"].get("trend_following")
    blockers = report["recommendation"].get("blockers", [])
    if report["validation_errors"] or blockers or not trend:
        reason = "; ".join(report["validation_errors"] + blockers) or "Technical evidence unavailable"
        return _unavailable(reason, "technical_only")
    # Explicitly score the standalone technical strategy, NOT the missing-data
    # combined recommendation. The latter is retained separately and may abstain.
    temporary = {"validation_errors": [], "recommendation": {
        "action": trend["action"], "score": trend["score"],
        "evidence_coverage": trend["evidence_coverage"], "blockers": [],
        "evidence_limitations": ["Technical-only screen: fundamental valuation and ETF structure were not assessed."]}}
    view = _buy_recommendation(temporary)
    view["scope"] = "technical_only"
    view["horizon"] = trend["horizon"]
    if view["score"] is not None:
        view["verdict"] = "TECHNICAL_" + view["verdict"].removeprefix("BUY_")
        view["conclusion"] = "Price-based trend screen. " + view["conclusion"] + " Fundamental valuation is not assessed."
    return view


def recommend_tickers(tickers, *, allow_public_data=False, fundamentals_by_symbol=None,
                      etf_by_symbol=None, as_of=None, fetcher=None) -> dict:
    """Fetch once per validated symbol and return compact, explicitly scoped scores.

    No auto-discovery of filings/holdings is claimed. Optional supplemental maps
    are explicit caller evidence; no sample file is silently attached by ticker.
    A technical-only score does not stand in for a combined recommendation.
    """
    parsed = parse_tickers(tickers)
    symbols = parsed["symbols"]
    fundamentals = _metadata_map(fundamentals_by_symbol, symbols, "fundamentals_by_symbol")
    etfs = _metadata_map(etf_by_symbol, symbols, "etf_by_symbol")
    cutoff = datetime.now(timezone.utc).date().isoformat() if as_of is None else as_of
    if not isinstance(cutoff, str) or date.fromisoformat(cutoff).isoformat() != cutoff:
        raise ValueError("as_of must be YYYY-MM-DD")
    if allow_public_data is not True:
        raise ValueError("public data disabled: explicit allow_public_data=True opt-in required")
    if fetcher is None:
        from .providers import fetch_public_snapshot
        fetcher = fetch_public_snapshot
    if not callable(fetcher):
        raise ValueError("fetcher must be callable")

    def one(symbol):
        aliases = [token for token in parsed["requested"] if token.upper() == symbol]
        base = {"symbol": symbol, "requested_as": aliases}
        try:
            raw = fetcher(symbol)
            if not isinstance(raw, dict) or raw.get("symbol") != symbol:
                raise ValueError("provider snapshot symbol mismatch or invalid object")
            snapshot = {key: value for key, value in raw.items() if key not in {"fundamentals", "etf"}}
            technical_report = analyze_snapshot(snapshot, as_of=cutoff)
            technical = _technical_view(technical_report)
            enriched = dict(snapshot)
            supplied = False
            if symbol in fundamentals:
                enriched["fundamentals"] = deepcopy(fundamentals[symbol])
                supplied = True
            if symbol in etfs:
                enriched["etf"] = deepcopy(etfs[symbol])
                supplied = True
            report = analyze_snapshot(enriched, as_of=cutoff) if supplied else technical_report
            combined = {**report["buy_recommendation"], "scope": "combined"}
            status = "unusable_evidence" if technical_report["validation_errors"] else "ok"
            row = {**base, "status": status, "asset_type": report["asset_type"],
                   "currency": report["currency"], "as_of": cutoff,
                   "price_as_of": snapshot["bars"][-1]["date"] if snapshot.get("bars") else None,
                   "source": report["sources"].get("prices", {}),
                   "metadata_status": "supplied_unverified" if supplied else "not_supplied",
                   "technical_recommendation": technical, "combined_recommendation": combined,
                   "technical_metrics": technical_report["metrics"]["technical"],
                   "fundamental_metrics": report["metrics"]["fundamentals"],
                   "etf_metrics": report["metrics"]["etf"],
                   "positive_reasons": technical_report["strategies"].get("trend_following", {}).get("bullish_reasons", [])[:3],
                   "missing_data": list(dict.fromkeys(report["missing_data"])),
                   "warnings": report["warnings"], "validation_errors": report["validation_errors"]}
            # An explicitly supplied but invalid/incomplete combined case must
            # not silently fall back to a more attractive technical score.
            row["buy_recommendation"] = combined if supplied else technical
            return row
        except (ValueError, TypeError, KeyError, OSError, ArithmeticError) as exc:
            message = str(exc)
            return {**base, "status": "unavailable", "error": message,
                    "metadata_status": "unavailable", "technical_recommendation": _unavailable(message, "technical_only"),
                    "combined_recommendation": _unavailable(message, "combined"),
                    "buy_recommendation": _unavailable(message)}

    with ThreadPoolExecutor(max_workers=min(3, len(symbols))) as pool:
        results = list(pool.map(one, symbols))  # map preserves requested order.
    succeeded = sum(row["status"] == "ok" for row in results)
    return {"success": succeeded > 0, "requested": parsed["requested"], "symbols": symbols,
            "input_count": len(parsed["requested"]), "count": len(results),
            "succeeded": succeeded, "failed": len(results) - succeeded,
            "as_of": cutoff, "research_only": True, "model_status": "unvalidated_heuristic",
            "fundamental_auto_fetch": "not_implemented", "results": results,
            "warning": "Technical-only scores are price-trend research screens, not combined valuation recommendations or probabilities. No orders. Results preserve input order, not investment rank."}
