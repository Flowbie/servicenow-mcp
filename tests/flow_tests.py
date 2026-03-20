"""Unit tests for Flow Designer lifecycle tools in flow_tools.py."""

import unittest
from unittest.mock import MagicMock, patch

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.flow_tools import (
    CreateActionParams,
    CreateSubflowParams,
    GetActionParams,
    GetFlowParams,
    GetSubflowParams,
    ListActionsParams,
    ListFlowsParams,
    ListSubflowsParams,
    PublishActionParams,
    PublishFlowParams,
    PublishSubflowParams,
    UpdateActionParams,
    UpdateFlowParams,
    UpdateSubflowParams,
    create_action,
    create_subflow,
    get_action,
    get_flow,
    get_subflow,
    list_actions,
    list_flows,
    list_subflows,
    publish_action,
    publish_flow,
    publish_subflow,
    update_action,
    update_flow,
    update_subflow,
)
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig


class TestFlowLifecycleTools(unittest.TestCase):
    """Covers lifecycle CRUD/publish wrappers for flow/subflow/action artifacts."""

    def setUp(self):
        self.auth_config = AuthConfig(
            type=AuthType.BASIC,
            basic=BasicAuthConfig(username="test_user", password="test_password"),
        )
        self.server_config = ServerConfig(
            instance_url="https://test.service-now.com",
            auth=self.auth_config,
        )
        self.auth_manager = AuthManager(self.auth_config)

    @patch("servicenow_mcp.tools.flow_tools.requests.get")
    def test_list_flows(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": [{"sys_id": "f1", "name": "Flow A", "type": "flow", "active": "true"}]
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = list_flows(self.server_config, self.auth_manager, ListFlowsParams())
        self.assertEqual(result.count, 1)
        self.assertEqual(result.artifacts[0].artifact_type, "flow")

    @patch("servicenow_mcp.tools.flow_tools.requests.get")
    def test_get_flow(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": {"sys_id": "f1", "name": "Flow A", "type": "flow"}}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = get_flow(self.server_config, self.auth_manager, GetFlowParams(sys_id="f1"))
        self.assertEqual(result.artifact["sys_id"], "f1")

    @patch("servicenow_mcp.tools.flow_tools.requests.patch")
    def test_update_flow(self, mock_patch):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_patch.return_value = mock_response

        result = update_flow(
            self.server_config,
            self.auth_manager,
            UpdateFlowParams(sys_id="f1", name="Flow A Updated"),
        )
        self.assertTrue(result.success)
        self.assertEqual(result.sys_id, "f1")

    @patch("servicenow_mcp.tools.flow_tools.requests.post")
    @patch("servicenow_mcp.tools.flow_tools.requests.patch")
    def test_publish_flow(self, mock_patch, mock_post):
        post_response = MagicMock()
        post_response.raise_for_status = MagicMock()
        mock_post.return_value = post_response
        patch_response = MagicMock()
        patch_response.raise_for_status = MagicMock()
        mock_patch.return_value = patch_response

        result = publish_flow(
            self.server_config,
            self.auth_manager,
            PublishFlowParams(sys_id="f1"),
        )
        self.assertTrue(result.success)
        self.assertEqual(result.sys_id, "f1")

    @patch("servicenow_mcp.tools.flow_tools.requests.post")
    def test_create_subflow(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": {"data": {"id": "s1"}}}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        result = create_subflow(
            self.server_config,
            self.auth_manager,
            CreateSubflowParams(name="Subflow A"),
        )
        self.assertTrue(result.success)
        self.assertEqual(result.sys_id, "s1")

    @patch("servicenow_mcp.tools.flow_tools.requests.get")
    def test_list_subflows(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": [{"sys_id": "s1", "name": "Subflow A", "type": "subflow", "active": "false"}]
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = list_subflows(self.server_config, self.auth_manager, ListSubflowsParams())
        self.assertEqual(result.count, 1)
        self.assertEqual(result.artifacts[0].artifact_type, "subflow")

    @patch("servicenow_mcp.tools.flow_tools.requests.get")
    def test_get_subflow(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": {"sys_id": "s1", "name": "Subflow A", "type": "subflow"}}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = get_subflow(self.server_config, self.auth_manager, GetSubflowParams(sys_id="s1"))
        self.assertEqual(result.artifact["sys_id"], "s1")

    @patch("servicenow_mcp.tools.flow_tools.requests.patch")
    def test_update_subflow(self, mock_patch):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_patch.return_value = mock_response

        result = update_subflow(
            self.server_config,
            self.auth_manager,
            UpdateSubflowParams(sys_id="s1", description="Updated"),
        )
        self.assertTrue(result.success)
        self.assertEqual(result.sys_id, "s1")

    @patch("servicenow_mcp.tools.flow_tools.requests.post")
    @patch("servicenow_mcp.tools.flow_tools.requests.patch")
    def test_publish_subflow(self, mock_patch, mock_post):
        post_response = MagicMock()
        post_response.raise_for_status = MagicMock()
        mock_post.return_value = post_response
        patch_response = MagicMock()
        patch_response.raise_for_status = MagicMock()
        mock_patch.return_value = patch_response

        result = publish_subflow(
            self.server_config,
            self.auth_manager,
            PublishSubflowParams(sys_id="s1"),
        )
        self.assertTrue(result.success)
        self.assertEqual(result.sys_id, "s1")

    @patch("servicenow_mcp.tools.flow_tools.requests.post")
    def test_create_action(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": {"data": {"id": "a1"}}}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        result = create_action(
            self.server_config,
            self.auth_manager,
            CreateActionParams(name="Action A"),
        )
        self.assertTrue(result.success)
        self.assertEqual(result.sys_id, "a1")

    @patch("servicenow_mcp.tools.flow_tools.requests.get")
    def test_list_actions(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": [{"sys_id": "a1", "name": "Action A", "type": "action", "active": "true"}]
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = list_actions(self.server_config, self.auth_manager, ListActionsParams())
        self.assertEqual(result.count, 1)
        self.assertEqual(result.artifacts[0].artifact_type, "action")

    @patch("servicenow_mcp.tools.flow_tools.requests.get")
    def test_get_action(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": {"sys_id": "a1", "name": "Action A", "type": "action"}}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = get_action(self.server_config, self.auth_manager, GetActionParams(sys_id="a1"))
        self.assertEqual(result.artifact["sys_id"], "a1")

    @patch("servicenow_mcp.tools.flow_tools.requests.patch")
    def test_update_action(self, mock_patch):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_patch.return_value = mock_response

        result = update_action(
            self.server_config,
            self.auth_manager,
            UpdateActionParams(sys_id="a1", active=True),
        )
        self.assertTrue(result.success)
        self.assertEqual(result.sys_id, "a1")

    @patch("servicenow_mcp.tools.flow_tools.requests.post")
    @patch("servicenow_mcp.tools.flow_tools.requests.patch")
    def test_publish_action(self, mock_patch, mock_post):
        post_response = MagicMock()
        post_response.raise_for_status = MagicMock()
        mock_post.return_value = post_response
        patch_response = MagicMock()
        patch_response.raise_for_status = MagicMock()
        mock_patch.return_value = patch_response

        result = publish_action(
            self.server_config,
            self.auth_manager,
            PublishActionParams(sys_id="a1"),
        )
        self.assertTrue(result.success)
        self.assertEqual(result.sys_id, "a1")


if __name__ == "__main__":
    unittest.main()
