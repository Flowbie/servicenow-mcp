"""
Tests for integration_tools.py compound functions.

Covers get_rest_message and get_scripted_rest_api.

CRUD for integration tables (sys_rest_message, sys_ws_definition, sys_import_set,
ecc_agent, sys_transform_map) is handled by table_tools; tests for those
operations live in test_table_tools.py.
"""

import unittest
from unittest.mock import MagicMock, patch

from servicenow_mcp.auth.auth_manager import AuthManager
import requests

from servicenow_mcp.tools.integration_tools import (
    GetRestMessageParams,
    GetScriptedRestApiParams,
    get_rest_message,
    get_scripted_rest_api,
)
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig


INSTANCE_URL = "https://dev99999.service-now.com"


def _make_config() -> ServerConfig:
    auth_config = AuthConfig(
        type=AuthType.BASIC,
        basic=BasicAuthConfig(username="test_user", password="test_password"),
    )
    return ServerConfig(instance_url=INSTANCE_URL, auth=auth_config)


def _make_auth_manager() -> MagicMock:
    auth_manager = MagicMock(spec=AuthManager)
    auth_manager.get_headers.return_value = {"Authorization": "Bearer FAKE_TOKEN"}
    return auth_manager


def _mock_response(json_data: dict, status_code: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.raise_for_status = MagicMock()
    return resp


class TestGetRestMessage(unittest.TestCase):
    """Tests for get_rest_message."""

    def setUp(self):
        self.config = _make_config()
        self.auth_manager = _make_auth_manager()

    @patch("servicenow_mcp.tools.integration_tools.requests.get")
    def test_success_by_name(self, mock_get):
        msg_record = {"sys_id": "msg001", "name": "SlackIntegration"}
        fn_records = [
            {"sys_id": "fn001", "function_name": "sendMessage", "http_method": "post"}
        ]
        mock_get.side_effect = [
            _mock_response({"result": [msg_record]}),
            _mock_response({"result": fn_records}),
        ]

        params = GetRestMessageParams(message_name="SlackIntegration")
        result = get_rest_message(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        self.assertEqual(result["message_record"]["sys_id"], "msg001")
        self.assertEqual(len(result["http_methods"]), 1)
        self.assertEqual(mock_get.call_count, 2)

    @patch("servicenow_mcp.tools.integration_tools.requests.get")
    def test_success_by_sys_id(self, mock_get):
        msg_record = {"sys_id": "msg002", "name": "ServiceNowIntegration"}
        mock_get.side_effect = [
            _mock_response({"result": [msg_record]}),
            _mock_response({"result": []}),
        ]

        params = GetRestMessageParams(message_sys_id="msg002")
        result = get_rest_message(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        self.assertEqual(result["message_record"]["sys_id"], "msg002")
        self.assertEqual(len(result["http_methods"]), 0)

    @patch("servicenow_mcp.tools.integration_tools.requests.get")
    def test_not_found_returns_failure(self, mock_get):
        mock_get.return_value = _mock_response({"result": []})

        params = GetRestMessageParams(message_sys_id="nonexistent")
        result = get_rest_message(self.config, self.auth_manager, params)

        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    def test_validator_requires_at_least_one(self):
        from pydantic import ValidationError

        with self.assertRaises(ValidationError):
            GetRestMessageParams()

    @patch("servicenow_mcp.tools.integration_tools.requests.get")
    def test_http_error_returns_failure(self, mock_get):
        resp = MagicMock()
        resp.raise_for_status.side_effect = requests.HTTPError("404 Not Found")
        mock_get.return_value = resp

        params = GetRestMessageParams(message_name="AnyMsg")
        result = get_rest_message(self.config, self.auth_manager, params)

        self.assertFalse(result["success"])
        self.assertIn("HTTP error", result["message"])

    @patch("servicenow_mcp.tools.integration_tools.requests.get")
    def test_second_request_fetches_http_methods(self, mock_get):
        """Verify the second GET call targets sys_rest_message_fn."""
        msg_record = {"sys_id": "msg003", "name": "TestMsg"}
        mock_get.side_effect = [
            _mock_response({"result": [msg_record]}),
            _mock_response({"result": [{"sys_id": "fn1"}, {"sys_id": "fn2"}]}),
        ]

        params = GetRestMessageParams(message_name="TestMsg")
        result = get_rest_message(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        self.assertEqual(len(result["http_methods"]), 2)
        second_url = mock_get.call_args_list[1][0][0]
        self.assertIn("sys_rest_message_fn", second_url)


class TestGetScriptedRestApi(unittest.TestCase):
    """Tests for get_scripted_rest_api."""

    def setUp(self):
        self.config = _make_config()
        self.auth_manager = _make_auth_manager()

    @patch("servicenow_mcp.tools.integration_tools.requests.get")
    def test_success_by_sys_id(self, mock_get):
        api_record = {"sys_id": "api001", "name": "InventoryAPI"}
        operations = [
            {"sys_id": "op001", "name": "getItem", "http_method": "GET"}
        ]
        mock_get.side_effect = [
            _mock_response({"result": [api_record]}),
            _mock_response({"result": operations}),
        ]

        params = GetScriptedRestApiParams(api_sys_id="api001")
        result = get_scripted_rest_api(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        self.assertEqual(result["api_record"]["name"], "InventoryAPI")
        self.assertEqual(len(result["operations"]), 1)
        self.assertEqual(mock_get.call_count, 2)

    @patch("servicenow_mcp.tools.integration_tools.requests.get")
    def test_success_by_name(self, mock_get):
        api_record = {"sys_id": "api002", "name": "OrdersAPI"}
        mock_get.side_effect = [
            _mock_response({"result": [api_record]}),
            _mock_response({"result": []}),
        ]

        params = GetScriptedRestApiParams(api_name="OrdersAPI")
        result = get_scripted_rest_api(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        self.assertEqual(result["api_record"]["sys_id"], "api002")
        self.assertEqual(len(result["operations"]), 0)

    @patch("servicenow_mcp.tools.integration_tools.requests.get")
    def test_not_found(self, mock_get):
        mock_get.return_value = _mock_response({"result": []})

        params = GetScriptedRestApiParams(api_name="Ghost")
        result = get_scripted_rest_api(self.config, self.auth_manager, params)

        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    def test_validator_requires_at_least_one(self):
        from pydantic import ValidationError

        with self.assertRaises(ValidationError):
            GetScriptedRestApiParams()

    @patch("servicenow_mcp.tools.integration_tools.requests.get")
    def test_second_request_fetches_operations(self, mock_get):
        """Verify the second GET call targets sys_ws_operation."""
        api_record = {"sys_id": "api003", "name": "CatalogAPI"}
        mock_get.side_effect = [
            _mock_response({"result": [api_record]}),
            _mock_response({"result": [{"sys_id": "op1"}, {"sys_id": "op2"}, {"sys_id": "op3"}]}),
        ]

        params = GetScriptedRestApiParams(api_sys_id="api003")
        result = get_scripted_rest_api(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        self.assertEqual(len(result["operations"]), 3)
        second_url = mock_get.call_args_list[1][0][0]
        self.assertIn("sys_ws_operation", second_url)

    @patch("servicenow_mcp.tools.integration_tools.requests.get")
    def test_http_error_returns_failure(self, mock_get):
        resp = MagicMock()
        resp.raise_for_status.side_effect = requests.HTTPError("503 Unavailable")
        mock_get.return_value = resp

        params = GetScriptedRestApiParams(api_name="AnyAPI")
        result = get_scripted_rest_api(self.config, self.auth_manager, params)

        self.assertFalse(result["success"])
        self.assertIn("HTTP error", result["message"])


if __name__ == "__main__":
    unittest.main()
