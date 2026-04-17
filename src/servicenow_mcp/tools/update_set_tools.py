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
from collections import Counter
from typing import Any, Dict, List, Optional, Type, TypeVar, Union

import requests
from pydantic import BaseModel, Field, model_validator

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.utils.config import ServerConfig
from servicenow_mcp.utils.response_envelope import SnowResponse
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
            "Scope name (e.g. 'sn_grc', 'global', 'x_acme_app') or sys_id of the "
            "target application scope from the sys_scope table."
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
            acknowledge_update_set_bypass=True,
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
    Get the currently active application scope for the authenticated user.

    Uses gs.getCurrentApplicationId() via background script — works with
    standard REST API credentials (no browser session required).
    """
    from servicenow_mcp.tools.script_tools import RunBackgroundScriptParams, run_background_script

    script = """\
var appId = gs.getCurrentApplicationId();
if (!appId) {
    gs.info(JSON.stringify({success: false, message: 'No current application scope'}) + ' | run_id=' + __MFCP_RUN_ID);
} else {
    var scopeGr = new GlideRecord('sys_scope');
    if (scopeGr.get(appId)) {
        gs.info(JSON.stringify({
            success: true,
            app_id: appId,
            scope_name: scopeGr.getValue('scope'),
            scope_display_name: scopeGr.getDisplayValue('name')
        }) + ' | run_id=' + __MFCP_RUN_ID);
    } else {
        gs.info(JSON.stringify({
            success: true,
            app_id: appId,
            scope_name: null,
            scope_display_name: null
        }) + ' | run_id=' + __MFCP_RUN_ID);
    }
}
"""

    bg = run_background_script(
        config,
        auth_manager,
        RunBackgroundScriptParams(
            description="Read current application scope via gs.getCurrentApplicationId() — no writes.",
            script=script,
            acknowledge_update_set_bypass=True,
        ),
    )

    if not bg.success:
        return {"success": False, "message": f"Background script failed: {bg.message}"}

    data = _parse_script_json_result(bg.direct_output)
    if data is None:
        return {
            "success": False,
            "message": f"Could not parse scope result from script output: {bg.direct_output[:300]}",
        }

    return data


def set_current_scope(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: Union[Dict[str, Any], SetCurrentScopeParams],
) -> Dict[str, Any]:
    """
    Set the currently active application scope for the authenticated user.

    Uses gs.setCurrentApplicationId() via background script — works with
    standard REST API credentials (no browser session required).

    app_id accepts either a scope name (e.g. 'sn_grc', 'global') or a sys_id.
    """
    from servicenow_mcp.tools.script_tools import RunBackgroundScriptParams, run_background_script

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

    # Sanitise — scope names are alphanumeric + underscore; sys_ids are hex + hyphens
    if not re.fullmatch(r"[a-zA-Z0-9_\-]+", app_id):
        return {"success": False, "message": f"Invalid app_id format: {app_id!r}"}

    script = f"""\
var appId = '{app_id}';
// Try by scope name first, then by sys_id
var scopeGr = new GlideRecord('sys_scope');
var found = scopeGr.get('scope', appId);
if (!found) {{
    scopeGr = new GlideRecord('sys_scope');
    found = scopeGr.get(appId);
}}
if (!found) {{
    gs.info(JSON.stringify({{success: false, message: 'Application scope not found: ' + appId}}) + ' | run_id=' + __MFCP_RUN_ID);
}} else {{
    var sysId = scopeGr.getUniqueValue();
    gs.setCurrentApplicationId(sysId);
    gs.info(JSON.stringify({{
        success: true,
        app_id: sysId,
        scope_name: scopeGr.getValue('scope'),
        scope_display_name: scopeGr.getDisplayValue('name')
    }}) + ' | run_id=' + __MFCP_RUN_ID);
}}
"""

    bg = run_background_script(
        config,
        auth_manager,
        RunBackgroundScriptParams(
            description=f"Set application scope to {app_id!r} via gs.setCurrentApplicationId().",
            script=script,
            acknowledge_update_set_bypass=True,
        ),
    )

    if not bg.success:
        return {"success": False, "message": f"Background script failed: {bg.message}"}

    data = _parse_script_json_result(bg.direct_output)
    if data is None:
        return {
            "success": False,
            "message": f"Could not parse scope result from script output: {bg.direct_output[:300]}",
        }

    if not data.get("success"):
        return data

    return {
        "success": True,
        "message": f"Application scope set to {data.get('scope_display_name') or data.get('scope_name') or app_id}.",
        "app_id": data.get("app_id"),
        "scope_name": data.get("scope_name"),
        "scope_display_name": data.get("scope_display_name"),
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
            acknowledge_update_set_bypass=True,
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


# ── New Enhanced Update Set Tools (Task 6) ────────────────────────────────


class MoveRecordsToUpdateSetParams(BaseModel):
    target_update_set_sys_id: str = Field(
        ..., description="sys_id of the destination update set (must be 'in progress')"
    )
    source_update_set_sys_id: Optional[str] = Field(
        default=None,
        description="Move all records currently in this source update set to the target.",
    )
    record_sys_ids: Optional[List[str]] = Field(
        default=None,
        description="Move only these specific sys_update_xml sys_ids.",
    )
    time_range_start: Optional[str] = Field(
        default=None,
        description="ISO 8601 timestamp. Move records with sys_created_on >= this value.",
    )
    time_range_end: Optional[str] = Field(
        default=None,
        description="ISO 8601 timestamp. Move records with sys_created_on <= this value.",
    )

    @model_validator(mode="after")
    def require_at_least_one_filter(self) -> "MoveRecordsToUpdateSetParams":
        has_filter = (
            self.source_update_set_sys_id is not None
            or self.record_sys_ids is not None
            or self.time_range_start is not None
            or self.time_range_end is not None
        )
        if not has_filter:
            raise ValueError(
                "Provide at least one filter: source_update_set_sys_id, record_sys_ids, "
                "or time_range_start/time_range_end."
            )
        return self


class InspectUpdateSetParams(BaseModel):
    update_set_sys_id: str = Field(..., description="sys_id of the update set to inspect")
    include_dependencies: bool = Field(
        default=False,
        description="Include cross-reference analysis. Slower — requires additional API calls.",
    )


class CloneUpdateSetParams(BaseModel):
    source_sys_id: str = Field(..., description="sys_id of the update set to clone")
    new_name: str = Field(..., min_length=3, description="Name for the cloned update set")
    start_as_in_progress: bool = Field(
        default=True,
        description="New update set state. True = 'in progress', False = 'complete'.",
    )


def move_records_to_update_set(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: MoveRecordsToUpdateSetParams,
) -> dict:
    headers = auth_manager.get_headers()
    base_url = f"{config.api_url}/table/sys_update_xml"

    query_parts: List[str] = []
    if params.source_update_set_sys_id:
        query_parts.append(f"update_set={params.source_update_set_sys_id}")
    if params.time_range_start:
        query_parts.append(f"sys_created_on>={params.time_range_start}")
    if params.time_range_end:
        query_parts.append(f"sys_created_on<={params.time_range_end}")
    if params.record_sys_ids:
        sys_id_query = "^OR^".join(f"sys_id={sid}" for sid in params.record_sys_ids)
        query_parts.append(f"({sys_id_query})")

    encoded_query = "^".join(query_parts)

    fetch_resp = requests.get(
        base_url,
        headers=headers,
        params={"sysparm_query": encoded_query, "sysparm_fields": "sys_id,name,type", "sysparm_limit": 1000},
        timeout=config.timeout,
    )
    fetch_resp.raise_for_status()
    records = fetch_resp.json().get("result", [])

    if not records:
        return SnowResponse(
            success=True,
            data={"moved": 0, "skipped": 0, "errors": []},
            operation="move_records_to_update_set",
        ).to_dict()

    moved, errors = 0, []
    for rec in records:
        patch_resp = requests.patch(
            f"{base_url}/{rec['sys_id']}",
            headers=headers,
            json={"update_set": params.target_update_set_sys_id},
            timeout=config.timeout,
        )
        if patch_resp.status_code in (200, 201):
            moved += 1
        else:
            errors.append({"sys_id": rec["sys_id"], "name": rec.get("name"), "http_status": patch_resp.status_code})

    return SnowResponse(
        success=len(errors) == 0,
        data={"moved": moved, "failed": len(errors), "errors": errors},
        operation="move_records_to_update_set",
        warnings=[f"{len(errors)} records failed to move"] if errors else [],
    ).to_dict()


def inspect_update_set(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: InspectUpdateSetParams,
) -> dict:
    headers = auth_manager.get_headers()
    base = config.api_url

    us_resp = requests.get(
        f"{base}/table/sys_update_set",
        headers=headers,
        params={
            "sysparm_query": f"sys_id={params.update_set_sys_id}",
            "sysparm_fields": "sys_id,name,state,application,description,sys_created_on",
            "sysparm_limit": 1,
        },
        timeout=config.timeout,
    )
    us_resp.raise_for_status()
    us_records = us_resp.json().get("result", [])
    if not us_records:
        return SnowResponse(
            success=False,
            error=f"Update set not found: {params.update_set_sys_id}",
            operation="inspect_update_set",
        ).to_dict()
    us = us_records[0]

    xml_resp = requests.get(
        f"{base}/table/sys_update_xml",
        headers=headers,
        params={
            "sysparm_query": f"update_set={params.update_set_sys_id}",
            "sysparm_fields": "sys_id,name,type,action,sys_created_on",
            "sysparm_limit": 1000,
        },
        timeout=config.timeout,
    )
    xml_resp.raise_for_status()
    xml_records = xml_resp.json().get("result", [])

    by_type = dict(Counter(r.get("type", "Unknown") for r in xml_records))
    by_action = dict(Counter(r.get("action", "Unknown") for r in xml_records))

    data: dict = {
        "update_set": {
            "sys_id": us.get("sys_id"),
            "name": us.get("name"),
            "state": us.get("state"),
            "application": us.get("application", {}).get("value") if isinstance(us.get("application"), dict) else us.get("application"),
            "created_on": us.get("sys_created_on"),
        },
        "total_records": len(xml_records),
        "by_type": by_type,
        "by_action": by_action,
        "records": xml_records[:50],
    }

    if len(xml_records) > 50:
        data["note"] = f"Showing 50 of {len(xml_records)} records. Use query_records on sys_update_xml for the full list."

    return SnowResponse(
        success=True,
        data=data,
        table="sys_update_set",
        operation="inspect_update_set",
    ).to_dict()


def clone_update_set(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: CloneUpdateSetParams,
) -> dict:
    headers = auth_manager.get_headers()
    base = config.api_url

    src_resp = requests.get(
        f"{base}/table/sys_update_set",
        headers=headers,
        params={
            "sysparm_query": f"sys_id={params.source_sys_id}",
            "sysparm_fields": "sys_id,name,application,description",
            "sysparm_limit": 1,
        },
        timeout=config.timeout,
    )
    src_resp.raise_for_status()
    src_list = src_resp.json().get("result", [])
    if not src_list:
        return SnowResponse(
            success=False,
            error=f"Source update set not found: {params.source_sys_id}",
            operation="clone_update_set",
        ).to_dict()
    source = src_list[0]

    new_state = "in progress" if params.start_as_in_progress else "complete"
    create_resp = requests.post(
        f"{base}/table/sys_update_set",
        headers=headers,
        json={
            "name": params.new_name,
            "application": (source.get("application", {}).get("value") if isinstance(source.get("application"), dict) else source.get("application")) or "",
            "state": new_state,
            "description": f"Clone of '{source.get('name')}'. {source.get('description', '')}".strip(),
        },
        timeout=config.timeout,
    )
    create_resp.raise_for_status()
    new_us = create_resp.json().get("result", {})
    new_sys_id = new_us.get("sys_id")

    xml_resp = requests.get(
        f"{base}/table/sys_update_xml",
        headers=headers,
        params={
            "sysparm_query": f"update_set={params.source_sys_id}",
            "sysparm_fields": "sys_id",
            "sysparm_limit": 1000,
        },
        timeout=config.timeout,
    )
    xml_resp.raise_for_status()
    xml_records = xml_resp.json().get("result", [])

    copied, errors = 0, []
    for rec in xml_records:
        patch_resp = requests.patch(
            f"{base}/table/sys_update_xml/{rec['sys_id']}",
            headers=headers,
            json={"update_set": new_sys_id},
            timeout=config.timeout,
        )
        if patch_resp.status_code in (200, 201):
            copied += 1
        else:
            errors.append(rec["sys_id"])

    return SnowResponse(
        success=len(errors) == 0,
        data={
            "source_update_set_sys_id": params.source_sys_id,
            "new_update_set_sys_id": new_sys_id,
            "new_update_set_name": params.new_name,
            "records_copied": copied,
            "failed": len(errors),
        },
        table="sys_update_set",
        operation="clone_update_set",
        warnings=[f"{len(errors)} records failed to copy"] if errors else [],
    ).to_dict()
