"""Exercise the shipped derivative fixtures through real offline entrypoints.

This developer-only script performs no network, credential, account, or order
access. It compares the actual CLI output with the registered native handler,
checks the unavailable M1 root path, and exercises the interactive JSON prompt.
"""
from __future__ import annotations

import argparse
from collections.abc import Callable
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
AS_OF = "2026-11-10T08:00:00Z"
PROVIDER_UNAVAILABLE = "DERIVATIVES_PROVIDER_NOT_IMPLEMENTED"


class Context:
    """Collect the plugin's documented registration surface."""

    def __init__(self) -> None:
        self.tools: dict[str, Callable[..., str]] = {}

    def register_tool(self, *, name, toolset, schema, handler) -> None:
        if toolset != "tradeguard" or schema.get("name") != name:
            raise ValueError("invalid native tool registration")
        self.tools[name] = handler

    def get_config(self, key, default=None):
        return default


def registered_context() -> Context:
    """Load and register the real plugin entrypoint without installing it."""
    spec = importlib.util.spec_from_file_location(
        "tradeguard_derivatives_offline_exercise",
        ROOT / "__init__.py",
        submodule_search_locations=[str(ROOT)],
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("native plugin entrypoint could not be loaded")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    context = Context()
    module.register(context)
    return context


def run_cli(*arguments: str, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    """Run the actual package CLI with bounded offline subprocess I/O."""
    return subprocess.run(
        [sys.executable, "-m", "tradeguard", *arguments],
        cwd=ROOT,
        input=input_text,
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
    )


def parse_json_output(process: subprocess.CompletedProcess[str], label: str) -> dict:
    try:
        value = json.loads(process.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label} did not emit one JSON object") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} JSON output must be an object")
    return value


def exercise_case(context: Context, name: str, snapshot_name: str,
                  short_leg_name: str | None = None) -> dict:
    snapshot_path = ROOT / "examples" / snapshot_name
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    native_arguments = {"snapshot": snapshot, "as_of": AS_OF}
    cli_arguments = [
        "derivatives", "--snapshot", str(snapshot_path),
        "--as-of", AS_OF, "--json",
    ]
    if short_leg_name is not None:
        short_path = ROOT / "examples" / short_leg_name
        native_arguments["short_leg"] = json.loads(short_path.read_text(encoding="utf-8"))
        cli_arguments[3:3] = ["--short-leg", str(short_path)]

    process = run_cli(*cli_arguments)
    cli_result = parse_json_output(process, name)
    handler = context.tools["tradeguard_derivatives_research"]
    native_result = json.loads(handler(native_arguments))
    equal = cli_result == native_result
    recommendation = cli_result.get("recommendation", {})
    return {
        "name": name,
        "cli_returncode": process.returncode,
        "cli_native_equal": equal,
        "success": cli_result.get("success") is True,
        "strategy": cli_result.get("strategy"),
        "data_mode": cli_result.get("data_mode"),
        "score": recommendation.get("score"),
        "performance_validated": cli_result.get("performance_validated"),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    context = registered_context()
    tools = sorted(context.tools)
    cases = [
        exercise_case(context, "future", "derivatives_synthetic.json"),
        exercise_case(context, "long_call", "derivatives_synthetic_call.json"),
        exercise_case(
            context,
            "bull_call_debit",
            "derivatives_synthetic_call.json",
            "derivatives_synthetic_call_short.json",
        ),
        exercise_case(context, "long_put", "derivatives_synthetic_put.json"),
        exercise_case(
            context,
            "bear_put_debit",
            "derivatives_synthetic_put.json",
            "derivatives_synthetic_put_short.json",
        ),
    ]

    root_process = run_cli(
        "derivatives", "NFO:NIFTY", "--kind", "options", "--json"
    )
    root_result = parse_json_output(root_process, "root request")
    root_request = {
        "returncode": root_process.returncode,
        "code": root_result.get("code"),
    }

    prompt_process = run_cli(
        "derivatives", "--interactive", "--kind", "options", "--json",
        input_text="NFO:NIFTY;bad\nNFO:NIFTY\nquit\n",
    )
    prompt_lines = [
        json.loads(line) for line in prompt_process.stdout.splitlines() if line.strip()
    ]
    prompt = {
        "returncode": prompt_process.returncode,
        "json_line_count": len(prompt_lines),
    }

    cases_ok = all(
        row["cli_returncode"] == 0
        and row["cli_native_equal"]
        and row["success"]
        and row["data_mode"] == "fixture"
        and row["score"] is None
        and row["performance_validated"] is False
        for row in cases
    )
    root_ok = (
        root_request["returncode"] == 1
        and root_request["code"] == PROVIDER_UNAVAILABLE
    )
    prompt_ok = (
        prompt["returncode"] == 0
        and prompt["json_line_count"] == 2
        and prompt_lines[0].get("success") is False
        and prompt_lines[1].get("code") == PROVIDER_UNAVAILABLE
    )
    ok = (
        len(tools) == 8
        and "tradeguard_derivatives_research" in tools
        and cases_ok
        and root_ok
        and prompt_ok
    )
    report = {
        "ok": ok,
        "data_mode": "synthetic_fixture_not_live",
        "case_count": len(cases),
        "cases": cases,
        "tool_count": len(tools),
        "tools": tools,
        "root_request": root_request,
        "prompt": prompt,
        "performance_validated": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, allow_nan=False))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
