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
