"""
Tools module for the ServiceNow MCP server.
"""

# Import tools as they are implemented
from servicenow_mcp.tools.catalog_optimization import (
    get_optimization_recommendations,
)
from servicenow_mcp.tools.catalog_tools import (
    move_catalog_items,
)
from servicenow_mcp.tools.catalog_variables import (
    create_catalog_item_variable,
    list_catalog_item_variables,
    update_catalog_item_variable,
)
from servicenow_mcp.tools.change_tools import (
    add_change_task,
    approve_change,
    create_change_request,
    get_change_request_details,
    list_change_requests,
    reject_change,
    submit_change_for_approval,
    update_change_request,
)
from servicenow_mcp.tools.changeset_tools import (
    add_file_to_changeset,
    commit_changeset,
    create_changeset,
    get_changeset_details,
    list_changesets,
    publish_changeset,
    update_changeset,
)
from servicenow_mcp.tools.script_include_tools import (
    create_script_include,
    delete_script_include,
    get_script_include,
    list_script_includes,
    update_script_include,
)
from servicenow_mcp.tools.user_tools import (
    grant_role_to_user,
    revoke_role_from_user,
    grant_role_to_group,
    revoke_role_from_group,
    list_user_roles,
    list_group_roles,
)
from servicenow_mcp.tools.workflow_tools import (
    activate_workflow,
    add_workflow_activity,
    create_workflow,
    deactivate_workflow,
    delete_workflow_activity,
    get_workflow_activities,
    get_workflow_details,
    list_workflow_versions,
    list_workflows,
    reorder_workflow_activities,
    update_workflow,
    update_workflow_activity,
)
from servicenow_mcp.tools.story_tools import (
    archive_story,
    move_story_state,
    assign_stories_to_sprint,
)
from servicenow_mcp.tools.scrum_task_tools import (
    close_scrum_task,
)
from servicenow_mcp.tools.flow_tools import (
    create_flow,
    list_trigger_types,
    list_flows,
    get_flow,
    update_flow,
    publish_flow,
    create_subflow,
    list_subflows,
    get_subflow,
    update_subflow,
    publish_subflow,
    create_action,
    list_actions,
    get_action,
    update_action,
    publish_action,
)
# from servicenow_mcp.tools.problem_tools import create_problem, update_problem
# from servicenow_mcp.tools.request_tools import create_request, update_request

__all__ = [
    # Catalog tools
    "move_catalog_items",
    "get_optimization_recommendations",
    "create_catalog_item_variable",
    "list_catalog_item_variables",
    "update_catalog_item_variable",
    
    # Change management tools
    "create_change_request",
    "update_change_request",
    "list_change_requests",
    "get_change_request_details",
    "add_change_task",
    "submit_change_for_approval",
    "approve_change",
    "reject_change",
    
    # Workflow management tools
    "list_workflows",
    "get_workflow_details",
    "list_workflow_versions",
    "get_workflow_activities",
    "create_workflow",
    "update_workflow",
    "activate_workflow",
    "deactivate_workflow",
    "add_workflow_activity",
    "update_workflow_activity",
    "delete_workflow_activity",
    "reorder_workflow_activities",
    
    # Changeset tools
    "list_changesets",
    "get_changeset_details",
    "create_changeset",
    "update_changeset",
    "commit_changeset",
    "publish_changeset",
    "add_file_to_changeset",
    
    # Script Include tools
    "list_script_includes",
    "get_script_include",
    "create_script_include",
    "update_script_include",
    "delete_script_include",
    
    # User role management tools
    "grant_role_to_user",
    "revoke_role_from_user",
    "grant_role_to_group",
    "revoke_role_from_group",
    "list_user_roles",
    "list_group_roles",

    # Story tools (compound only)
    "archive_story",
    "move_story_state",
    "assign_stories_to_sprint",

    # Scrum Task tools (compound only)
    "close_scrum_task",

    # Project tools
    "create_project",
    "update_project",
    "list_projects",

    # Flow Designer tools
    "list_trigger_types",
    "create_flow",
    "list_flows",
    "get_flow",
    "update_flow",
    "publish_flow",
    "create_subflow",
    "list_subflows",
    "get_subflow",
    "update_subflow",
    "publish_subflow",
    "create_action",
    "list_actions",
    "get_action",
    "update_action",
    "publish_action",

    
    # Future tools
    # "create_problem",
    # "update_problem",
    # "create_request",
    # "update_request",
] 
