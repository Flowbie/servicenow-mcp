"""
Project management tools for the ServiceNow MCP server.

This module provides tools for managing projects in ServiceNow.
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional

import requests
from pydantic import BaseModel, Field

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.utils.config import ServerConfig

logger = logging.getLogger(__name__)


class CreateProjectParams(BaseModel):
    """Parameters for creating a project."""

    short_description: str = Field(..., description="Project name of the project")
    description: Optional[str] = Field(None, description="Detailed description of the project")
    status: Optional[str] = Field(None, description="Status of the project (green, yellow, red)")
    state: Optional[str] = Field(None, description="State of project (-5 is Pending,1 is Open, 2 is Work in progress, 3 is Closed Complete, 4 is Closed Incomplete, 5 is Closed Skipped)")
    project_manager: Optional[str] = Field(None, description="Project manager for the project")
    percentage_complete: Optional[int] = Field(None, description="Percentage complete for the project")
    assignment_group: Optional[str] = Field(None, description="Group assigned to the project")
    assigned_to: Optional[str] = Field(None, description="User assigned to the project")
    start_date: Optional[str] = Field(None, description="Start date for the project")
    end_date: Optional[str] = Field(None, description="End date for the project")


class UpdateProjectParams(BaseModel):
    """Parameters for updating a project."""

    project_id: str = Field(..., description="Project ID or sys_id")
    short_description: Optional[str] = Field(None, description="Project name of the project")
    description: Optional[str] = Field(None, description="Detailed description of the project")
    status: Optional[str] = Field(None, description="Status of the project (green, yellow, red)")
    state: Optional[str] = Field(None, description="State of project (-5 is Pending,1 is Open, 2 is Work in progress, 3 is Closed Complete, 4 is Closed Incomplete, 5 is Closed Skipped)")
    project_manager: Optional[str] = Field(None, description="Project manager for the project")
    percentage_complete: Optional[int] = Field(None, description="Percentage complete for the project")
    assignment_group: Optional[str] = Field(None, description="Group assigned to the project")
    assigned_to: Optional[str] = Field(None, description="User assigned to the project")
    start_date: Optional[str] = Field(None, description="Start date for the project")
    end_date: Optional[str] = Field(None, description="End date for the project")


class ListProjectsParams(BaseModel):
    """Parameters for listing projects."""

    limit: Optional[int] = Field(10, description="Maximum number of records to return")
    offset: Optional[int] = Field(0, description="Offset to start from")
    state: Optional[str] = Field(None, description="Filter by state")
    assignment_group: Optional[str] = Field(None, description="Filter by assignment group")
    timeframe: Optional[str] = Field(None, description="Filter by timeframe (upcoming, in-progress, completed)")
    query: Optional[str] = Field(None, description="Additional query string")


def create_project(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: CreateProjectParams,
) -> Dict:
    """
    Create a new project in ServiceNow.

    Args:
        config: The server configuration.
        auth_manager: The authentication manager.
        params: The parameters for creating the project.

    Returns:
        The created project.
    """
    data: Dict = {
        "short_description": params.short_description,
    }

    if params.description:
        data["description"] = params.description
    if params.status:
        data["status"] = params.status
    if params.state:
        data["state"] = params.state
    if params.assignment_group:
        data["assignment_group"] = params.assignment_group
    if params.percentage_complete:
        data["percentage_complete"] = params.percentage_complete
    if params.assigned_to:
        data["assigned_to"] = params.assigned_to
    if params.project_manager:
        data["project_manager"] = params.project_manager
    if params.start_date:
        data["start_date"] = params.start_date
    if params.end_date:
        data["end_date"] = params.end_date

    headers = auth_manager.get_headers()
    headers["Content-Type"] = "application/json"

    url = f"{config.instance_url}/api/now/table/pm_project"

    try:
        response = requests.post(url, json=data, headers=headers)
        response.raise_for_status()

        result = response.json()

        return {
            "success": True,
            "message": "Project created successfully",
            "project": result["result"],
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Error creating project: {e}")
        return {
            "success": False,
            "message": f"Error creating project: {str(e)}",
        }


def update_project(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: UpdateProjectParams,
) -> Dict:
    """
    Update an existing project in ServiceNow.

    Args:
        config: The server configuration.
        auth_manager: The authentication manager.
        params: The parameters for updating the project.

    Returns:
        The updated project.
    """
    data: Dict = {}

    if params.short_description:
        data["short_description"] = params.short_description
    if params.description:
        data["description"] = params.description
    if params.status:
        data["status"] = params.status
    if params.state:
        data["state"] = params.state
    if params.assignment_group:
        data["assignment_group"] = params.assignment_group
    if params.percentage_complete:
        data["percentage_complete"] = params.percentage_complete
    if params.assigned_to:
        data["assigned_to"] = params.assigned_to
    if params.project_manager:
        data["project_manager"] = params.project_manager
    if params.start_date:
        data["start_date"] = params.start_date
    if params.end_date:
        data["end_date"] = params.end_date

    headers = auth_manager.get_headers()
    headers["Content-Type"] = "application/json"

    url = f"{config.instance_url}/api/now/table/pm_project/{params.project_id}"

    try:
        response = requests.patch(url, json=data, headers=headers)
        response.raise_for_status()

        result = response.json()

        return {
            "success": True,
            "message": "Project updated successfully",
            "project": result["result"],
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Error updating project: {e}")
        return {
            "success": False,
            "message": f"Error updating project: {str(e)}",
        }


def list_projects(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: ListProjectsParams,
) -> Dict:
    """
    List projects from ServiceNow.

    Args:
        config: The server configuration.
        auth_manager: The authentication manager.
        params: The parameters for listing projects.

    Returns:
        A list of projects.
    """
    query_parts: List[str] = []

    if params.state:
        query_parts.append(f"state={params.state}")
    if params.assignment_group:
        query_parts.append(f"assignment_group={params.assignment_group}")

    if params.timeframe:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if params.timeframe == "upcoming":
            query_parts.append(f"start_date>{now}")
        elif params.timeframe == "in-progress":
            query_parts.append(f"start_date<{now}^end_date>{now}")
        elif params.timeframe == "completed":
            query_parts.append(f"end_date<{now}")

    if params.query:
        query_parts.append(params.query)

    query = "^".join(query_parts) if query_parts else ""

    headers = auth_manager.get_headers()

    url = f"{config.instance_url}/api/now/table/pm_project"

    request_params = {
        "sysparm_limit": params.limit,
        "sysparm_offset": params.offset,
        "sysparm_query": query,
        "sysparm_display_value": "true",
    }

    try:
        response = requests.get(url, headers=headers, params=request_params)
        response.raise_for_status()

        result = response.json()

        projects = result.get("result", [])
        count = len(projects)

        return {
            "success": True,
            "projects": projects,
            "count": count,
            "total": count,
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Error listing projects: {e}")
        return {
            "success": False,
            "message": f"Error listing projects: {str(e)}",
        }
