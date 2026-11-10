"""CLI behavior without a configured provider must be deterministic."""
import subprocess
import sys
import json


def test_cli_help_works_without_network_or_credentials():
    p = subprocess.run([sys.executable, "-m", "tradeguard", "--help"], capture_output=True, text=True)
    assert p.returncode == 0
    assert "analyze" in p.stdout
    assert "walk-forward" in p.stdout


def test_cli_refuses_implicit_network_access():
    p = subprocess.run([sys.executable, "-m", "tradeguard", "analyze", "--symbol", "AAPL"], capture_output=True, text=True)
    assert p.returncode == 2
    result = json.loads(p.stdout)
    assert result["success"] is False
    assert "allow-public-data" in result["error"]


def test_cli_catalog_is_offline_and_filters_one_family():
    result = subprocess.run([sys.executable, "-m", "tradeguard", "strategies", "--strategy-id", "trend_following"], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["count"] == 1
    assert data["exhaustive"] is False
    assert data["strategies"][0]["id"] == "trend_following"
