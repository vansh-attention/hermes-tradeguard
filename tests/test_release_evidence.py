"""Published verification evidence must not expose local filesystem identities."""
from copy import deepcopy
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def runner():
    spec = importlib.util.spec_from_file_location("tradeguard_verification_runner_test", ROOT / "scripts/verify_project.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_verification_path_redaction_is_recursive_and_keeps_exit_evidence(tmp_path):
    home = tmp_path / "local-user"
    checkout = home / "work" / "plugin"
    scratch = home / "cache" / "scratch"
    original = {"commands": [{"command": ["python", "--basetemp", str(scratch)],
                 "stdout": f"Plugin Doctor: {checkout}\n339 passed\n", "stderr": f"home={home}", "returncode": 0}], "ok": True}
    before = deepcopy(original)
    result = runner().redact_local_paths(original, checkout=checkout, home=home, scratch=scratch)
    assert result["commands"][0]["command"][-1] == "<scratch>"
    assert "<checkout>" in result["commands"][0]["stdout"]
    assert result["commands"][0]["stderr"] == "home=<home>"
    assert result["commands"][0]["returncode"] == 0
    assert result["ok"] is True
    assert "339 passed" in result["commands"][0]["stdout"]
    assert str(home) not in str(result)
    assert original == before


def test_wrapped_doctor_path_still_hides_home_prefix(tmp_path):
    home = tmp_path / "local-user"
    checkout = home / "space containing directory" / "plugin"
    wrapped = str(checkout).replace("containing directory", "containing\ndirectory")
    result = runner().redact_local_paths({"stdout": wrapped}, checkout=checkout, home=home)
    assert str(home) not in result["stdout"]
    assert "<home>" in result["stdout"]


def test_verification_runner_includes_actual_offline_derivative_entrypoints(tmp_path):
    import sys

    commands = runner().verification_commands(tmp_path / "dedicated-scratch")
    assert commands[0] == [sys.executable, "-m", "pytest", "-q", "--basetemp", str(tmp_path / "dedicated-scratch")]
    assert [sys.executable, "scripts/exercise_derivatives_offline.py", "--output",
            "artifacts/derivatives_offline_integration.json"] in commands
    assert ["hermes", "plugins", "doctor", ".", "--ci"] in commands
    assert ["hermes", "plugins", "validate", ".", "--install-deps", "--json"] in commands


def test_dependency_preparation_failure_cannot_be_hidden_by_zero_exit_and_ok_json():
    import json

    command = ["hermes", "plugins", "validate", ".", "--install-deps", "--json"]
    stdout = json.dumps({"ok": True, "checks": [{"name": "manifest", "ok": True}], "warnings": []})
    reason = runner().verification_failure(command, 0, stdout,
        "dependency preparation failed: Dependency inputs changed while preparing publication; retry.")
    assert reason == "HERMES_DEPENDENCY_PREPARATION_FAILED"


def test_validator_gate_checks_structured_checks_and_warnings_not_only_ok_field():
    import json

    module = runner()
    command = ["hermes", "plugins", "validate", ".", "--install-deps", "--json"]
    valid = {"ok": True, "checks": [{"name": "manifest", "ok": True}], "warnings": []}
    assert module.verification_failure(command, 0, "Preparing candidate...\n" + json.dumps(valid), "") is None
    assert module.verification_failure(command, 1, json.dumps(valid), "") == "COMMAND_NONZERO_EXIT"
    invalid = {**valid, "checks": [{"name": "manifest", "ok": False}]}
    assert module.verification_failure(command, 0, json.dumps(invalid), "") == "HERMES_VALIDATION_CHECK_FAILED"
    warning = {**valid, "warnings": ["unit-test synthetic warning"]}
    assert module.verification_failure(command, 0, json.dumps(warning), "") == "HERMES_VALIDATION_WARNINGS"
    assert module.verification_failure(command, 0, "not structured output", "") == "HERMES_VALIDATION_RESULT_UNAVAILABLE"
