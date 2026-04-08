"""
Tests for Phase 5 Flow Designer extension tools.

Covers: list_flows, get_flow, get_flow_triggers, get_flow_actions,
get_flow_version, publish_flow.
"""

import unittest
from unittest.mock import MagicMock, patch

import requests

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.flow_tools import (
    GetFlowActionsParams,
    GetFlowParams,
    GetFlowTriggersParams,
    GetFlowVersionParams,
    ListFlowsParams,
    PublishFlowParams,
    get_flow,
    get_flow_actions,
    get_flow_triggers,
    get_flow_version,
    list_flows,
    publish_flow,
)
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig


class TestFlowExtensionTools(unittest.TestCase):
    """Tests for Phase 5 Flow Designer read and publish tools."""

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

    # --- list_flows ---

    @patch("servicenow_mcp.tools.flow_tools.requests.get")
    def test_list_flows_success(self, mock_get):
        """Test listing flows returns results."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": [
                {"sys_id": "flow1", "name": "Incident Escalation", "status": "published"},
                {"sys_id": "flow2", "name": "Approval Flow", "status": "draft"},
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        params = ListFlowsParams()
        result = list_flows(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 2)
        self.assertEqual(result["flows"][0]["name"], "Incident Escalation")

    @patch("servicenow_mcp.tools.flow_tools.requests.get")
    def test_list_flows_with_filters(self, mock_get):
        """Test that type, status, and scope filters build correct query."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": []}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        params = ListFlowsParams(flow_type="flow", status="published", scope="global")
        result = list_flows(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        call_kwargs = mock_get.call_args[1]["params"]
        query = call_kwargs["sysparm_query"]
        self.assertIn("flow_type=flow", query)
        self.assertIn("status=published", query)
        self.assertIn("sys_scope=global", query)

    @patch("servicenow_mcp.tools.flow_tools.requests.get")
    def test_list_flows_with_name_filter(self, mock_get):
        """Test that name filter is applied as LIKE match."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": []}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        params = ListFlowsParams(name_filter="Incident")
        result = list_flows(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        call_kwargs = mock_get.call_args[1]["params"]
        self.assertIn("nameLIKEIncident", call_kwargs["sysparm_query"])

    @patch("servicenow_mcp.tools.flow_tools.requests.get")
    def test_list_flows_http_error(self, mock_get):
        """Test list_flows handles HTTP errors."""
        mock_get.side_effect = requests.HTTPError("500 error")
        result = list_flows(self.config, self.auth_manager, ListFlowsParams())
        self.assertFalse(result["success"])
        self.assertIn("Error listing flows", result["message"])

    # --- get_flow ---

    @patch("servicenow_mcp.tools.flow_tools.requests.get")
    def test_get_flow_success(self, mock_get):
        """Test getting a flow by sys_id."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": {
                "sys_id": "flow1",
                "name": "Incident Escalation",
                "status": "published",
                "active": "true",
            }
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        params = GetFlowParams(flow_sys_id="flow1")
        result = get_flow(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        self.assertEqual(result["flow"]["sys_id"], "flow1")
        called_url = mock_get.call_args[0][0]
        self.assertIn("flow1", called_url)
        self.assertIn("sys_hub_flow", called_url)

    @patch("servicenow_mcp.tools.flow_tools.requests.get")
    def test_get_flow_http_error(self, mock_get):
        """Test get_flow handles HTTP errors."""
        mock_get.side_effect = requests.HTTPError("404 Not Found")
        result = get_flow(self.config, self.auth_manager, GetFlowParams(flow_sys_id="missing"))
        self.assertFalse(result["success"])
        self.assertIn("Error getting flow", result["message"])

    @patch("servicenow_mcp.tools.flow_tools.requests.get")
    def test_get_flow_sends_sysparm_fields(self, mock_get):
        """get_flow must send sysparm_fields and must not request blob fields."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": {"sys_id": "flow1"}}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        get_flow(self.config, self.auth_manager, GetFlowParams(flow_sys_id="flow1"))

        call_params = mock_get.call_args[1]["params"]
        self.assertIn("sysparm_fields", call_params)
        fields = call_params["sysparm_fields"]
        self.assertIn("sys_id", fields)
        self.assertIn("name", fields)
        self.assertIn("master_snapshot", fields)
        # Blob fields must be excluded
        self.assertNotIn("outputs", fields)
        self.assertNotIn("acls", fields)
        self.assertNotIn("run_with_roles", fields)
        self.assertNotIn("annotation", fields)

    # --- get_flow_triggers ---

    @patch("servicenow_mcp.tools.flow_tools.requests.get")
    def test_get_flow_triggers_success(self, mock_get):
        """Test getting trigger instances for a flow."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": [
                {"sys_id": "trig1", "name": "Created", "flow": "flow1"},
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        params = GetFlowTriggersParams(flow_sys_id="flow1")
        result = get_flow_triggers(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["triggers"][0]["name"], "Created")
        called_url = mock_get.call_args[0][0]
        self.assertIn("sys_hub_trigger_instance", called_url)

    @patch("servicenow_mcp.tools.flow_tools.requests.get")
    def test_get_flow_triggers_empty(self, mock_get):
        """Test getting triggers when none exist returns empty list."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": []}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = get_flow_triggers(self.config, self.auth_manager, GetFlowTriggersParams(flow_sys_id="flow1"))
        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 0)

    @patch("servicenow_mcp.tools.flow_tools.requests.get")
    def test_get_flow_triggers_http_error(self, mock_get):
        """Test get_flow_triggers handles HTTP errors."""
        mock_get.side_effect = requests.HTTPError("403 Forbidden")
        result = get_flow_triggers(self.config, self.auth_manager, GetFlowTriggersParams(flow_sys_id="flow1"))
        self.assertFalse(result["success"])

    # --- get_flow_actions ---

    @patch("servicenow_mcp.tools.flow_tools.requests.get")
    def test_get_flow_actions_success(self, mock_get):
        """Test getting action instances for a flow."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": [
                {"sys_id": "act1", "name": "Look Up Record", "flow": "flow1"},
                {"sys_id": "act2", "name": "Update Record", "flow": "flow1"},
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        params = GetFlowActionsParams(flow_sys_id="flow1")
        result = get_flow_actions(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 2)
        called_url = mock_get.call_args[0][0]
        self.assertIn("sys_hub_action_instance", called_url)

    @patch("servicenow_mcp.tools.flow_tools.requests.get")
    def test_get_flow_actions_http_error(self, mock_get):
        """Test get_flow_actions handles HTTP errors."""
        mock_get.side_effect = requests.HTTPError("500 error")
        result = get_flow_actions(self.config, self.auth_manager, GetFlowActionsParams(flow_sys_id="flow1"))
        self.assertFalse(result["success"])

    # --- get_flow_version ---

    @patch("servicenow_mcp.tools.flow_tools.requests.get")
    def test_get_flow_version_latest(self, mock_get):
        """Test getting the latest flow version."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": [
                {"sys_id": "ver1", "flow": "flow1", "published": "false", "annotation": ""}
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        params = GetFlowVersionParams(flow_sys_id="flow1")
        result = get_flow_version(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        self.assertEqual(result["version"]["sys_id"], "ver1")
        call_kwargs = mock_get.call_args[1]["params"]
        self.assertNotIn("published=true", call_kwargs.get("sysparm_query", ""))

    @patch("servicenow_mcp.tools.flow_tools.requests.get")
    def test_get_flow_version_published_only(self, mock_get):
        """Test getting only the published flow version adds published=true filter."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": [{"sys_id": "ver2", "published": "true"}]
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        params = GetFlowVersionParams(flow_sys_id="flow1", published_only=True)
        result = get_flow_version(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        call_kwargs = mock_get.call_args[1]["params"]
        self.assertIn("published=true", call_kwargs["sysparm_query"])

    @patch("servicenow_mcp.tools.flow_tools.requests.get")
    def test_get_flow_version_not_found(self, mock_get):
        """No sys_hub_flow_version and no snapshot returns failure."""
        empty = MagicMock()
        empty.json.return_value = {"result": []}
        empty.raise_for_status = MagicMock()
        mock_get.side_effect = [empty, empty]

        result = get_flow_version(self.config, self.auth_manager, GetFlowVersionParams(flow_sys_id="flow1"))
        self.assertFalse(result["success"])
        self.assertIn("No", result["message"])
        self.assertEqual(mock_get.call_count, 2)

    @patch("servicenow_mcp.tools.flow_tools.requests.get")
    def test_get_flow_version_snapshot_fallback(self, mock_get):
        """When version table is empty, use sys_hub_flow_snapshot if present."""
        ver_empty = MagicMock()
        ver_empty.json.return_value = {"result": []}
        ver_empty.raise_for_status = MagicMock()
        snap_row = MagicMock()
        snap_row.json.return_value = {
            "result": [{"sys_id": "snap1", "flow": "flow1", "annotation": "pkg"}]
        }
        snap_row.raise_for_status = MagicMock()
        mock_get.side_effect = [ver_empty, snap_row]

        result = get_flow_version(self.config, self.auth_manager, GetFlowVersionParams(flow_sys_id="flow1"))
        self.assertTrue(result["success"])
        self.assertTrue(result.get("snapshot_fallback"))
        self.assertEqual(result["version"]["sys_id"], "snap1")
        self.assertEqual(mock_get.call_count, 2)

    @patch("servicenow_mcp.tools.flow_tools.requests.get")
    def test_get_flow_version_http_error(self, mock_get):
        """Test get_flow_version handles HTTP errors."""
        mock_get.side_effect = requests.HTTPError("500 error")
        result = get_flow_version(self.config, self.auth_manager, GetFlowVersionParams(flow_sys_id="flow1"))
        self.assertFalse(result["success"])

    # --- publish_flow ---

    @patch("servicenow_mcp.tools.flow_tools.requests.patch")
    def test_publish_flow_success(self, mock_patch):
        """Test publishing a flow sets active=true and status=published."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": {"sys_id": "flow1", "active": "true", "status": "published"}
        }
        mock_response.raise_for_status = MagicMock()
        mock_patch.return_value = mock_response

        params = PublishFlowParams(flow_sys_id="flow1")
        result = publish_flow(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        self.assertIn("published", result["message"])
        sent_data = mock_patch.call_args[1]["json"]
        self.assertEqual(sent_data["active"], "true")
        self.assertEqual(sent_data["status"], "published")

    @patch("servicenow_mcp.tools.flow_tools.requests.patch")
    def test_publish_flow_http_error(self, mock_patch):
        """Test publish_flow handles HTTP errors and provides fallback hint."""
        mock_patch.side_effect = requests.HTTPError("403 Forbidden")
        result = publish_flow(self.config, self.auth_manager, PublishFlowParams(flow_sys_id="flow1"))
        self.assertFalse(result["success"])
        # Error message should suggest background script fallback
        self.assertIn("FlowDesignerAPI.publishFlow", result["message"])

    @patch("servicenow_mcp.tools.flow_tools.requests.patch")
    def test_publish_flow_hits_sys_hub_flow(self, mock_patch):
        """Test that publish_flow sends PATCH to sys_hub_flow not sys_hub_flow_version."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": {"sys_id": "flow1"}}
        mock_response.raise_for_status = MagicMock()
        mock_patch.return_value = mock_response

        publish_flow(self.config, self.auth_manager, PublishFlowParams(flow_sys_id="flow1"))
        called_url = mock_patch.call_args[0][0]
        self.assertIn("sys_hub_flow/flow1", called_url)
        self.assertNotIn("sys_hub_flow_version", called_url)


if __name__ == "__main__":
    unittest.main()
