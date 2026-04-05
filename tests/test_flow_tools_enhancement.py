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


class TestListActionTypeInputs(unittest.TestCase):

    @patch("servicenow_mcp.tools.flow_tools.requests.get")
    def test_returns_inputs_for_valid_action_type(self, mock_get):
        from servicenow_mcp.tools.flow_tools import ListActionTypeInputsParams, list_action_type_inputs
        mock_get.return_value.raise_for_status = MagicMock()
        mock_get.return_value.json.return_value = {
            "result": [
                {"sys_id": "abc123", "element": "table", "label": "Table", "type": "table_name", "mandatory": "true", "default_value": "", "order": "100"},
                {"sys_id": "def456", "element": "conditions", "label": "Conditions", "type": "conditions", "mandatory": "false", "default_value": "", "order": "200"},
            ]
        }
        params = ListActionTypeInputsParams(action_type_sys_id="lookup_record_sys_id")
        result = list_action_type_inputs(_make_config(), _make_auth(), params)
        self.assertEqual(len(result.inputs), 2)
        self.assertEqual(result.inputs[0].sys_id, "abc123")
        self.assertEqual(result.inputs[0].name, "table")
        self.assertTrue(result.inputs[0].mandatory)

    @patch("servicenow_mcp.tools.flow_tools.requests.get")
    def test_queries_correct_table_and_filters_by_action_type(self, mock_get):
        from servicenow_mcp.tools.flow_tools import ListActionTypeInputsParams, list_action_type_inputs
        mock_get.return_value.raise_for_status = MagicMock()
        mock_get.return_value.json.return_value = {"result": []}
        params = ListActionTypeInputsParams(action_type_sys_id="ATID")
        list_action_type_inputs(_make_config(), _make_auth(), params)
        call_params = mock_get.call_args[1]["params"]
        # Query field must be `model=` — NOT `action_type=` (does not exist on sys_hub_action_input)
        self.assertIn("model=ATID", call_params["sysparm_query"])
        self.assertIn("element", call_params["sysparm_fields"])

    @patch("servicenow_mcp.tools.flow_tools.requests.get")
    def test_http_error_returns_empty_with_message(self, mock_get):
        from servicenow_mcp.tools.flow_tools import ListActionTypeInputsParams, list_action_type_inputs
        mock_get.return_value.raise_for_status.side_effect = requests.HTTPError("500")
        mock_get.return_value.text = "Server Error"
        params = ListActionTypeInputsParams(action_type_sys_id="X")
        result = list_action_type_inputs(_make_config(), _make_auth(), params)
        self.assertEqual(result.inputs, [])
        self.assertIn("Failed", result.message)

    @patch("servicenow_mcp.tools.flow_tools.requests.get")
    def test_empty_result_returns_empty_list(self, mock_get):
        from servicenow_mcp.tools.flow_tools import ListActionTypeInputsParams, list_action_type_inputs
        mock_get.return_value.raise_for_status = MagicMock()
        mock_get.return_value.json.return_value = {"result": []}
        params = ListActionTypeInputsParams(action_type_sys_id="unknown")
        result = list_action_type_inputs(_make_config(), _make_auth(), params)
        self.assertEqual(result.inputs, [])
        self.assertIn("0", result.message)

    @patch("servicenow_mcp.tools.flow_tools.requests.get")
    def test_mandatory_field_coercion_string_true(self, mock_get):
        from servicenow_mcp.tools.flow_tools import ListActionTypeInputsParams, list_action_type_inputs
        mock_get.return_value.raise_for_status = MagicMock()
        mock_get.return_value.json.return_value = {
            "result": [{"sys_id": "x", "element": "n", "label": "L", "type": "string", "mandatory": "true", "default_value": "", "order": "1"}]
        }
        result = list_action_type_inputs(_make_config(), _make_auth(), ListActionTypeInputsParams(action_type_sys_id="X"))
        self.assertTrue(result.inputs[0].mandatory)

    @patch("servicenow_mcp.tools.flow_tools.requests.get")
    def test_mandatory_field_coercion_string_false(self, mock_get):
        from servicenow_mcp.tools.flow_tools import ListActionTypeInputsParams, list_action_type_inputs
        mock_get.return_value.raise_for_status = MagicMock()
        mock_get.return_value.json.return_value = {
            "result": [{"sys_id": "x", "element": "n", "label": "L", "type": "string", "mandatory": "false", "default_value": "", "order": "1"}]
        }
        result = list_action_type_inputs(_make_config(), _make_auth(), ListActionTypeInputsParams(action_type_sys_id="X"))
        self.assertFalse(result.inputs[0].mandatory)


class TestListFlowLogicTypes(unittest.TestCase):

    @patch("servicenow_mcp.tools.flow_tools.requests.get")
    def test_returns_logic_types(self, mock_get):
        from servicenow_mcp.tools.flow_tools import ListFlowLogicTypesParams, list_flow_logic_types
        mock_get.return_value.raise_for_status = MagicMock()
        mock_get.return_value.json.return_value = {
            "result": [
                {"sys_id": "if_id", "name": "If", "type": "if"},
                {"sys_id": "switch_id", "name": "Switch", "type": "switch"},
                {"sys_id": "for_each_id", "name": "For Each", "type": "for_each"},
            ]
        }
        result = list_flow_logic_types(_make_config(), _make_auth(), ListFlowLogicTypesParams())
        self.assertEqual(len(result.logic_types), 3)
        self.assertEqual(result.logic_types[0].sys_id, "if_id")
        self.assertEqual(result.logic_types[0].name, "If")

    @patch("servicenow_mcp.tools.flow_tools.requests.get")
    def test_calls_processflow_flow_logic_types_endpoint(self, mock_get):
        from servicenow_mcp.tools.flow_tools import ListFlowLogicTypesParams, list_flow_logic_types
        mock_get.return_value.raise_for_status = MagicMock()
        mock_get.return_value.json.return_value = {"result": []}
        list_flow_logic_types(_make_config(), _make_auth(), ListFlowLogicTypesParams())
        url = mock_get.call_args[0][0]
        self.assertIn("flow_logic/types", url)

    @patch("servicenow_mcp.tools.flow_tools.requests.get")
    def test_http_error_returns_empty(self, mock_get):
        from servicenow_mcp.tools.flow_tools import ListFlowLogicTypesParams, list_flow_logic_types
        mock_get.return_value.raise_for_status.side_effect = requests.HTTPError("403")
        mock_get.return_value.text = "Forbidden"
        result = list_flow_logic_types(_make_config(), _make_auth(), ListFlowLogicTypesParams())
        self.assertEqual(result.logic_types, [])
        self.assertIn("Failed", result.message)

    @patch("servicenow_mcp.tools.flow_tools.requests.get")
    def test_result_list_at_top_level(self, mock_get):
        """Handles response where result is a list at top level (no 'result' key)."""
        from servicenow_mcp.tools.flow_tools import ListFlowLogicTypesParams, list_flow_logic_types
        mock_get.return_value.raise_for_status = MagicMock()
        mock_get.return_value.json.return_value = [
            {"sys_id": "if_id", "name": "If", "type": "if"},
        ]
        result = list_flow_logic_types(_make_config(), _make_auth(), ListFlowLogicTypesParams())
        self.assertEqual(len(result.logic_types), 1)


class TestAddStepsToFlow(unittest.TestCase):

    def _mock_get_flow_response(self, flow_sys_id="flow123"):
        m = MagicMock()
        m.raise_for_status = MagicMock()
        m.json.return_value = {
            "result": {
                "data": {
                    "id": flow_sys_id,
                    "name": "Test Flow",
                    "actionInstances": [],
                    "triggerInstances": [],
                }
            }
        }
        return m

    @patch("servicenow_mcp.tools.flow_tools.requests.post")
    @patch("servicenow_mcp.tools.flow_tools.requests.put")
    @patch("servicenow_mcp.tools.flow_tools.requests.get")
    def test_success_adds_steps_and_returns_count(self, mock_get, mock_put, mock_post):
        from servicenow_mcp.tools.flow_tools import (
            ActionInputParam, ActionInstanceParam, AddStepsToFlowParams, add_steps_to_flow
        )
        mock_get.return_value = self._mock_get_flow_response()
        mock_put.return_value.raise_for_status = MagicMock()
        mock_put.return_value.json.return_value = {"result": {"data": {"id": "flow123"}}}
        mock_post.return_value.raise_for_status = MagicMock()

        params = AddStepsToFlowParams(
            flow_sys_id="flow123",
            actions=[
                ActionInstanceParam(
                    action_type_sys_id="delete_record_sys_id",
                    name="Delete Record",
                    order=1,
                )
            ],
        )
        result = add_steps_to_flow(_make_config(), _make_auth(), params)
        self.assertTrue(result.success)
        self.assertEqual(result.steps_added, 1)
        self.assertEqual(result.flow_sys_id, "flow123")

    @patch("servicenow_mcp.tools.flow_tools.requests.get")
    def test_get_failure_returns_error(self, mock_get):
        from servicenow_mcp.tools.flow_tools import AddStepsToFlowParams, add_steps_to_flow
        mock_get.return_value.raise_for_status.side_effect = requests.HTTPError("404")
        mock_get.return_value.text = "Not Found"
        params = AddStepsToFlowParams(flow_sys_id="bad_id", actions=[])
        result = add_steps_to_flow(_make_config(), _make_auth(), params)
        self.assertFalse(result.success)
        self.assertIn("Failed to fetch flow", result.message)

    @patch("servicenow_mcp.tools.flow_tools.requests.post")
    @patch("servicenow_mcp.tools.flow_tools.requests.put")
    @patch("servicenow_mcp.tools.flow_tools.requests.get")
    def test_put_failure_returns_error(self, mock_get, mock_put, mock_post):
        from servicenow_mcp.tools.flow_tools import AddStepsToFlowParams, add_steps_to_flow
        mock_get.return_value = self._mock_get_flow_response()
        mock_put.return_value.raise_for_status.side_effect = requests.HTTPError("500")
        mock_put.return_value.text = "Server Error"
        params = AddStepsToFlowParams(flow_sys_id="flow123", actions=[])
        result = add_steps_to_flow(_make_config(), _make_auth(), params)
        self.assertFalse(result.success)
        self.assertIn("Failed to update flow", result.message)

    @patch("servicenow_mcp.tools.flow_tools.requests.post")
    @patch("servicenow_mcp.tools.flow_tools.requests.put")
    @patch("servicenow_mcp.tools.flow_tools.requests.get")
    def test_existing_action_instances_preserved(self, mock_get, mock_put, mock_post):
        """Existing action instances are not clobbered."""
        from servicenow_mcp.tools.flow_tools import ActionInstanceParam, AddStepsToFlowParams, add_steps_to_flow
        existing_instance = {"id": "existing_action", "order": 1}
        mock_get.return_value.raise_for_status = MagicMock()
        mock_get.return_value.json.return_value = {
            "result": {"data": {"id": "flow123", "actionInstances": [existing_instance], "triggerInstances": []}}
        }
        mock_put.return_value.raise_for_status = MagicMock()
        mock_put.return_value.json.return_value = {"result": {"data": {"id": "flow123"}}}
        mock_post.return_value.raise_for_status = MagicMock()

        params = AddStepsToFlowParams(
            flow_sys_id="flow123",
            actions=[ActionInstanceParam(action_type_sys_id="x", name="New Step", order=2)],
        )
        add_steps_to_flow(_make_config(), _make_auth(), params)

        put_body = mock_put.call_args[1]["json"]
        self.assertEqual(len(put_body["actionInstances"]), 2)
        self.assertEqual(put_body["actionInstances"][0], existing_instance)

    @patch("servicenow_mcp.tools.flow_tools.requests.post")
    @patch("servicenow_mcp.tools.flow_tools.requests.put")
    @patch("servicenow_mcp.tools.flow_tools.requests.get")
    def test_version_created_after_put(self, mock_get, mock_put, mock_post):
        from servicenow_mcp.tools.flow_tools import AddStepsToFlowParams, add_steps_to_flow
        mock_get.return_value = self._mock_get_flow_response()
        mock_put.return_value.raise_for_status = MagicMock()
        mock_put.return_value.json.return_value = {"result": {"data": {"id": "flow123"}}}
        mock_post.return_value.raise_for_status = MagicMock()
        add_steps_to_flow(_make_config(), _make_auth(), AddStepsToFlowParams(flow_sys_id="flow123", actions=[]))
        post_url = mock_post.call_args[0][0]
        self.assertIn("create_version", post_url)

    @patch("servicenow_mcp.tools.flow_tools.requests.post")
    @patch("servicenow_mcp.tools.flow_tools.requests.put")
    @patch("servicenow_mcp.tools.flow_tools.requests.get")
    def test_version_failure_is_non_fatal(self, mock_get, mock_put, mock_post):
        from servicenow_mcp.tools.flow_tools import AddStepsToFlowParams, add_steps_to_flow
        mock_get.return_value = self._mock_get_flow_response()
        mock_put.return_value.raise_for_status = MagicMock()
        mock_put.return_value.json.return_value = {"result": {"data": {"id": "flow123"}}}
        mock_post.return_value.raise_for_status.side_effect = requests.HTTPError("500")
        result = add_steps_to_flow(_make_config(), _make_auth(), AddStepsToFlowParams(flow_sys_id="flow123", actions=[]))
        self.assertTrue(result.success)


class TestDeleteArtifacts(unittest.TestCase):

    @patch("servicenow_mcp.tools.flow_tools.requests.delete")
    def test_delete_flow_success(self, mock_del):
        from servicenow_mcp.tools.flow_tools import DeleteFlowParams, delete_flow
        mock_del.return_value.raise_for_status = MagicMock()
        result = delete_flow(_make_config(), _make_auth(), DeleteFlowParams(sys_id="flow123"))
        self.assertTrue(result.success)
        self.assertEqual(result.sys_id, "flow123")

    @patch("servicenow_mcp.tools.flow_tools.requests.delete")
    def test_delete_flow_calls_sys_hub_flow_table(self, mock_del):
        from servicenow_mcp.tools.flow_tools import DeleteFlowParams, delete_flow
        mock_del.return_value.raise_for_status = MagicMock()
        delete_flow(_make_config(), _make_auth(), DeleteFlowParams(sys_id="FLOW_ID"))
        url = mock_del.call_args[0][0]
        self.assertIn("sys_hub_flow/FLOW_ID", url)

    @patch("servicenow_mcp.tools.flow_tools.requests.delete")
    def test_delete_flow_http_error_returns_failure(self, mock_del):
        from servicenow_mcp.tools.flow_tools import DeleteFlowParams, delete_flow
        mock_del.return_value.raise_for_status.side_effect = requests.HTTPError("403")
        mock_del.return_value.text = "Forbidden"
        result = delete_flow(_make_config(), _make_auth(), DeleteFlowParams(sys_id="X"))
        self.assertFalse(result.success)
        self.assertIn("Failed", result.message)

    @patch("servicenow_mcp.tools.flow_tools.requests.delete")
    def test_delete_action_calls_action_type_definition_table(self, mock_del):
        from servicenow_mcp.tools.flow_tools import DeleteActionParams, delete_action
        mock_del.return_value.raise_for_status = MagicMock()
        delete_action(_make_config(), _make_auth(), DeleteActionParams(sys_id="ACT_ID"))
        url = mock_del.call_args[0][0]
        self.assertIn("sys_hub_action_type_definition/ACT_ID", url)

    @patch("servicenow_mcp.tools.flow_tools.requests.delete")
    def test_delete_subflow_calls_sys_hub_flow_table(self, mock_del):
        from servicenow_mcp.tools.flow_tools import DeleteSubflowParams, delete_subflow
        mock_del.return_value.raise_for_status = MagicMock()
        delete_subflow(_make_config(), _make_auth(), DeleteSubflowParams(sys_id="SUB_ID"))
        url = mock_del.call_args[0][0]
        self.assertIn("sys_hub_flow/SUB_ID", url)


class TestGetFlowExecutionHistory(unittest.TestCase):

    @patch("servicenow_mcp.tools.flow_tools.requests.get")
    def test_returns_executions(self, mock_get):
        from servicenow_mcp.tools.flow_tools import GetFlowExecutionHistoryParams, get_flow_execution_history
        mock_get.return_value.raise_for_status = MagicMock()
        mock_get.return_value.json.return_value = {
            "result": [
                {"sys_id": "exec1", "name": "Run 1", "state": "complete", "started": "2026-04-01 10:00:00", "ended": "2026-04-01 10:00:05", "error": ""},
                {"sys_id": "exec2", "name": "Run 2", "state": "error", "started": "2026-04-01 11:00:00", "ended": "", "error": "Timeout"},
            ]
        }
        params = GetFlowExecutionHistoryParams(flow_sys_id="flow123")
        result = get_flow_execution_history(_make_config(), _make_auth(), params)
        self.assertEqual(result.count, 2)
        self.assertEqual(result.executions[0].sys_id, "exec1")
        self.assertEqual(result.executions[1].error, "Timeout")

    @patch("servicenow_mcp.tools.flow_tools.requests.get")
    def test_queries_sys_hub_flow_context(self, mock_get):
        from servicenow_mcp.tools.flow_tools import GetFlowExecutionHistoryParams, get_flow_execution_history
        mock_get.return_value.raise_for_status = MagicMock()
        mock_get.return_value.json.return_value = {"result": []}
        get_flow_execution_history(_make_config(), _make_auth(), GetFlowExecutionHistoryParams(flow_sys_id="FQID"))
        url = mock_get.call_args[0][0]
        self.assertIn("sys_hub_flow_context", url)

    @patch("servicenow_mcp.tools.flow_tools.requests.get")
    def test_flow_sys_id_in_query(self, mock_get):
        from servicenow_mcp.tools.flow_tools import GetFlowExecutionHistoryParams, get_flow_execution_history
        mock_get.return_value.raise_for_status = MagicMock()
        mock_get.return_value.json.return_value = {"result": []}
        get_flow_execution_history(_make_config(), _make_auth(), GetFlowExecutionHistoryParams(flow_sys_id="FQID"))
        query = mock_get.call_args[1]["params"]["sysparm_query"]
        self.assertIn("FQID", query)

    @patch("servicenow_mcp.tools.flow_tools.requests.get")
    def test_state_filter_applied(self, mock_get):
        from servicenow_mcp.tools.flow_tools import GetFlowExecutionHistoryParams, get_flow_execution_history
        mock_get.return_value.raise_for_status = MagicMock()
        mock_get.return_value.json.return_value = {"result": []}
        get_flow_execution_history(_make_config(), _make_auth(), GetFlowExecutionHistoryParams(flow_sys_id="X", state="error"))
        query = mock_get.call_args[1]["params"]["sysparm_query"]
        self.assertIn("error", query)

    @patch("servicenow_mcp.tools.flow_tools.requests.get")
    def test_http_error_returns_empty(self, mock_get):
        from servicenow_mcp.tools.flow_tools import GetFlowExecutionHistoryParams, get_flow_execution_history
        mock_get.return_value.raise_for_status.side_effect = requests.HTTPError("500")
        mock_get.return_value.text = "Error"
        result = get_flow_execution_history(_make_config(), _make_auth(), GetFlowExecutionHistoryParams(flow_sys_id="X"))
        self.assertEqual(result.count, 0)
        self.assertIn("Failed", result.message)

    @patch("servicenow_mcp.tools.flow_tools.requests.get")
    def test_respects_limit(self, mock_get):
        from servicenow_mcp.tools.flow_tools import GetFlowExecutionHistoryParams, get_flow_execution_history
        mock_get.return_value.raise_for_status = MagicMock()
        mock_get.return_value.json.return_value = {"result": []}
        get_flow_execution_history(_make_config(), _make_auth(), GetFlowExecutionHistoryParams(flow_sys_id="X", limit=5))
        self.assertEqual(mock_get.call_args[1]["params"]["sysparm_limit"], 5)
