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

import json
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
    trigger_definition_id: Optional[str] = Field(
        None,
        description=(
            "sys_id of the trigger type definition (sys_hub_trigger_type). "
            "If omitted, create_flow will resolve it automatically from the 'type' field "
            "by querying sys_hub_trigger_type on the instance. "
            "Call list_trigger_types to discover available sys_ids explicitly."
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


class ListTriggerTypesParams(BaseModel):
    """Parameters for list_trigger_types (no required inputs)."""
    pass


class TriggerTypeInfo(BaseModel):
    """One trigger type definition from sys_hub_trigger_type."""
    sys_id: str
    name: str
    type_string: Optional[str] = None


class ListTriggerTypesResult(BaseModel):
    """Result from list_trigger_types."""
    trigger_types: List[TriggerTypeInfo]
    message: str


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

# Maps the user-facing type string to the display name stored in sys_hub_trigger_type.name
_TRIGGER_TYPE_NAME_MAP = {
    "record_create": "Created",
    "record_create_or_update": "Created or Updated",
    "record_update": "Updated",
    "recurrence": "Recurrence",
}


# ---------------------------------------------------------------------------
# Record trigger input parameter definitions
# ---------------------------------------------------------------------------
# Each dict is a parameter definition object used by the Flow Designer renderInput
# component. Values extracted from sys_hub_flow_version.payload of a manually-created
# flow on dev296536 (2026-02-27). These are core platform config, stable within a release.


def _param(
    param_id: str,
    label: str,
    name: str,
    ptype: str,
    order: int,
    mandatory: bool = False,
    maxsize: int = 4000,
    reference: str = "",
    dependent_on: str = "",
    default_value: str = "",
    attributes: Optional[dict] = None,
    choices: Optional[list] = None,
    default_choices: Optional[list] = None,
) -> dict:
    """Build a full parameter definition dict matching the Flow Designer payload schema.

    choices and default_choices are required for 'choice' type inputs so Flow Designer
    renders display labels instead of raw values. Values are confirmed from instance
    payload (sys_hub_flow_version) of a manually-created flow on dev296536 (2026-02-27).
    """
    return {
        "children": [],
        "id": param_id,
        "label": label,
        "name": name,
        "type": ptype,
        "order": order,
        "extended": False,
        "mandatory": mandatory,
        "readOnly": False,
        "hint": "",
        "maxsize": maxsize,
        "reference": reference,
        "reference_display": "",
        "choiceOption": "",
        "table": "",
        "columnName": "",
        "defaultValue": default_value,
        "use_dependent": False,
        "fShowReferenceFinder": False,
        "local": False,
        "attributes": attributes if attributes is not None else {},
        "ref_qual": "",
        "dependent_on": dependent_on,
        "choices": choices if choices is not None else [],
        "defaultChoices": default_choices if default_choices is not None else [],
    }


# Ordered list of all 7 standard record trigger inputs.
# Must be sent in this order to match what Flow Designer produces manually.
_RECORD_TRIGGER_INPUTS: List[dict] = [
    _param("cfca92e0c31322002841b63b12d3ae00", "Table",                 "table",                 "table_name", order=1,   mandatory=True,  maxsize=80,   attributes={"filter_table_source": "RECORD_WATCHER_RESTRICTED"}),
    _param("66aadea0c31322002841b63b12d3aebf", "Condition",             "condition",             "conditions", order=100, mandatory=False, maxsize=4000, dependent_on="table"),
    _param(
        "11ffbef2072200103bf10705afd300c2", "run_on_extended", "run_on_extended", "choice",
        order=100, mandatory=False, maxsize=40, default_value="false",
        choices=[
            {"label": "Run only on current table",         "value": "false", "order": 0},
            {"label": "Run on current and extended tables", "value": "true",  "order": 1},
        ],
        default_choices=[
            {"label": "Run only on current table",         "value": "false", "order": 1},
            {"label": "Run on current and extended tables", "value": "true",  "order": 2},
        ],
    ),
    _param(
        "3f1b9e4e0f103300b599bca2ff767e21", "run_flow_in", "run_flow_in", "choice",
        order=100, mandatory=False, maxsize=40, default_value="any",
        choices=[
            {"label": "Run flow in background (default)", "value": "background", "order": 0},
            {"label": "Run flow in foreground",           "value": "foreground", "order": 1},
        ],
        default_choices=[
            {"label": "Run flow in background (default)", "value": "background", "order": 1},
            {"label": "Run flow in foreground",           "value": "foreground", "order": 2},
        ],
    ),
    _param("f89c5177c7002300f4eba1425a976385", "run_when_user_list",    "run_when_user_list",    "glide_list", order=100, mandatory=False, maxsize=4000, reference="sys_user"),
    _param(
        "1e4859f3c7002300f4eba1425a9763f9", "run_when_setting", "run_when_setting", "choice",
        order=100, mandatory=False, maxsize=40, default_value="both",
        choices=[
            {"label": "Only Run for Non-Interactive Session",                 "value": "non_interactive", "order": 0},
            {"label": "Only Run for User Interactive Session",                "value": "interactive",     "order": 1},
            {"label": "Run for Both Interactive and Non-Interactive Sessions", "value": "both",           "order": 2},
        ],
        default_choices=[
            {"label": "Only Run for Non-Interactive Session",                 "value": "non_interactive", "order": 1},
            {"label": "Only Run for User Interactive Session",                "value": "interactive",     "order": 2},
            {"label": "Run for Both Interactive and Non-Interactive Sessions", "value": "both",           "order": 3},
        ],
    ),
    _param(
        "ed7a5537c7002300f4eba1425a976391", "run_when_user_setting", "run_when_user_setting", "choice",
        order=100, mandatory=False, maxsize=40, default_value="any",
        choices=[
            {"label": "Do not run if triggered by the following users", "value": "not_one_of", "order": 0},
            {"label": "Only Run if triggered by the following users",   "value": "one_of",     "order": 1},
            {"label": "Run for any user",                               "value": "any",        "order": 2},
        ],
        default_choices=[
            {"label": "Do not run if triggered by the following users", "value": "not_one_of", "order": 1},
            {"label": "Only Run if triggered by the following users",   "value": "one_of",     "order": 2},
            {"label": "Run for any user",                               "value": "any",        "order": 3},
        ],
    ),
]
_RECORD_TRIGGER_INPUT_BY_NAME = {p["name"]: p for p in _RECORD_TRIGGER_INPUTS}
_RECORD_TRIGGER_TYPES = {"record_create", "record_create_or_update", "record_update"}


def _lookup_table_label(config: ServerConfig, auth_manager: AuthManager, table_name: str) -> str:
    """Return the display label for a table from sys_db_object (e.g. 'incident' → 'Incident').
    Falls back to title-casing the table name if the lookup fails or returns empty.
    """
    try:
        response = requests.get(
            f"{config.api_url}/table/sys_db_object",
            params={
                "sysparm_query": f"name={table_name}",
                "sysparm_fields": "label",
                "sysparm_limit": 1,
            },
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()
        records = response.json().get("result", [])
        if records:
            label = records[0].get("label", "")
            if label:
                return label
    except requests.RequestException as e:
        logger.warning(f"_lookup_table_label | failed | table={table_name} | error={e}")
    return table_name.replace("_", " ").title()


def list_trigger_types(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: ListTriggerTypesParams,
) -> ListTriggerTypesResult:
    """
    List all available Flow Designer trigger types from sys_hub_trigger_type.

    Use this to discover the sys_id values needed for create_flow's
    trigger_definition_id field, or to verify which triggers are active
    on the instance.
    """
    try:
        response = requests.get(
            f"{config.api_url}/table/sys_hub_trigger_type",
            params={
                "sysparm_fields": "sys_id,name,internal_name",
                "sysparm_limit": 50,
                "sysparm_orderby": "name",
            },
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()
    except requests.RequestException as e:
        _body = e.response.text[:2000] if getattr(e, "response", None) is not None else ""
        logger.error(f"list_trigger_types | request failed | error={e}" + (f" | body={_body}" if _body else ""))
        return ListTriggerTypesResult(
            trigger_types=[],
            message=f"Failed to fetch trigger types: {str(e)}" + (f" | response: {_body}" if _body else ""),
        )

    records = response.json().get("result", [])
    # Build a reverse map from display name → type string for annotation
    _name_to_type = {v: k for k, v in _TRIGGER_TYPE_NAME_MAP.items()}

    trigger_types = [
        TriggerTypeInfo(
            sys_id=r["sys_id"],
            name=r.get("name", ""),
            type_string=r.get("internal_name") or _name_to_type.get(r.get("name", "")),
        )
        for r in records
    ]
    logger.info(f"list_trigger_types | found {len(trigger_types)} trigger types")
    return ListTriggerTypesResult(
        trigger_types=trigger_types,
        message=f"Found {len(trigger_types)} trigger type(s). Use sys_id as trigger_definition_id in create_flow.",
    )


def _resolve_trigger_definition_id(
    config: ServerConfig,
    auth_manager: AuthManager,
    type_str: str,
) -> tuple:
    """
    Resolve a trigger type string (e.g. 'record_create') to its sys_id on this instance.

    Returns (sys_id: str | None, error_message: str | None).
    """
    display_name = _TRIGGER_TYPE_NAME_MAP.get(type_str.lower())
    if not display_name:
        # Try passing the type_str as the display name directly (e.g. user said "Created")
        display_name = type_str

    try:
        response = requests.get(
            f"{config.api_url}/table/sys_hub_trigger_type",
            params={
                "sysparm_query": f"name={display_name}",
                "sysparm_fields": "sys_id,name",
                "sysparm_limit": 1,
            },
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()
    except requests.RequestException as e:
        _body = e.response.text[:2000] if getattr(e, "response", None) is not None else ""
        return None, f"Failed to query sys_hub_trigger_type: {str(e)}" + (f" | body: {_body}" if _body else "")

    records = response.json().get("result", [])
    if not records:
        return None, (
            f"No trigger type found with name='{display_name}' (resolved from type='{type_str}'). "
            f"Call list_trigger_types to see available options."
        )

    sys_id = records[0]["sys_id"]
    logger.info(f"_resolve_trigger_definition_id | type={type_str} | name={display_name} | sys_id={sys_id}")
    return sys_id, None


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
    # Step 3: Resolve trigger_definition_id if not provided, then build payloads
    # ------------------------------------------------------------------
    if params.trigger and not params.trigger.trigger_definition_id:
        resolved_id, resolve_err = _resolve_trigger_definition_id(
            config, auth_manager, params.trigger.type
        )
        if resolve_err:
            return CreateFlowResponse(
                success=False,
                message=(
                    f"Flow shell was created (sys_id={flow_sys_id}) but trigger type "
                    f"could not be resolved: {resolve_err}. The draft shell exists in Flow Designer."
                ),
                flow_sys_id=flow_sys_id,
                flow_name=params.name,
                flow_internal_name=flow_internal_name,
            )
        params.trigger.trigger_definition_id = resolved_id

    trigger_instances = _build_trigger_instances(config, auth_manager, params.trigger, flow_sys_id)
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

    # ------------------------------------------------------------------
    # Step 6: Patch fTriggerType='Record' in the saved version payload
    # ------------------------------------------------------------------
    # The processflow PUT cannot set fTriggerType reliably — a Business Rule overwrites
    # it using a sys_hub_trigger_type field the service account cannot read. Patching the
    # serialised payload via the Table API is the only reliable fix.
    # Non-fatal: the flow functions correctly; only the trigger label in the UI is affected.
    if params.trigger and params.trigger.type in _RECORD_TRIGGER_TYPES:
        patch_err = _patch_flow_version_trigger_type(config, auth_manager, flow_sys_id)
        if patch_err:
            logger.warning(
                f"create_flow | fTriggerType patch failed (non-fatal) | "
                f"flow_sys_id={flow_sys_id} | error={patch_err}"
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


def _build_trigger_instances(
    config: ServerConfig,
    auth_manager: AuthManager,
    trigger: Optional[TriggerInstanceParam],
    flow_sys_id: str,
) -> list:
    """Convert a TriggerInstanceParam into the triggerInstances array for the PUT body.

    For record-based triggers all 7 standard inputs are always included (with empty
    values for the 5 system inputs). Each input carries a full 'parameter' sub-object
    required by the Flow Designer renderInput component — omitting it causes a
    TypeError crash in the UI.

    The table input additionally carries displayValue (e.g. 'Incident') and
    displayField ('number') so Flow Designer renders the correct label and data pill
    reference instead of showing 'undefined record' / 'undefined table'.
    """
    if trigger is None:
        return []

    # Resolve name→value from explicit inputs or convenience fields
    if trigger.inputs is not None:
        input_values = {i.name: i.value for i in trigger.inputs}
    else:
        input_values = {}
        if trigger.table:
            input_values["table"] = trigger.table
        if trigger.condition:
            input_values["condition"] = trigger.condition

    if trigger.type in _RECORD_TRIGGER_TYPES:
        # Look up the table display label so Flow Designer can render the correct
        # label and data pill (e.g. "Incident" instead of "incident" / "undefined record").
        table_value = input_values.get("table", "")
        table_label = _lookup_table_label(config, auth_manager, table_value) if table_value else ""

        # Always emit all 7 standard inputs in the required order.
        # User-supplied values override the empty default; system inputs default to "".
        built_inputs = []
        for param_def in _RECORD_TRIGGER_INPUTS:
            name = param_def["name"]
            input_obj = {
                "label": param_def["label"],
                "internalType": param_def["type"],
                "mandatory": param_def["mandatory"],
                "fromTemplate": False,
                "order": param_def["order"],
                "valueSysId": "",
                "name": name,
                "value": input_values.get(name, param_def.get("defaultValue", "")),
                "children": [],
                "parameter": param_def,
                "scriptActive": False,
            }
            # The table input needs displayValue and displayField for Flow Designer
            # to resolve the correct table label and number field data pill.
            if name == "table" and table_label:
                input_obj["displayValue"] = table_label
                input_obj["displayField"] = "number"
            built_inputs.append(input_obj)
        # Append any caller-supplied inputs not in the standard set
        for name, value in input_values.items():
            if name not in _RECORD_TRIGGER_INPUT_BY_NAME:
                built_inputs.append(_minimal_trigger_input(name, value))
    else:
        # Non-record trigger: emit only what the caller specified, with minimal parameter stub
        built_inputs = [
            _minimal_trigger_input(name, value, _RECORD_TRIGGER_INPUT_BY_NAME.get(name))
            for name, value in input_values.items()
        ]

    return [
        {
            "id": uuid.uuid4().hex,
            "flowSysId": flow_sys_id,
            "remoteSysId": "",
            "name": trigger.name or _TRIGGER_TYPE_NAME_MAP.get(trigger.type, trigger.type),
            "type": trigger.type,
            "triggerDefinitionId": trigger.trigger_definition_id,
            "fTriggerType": "Record" if trigger.type in _RECORD_TRIGGER_TYPES else "",
            "deleted": False,
            "comment": "",
            "inputs": built_inputs,
        }
    ]


def _minimal_trigger_input(name: str, value: str, param_def: Optional[dict] = None) -> dict:
    """Build a trigger input object with a minimal parameter stub for unknown input types."""
    p = param_def or _param("", name, name, "string", order=200, maxsize=4000)
    return {
        "label": p["label"],
        "internalType": p["type"],
        "mandatory": p["mandatory"],
        "fromTemplate": False,
        "order": p["order"],
        "valueSysId": "",
        "name": name,
        "value": value,
        "children": [],
        "parameter": p,
        "scriptActive": False,
    }


def _patch_flow_version_trigger_type(
    config: ServerConfig,
    auth_manager: AuthManager,
    flow_sys_id: str,
) -> Optional[str]:
    """Set fTriggerType='Record' on all trigger instances in the latest flow version payload.

    The processflow PUT cannot reliably set fTriggerType — a Business Rule overwrites it
    using a sys_hub_trigger_type field the service account cannot read. Patching the
    serialised payload directly via the Table API after autosave is the only reliable fix.

    Returns None on success, or an error message string on failure.
    """
    try:
        ver_response = requests.get(
            f"{config.api_url}/table/sys_hub_flow_version",
            params={
                "sysparm_query": f"flow={flow_sys_id}^ORDERBYDESCsys_created_on",
                "sysparm_fields": "sys_id,payload",
                "sysparm_limit": 1,
            },
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        ver_response.raise_for_status()
    except requests.RequestException as e:
        _body = e.response.text[:2000] if getattr(e, "response", None) is not None else ""
        return f"GET sys_hub_flow_version failed: {str(e)}" + (f" | body: {_body}" if _body else "")

    records = ver_response.json().get("result", [])
    if not records:
        return f"No sys_hub_flow_version found for flow_sys_id={flow_sys_id}"

    version_sys_id = records[0]["sys_id"]
    payload_str = records[0].get("payload", "")
    if not payload_str:
        return f"sys_hub_flow_version {version_sys_id} has an empty payload — nothing to patch"

    try:
        payload = json.loads(payload_str)
    except (ValueError, TypeError) as exc:
        return f"Failed to parse payload JSON for version {version_sys_id}: {exc}"

    trigger_instances = payload.get("triggerInstances", [])
    if not trigger_instances:
        logger.info(
            f"_patch_flow_version_trigger_type | no triggerInstances in payload — skipping | "
            f"version_sys_id={version_sys_id}"
        )
        return None

    patched_any = False
    for ti in trigger_instances:
        if ti.get("fTriggerType") != "Record":
            ti["fTriggerType"] = "Record"
            patched_any = True

    if not patched_any:
        logger.info(
            f"_patch_flow_version_trigger_type | fTriggerType already 'Record' — skipping | "
            f"version_sys_id={version_sys_id}"
        )
        return None

    try:
        patch_response = requests.patch(
            f"{config.api_url}/table/sys_hub_flow_version/{version_sys_id}",
            json={"payload": json.dumps(payload)},
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        patch_response.raise_for_status()
    except requests.RequestException as e:
        _body = e.response.text[:2000] if getattr(e, "response", None) is not None else ""
        return (
            f"PATCH sys_hub_flow_version/{version_sys_id} failed: {str(e)}"
            + (f" | body: {_body}" if _body else "")
        )

    logger.info(
        f"_patch_flow_version_trigger_type | patched fTriggerType=Record | "
        f"version_sys_id={version_sys_id}"
    )
    return None


def _build_action_instances(flow_sys_id: str, actions: Optional[List[ActionInstanceParam]]) -> list:
    """Convert ActionInstanceParam list into the actionInstances array for the PUT body."""
    if not actions:
        return []

    result = []
    for action in actions:
        result.append(
            {
                "id": uuid.uuid4().hex,
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
