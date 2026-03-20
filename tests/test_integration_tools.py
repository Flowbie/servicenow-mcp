"""
Tests for integration_tools.py.

Covers outbound REST messages, Scripted REST APIs, Import Sets, and MID Servers.
"""

import unittest
from unittest.mock import MagicMock, call, patch

from servicenow_mcp.auth.auth_manager import AuthManager
import requests

from servicenow_mcp.tools.integration_tools import (
    AddHttpMethodParams,
    AddRestResourceParams,
    CreateRestMessageParams,
    CreateScriptedRestApiParams,
    CreateTransformMapParams,
    GetMidServerStatusParams,
    GetRestMessageParams,
    GetScriptedRestApiParams,
    ListImportSetsParams,
    ListMidServersParams,
    ListRestMessagesParams,
    ListScriptedRestApisParams,
    ListTransformMapsParams,
    RunImportParams,
    RunTransformParams,
    add_http_method,
    add_rest_resource,
    create_rest_message,
    create_scripted_rest_api,
    create_transform_map,
    get_mid_server_status,
    get_rest_message,
    get_scripted_rest_api,
    list_import_sets,
    list_mid_servers,
    list_rest_messages,
    list_scripted_rest_apis,
    list_transform_maps,
    run_import,
    run_transform,
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


class TestListRestMessages(unittest.TestCase):
    """Tests for list_rest_messages."""

    def setUp(self):
        self.config = _make_config()
        self.auth_manager = _make_auth_manager()

    @patch("servicenow_mcp.tools.integration_tools.requests.get")
    def test_success_with_results(self, mock_get):
        mock_get.return_value = _mock_response(
            {"result": [{"sys_id": "abc123", "name": "MyRestMsg"}]}
        )
        params = ListRestMessagesParams()
        result = list_rest_messages(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        self.assertEqual(len(result["items"]), 1)
        self.assertEqual(result["items"][0]["name"], "MyRestMsg")

    @patch("servicenow_mcp.tools.integration_tools.requests.get")
    def test_empty_results(self, mock_get):
        mock_get.return_value = _mock_response({"result": []})
        params = ListRestMessagesParams()
        result = list_rest_messages(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        self.assertEqual(len(result["items"]), 0)
        self.assertIn("0", result["message"])

    @patch("servicenow_mcp.tools.integration_tools.requests.get")
    def test_name_filter_sets_query(self, mock_get):
        mock_get.return_value = _mock_response({"result": []})
        params = ListRestMessagesParams(name_filter="Slack")
        list_rest_messages(self.config, self.auth_manager, params)

        _, kwargs = mock_get.call_args
        self.assertIn("nameLIKESlack", kwargs["params"]["sysparm_query"])

    @patch("servicenow_mcp.tools.integration_tools.requests.get")
    def test_http_error_returns_failure(self, mock_get):
        import requests as req

        resp = MagicMock()
        resp.raise_for_status.side_effect = req.HTTPError("404 Not Found")
        mock_get.return_value = resp

        params = ListRestMessagesParams()
        result = list_rest_messages(self.config, self.auth_manager, params)

        self.assertFalse(result["success"])
        self.assertIn("HTTP error", result["message"])


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


class TestCreateRestMessage(unittest.TestCase):
    """Tests for create_rest_message."""

    def setUp(self):
        self.config = _make_config()
        self.auth_manager = _make_auth_manager()

    @patch("servicenow_mcp.tools.integration_tools.requests.post")
    def test_success(self, mock_post):
        created = {"sys_id": "new001", "name": "NewMsg", "endpoint": "https://api.example.com"}
        mock_post.return_value = _mock_response({"result": created})

        params = CreateRestMessageParams(name="NewMsg", endpoint="https://api.example.com")
        result = create_rest_message(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        self.assertIn("NewMsg", result["message"])
        self.assertEqual(result["item"]["sys_id"], "new001")

    @patch("servicenow_mcp.tools.integration_tools.requests.post")
    def test_http_error(self, mock_post):
        import requests as req

        resp = MagicMock()
        resp.raise_for_status.side_effect = req.HTTPError("400 Bad Request")
        mock_post.return_value = resp

        params = CreateRestMessageParams(name="Bad", endpoint="https://x.com")
        result = create_rest_message(self.config, self.auth_manager, params)

        self.assertFalse(result["success"])
        self.assertIn("HTTP error", result["message"])


class TestAddHttpMethod(unittest.TestCase):
    """Tests for add_http_method."""

    def setUp(self):
        self.config = _make_config()
        self.auth_manager = _make_auth_manager()

    @patch("servicenow_mcp.tools.integration_tools.requests.post")
    def test_success(self, mock_post):
        created = {"sys_id": "fn002", "function_name": "postData", "http_method": "post"}
        mock_post.return_value = _mock_response({"result": created})

        params = AddHttpMethodParams(
            rest_message_sys_id="msg001",
            function_name="postData",
            http_method="POST",
        )
        result = add_http_method(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        self.assertIn("postData", result["message"])
        # Verify http_method is lowercased in payload
        _, kwargs = mock_post.call_args
        self.assertEqual(kwargs["json"]["http_method"], "post")


class TestListScriptedRestApis(unittest.TestCase):
    """Tests for list_scripted_rest_apis."""

    def setUp(self):
        self.config = _make_config()
        self.auth_manager = _make_auth_manager()

    @patch("servicenow_mcp.tools.integration_tools.requests.get")
    def test_success(self, mock_get):
        mock_get.return_value = _mock_response(
            {"result": [{"sys_id": "api001", "name": "MyAPI", "active": "true"}]}
        )
        params = ListScriptedRestApisParams(active=True)
        result = list_scripted_rest_apis(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        self.assertEqual(len(result["items"]), 1)

    @patch("servicenow_mcp.tools.integration_tools.requests.get")
    def test_active_filter_in_query(self, mock_get):
        mock_get.return_value = _mock_response({"result": []})
        params = ListScriptedRestApisParams(active=False)
        list_scripted_rest_apis(self.config, self.auth_manager, params)

        _, kwargs = mock_get.call_args
        self.assertIn("active=false", kwargs["params"]["sysparm_query"])


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


class TestCreateScriptedRestApi(unittest.TestCase):
    """Tests for create_scripted_rest_api."""

    def setUp(self):
        self.config = _make_config()
        self.auth_manager = _make_auth_manager()

    @patch("servicenow_mcp.tools.integration_tools.requests.post")
    def test_success(self, mock_post):
        created = {"sys_id": "api002", "name": "OrdersAPI", "base_api_path": "orders"}
        mock_post.return_value = _mock_response({"result": created})

        params = CreateScriptedRestApiParams(name="OrdersAPI", base_api_path="orders")
        result = create_scripted_rest_api(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        self.assertIn("OrdersAPI", result["message"])
        self.assertEqual(result["item"]["sys_id"], "api002")


class TestAddRestResource(unittest.TestCase):
    """Tests for add_rest_resource."""

    def setUp(self):
        self.config = _make_config()
        self.auth_manager = _make_auth_manager()

    @patch("servicenow_mcp.tools.integration_tools.requests.post")
    def test_success(self, mock_post):
        created = {"sys_id": "op002", "name": "createOrder", "http_method": "POST"}
        mock_post.return_value = _mock_response({"result": created})

        params = AddRestResourceParams(
            api_sys_id="api002",
            name="createOrder",
            http_method="post",
            relative_path="/orders",
        )
        result = add_rest_resource(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        self.assertIn("createOrder", result["message"])
        # Verify http_method is uppercased in payload
        _, kwargs = mock_post.call_args
        self.assertEqual(kwargs["json"]["http_method"], "POST")


class TestListImportSets(unittest.TestCase):
    """Tests for list_import_sets."""

    def setUp(self):
        self.config = _make_config()
        self.auth_manager = _make_auth_manager()

    @patch("servicenow_mcp.tools.integration_tools.requests.get")
    def test_success(self, mock_get):
        mock_get.return_value = _mock_response(
            {"result": [{"sys_id": "is001", "label": "Employee Import", "state": "complete"}]}
        )
        params = ListImportSetsParams()
        result = list_import_sets(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        self.assertEqual(len(result["items"]), 1)

    @patch("servicenow_mcp.tools.integration_tools.requests.get")
    def test_state_filter_applied(self, mock_get):
        mock_get.return_value = _mock_response({"result": []})
        params = ListImportSetsParams(state_filter="loaded")
        list_import_sets(self.config, self.auth_manager, params)

        _, kwargs = mock_get.call_args
        self.assertEqual(kwargs["params"]["sysparm_query"], "state=loaded")


class TestListMidServers(unittest.TestCase):
    """Tests for list_mid_servers."""

    def setUp(self):
        self.config = _make_config()
        self.auth_manager = _make_auth_manager()

    @patch("servicenow_mcp.tools.integration_tools.requests.get")
    def test_success(self, mock_get):
        mock_get.return_value = _mock_response(
            {
                "result": [
                    {
                        "sys_id": "mid001",
                        "name": "MID-PROD-01",
                        "status": "Up",
                        "validated": "true",
                        "version": "8.4.0",
                        "host_name": "mid-prod-01.example.com",
                        "ip_address": "10.0.0.10",
                        "last_refreshed": "2026-03-01 12:00:00",
                    }
                ]
            }
        )
        params = ListMidServersParams()
        result = list_mid_servers(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        self.assertEqual(len(result["items"]), 1)
        self.assertEqual(result["items"][0]["name"], "MID-PROD-01")

    @patch("servicenow_mcp.tools.integration_tools.requests.get")
    def test_status_filter_applied(self, mock_get):
        mock_get.return_value = _mock_response({"result": []})
        params = ListMidServersParams(status_filter="Up")
        list_mid_servers(self.config, self.auth_manager, params)

        _, kwargs = mock_get.call_args
        self.assertEqual(kwargs["params"]["sysparm_query"], "status=Up")
        self.assertIn(
            "sys_id,name,status", kwargs["params"]["sysparm_fields"]
        )


class TestGetMidServerStatus(unittest.TestCase):
    """Tests for get_mid_server_status."""

    def setUp(self):
        self.config = _make_config()
        self.auth_manager = _make_auth_manager()

    @patch("servicenow_mcp.tools.integration_tools.requests.get")
    def test_success_by_name(self, mock_get):
        server = {
            "sys_id": "mid001",
            "name": "MID-PROD-01",
            "status": "Up",
            "validated": "true",
            "up": "true",
            "error_message": "",
        }
        mock_get.return_value = _mock_response({"result": [server]})

        params = GetMidServerStatusParams(server_name="MID-PROD-01")
        result = get_mid_server_status(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        self.assertEqual(result["server"]["name"], "MID-PROD-01")
        _, kwargs = mock_get.call_args
        self.assertIn(
            "error_message", kwargs["params"]["sysparm_fields"]
        )

    @patch("servicenow_mcp.tools.integration_tools.requests.get")
    def test_not_found(self, mock_get):
        mock_get.return_value = _mock_response({"result": []})

        params = GetMidServerStatusParams(server_sys_id="nonexistent")
        result = get_mid_server_status(self.config, self.auth_manager, params)

        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    def test_validator_requires_at_least_one(self):
        from pydantic import ValidationError

        with self.assertRaises(ValidationError):
            GetMidServerStatusParams()

    @patch("servicenow_mcp.tools.integration_tools.requests.get")
    def test_http_error_returns_failure(self, mock_get):
        import requests as req

        resp = MagicMock()
        resp.raise_for_status.side_effect = req.HTTPError("503 Service Unavailable")
        mock_get.return_value = resp

        params = GetMidServerStatusParams(server_name="MID-DOWN")
        result = get_mid_server_status(self.config, self.auth_manager, params)

        self.assertFalse(result["success"])
        self.assertIn("HTTP error", result["message"])


class TestListTransformMaps(unittest.TestCase):
    def setUp(self):
        auth_config = AuthConfig(
            type=AuthType.BASIC,
            basic=BasicAuthConfig(username="test_user", password="test_password"),
        )
        self.config = ServerConfig(instance_url="https://test.service-now.com", auth=auth_config)
        self.auth_manager = MagicMock(spec=AuthManager)
        self.auth_manager.get_headers.return_value = {"Authorization": "Bearer FAKE_TOKEN"}

    @patch("servicenow_mcp.tools.integration_tools.requests.get")
    def test_list_transform_maps_success(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": [
                {"sys_id": "tm1", "name": "User Import Map", "source_table": "u_user_staging",
                 "target_table": "sys_user", "active": "true"},
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        params = ListTransformMapsParams()
        result = list_transform_maps(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["transform_maps"][0]["name"], "User Import Map")

    @patch("servicenow_mcp.tools.integration_tools.requests.get")
    def test_list_transform_maps_with_filter(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": []}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        params = ListTransformMapsParams(source_table_filter="u_staging")
        result = list_transform_maps(self.config, self.auth_manager, params)

        call_args = mock_get.call_args
        self.assertIn("sysparm_query", call_args[1]["params"])

    @patch("servicenow_mcp.tools.integration_tools.requests.get")
    def test_list_transform_maps_http_error(self, mock_get):
        mock_get.side_effect = requests.HTTPError("Connection refused")
        params = ListTransformMapsParams()
        result = list_transform_maps(self.config, self.auth_manager, params)
        self.assertFalse(result["success"])
        self.assertIn("message", result)


class TestCreateTransformMap(unittest.TestCase):
    def setUp(self):
        auth_config = AuthConfig(
            type=AuthType.BASIC,
            basic=BasicAuthConfig(username="test_user", password="test_password"),
        )
        self.config = ServerConfig(instance_url="https://test.service-now.com", auth=auth_config)
        self.auth_manager = MagicMock(spec=AuthManager)
        self.auth_manager.get_headers.return_value = {"Authorization": "Bearer FAKE_TOKEN"}

    @patch("servicenow_mcp.tools.integration_tools.requests.post")
    def test_create_transform_map_success(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": {"sys_id": "tm_new", "name": "New Import Map", "active": "true"}
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        params = CreateTransformMapParams(
            name="New Import Map",
            source_table="u_staging_table",
            target_table="incident",
        )
        result = create_transform_map(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        self.assertEqual(result["transform_map"]["sys_id"], "tm_new")

    @patch("servicenow_mcp.tools.integration_tools.requests.post")
    def test_create_transform_map_http_error(self, mock_post):
        mock_post.side_effect = requests.HTTPError("Connection refused")
        params = CreateTransformMapParams(name="Fail Map", source_table="u_src", target_table="incident")
        result = create_transform_map(self.config, self.auth_manager, params)
        self.assertFalse(result["success"])
        self.assertIn("message", result)


class TestRunTransform(unittest.TestCase):
    def setUp(self):
        auth_config = AuthConfig(
            type=AuthType.BASIC,
            basic=BasicAuthConfig(username="test_user", password="test_password"),
        )
        self.config = ServerConfig(instance_url="https://test.service-now.com", auth=auth_config)
        self.auth_manager = MagicMock(spec=AuthManager)
        self.auth_manager.get_headers.return_value = {"Authorization": "Bearer FAKE_TOKEN"}

    @patch("servicenow_mcp.tools.integration_tools.requests.patch")
    def test_run_transform_success(self, mock_patch):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": {"sys_id": "is1", "state": "complete"}
        }
        mock_response.raise_for_status = MagicMock()
        mock_patch.return_value = mock_response

        params = RunTransformParams(import_set_sys_id="is1", transform_map_sys_id="tm1")
        result = run_transform(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])

    @patch("servicenow_mcp.tools.integration_tools.requests.patch")
    def test_run_transform_http_error(self, mock_patch):
        mock_patch.side_effect = requests.HTTPError("Timeout")
        params = RunTransformParams(import_set_sys_id="is1")
        result = run_transform(self.config, self.auth_manager, params)
        self.assertFalse(result["success"])
        self.assertIn("message", result)


class TestRunImport(unittest.TestCase):
    def setUp(self):
        auth_config = AuthConfig(
            type=AuthType.BASIC,
            basic=BasicAuthConfig(username="test_user", password="test_password"),
        )
        self.config = ServerConfig(instance_url="https://test.service-now.com", auth=auth_config)
        self.auth_manager = MagicMock(spec=AuthManager)
        self.auth_manager.get_headers.return_value = {"Authorization": "Bearer FAKE_TOKEN"}

    @patch("servicenow_mcp.tools.integration_tools.requests.post")
    def test_run_import_success(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": [{"display_name": "number", "display_value": "IMP0010001",
                        "status": "inserted", "sys_id": "is1", "table": "incident",
                        "transform_map": "User Import Map", "error": None}]
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        params = RunImportParams(staging_table="u_user_staging", payload={"u_name": "Test User"})
        result = run_import(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        self.assertEqual(result["results"][0]["status"], "inserted")

    @patch("servicenow_mcp.tools.integration_tools.requests.post")
    def test_run_import_dict_result_wrapped_in_list(self, mock_post):
        """Test that a single dict result is normalized to a list."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": {"status": "inserted", "sys_id": "is2"}
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        params = RunImportParams(staging_table="u_staging", payload={"field": "val"})
        result = run_import(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        self.assertIsInstance(result["results"], list)

    @patch("servicenow_mcp.tools.integration_tools.requests.post")
    def test_run_import_http_error(self, mock_post):
        mock_post.side_effect = requests.HTTPError("Timeout")
        params = RunImportParams(staging_table="u_staging", payload={"field": "val"})
        result = run_import(self.config, self.auth_manager, params)
        self.assertFalse(result["success"])
        self.assertIn("message", result)


if __name__ == "__main__":
    unittest.main()
