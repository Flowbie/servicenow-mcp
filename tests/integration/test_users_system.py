"""
Integration tests for user management tools against a live ServiceNow instance.
Run with: SN_INTEGRATION_TESTS=1 pytest tests/integration/test_users_system.py -v -s
"""
import json
import pytest

from servicenow_mcp.tools.user_tools import (
    list_users,
    get_user,
    list_groups,
    ListUsersParams,
    GetUserParams,
    ListGroupsParams,
)


@pytest.mark.integration
class TestUserManagementIntegration:
    """Integration tests for user and group management tools."""

    def test_list_users_returns_results(self, live_config, live_auth):
        """list_users with limit=5 should return success and a 'users' key."""
        params = ListUsersParams(limit=5)
        result = list_users(live_config, live_auth, params)
        print(json.dumps(result, indent=2, default=str))
        assert result["success"] is True
        assert "users" in result

    def test_list_users_shape(self, live_config, live_auth):
        """First user record should contain sys_id and user_name fields."""
        params = ListUsersParams(limit=5)
        result = list_users(live_config, live_auth, params)
        print(json.dumps(result, indent=2, default=str))
        if not result.get("users"):
            pytest.skip("No users returned from instance — cannot verify shape.")
        first_user = result["users"][0]
        assert "sys_id" in first_user, f"Expected 'sys_id' in user record, got keys: {list(first_user.keys())}"
        assert "user_name" in first_user, f"Expected 'user_name' in user record, got keys: {list(first_user.keys())}"

    def test_list_users_limit_respected(self, live_config, live_auth):
        """list_users with limit=2 should return at most 2 users."""
        params = ListUsersParams(limit=2)
        result = list_users(live_config, live_auth, params)
        print(json.dumps(result, indent=2, default=str))
        assert result["success"] is True
        assert len(result["users"]) <= 2

    def test_list_users_with_query(self, live_config, live_auth):
        """list_users with a query string should succeed (LIKE search across name/user_name/email)."""
        params = ListUsersParams(limit=5, query="admin")
        result = list_users(live_config, live_auth, params)
        print(json.dumps(result, indent=2, default=str))
        assert result["success"] is True
        assert "users" in result

    def test_get_user_by_sys_id(self, live_config, live_auth):
        """get_user with a real sys_id obtained from list_users should return the user record."""
        # First retrieve a real sys_id
        list_result = list_users(live_config, live_auth, ListUsersParams(limit=1))
        if not list_result.get("users"):
            pytest.skip("No users available on instance — cannot test get_user.")
        sys_id = list_result["users"][0]["sys_id"]

        params = GetUserParams(user_id=sys_id)
        result = get_user(live_config, live_auth, params)
        print(json.dumps(result, indent=2, default=str))
        assert result["success"] is True
        assert "user" in result

    def test_get_user_invalid_sys_id(self, live_config, live_auth):
        """get_user with a nonexistent sys_id should return success=False."""
        params = GetUserParams(user_id="nonexistent_000")
        result = get_user(live_config, live_auth, params)
        print(json.dumps(result, indent=2, default=str))
        assert result["success"] is False

    def test_list_groups_returns_results(self, live_config, live_auth):
        """list_groups with limit=5 should return success and a 'groups' key."""
        params = ListGroupsParams(limit=5)
        result = list_groups(live_config, live_auth, params)
        print(json.dumps(result, indent=2, default=str))
        assert result["success"] is True
        assert "groups" in result

    def test_list_groups_shape(self, live_config, live_auth):
        """First group record should contain sys_id and name fields."""
        params = ListGroupsParams(limit=5)
        result = list_groups(live_config, live_auth, params)
        print(json.dumps(result, indent=2, default=str))
        if not result.get("groups"):
            pytest.skip("No groups returned from instance — cannot verify shape.")
        first_group = result["groups"][0]
        assert "sys_id" in first_group, f"Expected 'sys_id' in group record, got keys: {list(first_group.keys())}"
        assert "name" in first_group, f"Expected 'name' in group record, got keys: {list(first_group.keys())}"

    def test_list_groups_limit_respected(self, live_config, live_auth):
        """list_groups with limit=2 should return at most 2 groups."""
        params = ListGroupsParams(limit=2)
        result = list_groups(live_config, live_auth, params)
        print(json.dumps(result, indent=2, default=str))
        assert result["success"] is True
        assert len(result["groups"]) <= 2
