"""Tests for flow_tools phase 2 additions."""
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
