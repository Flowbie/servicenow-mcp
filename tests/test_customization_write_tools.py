"""
Tests for Phase 6 platform scripting write tools.

Covers: create/update/delete business rules, create/update client scripts,
create/update UI actions, and list_scheduled_scripts.
"""

import unittest
from unittest.mock import MagicMock, patch

import requests

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.customization_tools import (
    CreateBusinessRuleParams,
    CreateClientScriptParams,
    CreateUIActionParams,
    DeleteBusinessRuleParams,
    ListScheduledScriptsParams,
    UpdateBusinessRuleParams,
    UpdateClientScriptParams,
    UpdateUIActionParams,
    create_business_rule,
    create_client_script,
    create_ui_action,
    delete_business_rule,
    list_scheduled_scripts,
    update_business_rule,
    update_client_script,
    update_ui_action,
)
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig


class TestPlatformScriptingWriteTools(unittest.TestCase):
    """Tests for Phase 6 platform scripting write tools."""

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

    # --- create_business_rule ---

    @patch("servicenow_mcp.tools.customization_tools.requests.post")
    def test_create_business_rule_success(self, mock_post):
        """Test creating a business rule."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": {"sys_id": "br1", "name": "Set Priority", "collection": "incident"}
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        params = CreateBusinessRuleParams(
            name="Set Priority",
            table="incident",
            when="before",
            script="current.priority = 1;",
            action_insert=True,
            action_update=True,
        )
        result = create_business_rule(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        self.assertIn("Set Priority", result["message"])
        sent_data = mock_post.call_args[1]["json"]
        # table field is stored as 'collection' on sys_script
        self.assertEqual(sent_data["collection"], "incident")
        self.assertNotIn("table", sent_data)
        self.assertEqual(sent_data["when"], "before")
        self.assertEqual(sent_data["action_insert"], "true")
        called_url = mock_post.call_args[0][0]
        self.assertIn("sys_script", called_url)
        self.assertNotIn("sys_script_client", called_url)

    @patch("servicenow_mcp.tools.customization_tools.requests.post")
    def test_create_business_rule_http_error(self, mock_post):
        """Test create_business_rule handles HTTP errors."""
        mock_post.side_effect = requests.RequestException("500 error")
        params = CreateBusinessRuleParams(
            name="BR", table="incident", when="after", script="// script"
        )
        result = create_business_rule(self.config, self.auth_manager, params)
        self.assertFalse(result["success"])
        self.assertIn("Error creating business rule", result["message"])

    # --- update_business_rule ---

    @patch("servicenow_mcp.tools.customization_tools.requests.patch")
    def test_update_business_rule_success(self, mock_patch):
        """Test updating a business rule."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": {"sys_id": "br1", "active": "false"}}
        mock_response.raise_for_status = MagicMock()
        mock_patch.return_value = mock_response

        params = UpdateBusinessRuleParams(sys_id="br1", active=False, when="after")
        result = update_business_rule(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        sent_data = mock_patch.call_args[1]["json"]
        self.assertEqual(sent_data["active"], "false")
        self.assertEqual(sent_data["when"], "after")
        called_url = mock_patch.call_args[0][0]
        self.assertIn("sys_script/br1", called_url)

    @patch("servicenow_mcp.tools.customization_tools.requests.patch")
    def test_update_business_rule_http_error(self, mock_patch):
        """Test update_business_rule handles HTTP errors."""
        mock_patch.side_effect = requests.RequestException("403 error")
        result = update_business_rule(self.config, self.auth_manager, UpdateBusinessRuleParams(sys_id="br1"))
        self.assertFalse(result["success"])

    # --- delete_business_rule ---

    @patch("servicenow_mcp.tools.customization_tools.requests.delete")
    def test_delete_business_rule_success(self, mock_delete):
        """Test deleting a business rule."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_delete.return_value = mock_response

        params = DeleteBusinessRuleParams(sys_id="br1")
        result = delete_business_rule(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        self.assertIn("deleted", result["message"])
        called_url = mock_delete.call_args[0][0]
        self.assertIn("sys_script/br1", called_url)

    @patch("servicenow_mcp.tools.customization_tools.requests.delete")
    def test_delete_business_rule_http_error(self, mock_delete):
        """Test delete_business_rule handles HTTP errors."""
        mock_delete.side_effect = requests.RequestException("404 error")
        result = delete_business_rule(self.config, self.auth_manager, DeleteBusinessRuleParams(sys_id="missing"))
        self.assertFalse(result["success"])

    # --- create_client_script ---

    @patch("servicenow_mcp.tools.customization_tools.requests.post")
    def test_create_client_script_success(self, mock_post):
        """Test creating a client script hits sys_script_client (not sys_client_script)."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": {"sys_id": "cs1", "name": "Hide Field", "type": "onLoad"}
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        params = CreateClientScriptParams(
            name="Hide Field",
            table="incident",
            script_type="onLoad",
            script="g_form.setVisible('category', false);",
        )
        result = create_client_script(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        called_url = mock_post.call_args[0][0]
        self.assertIn("sys_script_client", called_url)
        self.assertNotIn("sys_client_script", called_url)
        sent_data = mock_post.call_args[1]["json"]
        self.assertEqual(sent_data["type"], "onLoad")
        self.assertEqual(sent_data["table"], "incident")

    @patch("servicenow_mcp.tools.customization_tools.requests.post")
    def test_create_client_script_onchange_with_field(self, mock_post):
        """Test onChange client script passes field_name."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": {"sys_id": "cs2"}}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        params = CreateClientScriptParams(
            name="Watch Priority",
            table="incident",
            script_type="onChange",
            script="// handle change",
            field_name="priority",
        )
        result = create_client_script(self.config, self.auth_manager, params)
        self.assertTrue(result["success"])
        sent_data = mock_post.call_args[1]["json"]
        self.assertEqual(sent_data["field_name"], "priority")

    @patch("servicenow_mcp.tools.customization_tools.requests.post")
    def test_create_client_script_http_error(self, mock_post):
        """Test create_client_script handles HTTP errors."""
        mock_post.side_effect = requests.RequestException("500 error")
        params = CreateClientScriptParams(
            name="CS", table="incident", script_type="onLoad", script="// x"
        )
        result = create_client_script(self.config, self.auth_manager, params)
        self.assertFalse(result["success"])

    # --- update_client_script ---

    @patch("servicenow_mcp.tools.customization_tools.requests.patch")
    def test_update_client_script_success(self, mock_patch):
        """Test updating a client script."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": {"sys_id": "cs1", "active": "false"}}
        mock_response.raise_for_status = MagicMock()
        mock_patch.return_value = mock_response

        params = UpdateClientScriptParams(sys_id="cs1", active=False)
        result = update_client_script(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        sent_data = mock_patch.call_args[1]["json"]
        self.assertEqual(sent_data["active"], "false")
        called_url = mock_patch.call_args[0][0]
        self.assertIn("sys_script_client/cs1", called_url)

    # --- create_ui_action ---

    @patch("servicenow_mcp.tools.customization_tools.requests.post")
    def test_create_ui_action_success(self, mock_post):
        """Test creating a UI action with surface flags."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": {"sys_id": "ua1", "name": "Close Incident", "form_button": "true"}
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        params = CreateUIActionParams(
            name="Close Incident",
            table="incident",
            script="current.state = 7; current.update();",
            form_button=True,
            form_context_menu=True,
        )
        result = create_ui_action(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        called_url = mock_post.call_args[0][0]
        self.assertIn("sys_ui_action", called_url)
        sent_data = mock_post.call_args[1]["json"]
        self.assertEqual(sent_data["form_button"], "true")
        self.assertEqual(sent_data["form_context_menu"], "true")
        self.assertEqual(sent_data["list_choice"], "false")
        # No action_type field should be sent
        self.assertNotIn("action_type", sent_data)

    @patch("servicenow_mcp.tools.customization_tools.requests.post")
    def test_create_ui_action_all_14_flags_sent(self, mock_post):
        """Test that all 14 surface boolean flags are included in the POST."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": {"sys_id": "ua2"}}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        params = CreateUIActionParams(name="Test", table="incident", script="// x")
        create_ui_action(self.config, self.auth_manager, params)

        sent_data = mock_post.call_args[1]["json"]
        for flag in [
            "form_button", "form_context_menu", "form_link", "list_banner_button",
            "list_choice", "list_context_menu", "list_expanded", "list_link",
            "form_menu_button", "ref_contributions", "onload", "client", "ajax",
            "isolate_script",
        ]:
            self.assertIn(flag, sent_data, f"Missing surface flag: {flag}")

    @patch("servicenow_mcp.tools.customization_tools.requests.post")
    def test_create_ui_action_http_error(self, mock_post):
        """Test create_ui_action handles HTTP errors."""
        mock_post.side_effect = requests.RequestException("500 error")
        params = CreateUIActionParams(name="UA", table="incident", script="// x")
        result = create_ui_action(self.config, self.auth_manager, params)
        self.assertFalse(result["success"])

    # --- update_ui_action ---

    @patch("servicenow_mcp.tools.customization_tools.requests.patch")
    def test_update_ui_action_success(self, mock_patch):
        """Test updating a UI action."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": {"sys_id": "ua1"}}
        mock_response.raise_for_status = MagicMock()
        mock_patch.return_value = mock_response

        params = UpdateUIActionParams(sys_id="ua1", form_button=False, active=True)
        result = update_ui_action(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        sent_data = mock_patch.call_args[1]["json"]
        self.assertEqual(sent_data["form_button"], "false")
        self.assertEqual(sent_data["active"], "true")
        # Flags not supplied should NOT be in the patch
        self.assertNotIn("form_link", sent_data)

    @patch("servicenow_mcp.tools.customization_tools.requests.patch")
    def test_update_ui_action_http_error(self, mock_patch):
        """Test update_ui_action handles HTTP errors."""
        mock_patch.side_effect = requests.RequestException("403 error")
        result = update_ui_action(self.config, self.auth_manager, UpdateUIActionParams(sys_id="ua1"))
        self.assertFalse(result["success"])

    # --- list_scheduled_scripts ---

    @patch("servicenow_mcp.tools.customization_tools.requests.get")
    def test_list_scheduled_scripts_success(self, mock_get):
        """Test listing scheduled scripts from sysauto_script."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": [
                {"sys_id": "ss1", "name": "Nightly Cleanup", "active": "true"},
                {"sys_id": "ss2", "name": "Weekly Report", "active": "true"},
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        params = ListScheduledScriptsParams()
        result = list_scheduled_scripts(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 2)
        called_url = mock_get.call_args[0][0]
        self.assertIn("sysauto_script", called_url)

    @patch("servicenow_mcp.tools.customization_tools.requests.get")
    def test_list_scheduled_scripts_with_active_filter(self, mock_get):
        """Test listing scheduled scripts with active filter."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": []}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        params = ListScheduledScriptsParams(active=True, name_filter="Cleanup")
        result = list_scheduled_scripts(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        call_kwargs = mock_get.call_args[1]["params"]
        self.assertIn("active=true", call_kwargs["sysparm_query"])
        self.assertIn("nameLIKECleanup", call_kwargs["sysparm_query"])

    @patch("servicenow_mcp.tools.customization_tools.requests.get")
    def test_list_scheduled_scripts_http_error(self, mock_get):
        """Test list_scheduled_scripts handles HTTP errors."""
        mock_get.side_effect = requests.RequestException("500 error")
        result = list_scheduled_scripts(self.config, self.auth_manager, ListScheduledScriptsParams())
        self.assertFalse(result["success"])


if __name__ == "__main__":
    unittest.main()
