"""Developer verification runner; not loaded by the native plugin.

Runs actual offline tests and official Hermes gates, preserving their stdout,
stderr and exit codes in artifacts/verification_run.json. No installation into an
active profile, catalog submission, remote git writes or trading activity.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def redact_local_paths(value, *, checkout=ROOT, home=None, scratch=None):
    """Preserve actual verification evidence without publishing local identities."""
    home = Path.home() if home is None else home
    substitutions = [(str(checkout), "<checkout>"), (str(home), "<home>")]
    if scratch is not None:
        substitutions.append((str(scratch), "<scratch>"))
    substitutions.sort(key=lambda pair: len(pair[0]), reverse=True)

    def clean(item):
        if isinstance(item, str):
            for original, placeholder in substitutions:
                item = item.replace(original, placeholder)
            return item
        if isinstance(item, list):
            return [clean(child) for child in item]
        if isinstance(item, dict):
            return {key: clean(child) for key, child in item.items()}
        return item

    return clean(value)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scratch", required=True, help="Explicit disposable pytest scratch directory")
    args = parser.parse_args(argv)
    scratch = Path(args.scratch).expanduser().resolve()
    if scratch == ROOT or scratch == Path.home() or len(scratch.parts) < 4:
        parser.error("scratch must be a dedicated disposable subdirectory")
    commands = [
        [sys.executable, "-m", "pytest", "-q", "--basetemp", str(scratch)],
        [sys.executable, "scripts/check_research_integrity.py"],
        ["hermes", "plugins", "doctor", ".", "--ci"],
        ["hermes", "plugins", "validate", ".", "--install-deps", "--json"],
        ["git", "diff", "--check"],
    ]
    report = {"run_at": datetime.now(timezone.utc).isoformat(), "commands": [], "ok": True}
    for command in commands:
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=300)
        record = {"command": command, "returncode": result.returncode,
                  "stdout": result.stdout, "stderr": result.stderr}
        report["commands"].append(record)
        print("COMMAND:", " ".join(command))
        print(result.stdout, end="")
        if result.stderr:
            print(result.stderr, file=sys.stderr, end="")
        if result.returncode:
            report["ok"] = False
            break
    path = ROOT / "artifacts" / "verification_run.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    public_report = redact_local_paths(report, scratch=scratch)
    assert isinstance(public_report, dict)
    public_report["path_redaction"] = "Absolute checkout/home/scratch paths replaced for publication; measured exit codes and other output preserved."
    path.write_text(json.dumps(public_report, indent=2) + "\n")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
