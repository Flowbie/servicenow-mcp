"""
Service Request tools for the ServiceNow MCP server.

This module provides tools for managing service requests (sc_request),
request items (sc_req_item / RITM), and catalog tasks (sc_task).
"""

import logging
from typing import Any, Dict, List, Optional

import requests
from pydantic import BaseModel, Field, model_validator

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.utils.config import ServerConfig

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Param models
# ---------------------------------------------------------------------------


class ListRequestsParams(BaseModel):
    """Parameters for listing service requests."""

    limit: int = Field(10, description="Maximum number of requests to return")
    offset: int = Field(0, description="Pagination offset")
    state_filter: Optional[str] = Field(None, description="Filter by state value")
    requested_for: Optional[str] = Field(None, description="Filter by requested_for sys_id or user name")


class GetRequestParams(BaseModel):
    """Parameters for getting a specific service request."""

    request_number: Optional[str] = Field(None, description="Request number (e.g. REQ0001234)")
    request_sys_id: Optional[str] = Field(None, description="Request sys_id")

    @model_validator(mode="after")
    def require_one_identifier(self) -> "GetRequestParams":
        if not self.request_number and not self.request_sys_id:
            raise ValueError("At least one of request_number or request_sys_id must be provided")
        return self


class ListRequestItemsParams(BaseModel):
    """Parameters for listing request items (RITMs)."""

    limit: int = Field(10, description="Maximum number of items to return")
    offset: int = Field(0, description="Pagination offset")
    request_sys_id: Optional[str] = Field(None, description="Filter by parent request sys_id")
    state_filter: Optional[str] = Field(None, description="Filter by state value")


class UpdateRequestItemParams(BaseModel):
    """Parameters for updating a request item (RITM)."""

    ritm_sys_id: str = Field(..., description="RITM sys_id")
    state: Optional[str] = Field(None, description="New state value")
    assignment_group: Optional[str] = Field(None, description="Assignment group sys_id")
    assigned_to: Optional[str] = Field(None, description="Assigned-to user sys_id")
    work_notes: Optional[str] = Field(None, description="Work notes to append")
    close_notes: Optional[str] = Field(None, description="Close notes")


class ListScTasksParams(BaseModel):
    """Parameters for listing catalog tasks (sc_task)."""

    limit: int = Field(10, description="Maximum number of tasks to return")
    offset: int = Field(0, description="Pagination offset")
    request_item_sys_id: Optional[str] = Field(None, description="Filter by parent RITM sys_id")
    state_filter: Optional[str] = Field(None, description="Filter by state value")


class UpdateScTaskParams(BaseModel):
    """Parameters for updating a catalog task."""

    task_sys_id: str = Field(..., description="sc_task sys_id")
    state: Optional[str] = Field(None, description="New state value")
    assignment_group: Optional[str] = Field(None, description="Assignment group sys_id")
    assigned_to: Optional[str] = Field(None, description="Assigned-to user sys_id")
    work_notes: Optional[str] = Field(None, description="Work notes to append")
    close_notes: Optional[str] = Field(None, description="Close notes")


class GetRitmVariablesParams(BaseModel):
    """Parameters for getting RITM variable answers."""

    ritm_sys_id: str = Field(..., description="RITM sys_id")


# ---------------------------------------------------------------------------
# Tool functions
# ---------------------------------------------------------------------------


def list_requests(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: ListRequestsParams,
) -> Dict[str, Any]:
    """
    List service requests from ServiceNow (sc_request table).

    Args:
        config: Server configuration
        auth_manager: Authentication manager
        params: Parameters for listing requests

    Returns:
        Dictionary containing requests and metadata
    """
    logger.info("Listing service requests")

    url = f"{config.instance_url}/api/now/table/sc_request"

    query_params: Dict[str, Any] = {
        "sysparm_limit": params.limit,
        "sysparm_offset": params.offset,
        "sysparm_fields": "sys_id,number,short_description,state,requested_for,opened_at,opened_by",
        "sysparm_display_value": "true",
        "sysparm_exclude_reference_link": "true",
    }

    filters = []
    if params.state_filter:
        filters.append(f"state={params.state_filter}")
    if params.requested_for:
        filters.append(f"requested_for={params.requested_for}")

    if filters:
        query_params["sysparm_query"] = "^".join(filters)

    headers = auth_manager.get_headers()
    headers["Accept"] = "application/json"

    try:
        response = requests.get(url, headers=headers, params=query_params)
        response.raise_for_status()

        items = response.json().get("result", [])
        return {
            "success": True,
            "message": f"Found {len(items)} request(s)",
            "requests": items,
            "total": len(items),
            "limit": params.limit,
            "offset": params.offset,
        }

    except requests.exceptions.RequestException as e:
        logger.error(f"Error listing requests: {str(e)}")
        return {
            "success": False,
            "message": f"Error listing requests: {str(e)}",
            "requests": [],
            "total": 0,
            "limit": params.limit,
            "offset": params.offset,
        }


def get_request(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: GetRequestParams,
) -> Dict[str, Any]:
    """
    Get a specific service request from ServiceNow.

    Args:
        config: Server configuration
        auth_manager: Authentication manager
        params: Parameters for getting a request (number or sys_id)

    Returns:
        Dictionary containing the full request record
    """
    logger.info(
        f"Getting request: number={params.request_number} sys_id={params.request_sys_id}"
    )

    headers = auth_manager.get_headers()
    headers["Accept"] = "application/json"

    common_qp = {
        "sysparm_display_value": "true",
        "sysparm_exclude_reference_link": "true",
    }

    try:
        if params.request_sys_id:
            url = f"{config.instance_url}/api/now/table/sc_request/{params.request_sys_id}"
            response = requests.get(url, headers=headers, params=common_qp)
            response.raise_for_status()
            record = response.json().get("result", {})
        else:
            url = f"{config.instance_url}/api/now/table/sc_request"
            qp = dict(common_qp)
            qp["sysparm_query"] = f"number={params.request_number}"
            qp["sysparm_limit"] = "1"
            response = requests.get(url, headers=headers, params=qp)
            response.raise_for_status()
            results = response.json().get("result", [])
            record = results[0] if results else {}

        if not record:
            return {
                "success": False,
                "message": f"Request not found: {params.request_number or params.request_sys_id}",
                "request": None,
            }

        return {
            "success": True,
            "message": f"Retrieved request: {record.get('number', '')}",
            "request": record,
        }

    except requests.exceptions.RequestException as e:
        logger.error(f"Error getting request: {str(e)}")
        return {
            "success": False,
            "message": f"Error getting request: {str(e)}",
            "request": None,
        }


def list_request_items(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: ListRequestItemsParams,
) -> Dict[str, Any]:
    """
    List request items (RITMs) from ServiceNow (sc_req_item table).

    Args:
        config: Server configuration
        auth_manager: Authentication manager
        params: Parameters for listing request items

    Returns:
        Dictionary containing request items and metadata
    """
    logger.info("Listing request items")

    url = f"{config.instance_url}/api/now/table/sc_req_item"

    query_params: Dict[str, Any] = {
        "sysparm_limit": params.limit,
        "sysparm_offset": params.offset,
        "sysparm_fields": "sys_id,number,short_description,state,cat_item,request,quantity,stage",
        "sysparm_display_value": "true",
        "sysparm_exclude_reference_link": "true",
    }

    filters = []
    if params.request_sys_id:
        filters.append(f"request={params.request_sys_id}")
    if params.state_filter:
        filters.append(f"state={params.state_filter}")

    if filters:
        query_params["sysparm_query"] = "^".join(filters)

    headers = auth_manager.get_headers()
    headers["Accept"] = "application/json"

    try:
        response = requests.get(url, headers=headers, params=query_params)
        response.raise_for_status()

        items = response.json().get("result", [])
        return {
            "success": True,
            "message": f"Found {len(items)} request item(s)",
            "items": items,
            "total": len(items),
            "limit": params.limit,
            "offset": params.offset,
        }

    except requests.exceptions.RequestException as e:
        logger.error(f"Error listing request items: {str(e)}")
        return {
            "success": False,
            "message": f"Error listing request items: {str(e)}",
            "items": [],
            "total": 0,
            "limit": params.limit,
            "offset": params.offset,
        }


def update_request_item(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: UpdateRequestItemParams,
) -> Dict[str, Any]:
    """
    Update a request item (RITM) in ServiceNow.

    Args:
        config: Server configuration
        auth_manager: Authentication manager
        params: Parameters for updating the RITM

    Returns:
        Dictionary containing the result of the operation
    """
    logger.info(f"Updating request item: {params.ritm_sys_id}")

    url = f"{config.instance_url}/api/now/table/sc_req_item/{params.ritm_sys_id}"

    body: Dict[str, Any] = {}
    if params.state is not None:
        body["state"] = params.state
    if params.assignment_group is not None:
        body["assignment_group"] = params.assignment_group
    if params.assigned_to is not None:
        body["assigned_to"] = params.assigned_to
    if params.work_notes is not None:
        body["work_notes"] = params.work_notes
    if params.close_notes is not None:
        body["close_notes"] = params.close_notes

    headers = auth_manager.get_headers()
    headers["Accept"] = "application/json"
    headers["Content-Type"] = "application/json"

    try:
        response = requests.patch(url, headers=headers, json=body)
        response.raise_for_status()

        result = response.json().get("result", {})
        return {
            "success": True,
            "message": f"Request item updated: {params.ritm_sys_id}",
            "item": result,
        }

    except requests.exceptions.RequestException as e:
        logger.error(f"Error updating request item: {str(e)}")
        return {
            "success": False,
            "message": f"Error updating request item: {str(e)}",
            "item": None,
        }


def list_sc_tasks(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: ListScTasksParams,
) -> Dict[str, Any]:
    """
    List catalog tasks (sc_task) from ServiceNow.

    Args:
        config: Server configuration
        auth_manager: Authentication manager
        params: Parameters for listing catalog tasks

    Returns:
        Dictionary containing catalog tasks and metadata
    """
    logger.info("Listing catalog tasks")

    url = f"{config.instance_url}/api/now/table/sc_task"

    query_params: Dict[str, Any] = {
        "sysparm_limit": params.limit,
        "sysparm_offset": params.offset,
        "sysparm_fields": "sys_id,number,short_description,state,assigned_to,assignment_group,request_item",
        "sysparm_display_value": "true",
        "sysparm_exclude_reference_link": "true",
    }

    filters = []
    if params.request_item_sys_id:
        filters.append(f"request_item={params.request_item_sys_id}")
    if params.state_filter:
        filters.append(f"state={params.state_filter}")

    if filters:
        query_params["sysparm_query"] = "^".join(filters)

    headers = auth_manager.get_headers()
    headers["Accept"] = "application/json"

    try:
        response = requests.get(url, headers=headers, params=query_params)
        response.raise_for_status()

        items = response.json().get("result", [])
        return {
            "success": True,
            "message": f"Found {len(items)} catalog task(s)",
            "tasks": items,
            "total": len(items),
            "limit": params.limit,
            "offset": params.offset,
        }

    except requests.exceptions.RequestException as e:
        logger.error(f"Error listing catalog tasks: {str(e)}")
        return {
            "success": False,
            "message": f"Error listing catalog tasks: {str(e)}",
            "tasks": [],
            "total": 0,
            "limit": params.limit,
            "offset": params.offset,
        }


def update_sc_task(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: UpdateScTaskParams,
) -> Dict[str, Any]:
    """
    Update a catalog task (sc_task) in ServiceNow.

    Args:
        config: Server configuration
        auth_manager: Authentication manager
        params: Parameters for updating the catalog task

    Returns:
        Dictionary containing the result of the operation
    """
    logger.info(f"Updating catalog task: {params.task_sys_id}")

    url = f"{config.instance_url}/api/now/table/sc_task/{params.task_sys_id}"

    body: Dict[str, Any] = {}
    if params.state is not None:
        body["state"] = params.state
    if params.assignment_group is not None:
        body["assignment_group"] = params.assignment_group
    if params.assigned_to is not None:
        body["assigned_to"] = params.assigned_to
    if params.work_notes is not None:
        body["work_notes"] = params.work_notes
    if params.close_notes is not None:
        body["close_notes"] = params.close_notes

    headers = auth_manager.get_headers()
    headers["Accept"] = "application/json"
    headers["Content-Type"] = "application/json"

    try:
        response = requests.patch(url, headers=headers, json=body)
        response.raise_for_status()

        result = response.json().get("result", {})
        return {
            "success": True,
            "message": f"Catalog task updated: {params.task_sys_id}",
            "task": result,
        }

    except requests.exceptions.RequestException as e:
        logger.error(f"Error updating catalog task: {str(e)}")
        return {
            "success": False,
            "message": f"Error updating catalog task: {str(e)}",
            "task": None,
        }


def get_ritm_variables(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: GetRitmVariablesParams,
) -> Dict[str, Any]:
    """
    Get variable answers for a RITM via the sc_item_option_mtom indirect join.

    Fetches sc_item_option_mtom rows for the RITM, then retrieves the actual
    sc_item_option record for each link to get the variable name, label, and value.

    Args:
        config: Server configuration
        auth_manager: Authentication manager
        params: Parameters containing the RITM sys_id

    Returns:
        Dictionary with a list of {name, label, value} variable answers
    """
    logger.info(f"Getting RITM variables for: {params.ritm_sys_id}")

    headers = auth_manager.get_headers()
    headers["Accept"] = "application/json"

    try:
        # Step 1 – get mtom join rows for this RITM
        mtom_url = f"{config.instance_url}/api/now/table/sc_item_option_mtom"
        mtom_response = requests.get(
            mtom_url,
            headers=headers,
            params={
                "sysparm_query": f"request_item={params.ritm_sys_id}",
                "sysparm_display_value": "true",
                "sysparm_exclude_reference_link": "true",
            },
        )
        mtom_response.raise_for_status()
        mtom_rows = mtom_response.json().get("result", [])

        if not mtom_rows:
            return {
                "success": True,
                "message": "No variables found for this RITM",
                "variables": [],
            }

        # Step 2 – for each mtom row, fetch the sc_item_option record
        variables: List[Dict[str, Any]] = []
        for row in mtom_rows:
            # The sc_item_option sys_id is stored in the sc_item_option field
            option_ref = row.get("sc_item_option", "")
            if not option_ref:
                continue

            # When display_value=true, reference fields may be dicts or plain strings
            option_sys_id = (
                option_ref.get("value", option_ref)
                if isinstance(option_ref, dict)
                else option_ref
            )

            option_url = f"{config.instance_url}/api/now/table/sc_item_option"
            option_response = requests.get(
                option_url,
                headers=headers,
                params={
                    "sys_id": option_sys_id,
                    "sysparm_display_value": "true",
                    "sysparm_exclude_reference_link": "true",
                },
            )
            option_response.raise_for_status()
            option_results = option_response.json().get("result", [])

            if not option_results:
                continue

            opt = option_results[0] if isinstance(option_results, list) else option_results

            # item_option_new holds the variable definition; value is in sc_item_option
            variables.append(
                {
                    "name": opt.get("item_option_new", {}).get("name", "")
                    if isinstance(opt.get("item_option_new"), dict)
                    else opt.get("item_option_new", ""),
                    "label": opt.get("item_option_new", {}).get("question_text", "")
                    if isinstance(opt.get("item_option_new"), dict)
                    else "",
                    "value": opt.get("value", ""),
                }
            )

        return {
            "success": True,
            "message": f"Found {len(variables)} variable(s) for RITM",
            "variables": variables,
        }

    except requests.exceptions.RequestException as e:
        logger.error(f"Error getting RITM variables: {str(e)}")
        return {
            "success": False,
            "message": f"Error getting RITM variables: {str(e)}",
            "variables": [],
        }
