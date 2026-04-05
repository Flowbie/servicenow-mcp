"""Tests for flow_tools phase 2 additions."""
import json
from unittest.mock import MagicMock, patch
import pytest
from servicenow_mcp.tools.flow_tools import (
    RemoveStepsFromFlowParams,
    remove_steps_from_flow,
)
from servicenow_mcp.utils.config import ServerConfig
from servicenow_mcp.auth.auth_manager import AuthManager


@pytest.fixture
def config():
    from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig
    return ServerConfig(
        instance_url="https://test.service-now.com",
        auth=AuthConfig(
            type=AuthType.BASIC,
            basic=BasicAuthConfig(username="u", password="p"),
        ),
        timeout=30,
        script_execution_api_resource_path="/api/1425483/bg_runner/execute",
    )


@pytest.fixture
def auth():
    m = MagicMock(spec=AuthManager)
    m.get_headers.return_value = {"Authorization": "Basic dXNlcjpwYXNz"}
    return m


FLOW_ID = "abc123def456abc123def456abc12345"
STEP_ID_1 = "step111111111111111111111111111a"
STEP_ID_2 = "step222222222222222222222222222b"

MOCK_FLOW_PAYLOAD = {
    "result": {
        "data": {
            "id": FLOW_ID,
            "masterSnapshotId": "snap001",
            "name": "Test Flow",
            "triggerInstances": [],
            "actionInstances": [
                {"id": STEP_ID_1, "order": "1", "deleted": False, "uiUniqueIdentifier": "uid-1"},
                {"id": STEP_ID_2, "order": "2", "deleted": False, "uiUniqueIdentifier": "uid-2"},
            ],
            "flowLogicInstances": [],
            "subFlowInstances": [],
        }
    }
}

MOCK_PUT_RESPONSE = {"result": {"data": {"id": FLOW_ID}}}
MOCK_VERSION_RESPONSE = {"result": {}}


def _make_response(status, body):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = body
    r.raise_for_status = MagicMock()
    return r


def test_remove_steps_success(config, auth):
    """Marks specified action steps as deleted and PUTs back."""
    with patch("servicenow_mcp.tools.flow_tools.requests.get") as mock_get, \
         patch("servicenow_mcp.tools.flow_tools.requests.put") as mock_put, \
         patch("servicenow_mcp.tools.flow_tools.requests.post") as mock_post:
        mock_get.return_value = _make_response(200, MOCK_FLOW_PAYLOAD)
        mock_put.return_value = _make_response(200, MOCK_PUT_RESPONSE)
        mock_post.return_value = _make_response(200, MOCK_VERSION_RESPONSE)

        params = RemoveStepsFromFlowParams(
            flow_sys_id=FLOW_ID,
            step_ids=[STEP_ID_1],
        )
        result = remove_steps_from_flow(config, auth, params)

    assert result.success is True
    assert result.steps_removed == 1
    assert result.flow_sys_id == FLOW_ID

    # Confirm PUT was called with the step marked deleted
    put_body = mock_put.call_args.kwargs.get("json") or mock_put.call_args[1].get("json")
    action_instances = put_body["actionInstances"]
    deleted_step = next(s for s in action_instances if s["id"] == STEP_ID_1)
    assert deleted_step["deleted"] is True
    # Other step untouched
    kept_step = next(s for s in action_instances if s["id"] == STEP_ID_2)
    assert kept_step["deleted"] is False


def test_remove_steps_multiple(config, auth):
    """Can remove multiple steps in a single call."""
    with patch("servicenow_mcp.tools.flow_tools.requests.get") as mock_get, \
         patch("servicenow_mcp.tools.flow_tools.requests.put") as mock_put, \
         patch("servicenow_mcp.tools.flow_tools.requests.post") as mock_post:
        mock_get.return_value = _make_response(200, MOCK_FLOW_PAYLOAD)
        mock_put.return_value = _make_response(200, MOCK_PUT_RESPONSE)
        mock_post.return_value = _make_response(200, MOCK_VERSION_RESPONSE)

        params = RemoveStepsFromFlowParams(
            flow_sys_id=FLOW_ID,
            step_ids=[STEP_ID_1, STEP_ID_2],
        )
        result = remove_steps_from_flow(config, auth, params)

    assert result.success is True
    assert result.steps_removed == 2


def test_remove_steps_not_found(config, auth):
    """Returns success=False when step_id not found in flow."""
    with patch("servicenow_mcp.tools.flow_tools.requests.get") as mock_get:
        mock_get.return_value = _make_response(200, MOCK_FLOW_PAYLOAD)

        params = RemoveStepsFromFlowParams(
            flow_sys_id=FLOW_ID,
            step_ids=["nonexistent_step_id_00000000000000"],
        )
        result = remove_steps_from_flow(config, auth, params)

    assert result.success is False
    assert "not found" in result.message.lower()


def test_remove_steps_get_failure(config, auth):
    """Returns success=False when GET fails."""
    import requests as req_lib
    with patch("servicenow_mcp.tools.flow_tools.requests.get") as mock_get:
        mock_get.side_effect = req_lib.RequestException("connection error")

        params = RemoveStepsFromFlowParams(flow_sys_id=FLOW_ID, step_ids=[STEP_ID_1])
        result = remove_steps_from_flow(config, auth, params)

    assert result.success is False
    assert "connection error" in result.message


def test_remove_steps_put_failure(config, auth):
    """Returns success=False when PUT fails."""
    import requests as req_lib
    error_response = MagicMock()
    error_response.text = "internal error"
    with patch("servicenow_mcp.tools.flow_tools.requests.get") as mock_get, \
         patch("servicenow_mcp.tools.flow_tools.requests.put") as mock_put:
        mock_get.return_value = _make_response(200, MOCK_FLOW_PAYLOAD)
        mock_put.side_effect = req_lib.HTTPError(response=error_response)

        params = RemoveStepsFromFlowParams(flow_sys_id=FLOW_ID, step_ids=[STEP_ID_1])
        result = remove_steps_from_flow(config, auth, params)

    assert result.success is False


def test_remove_logic_step(config, auth):
    """Can remove flowLogicInstances by id."""
    logic_id = "logic111111111111111111111111111"
    payload_with_logic = {
        "result": {
            "data": {
                "id": FLOW_ID,
                "masterSnapshotId": "snap001",
                "name": "Test Flow",
                "triggerInstances": [],
                "actionInstances": [],
                "flowLogicInstances": [
                    {"id": logic_id, "order": "1", "deleted": False, "uiUniqueIdentifier": "uid-logic-1", "type": "flowlogic"},
                ],
                "subFlowInstances": [],
            }
        }
    }
    with patch("servicenow_mcp.tools.flow_tools.requests.get") as mock_get, \
         patch("servicenow_mcp.tools.flow_tools.requests.put") as mock_put, \
         patch("servicenow_mcp.tools.flow_tools.requests.post") as mock_post:
        mock_get.return_value = _make_response(200, payload_with_logic)
        mock_put.return_value = _make_response(200, MOCK_PUT_RESPONSE)
        mock_post.return_value = _make_response(200, MOCK_VERSION_RESPONSE)

        params = RemoveStepsFromFlowParams(flow_sys_id=FLOW_ID, step_ids=[logic_id])
        result = remove_steps_from_flow(config, auth, params)

    assert result.success is True
    assert result.steps_removed == 1
    put_body = mock_put.call_args.kwargs.get("json") or mock_put.call_args[1].get("json")
    deleted = next(s for s in put_body["flowLogicInstances"] if s["id"] == logic_id)
    assert deleted["deleted"] is True


def test_remove_steps_creates_version(config, auth):
    """Calls create_version after PUT to save the change."""
    with patch("servicenow_mcp.tools.flow_tools.requests.get") as mock_get, \
         patch("servicenow_mcp.tools.flow_tools.requests.put") as mock_put, \
         patch("servicenow_mcp.tools.flow_tools.requests.post") as mock_post:
        mock_get.return_value = _make_response(200, MOCK_FLOW_PAYLOAD)
        mock_put.return_value = _make_response(200, MOCK_PUT_RESPONSE)
        mock_post.return_value = _make_response(200, MOCK_VERSION_RESPONSE)

        params = RemoveStepsFromFlowParams(flow_sys_id=FLOW_ID, step_ids=[STEP_ID_1])
        remove_steps_from_flow(config, auth, params)

    # POST to versioning endpoint must have been called
    post_url = mock_post.call_args.args[0]
    assert "create_version" in post_url


def test_remove_steps_empty_list(config, auth):
    """Returns success=False for empty step_ids list."""
    params = RemoveStepsFromFlowParams(flow_sys_id=FLOW_ID, step_ids=[])
    result = remove_steps_from_flow(config, auth, params)
    assert result.success is False
    assert "step_ids" in result.message.lower() or "empty" in result.message.lower()


from servicenow_mcp.tools.flow_tools import (
    AddLogicToFlowParams,
    LogicInputParam,
    AddLogicToFlowResponse,
    add_logic_to_flow,
)

IF_DEFINITION_ID = "af4e1945c3e232002841b63b12d3ae3e"

MOCK_FLOW_FOR_LOGIC = {
    "result": {
        "data": {
            "id": FLOW_ID,
            "masterSnapshotId": "snap002",
            "name": "Test Flow",
            "triggerInstances": [],
            "actionInstances": [],
            "flowLogicInstances": [],
            "subFlowInstances": [],
        }
    }
}

MOCK_PUT_LOGIC_RESPONSE = {"result": {"data": {"id": FLOW_ID}}}


def test_add_logic_success(config, auth):
    """Adds a flowLogicInstance to the flow and PUTs back."""
    with patch("servicenow_mcp.tools.flow_tools.requests.get") as mock_get, \
         patch("servicenow_mcp.tools.flow_tools.requests.put") as mock_put, \
         patch("servicenow_mcp.tools.flow_tools.requests.post") as mock_post:
        mock_get.return_value = _make_response(200, MOCK_FLOW_FOR_LOGIC)
        mock_put.return_value = _make_response(200, MOCK_PUT_LOGIC_RESPONSE)
        mock_post.return_value = _make_response(200, MOCK_VERSION_RESPONSE)

        params = AddLogicToFlowParams(
            flow_sys_id=FLOW_ID,
            logic_type_sys_id=IF_DEFINITION_ID,
            name="If: incident is high priority",
            order=1,
        )
        result = add_logic_to_flow(config, auth, params)

    assert result.success is True
    assert result.flow_sys_id == FLOW_ID
    assert result.logic_step_id is not None

    put_body = mock_put.call_args.kwargs.get("json") or mock_put.call_args[1].get("json")
    logic_list = put_body["flowLogicInstances"]
    assert len(logic_list) == 1
    step = logic_list[0]
    assert step["definitionId"] == IF_DEFINITION_ID
    assert step["name"] == "If: incident is high priority"
    assert step["order"] == "1"
    assert step["type"] == "flowlogic"
    assert step["deleted"] is False
    assert "uiUniqueIdentifier" in step
    assert "id" in step


def test_add_logic_with_inputs(config, auth):
    """Logic inputs are included in the flowLogicInstance."""
    with patch("servicenow_mcp.tools.flow_tools.requests.get") as mock_get, \
         patch("servicenow_mcp.tools.flow_tools.requests.put") as mock_put, \
         patch("servicenow_mcp.tools.flow_tools.requests.post") as mock_post:
        mock_get.return_value = _make_response(200, MOCK_FLOW_FOR_LOGIC)
        mock_put.return_value = _make_response(200, MOCK_PUT_LOGIC_RESPONSE)
        mock_post.return_value = _make_response(200, MOCK_VERSION_RESPONSE)

        params = AddLogicToFlowParams(
            flow_sys_id=FLOW_ID,
            logic_type_sys_id=IF_DEFINITION_ID,
            name="If: check priority",
            order=2,
            inputs=[LogicInputParam(name="condition_name", value="priority=1")],
        )
        result = add_logic_to_flow(config, auth, params)

    assert result.success is True
    put_body = mock_put.call_args.kwargs.get("json") or mock_put.call_args[1].get("json")
    step = put_body["flowLogicInstances"][0]
    assert any(i["name"] == "condition_name" and i["value"] == "priority=1" for i in step["inputs"])


def test_add_logic_with_parent(config, auth):
    """Parent uiUniqueIdentifier is set on nested logic blocks (e.g. Else inside If)."""
    parent_uid = "parent-uid-abc123"
    with patch("servicenow_mcp.tools.flow_tools.requests.get") as mock_get, \
         patch("servicenow_mcp.tools.flow_tools.requests.put") as mock_put, \
         patch("servicenow_mcp.tools.flow_tools.requests.post") as mock_post:
        mock_get.return_value = _make_response(200, MOCK_FLOW_FOR_LOGIC)
        mock_put.return_value = _make_response(200, MOCK_PUT_LOGIC_RESPONSE)
        mock_post.return_value = _make_response(200, MOCK_VERSION_RESPONSE)

        params = AddLogicToFlowParams(
            flow_sys_id=FLOW_ID,
            logic_type_sys_id="1f781bf3c32232002841b63b12d3aee6",  # Else
            name="Else:",
            order=3,
            parent_ui_id=parent_uid,
        )
        result = add_logic_to_flow(config, auth, params)

    assert result.success is True
    put_body = mock_put.call_args.kwargs.get("json") or mock_put.call_args[1].get("json")
    step = put_body["flowLogicInstances"][0]
    assert step["parent"] == parent_uid


def test_add_logic_appends_to_existing(config, auth):
    """New logic block is appended, not replacing existing blocks."""
    existing_logic_payload = {
        "result": {
            "data": {
                "id": FLOW_ID,
                "masterSnapshotId": "snap003",
                "name": "Test Flow",
                "triggerInstances": [],
                "actionInstances": [],
                "flowLogicInstances": [
                    {"id": "existing-logic-id", "order": "1", "deleted": False,
                     "uiUniqueIdentifier": "uid-existing", "type": "flowlogic",
                     "definitionId": IF_DEFINITION_ID},
                ],
                "subFlowInstances": [],
            }
        }
    }
    with patch("servicenow_mcp.tools.flow_tools.requests.get") as mock_get, \
         patch("servicenow_mcp.tools.flow_tools.requests.put") as mock_put, \
         patch("servicenow_mcp.tools.flow_tools.requests.post") as mock_post:
        mock_get.return_value = _make_response(200, existing_logic_payload)
        mock_put.return_value = _make_response(200, MOCK_PUT_LOGIC_RESPONSE)
        mock_post.return_value = _make_response(200, MOCK_VERSION_RESPONSE)

        params = AddLogicToFlowParams(
            flow_sys_id=FLOW_ID,
            logic_type_sys_id=IF_DEFINITION_ID,
            name="If: second condition",
            order=2,
        )
        result = add_logic_to_flow(config, auth, params)

    assert result.success is True
    put_body = mock_put.call_args.kwargs.get("json") or mock_put.call_args[1].get("json")
    assert len(put_body["flowLogicInstances"]) == 2
    assert put_body["flowLogicInstances"][0]["id"] == "existing-logic-id"


def test_add_logic_get_failure(config, auth):
    import requests as req_lib
    with patch("servicenow_mcp.tools.flow_tools.requests.get") as mock_get:
        mock_get.side_effect = req_lib.RequestException("timeout")
        params = AddLogicToFlowParams(
            flow_sys_id=FLOW_ID, logic_type_sys_id=IF_DEFINITION_ID, name="If:", order=1
        )
        result = add_logic_to_flow(config, auth, params)
    assert result.success is False
    assert "timeout" in result.message


def test_add_logic_creates_version(config, auth):
    """create_version is called after PUT."""
    with patch("servicenow_mcp.tools.flow_tools.requests.get") as mock_get, \
         patch("servicenow_mcp.tools.flow_tools.requests.put") as mock_put, \
         patch("servicenow_mcp.tools.flow_tools.requests.post") as mock_post:
        mock_get.return_value = _make_response(200, MOCK_FLOW_FOR_LOGIC)
        mock_put.return_value = _make_response(200, MOCK_PUT_LOGIC_RESPONSE)
        mock_post.return_value = _make_response(200, MOCK_VERSION_RESPONSE)

        params = AddLogicToFlowParams(
            flow_sys_id=FLOW_ID, logic_type_sys_id=IF_DEFINITION_ID, name="If:", order=1
        )
        add_logic_to_flow(config, auth, params)

    post_url = mock_post.call_args.args[0]
    assert "create_version" in post_url


# ---------------------------------------------------------------------------
# Task 3: list_action_type_outputs
# ---------------------------------------------------------------------------

from servicenow_mcp.tools.flow_tools import (
    ListActionTypeOutputsParams,
    ListActionTypeOutputsResult,
    list_action_type_outputs,
)

ACTION_DEF_ID = "b93f42810b30030085c083eb37673a63"  # Look Up Record definition

MOCK_ACTION_OUTPUTS = {
    "result": [
        {
            "sys_id": "out111111111111111111111111111a",
            "element": "record",
            "label": {"value": "Record", "display_value": "Record"},
            "column_label": {"value": "Record", "display_value": "Record"},
            "internal_type": {"value": "GlideRecord", "display_value": "GlideRecord"},
            "mandatory": {"value": "false"},
            "default_value": {"value": ""},
            "order": {"value": "100"},
        },
        {
            "sys_id": "out222222222222222222222222222b",
            "element": "found",
            "label": {"value": "Found", "display_value": "Found"},
            "column_label": {"value": "Found", "display_value": "Found"},
            "internal_type": {"value": "boolean", "display_value": "True/False"},
            "mandatory": {"value": "false"},
            "default_value": {"value": ""},
            "order": {"value": "200"},
        },
    ]
}


def test_list_action_type_outputs_success(config, auth):
    """Returns list of output variable definitions for an action type."""
    with patch("servicenow_mcp.tools.flow_tools.requests.get") as mock_get:
        mock_get.return_value = _make_response(200, MOCK_ACTION_OUTPUTS)

        params = ListActionTypeOutputsParams(action_type_sys_id=ACTION_DEF_ID)
        result = list_action_type_outputs(config, auth, params)

    assert result.action_type_sys_id == ACTION_DEF_ID
    assert len(result.outputs) == 2
    assert result.outputs[0].element == "record"
    assert result.outputs[0].label == "Record"
    assert result.outputs[0].internal_type == "GlideRecord"
    assert result.outputs[1].element == "found"

    # Verify correct Table API query
    call_url = mock_get.call_args[0][0]
    assert "sys_hub_action_output" in call_url
    call_params = mock_get.call_args.kwargs.get("params") or mock_get.call_args[1].get("params", {})
    query = call_params.get("sysparm_query", "")
    assert ACTION_DEF_ID in query


def test_list_action_type_outputs_empty(config, auth):
    """Returns empty list when action type has no outputs."""
    with patch("servicenow_mcp.tools.flow_tools.requests.get") as mock_get:
        mock_get.return_value = _make_response(200, {"result": []})

        params = ListActionTypeOutputsParams(action_type_sys_id=ACTION_DEF_ID)
        result = list_action_type_outputs(config, auth, params)

    assert result.outputs == []
    assert "0" in result.message


def test_list_action_type_outputs_request_failure(config, auth):
    """Returns empty list with error message on request failure."""
    import requests as req_lib
    with patch("servicenow_mcp.tools.flow_tools.requests.get") as mock_get:
        mock_get.side_effect = req_lib.RequestException("timeout")

        params = ListActionTypeOutputsParams(action_type_sys_id=ACTION_DEF_ID)
        result = list_action_type_outputs(config, auth, params)

    assert result.outputs == []
    assert "timeout" in result.message


# ---------------------------------------------------------------------------
# Task 4: list_flow_io
# ---------------------------------------------------------------------------

from servicenow_mcp.tools.flow_tools import (
    ListFlowIOParams,
    ListFlowIOResult,
    list_flow_io,
)

MOCK_FLOW_INPUTS = {
    "result": [
        {
            "sys_id": "inp001",
            "element": "record_sys_id",
            "label": {"value": "Record Sys ID", "display_value": "Record Sys ID"},
            "column_label": {"value": "Record Sys ID", "display_value": "Record Sys ID"},
            "internal_type": {"value": "string", "display_value": "String"},
            "mandatory": {"value": "true"},
            "default_value": {"value": ""},
            "order": {"value": "100"},
        }
    ]
}

MOCK_FLOW_OUTPUTS = {
    "result": [
        {
            "sys_id": "out001",
            "element": "result_record",
            "label": {"value": "Result Record", "display_value": "Result Record"},
            "column_label": {"value": "Result Record", "display_value": "Result Record"},
            "internal_type": {"value": "GlideRecord", "display_value": "GlideRecord"},
            "mandatory": {"value": "false"},
            "default_value": {"value": ""},
            "order": {"value": "100"},
        }
    ]
}


def test_list_flow_io_success(config, auth):
    """Returns inputs and outputs for the flow in one call."""
    with patch("servicenow_mcp.tools.flow_tools.requests.get") as mock_get:
        mock_get.side_effect = [
            _make_response(200, MOCK_FLOW_INPUTS),
            _make_response(200, MOCK_FLOW_OUTPUTS),
        ]

        params = ListFlowIOParams(flow_sys_id=FLOW_ID)
        result = list_flow_io(config, auth, params)

    assert result.flow_sys_id == FLOW_ID
    assert len(result.inputs) == 1
    assert result.inputs[0].element == "record_sys_id"
    assert result.inputs[0].mandatory is True
    assert len(result.outputs) == 1
    assert result.outputs[0].element == "result_record"
    assert result.outputs[0].internal_type == "GlideRecord"


def test_list_flow_io_queries_correct_tables(config, auth):
    """Queries sys_hub_flow_input and sys_hub_flow_output with correct filter."""
    with patch("servicenow_mcp.tools.flow_tools.requests.get") as mock_get:
        mock_get.side_effect = [
            _make_response(200, MOCK_FLOW_INPUTS),
            _make_response(200, MOCK_FLOW_OUTPUTS),
        ]

        params = ListFlowIOParams(flow_sys_id=FLOW_ID)
        list_flow_io(config, auth, params)

    calls = mock_get.call_args_list
    assert len(calls) == 2
    input_url, output_url = calls[0][0][0], calls[1][0][0]
    assert "sys_hub_flow_input" in input_url
    assert "sys_hub_flow_output" in output_url
    # Both queries must include the flow sys_id
    for call in calls:
        p = call.kwargs.get("params") or call[1].get("params", {})
        assert FLOW_ID in p.get("sysparm_query", "")


def test_list_flow_io_empty(config, auth):
    """Returns empty lists when flow has no I/O defined."""
    with patch("servicenow_mcp.tools.flow_tools.requests.get") as mock_get:
        mock_get.side_effect = [
            _make_response(200, {"result": []}),
            _make_response(200, {"result": []}),
        ]

        params = ListFlowIOParams(flow_sys_id=FLOW_ID)
        result = list_flow_io(config, auth, params)

    assert result.inputs == []
    assert result.outputs == []


def test_list_flow_io_request_failure(config, auth):
    """Returns empty lists with error when request fails."""
    import requests as req_lib
    with patch("servicenow_mcp.tools.flow_tools.requests.get") as mock_get:
        mock_get.side_effect = req_lib.RequestException("network error")

        params = ListFlowIOParams(flow_sys_id=FLOW_ID)
        result = list_flow_io(config, auth, params)

    assert result.inputs == []
    assert result.outputs == []
    assert "network error" in result.message


# ---------------------------------------------------------------------------
# Task 6: execute_flow
# ---------------------------------------------------------------------------

from servicenow_mcp.tools.flow_tools import (
    ExecuteFlowParams,
    execute_flow,
)

MOCK_FLOW_META_ROW = {
    "result": [
        {
            "sys_id": FLOW_ID,
            "internal_name": "u_test_flow",
            "scope": "global",
        }
    ]
}

MOCK_SCRIPT_SUCCESS = {
    "result": {
        "status": "success",
        "output": '{"executionId": "ctx123456789", "state": "running"}',
    }
}

MOCK_PROCESSFLOW_TEST_SUCCESS = {
    "result": {"executionId": "ctx_from_rest_aaaaaaaaaaaaaaaaaa"},
}

MOCK_SCRIPT_FAILURE = {
    "result": {
        "status": "error",
        "output": "FlowAPI error: flow not found",
    }
}


def test_execute_flow_success(config, auth):
    """POST processflow/flow/{id}/test returns execution id (REST primary)."""
    with patch("servicenow_mcp.tools.flow_tools.requests.post") as mock_post:
        mock_post.return_value = _make_response(200, MOCK_PROCESSFLOW_TEST_SUCCESS)

        params = ExecuteFlowParams(flow_sys_id=FLOW_ID)
        result = execute_flow(config, auth, params)

    assert result.success is True
    assert result.execution_id == "ctx_from_rest_aaaaaaaaaaaaaaaaaa"
    assert result.execution_source == "processflow_test"
    url = mock_post.call_args[0][0]
    assert "/processflow/flow/" in url and url.endswith("/test")


def test_execute_flow_with_inputs(config, auth):
    """Inputs are JSON body for processflow test POST."""
    with patch("servicenow_mcp.tools.flow_tools.requests.post") as mock_post:
        mock_post.return_value = _make_response(200, MOCK_PROCESSFLOW_TEST_SUCCESS)

        params = ExecuteFlowParams(
            flow_sys_id=FLOW_ID,
            inputs={"record_sys_id": "abc123", "priority": "1"},
        )
        result = execute_flow(config, auth, params)

    assert result.success is True
    post_body = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json", {})
    assert post_body.get("inputs", {}).get("record_sys_id") == "abc123"


def test_execute_flow_script_error(config, auth):
    """REST returns no id; fallback script returns error status."""
    with patch("servicenow_mcp.tools.flow_tools.requests.get") as mock_get, patch(
        "servicenow_mcp.tools.flow_tools.requests.post"
    ) as mock_post:
        mock_get.return_value = _make_response(200, MOCK_FLOW_META_ROW)
        mock_post.side_effect = [
            _make_response(200, {"result": {}}),
            _make_response(200, MOCK_SCRIPT_FAILURE),
        ]

        params = ExecuteFlowParams(flow_sys_id=FLOW_ID)
        result = execute_flow(config, auth, params)

    assert result.success is False
    assert "FlowAPI error" in result.message


def test_execute_flow_request_failure(config, auth):
    """Returns success=False when REST and script POST both fail."""
    import requests as req_lib

    with patch("servicenow_mcp.tools.flow_tools.requests.get") as mock_get, patch(
        "servicenow_mcp.tools.flow_tools.requests.post"
    ) as mock_post:
        mock_get.return_value = _make_response(200, MOCK_FLOW_META_ROW)
        mock_post.side_effect = [
            req_lib.RequestException("rest failed"),
            req_lib.RequestException("connection refused"),
        ]

        params = ExecuteFlowParams(flow_sys_id=FLOW_ID)
        result = execute_flow(config, auth, params)

    assert result.success is False
    assert "connection refused" in result.message


def test_execute_flow_fallback_to_script(config, auth):
    """When test endpoint returns 200 without execution id, uses GlideFlowAPI script."""
    with patch("servicenow_mcp.tools.flow_tools.requests.get") as mock_get, patch(
        "servicenow_mcp.tools.flow_tools.requests.post"
    ) as mock_post:
        mock_get.return_value = _make_response(200, MOCK_FLOW_META_ROW)
        mock_post.side_effect = [
            _make_response(200, {"result": {}}),
            _make_response(200, MOCK_SCRIPT_SUCCESS),
        ]

        params = ExecuteFlowParams(flow_sys_id=FLOW_ID)
        result = execute_flow(config, auth, params)

    assert result.success is True
    assert result.execution_id == "ctx123456789"
    assert result.execution_source == "script"
    assert mock_post.call_count == 2


# ---------------------------------------------------------------------------
# get_flow_execution_detail (scripted sys_hub_flow_context + stage context)
# ---------------------------------------------------------------------------

from servicenow_mcp.tools.flow_tools import (
    GetFlowExecutionDetailParams,
    get_flow_execution_detail,
)

EXEC_CTX_ID = "exec1111111111111111111111111111"

MOCK_DETAIL_BODY = {
    "context": {
        "sys_id": EXEC_CTX_ID,
        "name": "Flow run",
        "state": "complete",
        "started": "2026-01-01 10:00:00",
        "ended": "2026-01-01 10:00:05",
        "error": "",
        "flow": "flow2222222222222222222222222222",
    },
    "steps": [
        {
            "sys_id": "stepaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            "name": "Look Up Record",
            "state": "complete",
            "started": "2026-01-01 10:00:01",
            "ended": "2026-01-01 10:00:02",
            "output": "",
            "error": "",
        },
    ],
}

MOCK_DETAIL_SUCCESS = {
    "result": {
        "status": "success",
        "output": json.dumps(MOCK_DETAIL_BODY),
    }
}


def test_get_flow_execution_detail_success(config, auth):
    """Parses context and steps from scripted API JSON output."""
    with patch("servicenow_mcp.tools.flow_tools.requests.post") as mock_post:
        mock_post.return_value = _make_response(200, MOCK_DETAIL_SUCCESS)

        params = GetFlowExecutionDetailParams(execution_sys_id=EXEC_CTX_ID)
        result = get_flow_execution_detail(config, auth, params)

    assert result.success is True
    assert result.execution_sys_id == EXEC_CTX_ID
    assert result.state == "complete"
    assert len(result.steps) == 1
    assert result.steps[0].sys_id == "stepaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    assert result.steps[0].name == "Look Up Record"
    script = mock_post.call_args.kwargs.get("json", {}).get("script", "")
    assert EXEC_CTX_ID in script
    assert "sys_hub_flow_context" in script


def test_get_flow_execution_detail_empty_steps(config, auth):
    """Allows zero step rows."""
    body = {"context": MOCK_DETAIL_BODY["context"], "steps": []}
    with patch("servicenow_mcp.tools.flow_tools.requests.post") as mock_post:
        mock_post.return_value = _make_response(
            200,
            {"result": {"status": "success", "output": json.dumps(body)}},
        )
        result = get_flow_execution_detail(
            config, auth, GetFlowExecutionDetailParams(execution_sys_id=EXEC_CTX_ID)
        )
    assert result.success is True
    assert result.steps == []


def test_get_flow_execution_detail_not_found(config, auth):
    """Maps script not_found to success=False."""
    out = json.dumps({"error": "not_found", "execution_sys_id": EXEC_CTX_ID})
    with patch("servicenow_mcp.tools.flow_tools.requests.post") as mock_post:
        mock_post.return_value = _make_response(
            200, {"result": {"status": "success", "output": out}}
        )
        result = get_flow_execution_detail(
            config, auth, GetFlowExecutionDetailParams(execution_sys_id=EXEC_CTX_ID)
        )
    assert result.success is False
    assert "not found" in result.message.lower()


def test_get_flow_execution_detail_script_status_error(config, auth):
    """Propagates scripted API error status."""
    with patch("servicenow_mcp.tools.flow_tools.requests.post") as mock_post:
        mock_post.return_value = _make_response(
            200,
            {"result": {"status": "error", "output": "ACL failure"}},
        )
        result = get_flow_execution_detail(
            config, auth, GetFlowExecutionDetailParams(execution_sys_id=EXEC_CTX_ID)
        )
    assert result.success is False
    assert "ACL failure" in result.message


def test_get_flow_execution_detail_request_failure(config, auth):
    """Handles HTTP failure."""
    import requests as req_lib

    with patch("servicenow_mcp.tools.flow_tools.requests.post") as mock_post:
        mock_post.side_effect = req_lib.RequestException("timeout")
        result = get_flow_execution_detail(
            config, auth, GetFlowExecutionDetailParams(execution_sys_id=EXEC_CTX_ID)
        )
    assert result.success is False
    assert "timeout" in result.message


def test_get_flow_execution_detail_no_script_path(config, auth):
    """Fails fast when scripted endpoint is not configured."""
    c = config.model_copy(update={"script_execution_api_resource_path": None})
    result = get_flow_execution_detail(
        c, auth, GetFlowExecutionDetailParams(execution_sys_id=EXEC_CTX_ID)
    )
    assert result.success is False
    assert "script_execution_api_resource_path" in result.message


def test_get_flow_execution_detail_invalid_json_output(config, auth):
    """Rejects non-JSON script output."""
    with patch("servicenow_mcp.tools.flow_tools.requests.post") as mock_post:
        mock_post.return_value = _make_response(
            200,
            {"result": {"status": "success", "output": "NOT_JSON"}},
        )
        result = get_flow_execution_detail(
            config, auth, GetFlowExecutionDetailParams(execution_sys_id=EXEC_CTX_ID)
        )
    assert result.success is False
    assert "not valid JSON" in result.message


def test_get_flow_execution_detail_missing_context(config, auth):
    """Handles malformed payload without context object."""
    with patch("servicenow_mcp.tools.flow_tools.requests.post") as mock_post:
        mock_post.return_value = _make_response(
            200,
            {"result": {"status": "success", "output": json.dumps({"steps": []})}},
        )
        result = get_flow_execution_detail(
            config, auth, GetFlowExecutionDetailParams(execution_sys_id=EXEC_CTX_ID)
        )
    assert result.success is False
    assert "unexpected payload" in result.message


def test_get_flow_execution_detail_skips_malformed_steps(config, auth):
    """Drops step dicts without sys_id."""
    body = {
        "context": MOCK_DETAIL_BODY["context"],
        "steps": [
            {"name": "no sys_id"},
            {"sys_id": "goodstep", "name": "OK"},
        ],
    }
    with patch("servicenow_mcp.tools.flow_tools.requests.post") as mock_post:
        mock_post.return_value = _make_response(
            200,
            {"result": {"status": "success", "output": json.dumps(body)}},
        )
        result = get_flow_execution_detail(
            config, auth, GetFlowExecutionDetailParams(execution_sys_id=EXEC_CTX_ID)
        )
    assert result.success is True
    assert len(result.steps) == 1
    assert result.steps[0].sys_id == "goodstep"


def test_get_flow_execution_detail_strips_execution_sys_id(config, auth):
    """Trims whitespace on execution_sys_id."""
    with patch("servicenow_mcp.tools.flow_tools.requests.post") as mock_post:
        mock_post.return_value = _make_response(200, MOCK_DETAIL_SUCCESS)
        get_flow_execution_detail(
            config,
            auth,
            GetFlowExecutionDetailParams(execution_sys_id=f"  {EXEC_CTX_ID}  "),
        )
    script = mock_post.call_args.kwargs.get("json", {}).get("script", "")
    assert json.dumps(EXEC_CTX_ID.strip()) in script or EXEC_CTX_ID.strip() in script


CLONE_SOURCE = "a" * 32
CLONE_NEW = "b" * 32


def test_clone_flow_success(config, auth):
    """GET source, POST shell, PUT cloned instances, Save version."""
    from servicenow_mcp.tools.flow_tools import CloneFlowParams, clone_flow

    table_row = {
        "sys_id": CLONE_SOURCE,
        "type": "flow",
        "scope": "global",
        "run_as": "user",
        "access": "public",
        "flow_priority": "MEDIUM",
        "description": "",
    }
    src_payload = {
        "result": {
            "data": {
                "id": CLONE_SOURCE,
                "name": "Source Flow",
                "triggerInstances": [
                    {
                        "id": "trigold",
                        "flowSysId": CLONE_SOURCE,
                        "type": "record_create",
                        "remoteSysId": "td1",
                    }
                ],
                "actionInstances": [
                    {
                        "id": "actold",
                        "flowSysId": CLONE_SOURCE,
                        "order": "1",
                        "uiUniqueIdentifier": "u1u1u1u1u1u1u1u1u1u1u1u1u1u1",
                        "deleted": False,
                    }
                ],
                "flowLogicInstances": [],
                "subFlowInstances": [],
            }
        }
    }
    shell_resp = {
        "result": {"data": {"id": CLONE_NEW, "internalName": "u_cloned_flow", "name": "Cloned"}}
    }

    with patch("servicenow_mcp.tools.flow_tools.requests.get") as mock_get, \
            patch("servicenow_mcp.tools.flow_tools.requests.post") as mock_post, \
            patch("servicenow_mcp.tools.flow_tools.requests.put") as mock_put, \
            patch("servicenow_mcp.tools.flow_tools._patch_flow_version_trigger_type", return_value=None), \
            patch("servicenow_mcp.tools.flow_tools._release_flow_edit_lock", return_value=None):
        mock_get.side_effect = [
            _make_response(200, {"result": table_row}),
            _make_response(200, src_payload),
        ]
        mock_post.side_effect = [
            _make_response(200, shell_resp),
            _make_response(200, MOCK_VERSION_RESPONSE),
            _make_response(200, MOCK_VERSION_RESPONSE),
        ]
        mock_put.return_value = _make_response(200, {"result": {"data": {"id": CLONE_NEW}}})

        result = clone_flow(
            config,
            auth,
            CloneFlowParams(source_flow_sys_id=CLONE_SOURCE, name="Cloned Copy"),
        )

    assert result.success is True
    assert result.flow_sys_id == CLONE_NEW
    assert result.source_flow_sys_id == CLONE_SOURCE
    put_body = mock_put.call_args.kwargs.get("json") or mock_put.call_args[1].get("json")
    assert put_body["id"] == CLONE_NEW
    assert len(put_body["triggerInstances"]) == 1
    assert put_body["triggerInstances"][0]["flowSysId"] == CLONE_NEW
    assert put_body["triggerInstances"][0]["id"] != "trigold"
    assert len(put_body["actionInstances"]) == 1
    assert put_body["actionInstances"][0]["flowSysId"] == CLONE_NEW
    assert put_body["actionInstances"][0]["uiUniqueIdentifier"] != "u1u1u1u1u1u1u1u1u1u1u1u1u1u1"


def test_clone_flow_rejects_subflow_type(config, auth):
    """Refuses when sys_hub_flow.type is subflow."""
    from servicenow_mcp.tools.flow_tools import CloneFlowParams, clone_flow

    with patch("servicenow_mcp.tools.flow_tools.requests.get") as mock_get:
        mock_get.return_value = _make_response(
            200,
            {"result": {"sys_id": CLONE_SOURCE, "type": "subflow"}},
        )
        result = clone_flow(
            config,
            auth,
            CloneFlowParams(source_flow_sys_id=CLONE_SOURCE, name="X"),
        )
    assert result.success is False
    assert "type=flow" in result.message


PARENT_FLOW = "f" * 32
SUBFLOW_ID = "c" * 32


def test_add_subflow_step_success(config, auth):
    """Validates parent flow + subflow, appends subFlowInstances, PUT, create_version."""
    from servicenow_mcp.tools.flow_tools import AddSubflowStepToFlowParams, add_subflow_step_to_flow

    payload = {
        "result": {
            "data": {
                "id": PARENT_FLOW,
                "name": "Parent",
                "triggerInstances": [],
                "actionInstances": [],
                "flowLogicInstances": [],
                "subFlowInstances": [],
            }
        }
    }

    with patch("servicenow_mcp.tools.flow_tools._get_artifact") as mock_art, \
            patch("servicenow_mcp.tools.flow_tools.requests.get") as mock_get, \
            patch("servicenow_mcp.tools.flow_tools.requests.put") as mock_put, \
            patch("servicenow_mcp.tools.flow_tools.requests.post") as mock_post:
        mock_art.side_effect = [
            MagicMock(artifact={"sys_id": PARENT_FLOW, "type": "flow"}, message="ok"),
            MagicMock(artifact={"sys_id": SUBFLOW_ID, "type": "subflow"}, message="ok"),
        ]
        mock_get.return_value = _make_response(200, payload)
        mock_put.return_value = _make_response(200, MOCK_PUT_RESPONSE)
        mock_post.return_value = _make_response(200, MOCK_VERSION_RESPONSE)

        result = add_subflow_step_to_flow(
            config,
            auth,
            AddSubflowStepToFlowParams(
                flow_sys_id=PARENT_FLOW,
                subflow_sys_id=SUBFLOW_ID,
                name="Run my subflow",
                order=3,
                inputs=[],
            ),
        )

    assert result.success is True
    assert result.flow_sys_id == PARENT_FLOW
    assert result.subflow_step_id
    put_body = mock_put.call_args.kwargs.get("json") or mock_put.call_args[1].get("json")
    subs = put_body["subFlowInstances"]
    assert len(subs) == 1
    assert subs[0]["subFlowSysId"] == SUBFLOW_ID
    assert subs[0]["type"] == "subflow"
    assert subs[0]["order"] == "3"


def test_add_subflow_step_rejects_missing_subflow(config, auth):
    """Fails when subflow artifact not found."""
    from servicenow_mcp.tools.flow_tools import AddSubflowStepToFlowParams, add_subflow_step_to_flow

    with patch("servicenow_mcp.tools.flow_tools._get_artifact") as mock_art:
        mock_art.side_effect = [
            MagicMock(artifact={"sys_id": PARENT_FLOW}, message="ok"),
            MagicMock(artifact=None, message="not found"),
        ]
        result = add_subflow_step_to_flow(
            config,
            auth,
            AddSubflowStepToFlowParams(
                flow_sys_id=PARENT_FLOW,
                subflow_sys_id=SUBFLOW_ID,
                name="X",
                order=1,
            ),
        )
    assert result.success is False


def test_update_flow_trigger_success(config, auth):
    """GET processflow, replace triggerInstances, PUT, Save."""
    from servicenow_mcp.tools.flow_tools import (
        TriggerInstanceParam,
        UpdateFlowTriggerParams,
        update_flow_trigger,
    )

    payload = {
        "result": {
            "data": {
                "id": FLOW_ID,
                "name": "F",
                "triggerInstances": [{"id": "old"}],
                "actionInstances": [],
            }
        }
    }
    with patch("servicenow_mcp.tools.flow_tools._get_artifact") as mock_ga, \
            patch("servicenow_mcp.tools.flow_tools.requests.get") as mock_get, \
            patch("servicenow_mcp.tools.flow_tools.requests.put") as mock_put, \
            patch("servicenow_mcp.tools.flow_tools.requests.post") as mock_post, \
            patch("servicenow_mcp.tools.flow_tools._patch_flow_version_trigger_type", return_value=None), \
            patch("servicenow_mcp.tools.flow_tools._release_flow_edit_lock", return_value=None), \
            patch(
                "servicenow_mcp.tools.flow_tools._resolve_trigger_definition_id",
                return_value=("defid", None),
            ), \
            patch("servicenow_mcp.tools.flow_tools._build_trigger_instances") as mock_build:
        mock_ga.return_value = MagicMock(artifact={"sys_id": FLOW_ID, "type": "flow"}, message="ok")
        mock_get.return_value = _make_response(200, payload)
        mock_put.return_value = _make_response(200, {})
        mock_post.return_value = _make_response(200, {})
        mock_build.return_value = [{"id": "newtrig", "flowSysId": FLOW_ID}]

        result = update_flow_trigger(
            config,
            auth,
            UpdateFlowTriggerParams(
                flow_sys_id=FLOW_ID,
                trigger=TriggerInstanceParam(type="record_create", table="incident"),
            ),
        )

    assert result.success is True
    assert result.flow_sys_id == FLOW_ID
    put_body = mock_put.call_args.kwargs.get("json") or mock_put.call_args[1].get("json")
    assert put_body["triggerInstances"][0]["id"] == "newtrig"


def test_remove_steps_marks_subflow_deleted(config, auth):
    """remove_steps_from_flow marks subFlowInstances by id."""
    from servicenow_mcp.tools.flow_tools import RemoveStepsFromFlowParams, remove_steps_from_flow

    sf_id = "subflowstep111111111111111111sf"
    payload = {
        "result": {
            "data": {
                "id": FLOW_ID,
                "actionInstances": [],
                "flowLogicInstances": [],
                "subFlowInstances": [
                    {"id": sf_id, "order": "1", "deleted": False, "type": "subflow"},
                ],
            }
        }
    }
    with patch("servicenow_mcp.tools.flow_tools.requests.get") as mock_get, \
            patch("servicenow_mcp.tools.flow_tools.requests.put") as mock_put, \
            patch("servicenow_mcp.tools.flow_tools.requests.post") as mock_post:
        mock_get.return_value = _make_response(200, payload)
        mock_put.return_value = _make_response(200, MOCK_PUT_RESPONSE)
        mock_post.return_value = _make_response(200, MOCK_VERSION_RESPONSE)

        result = remove_steps_from_flow(
            config,
            auth,
            RemoveStepsFromFlowParams(flow_sys_id=FLOW_ID, step_ids=[sf_id]),
        )

    assert result.success is True
    put_body = mock_put.call_args.kwargs.get("json") or mock_put.call_args[1].get("json")
    assert put_body["subFlowInstances"][0]["deleted"] is True
