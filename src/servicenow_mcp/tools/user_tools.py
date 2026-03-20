"""
User management tools for the ServiceNow MCP server.

This module provides tools for managing users and groups in ServiceNow.
"""

import logging
from typing import List, Optional

import requests
from pydantic import BaseModel, Field

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.utils.config import ServerConfig

logger = logging.getLogger(__name__)


class CreateUserParams(BaseModel):
    """Parameters for creating a user."""

    user_name: str = Field(..., description="Username for the user")
    first_name: str = Field(..., description="First name of the user")
    last_name: str = Field(..., description="Last name of the user")
    email: str = Field(..., description="Email address of the user")
    title: Optional[str] = Field(None, description="Job title of the user")
    department: Optional[str] = Field(None, description="Department the user belongs to")
    manager: Optional[str] = Field(None, description="Manager of the user (sys_id or username)")
    roles: Optional[List[str]] = Field(None, description="Roles to assign to the user")
    phone: Optional[str] = Field(None, description="Phone number of the user")
    mobile_phone: Optional[str] = Field(None, description="Mobile phone number of the user")
    location: Optional[str] = Field(None, description="Location of the user")
    password: Optional[str] = Field(None, description="Password for the user account")
    active: Optional[bool] = Field(True, description="Whether the user account is active")


class UpdateUserParams(BaseModel):
    """Parameters for updating a user."""

    user_id: str = Field(..., description="User ID or sys_id to update")
    user_name: Optional[str] = Field(None, description="Username for the user")
    first_name: Optional[str] = Field(None, description="First name of the user")
    last_name: Optional[str] = Field(None, description="Last name of the user")
    email: Optional[str] = Field(None, description="Email address of the user")
    title: Optional[str] = Field(None, description="Job title of the user")
    department: Optional[str] = Field(None, description="Department the user belongs to")
    manager: Optional[str] = Field(None, description="Manager of the user (sys_id or username)")
    roles: Optional[List[str]] = Field(None, description="Roles to assign to the user")
    phone: Optional[str] = Field(None, description="Phone number of the user")
    mobile_phone: Optional[str] = Field(None, description="Mobile phone number of the user")
    location: Optional[str] = Field(None, description="Location of the user")
    password: Optional[str] = Field(None, description="Password for the user account")
    active: Optional[bool] = Field(None, description="Whether the user account is active")


class GetUserParams(BaseModel):
    """Parameters for getting a user."""

    user_id: Optional[str] = Field(None, description="User ID or sys_id")
    user_name: Optional[str] = Field(None, description="Username of the user")
    email: Optional[str] = Field(None, description="Email address of the user")


class ListUsersParams(BaseModel):
    """Parameters for listing users."""

    limit: int = Field(10, description="Maximum number of users to return")
    offset: int = Field(0, description="Offset for pagination")
    active: Optional[bool] = Field(None, description="Filter by active status")
    department: Optional[str] = Field(None, description="Filter by department")
    query: Optional[str] = Field(
        None,
        description="Case-insensitive search term that matches against name, username, or email fields. Uses ServiceNow's LIKE operator for partial matching.",
    )


class CreateGroupParams(BaseModel):
    """Parameters for creating a group."""

    name: str = Field(..., description="Name of the group")
    description: Optional[str] = Field(None, description="Description of the group")
    manager: Optional[str] = Field(None, description="Manager of the group (sys_id or username)")
    parent: Optional[str] = Field(None, description="Parent group (sys_id or name)")
    type: Optional[str] = Field(None, description="Type of the group")
    email: Optional[str] = Field(None, description="Email address for the group")
    members: Optional[List[str]] = Field(
        None, description="List of user sys_ids or usernames to add as members"
    )
    active: Optional[bool] = Field(True, description="Whether the group is active")


class UpdateGroupParams(BaseModel):
    """Parameters for updating a group."""

    group_id: str = Field(..., description="Group ID or sys_id to update")
    name: Optional[str] = Field(None, description="Name of the group")
    description: Optional[str] = Field(None, description="Description of the group")
    manager: Optional[str] = Field(None, description="Manager of the group (sys_id or username)")
    parent: Optional[str] = Field(None, description="Parent group (sys_id or name)")
    type: Optional[str] = Field(None, description="Type of the group")
    email: Optional[str] = Field(None, description="Email address for the group")
    active: Optional[bool] = Field(None, description="Whether the group is active")


class AddGroupMembersParams(BaseModel):
    """Parameters for adding members to a group."""

    group_id: str = Field(..., description="Group ID or sys_id")
    members: List[str] = Field(
        ..., description="List of user sys_ids or usernames to add as members"
    )


class RemoveGroupMembersParams(BaseModel):
    """Parameters for removing members from a group."""

    group_id: str = Field(..., description="Group ID or sys_id")
    members: List[str] = Field(
        ..., description="List of user sys_ids or usernames to remove as members"
    )


class ListGroupsParams(BaseModel):
    """Parameters for listing groups."""

    limit: int = Field(10, description="Maximum number of groups to return")
    offset: int = Field(0, description="Offset for pagination")
    active: Optional[bool] = Field(None, description="Filter by active status")
    query: Optional[str] = Field(
        None,
        description="Case-insensitive search term that matches against group name or description fields. Uses ServiceNow's LIKE operator for partial matching.",
    )
    type: Optional[str] = Field(None, description="Filter by group type")


class UserResponse(BaseModel):
    """Response from user operations."""

    success: bool = Field(..., description="Whether the operation was successful")
    message: str = Field(..., description="Message describing the result")
    user_id: Optional[str] = Field(None, description="ID of the affected user")
    user_name: Optional[str] = Field(None, description="Username of the affected user")


class GroupResponse(BaseModel):
    """Response from group operations."""

    success: bool = Field(..., description="Whether the operation was successful")
    message: str = Field(..., description="Message describing the result")
    group_id: Optional[str] = Field(None, description="ID of the affected group")
    group_name: Optional[str] = Field(None, description="Name of the affected group")


def create_user(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: CreateUserParams,
) -> UserResponse:
    """
    Create a new user in ServiceNow.

    Args:
        config: Server configuration.
        auth_manager: Authentication manager.
        params: Parameters for creating the user.

    Returns:
        Response with the created user details.
    """
    api_url = f"{config.api_url}/table/sys_user"

    # Build request data
    data = {
        "user_name": params.user_name,
        "first_name": params.first_name,
        "last_name": params.last_name,
        "email": params.email,
        "active": str(params.active).lower(),
    }

    if params.title:
        data["title"] = params.title
    if params.department:
        data["department"] = params.department
    if params.manager:
        data["manager"] = params.manager
    if params.phone:
        data["phone"] = params.phone
    if params.mobile_phone:
        data["mobile_phone"] = params.mobile_phone
    if params.location:
        data["location"] = params.location
    if params.password:
        data["user_password"] = params.password

    # Make request
    try:
        response = requests.post(
            api_url,
            json=data,
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()

        result = response.json().get("result", {})

        # Handle role assignments if provided
        if params.roles and result.get("sys_id"):
            assign_roles_to_user(config, auth_manager, result.get("sys_id"), params.roles)

        return UserResponse(
            success=True,
            message="User created successfully",
            user_id=result.get("sys_id"),
            user_name=result.get("user_name"),
        )

    except requests.RequestException as e:
        _body = e.response.text[:2000] if getattr(e, "response", None) is not None else ""
        logger.error(f"Failed to create user: {e}" + (f" | body={_body}" if _body else ""))
        return UserResponse(
            success=False,
            message=f"Failed to create user: {str(e)}" + (f" | response: {_body}" if _body else ""),
        )


def update_user(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: UpdateUserParams,
) -> UserResponse:
    """
    Update an existing user in ServiceNow.

    Args:
        config: Server configuration.
        auth_manager: Authentication manager.
        params: Parameters for updating the user.

    Returns:
        Response with the updated user details.
    """
    api_url = f"{config.api_url}/table/sys_user/{params.user_id}"

    # Build request data
    data = {}
    if params.user_name:
        data["user_name"] = params.user_name
    if params.first_name:
        data["first_name"] = params.first_name
    if params.last_name:
        data["last_name"] = params.last_name
    if params.email:
        data["email"] = params.email
    if params.title:
        data["title"] = params.title
    if params.department:
        data["department"] = params.department
    if params.manager:
        data["manager"] = params.manager
    if params.phone:
        data["phone"] = params.phone
    if params.mobile_phone:
        data["mobile_phone"] = params.mobile_phone
    if params.location:
        data["location"] = params.location
    if params.password:
        data["user_password"] = params.password
    if params.active is not None:
        data["active"] = str(params.active).lower()

    # Make request
    try:
        response = requests.patch(
            api_url,
            json=data,
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()

        result = response.json().get("result", {})

        # Handle role assignments if provided
        if params.roles:
            assign_roles_to_user(config, auth_manager, params.user_id, params.roles)

        return UserResponse(
            success=True,
            message="User updated successfully",
            user_id=result.get("sys_id"),
            user_name=result.get("user_name"),
        )

    except requests.RequestException as e:
        _body = e.response.text[:2000] if getattr(e, "response", None) is not None else ""
        logger.error(f"Failed to update user: {e}" + (f" | body={_body}" if _body else ""))
        return UserResponse(
            success=False,
            message=f"Failed to update user: {str(e)}" + (f" | response: {_body}" if _body else ""),
        )


def get_user(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: GetUserParams,
) -> dict:
    """
    Get a user from ServiceNow.

    Args:
        config: Server configuration.
        auth_manager: Authentication manager.
        params: Parameters for getting the user.

    Returns:
        Dictionary containing user details.
    """
    api_url = f"{config.api_url}/table/sys_user"
    query_params = {}

    # Build query parameters
    if params.user_id:
        query_params["sysparm_query"] = f"sys_id={params.user_id}"
    elif params.user_name:
        query_params["sysparm_query"] = f"user_name={params.user_name}"
    elif params.email:
        query_params["sysparm_query"] = f"email={params.email}"
    else:
        return {"success": False, "message": "At least one search parameter is required"}

    query_params["sysparm_limit"] = "1"
    query_params["sysparm_display_value"] = "true"

    # Make request
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
            return {"success": False, "message": "User not found"}

        return {"success": True, "message": "User found", "user": result[0]}

    except requests.RequestException as e:
        _body = e.response.text[:2000] if getattr(e, "response", None) is not None else ""
        logger.error(f"Failed to get user: {e}" + (f" | body={_body}" if _body else ""))
        return {"success": False, "message": f"Failed to get user: {str(e)}" + (f" | response: {_body}" if _body else "")}


def list_users(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: ListUsersParams,
) -> dict:
    """
    List users from ServiceNow.

    Args:
        config: Server configuration.
        auth_manager: Authentication manager.
        params: Parameters for listing users.

    Returns:
        Dictionary containing list of users.
    """
    api_url = f"{config.api_url}/table/sys_user"
    query_params = {
        "sysparm_limit": str(params.limit),
        "sysparm_offset": str(params.offset),
        "sysparm_display_value": "true",
    }

    # Build query
    query_parts = []
    if params.active is not None:
        query_parts.append(f"active={str(params.active).lower()}")
    if params.department:
        query_parts.append(f"department={params.department}")
    if params.query:
        query_parts.append(
            f"^nameLIKE{params.query}^ORuser_nameLIKE{params.query}^ORemailLIKE{params.query}"
        )

    if query_parts:
        query_params["sysparm_query"] = "^".join(query_parts)

    # Make request
    try:
        response = requests.get(
            api_url,
            params=query_params,
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()

        result = response.json().get("result", [])

        return {
            "success": True,
            "message": f"Found {len(result)} users",
            "users": result,
            "count": len(result),
        }

    except requests.RequestException as e:
        _body = e.response.text[:2000] if getattr(e, "response", None) is not None else ""
        logger.error(f"Failed to list users: {e}" + (f" | body={_body}" if _body else ""))
        return {"success": False, "message": f"Failed to list users: {str(e)}" + (f" | response: {_body}" if _body else "")}


def list_groups(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: ListGroupsParams,
) -> dict:
    """
    List groups from ServiceNow.

    Args:
        config: Server configuration.
        auth_manager: Authentication manager.
        params: Parameters for listing groups.

    Returns:
        Dictionary containing list of groups.
    """
    api_url = f"{config.api_url}/table/sys_user_group"
    query_params = {
        "sysparm_limit": str(params.limit),
        "sysparm_offset": str(params.offset),
        "sysparm_display_value": "true",
    }

    # Build query
    query_parts = []
    if params.active is not None:
        query_parts.append(f"active={str(params.active).lower()}")
    if params.type:
        query_parts.append(f"type={params.type}")
    if params.query:
        query_parts.append(f"^nameLIKE{params.query}^ORdescriptionLIKE{params.query}")

    if query_parts:
        query_params["sysparm_query"] = "^".join(query_parts)

    # Make request
    try:
        response = requests.get(
            api_url,
            params=query_params,
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()

        result = response.json().get("result", [])

        return {
            "success": True,
            "message": f"Found {len(result)} groups",
            "groups": result,
            "count": len(result),
        }

    except requests.RequestException as e:
        _body = e.response.text[:2000] if getattr(e, "response", None) is not None else ""
        logger.error(f"Failed to list groups: {e}" + (f" | body={_body}" if _body else ""))
        return {"success": False, "message": f"Failed to list groups: {str(e)}" + (f" | response: {_body}" if _body else "")}


def assign_roles_to_user(
    config: ServerConfig,
    auth_manager: AuthManager,
    user_id: str,
    roles: List[str],
) -> bool:
    """
    Assign roles to a user in ServiceNow.

    Args:
        config: Server configuration.
        auth_manager: Authentication manager.
        user_id: User ID or sys_id.
        roles: List of roles to assign.

    Returns:
        Boolean indicating success.
    """
    # For each role, create a user_role record
    api_url = f"{config.api_url}/table/sys_user_has_role"

    success = True
    for role in roles:
        # First check if the role exists
        role_id = get_role_id(config, auth_manager, role)
        if not role_id:
            logger.warning(f"Role '{role}' not found, skipping assignment")
            continue

        # Check if the user already has this role
        if check_user_has_role(config, auth_manager, user_id, role_id):
            logger.info(f"User already has role '{role}', skipping assignment")
            continue

        # Create the user role assignment
        data = {
            "user": user_id,
            "role": role_id,
        }

        try:
            response = requests.post(
                api_url,
                json=data,
                headers=auth_manager.get_headers(),
                timeout=config.timeout,
            )
            response.raise_for_status()
        except requests.RequestException as e:
            _body = e.response.text[:2000] if getattr(e, "response", None) is not None else ""
            logger.error(f"Failed to assign role '{role}' to user: {e}" + (f" | body={_body}" if _body else ""))
            success = False

    return success


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


def check_user_has_role(
    config: ServerConfig,
    auth_manager: AuthManager,
    user_id: str,
    role_id: str,
) -> bool:
    """
    Check if a user has a specific role.

    Args:
        config: Server configuration.
        auth_manager: Authentication manager.
        user_id: User ID or sys_id.
        role_id: Role ID or sys_id.

    Returns:
        Boolean indicating whether the user has the role.
    """
    api_url = f"{config.api_url}/table/sys_user_has_role"
    query_params = {
        "sysparm_query": f"user={user_id}^role={role_id}",
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
        return len(result) > 0

    except requests.RequestException as e:
        _body = e.response.text[:2000] if getattr(e, "response", None) is not None else ""
        logger.error(f"Failed to check if user has role: {e}" + (f" | body={_body}" if _body else ""))
        return False


def create_group(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: CreateGroupParams,
) -> GroupResponse:
    """
    Create a new group in ServiceNow.

    Args:
        config: Server configuration.
        auth_manager: Authentication manager.
        params: Parameters for creating the group.

    Returns:
        Response with the created group details.
    """
    api_url = f"{config.api_url}/table/sys_user_group"

    # Build request data
    data = {
        "name": params.name,
        "active": str(params.active).lower(),
    }

    if params.description:
        data["description"] = params.description
    if params.manager:
        data["manager"] = params.manager
    if params.parent:
        data["parent"] = params.parent
    if params.type:
        data["type"] = params.type
    if params.email:
        data["email"] = params.email

    # Make request
    try:
        response = requests.post(
            api_url,
            json=data,
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()

        result = response.json().get("result", {})
        group_id = result.get("sys_id")

        # Add members if provided
        if params.members and group_id:
            add_group_members(
                config,
                auth_manager,
                AddGroupMembersParams(group_id=group_id, members=params.members),
            )

        return GroupResponse(
            success=True,
            message="Group created successfully",
            group_id=group_id,
            group_name=result.get("name"),
        )

    except requests.RequestException as e:
        _body = e.response.text[:2000] if getattr(e, "response", None) is not None else ""
        logger.error(f"Failed to create group: {e}" + (f" | body={_body}" if _body else ""))
        return GroupResponse(
            success=False,
            message=f"Failed to create group: {str(e)}" + (f" | response: {_body}" if _body else ""),
        )


def update_group(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: UpdateGroupParams,
) -> GroupResponse:
    """
    Update an existing group in ServiceNow.

    Args:
        config: Server configuration.
        auth_manager: Authentication manager.
        params: Parameters for updating the group.

    Returns:
        Response with the updated group details.
    """
    api_url = f"{config.api_url}/table/sys_user_group/{params.group_id}"

    # Build request data
    data = {}
    if params.name:
        data["name"] = params.name
    if params.description:
        data["description"] = params.description
    if params.manager:
        data["manager"] = params.manager
    if params.parent:
        data["parent"] = params.parent
    if params.type:
        data["type"] = params.type
    if params.email:
        data["email"] = params.email
    if params.active is not None:
        data["active"] = str(params.active).lower()

    # Make request
    try:
        response = requests.patch(
            api_url,
            json=data,
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()

        result = response.json().get("result", {})

        return GroupResponse(
            success=True,
            message="Group updated successfully",
            group_id=result.get("sys_id"),
            group_name=result.get("name"),
        )

    except requests.RequestException as e:
        _body = e.response.text[:2000] if getattr(e, "response", None) is not None else ""
        logger.error(f"Failed to update group: {e}" + (f" | body={_body}" if _body else ""))
        return GroupResponse(
            success=False,
            message=f"Failed to update group: {str(e)}" + (f" | response: {_body}" if _body else ""),
        )


def add_group_members(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: AddGroupMembersParams,
) -> GroupResponse:
    """
    Add members to a group in ServiceNow.

    Args:
        config: Server configuration.
        auth_manager: Authentication manager.
        params: Parameters for adding members to the group.

    Returns:
        Response with the result of the operation.
    """
    api_url = f"{config.api_url}/table/sys_user_grmember"

    success = True
    failed_members = []

    for member in params.members:
        # Get user ID if username is provided
        user_id = member
        if not member.startswith("sys_id:"):
            user = get_user(config, auth_manager, GetUserParams(user_name=member))
            if not user.get("success"):
                user = get_user(config, auth_manager, GetUserParams(email=member))

            if user.get("success"):
                user_id = user.get("user", {}).get("sys_id")
            else:
                success = False
                failed_members.append(member)
                continue

        # Create group membership
        data = {
            "group": params.group_id,
            "user": user_id,
        }

        try:
            response = requests.post(
                api_url,
                json=data,
                headers=auth_manager.get_headers(),
                timeout=config.timeout,
            )
            response.raise_for_status()
        except requests.RequestException as e:
            _body = e.response.text[:2000] if getattr(e, "response", None) is not None else ""
            logger.error(f"Failed to add member '{member}' to group: {e}" + (f" | body={_body}" if _body else ""))
            success = False
            failed_members.append(member)

    if failed_members:
        message = f"Some members could not be added to the group: {', '.join(failed_members)}"
    else:
        message = "All members added to the group successfully"

    return GroupResponse(
        success=success,
        message=message,
        group_id=params.group_id,
    )


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


class ListUserRolesParams(BaseModel):
    """Parameters for listing a user's roles."""

    user_sys_id: str = Field(
        ...,
        description="sys_id of the sys_user record.",
    )
    include_inherited: bool = Field(
        default=True,
        description=(
            "Include inherited role records (created automatically by the platform). "
            "Default true. Set false to see only directly-granted roles."
        ),
    )


class ListGroupRolesParams(BaseModel):
    """Parameters for listing a group's roles."""

    group_sys_id: str = Field(
        ...,
        description="sys_id of the sys_user_group record.",
    )
    include_inherited: bool = Field(
        default=True,
        description=(
            "Include inherited role records. Default true. "
            "Set false to see only directly-granted roles."
        ),
    )


def grant_role_to_user(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: GrantRoleToUserParams,
) -> dict:
    """
    Grant a role to a user by creating a sys_user_has_role record.

    The platform automatically creates inherited records for contained roles —
    this tool never sets inherited=true. Use list_user_roles to confirm the grant.
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


def list_user_roles(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: ListUserRolesParams,
) -> dict:
    """
    List roles granted to a user from sys_user_has_role.

    By default includes inherited records (platform-generated). Set
    include_inherited=false to see only directly-granted roles.
    """
    url = f"{config.api_url}/table/sys_user_has_role"
    query = f"user={params.user_sys_id}"
    if not params.include_inherited:
        query += "^inherited=false"

    try:
        response = requests.get(
            url,
            params={
                "sysparm_query": query,
                "sysparm_limit": 500,
                "sysparm_fields": "sys_id,role,role.name,inherited,state",
                "sysparm_display_value": "true",
            },
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()
        roles = response.json().get("result", [])
        return {
            "success": True,
            "user_sys_id": params.user_sys_id,
            "count": len(roles),
            "roles": roles,
        }
    except requests.RequestException as e:
        _body = e.response.text[:2000] if getattr(e, "response", None) is not None else ""
        logger.error("list_user_roles | user=%s | error=%s", params.user_sys_id, e)
        return {
            "success": False,
            "message": f"Failed to list user roles: {e}" + (f" | response: {_body}" if _body else ""),
        }


def list_group_roles(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: ListGroupRolesParams,
) -> dict:
    """
    List roles granted to a group from sys_group_has_role.

    By default includes inherited records. Set include_inherited=false to see
    only directly-granted roles.
    """
    url = f"{config.api_url}/table/sys_group_has_role"
    query = f"group={params.group_sys_id}"
    if not params.include_inherited:
        query += "^inherited=false"

    try:
        response = requests.get(
            url,
            params={
                "sysparm_query": query,
                "sysparm_limit": 500,
                "sysparm_fields": "sys_id,role,role.name,inherited",
                "sysparm_display_value": "true",
            },
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()
        roles = response.json().get("result", [])
        return {
            "success": True,
            "group_sys_id": params.group_sys_id,
            "count": len(roles),
            "roles": roles,
        }
    except requests.RequestException as e:
        _body = e.response.text[:2000] if getattr(e, "response", None) is not None else ""
        logger.error("list_group_roles | group=%s | error=%s", params.group_sys_id, e)
        return {
            "success": False,
            "message": f"Failed to list group roles: {e}" + (f" | response: {_body}" if _body else ""),
        }


def remove_group_members(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: RemoveGroupMembersParams,
) -> GroupResponse:
    """
    Remove members from a group in ServiceNow.

    Args:
        config: Server configuration.
        auth_manager: Authentication manager.
        params: Parameters for removing members from the group.

    Returns:
        Response with the result of the operation.
    """
    success = True
    failed_members = []

    for member in params.members:
        # Get user ID if username is provided
        user_id = member
        if not member.startswith("sys_id:"):
            user = get_user(config, auth_manager, GetUserParams(user_name=member))
            if not user.get("success"):
                user = get_user(config, auth_manager, GetUserParams(email=member))

            if user.get("success"):
                user_id = user.get("user", {}).get("sys_id")
            else:
                success = False
                failed_members.append(member)
                continue

        # Find and delete the group membership
        api_url = f"{config.api_url}/table/sys_user_grmember"
        query_params = {
            "sysparm_query": f"group={params.group_id}^user={user_id}",
            "sysparm_limit": "1",
        }

        try:
            # First find the membership record
            response = requests.get(
                api_url,
                params=query_params,
                headers=auth_manager.get_headers(),
                timeout=config.timeout,
            )
            response.raise_for_status()

            result = response.json().get("result", [])
            if not result:
                success = False
                failed_members.append(member)
                continue

            # Then delete the membership record
            membership_id = result[0].get("sys_id")
            delete_url = f"{api_url}/{membership_id}"

            response = requests.delete(
                delete_url,
                headers=auth_manager.get_headers(),
                timeout=config.timeout,
            )
            response.raise_for_status()

        except requests.RequestException as e:
            _body = e.response.text[:2000] if getattr(e, "response", None) is not None else ""
            logger.error(f"Failed to remove member '{member}' from group: {e}" + (f" | body={_body}" if _body else ""))
            success = False
            failed_members.append(member)

    if failed_members:
        message = f"Some members could not be removed from the group: {', '.join(failed_members)}"
    else:
        message = "All members removed from the group successfully"

    return GroupResponse(
        success=success,
        message=message,
        group_id=params.group_id,
    )
