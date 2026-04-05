"""
Flow Designer tools for the ServiceNow MCP server.

Creates Flow Designer flows via the internal /api/now/processflow/ API, which is the
only mechanism capable of writing trigger instances and action instances (the standard
Table API cannot write sys_hub_flow_snapshot, which has sys_policy=read).

API sequence for create_flow:
  1. POST /api/now/processflow/flow                         — create flow shell
  2. POST /api/now/processflow/versioning/create_version    — initial autosave
  3. Resolve trigger_definition_id (if not supplied)
  4. Build trigger + action instance payloads
  5. PUT  /api/now/processflow/flow                         — save trigger + action instances
  6. POST /api/now/processflow/versioning/create_version    — final Save version
  7. PATCH /api/now/table/sys_hub_flow_version              — set fTriggerType='Record' and inject choices into version payload
  8. DELETE /api/now/table/sys_hub_flow_safe_edit           — release Flow Designer edit lock
"""

import json
import logging
import time
import uuid
from typing import Any, Literal

import requests
from pydantic import BaseModel, Field, field_validator

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.utils.config import ServerConfig

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Parameter models
# ---------------------------------------------------------------------------


class TriggerInputParam(BaseModel):
    """A single trigger input name/value pair.

    All values must be strings — the ServiceNow processflow API serialises
    every input value as a string, including booleans ('0'/'1') and integers.
    """

    name: str = Field(..., description="Trigger input name (e.g. 'table', 'condition')")
    value: str = Field(..., description="Trigger input value (all values are strings)")


class TriggerInstanceParam(BaseModel):
    """Trigger configuration for a flow.

    Convenience fields 'table' and 'condition' are converted to trigger inputs
    automatically. Provide 'inputs' directly to override all trigger inputs.
    Note: 'inputs' must be a non-empty list to take effect — an empty list is
    treated the same as None (convenience fields are used instead).
    """

    type: str = Field(
        ...,
        description=(
            "Trigger type string. Common values: 'record_create', "
            "'record_create_or_update', 'record_update', 'recurrence'. "
            "Verify available types via GET /api/now/hub/triggerpicker/basic on the instance."
        ),
    )
    trigger_definition_id: str | None = Field(
        None,
        description=(
            "sys_id of the trigger type definition (sys_hub_trigger_definition — V2 trigger catalog). "
            "If omitted, create_flow will resolve it automatically from the 'type' field "
            "by querying sys_hub_trigger_type.base_trigger on the instance. "
            "Call list_trigger_types to discover available sys_ids explicitly."
        ),
    )
    name: str | None = Field(
        None,
        description=(
            "Display name for the trigger (e.g. 'Created', 'Created or Updated'). "
            "Defaults to the type value if omitted."
        ),
    )
    table: str | None = Field(
        None,
        description=(
            "Table name to trigger on (e.g. 'incident'). "
            "Convenience field — sets the 'table' trigger input. "
            "Ignored if 'inputs' is provided."
        ),
    )
    condition: str | None = Field(
        None,
        description=(
            "Encoded query condition (e.g. 'active=true'). "
            "Convenience field — sets the 'condition' trigger input. "
            "Ignored if 'inputs' is provided."
        ),
    )
    inputs: list[TriggerInputParam] | None = Field(
        None,
        description=(
            "Full trigger input list. If provided and non-empty, overrides 'table' and 'condition'. "
            "An empty list ([]) is treated as None — convenience fields are used instead. "
            "Only 'table' is mandatory for record triggers."
        ),
    )

    @field_validator("inputs")
    @classmethod
    def normalize_empty_inputs(cls, v: list[TriggerInputParam] | None) -> list[TriggerInputParam] | None:
        """Treat an explicitly empty inputs list the same as None.

        Prevents inputs=[] from silently discarding table and condition convenience fields.
        """
        if v is not None and len(v) == 0:
            return None
        return v


class ActionInputParam(BaseModel):
    """A single action input parameter with its parameter definition sys_id."""

    id: str = Field(
        ...,
        description=(
            "Parameter definition sys_id (sys_hub_action_input.sys_id). "
            "Must exactly match the action type's input parameter definition. "
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
    order: int = Field(
        1,
        description=(
            "Execution order, 1-based integer. Must be unique across all actions in the flow — "
            "duplicate order values will result in undefined rendering order in the UI."
        ),
    )
    internal_name: str | None = Field(
        None,
        description=(
            "Internal name of the action type (e.g. 'look_up_record'). "
            "Written into the PUT payload; leave None if unknown."
        ),
    )
    parent_action_type_id: str | None = Field(
        None,
        description=(
            "Parent action type sys_id. "
            "For Look Up Record: 'b93f42810b30030085c083eb37673a63'. "
            "Leave empty if unknown — the platform will resolve it."
        ),
    )
    inputs: list[ActionInputParam] = Field(
        default_factory=list,
        description=(
            "Input parameters for this action. Each input requires the exact parameter "
            "definition sys_id ('id' field) from the action type. "
            "See flow-designer-api.md memory for known parameter definition IDs."
        ),
    )


class ListTriggerTypesParams(BaseModel):
    """Parameters for list_trigger_types (no required inputs).

    Kept for interface consistency with the (config, auth_manager, params) tool signature.
    """
    pass


class TriggerTypeInfo(BaseModel):
    """One trigger type definition.

    sys_id is the sys_hub_trigger_definition sys_id (V2 trigger catalog), obtained
    by traversing sys_hub_trigger_type.base_trigger. Use this value as
    trigger_definition_id in create_flow.
    """
    sys_id: str
    name: str
    type_string: str | None = None
    """Mapped type string (e.g. 'record_create') for use as create_flow trigger.type.
    May be None for non-standard or scoped-app trigger types not in the built-in map.
    """


class ListTriggerTypesResult(BaseModel):
    """Result from list_trigger_types."""
    trigger_types: list[TriggerTypeInfo]
    message: str


class CreateFlowParams(BaseModel):
    """Parameters for creating a Flow Designer flow."""

    name: str = Field(..., description="Flow name as it will appear in Flow Designer")
    description: str | None = Field(None, description="Flow description")
    scope: str = Field(
        "global",
        description="Application scope. Use 'global' for global scope or provide a scope sys_id.",
    )
    run_as: Literal["user", "system"] = Field(
        "user",
        description="Execution context: 'user' (runs as the triggering user) or 'system'.",
    )
    access: Literal["public", "package_private", "private"] = Field(
        "public",
        description="Access level: 'public', 'package_private', or 'private'.",
    )
    flow_priority: Literal["LOW", "MEDIUM", "HIGH"] = Field(
        "MEDIUM",
        description="Flow priority: 'LOW', 'MEDIUM', or 'HIGH'.",
    )
    trigger: TriggerInstanceParam | None = Field(
        None,
        description=(
            "Trigger configuration. If omitted the flow is created as a subflow "
            "(no trigger, callable by other flows or the REST API)."
        ),
    )
    actions: list[ActionInstanceParam] = Field(
        default_factory=list,
        description=(
            "Action steps to add to the flow. Each action requires exact parameter "
            "definition sys_ids for its inputs — these are instance-specific values "
            "from sys_hub_action_input. See flow-designer-api.md memory "
            "for confirmed IDs for Look Up Record and Create Record."
        ),
    )


# ---------------------------------------------------------------------------
# Response model
# ---------------------------------------------------------------------------


class CreateFlowResponse(BaseModel):
    """Response from create_flow.

    When success=False but flow_sys_id is populated, the flow shell was partially
    created. The caller should inspect flow_sys_id to clean up or retry in Flow Designer.
    """

    success: bool = Field(..., description="Whether the flow was created successfully")
    message: str = Field(..., description="Human-readable result description")
    flow_sys_id: str | None = Field(None, description="sys_id of the created flow (sys_hub_flow)")
    flow_name: str | None = Field(None, description="Name of the created flow")
    flow_internal_name: str | None = Field(None, description="Auto-generated internal name of the flow")


class ListArtifactsParams(BaseModel):
    """Common pagination/filter parameters for flow artifacts."""

    limit: int = Field(20, ge=1, le=200, description="Maximum number of records to return")
    offset: int = Field(0, ge=0, description="Zero-based record offset")
    query: str | None = Field(
        None,
        description="Additional encoded query fragment appended with '^'",
    )
    active: bool | None = Field(
        None,
        description="Optional active-state filter",
    )


class ListFlowsParams(ListArtifactsParams):
    """Parameters for list_flows."""


class ListSubflowsParams(ListArtifactsParams):
    """Parameters for list_subflows."""


class ListActionsParams(ListArtifactsParams):
    """Parameters for list_actions."""


class GetArtifactParams(BaseModel):
    """Common lookup parameter for flow artifacts."""

    sys_id: str = Field(..., description="sys_id of the artifact")


class GetFlowParams(GetArtifactParams):
    """Parameters for get_flow."""


class GetSubflowParams(GetArtifactParams):
    """Parameters for get_subflow."""


class GetActionParams(GetArtifactParams):
    """Parameters for get_action."""


class CreateArtifactParams(BaseModel):
    """Common create parameters for flow/subflow/action artifacts."""

    name: str = Field(..., description="Artifact display name")
    description: str | None = Field(None, description="Artifact description")
    scope: str = Field("global", description="Application scope sys_id or 'global'")
    run_as: Literal["user", "system"] = Field(
        "user",
        description="Execution context",
    )
    access: Literal["public", "package_private", "private"] = Field(
        "public",
        description="Artifact access level",
    )
    flow_priority: Literal["LOW", "MEDIUM", "HIGH"] = Field(
        "MEDIUM",
        description="Default run priority",
    )


class CreateSubflowParams(CreateArtifactParams):
    """Parameters for create_subflow."""


class CreateActionParams(CreateArtifactParams):
    """Parameters for create_action."""


class UpdateArtifactParams(BaseModel):
    """Common update parameters for flow/subflow/action artifacts."""

    sys_id: str = Field(..., description="sys_id of the artifact to update")
    name: str | None = Field(None, description="Updated name")
    description: str | None = Field(None, description="Updated description")
    run_as: Literal["user", "system"] | None = Field(None, description="Updated execution context")
    access: Literal["public", "package_private", "private"] | None = Field(
        None, description="Updated access level"
    )
    flow_priority: Literal["LOW", "MEDIUM", "HIGH"] | None = Field(
        None, description="Updated run priority"
    )
    active: bool | None = Field(None, description="Updated active state")


class UpdateFlowParams(UpdateArtifactParams):
    """Parameters for update_flow."""


class UpdateSubflowParams(UpdateArtifactParams):
    """Parameters for update_subflow."""


class UpdateActionParams(UpdateArtifactParams):
    """Parameters for update_action."""


class PublishArtifactParams(BaseModel):
    """Common publish parameters for flow/subflow/action artifacts."""

    sys_id: str = Field(..., description="sys_id of the artifact to publish")
    annotation: str | None = Field("", description="Optional publish note/annotation")


class PublishFlowParams(PublishArtifactParams):
    """Parameters for publish_flow."""


class PublishSubflowParams(PublishArtifactParams):
    """Parameters for publish_subflow."""


class PublishActionParams(PublishArtifactParams):
    """Parameters for publish_action."""


# ---------------------------------------------------------------------------
# Action Type Catalog — list_action_types, list_action_type_inputs
# ---------------------------------------------------------------------------


class ListActionTypesParams(BaseModel):
    """Parameters for list_action_types."""

    query: str = Field(
        ...,
        min_length=1,
        description=(
            "Search string to filter action types by name or internal_name. "
            "Examples: 'Look Up Record', 'Create Record', 'Send Email'. "
            "Returns up to limit results matching the name CONTAINS query."
        ),
    )
    limit: int = Field(25, ge=1, le=200, description="Maximum number of results to return")


class ActionTypeSummary(BaseModel):
    """One action type from the action type catalog."""

    definition_sys_id: str = Field(
        ...,
        description=(
            "sys_hub_action_type_definition.sys_id — pass to list_action_type_inputs "
            "to get input parameter definitions."
        ),
    )
    base_sys_id: str = Field(
        ...,
        description=(
            "sys_hub_action_type_base.sys_id — use as ActionInstanceParam.action_type_sys_id "
            "when calling add_steps_to_flow or create_flow."
        ),
    )
    name: str = Field(..., description="Display name (e.g. 'Look Up Record')")
    internal_name: str | None = Field(None, description="Internal name (e.g. 'glide_record_lookup')")
    spoke: str | None = Field(None, description="Spoke name (e.g. 'ServiceNow Core')")
    description: str | None = Field(None, description="Action description")


class ListActionTypesResult(BaseModel):
    """Result from list_action_types."""

    action_types: list[ActionTypeSummary]
    message: str


class ListActionTypeInputsParams(BaseModel):
    """Parameters for list_action_type_inputs."""

    action_type_sys_id: str = Field(
        ...,
        description=(
            "sys_id of the action type definition (sys_hub_action_type_definition). "
            "Use definition_sys_id from list_action_types to find this value."
        ),
    )


class ActionTypeInput(BaseModel):
    """One input parameter definition on an action type."""

    sys_id: str = Field(..., description="sys_hub_action_input.sys_id — use as ActionInputParam.id in create_flow/add_steps_to_flow")
    name: str = Field(..., description="Input parameter logical name from the 'element' field (e.g. 'table', 'conditions') — use as the key when setting values")
    label: str = Field(..., description="Display label shown in Flow Designer")
    type: str = Field(..., description="Field type (e.g. 'table_name', 'conditions', 'string')")
    mandatory: bool = Field(False, description="Whether this input is required")
    default_value: str | None = Field(None, description="Default value if any")
    order: int = Field(0, description="Display order in Flow Designer")


class ListActionTypeInputsResult(BaseModel):
    """Result from list_action_type_inputs."""

    action_type_sys_id: str
    inputs: list[ActionTypeInput]
    message: str


class ListFlowLogicTypesParams(BaseModel):
    """Parameters for list_flow_logic_types (no required inputs)."""
    pass


class FlowLogicType(BaseModel):
    """One flow logic step type (e.g. If, Switch, For Each)."""

    sys_id: str = Field(..., description="sys_id of this logic type — use when building flow logic steps")
    name: str = Field(..., description="Display name (e.g. 'If', 'Switch', 'For Each')")
    label: str | None = Field(None, description="UI label if different from name")
    type_string: str | None = Field(None, description="Internal type string (e.g. 'if', 'switch', 'for_each')")


class ListFlowLogicTypesResult(BaseModel):
    """Result from list_flow_logic_types."""

    logic_types: list[FlowLogicType]
    message: str


class AddStepsToFlowParams(BaseModel):
    """Parameters for add_steps_to_flow."""

    flow_sys_id: str = Field(
        ...,
        description="sys_id of the existing flow to modify (sys_hub_flow). Flow must be in draft state or will be set to draft on edit.",
    )
    actions: list[ActionInstanceParam] = Field(
        default_factory=list,
        description=(
            "Action steps to append. Order values must not conflict with existing steps — "
            "use get_flow_actions to inspect current orders before calling this tool."
        ),
    )


class AddStepsToFlowResponse(BaseModel):
    """Response from add_steps_to_flow."""

    success: bool
    message: str
    flow_sys_id: str | None = None
    steps_added: int = 0


class DeleteArtifactParams(BaseModel):
    """Common delete parameter — sys_id of the artifact to delete."""

    sys_id: str = Field(..., description="sys_id of the artifact to delete")


class DeleteFlowParams(DeleteArtifactParams):
    """Parameters for delete_flow."""


class DeleteSubflowParams(DeleteArtifactParams):
    """Parameters for delete_subflow."""


class DeleteActionParams(DeleteArtifactParams):
    """Parameters for delete_action."""


class DeleteArtifactResponse(BaseModel):
    """Response from delete_* tools."""

    success: bool
    message: str
    sys_id: str | None = None


class GetFlowExecutionHistoryParams(BaseModel):
    """Parameters for get_flow_execution_history."""

    flow_sys_id: str = Field(..., description="sys_id of the flow to get execution history for")
    limit: int = Field(20, ge=1, le=100, description="Maximum number of executions to return")
    state: str | None = Field(
        None,
        description="Optional state filter. Common values: 'complete', 'error', 'running', 'cancelled'.",
    )


class FlowExecution(BaseModel):
    """Summary of one flow execution from sys_hub_flow_context."""

    sys_id: str
    name: str | None = None
    state: str | None = None
    started: str | None = None
    ended: str | None = None
    error: str | None = None


class GetFlowExecutionHistoryResult(BaseModel):
    """Result from get_flow_execution_history."""

    executions: list[FlowExecution]
    count: int
    message: str


class ArtifactSummary(BaseModel):
    """Compact artifact summary used by list_* tools."""

    sys_id: str
    name: str
    artifact_type: str
    description: str | None = None
    active: bool = False
    published: bool = False
    internal_name: str | None = None


class ListArtifactsResponse(BaseModel):
    """List response model for artifact list tools."""

    artifacts: list[ArtifactSummary]
    count: int
    message: str


class GetArtifactResponse(BaseModel):
    """Get response model for artifact read tools."""

    artifact: dict[str, Any] | None = None
    message: str


class MutationResponse(BaseModel):
    """Response model for create/update/publish operations."""

    success: bool
    message: str
    sys_id: str | None = None
    name: str | None = None


# ---------------------------------------------------------------------------
# Implementation
# ---------------------------------------------------------------------------

# Maps the user-facing type string to the display name stored in sys_hub_trigger_type.name (V1 catalog)
_TRIGGER_TYPE_NAME_MAP = {
    "record_create": "Created",
    "record_create_or_update": "Created or Updated",
    "record_update": "Updated",
    "recurrence": "Recurrence",
    "daily": "Daily",
    "weekly": "Weekly",
    "monthly": "Monthly",
    "repeat": "Repeat",
    "run_once": "Run Once",
    "email": "Inbound Email",
    "rest": "Trigger Rest",
    "service_catalog": "Service Catalog",
    "knowledge_management": "Knowledge Management",
    "sla_task": "SLA Task",
    "analytics": "Proactive Analytics",
}

_TRUNCATE_BODY_AT = 2000
_TRUNCATE_SUFFIX = "...[truncated]"


def _truncate_body(text: str) -> str:
    """Truncate an error response body with a visible marker."""
    if len(text) > _TRUNCATE_BODY_AT:
        return text[:_TRUNCATE_BODY_AT] + _TRUNCATE_SUFFIX
    return text


def _err_body(e: requests.RequestException) -> str:
    """Extract and truncate the response body from a RequestException, or ''."""
    if e.response is not None:
        return _truncate_body(e.response.text)
    return ""


# ---------------------------------------------------------------------------
# Record trigger input parameter definitions
# ---------------------------------------------------------------------------
# Each dict is a parameter definition object used by the Flow Designer renderInput
# component. Values extracted from sys_hub_flow_version.payload of a manually-created
# flow on dev296536 (2026-02-27). These are core platform config, stable within a release.
#
# Ordering note on choices vs defaultChoices:
#   'choices' uses 0-based 'order' values.
#   'defaultChoices' uses 1-based 'order' values for the same entries.
#   This mirrors the exact values observed in the instance payload and is intentional —
#   do not "fix" the 1-based defaultChoices to 0-based.


def _param(
    param_id: str,
    label: str,
    name: str,
    ptype: str,
    order: int,
    mandatory: bool = False,
    maxsize: int = 4000,
    reference: str = "",
    reference_display: str = "",
    dependent_on: str = "",
    default_value: str = "",
    default_display_value: str | None = None,
    attributes: dict[str, str] | None = None,
    choices: list[dict] | None = None,
    default_choices: list[dict] | None = None,
    extended: bool = False,
    choice_option: str = "",
    use_dependent: bool = False,
) -> dict:
    """Build a full parameter definition dict matching the Flow Designer payload schema.

    choices and default_choices are required for 'choice' type inputs so Flow Designer
    renders display labels instead of raw values. Values are confirmed from instance
    payload (sys_hub_flow_version) of a manually-created flow on dev296536 (2026-02-27).
    extended=True places the input under the Advanced Options dropdown in Flow Designer.
    choice_option="3" tells Flow Designer to render the field as a dropdown using choices.
    default_display_value is the human-readable label for the default value shown in the UI.
    """
    d = {
        "children": [],
        "id": param_id,
        "label": label,
        "name": name,
        "type": ptype,
        "order": order,
        "extended": extended,
        "mandatory": mandatory,
        "readOnly": False,
        "hint": "",
        "maxsize": maxsize,
        "reference": reference,
        "reference_display": reference_display,
        "choiceOption": choice_option,
        "table": "",
        "columnName": "",
        "defaultValue": default_value,
        "use_dependent": use_dependent,
        "fShowReferenceFinder": False,
        "local": False,
        "attributes": attributes if attributes is not None else {},
        "ref_qual": "",
        "dependent_on": dependent_on,
        "choices": choices if choices is not None else [],
        "defaultChoices": default_choices if default_choices is not None else [],
    }
    if default_display_value is not None:
        d["defaultDisplayValue"] = default_display_value
    return d


# Ordered list of all 8 standard record trigger inputs.
# Order matches Flow Designer UI: table, condition (always visible),
# then advanced options: run_when_setting, run_when_user_setting,
# run_when_user_list (conditional), run_on_extended, run_flow_in, trigger_strategy.
_RECORD_TRIGGER_INPUTS: list[dict] = [
    _param("cfca92e0c31322002841b63b12d3ae00", "Table",     "table",     "table_name", order=1,   mandatory=True,  maxsize=80,   attributes={"filter_table_source": "RECORD_WATCHER_RESTRICTED"}),
    _param("66aadea0c31322002841b63b12d3aebf", "Condition", "condition", "conditions", order=100, mandatory=False, maxsize=4000, dependent_on="table", use_dependent=True, attributes={"modelDependent": "trigger_inputs", "wants_to_add_conditions": "true"}),
    _param(
        "1e4859f3c7002300f4eba1425a9763f9", "run_when_setting", "run_when_setting", "choice",
        order=200, mandatory=False, maxsize=40, default_value="both",
        extended=True, attributes={"advanced": "true"}, choice_option="3",
        default_display_value="Run for Both Interactive and Non-Interactive Sessions",
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
        order=300, mandatory=False, maxsize=40, default_value="any",
        extended=True, attributes={"advanced": "true"}, choice_option="3",
        default_display_value="Run for any user",
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
    _param("f89c5177c7002300f4eba1425a976385", "run_when_user_list", "run_when_user_list", "glide_list", order=400, mandatory=False, maxsize=4000, reference="sys_user", reference_display="User", dependent_on="run_when_user_setting", extended=True, attributes={"advanced": "true"}),
    _param(
        "11ffbef2072200103bf10705afd300c2", "run_on_extended", "run_on_extended", "choice",
        order=500, mandatory=False, maxsize=40, default_value="false",
        extended=True, attributes={"advanced": "true"}, choice_option="3",
        default_display_value="Run only on current table",
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
        order=600, mandatory=False, maxsize=40, default_value="background",
        extended=True, attributes={"advanced": "true"}, choice_option="3",
        default_display_value="Run flow in background (default)",
        choices=[
            {"label": "Run flow in background (default)", "value": "background", "order": 0},
            {"label": "Run flow in foreground",           "value": "foreground", "order": 1},
        ],
        default_choices=[
            {"label": "Run flow in background (default)", "value": "background", "order": 1},
            {"label": "Run flow in foreground",           "value": "foreground", "order": 2},
        ],
    ),
    # "Run Trigger" — controls how often the flow fires per record lifecycle.
    # sys_id confirmed from sys_hub_trigger_input on dev296536 (2026-02-28).
    # Appears as the 8th input in saved flow version payloads; platform injects it
    # with default "once" if omitted, but including it ensures correct Advanced Options rendering.
    _param(
        "2b9def50c31132002841b63b12d3ae5b", "Run Trigger", "trigger_strategy", "choice",
        order=700, mandatory=False, maxsize=40, default_value="once",
        extended=True, attributes={"advanced": "true"}, choice_option="3",
        default_display_value="Once",
        choices=[
            {"label": "Once",                          "value": "once",           "order": 1},
            {"label": "For each unique change",        "value": "unique_changes", "order": 2},
            {"label": "Only if not currently running", "value": "always",         "order": 3},
            {"label": "For every update",              "value": "every",          "order": 4},
        ],
        default_choices=[
            {"label": "Once",                          "value": "once",           "order": 1},
            {"label": "For each unique change",        "value": "unique_changes", "order": 2},
            {"label": "Only if not currently running", "value": "always",         "order": 3},
            {"label": "For every update",              "value": "every",          "order": 4},
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
        logger.warning("_lookup_table_label | failed | table=%s | error=%s", table_name, e)
    return table_name.replace("_", " ").title()


def list_trigger_types(
    config: ServerConfig,
    auth_manager: AuthManager,
    _params: ListTriggerTypesParams,
) -> ListTriggerTypesResult:
    """
    List all available Flow Designer trigger types from sys_hub_trigger_type.

    Returns sys_hub_trigger_definition sys_ids (V2 trigger catalog) by traversing
    sys_hub_trigger_type.base_trigger. These are the correct ids for create_flow's
    trigger_definition_id field — sys_hub_trigger_instance.trigger_definition references
    sys_hub_trigger_definition, not sys_hub_trigger_type.

    Returns up to 200 trigger types. If your instance has more, use
    list_trigger_types with a direct Table API query and sysparm_offset to paginate.
    """
    try:
        response = requests.get(
            f"{config.api_url}/table/sys_hub_trigger_type",
            params={
                "sysparm_fields": "sys_id,name,internal_name,base_trigger",
                "sysparm_limit": 200,
                "sysparm_orderby": "name",
            },
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()
    except requests.RequestException as e:
        _body = _err_body(e)
        logger.error("list_trigger_types | request failed | error=%s%s", e, f" | body={_body}" if _body else "")
        return ListTriggerTypesResult(
            trigger_types=[],
            message=f"Failed to fetch trigger types: {e}" + (f" | response: {_body}" if _body else ""),
        )

    records = response.json().get("result", [])
    # Build a reverse map from display name → type string for annotation
    _name_to_type = {v: k for k, v in _TRIGGER_TYPE_NAME_MAP.items()}

    trigger_types = []
    for r in records:
        # base_trigger references sys_hub_trigger_definition — extract its sys_id.
        # The Table API returns reference fields as {value, display_value, link} objects.
        raw_base = r.get("base_trigger")
        trigger_def_id = raw_base.get("value") if isinstance(raw_base, dict) else (raw_base or None)
        if not trigger_def_id:
            logger.warning(
                "list_trigger_types | base_trigger empty for '%s', sys_hub_trigger_type.sys_id used as fallback",
                r.get("name", ""),
            )
        trigger_types.append(TriggerTypeInfo(
            sys_id=trigger_def_id or r["sys_id"],
            name=r.get("name", ""),
            type_string=r.get("internal_name") or _name_to_type.get(r.get("name", "")),
        ))

    logger.info("list_trigger_types | found %d trigger types", len(trigger_types))
    truncation_note = " (result capped at 200 — instance may have more)" if len(trigger_types) == 200 else ""
    return ListTriggerTypesResult(
        trigger_types=trigger_types,
        message=f"Found {len(trigger_types)} trigger type(s){truncation_note}. Use sys_id as trigger_definition_id in create_flow.",
    )


def _resolve_trigger_definition_id(
    config: ServerConfig,
    auth_manager: AuthManager,
    type_str: str,
) -> tuple[str | None, str | None]:
    """
    Resolve a trigger type string (e.g. 'record_create') to its sys_hub_trigger_definition
    sys_id on this instance.

    Queries sys_hub_trigger_type by display name (e.g. 'Created' for 'record_create'),
    then traverses base_trigger to get the sys_hub_trigger_definition sys_id. That is the
    correct value for triggerDefinitionId in the processflow PUT body, since
    sys_hub_trigger_instance.trigger_definition references sys_hub_trigger_definition.

    Returns (sys_hub_trigger_definition_sys_id, None) on success, or (None, error_message)
    on failure. Falls back to sys_hub_trigger_type.sys_id with a warning if base_trigger
    is absent.
    """
    display_name = _TRIGGER_TYPE_NAME_MAP.get(type_str.lower())
    if not display_name:
        # Caller may have passed the display name directly (e.g. "Created").
        # Normalise to title-case so "CREATED" or "created" also resolve correctly.
        display_name = type_str.strip().title()

    try:
        response = requests.get(
            f"{config.api_url}/table/sys_hub_trigger_type",
            params={
                "sysparm_query": f"name={display_name}",
                "sysparm_fields": "sys_id,name,base_trigger",
                "sysparm_limit": 1,
            },
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()
    except requests.RequestException as e:
        _body = _err_body(e)
        return None, f"Failed to query sys_hub_trigger_type: {e}" + (f" | body: {_body}" if _body else "")

    records = response.json().get("result", [])
    if not records:
        return None, (
            f"No trigger type found with name='{display_name}' (resolved from type='{type_str}'). "
            f"Call list_trigger_types to see available options."
        )

    rec = records[0]
    # base_trigger references sys_hub_trigger_definition — that sys_id is what the
    # processflow PUT body needs as triggerDefinitionId.
    raw_base = rec.get("base_trigger")
    trigger_def_id = raw_base.get("value") if isinstance(raw_base, dict) else (raw_base or None)

    if trigger_def_id:
        logger.info(
            "_resolve_trigger_definition_id | type=%s | name=%s | trigger_def_id=%s",
            type_str, display_name, trigger_def_id,
        )
        return trigger_def_id, None

    # base_trigger was absent — fall back to sys_hub_trigger_type.sys_id with a warning.
    fallback_id = rec["sys_id"]
    logger.warning(
        "_resolve_trigger_definition_id | base_trigger empty for type=%s name=%s, "
        "using sys_hub_trigger_type.sys_id=%s as fallback — trigger may not attach correctly",
        type_str, display_name, fallback_id,
    )
    return fallback_id, None


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
      1. POST /processflow/flow                      — create the flow shell
      2. POST /processflow/versioning/create_version — initial autosave
      3. Resolve trigger_definition_id via sys_hub_trigger_type.base_trigger → sys_hub_trigger_definition (if not supplied)
      4. Build trigger + action instance payloads
      5. PUT  /processflow/flow                      — attach trigger and actions
      6. POST /processflow/versioning/create_version — final Save version (type='Save',
         not 'Autosave', so Flow Designer reads advanced options from the saved version)
      7. PATCH sys_hub_flow_version                  — set fTriggerType='Record' in payload
         (a Business Rule overwrites it; patching the serialised payload is the only fix)
      8. DELETE sys_hub_flow_safe_edit               — release the Flow Designer edit lock

    Args:
        config: Server configuration (instance_url, auth, timeout).
        auth_manager: Authentication manager.
        params: Flow creation parameters.

    Returns:
        CreateFlowResponse with success flag, message, and flow identifiers.
        When success=False but flow_sys_id is set, a partial shell was created.
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
        _body = _err_body(e)
        logger.error("create_flow | shell POST failed | error=%s%s", e, f" | body={_body}" if _body else "")
        return CreateFlowResponse(
            success=False,
            message=f"Failed to create flow shell: {e}" + (f" | response: {_body}" if _body else ""),
        )

    shell_result = shell_response.json()
    flow_data = shell_result.get("result", {}).get("data", {})
    flow_sys_id = flow_data.get("id")
    flow_internal_name = flow_data.get("internalName")

    if not flow_sys_id:
        logger.error(
            "create_flow | shell POST succeeded but no id in response | response=%s",
            shell_result,
        )
        return CreateFlowResponse(
            success=False,
            message=(
                "Flow shell POST returned HTTP 200 but no flow id was found in the response. "
                f"Raw response: {shell_result}"
            ),
        )

    logger.info("create_flow | shell created | flow_sys_id=%s", flow_sys_id)

    # ------------------------------------------------------------------
    # Step 2: Initial autosave version
    # ------------------------------------------------------------------
    autosave_body = {
        "item_sys_id": flow_sys_id,
        "type": "Autosave",
        "annotation": "",
        "favorite": False,
    }
    version_query_params = {"sysparm_transaction_scope": "global"}

    try:
        requests.post(
            f"{processflow_base}/versioning/create_version",
            params=version_query_params,
            json=autosave_body,
            headers=headers,
            timeout=config.timeout,
        ).raise_for_status()
        logger.info("create_flow | initial autosave created | flow_sys_id=%s", flow_sys_id)
    except requests.RequestException as e:
        _body = _err_body(e)
        # Non-fatal: the shell exists and the PUT can still proceed.
        # Surface the failure in a warning so it is visible if the subsequent PUT fails.
        logger.warning(
            "create_flow | initial autosave failed (non-fatal) | flow_sys_id=%s | error=%s%s",
            flow_sys_id, e, f" | body={_body}" if _body else "",
        )

    # ------------------------------------------------------------------
    # Steps 3–4: Resolve trigger_definition_id, build payloads
    # ------------------------------------------------------------------
    # Resolve the trigger definition id into a local variable — do NOT mutate
    # params.trigger in place, as that would modify the caller's model object.
    trigger_definition_id: str | None = None
    if params.trigger:
        trigger_definition_id = params.trigger.trigger_definition_id
        if not trigger_definition_id:
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
            trigger_definition_id = resolved_id

    trigger_instances = _build_trigger_instances(
        config, auth_manager, params.trigger, flow_sys_id, trigger_definition_id
    )
    action_instances = _build_action_instances(flow_sys_id, params.actions)

    # ------------------------------------------------------------------
    # Step 5: PUT to save trigger + actions onto the flow
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
            "create_flow | PUT saved | flow_sys_id=%s | triggers=%d | actions=%d",
            flow_sys_id, len(trigger_instances), len(action_instances),
        )
    except requests.RequestException as e:
        _body = _err_body(e)
        logger.error(
            "create_flow | PUT failed | flow_sys_id=%s | error=%s%s",
            flow_sys_id, e, f" | body={_body}" if _body else "",
        )
        return CreateFlowResponse(
            success=False,
            message=(
                f"Flow shell was created (sys_id={flow_sys_id}) but the PUT to attach "
                f"trigger/actions failed: {e}. The draft shell exists in Flow Designer."
                + (f" | response: {_body}" if _body else "")
            ),
            flow_sys_id=flow_sys_id,
            flow_name=params.name,
            flow_internal_name=flow_internal_name,
        )

    # ------------------------------------------------------------------
    # Step 6: Final Save version
    # ------------------------------------------------------------------
    # Use type="Save" (not "Autosave") so Flow Designer reads the trigger's
    # advanced options from a proper saved version. Autosave versions cause
    # the advanced options dropdown to render incorrectly (5 items vs 4).
    final_version_body = {
        "item_sys_id": flow_sys_id,
        "type": "Save",
        "annotation": "",
        "favorite": False,
    }
    try:
        requests.post(
            f"{processflow_base}/versioning/create_version",
            params=version_query_params,
            json=final_version_body,
            headers=headers,
            timeout=config.timeout,
        ).raise_for_status()
        logger.info("create_flow | final Save version created | flow_sys_id=%s", flow_sys_id)
    except requests.RequestException as e:
        _body = _err_body(e)
        logger.warning(
            "create_flow | final Save version failed (non-fatal) | flow_sys_id=%s | error=%s%s",
            flow_sys_id, e, f" | body={_body}" if _body else "",
        )

    # ------------------------------------------------------------------
    # Step 7: Patch fTriggerType='Record' in the saved version payload
    # ------------------------------------------------------------------
    # The processflow PUT cannot set fTriggerType reliably — a Business Rule overwrites
    # it using a sys_hub_trigger_type (V1 catalog) field the service account cannot read.
    # Patching the serialised payload via the Table API is the only reliable fix.
    # Non-fatal: the flow functions correctly; only the trigger label in the UI is affected.
    if params.trigger and params.trigger.type in _RECORD_TRIGGER_TYPES:
        patch_err = _patch_flow_version_trigger_type(config, auth_manager, flow_sys_id)
        if patch_err:
            logger.warning(
                "create_flow | fTriggerType patch failed (non-fatal) | flow_sys_id=%s | error=%s",
                flow_sys_id, patch_err,
            )

    # ------------------------------------------------------------------
    # Step 8: Release Flow Designer edit lock
    # ------------------------------------------------------------------
    # The processflow API writes a sys_hub_flow_safe_edit record that makes the flow
    # appear locked ('being edited by <user>') in the UI. Deleting it via the Table
    # API releases the lock. GraphQL safeEdit does not work for service accounts.
    # Non-fatal: log a warning but do not fail the overall creation response.
    lock_err = _release_flow_edit_lock(config, auth_manager, flow_sys_id)
    if lock_err:
        logger.warning(
            "create_flow | safeEdit lock release failed (non-fatal) | flow_sys_id=%s | error=%s",
            flow_sys_id, lock_err,
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
# Generic artifact lifecycle tools (flow/subflow/action)
# ---------------------------------------------------------------------------

_ARTIFACT_TYPE_MAP = {
    "flow": "flow",
    "subflow": "subflow",
    "action": "action",
}


def _coerce_bool(value: Any) -> bool:
    """Normalize ServiceNow truthy string/boolean values to bool."""
    if isinstance(value, bool):
        return value
    return str(value).lower() in {"1", "true", "yes"}


def _build_artifact_query(artifact_type: str, params: ListArtifactsParams) -> str:
    """Build encoded query for sys_hub_flow artifact filtering."""
    clauses = [f"type={artifact_type}"]
    if params.active is not None:
        clauses.append(f"active={str(params.active).lower()}")
    if params.query:
        clauses.append(params.query)
    return "^".join(clauses)


def _list_artifacts(
    config: ServerConfig,
    auth_manager: AuthManager,
    artifact_type: str,
    params: ListArtifactsParams,
) -> ListArtifactsResponse:
    """List flow/subflow/action artifacts from sys_hub_flow."""
    try:
        response = requests.get(
            f"{config.api_url}/table/sys_hub_flow",
            params={
                "sysparm_query": _build_artifact_query(artifact_type, params),
                "sysparm_fields": (
                    "sys_id,name,internal_name,description,type,active,published"
                ),
                "sysparm_limit": params.limit,
                "sysparm_offset": params.offset,
                "sysparm_orderby": "name",
            },
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()
    except requests.RequestException as e:
        _body = _err_body(e)
        return ListArtifactsResponse(
            artifacts=[],
            count=0,
            message=f"Failed to list {artifact_type}s: {e}" + (f" | response: {_body}" if _body else ""),
        )

    records = response.json().get("result", [])
    artifacts = [
        ArtifactSummary(
            sys_id=r.get("sys_id", ""),
            name=r.get("name", ""),
            artifact_type=r.get("type", artifact_type),
            description=r.get("description"),
            active=_coerce_bool(r.get("active", False)),
            published=_coerce_bool(r.get("published", False)),
            internal_name=r.get("internal_name"),
        )
        for r in records
    ]
    return ListArtifactsResponse(
        artifacts=artifacts,
        count=len(artifacts),
        message=f"Found {len(artifacts)} {artifact_type}(s).",
    )


def _get_artifact(
    config: ServerConfig,
    auth_manager: AuthManager,
    artifact_type: str,
    sys_id: str,
) -> GetArtifactResponse:
    """Get one flow/subflow/action artifact from sys_hub_flow."""
    try:
        response = requests.get(
            f"{config.api_url}/table/sys_hub_flow/{sys_id}",
            params={
                "sysparm_fields": (
                    "sys_id,name,internal_name,description,type,active,published,"
                    "access,run_as,flow_priority,sys_created_on,sys_updated_on"
                )
            },
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()
    except requests.RequestException as e:
        _body = _err_body(e)
        return GetArtifactResponse(
            artifact=None,
            message=f"Failed to get {artifact_type} '{sys_id}': {e}" + (f" | response: {_body}" if _body else ""),
        )

    record = response.json().get("result", {})
    actual_type = record.get("type")
    if actual_type and actual_type != artifact_type:
        return GetArtifactResponse(
            artifact=record,
            message=(
                f"Record '{sys_id}' exists but type is '{actual_type}', not expected '{artifact_type}'."
            ),
        )

    return GetArtifactResponse(
        artifact=record,
        message=f"Retrieved {artifact_type} '{sys_id}'.",
    )


def _create_artifact(
    config: ServerConfig,
    auth_manager: AuthManager,
    artifact_type: str,
    params: CreateArtifactParams,
) -> MutationResponse:
    """Create a flow/subflow/action shell via processflow API."""
    processflow_base = f"{config.api_url}/processflow"
    body = {
        "name": params.name,
        "type": _ARTIFACT_TYPE_MAP[artifact_type],
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
        response = requests.post(
            f"{processflow_base}/flow",
            params={
                "param_only_properties": "true",
                "sysparm_transaction_scope": "global",
            },
            json=body,
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()
    except requests.RequestException as e:
        _body = _err_body(e)
        return MutationResponse(
            success=False,
            message=f"Failed to create {artifact_type}: {e}" + (f" | response: {_body}" if _body else ""),
        )

    data = response.json().get("result", {}).get("data", {})
    artifact_sys_id = data.get("id")
    if not artifact_sys_id:
        return MutationResponse(
            success=False,
            message=f"{artifact_type.capitalize()} shell create returned no sys_id.",
        )

    return MutationResponse(
        success=True,
        message=f"Created {artifact_type} '{params.name}' in draft state.",
        sys_id=artifact_sys_id,
        name=params.name,
    )


def _update_artifact(
    config: ServerConfig,
    auth_manager: AuthManager,
    artifact_type: str,
    params: UpdateArtifactParams,
) -> MutationResponse:
    """Patch mutable fields on a flow/subflow/action record."""
    patch_fields: dict[str, Any] = {}
    if params.name is not None:
        patch_fields["name"] = params.name
    if params.description is not None:
        patch_fields["description"] = params.description
    if params.run_as is not None:
        patch_fields["run_as"] = params.run_as
    if params.access is not None:
        patch_fields["access"] = params.access
    if params.flow_priority is not None:
        patch_fields["flow_priority"] = params.flow_priority
    if params.active is not None:
        patch_fields["active"] = params.active

    if not patch_fields:
        return MutationResponse(
            success=False,
            message=f"No update fields provided for {artifact_type} '{params.sys_id}'.",
            sys_id=params.sys_id,
        )

    try:
        response = requests.patch(
            f"{config.api_url}/table/sys_hub_flow/{params.sys_id}",
            json=patch_fields,
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()
    except requests.RequestException as e:
        _body = _err_body(e)
        return MutationResponse(
            success=False,
            message=f"Failed to update {artifact_type} '{params.sys_id}': {e}" + (f" | response: {_body}" if _body else ""),
            sys_id=params.sys_id,
        )

    return MutationResponse(
        success=True,
        message=f"Updated {artifact_type} '{params.sys_id}'.",
        sys_id=params.sys_id,
        name=params.name,
    )


def _publish_artifact(
    config: ServerConfig,
    auth_manager: AuthManager,
    artifact_type: str,
    params: PublishArtifactParams,
) -> MutationResponse:
    """Publish a flow/subflow/action via versioning API."""
    processflow_base = f"{config.api_url}/processflow"
    try:
        version_response = requests.post(
            f"{processflow_base}/versioning/create_version",
            params={"sysparm_transaction_scope": "global"},
            json={
                "item_sys_id": params.sys_id,
                "type": "Publish",
                "annotation": params.annotation or "",
                "favorite": False,
            },
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        version_response.raise_for_status()
    except requests.RequestException as e:
        _body = _err_body(e)
        return MutationResponse(
            success=False,
            message=f"Failed to publish {artifact_type} '{params.sys_id}': {e}" + (f" | response: {_body}" if _body else ""),
            sys_id=params.sys_id,
        )

    # Best effort state sync on the parent record.
    try:
        requests.patch(
            f"{config.api_url}/table/sys_hub_flow/{params.sys_id}",
            json={"active": True, "published": True},
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        ).raise_for_status()
    except requests.RequestException as e:
        logger.warning("_publish_artifact | record patch failed | artifact=%s | sys_id=%s | error=%s", artifact_type, params.sys_id, e)

    return MutationResponse(
        success=True,
        message=f"Published {artifact_type} '{params.sys_id}'.",
        sys_id=params.sys_id,
    )


def update_flow(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: UpdateFlowParams,
) -> MutationResponse:
    """Update a flow artifact."""
    return _update_artifact(config, auth_manager, "flow", params)


def create_subflow(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: CreateSubflowParams,
) -> MutationResponse:
    """Create a subflow artifact shell."""
    return _create_artifact(config, auth_manager, "subflow", params)


def list_subflows(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: ListSubflowsParams,
) -> ListArtifactsResponse:
    """List subflow artifacts."""
    return _list_artifacts(config, auth_manager, "subflow", params)


def get_subflow(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: GetSubflowParams,
) -> GetArtifactResponse:
    """Get a subflow artifact by sys_id."""
    return _get_artifact(config, auth_manager, "subflow", params.sys_id)


def update_subflow(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: UpdateSubflowParams,
) -> MutationResponse:
    """Update a subflow artifact."""
    return _update_artifact(config, auth_manager, "subflow", params)


def publish_subflow(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: PublishSubflowParams,
) -> MutationResponse:
    """Publish a subflow artifact."""
    return _publish_artifact(config, auth_manager, "subflow", params)


def create_action(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: CreateActionParams,
) -> MutationResponse:
    """Create a custom action artifact shell."""
    return _create_artifact(config, auth_manager, "action", params)


def list_actions(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: ListActionsParams,
) -> ListArtifactsResponse:
    """List custom action artifacts."""
    return _list_artifacts(config, auth_manager, "action", params)


def get_action(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: GetActionParams,
) -> GetArtifactResponse:
    """Get a custom action artifact by sys_id."""
    return _get_artifact(config, auth_manager, "action", params.sys_id)


def update_action(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: UpdateActionParams,
) -> MutationResponse:
    """Update a custom action artifact."""
    return _update_artifact(config, auth_manager, "action", params)


def publish_action(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: PublishActionParams,
) -> MutationResponse:
    """Publish a custom action artifact."""
    return _publish_artifact(config, auth_manager, "action", params)


def list_action_types(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: ListActionTypesParams,
) -> ListActionTypesResult:
    """
    Search the action type catalog for action types matching a name query.

    Returns both definition_sys_id (for list_action_type_inputs) and
    base_sys_id (for ActionInstanceParam.action_type_sys_id in add_steps_to_flow
    and create_flow). These are different sys_ids for the same action — both are
    needed for the full create-and-configure workflow.

    Args:
        config: Server configuration.
        auth_manager: Authentication manager.
        params: Query string and limit.

    Returns:
        ListActionTypesResult with matching action types.
    """
    try:
        response = requests.get(
            f"{config.api_url}/table/sys_hub_action_type_definition",
            params={
                "sysparm_query": f"nameCONTAINS{params.query}^ORinternal_nameCONTAINS{params.query}",
                "sysparm_fields": "sys_id,name,internal_name,action_type_base,spoke,description",
                "sysparm_display_value": "true",
                "sysparm_limit": params.limit,
            },
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()
    except requests.RequestException as e:
        _body = _err_body(e)
        logger.error(
            "list_action_types | request failed | query=%s | error=%s%s",
            params.query, e, f" | body={_body}" if _body else "",
        )
        return ListActionTypesResult(
            action_types=[],
            message=f"Failed to fetch action types: {e}" + (f" | body: {_body}" if _body else ""),
        )

    records = response.json().get("result", [])
    action_types = []
    for r in records:
        # action_type_base is a reference field; with display_value=true it comes as
        # {"value": "<sys_id>", "display_value": "<name>"} or just a plain string.
        atb = r.get("action_type_base", {})
        base_sys_id = atb.get("value", "") if isinstance(atb, dict) else str(atb or "")
        spoke_field = r.get("spoke", {})
        spoke_name = spoke_field.get("display_value") if isinstance(spoke_field, dict) else str(spoke_field or "")
        action_types.append(ActionTypeSummary(
            definition_sys_id=r["sys_id"],
            base_sys_id=base_sys_id,
            name=r.get("name", ""),
            internal_name=r.get("internal_name") or None,
            spoke=spoke_name or None,
            description=r.get("description") or None,
        ))

    logger.info("list_action_types | query=%s | found %d result(s)", params.query, len(action_types))
    return ListActionTypesResult(
        action_types=action_types,
        message=f"Found {len(action_types)} action type(s) matching '{params.query}'.",
    )


def list_action_type_inputs(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: ListActionTypeInputsParams,
) -> ListActionTypeInputsResult:
    """
    Return all input parameter definitions for a given action type.

    Queries sys_hub_action_input filtered by definition sys_id and returns
    the sys_id, name, label, type, mandatory flag, and default value for each
    input. The sys_id field maps directly to ActionInputParam.id in
    create_flow and add_steps_to_flow — eliminating the need to hardcode
    instance-specific parameter sys_ids.

    NOTE: The logical name of each input is in the 'element' field (not 'name').
    The query field is 'model=' (not 'action_type=').
    Both verified against live sys_hub_action_input records.

    Args:
        config: Server configuration.
        auth_manager: Authentication manager.
        params: Contains action_type_sys_id (definition sys_id) to query against.

    Returns:
        ListActionTypeInputsResult with the inputs list and a summary message.
    """
    try:
        response = requests.get(
            f"{config.api_url}/table/sys_hub_action_input",
            params={
                # NOTE: The query field is `model`, NOT `action_type` — verified against live instance.
                # `action_type` does not exist on sys_hub_action_input.
                "sysparm_query": f"model={params.action_type_sys_id}",
                "sysparm_fields": "sys_id,element,label,type,mandatory,default_value,order",
                "sysparm_orderby": "order",
                "sysparm_limit": 200,
            },
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()
    except requests.RequestException as e:
        _body = _err_body(e)
        logger.error(
            "list_action_type_inputs | request failed | action_type=%s | error=%s%s",
            params.action_type_sys_id, e, f" | body={_body}" if _body else "",
        )
        return ListActionTypeInputsResult(
            action_type_sys_id=params.action_type_sys_id,
            inputs=[],
            message=f"Failed to fetch action type inputs: {e}" + (f" | body: {_body}" if _body else ""),
        )

    records = response.json().get("result", [])
    inputs = [
        ActionTypeInput(
            sys_id=r["sys_id"],
            # element = logical name (e.g. "table", "conditions") — NOT the `name` field.
            # Verified against live sys_hub_action_input records.
            name=r.get("element", ""),
            label=r.get("label", ""),
            type=r.get("type", ""),
            mandatory=_coerce_bool(r.get("mandatory", False)),
            default_value=r.get("default_value") or None,
            order=int(r.get("order") or 0),
        )
        for r in records
    ]
    logger.info(
        "list_action_type_inputs | action_type=%s | found %d inputs",
        params.action_type_sys_id, len(inputs),
    )
    return ListActionTypeInputsResult(
        action_type_sys_id=params.action_type_sys_id,
        inputs=inputs,
        message=f"Found {len(inputs)} input(s) for action type {params.action_type_sys_id}.",
    )


def list_flow_logic_types(
    config: ServerConfig,
    auth_manager: AuthManager,
    _params: ListFlowLogicTypesParams,
) -> ListFlowLogicTypesResult:
    """
    List all available Flow Designer logic step types (If, Switch, For Each, etc.).

    Calls GET /api/now/processflow/flow_logic/types. The sys_id values returned
    are the identifiers needed to add flow logic steps to a flow payload.
    """
    try:
        response = requests.get(
            f"{config.api_url}/processflow/flow_logic/types",
            params={"sysparm_transaction_scope": "global"},
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()
    except requests.RequestException as e:
        _body = _err_body(e)
        logger.error("list_flow_logic_types | request failed | error=%s%s", e, f" | body={_body}" if _body else "")
        return ListFlowLogicTypesResult(
            logic_types=[],
            message=f"Failed to fetch flow logic types: {e}" + (f" | body: {_body}" if _body else ""),
        )

    data = response.json()
    # The API may return {"result": [...]} or a bare list.
    raw = data.get("result", data) if isinstance(data, dict) else data
    logic_types: list[FlowLogicType] = []
    if isinstance(raw, list):
        for t in raw:
            if isinstance(t, dict):
                logic_types.append(FlowLogicType(
                    sys_id=t.get("sys_id") or t.get("id", ""),
                    name=t.get("name") or t.get("label", ""),
                    label=t.get("label"),
                    type_string=t.get("type") or t.get("typeString"),
                ))

    logger.info("list_flow_logic_types | found %d logic type(s)", len(logic_types))
    return ListFlowLogicTypesResult(
        logic_types=logic_types,
        message=f"Found {len(logic_types)} flow logic type(s).",
    )


def add_steps_to_flow(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: AddStepsToFlowParams,
) -> AddStepsToFlowResponse:
    """
    Add action steps to an existing flow using the GET→mutate→PUT pattern.

    Sequence:
      1. GET /processflow/flow/{sys_id}       — fetch current payload
      2. Append new action instances           — built via _build_action_instances
      3. PUT /processflow/flow                 — write back modified payload
      4. POST /processflow/versioning/create_version — save a new version

    The flow must exist. Order values in params.actions must not clash with
    existing steps — use get_flow_actions first to see current orders.
    """
    processflow_base = f"{config.api_url}/processflow"
    headers = auth_manager.get_headers()

    # Step 1: GET current flow payload
    try:
        get_response = requests.get(
            f"{processflow_base}/flow/{params.flow_sys_id}",
            headers=headers,
            timeout=config.timeout,
        )
        get_response.raise_for_status()
    except requests.RequestException as e:
        _body = _err_body(e)
        logger.error("add_steps_to_flow | GET failed | flow_sys_id=%s | error=%s%s", params.flow_sys_id, e, f" | body={_body}" if _body else "")
        return AddStepsToFlowResponse(
            success=False,
            message=f"Failed to fetch flow {params.flow_sys_id}: {e}" + (f" | body: {_body}" if _body else ""),
        )

    flow_data = get_response.json().get("result", {}).get("data", {})
    if not flow_data:
        return AddStepsToFlowResponse(
            success=False,
            message=f"GET /processflow/flow/{params.flow_sys_id} returned no data.",
            flow_sys_id=params.flow_sys_id,
        )

    # Step 2: Append new action instances to existing ones
    new_instances = _build_action_instances(params.flow_sys_id, params.actions)
    flow_data["actionInstances"] = (flow_data.get("actionInstances") or []) + new_instances

    # Step 3: PUT modified payload back
    try:
        put_response = requests.put(
            f"{processflow_base}/flow",
            params={"sysparm_transaction_scope": "global"},
            json=flow_data,
            headers=headers,
            timeout=config.timeout,
        )
        put_response.raise_for_status()
    except requests.RequestException as e:
        _body = _err_body(e)
        logger.error("add_steps_to_flow | PUT failed | flow_sys_id=%s | error=%s%s", params.flow_sys_id, e, f" | body={_body}" if _body else "")
        return AddStepsToFlowResponse(
            success=False,
            message=f"Failed to update flow {params.flow_sys_id}: {e}" + (f" | body: {_body}" if _body else ""),
            flow_sys_id=params.flow_sys_id,
        )

    # Step 4: Save version (non-fatal if it fails)
    try:
        requests.post(
            f"{processflow_base}/versioning/create_version",
            params={"sysparm_transaction_scope": "global"},
            json={
                "item_sys_id": params.flow_sys_id,
                "type": "Save",
                "annotation": "",
                "favorite": False,
            },
            headers=headers,
            timeout=config.timeout,
        ).raise_for_status()
        logger.info("add_steps_to_flow | version saved | flow_sys_id=%s", params.flow_sys_id)
    except requests.RequestException as e:
        logger.warning("add_steps_to_flow | create_version failed (non-fatal) | flow_sys_id=%s | error=%s", params.flow_sys_id, e)

    logger.info("add_steps_to_flow | success | flow_sys_id=%s | steps_added=%d", params.flow_sys_id, len(params.actions))
    return AddStepsToFlowResponse(
        success=True,
        message=f"Added {len(params.actions)} step(s) to flow {params.flow_sys_id}.",
        flow_sys_id=params.flow_sys_id,
        steps_added=len(params.actions),
    )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _build_trigger_instances(
    config: ServerConfig,
    auth_manager: AuthManager,
    trigger: TriggerInstanceParam | None,
    flow_sys_id: str,
    trigger_definition_id: str | None,
) -> list[dict]:
    """Convert a TriggerInstanceParam into the triggerInstances array for the PUT body.

    For record-based triggers all 8 standard inputs are always included (with default
    values for the 6 advanced inputs). Each input carries a full 'parameter' sub-object
    required by the Flow Designer renderInput component — omitting it causes a
    TypeError crash in the UI.

    A shallow copy of each param_def dict is used to avoid aliasing the module-level
    _RECORD_TRIGGER_INPUTS entries.

    The table input additionally carries displayValue (e.g. 'Incident') and
    displayField so Flow Designer renders the correct label and data pill reference.
    Note: displayField defaults to 'number' which is correct for task-derived tables
    (incident, problem, change, etc.). For non-task tables (sys_user, cmdb_ci, custom)
    this field does not exist and Flow Designer may show an empty data pill reference.

    Args:
        trigger_definition_id: Resolved sys_id for the trigger type. Passed explicitly
            to avoid mutating the caller's TriggerInstanceParam model in place.
    """
    if trigger is None:
        return []

    # Resolve name→value from explicit inputs or convenience fields.
    # TriggerInstanceParam.normalize_empty_inputs ensures inputs=[] is treated as None.
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
        # Shallow-copy each param_def to prevent aliasing the module-level list entries.
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
                "parameter": dict(param_def),  # shallow copy to avoid aliasing module-level dict
                "scriptActive": False,
            }
            # The table input needs displayValue and displayField for Flow Designer
            # to resolve the correct table label and data pill reference.
            if name == "table" and table_label:
                input_obj["displayValue"] = table_label
                input_obj["displayField"] = "number"  # correct for task-derived tables
            # condition and run_when_setting carry displayField="" in the reference payload.
            elif name in ("condition", "run_when_setting"):
                input_obj["displayField"] = ""
            # All other non-table inputs carry displayValue="" in the reference payload.
            # Required for Flow Designer to render the Advanced Options section correctly.
            else:
                input_obj["displayValue"] = ""
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
            "remoteSysId": trigger_definition_id or "",
            "name": trigger.name or _TRIGGER_TYPE_NAME_MAP.get(trigger.type, trigger.type),
            "type": trigger.type,
            "triggerDefinitionId": trigger_definition_id,
            "fTriggerType": "Record" if trigger.type in _RECORD_TRIGGER_TYPES else "",
            "deleted": False,
            "comment": "",
            "inputs": built_inputs,
        }
    ]


def _minimal_trigger_input(name: str, value: str, param_def: dict | None = None) -> dict:
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
        "parameter": dict(p),  # shallow copy to avoid aliasing module-level dict
        "scriptActive": False,
    }


def _patch_flow_version_trigger_type(
    config: ServerConfig,
    auth_manager: AuthManager,
    flow_sys_id: str,
) -> str | None:
    """Patch the latest flow version payload to fix fTriggerType and trigger input choices.

    Two issues are corrected here:
    1. fTriggerType='Record' — the processflow PUT cannot reliably set this field because
       a Business Rule overwrites it using a sys_hub_trigger_type (V1 catalog) lookup the
       service account cannot read.
    2. choices/defaultChoices — the processflow create_version call with a minimal request
       body does not persist choice arrays into the version payload. The Flow Designer UI
       sends full trigger state when it saves; our minimal call does not. This causes the
       advanced options dropdowns to render with no options in the UI.

    Both are patched by reading the latest sys_hub_flow_version.payload, mutating the
    trigger instance data in-place, and writing the corrected payload back via Table API.

    Returns None on success, or an error message string on failure.
    """
    _MAX_ATTEMPTS = 3
    records: list = []
    for _attempt in range(1, _MAX_ATTEMPTS + 1):
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
            records = ver_response.json().get("result", [])
            if records:
                break
            logger.info(
                "_patch_flow_version_trigger_type | no version yet, retrying (%d/%d) | flow_sys_id=%s",
                _attempt, _MAX_ATTEMPTS, flow_sys_id,
            )
            if _attempt < _MAX_ATTEMPTS:
                time.sleep(1)
        except requests.RequestException as e:
            _body = _err_body(e)
            return f"GET sys_hub_flow_version failed: {e}" + (f" | body: {_body}" if _body else "")

    if not records:
        return f"No sys_hub_flow_version found for flow_sys_id={flow_sys_id} after {_MAX_ATTEMPTS} attempts"

    version_sys_id = records[0]["sys_id"]
    payload_str = records[0].get("payload")
    if payload_str is None or payload_str == "":
        return f"sys_hub_flow_version {version_sys_id} has an empty payload — nothing to patch"

    try:
        payload = json.loads(payload_str)
    except (ValueError, TypeError) as exc:
        return f"Failed to parse payload JSON for version {version_sys_id}: {exc}"

    trigger_instances = payload.get("triggerInstances", [])
    if not trigger_instances:
        logger.info(
            "_patch_flow_version_trigger_type | no triggerInstances in payload — skipping | version_sys_id=%s",
            version_sys_id,
        )
        return None

    patched_any = False
    for ti in trigger_instances:
        # ti is a dict reference into payload — mutating it updates payload in place,
        # which is then serialised below. This is intentional, not an aliasing bug.
        if ti.get("fTriggerType") != "Record":
            ti["fTriggerType"] = "Record"
            patched_any = True

        # Inject choices/defaultChoices/choiceOption/defaultDisplayValue into choice-type
        # trigger inputs that are missing them. The processflow PUT does not reliably write
        # these into the version payload — only the UI does. Without this patch Flow Designer
        # renders the advanced options dropdowns with no selectable options and no defaults.
        for inp in ti.get("inputs", []):
            param = inp.get("parameter")
            if not isinstance(param, dict) or param.get("type") != "choice":
                continue
            input_name = inp.get("name") or param.get("name", "")
            known_def = _RECORD_TRIGGER_INPUT_BY_NAME.get(input_name)
            if not known_def:
                continue
            if not param.get("choices"):
                param["choices"] = known_def["choices"]
                patched_any = True
            if not param.get("defaultChoices"):
                param["defaultChoices"] = known_def["defaultChoices"]
                patched_any = True
            if not param.get("choiceOption") and known_def.get("choiceOption"):
                param["choiceOption"] = known_def["choiceOption"]
                patched_any = True
            if "defaultDisplayValue" not in param and "defaultDisplayValue" in known_def:
                param["defaultDisplayValue"] = known_def["defaultDisplayValue"]
                patched_any = True

    if not patched_any:
        logger.info(
            "_patch_flow_version_trigger_type | payload already up-to-date — skipping | version_sys_id=%s",
            version_sys_id,
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
        _body = _err_body(e)
        return (
            f"PATCH sys_hub_flow_version/{version_sys_id} failed: {e}"
            + (f" | body: {_body}" if _body else "")
        )

    logger.info(
        "_patch_flow_version_trigger_type | patched version payload (fTriggerType + choices) | version_sys_id=%s",
        version_sys_id,
    )
    return None


def _release_flow_edit_lock(
    config: ServerConfig,
    auth_manager: AuthManager,
    flow_sys_id: str,
) -> str | None:
    """Release the Flow Designer edit lock by deleting the sys_hub_flow_safe_edit record.

    Flow Designer writes a lock record to sys_hub_flow_safe_edit when a flow is opened
    for editing (including programmatic creation via processflow). Without deletion the
    flow appears locked ('being edited by <user>') in the UI and cannot be modified.

    GraphQL safeEdit does not work for service accounts (returns data:null). Table API
    DELETE is the reliable alternative, confirmed on dev296536.

    Returns None on success, or an error message string on failure.
    """
    # Step 1: Find the lock record for this flow
    try:
        get_response = requests.get(
            f"{config.api_url}/table/sys_hub_flow_safe_edit",
            params={
                "sysparm_query": f"flow={flow_sys_id}",
                "sysparm_fields": "sys_id",
                "sysparm_limit": 1,
            },
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        get_response.raise_for_status()
    except requests.RequestException as e:
        _body = _err_body(e)
        return f"GET sys_hub_flow_safe_edit failed: {e}" + (f" | body: {_body}" if _body else "")

    records = get_response.json().get("result", [])
    if not records:
        # No lock record — nothing to delete (may already be absent)
        logger.info("_release_flow_edit_lock | no lock record found | flow_sys_id=%s", flow_sys_id)
        return None

    lock_sys_id = records[0]["sys_id"]

    # Step 2: DELETE the lock record
    try:
        del_response = requests.delete(
            f"{config.api_url}/table/sys_hub_flow_safe_edit/{lock_sys_id}",
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        del_response.raise_for_status()
    except requests.RequestException as e:
        _body = _err_body(e)
        return (
            f"DELETE sys_hub_flow_safe_edit/{lock_sys_id} failed: {e}"
            + (f" | body: {_body}" if _body else "")
        )

    logger.info(
        "_release_flow_edit_lock | lock deleted | flow_sys_id=%s | lock_sys_id=%s",
        flow_sys_id, lock_sys_id,
    )
    return None


# ---------------------------------------------------------------------------
# Phase 5 — Flow read + publish tools
# ---------------------------------------------------------------------------


class ListFlowsParams(BaseModel):
    """Parameters for listing Flow Designer flows."""

    limit: int = Field(10, description="Maximum number of records to return")
    offset: int = Field(0, description="Pagination offset")
    flow_type: str | None = Field(
        None,
        description="Filter by flow type: 'flow' or 'subflow'",
    )
    status: str | None = Field(
        None,
        description="Filter by status: 'draft', 'published', 'published_and_draft'",
    )
    scope: str | None = Field(
        None,
        description="Filter by application scope (e.g. 'global' or a scope sys_id)",
    )
    name_filter: str | None = Field(None, description="Filter by name (LIKE match)")


class GetFlowParams(BaseModel):
    """Parameters for getting a single flow's detail view."""

    flow_sys_id: str = Field(..., description="sys_id of the flow (sys_hub_flow)")


class GetFlowTriggersParams(BaseModel):
    """Parameters for getting trigger instances attached to a flow."""

    flow_sys_id: str = Field(..., description="sys_id of the flow (sys_hub_flow / sys_hub_flow_base)")


class GetFlowActionsParams(BaseModel):
    """Parameters for getting action instances in a flow."""

    flow_sys_id: str = Field(..., description="sys_id of the flow (sys_hub_flow / sys_hub_flow_base)")


class GetFlowVersionParams(BaseModel):
    """Parameters for getting a flow version record.

    Returns the latest version by default. Set published_only=True to return only
    the published version (which may differ from the latest draft).
    """

    flow_sys_id: str = Field(..., description="sys_id of the flow (sys_hub_flow)")
    published_only: bool = Field(
        False,
        description="When True, return only the published version rather than the latest",
    )


class PublishFlowParams(BaseModel):
    """Parameters for publishing (activating) a Flow Designer flow.

    Sets active=true on sys_hub_flow. The platform then marks the current
    draft version as published. The sys_hub_flow_version.published field is
    read-only via the Table API and cannot be set directly.
    """

    flow_sys_id: str = Field(..., description="sys_id of the flow to publish (sys_hub_flow)")


def list_flows(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: ListFlowsParams,
) -> dict:
    """List Flow Designer flows from sys_hub_flow with optional filters."""
    try:
        url = f"{config.instance_url}/api/now/table/sys_hub_flow"
        headers = auth_manager.get_headers()

        query_parts: list[str] = []
        if params.flow_type is not None:
            query_parts.append(f"flow_type={params.flow_type}")
        if params.status is not None:
            query_parts.append(f"status={params.status}")
        if params.scope is not None:
            query_parts.append(f"sys_scope={params.scope}")
        if params.name_filter is not None:
            query_parts.append(f"nameLIKE{params.name_filter}")

        query_params: dict = {
            "sysparm_limit": params.limit,
            "sysparm_offset": params.offset,
            "sysparm_fields": "sys_id,name,internal_name,flow_type,status,active,sys_scope,sys_created_on,sys_updated_on",
            "sysparm_display_value": "true",
        }
        if query_parts:
            query_params["sysparm_query"] = "^".join(query_parts)

        response = requests.get(url, headers=headers, params=query_params, timeout=config.timeout)
        response.raise_for_status()
        flows = response.json().get("result", [])
        return {"success": True, "flows": flows, "count": len(flows)}
    except requests.RequestException as e:
        _body = _err_body(e)
        logger.error("list_flows | error=%s%s", e, f" | body={_body}" if _body else "")
        return {"success": False, "message": f"Error listing flows: {e}" + (f" | {_body}" if _body else "")}


def get_flow(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: GetFlowParams,
) -> dict:
    """Get detail view of a single flow from sys_hub_flow."""
    try:
        url = f"{config.instance_url}/api/now/table/sys_hub_flow/{params.flow_sys_id}"
        headers = auth_manager.get_headers()
        response = requests.get(
            url,
            headers=headers,
            params={"sysparm_display_value": "true"},
            timeout=config.timeout,
        )
        response.raise_for_status()
        record = response.json().get("result", {})
        return {"success": True, "flow": record}
    except requests.RequestException as e:
        _body = _err_body(e)
        logger.error("get_flow | flow_sys_id=%s | error=%s%s", params.flow_sys_id, e, f" | body={_body}" if _body else "")
        return {"success": False, "message": f"Error getting flow: {e}" + (f" | {_body}" if _body else "")}


def get_flow_triggers(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: GetFlowTriggersParams,
) -> dict:
    """Get trigger instances for a flow from sys_hub_trigger_instance.

    sys_hub_trigger_instance.flow references sys_hub_flow_base (the parent table of
    sys_hub_flow and sys_hub_subflow), so the flow sys_id is used directly.
    """
    try:
        url = f"{config.instance_url}/api/now/table/sys_hub_trigger_instance"
        headers = auth_manager.get_headers()
        response = requests.get(
            url,
            headers=headers,
            params={
                "sysparm_query": f"flow={params.flow_sys_id}",
                "sysparm_display_value": "true",
            },
            timeout=config.timeout,
        )
        response.raise_for_status()
        triggers = response.json().get("result", [])
        return {"success": True, "flow_sys_id": params.flow_sys_id, "triggers": triggers, "count": len(triggers)}
    except requests.RequestException as e:
        _body = _err_body(e)
        logger.error("get_flow_triggers | flow_sys_id=%s | error=%s%s", params.flow_sys_id, e, f" | body={_body}" if _body else "")
        return {"success": False, "message": f"Error getting flow triggers: {e}" + (f" | {_body}" if _body else "")}


def get_flow_actions(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: GetFlowActionsParams,
) -> dict:
    """Get action instances in a flow from sys_hub_action_instance.

    sys_hub_action_instance.flow references sys_hub_flow_base (the parent table of
    sys_hub_flow and sys_hub_subflow), so the flow sys_id is used directly.
    """
    try:
        url = f"{config.instance_url}/api/now/table/sys_hub_action_instance"
        headers = auth_manager.get_headers()
        response = requests.get(
            url,
            headers=headers,
            params={
                "sysparm_query": f"flow={params.flow_sys_id}",
                "sysparm_display_value": "true",
            },
            timeout=config.timeout,
        )
        response.raise_for_status()
        actions = response.json().get("result", [])
        return {"success": True, "flow_sys_id": params.flow_sys_id, "actions": actions, "count": len(actions)}
    except requests.RequestException as e:
        _body = _err_body(e)
        logger.error("get_flow_actions | flow_sys_id=%s | error=%s%s", params.flow_sys_id, e, f" | body={_body}" if _body else "")
        return {"success": False, "message": f"Error getting flow actions: {e}" + (f" | {_body}" if _body else "")}


def get_flow_version(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: GetFlowVersionParams,
) -> dict:
    """Get the latest (or published) version record for a flow from sys_hub_flow_version.

    Note: sys_hub_flow_version.published is read-only via the Table API.
    Use publish_flow to activate a flow rather than attempting to write this field.
    """
    try:
        url = f"{config.instance_url}/api/now/table/sys_hub_flow_version"
        headers = auth_manager.get_headers()

        query = f"flow={params.flow_sys_id}"
        if params.published_only:
            query += "^published=true"

        response = requests.get(
            url,
            headers=headers,
            params={
                "sysparm_query": query + "^ORDERBYDESCsys_created_on",
                "sysparm_limit": 1,
                "sysparm_display_value": "true",
            },
            timeout=config.timeout,
        )
        response.raise_for_status()
        records = response.json().get("result", [])
        if not records:
            label = "published" if params.published_only else "latest"
            return {
                "success": False,
                "message": f"No {label} version found for flow {params.flow_sys_id}",
            }
        return {"success": True, "flow_sys_id": params.flow_sys_id, "version": records[0]}
    except requests.RequestException as e:
        _body = _err_body(e)
        logger.error("get_flow_version | flow_sys_id=%s | error=%s%s", params.flow_sys_id, e, f" | body={_body}" if _body else "")
        return {"success": False, "message": f"Error getting flow version: {e}" + (f" | {_body}" if _body else "")}


def publish_flow(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: PublishFlowParams,
) -> dict:
    """Publish (activate) a Flow Designer flow by setting active=true on sys_hub_flow.

    The sys_hub_flow_version.published field is read-only via the Table API and cannot
    be set directly. Setting active=true on the flow record triggers the platform to
    mark the current version as published.

    Note: For flows that require the FlowDesignerAPI.publishFlow() server-side method
    (e.g. complex flows with ACL constraints), use run_background_script instead with
    the script: FlowDesignerAPI.publishFlow('<flow_sys_id>');
    """
    try:
        url = f"{config.instance_url}/api/now/table/sys_hub_flow/{params.flow_sys_id}"
        headers = auth_manager.get_headers()
        headers["Content-Type"] = "application/json"
        response = requests.patch(
            url,
            json={"active": "true", "status": "published"},
            headers=headers,
            timeout=config.timeout,
        )
        response.raise_for_status()
        record = response.json().get("result", {})
        return {
            "success": True,
            "message": f"Flow {params.flow_sys_id} published (active=true, status=published)",
            "flow": record,
        }
    except requests.RequestException as e:
        _body = _err_body(e)
        logger.error("publish_flow | flow_sys_id=%s | error=%s%s", params.flow_sys_id, e, f" | body={_body}" if _body else "")
        return {
            "success": False,
            "message": (
                f"Error publishing flow: {e}"
                + (f" | {_body}" if _body else "")
                + " — If this fails due to ACL constraints, use run_background_script with: "
                f"FlowDesignerAPI.publishFlow('{params.flow_sys_id}');"
            ),
        }


def _build_action_instances(flow_sys_id: str, actions: list[ActionInstanceParam] | None) -> list[dict]:
    """Convert ActionInstanceParam list into the actionInstances array for the PUT body.

    Note on order serialisation: 'order' is cast to str to match the processflow API's
    expected type for this field. uiComponentIndex stays as int — the asymmetry is
    intentional and mirrors the instance-captured payload schema.

    Note on UUID format: both 'id' and 'uiUniqueIdentifier' use uuid4().hex (32 hex
    chars, no dashes) to match the format observed in manually-created flow payloads.
    """
    if not actions:
        return []

    result = []
    for action in actions:
        result.append(
            {
                "id": uuid.uuid4().hex,
                "flowSysId": flow_sys_id,
                "order": str(action.order),          # API expects string; see docstring
                "uiUniqueIdentifier": uuid.uuid4().hex,
                "deleted": False,
                "parent": "",
                "comment": "",
                "generationSource": "",
                "uiComponentIndex": 0,               # API expects int; see docstring
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


_ARTIFACT_TABLE_MAP: dict[str, str] = {
    "flow": "sys_hub_flow",
    "subflow": "sys_hub_flow",
    "action": "sys_hub_action_type_definition",
}


def _delete_artifact(
    config: ServerConfig,
    auth_manager: AuthManager,
    artifact_type: str,
    sys_id: str,
) -> DeleteArtifactResponse:
    """Delete a flow artifact via the Table API DELETE endpoint."""
    table = _ARTIFACT_TABLE_MAP[artifact_type]
    try:
        response = requests.delete(
            f"{config.api_url}/table/{table}/{sys_id}",
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()
    except requests.RequestException as e:
        _body = _err_body(e)
        logger.error(
            "_delete_artifact | failed | artifact_type=%s | sys_id=%s | error=%s%s",
            artifact_type, sys_id, e, f" | body={_body}" if _body else "",
        )
        return DeleteArtifactResponse(
            success=False,
            message=f"Failed to delete {artifact_type} {sys_id}: {e}" + (f" | body: {_body}" if _body else ""),
            sys_id=sys_id,
        )
    logger.info("_delete_artifact | deleted | artifact_type=%s | sys_id=%s", artifact_type, sys_id)
    return DeleteArtifactResponse(success=True, message=f"Deleted {artifact_type} {sys_id}.", sys_id=sys_id)


def delete_flow(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: DeleteFlowParams,
) -> DeleteArtifactResponse:
    """Delete a flow by sys_id. Irreversible — ensure no dependent subflows or actions reference this flow."""
    return _delete_artifact(config, auth_manager, "flow", params.sys_id)


def delete_subflow(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: DeleteSubflowParams,
) -> DeleteArtifactResponse:
    """Delete a subflow by sys_id."""
    return _delete_artifact(config, auth_manager, "subflow", params.sys_id)


def delete_action(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: DeleteActionParams,
) -> DeleteArtifactResponse:
    """Delete a custom action type by sys_id."""
    return _delete_artifact(config, auth_manager, "action", params.sys_id)


def get_flow_execution_history(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: GetFlowExecutionHistoryParams,
) -> GetFlowExecutionHistoryResult:
    """
    Return recent executions of a flow from sys_hub_flow_context.

    Each execution record includes state, start/end times, and any error
    message. Useful for debugging flows that are failing or running unexpectedly.
    """
    query = f"flow={params.flow_sys_id}^ORDERBYDESCsys_created_on"
    if params.state:
        query += f"^state={params.state}"

    try:
        response = requests.get(
            f"{config.api_url}/table/sys_hub_flow_context",
            params={
                "sysparm_query": query,
                "sysparm_fields": "sys_id,name,state,started,ended,error",
                "sysparm_limit": params.limit,
                "sysparm_display_value": "true",
            },
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()
    except requests.RequestException as e:
        _body = _err_body(e)
        logger.error(
            "get_flow_execution_history | request failed | flow_sys_id=%s | error=%s%s",
            params.flow_sys_id, e, f" | body={_body}" if _body else "",
        )
        return GetFlowExecutionHistoryResult(
            executions=[],
            count=0,
            message=f"Failed to fetch execution history for flow {params.flow_sys_id}: {e}" + (f" | body: {_body}" if _body else ""),
        )

    records = response.json().get("result", [])
    executions = [
        FlowExecution(
            sys_id=r["sys_id"],
            name=r.get("name") or None,
            state=r.get("state") or None,
            started=r.get("started") or None,
            ended=r.get("ended") or None,
            error=r.get("error") or None,
        )
        for r in records
    ]
    logger.info(
        "get_flow_execution_history | flow_sys_id=%s | found %d execution(s)",
        params.flow_sys_id, len(executions),
    )
    return GetFlowExecutionHistoryResult(
        executions=executions,
        count=len(executions),
        message=f"Found {len(executions)} execution(s) for flow {params.flow_sys_id}.",
    )
