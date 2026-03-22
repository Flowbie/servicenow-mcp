"""
System tools for the ServiceNow MCP server.

Provides tools for querying instance-level system information:
- get_current_user: Identify the authenticated API user

sys_properties CRUD is handled by table_tools (query_records / get_record /
create_record / update_record / delete_record) using the sys_properties table.
"""

import logging
from typing import Any, Dict, Optional

import requests
from pydantic import BaseModel, Field

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.utils.config import ServerConfig

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# get_current_user
# ---------------------------------------------------------------------------


class GetCurrentUserParams(BaseModel):
    """Parameters for get_current_user (no required fields)."""

    include_roles: bool = Field(
        default=False,
        description=(
            "If True, also fetch the user's active roles from sys_user_has_role. "
            "Adds a second API call. Default False."
        ),
    )


def get_current_user(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: GetCurrentUserParams,
) -> Dict[str, Any]:
    """
    Retrieve information about the currently authenticated API user.

    Attempts the /api/now/ui/user/current_user endpoint first (fastest).
    Falls back to querying sys_user with the user_name from the session.
    Optionally returns the user's roles from sys_user_has_role.

    Use this to confirm which account the MCP server is acting as, verify
    role assignments, or retrieve the sys_id for assigning records.
    """
    # Try the UI endpoint first — returns user info without a sys_user query
    ui_url = f"{config.instance_url}/api/now/ui/user/current_user"
    user_data: Dict[str, Any] = {}

    try:
        ui_resp = requests.get(
            ui_url,
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        if ui_resp.status_code == 200:
            result = ui_resp.json().get("result", {})
            user_data = {
                "sys_id": result.get("user_sys_id") or result.get("sys_id", ""),
                "user_name": result.get("user_name", ""),
                "display_name": result.get("display_name", ""),
                "email": result.get("email", ""),
                "source": "ui_endpoint",
            }
    except requests.RequestException:
        pass  # Fall through to sys_user query

    # Fallback: get user_name from basic auth config, then query sys_user
    if not user_data:
        user_name = _get_auth_username(config)
        if user_name:
            try:
                su_url = f"{config.api_url}/table/sys_user"
                su_resp = requests.get(
                    su_url,
                    params={
                        "sysparm_query": f"user_name={user_name}",
                        "sysparm_fields": "sys_id,user_name,name,email,active",
                        "sysparm_limit": 1,
                    },
                    headers=auth_manager.get_headers(),
                    timeout=config.timeout,
                )
                su_resp.raise_for_status()
                records = su_resp.json().get("result", [])
                if records:
                    rec = records[0]
                    user_data = {
                        "sys_id": rec.get("sys_id", ""),
                        "user_name": rec.get("user_name", ""),
                        "display_name": rec.get("name", ""),
                        "email": rec.get("email", ""),
                        "source": "sys_user_table",
                    }
            except requests.RequestException as e:
                logger.error("get_current_user | sys_user fallback failed | error=%s", e)

    if not user_data:
        return {
            "success": False,
            "error": "Could not determine current user from UI endpoint or sys_user table.",
        }

    # Optionally fetch roles
    if params.include_roles and user_data.get("sys_id"):
        try:
            roles_url = f"{config.api_url}/table/sys_user_has_role"
            roles_resp = requests.get(
                roles_url,
                params={
                    "sysparm_query": f"user={user_data['sys_id']}^state=active",
                    "sysparm_fields": "role.name,role.sys_id",
                    "sysparm_limit": 200,
                    "sysparm_display_value": "true",
                },
                headers=auth_manager.get_headers(),
                timeout=config.timeout,
            )
            roles_resp.raise_for_status()
            role_records = roles_resp.json().get("result", [])
            user_data["roles"] = [
                r.get("role", {}).get("display_value", r.get("role", ""))
                for r in role_records
            ]
        except requests.RequestException as e:
            logger.warning("get_current_user | roles fetch failed | error=%s", e)
            user_data["roles"] = []
            user_data["roles_error"] = str(e)

    return {"success": True, "user": user_data}


def _get_auth_username(config: ServerConfig) -> Optional[str]:
    """Extract the configured username from auth config for sys_user fallback."""
    auth = config.auth
    if auth.basic:
        return auth.basic.username
    if auth.oauth:
        return getattr(auth.oauth, "username", None)
    return None
