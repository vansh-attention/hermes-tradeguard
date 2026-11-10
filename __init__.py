"""Hermes-native read-only research tools. No network or filesystem I/O on load."""
from __future__ import annotations

import json


def _json_call(fn, *args, **kwargs):
    try:
        return json.dumps({"success": True, **fn(*args, **kwargs)}, allow_nan=False)
    except (ValueError, TypeError, KeyError, ArithmeticError) as exc:
        return json.dumps({"success": False, "code": "INVALID_OR_UNAVAILABLE_EVIDENCE", "error": str(exc), "research_only": True})


def _research(args, **kwargs):
    from .tradeguard.equity import analyze_snapshot
    return _json_call(analyze_snapshot, args["snapshot"], as_of=args.get("as_of"))


def _validate(args, **kwargs):
    from .tradeguard.validation import walk_forward
    snapshot = args["snapshot"]
    def calculate():
        result = walk_forward(snapshot["bars"], adjustment=snapshot.get("adjustment", "raw"),
                              min_train=args.get("min_train", 252), cost_bps=args.get("cost_bps", 5.0))
        result.update({"symbol": snapshot.get("symbol"), "source": snapshot.get("source", "unavailable"),
                       "data_mode": snapshot.get("data_mode", "unavailable")})
        return result
    return _json_call(calculate)


def _book(args, **kwargs):
    def calculate():
        if ("events" in args) == ("quote" in args):
            raise ValueError("provide exactly one of quote or events")
        from .tradeguard.microstructure import book_features, order_flow_imbalance
        if "events" in args:
            return {"order_flow": order_flow_imbalance(args["events"]), "research_only": True, "not_an_entry_signal": True, "data_mode": "user_supplied_unverified"}
        return {"book": book_features(**args["quote"]), "research_only": True, "not_an_entry_signal": True, "data_mode": "user_supplied_unverified"}
    return _json_call(calculate)


def _boundary(handler, required):
    def checked(args, **kwargs):
        try:
            if not isinstance(args, dict):
                raise ValueError("tool arguments must be an object")
            if any(key not in args for key in required):
                raise ValueError("missing required tool arguments: " + ", ".join(required))
            return handler(args, **kwargs)
        except (ValueError, TypeError, KeyError, ArithmeticError, AttributeError) as exc:
            return json.dumps({"success": False, "code": "INVALID_ARGUMENTS", "error": str(exc), "research_only": True})
        except OSError:
            return json.dumps({"success": False, "code": "PROVIDER_IO_UNAVAILABLE", "error": "Provider I/O unavailable; no fallback data invented.", "research_only": True})
    return checked


def _rank(args, **kwargs):
    from .tradeguard.ranking import rank_snapshots
    return _json_call(rank_snapshots, args["snapshots"], as_of=args.get("as_of"))


def _catalog(args, **kwargs):
    from .tradeguard.catalog import strategy_catalog
    return _json_call(strategy_catalog, asset_type=args.get("asset_type"), strategy_id=args.get("strategy_id"))


def _schema(name, description, properties, required):
    return {"name": name, "description": description,
            "parameters": {"type": "object", "properties": properties, "required": required, "additionalProperties": False}}


SNAPSHOT = {"type": "object", "description": "Source-labelled normalized daily snapshot: symbol,asset_type,currency,source,retrieved_at,data_mode,adjustment,interval,bars and optional fundamentals/etf metadata. Never manufacture missing values."}
AS_OF = {"type": "string", "description": "YYYY-MM-DD research cutoff, defaults current UTC date. Not a historical-replay guarantee for retrospectively adjusted vendor data."}


def register(ctx):
    """Only documented PluginContext registration/configuration APIs."""
    def public_history(args, **kwargs):
        if ctx.get_config("allow_public_data", default=False) is not True:
            return json.dumps({"success": False, "code": "PUBLIC_DATA_DISABLED", "error": "Public data is disabled. Enable plugins.entries.tradeguard.settings.allow_public_data explicitly, or supply an authorized offline snapshot.", "research_only": True})
        from .tradeguard.providers import fetch_public_snapshot
        return _json_call(fetch_public_snapshot, args["symbol"])

    def ticker_recommendations(args, **kwargs):
        if ctx.get_config("allow_public_data", default=False) is not True:
            return json.dumps({"success": False, "code": "PUBLIC_DATA_DISABLED", "error": "Enable plugins.entries.tradeguard.settings.allow_public_data explicitly before ticker-only network requests.", "research_only": True})
        from .tradeguard.tickers import recommend_tickers
        return _json_call(recommend_tickers, args["tickers"], allow_public_data=True,
            fundamentals_by_symbol=args.get("fundamentals_by_symbol"),
            etf_by_symbol=args.get("etf_by_symbol"), as_of=args.get("as_of"))

    registrations = [
        ("tradeguard_recommend_tickers", "Use when the user supplies just stock/ETF tickers (e.g. MSFT AAPL SPY). One opt-in call fetches up to ten symbols and returns compact 0..1 research screens, source dates and gaps, never raw histories. Default score is explicitly technical-only; combined fundamental/technical recommendations remain unavailable without supplied symbol-bound metadata. Not probabilities or orders.", {"tickers": {"oneOf": [{"type": "string", "maxLength": 512}, {"type": "array", "minItems": 1, "maxItems": 10, "items": {"type": "string"}}]}, "as_of": AS_OF, "fundamentals_by_symbol": {"type": "object", "description": "Optional explicit metadata by exact canonical symbol; each object must carry that same symbol. Not automatically fetched."}, "etf_by_symbol": {"type": "object", "description": "Optional explicit source-labelled ETF metadata by exact canonical symbol."}}, ["tickers"], ticker_recommendations),
        ("tradeguard_strategy_catalog", "Browse source-linked stock/ETF strategy families, metrics, proposed rules, required data and failures. Explicitly distinguishes researched-only, feature-only, heuristic screens and experimental ML; no validated alpha claimed.", {"asset_type": {"type": "string", "enum": ["stock", "etf"]}, "strategy_id": {"type": "string"}}, [], _catalog),
        ("tradeguard_equity_research", "Explainable stock/ETF fundamental and daily technical research; unvalidated heuristic with coverage/abstention, NOT a calibrated buy probability. No order placement.", {"snapshot": SNAPSHOT, "as_of": AS_OF}, ["snapshot"], _research),
        ("tradeguard_public_history", "OPT-IN network: send one exact US stock/ETF symbol to Yahoo's unofficial public chart endpoint. Completed historical sessions only, no entitled executable price/fundamentals. Disabled by default.", {"symbol": {"type": "string", "pattern": "^[A-Z][A-Z0-9.\\-]{0,14}$"}}, ["symbol"], public_history),
        ("tradeguard_walk_forward", "Experimental expanding-window ridge evaluation on daily bars. Purged chronological labels, next-open entry, costs and buy-and-hold baseline. No strong-signal/production claim.", {"snapshot": SNAPSHOT, "min_train": {"type": "integer", "minimum": 50, "maximum": 2000}, "cost_bps": {"type": "number", "minimum": 0, "maximum": 500}}, ["snapshot"], _validate),
        ("tradeguard_microstructure", "Calculate spread, queue imbalance, weighted midpoint or top-of-book OFI from user-supplied event data; NOT an HFT strategy or calibrated microprice.", {"quote": {"type": "object", "properties": {k: {"type": "number"} for k in ("bid", "ask", "bid_size", "ask_size")}, "required": ["bid", "ask", "bid_size", "ask_size"], "additionalProperties": False}, "events": {"type": "array", "maxItems": 10000, "items": {"type": "object"}}}, [], _book),
        ("tradeguard_rank", "Compare up to 50 explicit source-labelled snapshots within one instrument family/currency/cutoff; missing or unvalidated evidence is never a probability. Does not discover all stocks or auto-trade.", {"snapshots": {"type": "array", "minItems": 1, "maxItems": 50, "items": SNAPSHOT}, "as_of": AS_OF}, ["snapshots"], _rank),
    ]
    for name, description, properties, required, handler in registrations:
        ctx.register_tool(name=name, toolset="tradeguard", schema=_schema(name, description, properties, required), handler=_boundary(handler, required))
