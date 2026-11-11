"""Exercise shipped synthetic files via actual CLI, prompt and native handler."""
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def test_offline_exercise_records_real_entrypoint_parity_and_no_live_claim(tmp_path):
    output = tmp_path / "integration.json"
    result = subprocess.run([sys.executable, "scripts/exercise_derivatives_offline.py", "--output", str(output)],
                            cwd=ROOT, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr + result.stdout
    report = json.loads(output.read_text())
    assert report["ok"] is True
    assert report["data_mode"] == "synthetic_fixture_not_live"
    assert report["case_count"] == len(report["cases"]) == 5
    assert report["tool_count"] == len(report["tools"]) == 8
    assert all(row["cli_native_equal"] and row["cli_returncode"] == 0 for row in report["cases"])
    assert all(row["score"] is None for row in report["cases"])
    assert report["root_request"]["returncode"] == 1
    assert report["root_request"]["code"] == "DERIVATIVES_PROVIDER_NOT_IMPLEMENTED"
    assert report["prompt"]["json_line_count"] == 2
    assert report["prompt"]["returncode"] == 0
    assert "bars" not in report["cases"][0]
    assert report["performance_validated"] is False
