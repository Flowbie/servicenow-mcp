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
    CreateCatalogCategoryParams,
    GetCatalogItemParams,
    ListCatalogCategoriesParams,
    ListCatalogItemsParams,
    MoveCatalogItemsParams,
    UpdateCatalogCategoryParams,
    UpdateCatalogItemParams,
)
from servicenow_mcp.tools.catalog_tools import (
    create_catalog_category as create_catalog_category_tool,
)
from servicenow_mcp.tools.catalog_tools import (
    get_catalog_item as get_catalog_item_tool,
)
from servicenow_mcp.tools.catalog_tools import (
    list_catalog_categories as list_catalog_categories_tool,
)
from servicenow_mcp.tools.catalog_tools import (
    list_catalog_items as list_catalog_items_tool,
)
from servicenow_mcp.tools.catalog_tools import (
    move_catalog_items as move_catalog_items_tool,
)
from servicenow_mcp.tools.catalog_tools import (
    update_catalog_category as update_catalog_category_tool,
)
from servicenow_mcp.tools.catalog_tools import (
    update_catalog_item as update_catalog_item_tool,
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
    AddFileToChangesetParams,
    CommitChangesetParams,
    CreateChangesetParams,
    GetChangesetDetailsParams,
    ListChangesetsParams,
    PublishChangesetParams,
    UpdateChangesetParams,
)
from servicenow_mcp.tools.changeset_tools import (
    add_file_to_changeset as add_file_to_changeset_tool,
)
from servicenow_mcp.tools.changeset_tools import (
    commit_changeset as commit_changeset_tool,
)
from servicenow_mcp.tools.changeset_tools import (
    create_changeset as create_changeset_tool,
)
from servicenow_mcp.tools.changeset_tools import (
    get_changeset_details as get_changeset_details_tool,
)
from servicenow_mcp.tools.changeset_tools import (
    list_changesets as list_changesets_tool,
)
from servicenow_mcp.tools.changeset_tools import (
    publish_changeset as publish_changeset_tool,
)
from servicenow_mcp.tools.changeset_tools import (
    update_changeset as update_changeset_tool,
)
from servicenow_mcp.tools.incident_tools import (
    AddCommentParams,
    CreateIncidentParams,
    ListIncidentsParams,
    ResolveIncidentParams,
    UpdateIncidentParams,
    GetIncidentByNumberParams,
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
from servicenow_mcp.tools.automation_tools import (
    ListScheduledJobsParams,
    GetScheduledJobParams,
    EnableScheduledJobParams,
    DisableScheduledJobParams,
    CreateScheduledScriptParams,
    DeleteScheduledJobParams,
    ListScheduledImportsParams,
    ListScheduledExportsParams,
    list_scheduled_jobs as list_scheduled_jobs_tool,
    get_scheduled_job as get_scheduled_job_tool,
    enable_scheduled_job as enable_scheduled_job_tool,
    disable_scheduled_job as disable_scheduled_job_tool,
    create_scheduled_script as create_scheduled_script_tool,
    delete_scheduled_job as delete_scheduled_job_tool,
    list_scheduled_imports as list_scheduled_imports_tool,
    list_scheduled_exports as list_scheduled_exports_tool,
)
from servicenow_mcp.tools.customization_tools import (
    CreateBusinessRuleParams,
    CreateClientScriptParams,
    CreateUIActionParams,
    DeleteBusinessRuleParams,
    ListAccessControlsParams,
    ListBusinessRulesParams,
    ListClientScriptsParams,
    ListNotificationsParams,
    ListScheduledScriptsParams,
    ListUIActionsParams,
    ListUIPoliciesParams,
    UpdateBusinessRuleParams,
    UpdateClientScriptParams,
    UpdateUIActionParams,
    create_business_rule as create_business_rule_tool,
    create_client_script as create_client_script_tool,
    create_ui_action as create_ui_action_tool,
    delete_business_rule as delete_business_rule_tool,
    list_access_controls as list_access_controls_tool,
    list_business_rules as list_business_rules_tool,
    list_client_scripts as list_client_scripts_tool,
    list_notifications as list_notifications_tool,
    list_scheduled_scripts as list_scheduled_scripts_tool,
    list_ui_actions as list_ui_actions_tool,
    list_ui_policies as list_ui_policies_tool,
    update_business_rule as update_business_rule_tool,
    update_client_script as update_client_script_tool,
    update_ui_action as update_ui_action_tool,
)
from servicenow_mcp.tools.incident_tools import (
    add_comment as add_comment_tool,
)
from servicenow_mcp.tools.incident_tools import (
    create_incident as create_incident_tool,
)
from servicenow_mcp.tools.incident_tools import (
    list_incidents as list_incidents_tool,
)
from servicenow_mcp.tools.incident_tools import (
    resolve_incident as resolve_incident_tool,
)
from servicenow_mcp.tools.incident_tools import (
    update_incident as update_incident_tool,
)
from servicenow_mcp.tools.incident_tools import (
    get_incident_by_number as get_incident_by_number_tool,
)
from servicenow_mcp.tools.knowledge_base import (
    CreateArticleParams,
    CreateKnowledgeBaseParams,
    GetArticleParams,
    ListArticlesParams,
    ListKnowledgeBasesParams,
    PublishArticleParams,
    UpdateArticleParams,
)
from servicenow_mcp.tools.knowledge_base import (
    CreateCategoryParams as CreateKBCategoryParams,  # Aliased
)
from servicenow_mcp.tools.knowledge_base import (
    ListCategoriesParams as ListKBCategoriesParams,  # Aliased
)
from servicenow_mcp.tools.knowledge_base import (
    create_article as create_article_tool,
)
from servicenow_mcp.tools.knowledge_base import (
    # create_category aliased in function call
    create_knowledge_base as create_knowledge_base_tool,
)
from servicenow_mcp.tools.knowledge_base import (
    get_article as get_article_tool,
)
from servicenow_mcp.tools.knowledge_base import (
    list_articles as list_articles_tool,
)
from servicenow_mcp.tools.knowledge_base import (
    # list_categories aliased in function call
    list_knowledge_bases as list_knowledge_bases_tool,
)
from servicenow_mcp.tools.knowledge_base import (
    publish_article as publish_article_tool,
)
from servicenow_mcp.tools.knowledge_base import (
    update_article as update_article_tool,
)
from servicenow_mcp.tools.script_include_tools import (
    CreateScriptIncludeParams,
    DeleteScriptIncludeParams,
    GetScriptIncludeParams,
    ListScriptIncludesParams,
    ScriptIncludeResponse,
    UpdateScriptIncludeParams,
)
from servicenow_mcp.tools.script_include_tools import (
    create_script_include as create_script_include_tool,
)
from servicenow_mcp.tools.script_include_tools import (
    delete_script_include as delete_script_include_tool,
)
from servicenow_mcp.tools.script_include_tools import (
    get_script_include as get_script_include_tool,
)
from servicenow_mcp.tools.script_include_tools import (
    list_script_includes as list_script_includes_tool,
)
from servicenow_mcp.tools.script_include_tools import (
    update_script_include as update_script_include_tool,
)
from servicenow_mcp.tools.user_tools import (
    AddGroupMembersParams,
    CreateGroupParams,
    CreateUserParams,
    GetUserParams,
    GrantRoleToGroupParams,
    GrantRoleToUserParams,
    ListGroupRolesParams,
    ListGroupsParams,
    ListUserRolesParams,
    ListUsersParams,
    RemoveGroupMembersParams,
    RevokeRoleFromGroupParams,
    RevokeRoleFromUserParams,
    UpdateGroupParams,
    UpdateUserParams,
)
from servicenow_mcp.tools.user_tools import (
    add_group_members as add_group_members_tool,
)
from servicenow_mcp.tools.user_tools import (
    create_group as create_group_tool,
)
from servicenow_mcp.tools.user_tools import (
    create_user as create_user_tool,
)
from servicenow_mcp.tools.user_tools import (
    get_user as get_user_tool,
)
from servicenow_mcp.tools.user_tools import (
    list_groups as list_groups_tool,
)
from servicenow_mcp.tools.user_tools import (
    list_users as list_users_tool,
)
from servicenow_mcp.tools.user_tools import (
    remove_group_members as remove_group_members_tool,
)
from servicenow_mcp.tools.user_tools import (
    update_group as update_group_tool,
)
from servicenow_mcp.tools.user_tools import (
    update_user as update_user_tool,
)
from servicenow_mcp.tools.user_tools import (
    grant_role_to_group as grant_role_to_group_tool,
    grant_role_to_user as grant_role_to_user_tool,
    list_group_roles as list_group_roles_tool,
    list_user_roles as list_user_roles_tool,
    revoke_role_from_group as revoke_role_from_group_tool,
    revoke_role_from_user as revoke_role_from_user_tool,
)
from servicenow_mcp.tools.risk_tools import (
    AssignRiskResponseParams,
    CreateRiskParams,
    GetRiskParams,
    ListRiskCriteriaParams,
    ListRisksParams,
    UpdateRiskStateParams,
)
from servicenow_mcp.tools.risk_tools import (
    assign_risk_response as assign_risk_response_tool,
    create_risk as create_risk_tool,
    get_risk as get_risk_tool,
    list_risk_criteria as list_risk_criteria_tool,
    list_risks as list_risks_tool,
    update_risk_state as update_risk_state_tool,
)
from servicenow_mcp.tools.workflow_tools import (
    ActivateWorkflowParams,
    AddWorkflowActivityParams,
    CreateWorkflowParams,
    DeactivateWorkflowParams,
    DeleteWorkflowActivityParams,
    GetWorkflowActivitiesParams,
    GetWorkflowDetailsParams,
    ListWorkflowsParams,
    ListWorkflowVersionsParams,
    ReorderWorkflowActivitiesParams,
    UpdateWorkflowActivityParams,
    UpdateWorkflowParams,
)
from servicenow_mcp.tools.workflow_tools import (
    activate_workflow as activate_workflow_tool,
)
from servicenow_mcp.tools.workflow_tools import (
    add_workflow_activity as add_workflow_activity_tool,
)
from servicenow_mcp.tools.workflow_tools import (
    create_workflow as create_workflow_tool,
)
from servicenow_mcp.tools.workflow_tools import (
    deactivate_workflow as deactivate_workflow_tool,
)
from servicenow_mcp.tools.workflow_tools import (
    delete_workflow_activity as delete_workflow_activity_tool,
)
from servicenow_mcp.tools.workflow_tools import (
    get_workflow_activities as get_workflow_activities_tool,
)
from servicenow_mcp.tools.workflow_tools import (
    get_workflow_details as get_workflow_details_tool,
)
from servicenow_mcp.tools.workflow_tools import (
    list_workflow_versions as list_workflow_versions_tool,
)
from servicenow_mcp.tools.workflow_tools import (
    list_workflows as list_workflows_tool,
)
from servicenow_mcp.tools.workflow_tools import (
    reorder_workflow_activities as reorder_workflow_activities_tool,
)
from servicenow_mcp.tools.workflow_tools import (
    update_workflow as update_workflow_tool,
)
from servicenow_mcp.tools.workflow_tools import (
    update_workflow_activity as update_workflow_activity_tool,
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
    CreateReleaseParams,
    GetReleaseParams,
    ValidateReleaseReadinessParams,
    CompileReleaseNotesParams,
    create_release as create_release_tool,
    get_release as get_release_tool,
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
    CreateStoryParams,
    UpdateStoryParams,
    ListStoriesParams,
    ListStoryDependenciesParams,
    CreateStoryDependencyParams,
    DeleteStoryDependencyParams,
    GetStoryParams,
    ArchiveStoryParams,
    MoveStoryStateParams,
    AssignStoryParams,
    AddStoryCommentParams,
    ListStoryBlockersParams,
)
from servicenow_mcp.tools.story_tools import (
    create_story as create_story_tool,
    update_story as update_story_tool,
    list_stories as list_stories_tool,
    list_story_dependencies as list_story_dependencies_tool,
    create_story_dependency as create_story_dependency_tool,
    delete_story_dependency as delete_story_dependency_tool,
    get_story as get_story_tool,
    archive_story as archive_story_tool,
    move_story_state as move_story_state_tool,
    assign_story as assign_story_tool,
    add_story_comment as add_story_comment_tool,
    list_story_blockers as list_story_blockers_tool,
    assign_stories_to_sprint as assign_stories_to_sprint_tool,
)
from servicenow_mcp.tools.epic_tools import (
    CreateEpicParams,
    UpdateEpicParams,
    ListEpicsParams,
)
from servicenow_mcp.tools.epic_tools import (
    create_epic as create_epic_tool,
    update_epic as update_epic_tool,
    list_epics as list_epics_tool,
)
from servicenow_mcp.tools.scrum_task_tools import (
    CreateScrumTaskParams,
    UpdateScrumTaskParams,
    ListScrumTasksParams,
    GetScrumTaskParams,
    CloseScrumTaskParams,
    AssignScrumTaskParams,
)
from servicenow_mcp.tools.scrum_task_tools import (
    create_scrum_task as create_scrum_task_tool,
    update_scrum_task as update_scrum_task_tool,
    list_scrum_tasks as list_scrum_tasks_tool,
    get_scrum_task as get_scrum_task_tool,
    close_scrum_task as close_scrum_task_tool,
    assign_scrum_task as assign_scrum_task_tool,
)
from servicenow_mcp.tools.project_tools import (
    CreateProjectParams,
    UpdateProjectParams,
    ListProjectsParams,
)
from servicenow_mcp.tools.project_tools import (
    create_project as create_project_tool,
    update_project as update_project_tool,
    list_projects as list_projects_tool,
)
from servicenow_mcp.tools.flow_tools import (
    CreateFlowParams,
    CreateFlowResponse,
    GetFlowActionsParams,
    GetFlowParams,
    GetFlowTriggersParams,
    GetFlowVersionParams,
    ListFlowsParams,
    ListTriggerTypesParams,
    ListTriggerTypesResult,
    PublishFlowParams,
)
from servicenow_mcp.tools.flow_tools import (
    create_flow as create_flow_tool,
    get_flow as get_flow_tool,
    get_flow_actions as get_flow_actions_tool,
    get_flow_triggers as get_flow_triggers_tool,
    get_flow_version as get_flow_version_tool,
    list_flows as list_flows_tool,
    list_trigger_types as list_trigger_types_tool,
    publish_flow as publish_flow_tool,
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
from servicenow_mcp.tools.catalog_tools import (
    CreateCatalogItemParams,
    DeleteCatalogItemParams,
    ListCatalogsParams,
    CreateCatalogParams,
)
from servicenow_mcp.tools.catalog_tools import (
    create_catalog_item as create_catalog_item_tool,
    delete_catalog_item as delete_catalog_item_tool,
    list_catalogs as list_catalogs_tool,
    create_catalog as create_catalog_tool,
)
from servicenow_mcp.tools.request_tools import (
    ListRequestsParams,
    GetRequestParams,
    ListRequestItemsParams,
    UpdateRequestItemParams,
    ListScTasksParams,
    UpdateScTaskParams,
    GetRitmVariablesParams,
)
from servicenow_mcp.tools.request_tools import (
    list_requests as list_requests_tool,
    get_request as get_request_tool,
    list_request_items as list_request_items_tool,
    update_request_item as update_request_item_tool,
    list_sc_tasks as list_sc_tasks_tool,
    update_sc_task as update_sc_task_tool,
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


def get_tool_definitions(
    create_kb_category_tool_impl: Callable, list_kb_categories_tool_impl: Callable
) -> Dict[str, ToolDefinition]:
    """
    Returns a dictionary containing definitions for all available ServiceNow tools.

    This centralizes the tool definitions for use in the server implementation.
    Pass aliased functions for KB categories directly.

    Returns:
        Dict[str, ToolDefinition]: A dictionary mapping tool names to their definitions.
    """
    tool_definitions: Dict[str, ToolDefinition] = {
        # Incident Tools
        "create_incident": (
            create_incident_tool,
            CreateIncidentParams,
            str,
            "Create a new incident in ServiceNow",
            "str",
        ),
        "update_incident": (
            update_incident_tool,
            UpdateIncidentParams,
            str,
            "Update an existing incident in ServiceNow",
            "str",
        ),
        "add_comment": (
            add_comment_tool,
            AddCommentParams,
            str,
            "Add a comment to an incident in ServiceNow",
            "str",
        ),
        "resolve_incident": (
            resolve_incident_tool,
            ResolveIncidentParams,
            str,
            "Resolve an incident in ServiceNow",
            "str",
        ),
        "list_incidents": (
            list_incidents_tool,
            ListIncidentsParams,
            str,  # Expects JSON string
            "List incidents from ServiceNow",
            "json",  # Tool returns list/dict, needs JSON dump
        ),
        "get_incident_by_number": (
            get_incident_by_number_tool,
            GetIncidentByNumberParams,
            str,
            "Incident details from ServiceNow",
            "json_dict",
        ),
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
        # Customization discovery tools — table-centric, read-only.
        # Use these for architecture blueprints and pre-implementation research.
        # Contrast with the field-centric diagnostic tools above (get_business_rules,
        # get_ui_policies) which require a field name and are used during write-mismatch
        # escalation.
        "list_business_rules": (
            list_business_rules_tool,
            ListBusinessRulesParams,
            dict,
            (
                "Query sys_script for all Business Rules on a table. Returns name, timing "
                "(before/after/async), trigger flags (insert/update/delete/query), condition, "
                "and a 500-character script preview for every rule. Use this for architecture "
                "blueprints to understand what server-side automation exists on the table. "
                "For diagnosing a specific field write mismatch, use get_business_rules instead "
                "(it filters by field name). Read-only."
            ),
            "json",
        ),
        "list_ui_policies": (
            list_ui_policies_tool,
            ListUIPoliciesParams,
            dict,
            (
                "Query sys_ui_policy for all UI Policies on a table. Returns policy name, "
                "active state, run_scripts flag, and short description. "
                "UI Policies are browser-form-only and have no effect on REST API writes. "
                "For checking a specific field's form behaviour use get_ui_policies instead. "
                "Read-only."
            ),
            "json",
        ),
        "list_client_scripts": (
            list_client_scripts_tool,
            ListClientScriptsParams,
            dict,
            (
                "Query sys_script_client for all Client Scripts on a table. Returns name, "
                "script type (onChange/onLoad/onSubmit), watched field (for onChange scripts), "
                "active state, and a script preview. Client scripts run in the browser only "
                "and do not affect server-side API behaviour. Read-only."
            ),
            "json",
        ),
        "list_notifications": (
            list_notifications_tool,
            ListNotificationsParams,
            dict,
            (
                "Query sysevent_email_action for all Notifications configured for a table. "
                "Returns notification name, triggering event (blank for condition-based), "
                "email subject template, and filter condition. Use for architecture blueprints "
                "to understand what outbound communications fire on record changes. Read-only."
            ),
            "json",
        ),
        "list_ui_actions": (
            list_ui_actions_tool,
            ListUIActionsParams,
            dict,
            (
                "Query sys_ui_action for all UI Actions on a table. Returns name, action type "
                "(form button / context menu / list choice), visibility condition, and script "
                "preview. Use to understand what user-initiated actions and their server-side "
                "scripts exist on the table. Read-only."
            ),
            "json",
        ),
        "list_access_controls": (
            list_access_controls_tool,
            ListAccessControlsParams,
            dict,
            (
                "Query sys_security_acl for all Access Control rules for a table. Returns both "
                "record-level ACLs (e.g., 'incident.read') and field-level ACLs "
                "(e.g., 'incident.caller_id.write') with operation, required roles, condition, "
                "and script preview. Use for architecture blueprints and security reviews. Read-only."
            ),
            "json",
        ),
        # Platform Scripting Write Tools (Phase 6)
        "create_business_rule": (
            create_business_rule_tool,
            CreateBusinessRuleParams,
            dict,
            "Create a Business Rule in sys_script. Note: the table field is 'collection' on sys_script.",
            "json",
        ),
        "update_business_rule": (
            update_business_rule_tool,
            UpdateBusinessRuleParams,
            dict,
            "Update an existing Business Rule in sys_script by sys_id",
            "json",
        ),
        "delete_business_rule": (
            delete_business_rule_tool,
            DeleteBusinessRuleParams,
            dict,
            "Delete a Business Rule from sys_script by sys_id",
            "json",
        ),
        "create_client_script": (
            create_client_script_tool,
            CreateClientScriptParams,
            dict,
            "Create a Client Script in sys_script_client (onChange/onLoad/onSubmit/onCellEdit)",
            "json",
        ),
        "update_client_script": (
            update_client_script_tool,
            UpdateClientScriptParams,
            dict,
            "Update an existing Client Script in sys_script_client by sys_id",
            "json",
        ),
        "create_ui_action": (
            create_ui_action_tool,
            CreateUIActionParams,
            dict,
            "Create a UI Action in sys_ui_action. No action_type field — surfaces controlled by 14 boolean flags.",
            "json",
        ),
        "update_ui_action": (
            update_ui_action_tool,
            UpdateUIActionParams,
            dict,
            "Update an existing UI Action in sys_ui_action by sys_id",
            "json",
        ),
        "list_scheduled_scripts": (
            list_scheduled_scripts_tool,
            ListScheduledScriptsParams,
            dict,
            "List scheduled script executions from sysauto_script. Read-only.",
            "json",
        ),
        # Catalog Tools
        "list_catalog_items": (
            list_catalog_items_tool,
            ListCatalogItemsParams,
            str,  # Expects JSON string
            "List service catalog items.",
            "json",  # Tool returns list/dict
        ),
        "get_catalog_item": (
            get_catalog_item_tool,
            GetCatalogItemParams,
            str,  # Expects JSON string
            "Get a specific service catalog item.",
            "json_dict",  # Tool returns Pydantic model
        ),
        "list_catalog_categories": (
            list_catalog_categories_tool,
            ListCatalogCategoriesParams,
            str,  # Expects JSON string
            "List service catalog categories.",
            "json",  # Tool returns list/dict
        ),
        "create_catalog_category": (
            create_catalog_category_tool,
            CreateCatalogCategoryParams,
            str,  # Expects JSON string
            "Create a new service catalog category.",
            "json_dict",  # Tool returns Pydantic model
        ),
        "update_catalog_category": (
            update_catalog_category_tool,
            UpdateCatalogCategoryParams,
            str,  # Expects JSON string
            "Update an existing service catalog category.",
            "json_dict",  # Tool returns Pydantic model
        ),
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
        "update_catalog_item": (
            update_catalog_item_tool,
            UpdateCatalogItemParams,
            str,  # Expects JSON string
            "Update a service catalog item.",
            "json",  # Tool returns Pydantic model
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
        # Catalog — new tools (gap fill)
        "create_catalog_item": (
            create_catalog_item_tool,
            CreateCatalogItemParams,
            dict,
            "Create a new service catalog item (sc_cat_item).",
            "json",
        ),
        "delete_catalog_item": (
            delete_catalog_item_tool,
            DeleteCatalogItemParams,
            dict,
            "Delete a service catalog item by sys_id (sc_cat_item).",
            "json",
        ),
        "list_catalogs": (
            list_catalogs_tool,
            ListCatalogsParams,
            dict,
            "List service catalogs (sc_catalog). Filter by active status.",
            "json",
        ),
        "create_catalog": (
            create_catalog_tool,
            CreateCatalogParams,
            dict,
            "Create a new service catalog (sc_catalog).",
            "json",
        ),
        # Request Fulfillment Tools (sc_request / sc_req_item / sc_task)
        "list_requests": (
            list_requests_tool,
            ListRequestsParams,
            dict,
            "List service requests (sc_request). Filter by state or requested_for user.",
            "json",
        ),
        "get_request": (
            get_request_tool,
            GetRequestParams,
            dict,
            "Get a single service request by number or sys_id (sc_request).",
            "json",
        ),
        "list_request_items": (
            list_request_items_tool,
            ListRequestItemsParams,
            dict,
            "List requested items (sc_req_item / RITM). Filter by parent request or state.",
            "json",
        ),
        "update_request_item": (
            update_request_item_tool,
            UpdateRequestItemParams,
            dict,
            "Update a requested item (sc_req_item) — state transitions, assignment, notes.",
            "json",
        ),
        "list_sc_tasks": (
            list_sc_tasks_tool,
            ListScTasksParams,
            dict,
            "List catalog tasks (sc_task). Filter by parent RITM or state.",
            "json",
        ),
        "update_sc_task": (
            update_sc_task_tool,
            UpdateScTaskParams,
            dict,
            "Update a catalog task (sc_task) — state transitions, assignment, notes.",
            "json",
        ),
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
        # Automation Platform Tools
        "list_scheduled_jobs": (
            list_scheduled_jobs_tool,
            ListScheduledJobsParams,
            str,
            "List scheduled jobs from sys_trigger with optional type/active filters",
            "json",
        ),
        "get_scheduled_job": (
            get_scheduled_job_tool,
            GetScheduledJobParams,
            str,
            "Get a single scheduled job by sys_id or name",
            "json",
        ),
        "enable_scheduled_job": (
            enable_scheduled_job_tool,
            EnableScheduledJobParams,
            str,
            "Enable a scheduled job by setting active=true",
            "json",
        ),
        "disable_scheduled_job": (
            disable_scheduled_job_tool,
            DisableScheduledJobParams,
            str,
            "Disable a scheduled job by setting trigger_type=2 (Once) — not active=false",
            "json",
        ),
        "create_scheduled_script": (
            create_scheduled_script_tool,
            CreateScheduledScriptParams,
            str,
            "Create a scheduled script execution job (time_zone mandatory)",
            "json",
        ),
        "delete_scheduled_job": (
            delete_scheduled_job_tool,
            DeleteScheduledJobParams,
            str,
            "Delete a scheduled job (refuses cluster-wide parent jobs)",
            "json",
        ),
        "list_scheduled_imports": (
            list_scheduled_imports_tool,
            ListScheduledImportsParams,
            str,
            "List scheduled import sets from scheduled_import_set",
            "json",
        ),
        "list_scheduled_exports": (
            list_scheduled_exports_tool,
            ListScheduledExportsParams,
            str,
            "List scheduled data exports from scheduled_data_export",
            "json",
        ),
        # Workflow Management Tools
        "list_workflows": (
            list_workflows_tool,
            ListWorkflowsParams,
            str,  # Expects JSON string
            "List workflows from ServiceNow",
            "json",  # Tool returns list/dict
        ),
        "get_workflow_details": (
            get_workflow_details_tool,
            GetWorkflowDetailsParams,
            str,  # Expects JSON string
            "Get detailed information about a specific workflow",
            "json",  # Tool returns list/dict
        ),
        "list_workflow_versions": (
            list_workflow_versions_tool,
            ListWorkflowVersionsParams,
            str,  # Expects JSON string
            "List workflow versions from ServiceNow",
            "json",  # Tool returns list/dict
        ),
        "get_workflow_activities": (
            get_workflow_activities_tool,
            GetWorkflowActivitiesParams,
            str,  # Expects JSON string
            "Get activities for a specific workflow",
            "json",  # Tool returns list/dict
        ),
        "create_workflow": (
            create_workflow_tool,
            CreateWorkflowParams,
            str,  # Expects JSON string
            "Create a new workflow in ServiceNow",
            "json_dict",  # Tool returns Pydantic model
        ),
        "update_workflow": (
            update_workflow_tool,
            UpdateWorkflowParams,
            str,  # Expects JSON string
            "Update an existing workflow in ServiceNow",
            "json_dict",  # Tool returns Pydantic model
        ),
        "activate_workflow": (
            activate_workflow_tool,
            ActivateWorkflowParams,
            str,
            "Activate a workflow in ServiceNow",
            "str",  # Tool returns simple message
        ),
        "deactivate_workflow": (
            deactivate_workflow_tool,
            DeactivateWorkflowParams,
            str,
            "Deactivate a workflow in ServiceNow",
            "str",  # Tool returns simple message
        ),
        "add_workflow_activity": (
            add_workflow_activity_tool,
            AddWorkflowActivityParams,
            str,  # Expects JSON string
            "Add a new activity to a workflow in ServiceNow",
            "json_dict",  # Tool returns Pydantic model
        ),
        "update_workflow_activity": (
            update_workflow_activity_tool,
            UpdateWorkflowActivityParams,
            str,  # Expects JSON string
            "Update an existing activity in a workflow",
            "json_dict",  # Tool returns Pydantic model
        ),
        "delete_workflow_activity": (
            delete_workflow_activity_tool,
            DeleteWorkflowActivityParams,
            str,
            "Delete an activity from a workflow",
            "str",  # Tool returns simple message
        ),
        "reorder_workflow_activities": (
            reorder_workflow_activities_tool,
            ReorderWorkflowActivitiesParams,
            str,
            "Reorder activities in a workflow",
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
        "publish_flow": (
            publish_flow_tool,
            PublishFlowParams,
            dict,
            "Publish (activate) a Flow Designer flow by setting active=true on sys_hub_flow",
            "json",
        ),
        # Changeset Management Tools
        "list_changesets": (
            list_changesets_tool,
            ListChangesetsParams,
            str,  # Expects JSON string
            "List changesets from ServiceNow",
            "json",  # Tool returns list/dict
        ),
        "get_changeset_details": (
            get_changeset_details_tool,
            GetChangesetDetailsParams,
            str,  # Expects JSON string
            "Get detailed information about a specific changeset",
            "json",  # Tool returns list/dict
        ),
        "create_changeset": (
            create_changeset_tool,
            CreateChangesetParams,
            str,  # Expects JSON string
            "Create a new changeset in ServiceNow",
            "json_dict",  # Tool returns Pydantic model
        ),
        "update_changeset": (
            update_changeset_tool,
            UpdateChangesetParams,
            str,  # Expects JSON string
            "Update an existing changeset in ServiceNow",
            "json_dict",  # Tool returns Pydantic model
        ),
        "commit_changeset": (
            commit_changeset_tool,
            CommitChangesetParams,
            str,
            "Commit a changeset in ServiceNow",
            "str",  # Tool returns simple message
        ),
        "publish_changeset": (
            publish_changeset_tool,
            PublishChangesetParams,
            str,
            "Publish a changeset in ServiceNow",
            "str",  # Tool returns simple message
        ),
        "add_file_to_changeset": (
            add_file_to_changeset_tool,
            AddFileToChangesetParams,
            str,
            "Add a file to a changeset in ServiceNow",
            "str",  # Tool returns simple message
        ),
        # Script Include Tools
        "list_script_includes": (
            list_script_includes_tool,
            ListScriptIncludesParams,
            Dict[str, Any],  # Expects dict
            "List script includes from ServiceNow",
            "raw_dict",  # Tool returns raw dict
        ),
        "get_script_include": (
            get_script_include_tool,
            GetScriptIncludeParams,
            Dict[str, Any],  # Expects dict
            "Get a specific script include from ServiceNow",
            "raw_dict",  # Tool returns raw dict
        ),
        "create_script_include": (
            create_script_include_tool,
            CreateScriptIncludeParams,
            ScriptIncludeResponse,  # Expects Pydantic model
            "Create a new script include in ServiceNow",
            "raw_pydantic",  # Tool returns Pydantic model
        ),
        "update_script_include": (
            update_script_include_tool,
            UpdateScriptIncludeParams,
            ScriptIncludeResponse,  # Expects Pydantic model
            "Update an existing script include in ServiceNow",
            "raw_pydantic",  # Tool returns Pydantic model
        ),
        "delete_script_include": (
            delete_script_include_tool,
            DeleteScriptIncludeParams,
            str,  # Expects JSON string
            "Delete a script include in ServiceNow",
            "json_dict",  # Tool returns Pydantic model
        ),
        # Knowledge Base Tools
        "create_knowledge_base": (
            create_knowledge_base_tool,
            CreateKnowledgeBaseParams,
            str,  # Expects JSON string
            "Create a new knowledge base in ServiceNow",
            "json_dict",  # Tool returns Pydantic model
        ),
        "list_knowledge_bases": (
            list_knowledge_bases_tool,
            ListKnowledgeBasesParams,
            Dict[str, Any],  # Expects dict
            "List knowledge bases from ServiceNow",
            "raw_dict",  # Tool returns raw dict
        ),
        # Use the passed-in implementations for aliased KB category tools
        "create_category": (
            create_kb_category_tool_impl,  # Use passed function
            CreateKBCategoryParams,
            str,  # Expects JSON string
            "Create a new category in a knowledge base",
            "json_dict",  # Tool returns Pydantic model
        ),
        "create_article": (
            create_article_tool,
            CreateArticleParams,
            str,  # Expects JSON string
            "Create a new knowledge article",
            "json_dict",  # Tool returns Pydantic model
        ),
        "update_article": (
            update_article_tool,
            UpdateArticleParams,
            str,  # Expects JSON string
            "Update an existing knowledge article",
            "json_dict",  # Tool returns Pydantic model
        ),
        "publish_article": (
            publish_article_tool,
            PublishArticleParams,
            str,  # Expects JSON string
            "Publish a knowledge article",
            "json_dict",  # Tool returns Pydantic model
        ),
        "list_articles": (
            list_articles_tool,
            ListArticlesParams,
            Dict[str, Any],  # Expects dict
            "List knowledge articles",
            "raw_dict",  # Tool returns raw dict
        ),
        "get_article": (
            get_article_tool,
            GetArticleParams,
            Dict[str, Any],  # Expects dict
            "Get a specific knowledge article by ID",
            "raw_dict",  # Tool returns raw dict
        ),
        # Use the passed-in implementations for aliased KB category tools
        "list_categories": (
            list_kb_categories_tool_impl,  # Use passed function
            ListKBCategoriesParams,
            Dict[str, Any],  # Expects dict
            "List categories in a knowledge base",
            "raw_dict",  # Tool returns raw dict
        ),
        # User Management Tools
        "create_user": (
            create_user_tool,
            CreateUserParams,
            Dict[str, Any],  # Expects dict
            "Create a new user in ServiceNow",
            "raw_dict",  # Tool returns raw dict
        ),
        "update_user": (
            update_user_tool,
            UpdateUserParams,
            Dict[str, Any],  # Expects dict
            "Update an existing user in ServiceNow",
            "raw_dict",
        ),
        "get_user": (
            get_user_tool,
            GetUserParams,
            Dict[str, Any],  # Expects dict
            "Get a specific user in ServiceNow",
            "raw_dict",
        ),
        "list_users": (
            list_users_tool,
            ListUsersParams,
            Dict[str, Any],  # Expects dict
            "List users in ServiceNow",
            "raw_dict",
        ),
        "create_group": (
            create_group_tool,
            CreateGroupParams,
            Dict[str, Any],  # Expects dict
            "Create a new group in ServiceNow",
            "raw_dict",
        ),
        "update_group": (
            update_group_tool,
            UpdateGroupParams,
            Dict[str, Any],  # Expects dict
            "Update an existing group in ServiceNow",
            "raw_dict",
        ),
        "add_group_members": (
            add_group_members_tool,
            AddGroupMembersParams,
            Dict[str, Any],  # Expects dict
            "Add members to an existing group in ServiceNow",
            "raw_dict",
        ),
        "remove_group_members": (
            remove_group_members_tool,
            RemoveGroupMembersParams,
            Dict[str, Any],  # Expects dict
            "Remove members from an existing group in ServiceNow",
            "raw_dict",
        ),
        "list_groups": (
            list_groups_tool,
            ListGroupsParams,
            Dict[str, Any],  # Expects dict
            "List groups from ServiceNow with optional filtering",
            "raw_dict",
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
        # GRC Risk Tools (Phase 9)
        "list_risks": (
            list_risks_tool,
            ListRisksParams,
            dict,
            (
                "List risks from sn_risk_risk. Filter by state (string label: draft/assess/respond/"
                "monitor/review/retired) or framework. Returns display values for reference fields. "
                "Read-only."
            ),
            "json",
        ),
        "get_risk": (
            get_risk_tool,
            GetRiskParams,
            dict,
            (
                "Retrieve a single risk by sys_id from sn_risk_risk. "
                "Returns all fields with display values. Likelihood, impact, score are "
                "references to sn_risk_criteria. Read-only."
            ),
            "json",
        ),
        "create_risk": (
            create_risk_tool,
            CreateRiskParams,
            dict,
            (
                "Create a new risk record in sn_risk_risk. "
                "Likelihood and impact must be sys_ids from sn_risk_criteria — "
                "use list_risk_criteria to resolve labels to sys_ids first."
            ),
            "json",
        ),
        "update_risk_state": (
            update_risk_state_tool,
            UpdateRiskStateParams,
            dict,
            (
                "Update the state of a risk record. "
                "State must be a string label: draft, assess, respond, monitor, review, or retired. "
                "NOT a numeric code."
            ),
            "json",
        ),
        "list_risk_criteria": (
            list_risk_criteria_tool,
            ListRiskCriteriaParams,
            dict,
            (
                "List risk criteria from sn_risk_criteria. "
                "Use to resolve likelihood, impact, or score label names to sys_ids "
                "before passing them to create_risk or assign_risk_response. Read-only."
            ),
            "json",
        ),
        "assign_risk_response": (
            assign_risk_response_tool,
            AssignRiskResponseParams,
            dict,
            (
                "Assign a treatment response to a risk. "
                "Response must be one of: Accept, Avoid, Mitigate, Transfer (string labels, "
                "NOT numeric codes)."
            ),
            "json",
        ),
        # Story Management Tools
        "create_story": (
            create_story_tool,
            CreateStoryParams,
            str,
            "Create a new story in ServiceNow",
            "str",
        ),
        "update_story": (
            update_story_tool,
            UpdateStoryParams,
            str,
            "Update an existing story in ServiceNow",
            "str",
        ),
        "list_stories": (
            list_stories_tool,
            ListStoriesParams,
            str,  # Expects JSON string
            "List stories from ServiceNow",
            "json",  # Tool returns list/dict
        ),
        "list_story_dependencies": (
            list_story_dependencies_tool,
            ListStoryDependenciesParams,
            str,  # Expects JSON string
            "List story dependencies from ServiceNow",
            "json",  # Tool returns list/dict
        ),
        "create_story_dependency": (
            create_story_dependency_tool,
            CreateStoryDependencyParams,
            str,
            "Create a dependency between two stories in ServiceNow",
            "str",
        ),
        "delete_story_dependency": (
            delete_story_dependency_tool,
            DeleteStoryDependencyParams,
            str,
            "Delete a story dependency in ServiceNow",
            "str",
        ),
        "get_story": (
            get_story_tool,
            GetStoryParams,
            dict,
            (
                "Retrieve a single story by sys_id or story number (e.g. STRY0001234). "
                "Returns the full story record including state, epic, sprint, assignee, "
                "acceptance_criteria, and story_points. Read-only."
            ),
            "json",
        ),
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
        "assign_story": (
            assign_story_tool,
            AssignStoryParams,
            dict,
            (
                "Assign a story to a user and/or group. "
                "Provide assigned_to (user sys_id), assignment_group (group sys_id), or both. "
                "At least one must be supplied."
            ),
            "json",
        ),
        "add_story_comment": (
            add_story_comment_tool,
            AddStoryCommentParams,
            dict,
            (
                "Add a work note / comment to a story. "
                "Appends the comment text to the story's work_notes journal field."
            ),
            "json",
        ),
        "list_story_blockers": (
            list_story_blockers_tool,
            ListStoryBlockersParams,
            dict,
            (
                "List all stories that are blocking the given story. "
                "Returns dependency records from m2m_story_dependencies where the story "
                "is the dependent (blocked) side. Read-only."
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
        # Epic Management Tools
        "create_epic": (
            create_epic_tool,
            CreateEpicParams,
            str,
            "Create a new epic in ServiceNow",
            "str",
        ),
        "update_epic": (
            update_epic_tool,
            UpdateEpicParams,
            str,
            "Update an existing epic in ServiceNow",
            "str",
        ),
        "list_epics": (
            list_epics_tool,
            ListEpicsParams,
            str,  # Expects JSON string
            "List epics from ServiceNow",
            "json",  # Tool returns list/dict
        ),
        # Scrum Task Management Tools
        "create_scrum_task": (
            create_scrum_task_tool,
            CreateScrumTaskParams,
            str,
            "Create a new scrum task in ServiceNow",
            "str",
        ),
        "update_scrum_task": (
            update_scrum_task_tool,
            UpdateScrumTaskParams,
            str,
            "Update an existing scrum task in ServiceNow",
            "str",
        ),
        "list_scrum_tasks": (
            list_scrum_tasks_tool,
            ListScrumTasksParams,
            str,  # Expects JSON string
            "List scrum tasks from ServiceNow",
            "json",  # Tool returns list/dict
        ),
        "get_scrum_task": (
            get_scrum_task_tool,
            GetScrumTaskParams,
            dict,
            "Retrieve a single scrum task by sys_id. Returns the full task record. Read-only.",
            "json",
        ),
        "close_scrum_task": (
            close_scrum_task_tool,
            CloseScrumTaskParams,
            dict,
            "Close a scrum task by setting its state to Complete (3). Optionally adds closing work notes.",
            "json",
        ),
        "assign_scrum_task": (
            assign_scrum_task_tool,
            AssignScrumTaskParams,
            dict,
            "Assign a scrum task to a user and/or group. At least one of assigned_to or assignment_group required.",
            "json",
        ),
        # Project Management Tools
        "create_project": (
            create_project_tool,
            CreateProjectParams,
            str,
            "Create a new project in ServiceNow",
            "str",
        ),
        "update_project": (
            update_project_tool,
            UpdateProjectParams,
            str,
            "Update an existing project in ServiceNow",
            "str",
        ),
        "list_projects": (
            list_projects_tool,
            ListProjectsParams,
            str,  # Expects JSON string
            "List projects from ServiceNow",
            "json",  # Tool returns list/dict
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
                "correct update set. Use list_changesets to find available update set sys_ids."
            ),
            "json",
        ),
    }
    return tool_definitions
