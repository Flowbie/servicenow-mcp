# tests/integration/test_system_tools.py
"""
Integration tests for system tools against a live ServiceNow instance.
Run with: SN_INTEGRATION_TESTS=1 pytest tests/integration/test_system_tools.py -v -s
"""
import json
import pytest

from servicenow_mcp.tools.system_tools import (
    get_current_user,
    GetCurrentUserParams,
)


@pytest.mark.integration
class TestGetCurrentUserIntegration:

    def test_get_current_user_returns_response(self, live_config, live_auth):
        """Verify get_current_user connects and returns a structured response."""
        params = GetCurrentUserParams()
        result = get_current_user(live_config, live_auth, params)

        print("\n--- get_current_user response ---")
        print(json.dumps(result, indent=2, default=str))

        assert result["success"] is True, f"Expected success, got: {result.get('error')}"

    def test_get_current_user_shape(self, live_config, live_auth):
        """Verify the response includes required user identity fields."""
        params = GetCurrentUserParams()
        result = get_current_user(live_config, live_auth, params)

        assert result["success"] is True, f"Expected success, got: {result.get('error')}"
        user = result.get("user", {})

        print("\n--- user fields ---")
        print(json.dumps(user, indent=2, default=str))

        for field in ["sys_id", "user_name", "display_name", "email"]:
            assert field in user, f"Missing expected field: {field}"

    def test_get_current_user_sys_id_is_non_empty(self, live_config, live_auth):
        """Verify the sys_id field is a non-empty string (needed for get_my_work etc.)."""
        params = GetCurrentUserParams()
        result = get_current_user(live_config, live_auth, params)

        assert result["success"] is True
        sys_id = result.get("user", {}).get("sys_id", "")
        assert sys_id, "sys_id should be a non-empty string"

    def test_get_current_user_with_roles(self, live_config, live_auth):
        """Verify include_roles=True returns a roles list."""
        params = GetCurrentUserParams(include_roles=True)
        result = get_current_user(live_config, live_auth, params)

        print("\n--- get_current_user (with roles) response ---")
        print(json.dumps(result, indent=2, default=str))

        assert result["success"] is True, f"Expected success, got: {result.get('error')}"
        user = result.get("user", {})
        assert "roles" in user, "include_roles=True should add a 'roles' key to user"
        assert isinstance(user["roles"], list)
