"""
Tests for user role management tools.

CRUD operations for sys_user and sys_user_group are covered by table_tools
(test_table_tools.py). This file covers the role management functions that
require multi-step platform logic beyond simple CRUD.
"""

import unittest
from unittest.mock import MagicMock, patch

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.user_tools import (
    GrantRoleToGroupParams,
    GrantRoleToUserParams,
    ListGroupRolesParams,
    ListUserRolesParams,
    RevokeRoleFromGroupParams,
    RevokeRoleFromUserParams,
    get_role_id,
    grant_role_to_group,
    grant_role_to_user,
    list_group_roles,
    list_user_roles,
    revoke_role_from_group,
    revoke_role_from_user,
)
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig


class TestUserRoleTools(unittest.TestCase):
    """Tests for user and group role management tools."""

    def setUp(self):
        """Set up test environment."""
        self.config = ServerConfig(
            instance_url="https://example.service-now.com",
            auth=AuthConfig(
                type=AuthType.BASIC,
                basic=BasicAuthConfig(username="admin", password="password"),
            ),
        )
        self.auth_manager = AuthManager(self.config.auth)
        self.auth_manager.get_headers = MagicMock(
            return_value={"Authorization": "Basic YWRtaW46cGFzc3dvcmQ="}
        )
        self.role_sys_id = "role_abc123"
        self.user_sys_id = "user_xyz789"
        self.group_sys_id = "group_def456"

    def _mock_role_lookup(self, mock_get, role_sys_id: str):
        """Configure the first get call to return a role lookup result."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "result": [{"sys_id": role_sys_id}]
        }
        mock_get.return_value = mock_response
        return mock_response

    # ------------------------------------------------------------------
    # get_role_id
    # ------------------------------------------------------------------

    @patch("requests.get")
    def test_get_role_id_found(self, mock_get):
        """get_role_id returns sys_id when role exists."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"result": [{"sys_id": self.role_sys_id}]}
        mock_get.return_value = mock_response

        result = get_role_id(self.config, self.auth_manager, "itil")

        self.assertEqual(result, self.role_sys_id)
        mock_get.assert_called_once()

    @patch("requests.get")
    def test_get_role_id_not_found(self, mock_get):
        """get_role_id returns None when role does not exist."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"result": []}
        mock_get.return_value = mock_response

        result = get_role_id(self.config, self.auth_manager, "nonexistent_role")

        self.assertIsNone(result)

    # ------------------------------------------------------------------
    # grant_role_to_user
    # ------------------------------------------------------------------

    @patch("requests.post")
    @patch("requests.get")
    def test_grant_role_to_user_success(self, mock_get, mock_post):
        """grant_role_to_user creates a sys_user_has_role record."""
        # First call: role lookup; second call: direct-grant check
        role_resp = MagicMock()
        role_resp.raise_for_status = MagicMock()
        role_resp.json.return_value = {"result": [{"sys_id": self.role_sys_id}]}

        check_resp = MagicMock()
        check_resp.raise_for_status = MagicMock()
        check_resp.json.return_value = {"result": []}  # no existing direct grant

        mock_get.side_effect = [role_resp, check_resp]

        post_resp = MagicMock()
        post_resp.raise_for_status = MagicMock()
        post_resp.json.return_value = {"result": {"sys_id": "grant_001"}}
        mock_post.return_value = post_resp

        params = GrantRoleToUserParams(user_sys_id=self.user_sys_id, role_name="itil")
        result = grant_role_to_user(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        self.assertEqual(result["sys_id"], "grant_001")
        mock_post.assert_called_once()

    @patch("requests.get")
    def test_grant_role_to_user_role_not_found(self, mock_get):
        """grant_role_to_user returns failure when role does not exist."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"result": []}
        mock_get.return_value = mock_response

        params = GrantRoleToUserParams(user_sys_id=self.user_sys_id, role_name="no_such_role")
        result = grant_role_to_user(self.config, self.auth_manager, params)

        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    @patch("requests.get")
    def test_grant_role_to_user_already_exists(self, mock_get):
        """grant_role_to_user returns already_exists=True when direct grant exists."""
        role_resp = MagicMock()
        role_resp.raise_for_status = MagicMock()
        role_resp.json.return_value = {"result": [{"sys_id": self.role_sys_id}]}

        existing_grant_resp = MagicMock()
        existing_grant_resp.raise_for_status = MagicMock()
        existing_grant_resp.json.return_value = {"result": [{"sys_id": "existing_grant"}]}

        mock_get.side_effect = [role_resp, existing_grant_resp]

        params = GrantRoleToUserParams(user_sys_id=self.user_sys_id, role_name="itil")
        result = grant_role_to_user(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        self.assertTrue(result.get("already_exists"))

    # ------------------------------------------------------------------
    # revoke_role_from_user
    # ------------------------------------------------------------------

    @patch("requests.delete")
    @patch("requests.get")
    def test_revoke_role_from_user_success(self, mock_get, mock_delete):
        """revoke_role_from_user deletes the direct grant record."""
        role_resp = MagicMock()
        role_resp.raise_for_status = MagicMock()
        role_resp.json.return_value = {"result": [{"sys_id": self.role_sys_id}]}

        grant_resp = MagicMock()
        grant_resp.raise_for_status = MagicMock()
        grant_resp.json.return_value = {"result": [{"sys_id": "grant_001"}]}

        mock_get.side_effect = [role_resp, grant_resp]

        del_resp = MagicMock()
        del_resp.raise_for_status = MagicMock()
        mock_delete.return_value = del_resp

        params = RevokeRoleFromUserParams(user_sys_id=self.user_sys_id, role_name="itil")
        result = revoke_role_from_user(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        self.assertEqual(result["sys_id"], "grant_001")
        mock_delete.assert_called_once()

    @patch("requests.get")
    def test_revoke_role_from_user_no_direct_grant(self, mock_get):
        """revoke_role_from_user returns failure when no direct grant exists."""
        role_resp = MagicMock()
        role_resp.raise_for_status = MagicMock()
        role_resp.json.return_value = {"result": [{"sys_id": self.role_sys_id}]}

        no_grant_resp = MagicMock()
        no_grant_resp.raise_for_status = MagicMock()
        no_grant_resp.json.return_value = {"result": []}

        mock_get.side_effect = [role_resp, no_grant_resp]

        params = RevokeRoleFromUserParams(user_sys_id=self.user_sys_id, role_name="itil")
        result = revoke_role_from_user(self.config, self.auth_manager, params)

        self.assertFalse(result["success"])
        self.assertIn("No direct grant", result["message"])

    # ------------------------------------------------------------------
    # grant_role_to_group
    # ------------------------------------------------------------------

    @patch("requests.post")
    @patch("requests.get")
    def test_grant_role_to_group_success(self, mock_get, mock_post):
        """grant_role_to_group creates a sys_group_has_role record."""
        role_resp = MagicMock()
        role_resp.raise_for_status = MagicMock()
        role_resp.json.return_value = {"result": [{"sys_id": self.role_sys_id}]}
        mock_get.return_value = role_resp

        post_resp = MagicMock()
        post_resp.raise_for_status = MagicMock()
        post_resp.json.return_value = {"result": {"sys_id": "group_grant_001"}}
        mock_post.return_value = post_resp

        params = GrantRoleToGroupParams(group_sys_id=self.group_sys_id, role_name="itil")
        result = grant_role_to_group(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        self.assertEqual(result["sys_id"], "group_grant_001")
        mock_post.assert_called_once()

    @patch("requests.get")
    def test_grant_role_to_group_role_not_found(self, mock_get):
        """grant_role_to_group returns failure when role does not exist."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"result": []}
        mock_get.return_value = mock_response

        params = GrantRoleToGroupParams(group_sys_id=self.group_sys_id, role_name="no_such_role")
        result = grant_role_to_group(self.config, self.auth_manager, params)

        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    # ------------------------------------------------------------------
    # revoke_role_from_group
    # ------------------------------------------------------------------

    @patch("requests.delete")
    @patch("requests.get")
    def test_revoke_role_from_group_success(self, mock_get, mock_delete):
        """revoke_role_from_group deletes the direct grant record."""
        role_resp = MagicMock()
        role_resp.raise_for_status = MagicMock()
        role_resp.json.return_value = {"result": [{"sys_id": self.role_sys_id}]}

        grant_resp = MagicMock()
        grant_resp.raise_for_status = MagicMock()
        grant_resp.json.return_value = {"result": [{"sys_id": "group_grant_001"}]}

        mock_get.side_effect = [role_resp, grant_resp]

        del_resp = MagicMock()
        del_resp.raise_for_status = MagicMock()
        mock_delete.return_value = del_resp

        params = RevokeRoleFromGroupParams(group_sys_id=self.group_sys_id, role_name="itil")
        result = revoke_role_from_group(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        self.assertEqual(result["sys_id"], "group_grant_001")
        mock_delete.assert_called_once()

    @patch("requests.get")
    def test_revoke_role_from_group_no_direct_grant(self, mock_get):
        """revoke_role_from_group returns failure when no direct grant exists."""
        role_resp = MagicMock()
        role_resp.raise_for_status = MagicMock()
        role_resp.json.return_value = {"result": [{"sys_id": self.role_sys_id}]}

        no_grant_resp = MagicMock()
        no_grant_resp.raise_for_status = MagicMock()
        no_grant_resp.json.return_value = {"result": []}

        mock_get.side_effect = [role_resp, no_grant_resp]

        params = RevokeRoleFromGroupParams(group_sys_id=self.group_sys_id, role_name="itil")
        result = revoke_role_from_group(self.config, self.auth_manager, params)

        self.assertFalse(result["success"])
        self.assertIn("No direct grant", result["message"])

    # ------------------------------------------------------------------
    # list_user_roles
    # ------------------------------------------------------------------

    @patch("requests.get")
    def test_list_user_roles_success(self, mock_get):
        """list_user_roles returns all roles for a user."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "result": [
                {"sys_id": "r1", "role": {"display_value": "itil"}, "inherited": "false"},
                {"sys_id": "r2", "role": {"display_value": "catalog_admin"}, "inherited": "true"},
            ]
        }
        mock_get.return_value = mock_response

        params = ListUserRolesParams(user_sys_id=self.user_sys_id)
        result = list_user_roles(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 2)
        self.assertEqual(len(result["roles"]), 2)

    @patch("requests.get")
    def test_list_user_roles_direct_only(self, mock_get):
        """list_user_roles with include_inherited=False adds the inherited filter."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"result": []}
        mock_get.return_value = mock_response

        params = ListUserRolesParams(user_sys_id=self.user_sys_id, include_inherited=False)
        result = list_user_roles(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        call_params = mock_get.call_args[1]["params"]
        self.assertIn("inherited=false", call_params["sysparm_query"])

    # ------------------------------------------------------------------
    # list_group_roles
    # ------------------------------------------------------------------

    @patch("requests.get")
    def test_list_group_roles_success(self, mock_get):
        """list_group_roles returns all roles for a group."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "result": [
                {"sys_id": "gr1", "role": {"display_value": "itil"}, "inherited": "false"},
            ]
        }
        mock_get.return_value = mock_response

        params = ListGroupRolesParams(group_sys_id=self.group_sys_id)
        result = list_group_roles(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["group_sys_id"], self.group_sys_id)

    @patch("requests.get")
    def test_list_group_roles_direct_only(self, mock_get):
        """list_group_roles with include_inherited=False adds the inherited filter."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"result": []}
        mock_get.return_value = mock_response

        params = ListGroupRolesParams(group_sys_id=self.group_sys_id, include_inherited=False)
        result = list_group_roles(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        call_params = mock_get.call_args[1]["params"]
        self.assertIn("inherited=false", call_params["sysparm_query"])


if __name__ == "__main__":
    unittest.main()
