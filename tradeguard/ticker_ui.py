"""Human table and an explicitly requested CLI-only ticker prompt."""
from __future__ import annotations

import json
import re
import sys

from .tickers import recommend_tickers


def _line(value):
    # Do not let a provider error inject terminal control sequences or new rows.
    return re.sub(r"[\x00-\x1f\x7f-\x9f]", " ", str(value))


def render_ticker_results(result: dict) -> str:
    lines = ["Ticker          Price date    Technical   Combined    Selected scope / verdict",
             "-" * 98]
    for row in result["results"]:
        technical = row["technical_recommendation"]["score"]
        combined = row["combined_recommendation"]["score"]
        t = "N/A" if technical is None else f"{technical:.2f}"
        c = "N/A" if combined is None else f"{combined:.2f}"
        chosen = row["buy_recommendation"]
        lines.append(f"{row['symbol']:<15} {_line(row.get('price_as_of') or '-'):12} {t:<11} {c:<11} {chosen['scope']} / {chosen['verdict']}")
        lines.append("  " + _line(chosen["conclusion"]))
        if row.get("error"):
            lines.append("  Error: " + _line(row["error"]))
    lines.extend(["", "Scores: 0..1 heuristic support, NOT probabilities of profit. N/A means abstain/unavailable.",
                  "Technical = price-trend screen only. Combined = fundamentals/ETF structure plus technical evidence.",
                  "Ticker-only mode does not auto-fetch fundamentals or silently attach sample files.",
                  f"Analyzed: {result['succeeded']}/{result['count']} unique tickers. Results are input order, not portfolio rank."])
    return "\n".join(lines)


def show_ticker_results(result, json_output=False):
    print(json.dumps(result, allow_nan=False) if json_output else render_ticker_results(result))


def run_ticker_prompt(*, allow_public_data=False, as_of=None, json_output=False) -> int:
    """Unattended native handlers never call this; only CLI --interactive does."""
    if allow_public_data is not True:
        raise ValueError("interactive network requests require explicit --allow-public-data")
    print("TradeGuard: enter 1..10 tickers, separated by spaces or commas. Type quit to exit.", file=sys.stderr)
    while True:
        print("Tickers> ", file=sys.stderr, end="", flush=True)
        try:
            line = sys.stdin.readline()
        except KeyboardInterrupt:
            print("\nStopped.", file=sys.stderr)
            return 130
        if line == "":
            return 0
        text = line.strip()
        if not text:
            continue
        if text.lower() in {"quit", "exit", ":q", ":quit"}:
            return 0
        try:
            result = recommend_tickers(text, allow_public_data=True, as_of=as_of)
            show_ticker_results(result, json_output=json_output)
        except (ValueError, TypeError, KeyError, OSError, ArithmeticError) as exc:
            error = {"success": False, "error": str(exc), "research_only": True}
            print(json.dumps(error) if json_output else "Error: " + _line(exc))
