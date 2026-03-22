"""
Tests for the ServiceNow MCP request tools.

Only compound tool tests are retained here.
CRUD operations (list_requests, get_request, list_request_items, update_request_item,
list_sc_tasks, update_sc_task) have been removed — those are handled by
table_tools + sc_request / sc_req_item / sc_task architecture blueprints.
"""

import unittest
from unittest.mock import MagicMock, patch

import requests

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.request_tools import (
    GetRitmVariablesParams,
    get_ritm_variables,
)
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig


class TestRequestTools(unittest.TestCase):
    """Test cases for the compound request tools."""

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

    @patch("servicenow_mcp.tools.request_tools.requests.get")
    def test_get_ritm_variables_dict_ref_handling(self, mock_get):
        """Test get_ritm_variables handles dict-style reference fields correctly."""
        # mtom row where sc_item_option is a dict (display_value=true returns dicts for refs)
        mtom_response = MagicMock()
        mtom_response.raise_for_status = MagicMock()
        mtom_response.json.return_value = {
            "result": [{"sc_item_option": {"value": "opt_id_dict", "display_value": "Opt"}}]
        }

        opt_response = MagicMock()
        opt_response.raise_for_status = MagicMock()
        opt_response.json.return_value = {
            "result": [
                {
                    "item_option_new": {"name": "size", "question_text": "Size"},
                    "value": "Large",
                }
            ]
        }

        mock_get.side_effect = [mtom_response, opt_response]

        params = GetRitmVariablesParams(ritm_sys_id="ritm_dict")
        result = get_ritm_variables(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        self.assertEqual(len(result["variables"]), 1)
        self.assertEqual(result["variables"][0]["name"], "size")
        self.assertEqual(result["variables"][0]["value"], "Large")

    @patch("servicenow_mcp.tools.request_tools.requests.get")
    def test_get_ritm_variables_skips_empty_option_ref(self, mock_get):
        """Test get_ritm_variables skips mtom rows with empty sc_item_option."""
        mtom_response = MagicMock()
        mtom_response.raise_for_status = MagicMock()
        mtom_response.json.return_value = {
            "result": [{"sc_item_option": ""}]  # empty — should be skipped
        }
        mock_get.return_value = mtom_response

        # A second call for sc_item_option should NOT happen
        params = GetRitmVariablesParams(ritm_sys_id="ritm_skip")
        result = get_ritm_variables(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        self.assertEqual(result["variables"], [])
        # Only one call (mtom), no second call for the option record
        self.assertEqual(mock_get.call_count, 1)


class TestGetRitmVariablesParams(unittest.TestCase):
    """Tests for GetRitmVariablesParams."""

    def test_requires_ritm_sys_id(self):
        """Test GetRitmVariablesParams raises when ritm_sys_id is missing."""
        with self.assertRaises(Exception):
            GetRitmVariablesParams()

    def test_valid_params(self):
        """Test valid GetRitmVariablesParams."""
        params = GetRitmVariablesParams(ritm_sys_id="ritm_xyz")
        self.assertEqual(params.ritm_sys_id, "ritm_xyz")


if __name__ == "__main__":
    unittest.main()
