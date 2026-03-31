"""
Changeset tools for the ServiceNow MCP server.

This module provides compound tools for managing update sets in ServiceNow.
CRUD operations (list, create, update, commit, publish, add_file) are handled
by table_tools (query_records / create_record / update_record) using the
sys_update_set architecture blueprint.
"""

import json
import logging
import re
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


class GetCurrentScopeParams(BaseModel):
    """Parameters for fetching the currently active application scope."""


class SetCurrentScopeParams(BaseModel):
    """Parameters for setting the currently active application scope."""

    app_id: str = Field(
        ...,
        description=(
            "Application picker app_id for the target scope. This is the same identifier "
            "used by the Next Experience application picker endpoint."
        ),
    )


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


def _parse_script_json_result(direct_output: str) -> Optional[Dict[str, Any]]:
    """
    Extract a JSON result object from background script direct_output.

    The output format from _extract_syslog_output is:
        [LEVEL] <user message> | run_id=<run_id>

    We strip the level prefix and the run_id suffix, then attempt JSON.loads
    on each line that looks like a JSON object containing "success".
    """
    level_prefix = re.compile(r"^\[(?:INFO|WARN|ERROR|DEBUG|\d+)\]\s*")
    for line in direct_output.splitlines():
        stripped = level_prefix.sub("", line).strip()
        # Strip " | run_id=..." suffix
        if " | run_id=" in stripped:
            stripped = stripped[: stripped.rfind(" | run_id=")].strip()
        if stripped.startswith("{") and '"success"' in stripped:
            try:
                return json.loads(stripped)
            except (json.JSONDecodeError, ValueError):
                continue
    return None


def _parse_scope_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    candidates: List[Dict[str, Any]] = [payload]
    for key in ("result", "data", "application", "picker"):
        nested = payload.get(key)
        if isinstance(nested, dict):
            candidates.append(nested)
    for candidate in list(candidates):
        for key in ("current", "selected", "value"):
            nested = candidate.get(key)
            if isinstance(nested, dict):
                candidates.append(nested)

    for candidate in candidates:
        app_id = candidate.get("app_id") or candidate.get("id") or candidate.get("sys_id") or candidate.get("value")
        scope_name = (
            candidate.get("scope")
            or candidate.get("scopeName")
            or candidate.get("name")
            or candidate.get("label")
            or candidate.get("displayValue")
            or candidate.get("display_value")
        )
        scope_display_name = (
            candidate.get("scopeDisplayName")
            or candidate.get("display_name")
            or candidate.get("displayName")
            or candidate.get("title")
            or scope_name
        )
        if isinstance(app_id, str) and app_id:
            return {
                "success": True,
                "app_id": app_id,
                "scope_name": scope_name if isinstance(scope_name, str) and scope_name else None,
                "scope_display_name": (
                    scope_display_name
                    if isinstance(scope_display_name, str) and scope_display_name
                    else (scope_name if isinstance(scope_name, str) and scope_name else None)
                ),
                "raw": payload,
            }

    return {
        "success": False,
        "message": "Could not parse application scope from picker response",
        "raw": payload,
    }


def _call_application_picker(
    config: ServerConfig,
    auth_manager: AuthManager,
    method: str,
    *,
    json_body: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    from servicenow_mcp.tools.script_tools import _get_ui_session

    session, csrf_token, failure_reason = _get_ui_session(config, auth_manager)
    if session is None:
        return {
            "success": False,
            "message": f"Could not establish authenticated UI session: {failure_reason}",
        }

    url = f"{config.instance_url.rstrip('/')}/api/now/ui/concoursepicker/application"
    headers = {"Accept": "application/json"}
    if csrf_token:
        headers["X-UserToken"] = csrf_token

    try:
        response = session.request(
            method.upper(),
            url,
            json=json_body,
            headers=headers,
            timeout=config.timeout,
        )
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.error(f"Error calling application picker endpoint: {e}")
        return {
            "success": False,
            "message": f"Error calling application picker endpoint: {str(e)}",
        }

    try:
        payload = response.json()
    except ValueError:
        return {
            "success": False,
            "message": "Application picker returned non-JSON response",
            "status_code": response.status_code,
        }

    parsed = _parse_scope_payload(payload)
    if not parsed.get("success"):
        parsed["status_code"] = response.status_code
    return parsed


def get_current_update_set(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: Union[Dict[str, Any], GetCurrentUpdateSetParams, None] = None,
) -> Dict[str, Any]:
    """
    Get the currently active update set for the authenticated user.

    Uses GlideUpdateSet.getOrCreate() — the same read path used by UpdateSetAjax
    (the UI's authoritative mechanism for update set management).
    """
    from servicenow_mcp.tools.script_tools import RunBackgroundScriptParams, run_background_script

    script = """\
// Use GlideUpdateSet.getOrCreate() — same read path as UpdateSetAjax.getUpdateSets()
var gus = new GlideUpdateSet();
var currentSysId = gus.getOrCreate();

if (!currentSysId) {
    gs.info(JSON.stringify({success: false, message: 'No active update set found for current user'}) + ' | run_id=' + __MFCP_RUN_ID);
} else {
    var us = new GlideRecord('sys_update_set');
    if (!us.get(currentSysId)) {
        gs.info(JSON.stringify({success: false, message: 'Update set record not found: ' + currentSysId}) + ' | run_id=' + __MFCP_RUN_ID);
    } else {
        var usName = us.getDisplayValue('name');
        var nameLower = usName.toLowerCase();
        var isDefault = (nameLower === 'default' || nameLower === 'default [global]' || nameLower.indexOf('default [') === 0);
        gs.info(JSON.stringify({
            success: true,
            name: usName,
            sys_id: us.getUniqueValue(),
            state: us.getValue('state'),
            is_default: isDefault
        }) + ' | run_id=' + __MFCP_RUN_ID);
    }
}
"""

    bg = run_background_script(
        config,
        auth_manager,
        RunBackgroundScriptParams(
            description="Read current update set via GlideUpdateSet.getOrCreate() — no writes.",
            script=script,
        ),
    )

    if not bg.success:
        return {"success": False, "message": f"Background script failed: {bg.message}"}

    data = _parse_script_json_result(bg.direct_output)
    if data is None:
        return {
            "success": False,
            "message": f"Could not parse update set result from script output: {bg.direct_output[:300]}",
        }

    if not data.get("success"):
        return data

    normalized = UpdateSetInfo(
        name=data.get("name"),
        sys_id=data.get("sys_id"),
        state=data.get("state"),
        is_default=bool(data.get("is_default")),
    )
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


def get_current_scope(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: Union[Dict[str, Any], GetCurrentScopeParams, None] = None,
) -> Dict[str, Any]:
    """
    Get the currently active Next Experience application scope for the authenticated UI session.

    Uses the same application picker endpoint that the ServiceNow UI and tools like SN Utils use.
    """
    result = _call_application_picker(config, auth_manager, "GET")
    if not result.get("success"):
        return result

    return {
        "success": True,
        "app_id": result.get("app_id"),
        "scope_name": result.get("scope_name"),
        "scope_display_name": result.get("scope_display_name"),
    }


def set_current_scope(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: Union[Dict[str, Any], SetCurrentScopeParams],
) -> Dict[str, Any]:
    """
    Set the currently active Next Experience application scope for the authenticated UI session.

    Sends a PUT to /api/now/ui/concoursepicker/application with the selected app_id, mirroring
    the behavior of the platform application picker.
    """
    result = _unwrap_and_validate_params(
        params,
        SetCurrentScopeParams,
        required_fields=["app_id"],
    )
    if not result["success"]:
        return result

    app_id = result["params"].app_id.strip()
    if not app_id:
        return {"success": False, "message": "app_id cannot be empty"}

    picker_result = _call_application_picker(
        config,
        auth_manager,
        "PUT",
        json_body={"app_id": app_id},
    )
    if not picker_result.get("success"):
        return picker_result

    return {
        "success": True,
        "message": (
            f"Application scope set to "
            f"{picker_result.get('scope_display_name') or picker_result.get('scope_name') or app_id}."
        ),
        "app_id": picker_result.get("app_id"),
        "scope_name": picker_result.get("scope_name"),
        "scope_display_name": picker_result.get("scope_display_name"),
    }


def set_current_update_set(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: Union[Dict[str, Any], SetCurrentUpdateSetParams],
) -> Dict[str, Any]:
    """
    Activate an update set as the current working set for the authenticated user.

    Runs a background script that calls GlideUpdateSet.set(sys_id) — the exact
    same server-side call made by UpdateSetAjax.changeUpdateSet(), which backs
    the "Make This My Current Set" UI action.

    Args:
        config: The server configuration.
        auth_manager: The authentication manager.
        params: The changeset_id to activate.

    Returns:
        Success status with the activated update set details.
    """
    from servicenow_mcp.tools.script_tools import RunBackgroundScriptParams, run_background_script

    result = _unwrap_and_validate_params(
        params,
        SetCurrentUpdateSetParams,
        required_fields=["changeset_id"],
    )
    if not result["success"]:
        return result

    changeset_id = result["params"].changeset_id

    # Sanitise — sys_ids are hex + hyphens only; reject anything else before interpolation
    if not re.fullmatch(r"[0-9a-fA-F\-]{32,}", changeset_id):
        return {"success": False, "message": f"Invalid changeset_id format: {changeset_id!r}"}

    script = f"""\
var targetSysId = '{changeset_id}';
var us = new GlideRecord('sys_update_set');
if (!us.get(targetSysId)) {{
    gs.info(JSON.stringify({{success: false, message: 'Update set not found: ' + targetSysId}}) + ' | run_id=' + __MFCP_RUN_ID);
}} else {{
    var state = us.getValue('state');
    if (state !== 'in progress') {{
        gs.info(JSON.stringify({{success: false, message: 'Update set state is "' + state + '", must be "in progress"'}}) + ' | run_id=' + __MFCP_RUN_ID);
    }} else {{
        // Use GlideUpdateSet.set() — exact same call as UpdateSetAjax.changeUpdateSet()
        var gus = new GlideUpdateSet();
        gus.set(targetSysId);

        var usName = us.getDisplayValue('name');
        var nameLower = usName.toLowerCase();
        var isDefault = (nameLower === 'default' || nameLower === 'default [global]' || nameLower.indexOf('default [') === 0);
        gs.info(JSON.stringify({{
            success: true,
            name: usName,
            sys_id: us.getUniqueValue(),
            state: state,
            is_default: isDefault
        }}) + ' | run_id=' + __MFCP_RUN_ID);
    }}
}}
"""

    bg = run_background_script(
        config,
        auth_manager,
        RunBackgroundScriptParams(
            description=f"Activate update set {changeset_id} as current via GlideUpdateSet.set() — mirrors UpdateSetAjax.changeUpdateSet().",
            script=script,
        ),
    )

    if not bg.success:
        return {"success": False, "message": f"Background script failed: {bg.message}"}

    data = _parse_script_json_result(bg.direct_output)
    if data is None:
        return {
            "success": False,
            "message": f"Could not parse result from script output: {bg.direct_output[:300]}",
        }

    if not data.get("success"):
        return data

    normalized = UpdateSetInfo(
        name=data.get("name"),
        sys_id=data.get("sys_id"),
        state=data.get("state"),
        is_default=bool(data.get("is_default")),
    )
    return {
        "success": True,
        "message": f"Update set '{normalized.name}' is now active.",
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
