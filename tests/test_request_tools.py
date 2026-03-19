"""
Tests for the ServiceNow MCP request tools.
"""

import unittest
from unittest.mock import MagicMock, call, patch

import requests

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.request_tools import (
    GetRequestParams,
    GetRitmVariablesParams,
    ListRequestItemsParams,
    ListRequestsParams,
    ListScTasksParams,
    UpdateRequestItemParams,
    UpdateScTaskParams,
    get_request,
    get_ritm_variables,
    list_request_items,
    list_requests,
    list_sc_tasks,
    update_request_item,
    update_sc_task,
)
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig


class TestRequestTools(unittest.TestCase):
    """Test cases for the request tools."""

    def setUp(self):
        """Set up test fixtures."""
        self.config = ServerConfig(
            instance_url="https://example.service-now.com",
            auth=AuthConfig(
                type=AuthType.BASIC,
                basic=BasicAuthConfig(username="admin", password="password"),
            ),
        )
        self.auth_manager = MagicMock(spec=AuthManager)
        self.auth_manager.get_headers.return_value = {
            "Authorization": "Basic YWRtaW46cGFzc3dvcmQ="
        }

    # -----------------------------------------------------------------------
    # list_requests
    # -----------------------------------------------------------------------

    @patch("servicenow_mcp.tools.request_tools.requests.get")
    def test_list_requests_success(self, mock_get):
        """Test listing requests returns results correctly."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": [
                {
                    "sys_id": "req1",
                    "number": "REQ0001001",
                    "short_description": "Need a laptop",
                    "state": "1",
                    "requested_for": "John Doe",
                    "opened_at": "2025-01-01 10:00:00",
                    "opened_by": "admin",
                }
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        params = ListRequestsParams(limit=10, offset=0)
        result = list_requests(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        self.assertEqual(len(result["requests"]), 1)
        self.assertEqual(result["requests"][0]["number"], "REQ0001001")
        self.assertEqual(result["total"], 1)

        _, kwargs = mock_get.call_args
        self.assertEqual(kwargs["params"]["sysparm_limit"], 10)
        self.assertIn(
            "sys_id,number,short_description,state,requested_for,opened_at,opened_by",
            kwargs["params"]["sysparm_fields"],
        )

    @patch("servicenow_mcp.tools.request_tools.requests.get")
    def test_list_requests_with_filters(self, mock_get):
        """Test list_requests applies state and requested_for filters."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": []}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        params = ListRequestsParams(
            limit=5, offset=0, state_filter="1", requested_for="user_sys_id"
        )
        result = list_requests(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        _, kwargs = mock_get.call_args
        query = kwargs["params"]["sysparm_query"]
        self.assertIn("state=1", query)
        self.assertIn("requested_for=user_sys_id", query)

    @patch("servicenow_mcp.tools.request_tools.requests.get")
    def test_list_requests_error(self, mock_get):
        """Test list_requests error handling."""
        mock_get.side_effect = requests.exceptions.RequestException("Connection error")

        params = ListRequestsParams(limit=10, offset=0)
        result = list_requests(self.config, self.auth_manager, params)

        self.assertFalse(result["success"])
        self.assertEqual(result["requests"], [])
        self.assertIn("Error listing requests", result["message"])

    # -----------------------------------------------------------------------
    # get_request
    # -----------------------------------------------------------------------

    @patch("servicenow_mcp.tools.request_tools.requests.get")
    def test_get_request_by_sys_id(self, mock_get):
        """Test getting a request by sys_id."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": {"sys_id": "req_abc", "number": "REQ0001234"}
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        params = GetRequestParams(request_sys_id="req_abc")
        result = get_request(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        self.assertEqual(result["request"]["number"], "REQ0001234")
        args, _ = mock_get.call_args
        self.assertIn("req_abc", args[0])

    @patch("servicenow_mcp.tools.request_tools.requests.get")
    def test_get_request_by_number(self, mock_get):
        """Test getting a request by number."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": [{"sys_id": "req_abc", "number": "REQ0001234"}]
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        params = GetRequestParams(request_number="REQ0001234")
        result = get_request(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        self.assertEqual(result["request"]["number"], "REQ0001234")
        _, kwargs = mock_get.call_args
        self.assertIn("number=REQ0001234", kwargs["params"]["sysparm_query"])

    def test_get_request_requires_identifier(self):
        """Test GetRequestParams raises when neither identifier is provided."""
        with self.assertRaises(Exception):
            GetRequestParams()

    @patch("servicenow_mcp.tools.request_tools.requests.get")
    def test_get_request_not_found(self, mock_get):
        """Test get_request returns failure when no record is found."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": []}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        params = GetRequestParams(request_number="REQ9999999")
        result = get_request(self.config, self.auth_manager, params)

        self.assertFalse(result["success"])
        self.assertIsNone(result["request"])

    # -----------------------------------------------------------------------
    # list_request_items
    # -----------------------------------------------------------------------

    @patch("servicenow_mcp.tools.request_tools.requests.get")
    def test_list_request_items_success(self, mock_get):
        """Test listing RITMs returns correct results."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": [
                {
                    "sys_id": "ritm1",
                    "number": "RITM0001001",
                    "short_description": "Laptop",
                    "state": "1",
                    "cat_item": "laptop_item",
                    "request": "req1",
                    "quantity": "1",
                    "stage": "Requested",
                }
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        params = ListRequestItemsParams(limit=10, offset=0, request_sys_id="req1")
        result = list_request_items(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        self.assertEqual(len(result["items"]), 1)
        self.assertEqual(result["items"][0]["number"], "RITM0001001")
        _, kwargs = mock_get.call_args
        self.assertIn("request=req1", kwargs["params"]["sysparm_query"])

    @patch("servicenow_mcp.tools.request_tools.requests.get")
    def test_list_request_items_error(self, mock_get):
        """Test list_request_items error handling."""
        mock_get.side_effect = requests.exceptions.RequestException("Server error")

        params = ListRequestItemsParams(limit=10, offset=0)
        result = list_request_items(self.config, self.auth_manager, params)

        self.assertFalse(result["success"])
        self.assertEqual(result["items"], [])

    # -----------------------------------------------------------------------
    # update_request_item
    # -----------------------------------------------------------------------

    @patch("servicenow_mcp.tools.request_tools.requests.patch")
    def test_update_request_item_success(self, mock_patch):
        """Test updating a RITM successfully."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": {"sys_id": "ritm1", "state": "3"}
        }
        mock_response.raise_for_status = MagicMock()
        mock_patch.return_value = mock_response

        params = UpdateRequestItemParams(
            ritm_sys_id="ritm1",
            state="3",
            work_notes="Completed",
        )
        result = update_request_item(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        self.assertIn("ritm1", result["message"])

        _, kwargs = mock_patch.call_args
        self.assertEqual(kwargs["json"]["state"], "3")
        self.assertEqual(kwargs["json"]["work_notes"], "Completed")
        self.assertNotIn("assignment_group", kwargs["json"])

    @patch("servicenow_mcp.tools.request_tools.requests.patch")
    def test_update_request_item_error(self, mock_patch):
        """Test update_request_item error handling."""
        mock_patch.side_effect = requests.exceptions.RequestException("Not found")

        params = UpdateRequestItemParams(ritm_sys_id="ghost_ritm", state="3")
        result = update_request_item(self.config, self.auth_manager, params)

        self.assertFalse(result["success"])
        self.assertIsNone(result["item"])

    # -----------------------------------------------------------------------
    # list_sc_tasks
    # -----------------------------------------------------------------------

    @patch("servicenow_mcp.tools.request_tools.requests.get")
    def test_list_sc_tasks_success(self, mock_get):
        """Test listing catalog tasks."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": [
                {
                    "sys_id": "task1",
                    "number": "SCTASK0001001",
                    "short_description": "Configure laptop",
                    "state": "1",
                    "assigned_to": "tech_user",
                    "assignment_group": "IT Support",
                    "request_item": "ritm1",
                }
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        params = ListScTasksParams(limit=10, offset=0, request_item_sys_id="ritm1")
        result = list_sc_tasks(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        self.assertEqual(len(result["tasks"]), 1)
        self.assertEqual(result["tasks"][0]["number"], "SCTASK0001001")
        _, kwargs = mock_get.call_args
        self.assertIn("request_item=ritm1", kwargs["params"]["sysparm_query"])

    @patch("servicenow_mcp.tools.request_tools.requests.get")
    def test_list_sc_tasks_error(self, mock_get):
        """Test list_sc_tasks error handling."""
        mock_get.side_effect = requests.exceptions.ConnectionError("Refused")

        params = ListScTasksParams(limit=10, offset=0)
        result = list_sc_tasks(self.config, self.auth_manager, params)

        self.assertFalse(result["success"])
        self.assertEqual(result["tasks"], [])
        self.assertIn("Error listing catalog tasks", result["message"])

    # -----------------------------------------------------------------------
    # update_sc_task
    # -----------------------------------------------------------------------

    @patch("servicenow_mcp.tools.request_tools.requests.patch")
    def test_update_sc_task_success(self, mock_patch):
        """Test updating a catalog task successfully."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": {"sys_id": "task1", "state": "3"}
        }
        mock_response.raise_for_status = MagicMock()
        mock_patch.return_value = mock_response

        params = UpdateScTaskParams(
            task_sys_id="task1",
            state="3",
            assignment_group="IT Support",
            close_notes="Done",
        )
        result = update_sc_task(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        self.assertIn("task1", result["message"])

        _, kwargs = mock_patch.call_args
        self.assertEqual(kwargs["json"]["state"], "3")
        self.assertEqual(kwargs["json"]["assignment_group"], "IT Support")
        self.assertEqual(kwargs["json"]["close_notes"], "Done")
        self.assertNotIn("work_notes", kwargs["json"])

    @patch("servicenow_mcp.tools.request_tools.requests.patch")
    def test_update_sc_task_error(self, mock_patch):
        """Test update_sc_task error handling."""
        mock_patch.side_effect = requests.exceptions.RequestException("API error")

        params = UpdateScTaskParams(task_sys_id="ghost_task", state="4")
        result = update_sc_task(self.config, self.auth_manager, params)

        self.assertFalse(result["success"])
        self.assertIsNone(result["task"])
        self.assertIn("Error updating catalog task", result["message"])

    # -----------------------------------------------------------------------
    # get_ritm_variables
    # -----------------------------------------------------------------------

    @patch("servicenow_mcp.tools.request_tools.requests.get")
    def test_get_ritm_variables_success(self, mock_get):
        """Test retrieving RITM variable answers."""
        # First call: sc_item_option_mtom
        mtom_response = MagicMock()
        mtom_response.raise_for_status = MagicMock()
        mtom_response.json.return_value = {
            "result": [{"sc_item_option": "opt_sys_id_1"}]
        }

        # Second call: sc_item_option fetch
        opt_response = MagicMock()
        opt_response.raise_for_status = MagicMock()
        opt_response.json.return_value = {
            "result": [
                {
                    "item_option_new": {"name": "color", "question_text": "Color"},
                    "value": "Blue",
                }
            ]
        }

        mock_get.side_effect = [mtom_response, opt_response]

        params = GetRitmVariablesParams(ritm_sys_id="ritm_abc")
        result = get_ritm_variables(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        self.assertEqual(len(result["variables"]), 1)
        self.assertEqual(result["variables"][0]["name"], "color")
        self.assertEqual(result["variables"][0]["value"], "Blue")

    @patch("servicenow_mcp.tools.request_tools.requests.get")
    def test_get_ritm_variables_no_variables(self, mock_get):
        """Test get_ritm_variables when the RITM has no variable answers."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"result": []}
        mock_get.return_value = mock_response

        params = GetRitmVariablesParams(ritm_sys_id="ritm_empty")
        result = get_ritm_variables(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        self.assertEqual(result["variables"], [])
        self.assertIn("No variables found", result["message"])

    @patch("servicenow_mcp.tools.request_tools.requests.get")
    def test_get_ritm_variables_error(self, mock_get):
        """Test get_ritm_variables error handling."""
        mock_get.side_effect = requests.exceptions.RequestException("API error")

        params = GetRitmVariablesParams(ritm_sys_id="ritm_bad")
        result = get_ritm_variables(self.config, self.auth_manager, params)

        self.assertFalse(result["success"])
        self.assertEqual(result["variables"], [])
        self.assertIn("Error getting RITM variables", result["message"])


if __name__ == "__main__":
    unittest.main()
