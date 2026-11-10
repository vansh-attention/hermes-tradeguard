"""The native plugin must declare exactly what it registers; no network on load."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_plugin():
    spec = importlib.util.spec_from_file_location("tradeguard_plugin_test", ROOT / "__init__.py", submodule_search_locations=[str(ROOT)])
    module = importlib.util.module_from_spec(spec)
    import sys
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class FakeContext:
    def __init__(self):
        self.tools = {}

    def register_tool(self, *, name, toolset, schema, handler):
        assert toolset == "tradeguard"
        assert schema["name"] == name
        self.tools[name] = handler

    def get_config(self, key, default=None):
        return default


def test_plugin_registers_pure_analysis_and_no_order_tools():
    plugin = load_plugin()
    ctx = FakeContext()
    plugin.register(ctx)
    assert set(ctx.tools) == {"tradeguard_equity_research", "tradeguard_public_history", "tradeguard_walk_forward", "tradeguard_microstructure", "tradeguard_rank", "tradeguard_strategy_catalog", "tradeguard_recommend_tickers"}
    response = json.loads(ctx.tools["tradeguard_public_history"]({"symbol": "AAPL"}))
    assert response["success"] is False
    assert response["code"] == "PUBLIC_DATA_DISABLED"


def test_native_catalog_handler_is_callable_and_never_claims_validated_alpha():
    ctx = FakeContext()
    load_plugin().register(ctx)
    result = json.loads(ctx.tools["tradeguard_strategy_catalog"]({"strategy_id": "market_making"}))
    assert result["success"] is True
    assert result["count"] == 1
    assert result["strategies"][0]["implementation_status"] == "researched_only"
    assert result["strategies"][0]["performance_validated"] is False


def test_missing_tool_arguments_return_json_not_tracebacks():
    ctx = FakeContext()
    load_plugin().register(ctx)
    for name, handler in ctx.tools.items():
        if name == "tradeguard_strategy_catalog":
            continue  # All catalog filters are optional.
        response = json.loads(handler({}))
        assert response["success"] is False, name
        assert response["research_only"] is True


def test_string_false_cannot_enable_network():
    class BadConfig(FakeContext):
        def get_config(self, key, default=None):
            return "false"
    ctx = BadConfig()
    load_plugin().register(ctx)
    response = json.loads(ctx.tools["tradeguard_public_history"]({"symbol": "AAPL"}))
    assert response["code"] == "PUBLIC_DATA_DISABLED"
