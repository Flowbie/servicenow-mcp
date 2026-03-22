"""
Tests for the change management approval workflow tools.

CRUD operations (create_change_request, update_change_request, list_change_requests,
get_change_request_details, add_change_task, list_change_tasks, get_change_task,
update_change_task, close_change_task, get_cab_schedule, update_cab_details) have been
removed — these are handled by table_tools + the change_request architecture blueprint.

Remaining compound tools: submit_change_for_approval, approve_change, reject_change.
"""

import unittest
from unittest.mock import MagicMock, patch

import requests

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.change_tools import (
    approve_change,
    reject_change,
    submit_change_for_approval,
)
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig


class TestChangeApprovalTools(unittest.TestCase):
    """Tests for the change request approval workflow tools."""

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

    def test_submit_change_for_approval_missing_change_id(self):
        """Test submitting a change for approval with missing change_id."""
        params = {}
        result = submit_change_for_approval(self.auth_manager, self.server_config, params)
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.change_tools.requests.post")
    @patch("servicenow_mcp.tools.change_tools.requests.patch")
    def test_submit_change_for_approval_without_comments(self, mock_patch, mock_post):
        """Test submitting a change for approval without optional comments."""
        patch_response = MagicMock()
        patch_response.raise_for_status = MagicMock()
        approval_response = MagicMock()
        approval_response.json.return_value = {"result": {"sys_id": "approval002", "state": "requested"}}
        approval_response.raise_for_status = MagicMock()
        mock_patch.return_value = patch_response
        mock_post.return_value = approval_response

        params = {"change_id": "change456"}
        result = submit_change_for_approval(self.auth_manager, self.server_config, params)

        self.assertTrue(result["success"])
        self.assertEqual(result["approval"]["sys_id"], "approval002")

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

    def test_approve_change_missing_change_id(self):
        """Test approving a change with missing change_id."""
        params = {}
        result = approve_change(self.auth_manager, self.server_config, params)
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.change_tools.requests.patch")
    @patch("servicenow_mcp.tools.change_tools.requests.get")
    def test_approve_change_with_comments(self, mock_get, mock_patch):
        """Test that approval comments are passed to the approval record."""
        approval_query_response = MagicMock()
        approval_query_response.json.return_value = {
            "result": [{"sys_id": "approval001", "state": "requested"}]
        }
        approval_query_response.raise_for_status = MagicMock()
        mock_get.return_value = approval_query_response
        patch_response = MagicMock()
        patch_response.raise_for_status = MagicMock()
        mock_patch.return_value = patch_response

        params = {"change_id": "change123", "approval_comments": "LGTM"}
        result = approve_change(self.auth_manager, self.server_config, params)

        self.assertTrue(result["success"])
        # Verify the second patch call (approval record update) includes comments
        calls = mock_patch.call_args_list
        approval_call_body = calls[0][1]["json"]
        self.assertEqual(approval_call_body["comments"], "LGTM")

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

    def test_reject_change_missing_change_id(self):
        """Test rejecting a change with missing change_id."""
        params = {"rejection_reason": "some reason"}
        result = reject_change(self.auth_manager, self.server_config, params)
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.change_tools.requests.patch")
    @patch("servicenow_mcp.tools.change_tools.requests.get")
    def test_reject_change_reason_passed_to_approval(self, mock_get, mock_patch):
        """Test that rejection reason is passed to the approval record comments."""
        approval_query_response = MagicMock()
        approval_query_response.json.return_value = {
            "result": [{"sys_id": "approval001", "state": "requested"}]
        }
        approval_query_response.raise_for_status = MagicMock()
        mock_get.return_value = approval_query_response
        patch_response = MagicMock()
        patch_response.raise_for_status = MagicMock()
        mock_patch.return_value = patch_response

        reason = "Infrastructure freeze — no changes permitted"
        params = {"change_id": "change123", "rejection_reason": reason}
        result = reject_change(self.auth_manager, self.server_config, params)

        self.assertTrue(result["success"])
        calls = mock_patch.call_args_list
        approval_call_body = calls[0][1]["json"]
        self.assertEqual(approval_call_body["comments"], reason)


if __name__ == "__main__":
    unittest.main()
