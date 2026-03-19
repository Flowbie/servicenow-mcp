"""
Scrum Task management tools for the ServiceNow MCP server.

This module provides tools for managing scrum tasks (rm_scrum_task) in ServiceNow.

States: -6=Draft, 1=Ready, 2=Work in progress, 3=Complete, 4=Cancelled
Types:  1=Analysis, 2=Coding, 3=Documentation, 4=Testing
"""

import logging
from typing import Any, Dict, Optional

import requests
from pydantic import BaseModel, Field

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.utils.config import ServerConfig

logger = logging.getLogger(__name__)

# Closed states — Complete (3) or Cancelled (4)
_CLOSED_STATES = {"3", "4"}


# ---------------------------------------------------------------------------
# Params models
# ---------------------------------------------------------------------------


class CreateScrumTaskParams(BaseModel):
    """Parameters for creating a scrum task."""

    story: str = Field(..., description="sys_id of the parent story (rm_story)")
    short_description: str = Field(..., description="Short description of the scrum task")
    priority: Optional[str] = Field(None, description="Priority (1=Critical, 2=High, 3=Moderate, 4=Low)")
    planned_hours: Optional[int] = Field(None, description="Planned hours for the scrum task")
    remaining_hours: Optional[int] = Field(None, description="Remaining hours for the scrum task")
    hours: Optional[int] = Field(None, description="Actual hours logged")
    description: Optional[str] = Field(None, description="Detailed description of the scrum task")
    type: Optional[str] = Field(None, description="Type (1=Analysis, 2=Coding, 3=Documentation, 4=Testing)")
    state: Optional[str] = Field(None, description="State (-6=Draft, 1=Ready, 2=Work in progress, 3=Complete, 4=Cancelled)")
    assignment_group: Optional[str] = Field(None, description="sys_id of the group assigned to the scrum task")
    assigned_to: Optional[str] = Field(None, description="sys_id of the user assigned to the scrum task")
    work_notes: Optional[str] = Field(None, description="Work notes to add to the scrum task")


class UpdateScrumTaskParams(BaseModel):
    """Parameters for updating a scrum task."""

    scrum_task_id: str = Field(..., description="sys_id of the scrum task to update")
    short_description: Optional[str] = Field(None, description="Short description of the scrum task")
    priority: Optional[str] = Field(None, description="Priority (1=Critical, 2=High, 3=Moderate, 4=Low)")
    planned_hours: Optional[int] = Field(None, description="Planned hours for the scrum task")
    remaining_hours: Optional[int] = Field(None, description="Remaining hours for the scrum task")
    hours: Optional[int] = Field(None, description="Actual hours logged")
    description: Optional[str] = Field(None, description="Detailed description of the scrum task")
    type: Optional[str] = Field(None, description="Type (1=Analysis, 2=Coding, 3=Documentation, 4=Testing)")
    state: Optional[str] = Field(None, description="State (-6=Draft, 1=Ready, 2=Work in progress, 3=Complete, 4=Cancelled)")
    assignment_group: Optional[str] = Field(None, description="sys_id of the group assigned to the scrum task")
    assigned_to: Optional[str] = Field(None, description="sys_id of the user assigned to the scrum task")
    work_notes: Optional[str] = Field(None, description="Work notes to add to the scrum task")


class ListScrumTasksParams(BaseModel):
    """Parameters for listing scrum tasks."""

    limit: Optional[int] = Field(10, description="Maximum number of records to return")
    offset: Optional[int] = Field(0, description="Offset to start from")
    story_id: Optional[str] = Field(None, description="Filter by parent story sys_id")
    state: Optional[str] = Field(None, description="Filter by state")
    assignment_group: Optional[str] = Field(None, description="Filter by assignment group sys_id")
    query: Optional[str] = Field(None, description="Additional encoded query string")


class GetScrumTaskParams(BaseModel):
    """Parameters for retrieving a single scrum task."""

    scrum_task_id: str = Field(..., description="sys_id of the scrum task to retrieve")


class CloseScrumTaskParams(BaseModel):
    """Parameters for closing a scrum task."""

    scrum_task_id: str = Field(..., description="sys_id of the scrum task to close")
    work_notes: Optional[str] = Field(None, description="Optional closing notes")


class AssignScrumTaskParams(BaseModel):
    """Parameters for assigning a scrum task."""

    scrum_task_id: str = Field(..., description="sys_id of the scrum task to assign")
    assigned_to: Optional[str] = Field(None, description="sys_id of the user to assign")
    assignment_group: Optional[str] = Field(None, description="sys_id of the group to assign")


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------


def create_scrum_task(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: CreateScrumTaskParams,
) -> Dict[str, Any]:
    """Create a new scrum task in ServiceNow."""
    url = f"{config.instance_url}/api/now/table/rm_scrum_task"

    data: Dict[str, Any] = {
        "story": params.story,
        "short_description": params.short_description,
    }
    if params.priority is not None:
        data["priority"] = params.priority
    if params.planned_hours is not None:
        data["planned_hours"] = params.planned_hours
    if params.remaining_hours is not None:
        data["remaining_hours"] = params.remaining_hours
    if params.hours is not None:
        data["hours"] = params.hours
    if params.description is not None:
        data["description"] = params.description
    if params.type is not None:
        data["type"] = params.type
    if params.state is not None:
        data["state"] = params.state
    if params.assignment_group is not None:
        data["assignment_group"] = params.assignment_group
    if params.assigned_to is not None:
        data["assigned_to"] = params.assigned_to
    if params.work_notes is not None:
        data["work_notes"] = params.work_notes

    headers = auth_manager.get_headers()
    headers["Content-Type"] = "application/json"

    try:
        response = requests.post(url, json=data, headers=headers, timeout=config.timeout)
        response.raise_for_status()
        return {
            "success": True,
            "message": "Scrum task created successfully",
            "scrum_task": response.json()["result"],
        }
    except requests.RequestException as e:
        logger.error("create_scrum_task | error=%s", e)
        return {
            "success": False,
            "message": f"Error creating scrum task: {e}",
        }


def update_scrum_task(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: UpdateScrumTaskParams,
) -> Dict[str, Any]:
    """Update an existing scrum task in ServiceNow."""
    url = f"{config.instance_url}/api/now/table/rm_scrum_task/{params.scrum_task_id}"

    data: Dict[str, Any] = {}
    if params.short_description is not None:
        data["short_description"] = params.short_description
    if params.priority is not None:
        data["priority"] = params.priority
    if params.planned_hours is not None:
        data["planned_hours"] = params.planned_hours
    if params.remaining_hours is not None:
        data["remaining_hours"] = params.remaining_hours
    if params.hours is not None:
        data["hours"] = params.hours
    if params.description is not None:
        data["description"] = params.description
    if params.type is not None:
        data["type"] = params.type
    if params.state is not None:
        data["state"] = params.state
    if params.assignment_group is not None:
        data["assignment_group"] = params.assignment_group
    if params.assigned_to is not None:
        data["assigned_to"] = params.assigned_to
    if params.work_notes is not None:
        data["work_notes"] = params.work_notes

    headers = auth_manager.get_headers()
    headers["Content-Type"] = "application/json"

    try:
        response = requests.put(url, json=data, headers=headers, timeout=config.timeout)
        if response.status_code == 404:
            return {
                "success": False,
                "message": f"Scrum task not found: {params.scrum_task_id}",
            }
        response.raise_for_status()
        return {
            "success": True,
            "message": "Scrum task updated successfully",
            "scrum_task": response.json()["result"],
        }
    except requests.RequestException as e:
        logger.error("update_scrum_task | task_id=%s | error=%s", params.scrum_task_id, e)
        return {
            "success": False,
            "message": f"Error updating scrum task: {e}",
        }


def list_scrum_tasks(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: ListScrumTasksParams,
) -> Dict[str, Any]:
    """List scrum tasks from ServiceNow."""
    url = f"{config.instance_url}/api/now/table/rm_scrum_task"

    query_parts = []
    if params.story_id:
        query_parts.append(f"story={params.story_id}")
    if params.state:
        query_parts.append(f"state={params.state}")
    if params.assignment_group:
        query_parts.append(f"assignment_group={params.assignment_group}")
    if params.query:
        query_parts.append(params.query)

    query = "^".join(query_parts) if query_parts else ""

    try:
        response = requests.get(
            url,
            headers=auth_manager.get_headers(),
            params={
                "sysparm_limit": params.limit,
                "sysparm_offset": params.offset,
                "sysparm_query": query,
                "sysparm_display_value": "true",
            },
            timeout=config.timeout,
        )
        response.raise_for_status()
        scrum_tasks = response.json().get("result", [])
        return {
            "success": True,
            "scrum_tasks": scrum_tasks,
            "count": len(scrum_tasks),
        }
    except requests.RequestException as e:
        logger.error("list_scrum_tasks | error=%s", e)
        return {
            "success": False,
            "message": f"Error listing scrum tasks: {e}",
        }


def get_scrum_task(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: GetScrumTaskParams,
) -> Dict[str, Any]:
    """Retrieve a single scrum task by sys_id."""
    url = f"{config.instance_url}/api/now/table/rm_scrum_task/{params.scrum_task_id}"

    try:
        response = requests.get(
            url,
            headers=auth_manager.get_headers(),
            params={"sysparm_display_value": "true"},
            timeout=config.timeout,
        )
        if response.status_code == 404:
            return {
                "success": False,
                "message": "Scrum task not found",
            }
        response.raise_for_status()
        result = response.json().get("result")
        if not result:
            return {
                "success": False,
                "message": "Scrum task not found",
            }
        return {
            "success": True,
            "scrum_task": result,
        }
    except requests.RequestException as e:
        logger.error("get_scrum_task | task_id=%s | error=%s", params.scrum_task_id, e)
        return {
            "success": False,
            "message": f"Error retrieving scrum task: {e}",
        }


def close_scrum_task(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: CloseScrumTaskParams,
) -> Dict[str, Any]:
    """Close a scrum task by setting its state to Complete (3)."""
    # First fetch the current state to check guard condition
    get_url = f"{config.instance_url}/api/now/table/rm_scrum_task/{params.scrum_task_id}"

    try:
        get_response = requests.get(
            get_url,
            headers=auth_manager.get_headers(),
            params={"sysparm_fields": "sys_id,state", "sysparm_display_value": "false"},
            timeout=config.timeout,
        )
        if get_response.status_code == 404:
            return {
                "success": False,
                "message": "Scrum task not found",
            }
        get_response.raise_for_status()
        current = get_response.json().get("result")
        if not current:
            return {
                "success": False,
                "message": "Scrum task not found",
            }

        current_state = str(current.get("state") or "")
        if current_state in _CLOSED_STATES:
            return {
                "success": False,
                "message": "Scrum task is already closed (Complete or Cancelled)",
            }
    except requests.RequestException as e:
        logger.error("close_scrum_task (get phase) | task_id=%s | error=%s", params.scrum_task_id, e)
        return {
            "success": False,
            "message": f"Error retrieving scrum task: {e}",
        }

    # Now patch state to Complete
    patch_data: Dict[str, Any] = {"state": "3"}
    if params.work_notes:
        patch_data["work_notes"] = params.work_notes

    headers = auth_manager.get_headers()
    headers["Content-Type"] = "application/json"

    try:
        patch_response = requests.patch(
            get_url,
            json=patch_data,
            headers=headers,
            timeout=config.timeout,
        )
        patch_response.raise_for_status()
        return {
            "success": True,
            "message": "Scrum task closed",
            "scrum_task": patch_response.json()["result"],
        }
    except requests.RequestException as e:
        logger.error("close_scrum_task (patch phase) | task_id=%s | error=%s", params.scrum_task_id, e)
        return {
            "success": False,
            "message": f"Error closing scrum task: {e}",
        }


def assign_scrum_task(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: AssignScrumTaskParams,
) -> Dict[str, Any]:
    """Assign a scrum task to a user and/or group."""
    if not params.assigned_to and not params.assignment_group:
        return {
            "success": False,
            "message": "At least one of assigned_to or assignment_group must be provided",
        }

    url = f"{config.instance_url}/api/now/table/rm_scrum_task/{params.scrum_task_id}"

    data: Dict[str, Any] = {}
    if params.assigned_to:
        data["assigned_to"] = params.assigned_to
    if params.assignment_group:
        data["assignment_group"] = params.assignment_group

    headers = auth_manager.get_headers()
    headers["Content-Type"] = "application/json"

    try:
        response = requests.put(url, json=data, headers=headers, timeout=config.timeout)
        if response.status_code == 404:
            return {
                "success": False,
                "message": f"Scrum task not found: {params.scrum_task_id}",
            }
        response.raise_for_status()
        return {
            "success": True,
            "message": "Scrum task assigned",
            "scrum_task": response.json()["result"],
        }
    except requests.RequestException as e:
        logger.error("assign_scrum_task | task_id=%s | error=%s", params.scrum_task_id, e)
        return {
            "success": False,
            "message": f"Error assigning scrum task: {e}",
        }
