"""
User role management tools for the ServiceNow MCP server.

This module provides tools for managing user and group role assignments in ServiceNow.
CRUD operations for sys_user and sys_user_group are handled by table_tools
(query_records / get_record / create_record / update_record / delete_record)
together with the architecture blueprint in architecture/user_architecture.md.
"""

import logging
from typing import Optional

import requests
from pydantic import BaseModel, Field

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.utils.config import ServerConfig

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Phase 8 — Role / Membership tools
# CONSTRAINT: NEVER set inherited=true. The platform creates inherited records
# automatically via Business Rules. Direct grants only.
# ---------------------------------------------------------------------------


class GrantRoleToUserParams(BaseModel):
    """Parameters for granting a role to a user."""

    user_sys_id: str = Field(
        ...,
        description="sys_id of the sys_user record to grant the role to.",
    )
    role_name: str = Field(
        ...,
        description="Name of the role to grant (e.g., 'itil', 'admin', 'catalog_admin').",
    )


class RevokeRoleFromUserParams(BaseModel):
    """Parameters for revoking a directly-granted role from a user."""

    user_sys_id: str = Field(
        ...,
        description="sys_id of the sys_user record.",
    )
    role_name: str = Field(
        ...,
        description="Name of the role to revoke. Only directly-granted (non-inherited) records are deleted.",
    )


class GrantRoleToGroupParams(BaseModel):
    """Parameters for granting a role to a group."""

    group_sys_id: str = Field(
        ...,
        description="sys_id of the sys_user_group record.",
    )
    role_name: str = Field(
        ...,
        description="Name of the role to grant to the group.",
    )


class RevokeRoleFromGroupParams(BaseModel):
    """Parameters for revoking a directly-granted role from a group."""

    group_sys_id: str = Field(
        ...,
        description="sys_id of the sys_user_group record.",
    )
    role_name: str = Field(
        ...,
        description="Name of the role to revoke. Only directly-granted records are deleted.",
    )



def get_role_id(
    config: ServerConfig,
    auth_manager: AuthManager,
    role_name: str,
) -> Optional[str]:
    """
    Get the sys_id of a role by its name.

    Args:
        config: Server configuration.
        auth_manager: Authentication manager.
        role_name: Name of the role.

    Returns:
        sys_id of the role if found, None otherwise.
    """
    api_url = f"{config.api_url}/table/sys_user_role"
    query_params = {
        "sysparm_query": f"name={role_name}",
        "sysparm_limit": "1",
    }

    try:
        response = requests.get(
            api_url,
            params=query_params,
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()

        result = response.json().get("result", [])
        if not result:
            return None

        return result[0].get("sys_id")

    except requests.RequestException as e:
        _body = e.response.text[:2000] if getattr(e, "response", None) is not None else ""
        logger.error(f"Failed to get role ID: {e}" + (f" | body={_body}" if _body else ""))
        return None


def grant_role_to_user(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: GrantRoleToUserParams,
) -> dict:
    """
    Grant a role to a user by creating a sys_user_has_role record.

    The platform automatically creates inherited records for contained roles —
    this tool never sets inherited=true. Use query_records on sys_user_has_role to confirm the grant.
    """
    role_id = get_role_id(config, auth_manager, params.role_name)
    if not role_id:
        return {
            "success": False,
            "message": f"Role '{params.role_name}' not found in sys_user_role.",
        }

    url = f"{config.api_url}/table/sys_user_has_role"
    try:
        # Check for an existing DIRECT grant only (inherited=false).
        # If user has role only via group membership (inherited record), we still create
        # a direct grant — inherited grants disappear when group membership changes.
        _direct_check_url = f"{config.api_url}/table/sys_user_has_role"
        _direct_resp = requests.get(
            _direct_check_url,
            params={
                "sysparm_query": f"user={params.user_sys_id}^role={role_id}^inherited=false",
                "sysparm_limit": "1",
            },
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        _direct_resp.raise_for_status()
        if _direct_resp.json().get("result"):
            return {
                "success": True,
                "message": f"User already has a direct grant for role '{params.role_name}'.",
                "sys_id": params.user_sys_id,
                "role_name": params.role_name,
                "already_exists": True,
            }

        response = requests.post(
            url,
            json={"user": params.user_sys_id, "role": role_id},
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()
        record = response.json().get("result", {})
        return {
            "success": True,
            "message": f"Role '{params.role_name}' granted to user {params.user_sys_id}.",
            "sys_id": record.get("sys_id", ""),
        }
    except requests.RequestException as e:
        _body = e.response.text[:2000] if getattr(e, "response", None) is not None else ""
        logger.error("grant_role_to_user | error=%s", e)
        return {
            "success": False,
            "message": f"Failed to grant role: {e}" + (f" | response: {_body}" if _body else ""),
        }


def revoke_role_from_user(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: RevokeRoleFromUserParams,
) -> dict:
    """
    Revoke a directly-granted role from a user.

    Only removes direct grants (inherited=false). Inherited records created by the
    platform are not touched — they are removed automatically when the source grant
    or group membership is removed.
    """
    role_id = get_role_id(config, auth_manager, params.role_name)
    if not role_id:
        return {
            "success": False,
            "message": f"Role '{params.role_name}' not found in sys_user_role.",
        }

    # Find the direct grant record
    url = f"{config.api_url}/table/sys_user_has_role"
    try:
        resp = requests.get(
            url,
            params={
                "sysparm_query": f"user={params.user_sys_id}^role={role_id}^inherited=false",
                "sysparm_limit": 1,
            },
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        resp.raise_for_status()
        results = resp.json().get("result", [])
        if not results:
            return {
                "success": False,
                "message": (
                    f"No direct grant of role '{params.role_name}' found for user "
                    f"{params.user_sys_id}. Inherited grants cannot be removed directly."
                ),
            }
        grant_sys_id = results[0]["sys_id"]
    except requests.RequestException as e:
        logger.error("revoke_role_from_user | lookup | error=%s", e)
        return {"success": False, "message": f"Failed to look up role grant: {e}"}

    # Delete the grant record
    try:
        del_resp = requests.delete(
            f"{url}/{grant_sys_id}",
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        del_resp.raise_for_status()
        return {
            "success": True,
            "message": f"Role '{params.role_name}' revoked from user {params.user_sys_id}.",
            "sys_id": grant_sys_id,
        }
    except requests.RequestException as e:
        _body = e.response.text[:2000] if getattr(e, "response", None) is not None else ""
        logger.error("revoke_role_from_user | delete | error=%s", e)
        return {
            "success": False,
            "message": f"Failed to delete role grant: {e}" + (f" | response: {_body}" if _body else ""),
        }


def grant_role_to_group(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: GrantRoleToGroupParams,
) -> dict:
    """
    Grant a role to a group by creating a sys_group_has_role record.

    The platform automatically propagates the role to all group members via
    inherited records. This tool never sets inherited=true.
    """
    role_id = get_role_id(config, auth_manager, params.role_name)
    if not role_id:
        return {
            "success": False,
            "message": f"Role '{params.role_name}' not found in sys_user_role.",
        }

    url = f"{config.api_url}/table/sys_group_has_role"
    try:
        response = requests.post(
            url,
            json={"group": params.group_sys_id, "role": role_id},
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()
        record = response.json().get("result", {})
        return {
            "success": True,
            "message": f"Role '{params.role_name}' granted to group {params.group_sys_id}.",
            "sys_id": record.get("sys_id", ""),
        }
    except requests.RequestException as e:
        _body = e.response.text[:2000] if getattr(e, "response", None) is not None else ""
        logger.error("grant_role_to_group | error=%s", e)
        return {
            "success": False,
            "message": f"Failed to grant role to group: {e}" + (f" | response: {_body}" if _body else ""),
        }


def revoke_role_from_group(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: RevokeRoleFromGroupParams,
) -> dict:
    """
    Revoke a directly-granted role from a group.

    Only removes direct grants (inherited=false). Inherited records are managed
    automatically by the platform.
    """
    role_id = get_role_id(config, auth_manager, params.role_name)
    if not role_id:
        return {
            "success": False,
            "message": f"Role '{params.role_name}' not found in sys_user_role.",
        }

    # Find the direct grant record
    url = f"{config.api_url}/table/sys_group_has_role"
    try:
        resp = requests.get(
            url,
            params={
                "sysparm_query": f"group={params.group_sys_id}^role={role_id}^inherited=false",
                "sysparm_limit": 1,
            },
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        resp.raise_for_status()
        results = resp.json().get("result", [])
        if not results:
            return {
                "success": False,
                "message": (
                    f"No direct grant of role '{params.role_name}' found for group "
                    f"{params.group_sys_id}. Inherited grants cannot be removed directly."
                ),
            }
        grant_sys_id = results[0]["sys_id"]
    except requests.RequestException as e:
        logger.error("revoke_role_from_group | lookup | error=%s", e)
        return {"success": False, "message": f"Failed to look up role grant: {e}"}

    # Delete the grant record
    try:
        del_resp = requests.delete(
            f"{url}/{grant_sys_id}",
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        del_resp.raise_for_status()
        return {
            "success": True,
            "message": f"Role '{params.role_name}' revoked from group {params.group_sys_id}.",
            "sys_id": grant_sys_id,
        }
    except requests.RequestException as e:
        _body = e.response.text[:2000] if getattr(e, "response", None) is not None else ""
        logger.error("revoke_role_from_group | delete | error=%s", e)
        return {
            "success": False,
            "message": f"Failed to delete role grant: {e}" + (f" | response: {_body}" if _body else ""),
        }


