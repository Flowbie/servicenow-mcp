"""
Flow Designer tools for the ServiceNow MCP server.

Creates Flow Designer flows via the internal /api/now/processflow/ API, which is the
only mechanism capable of writing trigger instances and action instances (the standard
Table API cannot write sys_hub_flow_snapshot, which has sys_policy=read).

API sequence for create_flow:
  1. POST /api/now/processflow/flow          — create flow shell
  2. POST /api/now/processflow/versioning/create_version  — initial autosave
  3. PUT  /api/now/processflow/flow          — save trigger + action instances
  4. POST /api/now/processflow/versioning/create_version  — final autosave
"""

import logging
import uuid
from typing import List, Optional

import requests
from pydantic import BaseModel, Field

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.utils.config import ServerConfig

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Parameter models
# ---------------------------------------------------------------------------


class TriggerInputParam(BaseModel):
    """A single trigger input name/value pair."""

    name: str = Field(..., description="Trigger input name (e.g. 'table', 'condition')")
    value: str = Field(..., description="Trigger input value (all values are strings)")


class TriggerInstanceParam(BaseModel):
    """Trigger configuration for a flow.

    Convenience fields 'table' and 'condition' are converted to trigger inputs
    automatically. Provide 'inputs' directly to override all trigger inputs.
    """

    type: str = Field(
        ...,
        description=(
            "Trigger type string. Common values: 'record_create', "
            "'record_create_or_update', 'record_update', 'recurrence'. "
            "Verify available types via GET /api/now/hub/triggerpicker/basic on the instance."
        ),
    )
    trigger_definition_id: str = Field(
        ...,
        description=(
            "sys_id of the trigger type definition (sys_hub_trigger_type). "
            "For 'record_create' on most instances: '798916a0c31322002841b63b12d3ae7c'. "
            "For 'record_create_or_update': 'a45d9180c32222002841b63b12d3aea7'. "
            "Verify per instance via GET /api/now/hub/triggerpicker/basic."
        ),
    )
    name: Optional[str] = Field(
        None,
        description=(
            "Display name for the trigger (e.g. 'Created', 'Created or Updated'). "
            "Defaults to the type value if omitted."
        ),
    )
    table: Optional[str] = Field(
        None,
        description=(
            "Table name to trigger on (e.g. 'incident'). "
            "Convenience field — sets the 'table' trigger input. "
            "Ignored if 'inputs' is provided."
        ),
    )
    condition: Optional[str] = Field(
        None,
        description=(
            "Encoded query condition (e.g. 'active=true'). "
            "Convenience field — sets the 'condition' trigger input. "
            "Ignored if 'inputs' is provided."
        ),
    )
    inputs: Optional[List[TriggerInputParam]] = Field(
        None,
        description=(
            "Full trigger input list. If provided, overrides 'table' and 'condition'. "
            "Only 'table' is mandatory for record triggers."
        ),
    )


class ActionInputParam(BaseModel):
    """A single action input parameter with its parameter definition sys_id."""

    id: str = Field(
        ...,
        description=(
            "Parameter definition sys_id (sys_hub_action_type_base_element.sys_id). "
            "Must exactly match the action type's parameter definition. "
            "Example — Look Up Record 'table' input: 'd909f99587003300663ca1bb36cb0ba4'."
        ),
    )
    name: str = Field(..., description="Input parameter name (e.g. 'table', 'conditions')")
    value: str = Field(..., description="Input value — all values are strings, including booleans ('0'/'1') and integers")


class ActionInstanceParam(BaseModel):
    """One action step to add to the flow."""

    action_type_sys_id: str = Field(
        ...,
        description=(
            "sys_id of the action type definition (sys_hub_action_type_definition). "
            "Known values: Look Up Record='9d09f99587003300663ca1bb36cb0ba3', "
            "Create Record='02f0b88cc3c632002841b63b12d3aeff'. "
            "Discover others via GET /api/now/hub/actionpicker/most-popular."
        ),
    )
    name: str = Field(..., description="Display name for this action step (e.g. 'Look Up Record')")
    order: int = Field(1, description="Execution order, 1-based integer")
    internal_name: Optional[str] = Field(
        None,
        description="Internal name of the action type (e.g. 'look_up_record'). Optional — used for display only.",
    )
    parent_action_type_id: Optional[str] = Field(
        None,
        description=(
            "Parent action type sys_id. "
            "For Look Up Record: 'b93f42810b30030085c083eb37673a63'. "
            "Leave empty if unknown — the platform will resolve it."
        ),
    )
    inputs: List[ActionInputParam] = Field(
        default_factory=list,
        description=(
            "Input parameters for this action. Each input requires the exact parameter "
            "definition sys_id ('id' field) from the action type. "
            "See flow-designer-api.md memory for known parameter definition IDs."
        ),
    )


class CreateFlowParams(BaseModel):
    """Parameters for creating a Flow Designer flow."""

    name: str = Field(..., description="Flow name as it will appear in Flow Designer")
    description: Optional[str] = Field(None, description="Flow description")
    scope: str = Field(
        "global",
        description="Application scope. Use 'global' for global scope or a scope sys_id.",
    )
    run_as: str = Field(
        "user",
        description="Execution context: 'user' (runs as the triggering user) or 'system'.",
    )
    access: str = Field(
        "public",
        description="Access level: 'public', 'package_private', or 'private'.",
    )
    flow_priority: str = Field(
        "MEDIUM",
        description="Flow priority: 'LOW', 'MEDIUM', or 'HIGH'.",
    )
    trigger: Optional[TriggerInstanceParam] = Field(
        None,
        description=(
            "Trigger configuration. If omitted the flow is created as a subflow "
            "(no trigger, callable by other flows or the REST API)."
        ),
    )
    actions: Optional[List[ActionInstanceParam]] = Field(
        None,
        description=(
            "Action steps to add to the flow. Each action requires exact parameter "
            "definition sys_ids for its inputs — these are instance-specific values "
            "from sys_hub_action_type_base_element. See flow-designer-api.md memory "
            "for confirmed IDs for Look Up Record and Create Record."
        ),
    )


# ---------------------------------------------------------------------------
# Response model
# ---------------------------------------------------------------------------


class CreateFlowResponse(BaseModel):
    """Response from create_flow."""

    success: bool = Field(..., description="Whether the flow was created successfully")
    message: str = Field(..., description="Human-readable result description")
    flow_sys_id: Optional[str] = Field(None, description="sys_id of the created flow (sys_hub_flow)")
    flow_name: Optional[str] = Field(None, description="Name of the created flow")
    flow_internal_name: Optional[str] = Field(None, description="Auto-generated internal name of the flow")


# ---------------------------------------------------------------------------
# Implementation
# ---------------------------------------------------------------------------


def create_flow(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: CreateFlowParams,
) -> CreateFlowResponse:
    """
    Create a new Flow Designer flow in ServiceNow.

    Uses the internal /api/now/processflow/ API (not the Table API), which is the
    only mechanism that can persist trigger instances and action instances. The
    sys_hub_flow_snapshot table is read-only via the Table API.

    Sequence:
      1. POST /processflow/flow            — create the flow shell
      2. POST /processflow/versioning/...  — initial autosave
      3. PUT  /processflow/flow            — attach trigger and actions
      4. POST /processflow/versioning/...  — final autosave

    Args:
        config: Server configuration (instance_url, auth, timeout).
        auth_manager: Authentication manager.
        params: Flow creation parameters.

    Returns:
        CreateFlowResponse with success flag, message, and flow identifiers.
    """
    processflow_base = f"{config.api_url}/processflow"
    headers = auth_manager.get_headers()

    # ------------------------------------------------------------------
    # Step 1: Create the flow shell
    # ------------------------------------------------------------------
    shell_body = {
        "name": params.name,
        "type": "flow",
        "scope": params.scope,
        "runAs": params.run_as,
        "access": params.access,
        "flowPriority": params.flow_priority,
        "status": "draft",
        "active": False,
        "deleted": False,
        "security": {"can_read": True, "can_write": True},
        "scopeName": "",
        "scopeDisplayName": "",
        "userHasRolesAssignedToFlow": True,
        "runWithRoles": {"value": "", "displayValue": ""},
        "description": params.description or "",
        "protection": "",
    }

    try:
        shell_response = requests.post(
            f"{processflow_base}/flow",
            params={
                "param_only_properties": "true",
                "sysparm_transaction_scope": "global",
            },
            json=shell_body,
            headers=headers,
            timeout=config.timeout,
        )
        shell_response.raise_for_status()
    except requests.RequestException as e:
        _body = e.response.text[:2000] if getattr(e, "response", None) is not None else ""
        logger.error(f"create_flow | shell POST failed | error={e}" + (f" | body={_body}" if _body else ""))
        return CreateFlowResponse(
            success=False,
            message=f"Failed to create flow shell: {str(e)}" + (f" | response: {_body}" if _body else ""),
        )

    shell_result = shell_response.json()
    flow_data = shell_result.get("result", {}).get("data", {})
    flow_sys_id = flow_data.get("id")
    flow_internal_name = flow_data.get("internalName")

    if not flow_sys_id:
        logger.error(
            f"create_flow | shell POST succeeded but no id in response | "
            f"response={shell_result}"
        )
        return CreateFlowResponse(
            success=False,
            message=(
                "Flow shell POST returned HTTP 200 but no flow id was found in the response. "
                f"Raw response: {shell_result}"
            ),
        )

    logger.info(f"create_flow | shell created | flow_sys_id={flow_sys_id}")

    # ------------------------------------------------------------------
    # Step 2: Initial autosave version
    # ------------------------------------------------------------------
    version_body = {
        "item_sys_id": flow_sys_id,
        "type": "Autosave",
        "annotation": "",
        "favorite": False,
    }
    version_params = {"sysparm_transaction_scope": "global"}

    try:
        requests.post(
            f"{processflow_base}/versioning/create_version",
            params=version_params,
            json=version_body,
            headers=headers,
            timeout=config.timeout,
        ).raise_for_status()
        logger.info(f"create_flow | initial autosave created | flow_sys_id={flow_sys_id}")
    except requests.RequestException as e:
        _body = e.response.text[:2000] if getattr(e, "response", None) is not None else ""
        # Autosave failure is non-fatal — the shell exists and the PUT can still proceed
        logger.warning(
            f"create_flow | initial autosave failed (non-fatal) | "
            f"flow_sys_id={flow_sys_id} | error={e}"
            + (f" | body={_body}" if _body else "")
        )

    # ------------------------------------------------------------------
    # Step 3: Build trigger and action instance payloads
    # ------------------------------------------------------------------
    trigger_instances = _build_trigger_instances(params.trigger)
    action_instances = _build_action_instances(flow_sys_id, params.actions)

    # ------------------------------------------------------------------
    # Step 4: PUT to save trigger + actions onto the flow
    # ------------------------------------------------------------------
    put_body = dict(flow_data)
    put_body["triggerInstances"] = trigger_instances
    put_body["actionInstances"] = action_instances

    try:
        put_response = requests.put(
            f"{processflow_base}/flow",
            params={"sysparm_transaction_scope": "global"},
            json=put_body,
            headers=headers,
            timeout=config.timeout,
        )
        put_response.raise_for_status()
        logger.info(
            f"create_flow | PUT saved | flow_sys_id={flow_sys_id} | "
            f"triggers={len(trigger_instances)} | actions={len(action_instances)}"
        )
    except requests.RequestException as e:
        _body = e.response.text[:2000] if getattr(e, "response", None) is not None else ""
        logger.error(
            f"create_flow | PUT failed | flow_sys_id={flow_sys_id} | error={e}"
            + (f" | body={_body}" if _body else "")
        )
        return CreateFlowResponse(
            success=False,
            message=(
                f"Flow shell was created (sys_id={flow_sys_id}) but the PUT to attach "
                f"trigger/actions failed: {str(e)}. The draft shell exists in Flow Designer."
                + (f" | response: {_body}" if _body else "")
            ),
            flow_sys_id=flow_sys_id,
            flow_name=params.name,
            flow_internal_name=flow_internal_name,
        )

    # ------------------------------------------------------------------
    # Step 5: Final autosave version
    # ------------------------------------------------------------------
    try:
        requests.post(
            f"{processflow_base}/versioning/create_version",
            params=version_params,
            json=version_body,
            headers=headers,
            timeout=config.timeout,
        ).raise_for_status()
        logger.info(f"create_flow | final autosave created | flow_sys_id={flow_sys_id}")
    except requests.RequestException as e:
        _body = e.response.text[:2000] if getattr(e, "response", None) is not None else ""
        logger.warning(
            f"create_flow | final autosave failed (non-fatal) | "
            f"flow_sys_id={flow_sys_id} | error={e}"
            + (f" | body={_body}" if _body else "")
        )

    return CreateFlowResponse(
        success=True,
        message=(
            f"Flow '{params.name}' created successfully in draft state. "
            f"sys_id={flow_sys_id}. "
            f"Open in Flow Designer to review, activate, and test."
        ),
        flow_sys_id=flow_sys_id,
        flow_name=params.name,
        flow_internal_name=flow_internal_name,
    )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _build_trigger_instances(trigger: Optional[TriggerInstanceParam]) -> list:
    """Convert a TriggerInstanceParam into the triggerInstances array for the PUT body."""
    if trigger is None:
        return []

    if trigger.inputs is not None:
        # Caller provided explicit inputs — use as-is
        inputs = [{"name": i.name, "value": i.value} for i in trigger.inputs]
    else:
        # Build inputs from convenience fields
        inputs = []
        if trigger.table:
            inputs.append({"name": "table", "value": trigger.table})
        if trigger.condition:
            inputs.append({"name": "condition", "value": trigger.condition})

    return [
        {
            "id": "",
            "name": trigger.name or trigger.type,
            "type": trigger.type,
            "triggerDefinitionId": trigger.trigger_definition_id,
            "deleted": False,
            "comment": "",
            "inputs": inputs,
        }
    ]


def _build_action_instances(flow_sys_id: str, actions: Optional[List[ActionInstanceParam]]) -> list:
    """Convert ActionInstanceParam list into the actionInstances array for the PUT body."""
    if not actions:
        return []

    result = []
    for action in actions:
        result.append(
            {
                "id": "",
                "flowSysId": flow_sys_id,
                "order": str(action.order),
                "uiUniqueIdentifier": str(uuid.uuid4()),
                "deleted": False,
                "parent": "",
                "comment": "",
                "generationSource": "",
                "uiComponentIndex": 0,
                "actionTypeSysId": action.action_type_sys_id,
                "inputs": [
                    {"id": i.id, "name": i.name, "value": i.value}
                    for i in action.inputs
                ],
                "parentActionTypeId": action.parent_action_type_id or "",
                "compiledSnapshot": "",
                "aliasIds": [],
                "internalName": action.internal_name or "",
                "name": action.name,
                "type": "action",
                "snapshot": False,
            }
        )
    return result
