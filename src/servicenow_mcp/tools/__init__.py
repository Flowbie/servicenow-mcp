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
from servicenow_mcp.tools.change_tools import (
    approve_change,
    reject_change,
    submit_change_for_approval,
)
from servicenow_mcp.tools.changeset_tools import (
    get_changeset_details,
    set_current_update_set,
)
from servicenow_mcp.tools.user_tools import (
    grant_role_to_user,
    revoke_role_from_user,
    grant_role_to_group,
    revoke_role_from_group,
    list_user_roles,
    list_group_roles,
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

    # Change management tools — compound approval workflow only
    # CRUD via table_tools + change_request architecture blueprint
    "submit_change_for_approval",
    "approve_change",
    "reject_change",
    
    # Changeset tools (compound only; CRUD via table_tools + sys_update_set blueprint)
    "get_changeset_details",
    "set_current_update_set",
    
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
