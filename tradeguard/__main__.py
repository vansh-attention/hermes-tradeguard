"""Read-only CLI. Reads only explicitly named JSON files; writes JSON to stdout."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def _read_json(path: str):
    p = Path(path)
    if p.stat().st_size > 16_000_000:
        raise ValueError("input exceeds 16 MB research limit")
    def reject_nonfinite(value):
        raise ValueError(f"nonfinite JSON number: {value}")
    return json.loads(p.read_text(encoding="utf-8"), parse_constant=reject_nonfinite)


def _attach(snapshot: dict, data: dict, field: str) -> None:
    if not isinstance(snapshot, dict):
        raise ValueError("snapshot must be an object before attaching metadata")
    if not isinstance(data, dict) or data.get("symbol") != snapshot.get("symbol"):
        raise ValueError(f"{field} file must explicitly identify the same symbol as the price snapshot")
    snapshot[field] = data


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="TradeGuard read-only stocks/ETF research. No orders; scores are not win probabilities.")
    sub = parser.add_subparsers(dest="command", required=True)
    catalog = sub.add_parser("strategies", help="Offline source-linked strategy research directory, not validated signals")
    catalog.add_argument("--asset-type", choices=["stock", "etf"])
    catalog.add_argument("--strategy-id")
    recommend = sub.add_parser("recommend", help="Type tickers only: fetch public history and return explicitly scoped 0..1 research screens")
    recommend.add_argument("tickers", nargs="*", help="1..10 stock/ETF tickers, spaces or commas; declared case-insensitive UI")
    recommend.add_argument("--allow-public-data", action="store_true", help="Explicit consent to public history requests for supplied symbols")
    recommend.add_argument("--interactive", action="store_true", help="Keep a ticker-only prompt open; type quit to exit")
    recommend.add_argument("--json", action="store_true", help="JSON output; interactive mode emits one JSON object per submitted line")
    recommend.add_argument("--as-of", help="YYYY-MM-DD research cutoff; not a historical-vintage guarantee")
    analyze = sub.add_parser("analyze", help="Fundamental and technical research on one daily snapshot")
    inp = analyze.add_mutually_exclusive_group(required=True)
    inp.add_argument("--snapshot", help="Explicit normalized JSON snapshot path (offline)")
    inp.add_argument("--symbol", help="Exact uppercase US symbol; requires --allow-public-data")
    analyze.add_argument("--allow-public-data", action="store_true", help="Opt in to unofficial public historical-price network request")
    analyze.add_argument("--fundamentals", help="Optional normalized, source-labelled stock fundamentals JSON")
    analyze.add_argument("--etf-metadata", help="Optional source-labelled ETF metadata JSON")
    analyze.add_argument("--as-of", help="YYYY-MM-DD analysis cutoff; current UTC if omitted")
    validate = sub.add_parser("walk-forward", help="Experimental next-open ridge evaluation, not production alpha")
    validate.add_argument("--snapshot", required=True)
    validate.add_argument("--min-train", type=int, default=252)
    validate.add_argument("--cost-bps", type=float, default=5.0)
    rank = sub.add_parser("rank", help="Prioritize a specified same-family same-currency snapshot universe")
    rank.add_argument("--snapshots", required=True, help="JSON array, max 50 normalized snapshots")
    rank.add_argument("--as-of")
    book = sub.add_parser("microstructure", help="User-supplied top-of-book observation/OFI; NOT an HFT strategy")
    book.add_argument("--input", required=True, help="JSON object with quote or events")
    args = parser.parse_args(argv)
    try:
        if args.command == "recommend":
            from .tickers import recommend_tickers
            from .ticker_ui import run_ticker_prompt, show_ticker_results
            if not args.allow_public_data:
                raise ValueError("network requests require explicit --allow-public-data")
            if args.interactive:
                if args.tickers:
                    raise ValueError("use initial tickers or --interactive, not both")
                return run_ticker_prompt(allow_public_data=True, as_of=args.as_of, json_output=args.json)
            result = recommend_tickers(" ".join(args.tickers), allow_public_data=True, as_of=args.as_of)
            show_ticker_results(result, json_output=args.json)
            return 0 if result["success"] else 1
        elif args.command == "strategies":
            from .catalog import strategy_catalog
            result = strategy_catalog(asset_type=args.asset_type, strategy_id=args.strategy_id)
        elif args.command == "analyze":
            if args.symbol and not args.allow_public_data:
                raise ValueError("network requests require explicit --allow-public-data; otherwise use --snapshot")
            if args.symbol:
                from .providers import fetch_public_snapshot
                snapshot = fetch_public_snapshot(args.symbol)
            else:
                snapshot = _read_json(args.snapshot)
            if args.fundamentals:
                _attach(snapshot, _read_json(args.fundamentals), "fundamentals")
            if args.etf_metadata:
                _attach(snapshot, _read_json(args.etf_metadata), "etf")
            from .equity import analyze_snapshot
            result = analyze_snapshot(snapshot, as_of=args.as_of)
        elif args.command == "walk-forward":
            from .validation import walk_forward
            snapshot = _read_json(args.snapshot)
            if not isinstance(snapshot, dict):
                raise ValueError("snapshot must be an object")
            result = walk_forward(snapshot["bars"], min_train=args.min_train, cost_bps=args.cost_bps,
                                  adjustment=snapshot.get("adjustment", "raw"))
            result["source"] = snapshot.get("source", "unavailable")
            result["data_mode"] = snapshot.get("data_mode", "unavailable")
            result["symbol"] = snapshot.get("symbol")
        elif args.command == "rank":
            from .ranking import rank_snapshots
            result = rank_snapshots(_read_json(args.snapshots), as_of=args.as_of)
        else:
            from .microstructure import book_features, order_flow_imbalance
            data = _read_json(args.input)
            if not isinstance(data, dict) or ("quote" in data) == ("events" in data):
                raise ValueError("provide an object with exactly one of quote or events")
            result = {"order_flow": order_flow_imbalance(data["events"])} if "events" in data else {"book": book_features(**data["quote"])}
            result.update({"research_only": True, "not_an_entry_signal": True})
        print(json.dumps({"success": True, **result}, indent=2, allow_nan=False))
        return 0
    except (ValueError, TypeError, KeyError, OSError, ArithmeticError) as exc:
        print(json.dumps({"success": False, "error": str(exc), "research_only": True}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
