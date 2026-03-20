"""
Tests for Phase 8 user/role membership tools.

Covers: grant_role_to_user, revoke_role_from_user, grant_role_to_group,
revoke_role_from_group, list_user_roles, list_group_roles.
"""

import unittest
from unittest.mock import MagicMock, patch

import requests

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.user_tools import (
    GrantRoleToGroupParams,
    GrantRoleToUserParams,
    ListGroupRolesParams,
    ListUserRolesParams,
    RevokeRoleFromGroupParams,
    RevokeRoleFromUserParams,
    grant_role_to_group,
    grant_role_to_user,
    list_group_roles,
    list_user_roles,
    revoke_role_from_group,
    revoke_role_from_user,
)
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig


class TestUserRoleTools(unittest.TestCase):
    """Tests for Phase 8 user/role membership tools."""

    def setUp(self):
        self.auth_config = AuthConfig(
            type=AuthType.BASIC,
            basic=BasicAuthConfig(username="test_user", password="test_password"),
        )
        self.config = ServerConfig(
            instance_url="https://test.service-now.com",
            auth=self.auth_config,
        )
        self.auth_manager = MagicMock(spec=AuthManager)
        self.auth_manager.get_headers.return_value = {"Authorization": "Bearer FAKE_TOKEN"}

    # -----------------------------------------------------------------------
    # grant_role_to_user
    # -----------------------------------------------------------------------

    @patch("servicenow_mcp.tools.user_tools.requests.get")
    @patch("servicenow_mcp.tools.user_tools.requests.post")
    def test_grant_role_to_user_success(self, mock_post, mock_get):
        """grant_role_to_user resolves role name then POSTs without inherited field."""
        # First GET: role lookup; second GET: check_user_has_role
        mock_get.side_effect = [
            MagicMock(**{
                "json.return_value": {"result": [{"sys_id": "role1"}]},
                "raise_for_status": MagicMock(),
            }),
            MagicMock(**{
                "json.return_value": {"result": []},  # user does NOT already have role
                "raise_for_status": MagicMock(),
            }),
        ]
        mock_post.return_value = MagicMock(**{
            "json.return_value": {"result": {"sys_id": "grant1"}},
            "raise_for_status": MagicMock(),
        })

        params = GrantRoleToUserParams(user_sys_id="user1", role_name="itil")
        result = grant_role_to_user(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        self.assertEqual(result["sys_id"], "grant1")
        sent_data = mock_post.call_args[1]["json"]
        self.assertEqual(sent_data["user"], "user1")
        self.assertEqual(sent_data["role"], "role1")
        # CRITICAL: inherited must NOT be set
        self.assertNotIn("inherited", sent_data)
        called_url = mock_post.call_args[0][0]
        self.assertIn("sys_user_has_role", called_url)

    @patch("servicenow_mcp.tools.user_tools.requests.get")
    def test_grant_role_to_user_role_not_found(self, mock_get):
        """grant_role_to_user returns error when role name not found."""
        mock_get.return_value = MagicMock(**{
            "json.return_value": {"result": []},
            "raise_for_status": MagicMock(),
        })
        result = grant_role_to_user(
            self.config, self.auth_manager,
            GrantRoleToUserParams(user_sys_id="user1", role_name="nonexistent_role")
        )
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    @patch("servicenow_mcp.tools.user_tools.requests.get")
    def test_grant_role_to_user_already_has_role(self, mock_get):
        """grant_role_to_user returns success without POST when user already has role."""
        mock_get.side_effect = [
            MagicMock(**{
                "json.return_value": {"result": [{"sys_id": "role1"}]},
                "raise_for_status": MagicMock(),
            }),
            MagicMock(**{
                "json.return_value": {"result": [{"sys_id": "existing_grant"}]},
                "raise_for_status": MagicMock(),
            }),
        ]
        result = grant_role_to_user(
            self.config, self.auth_manager,
            GrantRoleToUserParams(user_sys_id="user1", role_name="itil")
        )
        self.assertTrue(result["success"])
        self.assertTrue(result.get("already_exists"))

    @patch("servicenow_mcp.tools.user_tools.requests.get")
    @patch("servicenow_mcp.tools.user_tools.requests.post")
    def test_grant_role_to_user_post_error(self, mock_post, mock_get):
        """grant_role_to_user handles POST errors."""
        mock_get.side_effect = [
            MagicMock(**{
                "json.return_value": {"result": [{"sys_id": "role1"}]},
                "raise_for_status": MagicMock(),
            }),
            MagicMock(**{
                "json.return_value": {"result": []},
                "raise_for_status": MagicMock(),
            }),
        ]
        mock_post.side_effect = requests.RequestException("403 error")
        result = grant_role_to_user(
            self.config, self.auth_manager,
            GrantRoleToUserParams(user_sys_id="user1", role_name="itil")
        )
        self.assertFalse(result["success"])

    # -----------------------------------------------------------------------
    # revoke_role_from_user
    # -----------------------------------------------------------------------

    @patch("servicenow_mcp.tools.user_tools.requests.get")
    @patch("servicenow_mcp.tools.user_tools.requests.delete")
    def test_revoke_role_from_user_success(self, mock_delete, mock_get):
        """revoke_role_from_user looks up direct grant then DELETEs it."""
        mock_get.side_effect = [
            MagicMock(**{
                "json.return_value": {"result": [{"sys_id": "role1"}]},
                "raise_for_status": MagicMock(),
            }),
            MagicMock(**{
                "json.return_value": {"result": [{"sys_id": "grant1"}]},
                "raise_for_status": MagicMock(),
            }),
        ]
        mock_delete.return_value = MagicMock(raise_for_status=MagicMock())

        result = revoke_role_from_user(
            self.config, self.auth_manager,
            RevokeRoleFromUserParams(user_sys_id="user1", role_name="itil")
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["sys_id"], "grant1")
        # Verify the lookup used inherited=false filter
        lookup_query = mock_get.call_args_list[1][1]["params"]["sysparm_query"]
        self.assertIn("inherited=false", lookup_query)
        # Verify DELETE was called with grant sys_id in URL
        delete_url = mock_delete.call_args[0][0]
        self.assertIn("grant1", delete_url)

    @patch("servicenow_mcp.tools.user_tools.requests.get")
    def test_revoke_role_from_user_no_direct_grant(self, mock_get):
        """revoke_role_from_user returns error when no direct grant exists."""
        mock_get.side_effect = [
            MagicMock(**{
                "json.return_value": {"result": [{"sys_id": "role1"}]},
                "raise_for_status": MagicMock(),
            }),
            MagicMock(**{
                "json.return_value": {"result": []},  # no direct grant found
                "raise_for_status": MagicMock(),
            }),
        ]
        result = revoke_role_from_user(
            self.config, self.auth_manager,
            RevokeRoleFromUserParams(user_sys_id="user1", role_name="itil")
        )
        self.assertFalse(result["success"])
        self.assertIn("Inherited grants cannot be removed", result["message"])

    @patch("servicenow_mcp.tools.user_tools.requests.get")
    def test_revoke_role_from_user_role_not_found(self, mock_get):
        """revoke_role_from_user returns error when role name not found."""
        mock_get.return_value = MagicMock(**{
            "json.return_value": {"result": []},
            "raise_for_status": MagicMock(),
        })
        result = revoke_role_from_user(
            self.config, self.auth_manager,
            RevokeRoleFromUserParams(user_sys_id="user1", role_name="ghost_role")
        )
        self.assertFalse(result["success"])

    # -----------------------------------------------------------------------
    # grant_role_to_group
    # -----------------------------------------------------------------------

    @patch("servicenow_mcp.tools.user_tools.requests.get")
    @patch("servicenow_mcp.tools.user_tools.requests.post")
    def test_grant_role_to_group_success(self, mock_post, mock_get):
        """grant_role_to_group POSTs to sys_group_has_role without inherited."""
        mock_get.return_value = MagicMock(**{
            "json.return_value": {"result": [{"sys_id": "role1"}]},
            "raise_for_status": MagicMock(),
        })
        mock_post.return_value = MagicMock(**{
            "json.return_value": {"result": {"sys_id": "grp_grant1"}},
            "raise_for_status": MagicMock(),
        })

        result = grant_role_to_group(
            self.config, self.auth_manager,
            GrantRoleToGroupParams(group_sys_id="grp1", role_name="itil")
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["sys_id"], "grp_grant1")
        sent_data = mock_post.call_args[1]["json"]
        self.assertEqual(sent_data["group"], "grp1")
        self.assertEqual(sent_data["role"], "role1")
        self.assertNotIn("inherited", sent_data)
        called_url = mock_post.call_args[0][0]
        self.assertIn("sys_group_has_role", called_url)

    @patch("servicenow_mcp.tools.user_tools.requests.get")
    def test_grant_role_to_group_role_not_found(self, mock_get):
        """grant_role_to_group returns error when role not found."""
        mock_get.return_value = MagicMock(**{
            "json.return_value": {"result": []},
            "raise_for_status": MagicMock(),
        })
        result = grant_role_to_group(
            self.config, self.auth_manager,
            GrantRoleToGroupParams(group_sys_id="grp1", role_name="ghost_role")
        )
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.user_tools.requests.get")
    @patch("servicenow_mcp.tools.user_tools.requests.post")
    def test_grant_role_to_group_post_error(self, mock_post, mock_get):
        """grant_role_to_group handles POST errors."""
        mock_get.return_value = MagicMock(**{
            "json.return_value": {"result": [{"sys_id": "role1"}]},
            "raise_for_status": MagicMock(),
        })
        mock_post.side_effect = requests.RequestException("500 error")
        result = grant_role_to_group(
            self.config, self.auth_manager,
            GrantRoleToGroupParams(group_sys_id="grp1", role_name="itil")
        )
        self.assertFalse(result["success"])

    # -----------------------------------------------------------------------
    # revoke_role_from_group
    # -----------------------------------------------------------------------

    @patch("servicenow_mcp.tools.user_tools.requests.get")
    @patch("servicenow_mcp.tools.user_tools.requests.delete")
    def test_revoke_role_from_group_success(self, mock_delete, mock_get):
        """revoke_role_from_group finds direct grant and DELETEs from sys_group_has_role."""
        mock_get.side_effect = [
            MagicMock(**{
                "json.return_value": {"result": [{"sys_id": "role1"}]},
                "raise_for_status": MagicMock(),
            }),
            MagicMock(**{
                "json.return_value": {"result": [{"sys_id": "grp_grant1"}]},
                "raise_for_status": MagicMock(),
            }),
        ]
        mock_delete.return_value = MagicMock(raise_for_status=MagicMock())

        result = revoke_role_from_group(
            self.config, self.auth_manager,
            RevokeRoleFromGroupParams(group_sys_id="grp1", role_name="itil")
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["sys_id"], "grp_grant1")
        lookup_query = mock_get.call_args_list[1][1]["params"]["sysparm_query"]
        self.assertIn("inherited=false", lookup_query)
        delete_url = mock_delete.call_args[0][0]
        self.assertIn("grp_grant1", delete_url)

    @patch("servicenow_mcp.tools.user_tools.requests.get")
    def test_revoke_role_from_group_no_direct_grant(self, mock_get):
        """revoke_role_from_group returns error when only inherited grant exists."""
        mock_get.side_effect = [
            MagicMock(**{
                "json.return_value": {"result": [{"sys_id": "role1"}]},
                "raise_for_status": MagicMock(),
            }),
            MagicMock(**{
                "json.return_value": {"result": []},
                "raise_for_status": MagicMock(),
            }),
        ]
        result = revoke_role_from_group(
            self.config, self.auth_manager,
            RevokeRoleFromGroupParams(group_sys_id="grp1", role_name="itil")
        )
        self.assertFalse(result["success"])
        self.assertIn("Inherited grants cannot be removed", result["message"])

    # -----------------------------------------------------------------------
    # list_user_roles
    # -----------------------------------------------------------------------

    @patch("servicenow_mcp.tools.user_tools.requests.get")
    def test_list_user_roles_success(self, mock_get):
        """list_user_roles queries sys_user_has_role filtered by user sys_id."""
        mock_get.return_value = MagicMock(**{
            "json.return_value": {
                "result": [
                    {"sys_id": "g1", "role": {"display_value": "itil"}, "inherited": "false"},
                    {"sys_id": "g2", "role": {"display_value": "admin"}, "inherited": "true"},
                ]
            },
            "raise_for_status": MagicMock(),
        })

        result = list_user_roles(
            self.config, self.auth_manager,
            ListUserRolesParams(user_sys_id="user1")
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 2)
        self.assertEqual(result["user_sys_id"], "user1")
        called_url = mock_get.call_args[0][0]
        self.assertIn("sys_user_has_role", called_url)
        query = mock_get.call_args[1]["params"]["sysparm_query"]
        self.assertIn("user=user1", query)

    @patch("servicenow_mcp.tools.user_tools.requests.get")
    def test_list_user_roles_exclude_inherited(self, mock_get):
        """list_user_roles with include_inherited=False adds inherited=false to query."""
        mock_get.return_value = MagicMock(**{
            "json.return_value": {"result": [{"sys_id": "g1"}]},
            "raise_for_status": MagicMock(),
        })

        list_user_roles(
            self.config, self.auth_manager,
            ListUserRolesParams(user_sys_id="user1", include_inherited=False)
        )

        query = mock_get.call_args[1]["params"]["sysparm_query"]
        self.assertIn("inherited=false", query)

    @patch("servicenow_mcp.tools.user_tools.requests.get")
    def test_list_user_roles_http_error(self, mock_get):
        """list_user_roles handles HTTP errors."""
        mock_get.side_effect = requests.RequestException("500 error")
        result = list_user_roles(
            self.config, self.auth_manager,
            ListUserRolesParams(user_sys_id="user1")
        )
        self.assertFalse(result["success"])

    # -----------------------------------------------------------------------
    # list_group_roles
    # -----------------------------------------------------------------------

    @patch("servicenow_mcp.tools.user_tools.requests.get")
    def test_list_group_roles_success(self, mock_get):
        """list_group_roles queries sys_group_has_role filtered by group sys_id."""
        mock_get.return_value = MagicMock(**{
            "json.return_value": {
                "result": [
                    {"sys_id": "g1", "role": {"display_value": "itil"}, "inherited": "false"},
                ]
            },
            "raise_for_status": MagicMock(),
        })

        result = list_group_roles(
            self.config, self.auth_manager,
            ListGroupRolesParams(group_sys_id="grp1")
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["group_sys_id"], "grp1")
        called_url = mock_get.call_args[0][0]
        self.assertIn("sys_group_has_role", called_url)
        query = mock_get.call_args[1]["params"]["sysparm_query"]
        self.assertIn("group=grp1", query)

    @patch("servicenow_mcp.tools.user_tools.requests.get")
    def test_list_group_roles_exclude_inherited(self, mock_get):
        """list_group_roles with include_inherited=False adds inherited=false to query."""
        mock_get.return_value = MagicMock(**{
            "json.return_value": {"result": []},
            "raise_for_status": MagicMock(),
        })

        list_group_roles(
            self.config, self.auth_manager,
            ListGroupRolesParams(group_sys_id="grp1", include_inherited=False)
        )

        query = mock_get.call_args[1]["params"]["sysparm_query"]
        self.assertIn("inherited=false", query)

    @patch("servicenow_mcp.tools.user_tools.requests.get")
    def test_list_group_roles_http_error(self, mock_get):
        """list_group_roles handles HTTP errors."""
        mock_get.side_effect = requests.RequestException("500 error")
        result = list_group_roles(
            self.config, self.auth_manager,
            ListGroupRolesParams(group_sys_id="grp1")
        )
        self.assertFalse(result["success"])


    @patch("servicenow_mcp.tools.user_tools.requests.get")
    @patch("servicenow_mcp.tools.user_tools.requests.post")
    def test_grant_role_to_user_creates_direct_grant_when_only_inherited(self, mock_post, mock_get):
        """grant_role_to_user creates a direct grant even if user has role via inheritance only."""
        mock_get.side_effect = [
            MagicMock(**{  # get_role_id call
                "json.return_value": {"result": [{"sys_id": "role123"}]},
                "raise_for_status": MagicMock(),
            }),
            MagicMock(**{  # direct grant check (inherited=false) — empty: no direct grant yet
                "json.return_value": {"result": []},
                "raise_for_status": MagicMock(),
            }),
        ]
        mock_post.return_value = MagicMock(**{
            "json.return_value": {"result": {"sys_id": "grant_new"}},
            "raise_for_status": MagicMock(),
        })

        params = GrantRoleToUserParams(user_sys_id="user1", role_name="itil")
        result = grant_role_to_user(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        self.assertNotEqual(
            result.get("already_exists"), True,
            "Should not short-circuit when user only has role via inheritance",
        )
        self.assertTrue(mock_post.called, "Should have made a POST to create the direct grant")
        # Confirm the direct-grant check included inherited=false
        direct_check_call = mock_get.call_args_list[1]
        query = direct_check_call[1].get("params", {}).get("sysparm_query", "")
        self.assertIn("inherited=false", query, "Direct-grant check must filter inherited=false")


if __name__ == "__main__":
    unittest.main()
