"""
Changeset tools for the ServiceNow MCP server.

This module provides compound tools for managing update sets in ServiceNow.
CRUD operations (list, create, update, commit, publish, add_file) are handled
by table_tools (query_records / create_record / update_record) using the
sys_update_set architecture blueprint.
"""

import logging
from typing import Any, Dict, List, Optional, Type, TypeVar, Union

import requests
from pydantic import BaseModel, Field

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.utils.config import ServerConfig
from servicenow_mcp.utils.update_set_policy import UpdateSetInfo, is_default_update_set

logger = logging.getLogger(__name__)

# Type variable for Pydantic models
T = TypeVar('T', bound=BaseModel)


class GetChangesetDetailsParams(BaseModel):
    """Parameters for getting changeset details."""

    changeset_id: str = Field(..., description="Changeset ID or sys_id")


class SetCurrentUpdateSetParams(BaseModel):
    """Parameters for activating an update set as the current working set."""

    changeset_id: str = Field(
        ...,
        description=(
            "sys_id of the update set to activate as current. "
            "The update set must be in 'in progress' state."
        ),
    )


class GetCurrentUpdateSetParams(BaseModel):
    """Parameters for fetching the user's currently active update set."""


def _unwrap_and_validate_params(
    params: Union[Dict[str, Any], BaseModel],
    model_class: Type[T],
    required_fields: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Unwrap and validate parameters.

    Args:
        params: The parameters to unwrap and validate. Can be a dictionary or a Pydantic model.
        model_class: The Pydantic model class to validate against.
        required_fields: List of fields that must be present.

    Returns:
        A dictionary with success status and validated parameters or error message.
    """
    try:
        # Handle case where params is already a Pydantic model
        if isinstance(params, BaseModel):
            # If it's already the correct model class, use it directly
            if isinstance(params, model_class):
                model_instance = params
            # Otherwise, convert to dict and create new instance
            else:
                model_instance = model_class(**params.dict())
        # Handle dictionary case
        else:
            # Create model instance
            model_instance = model_class(**params)

        # Check required fields
        if required_fields:
            missing_fields = []
            for field in required_fields:
                if getattr(model_instance, field, None) is None:
                    missing_fields.append(field)

            if missing_fields:
                return {
                    "success": False,
                    "message": f"Missing required fields: {', '.join(missing_fields)}",
                }

        return {
            "success": True,
            "params": model_instance,
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Invalid parameters: {str(e)}",
        }


def get_changeset_details(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: Union[Dict[str, Any], GetChangesetDetailsParams],
) -> Dict[str, Any]:
    """
    Get detailed information about a specific changeset.

    Fetches the update set record and all associated sys_update_xml change records
    in a single compound call — two API requests joined on changeset_id.

    Args:
        config: The server configuration.
        auth_manager: The authentication manager.
        params: The parameters for getting changeset details. Can be a dictionary or a GetChangesetDetailsParams object.

    Returns:
        Detailed information about the changeset.
    """
    # Unwrap and validate parameters
    result = _unwrap_and_validate_params(
        params,
        GetChangesetDetailsParams,
        required_fields=["changeset_id"]
    )

    if not result["success"]:
        return result

    validated_params = result["params"]

    instance_url = config.instance_url
    headers = auth_manager.get_headers()

    # Make the API request
    url = f"{instance_url}/api/now/table/sys_update_set/{validated_params.changeset_id}"

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()

        result = response.json()

        # Get the changeset details
        changeset = result.get("result", {})

        # Get the changes in this changeset
        changes_url = f"{instance_url}/api/now/table/sys_update_xml"
        changes_params = {
            "sysparm_query": f"update_set={validated_params.changeset_id}",
        }

        changes_response = requests.get(changes_url, params=changes_params, headers=headers)
        changes_response.raise_for_status()

        changes_result = changes_response.json()
        changes = changes_result.get("result", [])

        return {
            "success": True,
            "changeset": changeset,
            "changes": changes,
            "change_count": len(changes),
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Error getting changeset details: {e}")
        return {
            "success": False,
            "message": f"Error getting changeset details: {str(e)}",
        }


def _normalize_update_set(update_set: Dict[str, Any]) -> UpdateSetInfo:
    name = update_set.get("name")
    sys_id = update_set.get("sys_id")
    state = update_set.get("state")
    return UpdateSetInfo(
        name=name if isinstance(name, str) else None,
        sys_id=sys_id if isinstance(sys_id, str) else None,
        state=state if isinstance(state, str) else None,
        is_default=is_default_update_set(name if isinstance(name, str) else None),
    )


def get_current_update_set(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: Union[Dict[str, Any], GetCurrentUpdateSetParams, None] = None,
) -> Dict[str, Any]:
    """
    Get the currently active update set for the authenticated user.

    The value is resolved from the user's sys_update_set preference and then
    normalized into a small stable contract for downstream governance checks.
    """
    result = _unwrap_and_validate_params(params or {}, GetCurrentUpdateSetParams)
    if not result["success"]:
        return result

    instance_url = config.instance_url
    headers = auth_manager.get_headers()
    pref_url = (
        f"{instance_url}/api/now/table/sys_user_preference"
        "?sysparm_query=name=sys_update_set^user.user_name=current&sysparm_limit=1"
    )

    try:
        pref_resp = requests.get(pref_url, headers=headers)
        pref_resp.raise_for_status()
        prefs = pref_resp.json().get("result", [])
        if not prefs:
            return {
                "success": False,
                "message": "No active sys_update_set preference was found for the current user.",
            }

        current_update_set_sys_id = prefs[0].get("value")
        if not isinstance(current_update_set_sys_id, str) or not current_update_set_sys_id:
            return {
                "success": False,
                "message": "The current user's sys_update_set preference does not contain a valid sys_id.",
            }

        update_set_resp = requests.get(
            f"{instance_url}/api/now/table/sys_update_set/{current_update_set_sys_id}",
            headers=headers,
        )
        update_set_resp.raise_for_status()
        normalized = _normalize_update_set(update_set_resp.json().get("result", {}))
        return {
            "success": True,
            "name": normalized.name,
            "sys_id": normalized.sys_id,
            "state": normalized.state,
            "is_default": normalized.is_default,
            "update_set": {
                "name": normalized.name,
                "sys_id": normalized.sys_id,
                "state": normalized.state,
                "is_default": normalized.is_default,
            },
        }
    except requests.exceptions.RequestException as e:
        logger.error("Error getting current update set: %s", e)
        return {"success": False, "message": f"Failed to fetch current update set: {e}"}


def set_current_update_set(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: Union[Dict[str, Any], SetCurrentUpdateSetParams],
) -> Dict[str, Any]:
    """
    Activate an update set as the current working set for the authenticated user.

    Validates the update set is in 'in progress' state, then updates the user's
    sys_user_preference to make it the active update set. All subsequent platform
    changes will be captured in this update set.

    Args:
        config: The server configuration.
        auth_manager: The authentication manager.
        params: The changeset_id to activate.

    Returns:
        Success status with the activated update set details.
    """
    result = _unwrap_and_validate_params(
        params,
        SetCurrentUpdateSetParams,
        required_fields=["changeset_id"],
    )
    if not result["success"]:
        return result

    validated_params = result["params"]
    instance_url = config.instance_url
    headers = auth_manager.get_headers()

    # Validate the update set exists and is in progress
    check_url = f"{instance_url}/api/now/table/sys_update_set/{validated_params.changeset_id}"
    try:
        check_resp = requests.get(check_url, headers=headers)
        check_resp.raise_for_status()
        update_set = check_resp.json().get("result", {})
    except requests.exceptions.RequestException as e:
        return {"success": False, "message": f"Failed to fetch update set: {e}"}

    state = update_set.get("state", "")
    if state != "in progress":
        return {
            "success": False,
            "message": (
                f"Update set is in state '{state}', not 'in progress'. "
                "Only 'in progress' update sets can be made current."
            ),
            "update_set": update_set,
        }

    # Set as current via sys_user_preference
    pref_url = f"{instance_url}/api/now/table/sys_user_preference"
    pref_query_url = (
        f"{pref_url}?sysparm_query=name=sys_update_set^user.user_name=current&sysparm_limit=1"
    )
    try:
        # Check if preference record already exists
        pref_resp = requests.get(pref_query_url, headers=headers)
        pref_resp.raise_for_status()
        prefs = pref_resp.json().get("result", [])

        pref_data = {"value": validated_params.changeset_id}
        if prefs:
            pref_sys_id = prefs[0].get("sys_id", "")
            upd_resp = requests.patch(
                f"{pref_url}/{pref_sys_id}",
                json=pref_data,
                headers=headers,
            )
            upd_resp.raise_for_status()
        else:
            pref_data["name"] = "sys_update_set"
            crt_resp = requests.post(pref_url, json=pref_data, headers=headers)
            crt_resp.raise_for_status()

        normalized = _normalize_update_set(update_set)
        return {
            "success": True,
            "message": f"Update set '{update_set.get('name', validated_params.changeset_id)}' is now active.",
            "name": normalized.name,
            "sys_id": normalized.sys_id,
            "state": normalized.state,
            "is_default": normalized.is_default,
            "update_set": {
                "name": normalized.name,
                "sys_id": normalized.sys_id,
                "state": normalized.state,
                "is_default": normalized.is_default,
            },
        }
    except requests.exceptions.RequestException as e:
        return {"success": False, "message": f"Failed to set current update set: {e}"}
