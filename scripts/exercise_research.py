"""Explicit developer-only integration exercise; never runs during plugin load.

Run from the checkout: python3 scripts/exercise_research.py --allow-public-data
Reads public historical data and dated issuer examples, exercises the *registered*
native handler and actual CLI, then runs the experimental chronological baseline.
No broker/credential access. Raw histories remain in git-ignored data/.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def dump(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


class Context:
    """Collect only the documented native registration surface, no host patches."""
    def __init__(self):
        self.tools = {}

    def register_tool(self, *, name, toolset, schema, handler):
        self.tools[name] = handler

    def get_config(self, key, default=None):
        return key == "allow_public_data"


def context() -> Context:
    spec = importlib.util.spec_from_file_location(
        "tradeguard_integration_plugin", ROOT / "__init__.py", submodule_search_locations=[str(ROOT)]
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("native plugin entrypoint could not be loaded")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    ctx = Context()
    module.register(ctx)
    return ctx


def cli(*args: str) -> dict:
    process = subprocess.run([sys.executable, "-m", "tradeguard", *args], cwd=ROOT,
                             text=True, capture_output=True, check=False, timeout=90)
    result = json.loads(process.stdout)
    if process.returncode or not result.get("success"):
        raise ValueError(f"CLI failed: {result}")
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-public-data", action="store_true")
    parser.add_argument("--offline", action="store_true", help="Use explicitly retained data/*_snapshot.json instead of network")
    args = parser.parse_args(argv)
    if not args.offline and not args.allow_public_data:
        parser.error("network requires --allow-public-data, or use --offline for retained snapshots")
    ctx = context()
    cutoff = datetime.now(timezone.utc).date().isoformat()
    verification = {"run_at": datetime.now(timezone.utc).isoformat(), "as_of": cutoff,
                    "mode": "retained_snapshot" if args.offline else "explicit_public_network",
                    "research_only": True, "symbols": {}, "errors": {},
                    "strong_recommendations_promoted": False}
    examples = {"MSFT": ("fundamentals", "msft_fy2026_fundamentals.json"),
                "SPY": ("etf", "spy_issuer_metadata.json")}
    for symbol, (field, filename) in examples.items():
        try:
            path = ROOT / "data" / f"{symbol.lower()}_snapshot.json"
            if args.offline:
                snapshot = json.loads(path.read_text(encoding="utf-8"))
            else:
                history = json.loads(ctx.tools["tradeguard_public_history"]({"symbol": symbol}))
                if not history.get("success"):
                    raise ValueError(f"history unavailable: {history}")
                snapshot = {k: v for k, v in history.items() if k != "success"}
            metadata = json.loads((ROOT / "examples" / filename).read_text(encoding="utf-8"))
            if metadata["symbol"] != snapshot["symbol"]:
                raise ValueError("issuer example identity mismatch")
            snapshot[field] = metadata
            dump(path, snapshot)
            report = json.loads(ctx.tools["tradeguard_equity_research"]({"snapshot": snapshot, "as_of": cutoff}))
            if not report.get("success") or report.get("validation_errors"):
                raise ValueError(f"analysis failed: {report}")
            command_report = cli("analyze", "--snapshot", str(path), "--as-of", cutoff)
            if command_report != report:
                raise ValueError("registered handler and actual CLI disagree")
            dump(ROOT / "artifacts" / f"{symbol.lower()}_research.json", report)
            model = json.loads(ctx.tools["tradeguard_walk_forward"]({"snapshot": snapshot, "min_train": 252, "cost_bps": 5.0}))
            if not model.get("success"):
                raise ValueError(f"ML experiment failed: {model}")
            command_model = cli("walk-forward", "--snapshot", str(path), "--min-train", "252", "--cost-bps", "5")
            if command_model != model:
                raise ValueError("registered ML handler and actual CLI disagree")
            dump(ROOT / "data" / f"{symbol.lower()}_walk_forward_full.json", model)
            summary = {k: v for k, v in model.items() if k not in {"predictions", "equity_curve", "fits"}}
            dump(ROOT / "artifacts" / f"{symbol.lower()}_walk_forward_summary.json", summary)
            verification["symbols"][symbol] = {
                "bars": len(snapshot["bars"]), "last_bar": snapshot["bars"][-1]["date"],
                "retrieved_at": snapshot["retrieved_at"], "source": snapshot["source"],
                "native_cli_equivalence": True, "recommendation": report["recommendation"],
                "out_of_sample": model["summary"],
            }
        except (ValueError, KeyError, TypeError, OSError, subprocess.SubprocessError) as exc:
            verification["errors"][symbol] = str(exc)
    if not args.offline:
        try:
            from tradeguard.providers import fetch_sec_fundamentals
            # Exact issuer CIK, supplied explicitly; no identity guessing.
            value = fetch_sec_fundamentals("0000789019")
            verification["sec_companyfacts"] = {"status": "retrieved", "source": value["source"], "period_end": value["period_end"]}
            dump(ROOT / "data" / "sec_msft_annual.json", value)
        except (ValueError, OSError) as exc:
            verification["sec_companyfacts"] = {"status": "unavailable", "error": str(exc),
                "alternative": "Dated Microsoft issuer release example, independently supplied; not a fabricated SEC result"}
    dump(ROOT / "artifacts" / "integration_verification.json", verification)
    print(json.dumps(verification, indent=2, allow_nan=False))
    return 1 if verification["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
