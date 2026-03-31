from typing import Any, Callable, Dict, Tuple, Type

from servicenow_mcp.utils.approval_client import WRITE_TOOLS, wrap_write_tool

# Import all necessary tool implementation functions and params models
# (This list needs to be kept complete and up-to-date)
from servicenow_mcp.tools.catalog_optimization import (
    OptimizationRecommendationsParams,
)
from servicenow_mcp.tools.catalog_optimization import (
    get_optimization_recommendations as get_optimization_recommendations_tool,
)
from servicenow_mcp.tools.catalog_tools import (
    MoveCatalogItemsParams,
)
from servicenow_mcp.tools.catalog_tools import (
    move_catalog_items as move_catalog_items_tool,
)
from servicenow_mcp.tools.change_tools import (
    ApproveChangeParams,
    RejectChangeParams,
    SubmitChangeForApprovalParams,
)
from servicenow_mcp.tools.change_tools import (
    approve_change as approve_change_tool,
)
from servicenow_mcp.tools.change_tools import (
    reject_change as reject_change_tool,
)
from servicenow_mcp.tools.change_tools import (
    submit_change_for_approval as submit_change_for_approval_tool,
)
from servicenow_mcp.tools.changeset_tools import (
    GetCurrentScopeParams,
    GetCurrentUpdateSetParams,
    GetChangesetDetailsParams,
)
from servicenow_mcp.tools.changeset_tools import (
    get_current_scope as get_current_scope_tool,
    get_current_update_set as get_current_update_set_tool,
    get_changeset_details as get_changeset_details_tool,
)
from servicenow_mcp.tools.write_safety_tools import (
    FieldMetadataParams,
    VerifyFieldsParams,
    get_field_metadata as get_field_metadata_tool,
    verify_fields as verify_fields_tool,
)
from servicenow_mcp.tools.blueprint_tools import (
    ListTableFieldsParams,
    ListTableRelationshipsParams,
    list_table_fields as list_table_fields_tool,
    list_table_relationships as list_table_relationships_tool,
)
from servicenow_mcp.tools.user_tools import (
    GrantRoleToGroupParams,
    GrantRoleToUserParams,
    RevokeRoleFromGroupParams,
    RevokeRoleFromUserParams,
    grant_role_to_group as grant_role_to_group_tool,
    grant_role_to_user as grant_role_to_user_tool,
    revoke_role_from_group as revoke_role_from_group_tool,
    revoke_role_from_user as revoke_role_from_user_tool,
)
from servicenow_mcp.tools.sprint_tools import (
    CreateSprintParams,
    GetSprintParams,
    GetSprintSummaryParams,
    StartSprintParams,
    CloseSprintParams,
)
from servicenow_mcp.tools.sprint_tools import (
    create_sprint as create_sprint_tool,
    get_sprint as get_sprint_tool,
    get_sprint_summary as get_sprint_summary_tool,
    start_sprint as start_sprint_tool,
    close_sprint as close_sprint_tool,
)
from servicenow_mcp.tools.agile_constants import StoryIdParams
from servicenow_mcp.tools.agile_planning_tools import (
    story_breakdown as story_breakdown_tool,
    generate_acceptance_criteria as generate_acceptance_criteria_tool,
    estimate_story_points as estimate_story_points_tool,
    identify_story_risks as identify_story_risks_tool,
    generate_test_scenarios as generate_test_scenarios_tool,
)
from servicenow_mcp.tools.release_tools import (
    GetReleaseParams,
    ValidateReleaseReadinessParams,
    CompileReleaseNotesParams,
    get_release as get_release_tool,
    validate_release_readiness as validate_release_readiness_tool,
    compile_release_notes as compile_release_notes_tool,
)
from servicenow_mcp.tools.agile_reporting_tools import (
    GetBlockedWorkParams,
    GetReleaseStatusParams,
    get_blocked_work as get_blocked_work_tool,
    get_release_status as get_release_status_tool,
)
from servicenow_mcp.tools.agile_governance_tools import (
    validate_story_dependencies as validate_story_dependencies_tool,
    validate_story_testing as validate_story_testing_tool,
)
from servicenow_mcp.tools.agile_sprint_planning_tools import (
    RecommendSprintStoriesParams,
    recommend_sprint_stories as recommend_sprint_stories_tool,
)
from servicenow_mcp.tools.story_tools import (
    AssignStoriesToSprintParams,
    ArchiveStoryParams,
    MoveStoryStateParams,
)
from servicenow_mcp.tools.story_tools import (
    archive_story as archive_story_tool,
    move_story_state as move_story_state_tool,
    assign_stories_to_sprint as assign_stories_to_sprint_tool,
)
from servicenow_mcp.tools.scrum_task_tools import (
    CloseScrumTaskParams,
)
from servicenow_mcp.tools.scrum_task_tools import (
    close_scrum_task as close_scrum_task_tool,
)
from servicenow_mcp.tools.flow_tools import (
    CreateActionParams,
    CreateFlowParams,
    CreateFlowResponse,
    CreateSubflowParams,
    GetActionParams,
    GetArtifactResponse,
    GetFlowActionsParams,
    GetFlowParams,
    GetFlowTriggersParams,
    GetFlowVersionParams,
    GetSubflowParams,
    ListActionsParams,
    ListArtifactsResponse,
    ListFlowsParams,
    ListSubflowsParams,
    ListTriggerTypesParams,
    ListTriggerTypesResult,
    MutationResponse,
    PublishActionParams,
    PublishFlowParams,
    PublishSubflowParams,
    UpdateActionParams,
    UpdateFlowParams,
    UpdateSubflowParams,
)
from servicenow_mcp.tools.flow_tools import (
    create_action as create_action_tool,
    create_flow as create_flow_tool,
    create_subflow as create_subflow_tool,
    get_action as get_action_tool,
    get_flow as get_flow_tool,
    get_flow_actions as get_flow_actions_tool,
    get_flow_triggers as get_flow_triggers_tool,
    get_flow_version as get_flow_version_tool,
    get_subflow as get_subflow_tool,
    list_actions as list_actions_tool,
    list_flows as list_flows_tool,
    list_subflows as list_subflows_tool,
    list_trigger_types as list_trigger_types_tool,
    publish_action as publish_action_tool,
    publish_flow as publish_flow_tool,
    publish_subflow as publish_subflow_tool,
    update_action as update_action_tool,
    update_flow as update_flow_tool,
    update_subflow as update_subflow_tool,
)
from servicenow_mcp.tools.script_tools import (
    RunBackgroundScriptParams,
    RunBackgroundScriptResult,
)
from servicenow_mcp.tools.script_tools import (
    run_background_script as run_background_script_tool,
)
from servicenow_mcp.tools.table_tools import (
    CreateRecordParams,
    DeleteRecordParams,
    GetRecordParams,
    QueryRecordsParams,
    UpdateRecordParams,
)
from servicenow_mcp.tools.table_tools import (
    create_record as create_record_tool,
    delete_record as delete_record_tool,
    get_record as get_record_tool,
    query_records as query_records_tool,
    update_record as update_record_tool,
)
from servicenow_mcp.tools.cmdb_tools import (
    CreateCIRelationshipParams,
    GetCIImpactGraphParams,
    GetCIRelationshipsParams,
)
from servicenow_mcp.tools.cmdb_tools import (
    create_ci_relationship as create_ci_relationship_tool,
    get_ci_impact_graph as get_ci_impact_graph_tool,
    get_ci_relationships as get_ci_relationships_tool,
)
from servicenow_mcp.tools.system_tools import (
    GetCurrentUserParams,
)
from servicenow_mcp.tools.system_tools import (
    get_current_user as get_current_user_tool,
)
from servicenow_mcp.tools.changeset_tools import (
    SetCurrentScopeParams,
    SetCurrentUpdateSetParams,
    set_current_scope as set_current_scope_tool,
    set_current_update_set as set_current_update_set_tool,
)
from servicenow_mcp.tools.request_tools import (
    GetRitmVariablesParams,
)
from servicenow_mcp.tools.request_tools import (
    get_ritm_variables as get_ritm_variables_tool,
)
from servicenow_mcp.tools.integration_tools import (
    GetRestMessageParams,
    GetScriptedRestApiParams,
)
from servicenow_mcp.tools.integration_tools import (
    get_rest_message as get_rest_message_tool,
    get_scripted_rest_api as get_scripted_rest_api_tool,
)

# Define a type alias for the Pydantic models or dataclasses used for params
ParamsModel = Type[Any]  # Use Type[Any] for broader compatibility initially

# Define the structure of the tool definition tuple
ToolDefinition = Tuple[
    Callable,  # Implementation function
    ParamsModel,  # Pydantic model for parameters
    Type,  # Return type annotation (used for hints, not strictly enforced by low-level server)
    str,  # Description
    str,  # Serialization method ('str', 'json', 'dict', 'model_dump', etc.)
]


def get_tool_definitions() -> Dict[str, ToolDefinition]:
    """
    Returns a dictionary containing definitions for all available ServiceNow tools.

    This centralizes the tool definitions for use in the server implementation.

    Returns:
        Dict[str, ToolDefinition]: A dictionary mapping tool names to their definitions.
    """
    tool_definitions: Dict[str, ToolDefinition] = {
        "verify_fields": (
            verify_fields_tool,
            VerifyFieldsParams,
            dict,
            (
                "Re-fetch a ServiceNow record and compare specified fields against expected "
                "values. Call this after every write to confirm the change persisted on the "
                "live record. Returns verified fields, mismatched fields with expected vs "
                "actual values, and an all_verified flag. A non-empty mismatched list means "
                "server-side logic (Business Rule, Data Policy, Data Lookup) overrode the "
                "written value — HTTP 200 from the write tool does not guarantee persistence."
            ),
            "json",
        ),
        "get_field_metadata": (
            get_field_metadata_tool,
            FieldMetadataParams,
            dict,
            (
                "Query sys_dictionary for a field's metadata before attempting a write. "
                "Returns read_only, calculated, mandatory, max_length, internal_type, and "
                "attributes. If read_only=true or calculated=true, do not write the field "
                "directly — the write will be silently discarded. If internal_type='choice', "
                "use query_records on sys_choice (filter: name=<table>^element=<field>^inactive=false) to validate the value before writing. Automatically "
                "falls back to the 'task' parent table for task-hierarchy tables (incident, "
                "change_request, problem, sc_task)."
            ),
            "json",
        ),
        # Diagnostic escalation — use query_records directly:
        # - sys_choice (field choices): filter name=<table>^element=<field>^inactive=false
        # - sys_data_policy2 (data policies): filter applies_to=<table>
        # - dl_definition (data lookup rules): filter active=true^table=<table>
        # - sys_script (business rules): filter collection=<table>^active=true
        # - sys_ui_policy_action (UI policies): filter table=<table>^field_name=<field>
        # Introspection tools — sys_dictionary for architecture blueprints
        # Table metadata / child tables: use query_records on sys_db_object
        "list_table_fields": (
            list_table_fields_tool,
            ListTableFieldsParams,
            dict,
            (
                "Query sys_dictionary for all columns of a table. Returns field name, internal_type, "
                "reference (target table for reference fields), read_only, calculated, mandatory, "
                "default_value. Use for blueprint field lists and relationship discovery. Read-only."
            ),
            "json",
        ),
        "list_table_relationships": (
            list_table_relationships_tool,
            ListTableRelationshipsParams,
            dict,
            (
                "Derive outbound reference relationships for a table from sys_dictionary. "
                "Returns from_field and to_table for each reference. Use for relationship graphs. Read-only."
            ),
            "json",
        ),
        # Catalog Tools
        "move_catalog_items": (
            move_catalog_items_tool,
            MoveCatalogItemsParams,
            str,  # Expects JSON string
            "Move catalog items to a different category.",
            "json_dict",  # Tool returns Pydantic model
        ),
        "get_optimization_recommendations": (
            get_optimization_recommendations_tool,
            OptimizationRecommendationsParams,
            str,  # Expects JSON string
            "Get optimization recommendations for the service catalog.",
            "json",  # Tool returns list/dict
        ),
        # Request Fulfillment Tools — compound only
        # CRUD (list_requests, get_request, list_request_items, update_request_item,
        # list_sc_tasks, update_sc_task) handled by table_tools + architecture blueprint.
        "get_ritm_variables": (
            get_ritm_variables_tool,
            GetRitmVariablesParams,
            dict,
            "Get variable answers for a requested item (sc_item_option_mtom indirect join). "
            "Returns list of {name, label, value} for the RITM's submitted variable values.",
            "json",
        ),
        # Change Management Tools — compound approval workflow only.
        # CRUD (create, update, list, get, add_task, list_tasks, get_task, update_task,
        # close_task, get_cab_schedule, update_cab_details) handled by table_tools +
        # change_request architecture blueprint.
        "submit_change_for_approval": (
            submit_change_for_approval_tool,
            SubmitChangeForApprovalParams,
            str,
            "Submit a change request for approval",
            "str",  # Tool returns simple message
        ),
        "approve_change": (
            approve_change_tool,
            ApproveChangeParams,
            str,
            "Approve a change request",
            "str",  # Tool returns simple message
        ),
        "reject_change": (
            reject_change_tool,
            RejectChangeParams,
            str,
            "Reject a change request",
            "str",  # Tool returns simple message
        ),
        # Background Script Execution
        "run_background_script": (
            run_background_script_tool,
            RunBackgroundScriptParams,
            RunBackgroundScriptResult,
            (
                "Execute a JavaScript server-side script on the ServiceNow instance "
                "using the background script mechanism (sys.scripts.do — same as the "
                "Background Script module in the ServiceNow UI). Requires admin "
                "privileges. Returns direct gs.print() output and syslog entries from "
                "the execution window. The variable __MFCP_RUN_ID is injected into "
                "the script and can be included in gs.info() calls for filtering. "
                "Use this tool to run diagnostic scripts, test API calls, and debug "
                "server-side behaviour directly from the AI layer."
            ),
            "json",
        ),
        # Flow Designer Tools
        "list_trigger_types": (
            list_trigger_types_tool,
            ListTriggerTypesParams,
            ListTriggerTypesResult,
            (
                "List all available Flow Designer trigger types from sys_hub_trigger_type. "
                "Returns the sys_id and name for each trigger type on this instance. "
                "Call this before create_flow to discover valid trigger_definition_id values, "
                "or let create_flow resolve the sys_id automatically from the type string."
            ),
            "json",
        ),
        "create_flow": (
            create_flow_tool,
            CreateFlowParams,
            CreateFlowResponse,
            (
                "Create a new Flow Designer flow in ServiceNow using the internal "
                "/api/now/processflow/ API. Supports flows with a trigger (record-based "
                "or recurrence) and one or more action steps. The flow is created in "
                "draft state and must be activated manually in Flow Designer. "
                "Action inputs require exact parameter definition sys_ids — see the "
                "flow-designer-api.md memory file for known IDs for Look Up Record and "
                "Create Record."
            ),
            "json",
        ),
        "list_flows": (
            list_flows_tool,
            ListFlowsParams,
            dict,
            "List Flow Designer flows from sys_hub_flow with optional filters for type, status, scope, and name",
            "json",
        ),
        "get_flow": (
            get_flow_tool,
            GetFlowParams,
            dict,
            "Get the detail view of a single Flow Designer flow by sys_id",
            "json",
        ),
        "get_flow_triggers": (
            get_flow_triggers_tool,
            GetFlowTriggersParams,
            dict,
            "Get trigger instances attached to a flow from sys_hub_trigger_instance",
            "json",
        ),
        "get_flow_actions": (
            get_flow_actions_tool,
            GetFlowActionsParams,
            dict,
            "Get action instances in a flow from sys_hub_action_instance",
            "json",
        ),
        "get_flow_version": (
            get_flow_version_tool,
            GetFlowVersionParams,
            dict,
            "Get the latest or published version record for a flow from sys_hub_flow_version",
            "json",
        ),
        "update_flow": (
            update_flow_tool,
            UpdateFlowParams,
            MutationResponse,
            "Update a Flow Designer flow.",
            "json",
        ),
        "publish_flow": (
            publish_flow_tool,
            PublishFlowParams,
            dict,
            "Publish (activate) a Flow Designer flow by setting active=true on sys_hub_flow",
            "json",
        ),
        "create_subflow": (
            create_subflow_tool,
            CreateSubflowParams,
            MutationResponse,
            "Create a Flow Designer subflow.",
            "json",
        ),
        "list_subflows": (
            list_subflows_tool,
            ListSubflowsParams,
            ListArtifactsResponse,
            "List Flow Designer subflows.",
            "json",
        ),
        "get_subflow": (
            get_subflow_tool,
            GetSubflowParams,
            GetArtifactResponse,
            "Get a Flow Designer subflow by sys_id.",
            "json",
        ),
        "update_subflow": (
            update_subflow_tool,
            UpdateSubflowParams,
            MutationResponse,
            "Update a Flow Designer subflow.",
            "json",
        ),
        "publish_subflow": (
            publish_subflow_tool,
            PublishSubflowParams,
            MutationResponse,
            "Publish a Flow Designer subflow.",
            "json",
        ),
        "create_action": (
            create_action_tool,
            CreateActionParams,
            MutationResponse,
            "Create a Flow Designer custom action.",
            "json",
        ),
        "list_actions": (
            list_actions_tool,
            ListActionsParams,
            ListArtifactsResponse,
            "List Flow Designer custom actions.",
            "json",
        ),
        "get_action": (
            get_action_tool,
            GetActionParams,
            GetArtifactResponse,
            "Get a Flow Designer custom action by sys_id.",
            "json",
        ),
        "update_action": (
            update_action_tool,
            UpdateActionParams,
            MutationResponse,
            "Update a Flow Designer custom action.",
            "json",
        ),
        "publish_action": (
            publish_action_tool,
            PublishActionParams,
            MutationResponse,
            "Publish a Flow Designer custom action.",
            "json",
        ),
        # Changeset Management Tools
        "get_changeset_details": (
            get_changeset_details_tool,
            GetChangesetDetailsParams,
            str,  # Expects JSON string
            "Get detailed information about a specific changeset, including all associated change records (sys_update_xml).",
            "json",  # Tool returns list/dict
        ),
        "get_current_update_set": (
            get_current_update_set_tool,
            GetCurrentUpdateSetParams,
            dict,
            (
                "Return the currently active update set for the authenticated user. "
                "The response is normalized to name, sys_id, state, and is_default "
                "for downstream governance checks."
            ),
            "json",
        ),
        "get_current_scope": (
            get_current_scope_tool,
            GetCurrentScopeParams,
            dict,
            (
                "Return the currently active Next Experience application scope for the authenticated UI session. "
                "Uses the same application picker endpoint the ServiceNow UI uses."
            ),
            "json",
        ),
        # User/Group Role Tools (Phase 8)
        "grant_role_to_user": (
            grant_role_to_user_tool,
            GrantRoleToUserParams,
            dict,
            (
                "Grant a role to a user via sys_user_has_role. "
                "Resolves role_name to sys_id automatically. "
                "Never sets inherited=true — platform creates inherited records automatically."
            ),
            "json",
        ),
        "revoke_role_from_user": (
            revoke_role_from_user_tool,
            RevokeRoleFromUserParams,
            dict,
            (
                "Revoke a directly-granted role from a user. "
                "Only removes direct grants (inherited=false). "
                "Inherited records are managed by the platform and cannot be removed directly."
            ),
            "json",
        ),
        "grant_role_to_group": (
            grant_role_to_group_tool,
            GrantRoleToGroupParams,
            dict,
            (
                "Grant a role to a group via sys_group_has_role. "
                "Resolves role_name to sys_id. "
                "The platform propagates the role to group members automatically."
            ),
            "json",
        ),
        "revoke_role_from_group": (
            revoke_role_from_group_tool,
            RevokeRoleFromGroupParams,
            dict,
            (
                "Revoke a directly-granted role from a group. "
                "Only removes direct grants. Inherited records are managed by the platform."
            ),
            "json",
        ),
        # Story Management Tools (compound only)
        "archive_story": (
            archive_story_tool,
            ArchiveStoryParams,
            dict,
            (
                "Archive (cancel) a story by setting its state to Cancelled. "
                "Requires a story_id. Optional reason is recorded as a work note. "
                "Blocked if the story is already Complete or Cancelled."
            ),
            "json",
        ),
        "move_story_state": (
            move_story_state_tool,
            MoveStoryStateParams,
            dict,
            (
                "Move a story to a new lifecycle state with transition validation. "
                "Accepts friendly state names (draft, ready, in_progress, ready_for_testing, "
                "testing, complete, cancelled) or numeric values (-6, 1, 2, -7, -8, 3, 4). "
                "Enforces allowed transitions and business rules: "
                "moving to Complete requires acceptance_criteria; "
                "moving to Cancelled requires a reason."
            ),
            "json",
        ),
        # Phase 10 — Agile Quick Win
        "assign_stories_to_sprint": (
            assign_stories_to_sprint_tool,
            AssignStoriesToSprintParams,
            dict,
            (
                "Bulk-assign a list of stories to a sprint. "
                "Loops update_story per story_id setting sprint=sprint_id. "
                "Returns {assigned, failed, errors} summary."
            ),
            "json",
        ),
        # Scrum Task Management Tools (compound only)
        "close_scrum_task": (
            close_scrum_task_tool,
            CloseScrumTaskParams,
            dict,
            "Close a scrum task by setting its state to Complete (3). Optionally adds closing work notes.",
            "json",
        ),
        # Generic Table API Tools
        "query_records": (
            query_records_tool,
            QueryRecordsParams,
            dict,
            (
                "Query records from any ServiceNow table using the Table REST API. "
                "Use this when no domain-specific tool exists for the target table. "
                "Supports encoded query strings, field selection, pagination, and ordering. "
                "Returns a list of matching records. Read-only."
            ),
            "json",
        ),
        "get_record": (
            get_record_tool,
            GetRecordParams,
            dict,
            (
                "Retrieve a single record from any ServiceNow table by sys_id. "
                "Use this when no domain-specific tool exists for the target table. "
                "Optionally filter to specific fields. Read-only."
            ),
            "json",
        ),
        "create_record": (
            create_record_tool,
            CreateRecordParams,
            dict,
            (
                "Create a new record in any ServiceNow table. "
                "Use this when no domain-specific create tool exists for the target table. "
                "Pass field key-value pairs; returns the generated sys_id and full record. "
                "Use verify_fields after creation to confirm values persisted."
            ),
            "json",
        ),
        "update_record": (
            update_record_tool,
            UpdateRecordParams,
            dict,
            (
                "Update an existing record in any ServiceNow table via PATCH. "
                "Use this when no domain-specific update tool exists for the target table. "
                "Only provided fields are modified. "
                "Use verify_fields after the update to confirm values persisted."
            ),
            "json",
        ),
        "delete_record": (
            delete_record_tool,
            DeleteRecordParams,
            dict,
            (
                "Delete a record from any ServiceNow table by sys_id. "
                "This is destructive — confirm the sys_id and table before calling. "
                "Use this when no domain-specific delete tool exists for the target table."
            ),
            "json",
        ),
        # CMDB Tools — compound only; CI CRUD via table_tools + CMDB architecture blueprint
        "get_ci_relationships": (
            get_ci_relationships_tool,
            GetCIRelationshipsParams,
            dict,
            (
                "Get relationships for a CMDB CI from cmdb_rel_ci. "
                "Returns parent (CIs this one depends on), child (CIs that depend on this one), "
                "or both directions. Optionally filter by relationship type. "
                "Use to map service dependencies, infrastructure topology, and impact chains. "
                "Read-only."
            ),
            "json",
        ),
        "create_ci_relationship": (
            create_ci_relationship_tool,
            CreateCIRelationshipParams,
            dict,
            (
                "Create a relationship between two CIs in cmdb_rel_ci. "
                "Accepts parent_id, child_id, and type_name (resolved to sys_id via cmdb_rel_type). "
                "Use list_ci_relationship_types to discover valid type names."
            ),
            "json",
        ),
        "get_ci_impact_graph": (
            get_ci_impact_graph_tool,
            GetCIImpactGraphParams,
            dict,
            (
                "Traverse the CI relationship graph to build an impact map. "
                "BFS traversal through cmdb_rel_ci up to max_depth hops (default 3). "
                "Returns nodes and edges. Supports upstream, downstream, and both directions. "
                "Useful for impact analysis — e.g., which services fail if a server goes down. "
                "Read-only."
            ),
            "json",
        ),
        # System Tools
        "get_current_user": (
            get_current_user_tool,
            GetCurrentUserParams,
            dict,
            (
                "Retrieve information about the currently authenticated API user. "
                "Returns sys_id, user_name, display_name, and email. "
                "Optionally includes the user's active roles (include_roles=true, costs an extra API call). "
                "Use to confirm which account the MCP server is acting as, verify role "
                "assignments, or retrieve the sys_id for assigning records. Read-only."
            ),
            "json",
        ),
        # Sprint Management Tools
        "create_sprint": (
            create_sprint_tool,
            CreateSprintParams,
            dict,
            (
                "Create a new sprint in ServiceNow (rm_sprint_2). "
                "Requires a name, start_date, and end_date (YYYY-MM-DD). "
                "Optionally attach to a release via release_id and set a sprint goal. "
                "Sprint is created in Planning state. "
                "To add stories to the sprint use update_story with the sprint field."
            ),
            "json",
        ),
        "get_sprint": (
            get_sprint_tool,
            GetSprintParams,
            dict,
            (
                "Retrieve a single sprint by sys_id, sprint number (e.g. SPRINT0001234), "
                "or sprint name (e.g. 'Sprint 14'). "
                "Returns full sprint record including state, dates, goal, and release. "
                "Read-only."
            ),
            "json",
        ),
        "get_sprint_summary": (
            get_sprint_summary_tool,
            GetSprintSummaryParams,
            dict,
            (
                "Return an aggregated summary for a sprint: story counts grouped by state "
                "(done, in_progress, backlog, cancelled) and story point totals "
                "(total, completed, remaining). Includes a completion_forecast signal. "
                "Set include_stories=true to also return the full story list. "
                "Read-only."
            ),
            "json",
        ),
        "start_sprint": (
            start_sprint_tool,
            StartSprintParams,
            dict,
            (
                "Transition a sprint from Planning to Active state. "
                "Validates the sprint is in Planning state before patching. "
                "Returns an open story count as an informational warning. "
                "Requires the sprint sys_id."
            ),
            "json",
        ),
        "close_sprint": (
            close_sprint_tool,
            CloseSprintParams,
            dict,
            (
                "Transition a sprint from Active to Completed state. "
                "Fails with OPEN_STORIES_BLOCKING_CLOSE if open stories remain (use force=True to override). "
                "Returns the count of stories carried over open at close time."
            ),
            "json",
        ),
        # Agile Planning Tools (read-only context gathering)
        "story_breakdown": (
            story_breakdown_tool,
            StoryIdParams,
            dict,
            (
                "Gather all context needed to break a user story into scrum tasks. "
                "Returns the story, its epic, existing tasks, similar stories from the same epic, "
                "a task type guide, and AI analysis hints. Read-only."
            ),
            "json",
        ),
        "generate_acceptance_criteria": (
            generate_acceptance_criteria_tool,
            StoryIdParams,
            dict,
            (
                "Gather context for writing acceptance criteria for a story. "
                "Returns the story, its epic, any existing AC, and AC from similar stories "
                "in the same epic as calibration examples. Read-only."
            ),
            "json",
        ),
        "estimate_story_points": (
            estimate_story_points_tool,
            StoryIdParams,
            dict,
            (
                "Gather context for estimating story points. "
                "Returns the story, its epic, similar completed stories with their point values, "
                "the Fibonacci scale, and calibration hints. Read-only."
            ),
            "json",
        ),
        "identify_story_risks": (
            identify_story_risks_tool,
            StoryIdParams,
            dict,
            (
                "Surface open blockers and risk signals for a story. "
                "Queries m2m_story_dependencies for prerequisites not yet done or cancelled. "
                "Returns open blocker count, blocker details, and risk analysis hints. Read-only."
            ),
            "json",
        ),
        "generate_test_scenarios": (
            generate_test_scenarios_tool,
            StoryIdParams,
            dict,
            (
                "Gather context for generating test scenarios for a story. "
                "Returns the story, its epic, existing testing tasks, and structured hints "
                "for happy path, edge cases, error paths, and integration points. Read-only."
            ),
            "json",
        ),
        # Release Management Tools
        "get_release": (
            get_release_tool,
            GetReleaseParams,
            dict,
            (
                "Retrieve a single release by sys_id, release number (e.g. REL0001234), or name. "
                "Attempts a direct sys_id lookup first; falls back to number/name query. Read-only."
            ),
            "json",
        ),
        "validate_release_readiness": (
            validate_release_readiness_tool,
            ValidateReleaseReadinessParams,
            dict,
            (
                "Run a readiness checklist against a release. "
                "Checks: all stories done, acceptance criteria populated, all sprints completed, "
                "planned date set, and no in-progress stories. "
                "Returns ready: true/false and a list of check results."
            ),
            "json",
        ),
        "compile_release_notes": (
            compile_release_notes_tool,
            CompileReleaseNotesParams,
            dict,
            (
                "Compile release notes from completed stories in a release, grouped by epic. "
                "Returns story count, total points, and stories organised by epic title. Read-only."
            ),
            "json",
        ),
        # Agile Reporting Tools
        "get_blocked_work": (
            get_blocked_work_tool,
            GetBlockedWorkParams,
            dict,
            (
                "Return stories that are blocked by unfinished prerequisites. "
                "Queries m2m_story_dependencies and filters to open blockers. "
                "Optionally restrict to a single sprint via sprint_id. Read-only."
            ),
            "json",
        ),
        "get_release_status": (
            get_release_status_tool,
            GetReleaseStatusParams,
            dict,
            (
                "Return a status dashboard for a release: sprint counts by state, story counts "
                "by state, point totals, and an overall_status signal "
                "(not_started / on_track / at_risk / complete). Read-only."
            ),
            "json",
        ),
        # Agile Sprint Planning Tools
        "recommend_sprint_stories": (
            recommend_sprint_stories_tool,
            RecommendSprintStoriesParams,
            dict,
            (
                "Recommend backlog stories for a sprint using a multi-factor scoring algorithm. "
                "Scores each candidate by priority (Critical=50, High=40, Moderate=30, Low=20, Planning=10), "
                "optional sprint objective keyword alignment (+3 per keyword match, max +10), "
                "and capacity fit (story points vs. sprint capacity). "
                "Performs a single batch dependency check across all candidates. "
                "Returns three lists: recommended (clear dependencies, fits capacity), "
                "blocked (has open prerequisite stories), and over_capacity (would exceed capacity). "
                "Read-only."
            ),
            "json",
        ),
        # Agile Governance Tools
        "validate_story_dependencies": (
            validate_story_dependencies_tool,
            StoryIdParams,
            dict,
            (
                "Check that all prerequisite stories for a given story are Complete or Cancelled. "
                "Returns all_dependencies_met: bool and a list of open_blockers with number, title, "
                "and state. A story with no dependencies returns all_dependencies_met: true. Read-only."
            ),
            "json",
        ),
        "validate_story_testing": (
            validate_story_testing_tool,
            StoryIdParams,
            dict,
            (
                "Check that at least one testing task (rm_scrum_task type=4) exists for the story "
                "and all testing tasks are in a done state (Complete or Cancelled). "
                "Returns testing_complete: bool, total_testing_tasks: int, and incomplete_tasks list. "
                "Read-only."
            ),
            "json",
        ),
        # Integration Platform Tools — compound only; CRUD via table_tools + integration architecture blueprint
        "get_rest_message": (
            get_rest_message_tool,
            GetRestMessageParams,
            dict,
            "Get a single outbound REST message with all its HTTP methods (sys_rest_message_fn). "
            "Provide message_name or message_sys_id. Returns the message record and its method list.",
            "json",
        ),
        "get_scripted_rest_api": (
            get_scripted_rest_api_tool,
            GetScriptedRestApiParams,
            dict,
            "Get a Scripted REST API with all its resources/operations (sys_ws_definition + sys_ws_operation). "
            "Provide api_name or api_sys_id. http_method on operations is UPPERCASE.",
            "json",
        ),
        # Update Set activation
        "set_current_update_set": (
            set_current_update_set_tool,
            SetCurrentUpdateSetParams,
            dict,
            (
                "Activate an update set as the current working set for the authenticated user. "
                "Validates the update set is in 'in progress' state, then sets it as current "
                "so all subsequent platform changes are captured in it. "
                "Call this before scripting or configuration work to ensure changes land in the "
                "correct update set. Use query_records on sys_update_set to find available update set sys_ids."
            ),
            "json",
        ),
        "set_current_scope": (
            set_current_scope_tool,
            SetCurrentScopeParams,
            dict,
            (
                "Set the currently active Next Experience application scope for the authenticated UI session "
                "using the platform application picker endpoint. Requires the target app_id."
            ),
            "json",
        ),
    }

    # Apply the workbench approval gate to all write tools.
    # No-op when WORKBENCH_URL is not set (direct CLI usage).
    for name in WRITE_TOOLS:
        if name in tool_definitions:
            func, params_model, return_type, description, serialization = tool_definitions[name]
            tool_definitions[name] = (wrap_write_tool(name, func), params_model, return_type, description, serialization)

    return tool_definitions
