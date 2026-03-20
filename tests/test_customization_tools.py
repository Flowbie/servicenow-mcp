"""
Tests for customization tools — client scripts, UI actions, UI policies, business rules.
"""

import unittest
from unittest.mock import MagicMock, patch

import requests

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.customization_tools import (
    DisableClientScriptParams,
    DisableUiActionParams,
    EnableClientScriptParams,
    EnableUiActionParams,
    DeleteClientScriptParams,
    disable_client_script,
    disable_ui_action,
    enable_client_script,
    enable_ui_action,
    delete_client_script,
    GetUiPolicyParams,
    CreateUiPolicyParams,
    UpdateUiPolicyParams,
    CreateUiPolicyActionParams,
    ListUiPolicyActionsParams,
    get_ui_policy,
    create_ui_policy,
    update_ui_policy,
    create_ui_policy_action,
    list_ui_policy_actions,
)
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig


class TestCustomizationTools(unittest.TestCase):
    """Tests for customization tools."""

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

    # --- enable_client_script ---

    @patch("servicenow_mcp.tools.customization_tools.requests.patch")
    def test_enable_client_script_success(self, mock_patch):
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": {"sys_id": "cs1", "active": "true"}}
        mock_response.raise_for_status = MagicMock()
        mock_patch.return_value = mock_response

        params = EnableClientScriptParams(script_sys_id="cs1")
        result = enable_client_script(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        call_payload = mock_patch.call_args[1]["json"]
        self.assertEqual(call_payload["active"], "true")

    @patch("servicenow_mcp.tools.customization_tools.requests.patch")
    def test_enable_client_script_request_error(self, mock_patch):
        mock_patch.side_effect = requests.RequestException("Connection refused")
        params = EnableClientScriptParams(script_sys_id="cs1")
        result = enable_client_script(self.config, self.auth_manager, params)
        self.assertFalse(result["success"])
        self.assertIn("message", result)

    # --- disable_client_script ---

    @patch("servicenow_mcp.tools.customization_tools.requests.patch")
    def test_disable_client_script_success(self, mock_patch):
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": {"sys_id": "cs1", "active": "false"}}
        mock_response.raise_for_status = MagicMock()
        mock_patch.return_value = mock_response

        params = DisableClientScriptParams(script_sys_id="cs1")
        result = disable_client_script(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        call_payload = mock_patch.call_args[1]["json"]
        self.assertEqual(call_payload["active"], "false")

    @patch("servicenow_mcp.tools.customization_tools.requests.patch")
    def test_disable_client_script_request_error(self, mock_patch):
        mock_patch.side_effect = requests.RequestException("Timeout")
        params = DisableClientScriptParams(script_sys_id="cs1")
        result = disable_client_script(self.config, self.auth_manager, params)
        self.assertFalse(result["success"])
        self.assertIn("message", result)

    # --- delete_client_script ---

    @patch("servicenow_mcp.tools.customization_tools.requests.delete")
    def test_delete_client_script_success(self, mock_delete):
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_response.raise_for_status = MagicMock()
        mock_delete.return_value = mock_response

        params = DeleteClientScriptParams(script_sys_id="cs1")
        result = delete_client_script(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        self.assertIn("deleted", result["message"].lower())

    @patch("servicenow_mcp.tools.customization_tools.requests.delete")
    def test_delete_client_script_request_error(self, mock_delete):
        mock_delete.side_effect = requests.RequestException("Not found")
        params = DeleteClientScriptParams(script_sys_id="bad_id")
        result = delete_client_script(self.config, self.auth_manager, params)
        self.assertFalse(result["success"])
        self.assertIn("message", result)

    # --- enable_ui_action ---

    @patch("servicenow_mcp.tools.customization_tools.requests.patch")
    def test_enable_ui_action_success(self, mock_patch):
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": {"sys_id": "ua1", "active": "true"}}
        mock_response.raise_for_status = MagicMock()
        mock_patch.return_value = mock_response

        params = EnableUiActionParams(action_sys_id="ua1")
        result = enable_ui_action(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        call_payload = mock_patch.call_args[1]["json"]
        self.assertEqual(call_payload["active"], "true")

    @patch("servicenow_mcp.tools.customization_tools.requests.patch")
    def test_enable_ui_action_request_error(self, mock_patch):
        mock_patch.side_effect = requests.RequestException("Timeout")
        params = EnableUiActionParams(action_sys_id="ua1")
        result = enable_ui_action(self.config, self.auth_manager, params)
        self.assertFalse(result["success"])
        self.assertIn("message", result)

    # --- disable_ui_action ---

    @patch("servicenow_mcp.tools.customization_tools.requests.patch")
    def test_disable_ui_action_success(self, mock_patch):
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": {"sys_id": "ua1", "active": "false"}}
        mock_response.raise_for_status = MagicMock()
        mock_patch.return_value = mock_response

        params = DisableUiActionParams(action_sys_id="ua1")
        result = disable_ui_action(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        call_payload = mock_patch.call_args[1]["json"]
        self.assertEqual(call_payload["active"], "false")

    @patch("servicenow_mcp.tools.customization_tools.requests.patch")
    def test_disable_ui_action_request_error(self, mock_patch):
        mock_patch.side_effect = requests.RequestException("Connection refused")
        params = DisableUiActionParams(action_sys_id="ua1")
        result = disable_ui_action(self.config, self.auth_manager, params)
        self.assertFalse(result["success"])
        self.assertIn("message", result)


class TestUiPolicyTools(unittest.TestCase):
    """Tests for UI policy write tools."""

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

    @patch("servicenow_mcp.tools.customization_tools.requests.get")
    def test_get_ui_policy_success(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": {"sys_id": "up1", "short_description": "Mandatory Priority",
                       "table_name": "incident", "active": "true"}
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        params = GetUiPolicyParams(policy_sys_id="up1")
        result = get_ui_policy(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        self.assertEqual(result["ui_policy"]["sys_id"], "up1")

    @patch("servicenow_mcp.tools.customization_tools.requests.post")
    def test_create_ui_policy_success(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": {"sys_id": "up_new", "short_description": "Hide Field When Resolved",
                       "table_name": "incident", "active": "true"}
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        params = CreateUiPolicyParams(
            table_name="incident",
            short_description="Hide Field When Resolved",
            conditions="state=6",
        )
        result = create_ui_policy(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        self.assertEqual(result["ui_policy"]["sys_id"], "up_new")

    @patch("servicenow_mcp.tools.customization_tools.requests.patch")
    def test_update_ui_policy_success(self, mock_patch):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": {"sys_id": "up1", "active": "false"}
        }
        mock_response.raise_for_status = MagicMock()
        mock_patch.return_value = mock_response

        params = UpdateUiPolicyParams(policy_sys_id="up1", active=False)
        result = update_ui_policy(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])

    @patch("servicenow_mcp.tools.customization_tools.requests.post")
    def test_create_ui_policy_action_success(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": {"sys_id": "upa1", "field": "priority", "mandatory": "true", "visible": "true"}
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        params = CreateUiPolicyActionParams(
            policy_sys_id="up1",
            field="priority",
            mandatory=True,
            visible=True,
            disabled=False,
        )
        result = create_ui_policy_action(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        self.assertEqual(result["ui_policy_action"]["field"], "priority")

    @patch("servicenow_mcp.tools.customization_tools.requests.get")
    def test_list_ui_policy_actions_success(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": [
                {"sys_id": "upa1", "field": "priority", "mandatory": "true"},
                {"sys_id": "upa2", "field": "category", "visible": "false"},
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        params = ListUiPolicyActionsParams(policy_sys_id="up1")
        result = list_ui_policy_actions(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 2)

    @patch("servicenow_mcp.tools.customization_tools.requests.post")
    def test_create_ui_policy_request_error(self, mock_post):
        mock_post.side_effect = requests.RequestException("Timeout")
        params = CreateUiPolicyParams(table_name="incident", short_description="Fail Policy")
        result = create_ui_policy(self.config, self.auth_manager, params)
        self.assertFalse(result["success"])
        self.assertIn("message", result)

    @patch("servicenow_mcp.tools.customization_tools.requests.get")
    def test_get_ui_policy_request_error(self, mock_get):
        mock_get.side_effect = requests.RequestException("Not found")
        params = GetUiPolicyParams(policy_sys_id="bad_id")
        result = get_ui_policy(self.config, self.auth_manager, params)
        self.assertFalse(result["success"])
        self.assertIn("message", result)


if __name__ == "__main__":
    unittest.main()
