# tests/integration/test_integration_platform.py
"""
Integration tests for integration platform tools against a live ServiceNow instance.
READ-ONLY — list/get operations only. run_transform and run_import are excluded.
Run with: SN_INTEGRATION_TESTS=1 pytest tests/integration/test_integration_platform.py -v -s
"""
import json
import pytest

from servicenow_mcp.tools.integration_tools import (
    list_rest_messages,
    get_rest_message,
    list_scripted_rest_apis,
    get_scripted_rest_api,
    list_import_sets,
    list_mid_servers,
    get_mid_server_status,
    list_transform_maps,
    ListRestMessagesParams,
    GetRestMessageParams,
    ListScriptedRestApisParams,
    GetScriptedRestApiParams,
    ListImportSetsParams,
    ListMidServersParams,
    GetMidServerStatusParams,
    ListTransformMapsParams,
)


@pytest.mark.integration
class TestIntegrationPlatformIntegration:

    def test_list_rest_messages_returns_results(self, live_config, live_auth):
        """Verify list_rest_messages connects and returns records."""
        params = ListRestMessagesParams(limit=5)
        result = list_rest_messages(live_config, live_auth, params)

        print("\n--- list_rest_messages response ---")
        print(json.dumps(result, indent=2, default=str))

        assert result["success"] is True, f"Expected success, got: {result.get('message')}"
        assert "rest_messages" in result
        assert isinstance(result["rest_messages"], list)

    def test_get_rest_message_by_sys_id(self, live_config, live_auth):
        """Verify get_rest_message returns full REST message details."""
        list_result = list_rest_messages(live_config, live_auth, ListRestMessagesParams(limit=1))
        assert list_result["success"] is True

        if not list_result["rest_messages"]:
            pytest.skip("No REST messages on this instance.")

        sys_id = list_result["rest_messages"][0]["sys_id"]

        params = GetRestMessageParams(message_sys_id=sys_id)
        result = get_rest_message(live_config, live_auth, params)

        print(f"\n--- get_rest_message({sys_id}) response ---")
        print(json.dumps(result, indent=2, default=str))

        assert result["success"] is True
        assert "message_record" in result

    def test_list_scripted_rest_apis_returns_results(self, live_config, live_auth):
        """Verify list_scripted_rest_apis returns records."""
        params = ListScriptedRestApisParams(limit=5)
        result = list_scripted_rest_apis(live_config, live_auth, params)

        print("\n--- list_scripted_rest_apis response ---")
        print(json.dumps(result, indent=2, default=str))

        assert result["success"] is True
        assert "scripted_rest_apis" in result
        assert isinstance(result["scripted_rest_apis"], list)

    def test_list_mid_servers_returns_results(self, live_config, live_auth):
        """Verify list_mid_servers returns MID server records."""
        params = ListMidServersParams()
        result = list_mid_servers(live_config, live_auth, params)

        print("\n--- list_mid_servers response ---")
        print(json.dumps(result, indent=2, default=str))

        assert result["success"] is True
        assert "mid_servers" in result
        assert isinstance(result["mid_servers"], list)

    def test_list_import_sets_returns_results(self, live_config, live_auth):
        """Verify list_import_sets returns records."""
        params = ListImportSetsParams(limit=5)
        result = list_import_sets(live_config, live_auth, params)

        print("\n--- list_import_sets response ---")
        print(json.dumps(result, indent=2, default=str))

        assert result["success"] is True
        assert "import_sets" in result
        assert isinstance(result["import_sets"], list)

    def test_list_transform_maps_returns_results(self, live_config, live_auth):
        """Verify list_transform_maps returns records."""
        params = ListTransformMapsParams(limit=5)
        result = list_transform_maps(live_config, live_auth, params)

        print("\n--- list_transform_maps response ---")
        print(json.dumps(result, indent=2, default=str))

        assert result["success"] is True
        assert "transform_maps" in result
        assert isinstance(result["transform_maps"], list)

    def test_get_mid_server_status(self, live_config, live_auth):
        """Verify get_mid_server_status returns status for a real MID server."""
        mid_result = list_mid_servers(live_config, live_auth, ListMidServersParams())

        if not mid_result.get("success") or not mid_result.get("mid_servers"):
            pytest.skip("No MID servers found on this instance.")

        mid_id = mid_result["mid_servers"][0]["sys_id"]

        params = GetMidServerStatusParams(server_sys_id=mid_id)
        result = get_mid_server_status(live_config, live_auth, params)

        print(f"\n--- get_mid_server_status({mid_id}) response ---")
        print(json.dumps(result, indent=2, default=str))

        assert "success" in result
