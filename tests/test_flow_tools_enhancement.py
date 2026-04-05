"""Tests for flow_tools enhancement — Tasks 0-5."""
import unittest
from unittest.mock import MagicMock, patch

import requests

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig


def _make_config():
    return ServerConfig(
        instance_url="https://test.service-now.com",
        auth=AuthConfig(
            type=AuthType.BASIC,
            basic=BasicAuthConfig(username="u", password="p"),
        ),
    )


def _make_auth():
    m = MagicMock(spec=AuthManager)
    m.get_headers.return_value = {"Authorization": "Bearer FAKE"}
    return m


class TestListActionTypes(unittest.TestCase):

    @patch("servicenow_mcp.tools.flow_tools.requests.get")
    def test_returns_action_types_with_both_sys_ids(self, mock_get):
        from servicenow_mcp.tools.flow_tools import ListActionTypesParams, list_action_types
        mock_get.return_value.raise_for_status = MagicMock()
        mock_get.return_value.json.return_value = {
            "result": [
                {
                    "sys_id": "def_id_1",
                    "name": "Look Up Record",
                    "internal_name": "glide_record_lookup",
                    "action_type_base": {"value": "base_id_1"},
                    "spoke": {"display_value": "ServiceNow Core"},
                    "description": "Look up a record",
                },
            ]
        }
        result = list_action_types(_make_config(), _make_auth(), ListActionTypesParams(query="Look Up"))
        self.assertEqual(len(result.action_types), 1)
        self.assertEqual(result.action_types[0].definition_sys_id, "def_id_1")
        self.assertEqual(result.action_types[0].base_sys_id, "base_id_1")
        self.assertEqual(result.action_types[0].name, "Look Up Record")

    @patch("servicenow_mcp.tools.flow_tools.requests.get")
    def test_queries_sys_hub_action_type_definition(self, mock_get):
        from servicenow_mcp.tools.flow_tools import ListActionTypesParams, list_action_types
        mock_get.return_value.raise_for_status = MagicMock()
        mock_get.return_value.json.return_value = {"result": []}
        list_action_types(_make_config(), _make_auth(), ListActionTypesParams(query="x"))
        url = mock_get.call_args[0][0]
        self.assertIn("sys_hub_action_type_definition", url)

    @patch("servicenow_mcp.tools.flow_tools.requests.get")
    def test_query_filter_applied(self, mock_get):
        from servicenow_mcp.tools.flow_tools import ListActionTypesParams, list_action_types
        mock_get.return_value.raise_for_status = MagicMock()
        mock_get.return_value.json.return_value = {"result": []}
        list_action_types(_make_config(), _make_auth(), ListActionTypesParams(query="Create Record"))
        q = mock_get.call_args[1]["params"]["sysparm_query"]
        self.assertIn("Create Record", q)

    @patch("servicenow_mcp.tools.flow_tools.requests.get")
    def test_http_error_returns_empty(self, mock_get):
        from servicenow_mcp.tools.flow_tools import ListActionTypesParams, list_action_types
        mock_get.return_value.raise_for_status.side_effect = requests.HTTPError("500")
        mock_get.return_value.text = "Error"
        result = list_action_types(_make_config(), _make_auth(), ListActionTypesParams(query="x"))
        self.assertEqual(result.action_types, [])
        self.assertIn("Failed", result.message)

    @patch("servicenow_mcp.tools.flow_tools.requests.get")
    def test_base_sys_id_extracted_from_nested_value(self, mock_get):
        """action_type_base is a reference field returned as {value: sys_id, display_value: name}."""
        from servicenow_mcp.tools.flow_tools import ListActionTypesParams, list_action_types
        mock_get.return_value.raise_for_status = MagicMock()
        mock_get.return_value.json.return_value = {
            "result": [
                {"sys_id": "d1", "name": "A", "internal_name": "a", "action_type_base": {"value": "b1"}, "spoke": {}, "description": ""},
            ]
        }
        result = list_action_types(_make_config(), _make_auth(), ListActionTypesParams(query="A"))
        self.assertEqual(result.action_types[0].base_sys_id, "b1")
