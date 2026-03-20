"""
Tests for the change management tools.
"""

import unittest
from unittest.mock import MagicMock, patch, call

import requests

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.change_tools import (
    create_change_request,
    list_change_requests,
    get_change_request_details,
    add_change_task,
    submit_change_for_approval,
    approve_change,
    reject_change,
    list_change_tasks,
    get_change_task,
    update_change_task,
    close_change_task,
    get_cab_schedule,
    update_cab_details,
)
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig


class TestChangeTools(unittest.TestCase):
    """Tests for the change management tools."""

    def setUp(self):
        """Set up test fixtures."""
        self.auth_config = AuthConfig(
            type=AuthType.BASIC,
            basic=BasicAuthConfig(username="test_user", password="test_password"),
        )
        self.server_config = ServerConfig(
            instance_url="https://test.service-now.com",
            auth=self.auth_config,
        )
        self.auth_manager = AuthManager(self.auth_config)

    # --- list_change_requests tests ---

    @patch("servicenow_mcp.tools.change_tools.requests.get")
    def test_list_change_requests_success(self, mock_get):
        """Test listing change requests successfully."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": [
                {
                    "sys_id": "change123",
                    "number": "CHG0010001",
                    "short_description": "Test Change",
                    "type": "normal",
                    "state": "open",
                },
                {
                    "sys_id": "change456",
                    "number": "CHG0010002",
                    "short_description": "Another Test Change",
                    "type": "emergency",
                    "state": "in progress",
                },
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        params = {
            "limit": 10,
            "timeframe": "upcoming",
        }
        result = list_change_requests(self.auth_manager, self.server_config, params)

        self.assertTrue(result["success"])
        self.assertEqual(len(result["change_requests"]), 2)
        self.assertEqual(result["count"], 2)
        self.assertEqual(result["total"], 2)
        self.assertEqual(result["change_requests"][0]["sys_id"], "change123")
        self.assertEqual(result["change_requests"][1]["sys_id"], "change456")

    @patch("servicenow_mcp.tools.change_tools.requests.get")
    def test_list_change_requests_empty_result(self, mock_get):
        """Test listing change requests with empty result."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": []}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        params = {
            "limit": 10,
            "timeframe": "upcoming",
        }
        result = list_change_requests(self.auth_manager, self.server_config, params)

        self.assertTrue(result["success"])
        self.assertEqual(len(result["change_requests"]), 0)
        self.assertEqual(result["count"], 0)
        self.assertEqual(result["total"], 0)

    @patch("servicenow_mcp.tools.change_tools.requests.get")
    def test_list_change_requests_missing_result(self, mock_get):
        """Test listing change requests with missing result key."""
        mock_response = MagicMock()
        mock_response.json.return_value = {}  # No "result" key
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        params = {
            "limit": 10,
            "timeframe": "upcoming",
        }
        result = list_change_requests(self.auth_manager, self.server_config, params)

        self.assertTrue(result["success"])
        self.assertEqual(len(result["change_requests"]), 0)
        self.assertEqual(result["count"], 0)
        self.assertEqual(result["total"], 0)

    @patch("servicenow_mcp.tools.change_tools.requests.get")
    def test_list_change_requests_error(self, mock_get):
        """Test listing change requests with error."""
        mock_get.side_effect = requests.exceptions.RequestException("Test error")

        params = {
            "limit": 10,
            "timeframe": "upcoming",
        }
        result = list_change_requests(self.auth_manager, self.server_config, params)

        self.assertFalse(result["success"])
        self.assertIn("Error listing change requests", result["message"])

    @patch("servicenow_mcp.tools.change_tools.requests.get")
    def test_list_change_requests_with_filters(self, mock_get):
        """Test listing change requests with filters."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": [
                {
                    "sys_id": "change123",
                    "number": "CHG0010001",
                    "short_description": "Test Change",
                    "type": "normal",
                    "state": "open",
                }
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        params = {
            "limit": 10,
            "state": "open",
            "type": "normal",
            "category": "Hardware",
            "assignment_group": "IT Support",
            "timeframe": "upcoming",
            "query": "short_description=Test",
        }
        result = list_change_requests(self.auth_manager, self.server_config, params)

        self.assertTrue(result["success"])
        self.assertEqual(len(result["change_requests"]), 1)

        args, kwargs = mock_get.call_args
        self.assertIn("params", kwargs)
        self.assertIn("sysparm_query", kwargs["params"])
        query = kwargs["params"]["sysparm_query"]

        self.assertIn("state=open", query)
        self.assertIn("type=normal", query)
        self.assertIn("category=Hardware", query)
        self.assertIn("assignment_group=IT Support", query)
        self.assertIn("short_description=Test", query)

    @patch("servicenow_mcp.tools.change_tools.requests.get")
    def test_list_change_requests_network_error(self, mock_get):
        """Test listing change requests with a network-level error."""
        mock_get.side_effect = requests.exceptions.ConnectionError("Connection refused")

        params = {"limit": 5}
        result = list_change_requests(self.auth_manager, self.server_config, params)

        self.assertFalse(result["success"])
        self.assertIn("Error listing change requests", result["message"])

    # --- create_change_request tests ---

    @patch("servicenow_mcp.tools.change_tools.requests.post")
    def test_create_change_request_success(self, mock_post):
        """Test creating a change request successfully."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": {
                "sys_id": "change123",
                "number": "CHG0010001",
                "short_description": "Test Change",
                "type": "normal",
            }
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        params = {
            "short_description": "Test Change",
            "type": "normal",
            "risk": "low",
            "impact": "medium",
        }
        result = create_change_request(self.auth_manager, self.server_config, params)

        self.assertTrue(result["success"])
        self.assertEqual(result["change_request"]["sys_id"], "change123")
        self.assertEqual(result["change_request"]["number"], "CHG0010001")
        self.assertIn("created successfully", result["message"])

    @patch("servicenow_mcp.tools.change_tools.requests.post")
    def test_create_change_request_all_optional_fields(self, mock_post):
        """Test creating a change request with all optional fields."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": {
                "sys_id": "change789",
                "number": "CHG0010003",
                "short_description": "Full Change",
                "type": "standard",
                "description": "Detailed description",
                "risk": "high",
                "impact": "high",
                "category": "Software",
                "requested_by": "user123",
                "assignment_group": "change_team",
                "start_date": "2026-03-10 09:00:00",
                "end_date": "2026-03-10 17:00:00",
            }
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        params = {
            "short_description": "Full Change",
            "type": "standard",
            "description": "Detailed description",
            "risk": "high",
            "impact": "high",
            "category": "Software",
            "requested_by": "user123",
            "assignment_group": "change_team",
            "start_date": "2026-03-10 09:00:00",
            "end_date": "2026-03-10 17:00:00",
        }
        result = create_change_request(self.auth_manager, self.server_config, params)

        self.assertTrue(result["success"])
        self.assertEqual(result["change_request"]["sys_id"], "change789")

        # Verify request body included all optional fields
        args, kwargs = mock_post.call_args
        body = kwargs["json"]
        self.assertEqual(body["description"], "Detailed description")
        self.assertEqual(body["risk"], "high")
        self.assertEqual(body["category"], "Software")

    @patch("servicenow_mcp.tools.change_tools.requests.post")
    def test_create_change_request_missing_required_field(self, mock_post):
        """Test creating a change request with a missing required field."""
        params = {
            "type": "normal",
            # missing short_description
        }
        result = create_change_request(self.auth_manager, self.server_config, params)

        self.assertFalse(result["success"])
        mock_post.assert_not_called()

    @patch("servicenow_mcp.tools.change_tools.requests.post")
    def test_create_change_request_missing_type(self, mock_post):
        """Test creating a change request with missing type field."""
        params = {
            "short_description": "Test Change",
            # missing type
        }
        result = create_change_request(self.auth_manager, self.server_config, params)

        self.assertFalse(result["success"])
        mock_post.assert_not_called()

    @patch("servicenow_mcp.tools.change_tools.requests.post")
    def test_create_change_request_network_error(self, mock_post):
        """Test creating a change request with a network error."""
        mock_post.side_effect = requests.exceptions.ConnectionError("Connection refused")

        params = {
            "short_description": "Test Change",
            "type": "normal",
        }
        result = create_change_request(self.auth_manager, self.server_config, params)

        self.assertFalse(result["success"])
        self.assertIn("Error creating change request", result["message"])

    @patch("servicenow_mcp.tools.change_tools.requests.post")
    def test_create_change_request_with_serverconfig_no_get_headers(self, mock_post):
        """Test creating a change request where auth_manager lacks get_headers."""
        params = {
            "short_description": "Test Change",
            "type": "normal",
            "risk": "low",
            "impact": "medium",
        }

        real_server_config = ServerConfig(
            instance_url="https://test.service-now.com",
            auth=self.auth_config,
        )

        mock_auth_manager = MagicMock()
        # Remove get_headers to simulate error condition
        del mock_auth_manager.get_headers
        # Also remove instance_url so _get_instance_url fails
        del mock_auth_manager.instance_url

        result = create_change_request(mock_auth_manager, real_server_config, params)

        # The function should detect the issue and return an error message
        self.assertFalse(result["success"])
        self.assertIn("Cannot find get_headers method", result["message"])

        # Verify that the post method was never called
        mock_post.assert_not_called()

    # --- get_change_request_details tests ---

    @patch("servicenow_mcp.tools.change_tools.requests.get")
    def test_get_change_request_details_success(self, mock_get):
        """Test getting change request details successfully."""
        change_response = MagicMock()
        change_response.json.return_value = {
            "result": {
                "sys_id": "change123",
                "number": "CHG0010001",
                "short_description": "Test Change",
                "type": "normal",
                "state": "open",
            }
        }
        change_response.raise_for_status = MagicMock()

        tasks_response = MagicMock()
        tasks_response.json.return_value = {
            "result": [
                {
                    "sys_id": "task001",
                    "short_description": "Implement change",
                    "state": "open",
                }
            ]
        }
        tasks_response.raise_for_status = MagicMock()

        mock_get.side_effect = [change_response, tasks_response]

        params = {"change_id": "change123"}
        result = get_change_request_details(self.auth_manager, self.server_config, params)

        self.assertTrue(result["success"])
        self.assertEqual(result["change_request"]["sys_id"], "change123")
        self.assertEqual(len(result["tasks"]), 1)

    @patch("servicenow_mcp.tools.change_tools.requests.get")
    def test_get_change_request_details_network_error(self, mock_get):
        """Test getting change request details with a network error."""
        mock_get.side_effect = requests.exceptions.RequestException("Network error")

        params = {"change_id": "change123"}
        result = get_change_request_details(self.auth_manager, self.server_config, params)

        self.assertFalse(result["success"])
        self.assertIn("Error getting change request details", result["message"])

    @patch("servicenow_mcp.tools.change_tools.requests.get")
    def test_get_change_request_details_missing_change_id(self, mock_get):
        """Test getting change request details with missing change_id."""
        params = {}
        result = get_change_request_details(self.auth_manager, self.server_config, params)

        self.assertFalse(result["success"])
        mock_get.assert_not_called()

    # --- add_change_task tests ---

    @patch("servicenow_mcp.tools.change_tools.requests.post")
    def test_add_change_task_success(self, mock_post):
        """Test adding a task to a change request successfully."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": {
                "sys_id": "task001",
                "short_description": "Implement change",
                "change_request": "change123",
                "state": "open",
            }
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        params = {
            "change_id": "change123",
            "short_description": "Implement change",
            "description": "Steps to implement the change",
            "assigned_to": "user123",
        }
        result = add_change_task(self.auth_manager, self.server_config, params)

        self.assertTrue(result["success"])
        self.assertIn("added successfully", result["message"])
        self.assertEqual(result["change_task"]["sys_id"], "task001")

        args, kwargs = mock_post.call_args
        self.assertIn("/change_task", args[0])
        self.assertEqual(kwargs["json"]["change_request"], "change123")

    @patch("servicenow_mcp.tools.change_tools.requests.post")
    def test_add_change_task_network_error(self, mock_post):
        """Test adding a change task with a network error."""
        mock_post.side_effect = requests.exceptions.RequestException("Network error")

        params = {
            "change_id": "change123",
            "short_description": "Implement change",
        }
        result = add_change_task(self.auth_manager, self.server_config, params)

        self.assertFalse(result["success"])
        self.assertIn("Error adding change task", result["message"])

    @patch("servicenow_mcp.tools.change_tools.requests.post")
    def test_add_change_task_missing_required_fields(self, mock_post):
        """Test adding a change task with missing required fields."""
        params = {
            "change_id": "change123",
            # missing short_description
        }
        result = add_change_task(self.auth_manager, self.server_config, params)

        self.assertFalse(result["success"])
        mock_post.assert_not_called()

    # --- submit_change_for_approval tests ---

    @patch("servicenow_mcp.tools.change_tools.requests.post")
    @patch("servicenow_mcp.tools.change_tools.requests.patch")
    def test_submit_change_for_approval_success(self, mock_patch, mock_post):
        """Test submitting a change for approval successfully."""
        patch_response = MagicMock()
        patch_response.raise_for_status = MagicMock()

        approval_response = MagicMock()
        approval_response.json.return_value = {
            "result": {
                "sys_id": "approval001",
                "state": "requested",
            }
        }
        approval_response.raise_for_status = MagicMock()

        mock_patch.return_value = patch_response
        mock_post.return_value = approval_response

        params = {
            "change_id": "change123",
            "approval_comments": "Ready for review",
        }
        result = submit_change_for_approval(self.auth_manager, self.server_config, params)

        self.assertTrue(result["success"])
        self.assertIn("submitted for approval", result["message"])
        self.assertEqual(result["approval"]["sys_id"], "approval001")

    @patch("servicenow_mcp.tools.change_tools.requests.patch")
    def test_submit_change_for_approval_network_error(self, mock_patch):
        """Test submitting a change for approval with a network error."""
        mock_patch.side_effect = requests.exceptions.RequestException("Network error")

        params = {"change_id": "change123"}
        result = submit_change_for_approval(self.auth_manager, self.server_config, params)

        self.assertFalse(result["success"])
        self.assertIn("Error submitting change for approval", result["message"])

    # --- approve_change tests ---

    @patch("servicenow_mcp.tools.change_tools.requests.patch")
    @patch("servicenow_mcp.tools.change_tools.requests.get")
    def test_approve_change_success(self, mock_get, mock_patch):
        """Test approving a change request successfully."""
        approval_query_response = MagicMock()
        approval_query_response.json.return_value = {
            "result": [{"sys_id": "approval001", "state": "requested"}]
        }
        approval_query_response.raise_for_status = MagicMock()
        mock_get.return_value = approval_query_response

        patch_response = MagicMock()
        patch_response.raise_for_status = MagicMock()
        mock_patch.return_value = patch_response

        params = {
            "change_id": "change123",
            "approval_comments": "Approved",
        }
        result = approve_change(self.auth_manager, self.server_config, params)

        self.assertTrue(result["success"])
        self.assertIn("approved successfully", result["message"])

    @patch("servicenow_mcp.tools.change_tools.requests.get")
    def test_approve_change_no_approval_record(self, mock_get):
        """Test approving a change when no approval record exists."""
        approval_query_response = MagicMock()
        approval_query_response.json.return_value = {"result": []}
        approval_query_response.raise_for_status = MagicMock()
        mock_get.return_value = approval_query_response

        params = {"change_id": "change123"}
        result = approve_change(self.auth_manager, self.server_config, params)

        self.assertFalse(result["success"])
        self.assertIn("No approval record found", result["message"])

    @patch("servicenow_mcp.tools.change_tools.requests.get")
    def test_approve_change_network_error(self, mock_get):
        """Test approving a change with a network error."""
        mock_get.side_effect = requests.exceptions.RequestException("Network error")

        params = {"change_id": "change123"}
        result = approve_change(self.auth_manager, self.server_config, params)

        self.assertFalse(result["success"])
        self.assertIn("Error approving change", result["message"])

    # --- reject_change tests ---

    @patch("servicenow_mcp.tools.change_tools.requests.patch")
    @patch("servicenow_mcp.tools.change_tools.requests.get")
    def test_reject_change_success(self, mock_get, mock_patch):
        """Test rejecting a change request successfully."""
        approval_query_response = MagicMock()
        approval_query_response.json.return_value = {
            "result": [{"sys_id": "approval001", "state": "requested"}]
        }
        approval_query_response.raise_for_status = MagicMock()
        mock_get.return_value = approval_query_response

        patch_response = MagicMock()
        patch_response.raise_for_status = MagicMock()
        mock_patch.return_value = patch_response

        params = {
            "change_id": "change123",
            "rejection_reason": "Does not meet standards",
        }
        result = reject_change(self.auth_manager, self.server_config, params)

        self.assertTrue(result["success"])
        self.assertIn("rejected successfully", result["message"])

    @patch("servicenow_mcp.tools.change_tools.requests.get")
    def test_reject_change_no_approval_record(self, mock_get):
        """Test rejecting a change when no approval record exists."""
        approval_query_response = MagicMock()
        approval_query_response.json.return_value = {"result": []}
        approval_query_response.raise_for_status = MagicMock()
        mock_get.return_value = approval_query_response

        params = {
            "change_id": "change123",
            "rejection_reason": "Does not meet standards",
        }
        result = reject_change(self.auth_manager, self.server_config, params)

        self.assertFalse(result["success"])
        self.assertIn("No approval record found", result["message"])

    @patch("servicenow_mcp.tools.change_tools.requests.get")
    def test_reject_change_missing_rejection_reason(self, mock_get):
        """Test rejecting a change with missing rejection_reason."""
        params = {
            "change_id": "change123",
            # missing rejection_reason
        }
        result = reject_change(self.auth_manager, self.server_config, params)

        self.assertFalse(result["success"])
        mock_get.assert_not_called()

    @patch("servicenow_mcp.tools.change_tools.requests.get")
    def test_reject_change_network_error(self, mock_get):
        """Test rejecting a change with a network error."""
        mock_get.side_effect = requests.exceptions.RequestException("Network error")

        params = {
            "change_id": "change123",
            "rejection_reason": "Does not meet standards",
        }
        result = reject_change(self.auth_manager, self.server_config, params)

        self.assertFalse(result["success"])
        self.assertIn("Error rejecting change", result["message"])


class TestChangeTaskTools(unittest.TestCase):
    """Tests for Phase 3 change task and CAB tools."""

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

    # --- list_change_tasks ---

    @patch("servicenow_mcp.tools.change_tools.requests.get")
    def test_list_change_tasks_success(self, mock_get):
        """Test listing change tasks successfully."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": [
                {"sys_id": "task1", "short_description": "Pre-check", "state": "1"},
                {"sys_id": "task2", "short_description": "Deploy", "state": "1"},
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = list_change_tasks(self.auth_manager, self.server_config, {"change_request_id": "chg123"})

        self.assertTrue(result["success"])
        self.assertEqual(len(result["change_tasks"]), 2)
        self.assertEqual(result["count"], 2)

    @patch("servicenow_mcp.tools.change_tools.requests.get")
    def test_list_change_tasks_empty(self, mock_get):
        """Test listing change tasks returns empty list."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": []}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = list_change_tasks(self.auth_manager, self.server_config, {"change_request_id": "chg123"})

        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 0)

    def test_list_change_tasks_missing_required(self):
        """Test that missing change_request_id returns error."""
        result = list_change_tasks(self.auth_manager, self.server_config, {})
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.change_tools.requests.get")
    def test_list_change_tasks_http_error(self, mock_get):
        """Test list_change_tasks handles HTTP errors."""
        mock_get.side_effect = requests.exceptions.RequestException("connection error")
        result = list_change_tasks(self.auth_manager, self.server_config, {"change_request_id": "chg123"})
        self.assertFalse(result["success"])
        self.assertIn("Error listing change tasks", result["message"])

    # --- get_change_task ---

    @patch("servicenow_mcp.tools.change_tools.requests.get")
    def test_get_change_task_success(self, mock_get):
        """Test getting a change task by sys_id."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": {"sys_id": "task1", "short_description": "Pre-check", "state": "1"}
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = get_change_task(self.auth_manager, self.server_config, {"task_id": "task1"})

        self.assertTrue(result["success"])
        self.assertEqual(result["change_task"]["sys_id"], "task1")

    def test_get_change_task_missing_required(self):
        """Test that missing task_id returns error."""
        result = get_change_task(self.auth_manager, self.server_config, {})
        self.assertFalse(result["success"])

    # --- update_change_task ---

    @patch("servicenow_mcp.tools.change_tools.requests.patch")
    def test_update_change_task_success(self, mock_patch):
        """Test updating a change task state and assignment."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": {"sys_id": "task1", "state": "2", "assigned_to": "user1"}
        }
        mock_response.raise_for_status = MagicMock()
        mock_patch.return_value = mock_response

        result = update_change_task(
            self.auth_manager,
            self.server_config,
            {"task_id": "task1", "state": "2", "assigned_to": "user1"},
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["message"], "Change task updated successfully")
        self.assertEqual(result["change_task"]["state"], "2")

    @patch("servicenow_mcp.tools.change_tools.requests.patch")
    def test_update_change_task_http_error(self, mock_patch):
        """Test update_change_task handles HTTP errors."""
        mock_patch.side_effect = requests.exceptions.RequestException("timeout")
        result = update_change_task(self.auth_manager, self.server_config, {"task_id": "task1", "state": "2"})
        self.assertFalse(result["success"])
        self.assertIn("Error updating change task", result["message"])

    def test_update_change_task_missing_required(self):
        """Test that missing task_id returns error."""
        result = update_change_task(self.auth_manager, self.server_config, {"state": "2"})
        self.assertFalse(result["success"])

    # --- close_change_task ---

    @patch("servicenow_mcp.tools.change_tools.requests.patch")
    def test_close_change_task_success(self, mock_patch):
        """Test closing a change task with required fields."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": {"sys_id": "task1", "state": "3", "close_code": "successful"}
        }
        mock_response.raise_for_status = MagicMock()
        mock_patch.return_value = mock_response

        result = close_change_task(
            self.auth_manager,
            self.server_config,
            {"task_id": "task1", "state": "3", "close_code": "successful", "close_notes": "Done"},
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["message"], "Change task closed successfully")

    def test_close_change_task_missing_close_code(self):
        """Test that missing close_code returns error."""
        result = close_change_task(
            self.auth_manager, self.server_config, {"task_id": "task1", "state": "3"}
        )
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.change_tools.requests.patch")
    def test_close_change_task_http_error(self, mock_patch):
        """Test close_change_task handles HTTP errors."""
        mock_patch.side_effect = requests.exceptions.RequestException("error")
        result = close_change_task(
            self.auth_manager,
            self.server_config,
            {"task_id": "task1", "state": "4", "close_code": "unsuccessful"},
        )
        self.assertFalse(result["success"])
        self.assertIn("Error closing change task", result["message"])

    # --- get_cab_schedule ---

    @patch("servicenow_mcp.tools.change_tools.requests.get")
    def test_get_cab_schedule_success(self, mock_get):
        """Test reading CAB schedule from a change request."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": {
                "sys_id": "chg123",
                "number": "CHG0010001",
                "cab_required": "true",
                "cab_date_time": "2026-04-01 10:00:00",
                "short_description": "Deploy",
            }
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = get_cab_schedule(self.auth_manager, self.server_config, {"change_id": "chg123"})

        self.assertTrue(result["success"])
        self.assertEqual(result["cab_required"], "true")
        self.assertEqual(result["cab_date_time"], "2026-04-01 10:00:00")
        self.assertEqual(result["number"], "CHG0010001")

    def test_get_cab_schedule_missing_required(self):
        """Test that missing change_id returns error."""
        result = get_cab_schedule(self.auth_manager, self.server_config, {})
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.change_tools.requests.get")
    def test_get_cab_schedule_http_error(self, mock_get):
        """Test get_cab_schedule handles HTTP errors."""
        mock_get.side_effect = requests.exceptions.RequestException("timeout")
        result = get_cab_schedule(self.auth_manager, self.server_config, {"change_id": "chg123"})
        self.assertFalse(result["success"])
        self.assertIn("Error getting CAB schedule", result["message"])

    # --- update_cab_details ---

    @patch("servicenow_mcp.tools.change_tools.requests.patch")
    def test_update_cab_details_success(self, mock_patch):
        """Test updating CAB details on a change request."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": {
                "cab_required": "true",
                "cab_date_time": "2026-04-15 14:00:00",
            }
        }
        mock_response.raise_for_status = MagicMock()
        mock_patch.return_value = mock_response

        result = update_cab_details(
            self.auth_manager,
            self.server_config,
            {"change_id": "chg123", "cab_required": True, "cab_date_time": "2026-04-15 14:00:00"},
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["message"], "CAB details updated successfully")
        self.assertEqual(result["cab_date_time"], "2026-04-15 14:00:00")

    def test_update_cab_details_missing_required(self):
        """Test that missing change_id returns error."""
        result = update_cab_details(self.auth_manager, self.server_config, {"cab_required": True})
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.change_tools.requests.patch")
    def test_update_cab_details_http_error(self, mock_patch):
        """Test update_cab_details handles HTTP errors."""
        mock_patch.side_effect = requests.exceptions.RequestException("error")
        result = update_cab_details(
            self.auth_manager, self.server_config, {"change_id": "chg123", "cab_required": False}
        )
        self.assertFalse(result["success"])
        self.assertIn("Error updating CAB details", result["message"])


    def test_close_change_task_invalid_state_rejected(self):
        """close_change_task rejects state values other than '3' or '4'."""
        result = close_change_task(
            self.auth_manager,
            self.server_config,
            {"task_id": "t1", "state": "open", "close_code": "successful"},
        )
        self.assertFalse(result["success"])
        self.assertTrue(
            "state" in result.get("message", "").lower()
            or "validation" in result.get("message", "").lower(),
            f"Expected state validation error, got: {result.get('message')}",
        )

    def test_close_change_task_invalid_close_code_rejected(self):
        """close_change_task rejects close_code values outside the allowed set."""
        result = close_change_task(
            self.auth_manager,
            self.server_config,
            {"task_id": "t1", "state": "3", "close_code": "invalid_code"},
        )
        self.assertFalse(result["success"])
        self.assertTrue(
            "close_code" in result.get("message", "").lower()
            or "validation" in result.get("message", "").lower(),
            f"Expected close_code validation error, got: {result.get('message')}",
        )

    @patch("servicenow_mcp.tools.change_tools.requests.patch")
    def test_close_change_task_valid_states_accepted(self, mock_patch):
        """close_change_task accepts '3' and '4' as valid states."""
        mock_patch.return_value = MagicMock(**{
            "json.return_value": {"result": {"sys_id": "t1"}},
            "raise_for_status": MagicMock(),
        })
        for valid_state in ["3", "4"]:
            result = close_change_task(
                self.auth_manager,
                self.server_config,
                {"task_id": "t1", "state": valid_state, "close_code": "successful"},
            )
            self.assertTrue(result["success"], f"state='{valid_state}' should be accepted")


if __name__ == "__main__":
    unittest.main()
