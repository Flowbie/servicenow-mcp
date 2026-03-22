from typing import Any, Callable, Dict, Tuple, Type

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
from servicenow_mcp.tools.catalog_variables import (
    CreateCatalogItemVariableParams,
    ListCatalogItemVariablesParams,
    UpdateCatalogItemVariableParams,
)
from servicenow_mcp.tools.catalog_variables import (
    create_catalog_item_variable as create_catalog_item_variable_tool,
)
from servicenow_mcp.tools.catalog_variables import (
    list_catalog_item_variables as list_catalog_item_variables_tool,
)
from servicenow_mcp.tools.catalog_variables import (
    update_catalog_item_variable as update_catalog_item_variable_tool,
)
from servicenow_mcp.tools.change_tools import (
    AddChangeTaskParams,
    ApproveChangeParams,
    CloseChangeTaskParams,
    CreateChangeRequestParams,
    GetCabScheduleParams,
    GetChangeRequestDetailsParams,
    GetChangeTaskParams,
    ListChangeRequestsParams,
    ListChangeTasksParams,
    RejectChangeParams,
    SubmitChangeForApprovalParams,
    UpdateCabDetailsParams,
    UpdateChangeRequestParams,
    UpdateChangeTaskParams,
)
from servicenow_mcp.tools.change_tools import (
    add_change_task as add_change_task_tool,
)
from servicenow_mcp.tools.change_tools import (
    approve_change as approve_change_tool,
)
from servicenow_mcp.tools.change_tools import (
    create_change_request as create_change_request_tool,
)
from servicenow_mcp.tools.change_tools import (
    get_change_request_details as get_change_request_details_tool,
)
from servicenow_mcp.tools.change_tools import (
    list_change_requests as list_change_requests_tool,
)
from servicenow_mcp.tools.change_tools import (
    reject_change as reject_change_tool,
)
from servicenow_mcp.tools.change_tools import (
    submit_change_for_approval as submit_change_for_approval_tool,
)
from servicenow_mcp.tools.change_tools import (
    update_change_request as update_change_request_tool,
)
from servicenow_mcp.tools.change_tools import (
    list_change_tasks as list_change_tasks_tool,
)
from servicenow_mcp.tools.change_tools import (
    get_change_task as get_change_task_tool,
)
from servicenow_mcp.tools.change_tools import (
    update_change_task as update_change_task_tool,
)
from servicenow_mcp.tools.change_tools import (
    close_change_task as close_change_task_tool,
)
from servicenow_mcp.tools.change_tools import (
    get_cab_schedule as get_cab_schedule_tool,
)
from servicenow_mcp.tools.change_tools import (
    update_cab_details as update_cab_details_tool,
)
from servicenow_mcp.tools.changeset_tools import (
    GetChangesetDetailsParams,
)
from servicenow_mcp.tools.changeset_tools import (
    get_changeset_details as get_changeset_details_tool,
)
from servicenow_mcp.tools.write_safety_tools import (
    BusinessRulesParams,
    DataLookupRulesParams,
    DataPoliciesParams,
    FieldChoicesParams,
    FieldMetadataParams,
    UIPoliciesParams,
    VerifyFieldsParams,
    get_business_rules as get_business_rules_tool,
    get_data_lookup_rules as get_data_lookup_rules_tool,
    get_data_policies as get_data_policies_tool,
    get_field_choices as get_field_choices_tool,
    get_field_metadata as get_field_metadata_tool,
    get_ui_policies as get_ui_policies_tool,
    verify_fields as verify_fields_tool,
)
from servicenow_mcp.tools.blueprint_tools import (
    GetTableMetadataParams,
    ListTableFieldsParams,
    ListTableRelationshipsParams,
    ListChildTablesParams,
    get_table_metadata as get_table_metadata_tool,
    list_table_fields as list_table_fields_tool,
    list_table_relationships as list_table_relationships_tool,
    list_child_tables as list_child_tables_tool,
)
from servicenow_mcp.tools.user_tools import (
    GrantRoleToGroupParams,
    GrantRoleToUserParams,
    ListGroupRolesParams,
    ListUserRolesParams,
    RevokeRoleFromGroupParams,
    RevokeRoleFromUserParams,
    grant_role_to_group as grant_role_to_group_tool,
    grant_role_to_user as grant_role_to_user_tool,
    list_group_roles as list_group_roles_tool,
    list_user_roles as list_user_roles_tool,
    revoke_role_from_group as revoke_role_from_group_tool,
    revoke_role_from_user as revoke_role_from_user_tool,
)
from servicenow_mcp.tools.sprint_tools import (
    CreateSprintParams,
    GetSprintParams,
    GetSprintSummaryParams,
    ListSprintsParams,
    StartSprintParams,
    CloseSprintParams,
)
from servicenow_mcp.tools.sprint_tools import (
    create_sprint as create_sprint_tool,
    get_sprint as get_sprint_tool,
    get_sprint_summary as get_sprint_summary_tool,
    list_sprints as list_sprints_tool,
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
    CreateReleaseParams,
    GetReleaseParams,
    ListReleasesParams,
    ValidateReleaseReadinessParams,
    CompileReleaseNotesParams,
    create_release as create_release_tool,
    get_release as get_release_tool,
    list_releases as list_releases_tool,
    validate_release_readiness as validate_release_readiness_tool,
    compile_release_notes as compile_release_notes_tool,
)
from servicenow_mcp.tools.agile_reporting_tools import (
    GetMyWorkParams,
    GetBlockedWorkParams,
    GetReleaseStatusParams,
    get_my_work as get_my_work_tool,
    get_blocked_work as get_blocked_work_tool,
    get_release_status as get_release_status_tool,
)
from servicenow_mcp.tools.agile_governance_tools import (
    validate_story_dependencies as validate_story_dependencies_tool,
    validate_story_testing as validate_story_testing_tool,
    validate_story_promotion_instructions as validate_story_promotion_instructions_tool,
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
    CreateCIParams,
    CreateCIRelationshipParams,
    DeleteCIRelationshipParams,
    GetCIImpactGraphParams,
    GetCIParams,
    GetCIRelationshipsParams,
    ListCIParams,
    ListCIRelationshipTypesParams,
    SearchCIParams,
    UpdateCIParams,
)
from servicenow_mcp.tools.cmdb_tools import (
    create_ci as create_ci_tool,
    create_ci_relationship as create_ci_relationship_tool,
    delete_ci_relationship as delete_ci_relationship_tool,
    get_ci as get_ci_tool,
    get_ci_impact_graph as get_ci_impact_graph_tool,
    get_ci_relationships as get_ci_relationships_tool,
    list_ci as list_ci_tool,
    list_ci_relationship_types as list_ci_relationship_types_tool,
    search_ci as search_ci_tool,
    update_ci as update_ci_tool,
)
from servicenow_mcp.tools.system_tools import (
    GetCurrentUserParams,
    GetSystemPropertiesParams,
)
from servicenow_mcp.tools.system_tools import (
    get_current_user as get_current_user_tool,
    get_system_properties as get_system_properties_tool,
)
from servicenow_mcp.tools.changeset_tools import (
    SetCurrentUpdateSetParams,
    set_current_update_set as set_current_update_set_tool,
)
from servicenow_mcp.tools.request_tools import (
    GetRitmVariablesParams,
)
from servicenow_mcp.tools.request_tools import (
    get_ritm_variables as get_ritm_variables_tool,
)
from servicenow_mcp.tools.integration_tools import (
    ListRestMessagesParams,
    GetRestMessageParams,
    CreateRestMessageParams,
    AddHttpMethodParams,
    ListScriptedRestApisParams,
    GetScriptedRestApiParams,
    CreateScriptedRestApiParams,
    AddRestResourceParams,
    ListImportSetsParams,
    ListMidServersParams,
    GetMidServerStatusParams,
    ListTransformMapsParams,
    CreateTransformMapParams,
    RunTransformParams,
    RunImportParams,
)
from servicenow_mcp.tools.integration_tools import (
    list_rest_messages as list_rest_messages_tool,
    get_rest_message as get_rest_message_tool,
    create_rest_message as create_rest_message_tool,
    add_http_method as add_http_method_tool,
    list_scripted_rest_apis as list_scripted_rest_apis_tool,
    get_scripted_rest_api as get_scripted_rest_api_tool,
    create_scripted_rest_api as create_scripted_rest_api_tool,
    add_rest_resource as add_rest_resource_tool,
    list_import_sets as list_import_sets_tool,
    list_mid_servers as list_mid_servers_tool,
    get_mid_server_status as get_mid_server_status_tool,
    list_transform_maps as list_transform_maps_tool,
    create_transform_map as create_transform_map_tool,
    run_transform as run_transform_tool,
    run_import as run_import_tool,
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
                "call get_field_choices to validate the value before writing. Automatically "
                "falls back to the 'task' parent table for task-hierarchy tables (incident, "
                "change_request, problem, sc_task)."
            ),
            "json",
        ),
        "get_field_choices": (
            get_field_choices_tool,
            FieldChoicesParams,
            dict,
            (
                "Query sys_choice for the valid values of a choice field. Returns a list of "
                "{value, label, inactive} entries. Use the 'value' (not the label) when "
                "writing the field. If a user provides a label (e.g., 'High'), find the "
                "matching 'value' here before calling the write tool. If choices_found=False, "
                "retry with table='task' — choice entries for task-hierarchy fields are "
                "stored under the 'task' table in sys_choice."
            ),
            "json",
        ),
        # Diagnostic escalation tools — called after a verify_fields mismatch
        # to identify which server-side mechanism overrode the write.
        # Investigation order: get_data_policies → get_data_lookup_rules →
        # get_business_rules → get_ui_policies (client-side only, never the cause).
        "get_data_lookup_rules": (
            get_data_lookup_rules_tool,
            DataLookupRulesParams,
            dict,
            (
                "Query dl_definition for active Data Lookup rules that set fields on a table. "
                "Data Lookup rules execute server-side after every insert or update and "
                "silently override written values — the primary mechanism behind derived "
                "fields like incident.priority (driven by impact and urgency). "
                "Also use this as the instance verification step for FIELD_CONTROL_GRAPH.md "
                "entries with mechanism='data_lookup'. "
                "Set output_field to filter to a specific field (e.g., 'priority')."
            ),
            "json",
        ),
        "get_business_rules": (
            get_business_rules_tool,
            BusinessRulesParams,
            dict,
            (
                "Query sys_script for active Business Rules on a table whose script body "
                "references a field. Business Rules with 'before' or 'after' timing run "
                "in the same transaction as the API write and can silently override field "
                "values. Returns rule name, timing, insert/update triggers, condition, and "
                "a 500-character script preview. Results use substring match — review "
                "script_preview to confirm whether the rule sets or merely reads the field."
            ),
            "json",
        ),
        "get_data_policies": (
            get_data_policies_tool,
            DataPoliciesParams,
            dict,
            (
                "Query sys_data_policy_rule for active Data Policy constraints on a field. "
                "Data Policies (sys_data_policy2) are SERVER-SIDE enforced — a read_only=True "
                "rule discards API writes silently regardless of how the request is made. "
                "This is distinct from UI Policies, which are client-side only. "
                "Call this as Step 2 in diagnostic escalation (after get_field_metadata, "
                "before get_data_lookup_rules). A read_only=True result here is definitive: "
                "the field cannot be written via the API without modifying the policy."
            ),
            "json",
        ),
        "get_ui_policies": (
            get_ui_policies_tool,
            UIPoliciesParams,
            dict,
            (
                "Query sys_ui_policy_action for active UI Policy constraints on a field. "
                "IMPORTANT: UI Policies are CLIENT-SIDE ONLY. They enforce field visibility, "
                "mandatory status, and read-only state in the browser form but have NO effect "
                "on REST API writes. api_relevant is always False in the result. "
                "Call this as the final diagnostic step to provide supplemental context "
                "about form behaviour. Never cite a UI Policy as the cause of an API write "
                "mismatch — if only a UI policy is found, continue searching for the real cause."
            ),
            "json",
        ),
        # Introspection tools — sys_db_object / sys_dictionary for architecture blueprints
        "get_table_metadata": (
            get_table_metadata_tool,
            GetTableMetadataParams,
            dict,
            (
                "Query sys_db_object for a table's metadata: label, extends (parent table), scope. "
                "Use for architecture blueprints and table hierarchy. Read-only."
            ),
            "json",
        ),
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
        "list_child_tables": (
            list_child_tables_tool,
            ListChildTablesParams,
            dict,
            (
                "Query sys_db_object for tables that extend (super_class) a parent table. "
                "Returns list of child table names. Use for table hierarchy in blueprints. Read-only."
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
        # Catalog Variables
        "create_catalog_item_variable": (
            create_catalog_item_variable_tool,
            CreateCatalogItemVariableParams,
            Dict[str, Any],  # Expects dict
            "Create a new catalog item variable",
            "dict",  # Tool returns Pydantic model
        ),
        "list_catalog_item_variables": (
            list_catalog_item_variables_tool,
            ListCatalogItemVariablesParams,
            Dict[str, Any],  # Expects dict
            "List catalog item variables",
            "dict",  # Tool returns Pydantic model
        ),
        "update_catalog_item_variable": (
            update_catalog_item_variable_tool,
            UpdateCatalogItemVariableParams,
            Dict[str, Any],  # Expects dict
            "Update a catalog item variable",
            "dict",  # Tool returns Pydantic model
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
        # Change Management Tools
        "create_change_request": (
            create_change_request_tool,
            CreateChangeRequestParams,
            str,
            "Create a new change request in ServiceNow",
            "str",
        ),
        "update_change_request": (
            update_change_request_tool,
            UpdateChangeRequestParams,
            str,
            "Update an existing change request in ServiceNow",
            "str",
        ),
        "list_change_requests": (
            list_change_requests_tool,
            ListChangeRequestsParams,
            str,  # Expects JSON string
            "List change requests from ServiceNow",
            "json",  # Tool returns list/dict
        ),
        "get_change_request_details": (
            get_change_request_details_tool,
            GetChangeRequestDetailsParams,
            str,  # Expects JSON string
            "Get detailed information about a specific change request",
            "json",  # Tool returns list/dict
        ),
        "add_change_task": (
            add_change_task_tool,
            AddChangeTaskParams,
            str,  # Expects JSON string
            "Add a task to a change request",
            "json_dict",  # Tool returns Pydantic model
        ),
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
        "list_change_tasks": (
            list_change_tasks_tool,
            ListChangeTasksParams,
            str,
            "List tasks for a specific change request",
            "json",
        ),
        "get_change_task": (
            get_change_task_tool,
            GetChangeTaskParams,
            str,
            "Get details of a single change task by sys_id",
            "json",
        ),
        "update_change_task": (
            update_change_task_tool,
            UpdateChangeTaskParams,
            str,
            "Update state, assignment, or close_code on a change task",
            "json",
        ),
        "close_change_task": (
            close_change_task_tool,
            CloseChangeTaskParams,
            str,
            "Close a change task (requires state and close_code)",
            "json",
        ),
        "get_cab_schedule": (
            get_cab_schedule_tool,
            GetCabScheduleParams,
            str,
            "Read CAB schedule (cab_required, cab_date_time) from a change request",
            "json",
        ),
        "update_cab_details": (
            update_cab_details_tool,
            UpdateCabDetailsParams,
            str,
            "Update CAB details (cab_required, cab_date_time) on a change request",
            "json",
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
        "list_user_roles": (
            list_user_roles_tool,
            ListUserRolesParams,
            dict,
            (
                "List roles granted to a user from sys_user_has_role. "
                "Optionally filter to direct grants only (include_inherited=false). "
                "Read-only."
            ),
            "json",
        ),
        "list_group_roles": (
            list_group_roles_tool,
            ListGroupRolesParams,
            dict,
            (
                "List roles granted to a group from sys_group_has_role. "
                "Optionally filter to direct grants only (include_inherited=false). "
                "Read-only."
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
        # CMDB Tools
        "list_ci": (
            list_ci_tool,
            ListCIParams,
            dict,
            (
                "List Configuration Items from the ServiceNow CMDB. "
                "Specify ci_class to target a type (e.g., cmdb_ci_server, cmdb_ci_appl). "
                "Supports encoded query filtering (e.g., install_status=1), field selection, "
                "and pagination. Returns count and list of CI records. Read-only."
            ),
            "json",
        ),
        "get_ci": (
            get_ci_tool,
            GetCIParams,
            dict,
            (
                "Retrieve a single CMDB Configuration Item by sys_id. "
                "Specify the exact ci_class subtype (e.g., cmdb_ci_server) for complete "
                "class-specific field data. Read-only."
            ),
            "json",
        ),
        "create_ci": (
            create_ci_tool,
            CreateCIParams,
            dict,
            (
                "Create a new Configuration Item in the ServiceNow CMDB. "
                "Always use the most specific CI subclass (e.g., cmdb_ci_server). "
                "Returns the sys_id and full record of the created CI. "
                "Use verify_fields after creation to confirm attribute values."
            ),
            "json",
        ),
        "update_ci": (
            update_ci_tool,
            UpdateCIParams,
            dict,
            (
                "Update an existing CMDB Configuration Item via PATCH. "
                "Only provided fields are modified. "
                "Use verify_fields after the update — Discovery and other mechanisms "
                "may override written values."
            ),
            "json",
        ),
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
        # CMDB Phase 7 enhancements
        "search_ci": (
            search_ci_tool,
            SearchCIParams,
            dict,
            (
                "Search CMDB Configuration Items with flexible filters. "
                "Filter by ci_class, name (substring), install_status, and environment. "
                "Returns matching CIs with display values. Read-only."
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
        "delete_ci_relationship": (
            delete_ci_relationship_tool,
            DeleteCIRelationshipParams,
            dict,
            (
                "Delete a CI relationship record from cmdb_rel_ci by sys_id. "
                "Use get_ci_relationships to find the relationship sys_id before deleting."
            ),
            "json",
        ),
        "list_ci_relationship_types": (
            list_ci_relationship_types_tool,
            ListCIRelationshipTypesParams,
            dict,
            (
                "List available CI relationship types from cmdb_rel_type. "
                "Returns sys_id and name (outbound::inbound format) for each type. "
                "Use to discover valid type_name values for create_ci_relationship. Read-only."
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
        "get_system_properties": (
            get_system_properties_tool,
            GetSystemPropertiesParams,
            dict,
            (
                "Query sys_properties for ServiceNow instance configuration values. "
                "Use to inspect instance settings, confirm feature flags, or look up "
                "configuration values before making environment-dependent decisions. "
                "Supports encoded query filtering (e.g., nameLIKEglide.email). Read-only."
            ),
            "json",
        ),
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
        "list_sprints": (
            list_sprints_tool,
            ListSprintsParams,
            dict,
            (
                "List sprints from ServiceNow (rm_sprint_2), ordered by start_date descending. "
                "Filter by state (1=Planning, 2=Active, 3=Completed, 4=Cancelled) or release_id. "
                "Returns sprints array with count. Read-only."
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
        "create_release": (
            create_release_tool,
            CreateReleaseParams,
            dict,
            (
                "Create a new release in ServiceNow (rm_release). "
                "Requires a name; optionally provide a planned_date (YYYY-MM-DD) and description. "
                "Returns the new release sys_id, number, and name."
            ),
            "json",
        ),
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
        "list_releases": (
            list_releases_tool,
            ListReleasesParams,
            dict,
            (
                "List releases from ServiceNow (rm_release) with optional state/query filters. "
                "Returns releases list with count."
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
        "get_my_work": (
            get_my_work_tool,
            GetMyWorkParams,
            dict,
            (
                "Return open stories assigned to a specific user. "
                "Call get_current_user first to obtain the user sys_id. "
                "Excludes Complete and Cancelled stories. Read-only."
            ),
            "json",
        ),
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
        "validate_story_promotion_instructions": (
            validate_story_promotion_instructions_tool,
            StoryIdParams,
            dict,
            (
                "Check that the story has non-empty promotion instructions. "
                "Returns has_promotion_instructions: bool and the field_value. "
                "Use before promoting a story to confirm deployment instructions are documented. "
                "Read-only."
            ),
            "json",
        ),
        # Integration Platform Tools
        "list_rest_messages": (
            list_rest_messages_tool,
            ListRestMessagesParams,
            dict,
            "List outbound REST message endpoints configured in ServiceNow (sys_rest_message). "
            "Filter by name. Returns name, endpoint, and authentication type for each.",
            "json",
        ),
        "get_rest_message": (
            get_rest_message_tool,
            GetRestMessageParams,
            dict,
            "Get a single outbound REST message with all its HTTP methods (sys_rest_message_fn). "
            "Provide message_name or message_sys_id. Returns the message record and its method list.",
            "json",
        ),
        "create_rest_message": (
            create_rest_message_tool,
            CreateRestMessageParams,
            dict,
            "Create a new outbound REST message endpoint (sys_rest_message). "
            "A default GET HTTP method is auto-created by the platform on insert.",
            "json",
        ),
        "add_http_method": (
            add_http_method_tool,
            AddHttpMethodParams,
            dict,
            "Add an HTTP method to an existing REST message (sys_rest_message_fn). "
            "http_method must be lowercase (get, post, put, patch, delete).",
            "json",
        ),
        "list_scripted_rest_apis": (
            list_scripted_rest_apis_tool,
            ListScriptedRestApisParams,
            dict,
            "List Scripted REST API definitions (sys_ws_definition). "
            "Filter by name or active status.",
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
        "create_scripted_rest_api": (
            create_scripted_rest_api_tool,
            CreateScriptedRestApiParams,
            dict,
            "Create a new Scripted REST API definition (sys_ws_definition). "
            "Namespace is auto-generated by the platform.",
            "json",
        ),
        "add_rest_resource": (
            add_rest_resource_tool,
            AddRestResourceParams,
            dict,
            "Add a resource/operation to a Scripted REST API (sys_ws_operation). "
            "http_method must be UPPERCASE (GET, POST, PUT, PATCH, DELETE).",
            "json",
        ),
        "list_import_sets": (
            list_import_sets_tool,
            ListImportSetsParams,
            dict,
            "List import set staging containers (sys_import_set). Filter by state.",
            "json",
        ),
        "list_mid_servers": (
            list_mid_servers_tool,
            ListMidServersParams,
            dict,
            "List MID Servers registered in ServiceNow (ecc_agent). "
            "Returns name, status, validated, version, host, and IP for each.",
            "json",
        ),
        "get_mid_server_status": (
            get_mid_server_status_tool,
            GetMidServerStatusParams,
            dict,
            "Get detailed status for a single MID Server (ecc_agent). "
            "Returns validated, status, version, last_refreshed, and any error messages.",
            "json",
        ),
        "list_transform_maps": (
            list_transform_maps_tool,
            ListTransformMapsParams,
            dict,
            "List transform maps (sys_transform_map). Filter by source table or active state.",
            "json",
        ),
        "create_transform_map": (
            create_transform_map_tool,
            CreateTransformMapParams,
            dict,
            "Create a new transform map (sys_transform_map) mapping a staging table to a target table.",
            "json",
        ),
        "run_transform": (
            run_transform_tool,
            RunTransformParams,
            dict,
            "Trigger transform map processing for an existing import set via sys_import_set_run.",
            "json",
        ),
        "run_import": (
            run_import_tool,
            RunImportParams,
            dict,
            "Insert a row into a staging table and run all active transform maps. "
            "staging_table must be alphanumeric + underscore only.",
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
    }
    return tool_definitions
