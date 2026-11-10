"""Actual ticker-only CLI, prompt and registered-handler exercise; explicit network.

Developer command, never run by plugin registration. Saves derived output only.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone

from exercise_research import ROOT, context, dump


def command(argv, input_text=None):
    completed = subprocess.run([sys.executable, "-m", "tradeguard", *argv], input=input_text,
                               capture_output=True, text=True, cwd=ROOT, timeout=150)
    if completed.returncode:
        raise ValueError(f"actual CLI failed ({completed.returncode}): {completed.stdout} {completed.stderr}")
    return completed


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-public-data", action="store_true")
    args = parser.parse_args(argv)
    if not args.allow_public_data:
        parser.error("explicit --allow-public-data is required")
    tickers = ["MSFT", "AAPL", "SPY"]
    cutoff = datetime.now(timezone.utc).date().isoformat()
    batch = command(["recommend", *tickers, "--allow-public-data", "--json", "--as-of", cutoff])
    cli_result = json.loads(batch.stdout)
    if not cli_result["success"] or cli_result["count"] != len(tickers) or cli_result["failed"]:
        raise ValueError("live batch has failures; do not report all symbols exercised")
    native_result = json.loads(context().tools["tradeguard_recommend_tickers"]({"tickers": " ".join(tickers), "as_of": cutoff}))
    if not native_result.get("success") or native_result["failed"]:
        raise ValueError("registered native handler failed")
    for cli, native in zip(cli_result["results"], native_result["results"]):
        for field in ("symbol", "price_as_of", "technical_recommendation", "combined_recommendation", "technical_metrics"):
            if cli[field] != native[field]:
                raise ValueError(f"live CLI/native analysis mismatch: {cli['symbol']} {field}")
        if cli["combined_recommendation"]["score"] is not None or cli["metadata_status"] != "not_supplied":
            raise ValueError("ticker-only mode falsely claimed combined evidence")
        if cli["buy_recommendation"]["scope"] != "technical_only":
            raise ValueError("technical score lacks explicit scope")
    prompt = command(["recommend", "--interactive", "--allow-public-data", "--as-of", cutoff], "MSFT\nquit\n")
    if "Tickers>" not in prompt.stderr or "MSFT" not in prompt.stdout or "technical_only" not in prompt.stdout:
        raise ValueError("actual interactive prompt did not complete ticker analysis")
    artifact = {"run_at": datetime.now(timezone.utc).isoformat(), "network_explicitly_enabled": True,
                "tickers": tickers, "cli_native_metrics_and_scopes_match": True,
                "comparison_note": "Independent live retrieval timestamps differ; deterministic metrics, cutoffs and decisions compared.",
                "interactive_actual_stdin": "MSFT followed by quit", "interactive_stdout": prompt.stdout,
                "interactive_stderr": prompt.stderr, "cli_result": cli_result,
                "native_result": native_result, "research_only": True, "ok": True}
    dump(ROOT / "artifacts" / "ticker_integration_verification.json", artifact)
    print(json.dumps({"ok": True, "tickers": tickers, "count": cli_result["count"],
        "cli_native_metrics_and_scopes_match": True, "interactive_prompt_exercised": True,
        "rows": [{"symbol": row["symbol"], "price_as_of": row["price_as_of"],
                  "technical_score": row["technical_recommendation"]["score"],
                  "combined_score": row["combined_recommendation"]["score"],
                  "scope": row["buy_recommendation"]["scope"]} for row in cli_result["results"]]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
