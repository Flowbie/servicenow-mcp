# tests/integration/test_script_includes.py
"""
Integration tests for script include tools against a live ServiceNow instance.
READ-ONLY — list and get operations only.
Run with: SN_INTEGRATION_TESTS=1 pytest tests/integration/test_script_includes.py -v -s
"""
import json
import pytest

from servicenow_mcp.tools.script_include_tools import (
    list_script_includes,
    get_script_include,
    ListScriptIncludesParams,
    GetScriptIncludeParams,
)


@pytest.mark.integration
class TestScriptIncludeIntegration:

    def test_list_script_includes_returns_results(self, live_config, live_auth):
        params = ListScriptIncludesParams(limit=5)
        result = list_script_includes(live_config, live_auth, params)
        print("\n--- list_script_includes response ---")
        print(json.dumps(result, indent=2, default=str))
        assert result["success"] is True, f"Expected success, got: {result.get('message')}"
        assert "script_includes" in result
        assert isinstance(result["script_includes"], list)

    def test_list_script_includes_shape(self, live_config, live_auth):
        params = ListScriptIncludesParams(limit=3)
        result = list_script_includes(live_config, live_auth, params)
        assert result["success"] is True
        includes = result["script_includes"]
        if not includes:
            pytest.skip("No script includes on this instance.")
        first = includes[0]
        print("\n--- first script include fields ---")
        print(json.dumps(first, indent=2, default=str))
        for field in ["sys_id", "name"]:
            assert field in first, f"Missing expected field: {field}"

    def test_get_script_include_by_sys_id(self, live_config, live_auth):
        list_result = list_script_includes(live_config, live_auth, ListScriptIncludesParams(limit=1))
        assert list_result["success"] is True
        if not list_result["script_includes"]:
            pytest.skip("No script includes on this instance.")
        sys_id = list_result["script_includes"][0]["sys_id"]
        params = GetScriptIncludeParams(script_include_id=f"sys_id:{sys_id}")
        result = get_script_include(live_config, live_auth, params)
        print(f"\n--- get_script_include({sys_id}) response ---")
        print(json.dumps(result, indent=2, default=str))
        assert result["success"] is True
        assert "script_include" in result

    def test_list_script_includes_limit_respected(self, live_config, live_auth):
        params = ListScriptIncludesParams(limit=2)
        result = list_script_includes(live_config, live_auth, params)
        assert result["success"] is True
        assert len(result["script_includes"]) <= 2
