# tests/integration/test_integration_platform.py
"""
Integration tests for integration platform compound tools against a live ServiceNow instance.
READ-ONLY — get operations only.
Run with: SN_INTEGRATION_TESTS=1 pytest tests/integration/test_integration_platform.py -v -s

CRUD for integration tables (sys_rest_message, sys_ws_definition, sys_import_set,
ecc_agent, sys_transform_map) uses table_tools (query_records/get_record).
"""
import json
import pytest

from servicenow_mcp.tools.integration_tools import (
    get_rest_message,
    get_scripted_rest_api,
    GetRestMessageParams,
    GetScriptedRestApiParams,
)


@pytest.mark.integration
class TestIntegrationPlatformIntegration:

    def test_get_rest_message_by_name(self, live_config, live_auth):
        """Verify get_rest_message returns a REST message with its HTTP methods."""
        # Attempt to look up a common OOB REST message; skip if not found.
        params = GetRestMessageParams(message_name="Test REST Message")
        result = get_rest_message(live_config, live_auth, params)

        print("\n--- get_rest_message response ---")
        print(json.dumps(result, indent=2, default=str))

        if not result["success"]:
            pytest.skip("No matching REST message on this instance.")

        assert "message_record" in result
        assert "http_methods" in result
        assert isinstance(result["http_methods"], list)

    def test_get_scripted_rest_api_by_name(self, live_config, live_auth):
        """Verify get_scripted_rest_api returns a Scripted REST API with its operations."""
        params = GetScriptedRestApiParams(api_name="Test Scripted REST API")
        result = get_scripted_rest_api(live_config, live_auth, params)

        print("\n--- get_scripted_rest_api response ---")
        print(json.dumps(result, indent=2, default=str))

        if not result["success"]:
            pytest.skip("No matching Scripted REST API on this instance.")

        assert "api_record" in result
        assert "operations" in result
        assert isinstance(result["operations"], list)
