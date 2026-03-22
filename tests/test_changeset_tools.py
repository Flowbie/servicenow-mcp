"""
Tests for the changeset tools.

Only compound tool tests are retained here.
CRUD operations (list, create, update, commit, publish, add_file) have been
removed — those are handled by table_tools + sys_update_set architecture blueprint.
"""

import unittest
from unittest.mock import MagicMock, patch

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.changeset_tools import (
    GetChangesetDetailsParams,
    SetCurrentUpdateSetParams,
    get_changeset_details,
    set_current_update_set,
)
from servicenow_mcp.utils.config import ServerConfig, AuthConfig, AuthType, BasicAuthConfig


class TestChangesetTools(unittest.TestCase):
    """Tests for the compound changeset tools."""

    def setUp(self):
        """Set up test fixtures."""
        auth_config = AuthConfig(
            type=AuthType.BASIC,
            basic=BasicAuthConfig(
                username="test_user",
                password="test_password"
            )
        )
        self.server_config = ServerConfig(
            instance_url="https://test.service-now.com",
            auth=auth_config,
        )
        self.auth_manager = MagicMock(spec=AuthManager)
        self.auth_manager.get_headers.return_value = {"Authorization": "Bearer test"}

    @patch("servicenow_mcp.tools.changeset_tools.requests.get")
    def test_get_changeset_details(self, mock_get):
        """Test getting changeset details."""
        # Mock responses
        mock_changeset_response = MagicMock()
        mock_changeset_response.json.return_value = {
            "result": {
                "sys_id": "123",
                "name": "Test Changeset",
                "state": "in_progress",
                "application": "Test App",
                "developer": "test.user",
            }
        }
        mock_changeset_response.raise_for_status.return_value = None

        mock_changes_response = MagicMock()
        mock_changes_response.json.return_value = {
            "result": [
                {
                    "sys_id": "456",
                    "name": "test_file.py",
                    "type": "file",
                    "update_set": "123",
                }
            ]
        }
        mock_changes_response.raise_for_status.return_value = None

        # Set up the mock to return different responses for different URLs
        def side_effect(*args, **kwargs):
            url = args[0]
            if "sys_update_set" in url:
                return mock_changeset_response
            elif "sys_update_xml" in url:
                return mock_changes_response
            return None

        mock_get.side_effect = side_effect

        # Call the function
        params = {"changeset_id": "123"}
        result = get_changeset_details(self.server_config, self.auth_manager, params)

        # Verify the result
        self.assertTrue(result["success"])
        self.assertEqual(result["changeset"]["sys_id"], "123")
        self.assertEqual(result["changeset"]["name"], "Test Changeset")
        self.assertEqual(len(result["changes"]), 1)
        self.assertEqual(result["changes"][0]["sys_id"], "456")
        self.assertEqual(result["changes"][0]["name"], "test_file.py")

        # Verify the API calls
        self.assertEqual(mock_get.call_count, 2)
        first_call_args, first_call_kwargs = mock_get.call_args_list[0]
        self.assertEqual(
            first_call_args[0], "https://test.service-now.com/api/now/table/sys_update_set/123"
        )
        self.assertEqual(first_call_kwargs["headers"], {"Authorization": "Bearer test"})

        second_call_args, second_call_kwargs = mock_get.call_args_list[1]
        self.assertEqual(
            second_call_args[0], "https://test.service-now.com/api/now/table/sys_update_xml"
        )
        self.assertEqual(second_call_kwargs["headers"], {"Authorization": "Bearer test"})
        self.assertEqual(second_call_kwargs["params"]["sysparm_query"], "update_set=123")

    @patch("servicenow_mcp.tools.changeset_tools.requests.get")
    def test_get_changeset_details_missing_id(self, mock_get):
        """Test get_changeset_details returns failure when changeset_id is missing."""
        params = {}
        result = get_changeset_details(self.server_config, self.auth_manager, params)
        self.assertFalse(result["success"])
        mock_get.assert_not_called()

    @patch("servicenow_mcp.tools.changeset_tools.requests.get")
    def test_set_current_update_set_success(self, mock_get):
        """Test set_current_update_set activates an in-progress update set."""
        # First call: validate the update set exists and is in progress
        check_resp = MagicMock()
        check_resp.raise_for_status.return_value = None
        check_resp.json.return_value = {
            "result": {"sys_id": "us1", "name": "My US", "state": "in progress"}
        }

        # Second call: query existing sys_user_preference
        pref_resp = MagicMock()
        pref_resp.raise_for_status.return_value = None
        pref_resp.json.return_value = {"result": [{"sys_id": "pref1"}]}

        mock_get.side_effect = [check_resp, pref_resp]

        with patch("servicenow_mcp.tools.changeset_tools.requests.patch") as mock_patch:
            patch_resp = MagicMock()
            patch_resp.raise_for_status.return_value = None
            mock_patch.return_value = patch_resp

            params = SetCurrentUpdateSetParams(changeset_id="us1")
            result = set_current_update_set(self.server_config, self.auth_manager, params)

        self.assertTrue(result["success"])
        self.assertIn("My US", result["message"])

    @patch("servicenow_mcp.tools.changeset_tools.requests.get")
    def test_set_current_update_set_wrong_state(self, mock_get):
        """Test set_current_update_set rejects update sets not in 'in progress' state."""
        check_resp = MagicMock()
        check_resp.raise_for_status.return_value = None
        check_resp.json.return_value = {
            "result": {"sys_id": "us2", "name": "Closed US", "state": "complete"}
        }
        mock_get.return_value = check_resp

        params = SetCurrentUpdateSetParams(changeset_id="us2")
        result = set_current_update_set(self.server_config, self.auth_manager, params)

        self.assertFalse(result["success"])
        self.assertIn("complete", result["message"])

    @patch("servicenow_mcp.tools.changeset_tools.requests.get")
    def test_set_current_update_set_creates_preference_when_missing(self, mock_get):
        """Test set_current_update_set creates a new preference when none exists."""
        check_resp = MagicMock()
        check_resp.raise_for_status.return_value = None
        check_resp.json.return_value = {
            "result": {"sys_id": "us3", "name": "New US", "state": "in progress"}
        }

        pref_resp = MagicMock()
        pref_resp.raise_for_status.return_value = None
        pref_resp.json.return_value = {"result": []}  # no existing preference

        mock_get.side_effect = [check_resp, pref_resp]

        with patch("servicenow_mcp.tools.changeset_tools.requests.post") as mock_post:
            post_resp = MagicMock()
            post_resp.raise_for_status.return_value = None
            mock_post.return_value = post_resp

            params = SetCurrentUpdateSetParams(changeset_id="us3")
            result = set_current_update_set(self.server_config, self.auth_manager, params)

        self.assertTrue(result["success"])
        mock_post.assert_called_once()


class TestChangesetToolsParams(unittest.TestCase):
    """Tests for the compound changeset param models."""

    def test_get_changeset_details_params(self):
        """Test GetChangesetDetailsParams."""
        params = GetChangesetDetailsParams(changeset_id="123")
        self.assertEqual(params.changeset_id, "123")

    def test_set_current_update_set_params(self):
        """Test SetCurrentUpdateSetParams."""
        params = SetCurrentUpdateSetParams(changeset_id="abc")
        self.assertEqual(params.changeset_id, "abc")

    def test_set_current_update_set_params_requires_id(self):
        """Test SetCurrentUpdateSetParams raises when changeset_id missing."""
        with self.assertRaises(Exception):
            SetCurrentUpdateSetParams()


if __name__ == "__main__":
    unittest.main()
