"""
CMDB tools for the ServiceNow MCP server.

Provides tools for managing Configuration Items (CIs) in the ServiceNow
Configuration Management Database (CMDB). All CIs live in tables that extend
cmdb_ci (e.g., cmdb_ci_server, cmdb_ci_appl, cmdb_ci_network_adapter).
"""

import logging
from typing import Any, Dict, List, Optional

import requests
from pydantic import BaseModel, Field

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.utils.config import ServerConfig

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# list_ci
# ---------------------------------------------------------------------------


class ListCIParams(BaseModel):
    """Parameters for listing Configuration Items."""

    ci_class: str = Field(
        default="cmdb_ci",
        description=(
            "CMDB CI class (table) to query. Common values: "
            "'cmdb_ci' (all CIs), 'cmdb_ci_server' (servers), "
            "'cmdb_ci_appl' (applications), 'cmdb_ci_service' (services), "
            "'cmdb_ci_computer' (computers), 'cmdb_ci_network_adapter' (network). "
            "Default is 'cmdb_ci' which returns all CI types."
        ),
    )
    query: Optional[str] = Field(
        None,
        description=(
            "Encoded query string (e.g., 'install_status=1^operational_status=1' "
            "for operational CIs). Leave empty to return all records up to the limit."
        ),
    )
    fields: Optional[str] = Field(
        None,
        description=(
            "Comma-separated list of fields to return. Common fields: "
            "'sys_id,name,sys_class_name,ip_address,install_status,operational_status,"
            "assigned_to,location,manufacturer,model_id'. Leave empty for all fields."
        ),
    )
    limit: int = Field(
        default=10,
        ge=1,
        le=1000,
        description="Maximum number of CIs to return (1–1000). Default 10.",
    )
    offset: int = Field(
        default=0,
        ge=0,
        description="Zero-based offset for pagination.",
    )


def list_ci(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: ListCIParams,
) -> Dict[str, Any]:
    """
    List Configuration Items from the CMDB.

    Queries the specified CI class table. Use ci_class to target a specific
    type (e.g., cmdb_ci_server for servers). Use query to filter by attributes
    like install_status, operational_status, or assigned_to.
    """
    url = f"{config.api_url}/table/{params.ci_class}"
    query_params: Dict[str, Any] = {
        "sysparm_limit": params.limit,
        "sysparm_offset": params.offset,
    }
    if params.query:
        query_params["sysparm_query"] = params.query
    if params.fields:
        query_params["sysparm_fields"] = params.fields

    try:
        response = requests.get(
            url,
            params=query_params,
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()
        cis: List[Dict] = response.json().get("result", [])
        return {
            "success": True,
            "ci_class": params.ci_class,
            "count": len(cis),
            "cis": cis,
        }
    except requests.RequestException as e:
        body = getattr(e, "response", None)
        body_text = (body.text[:2000] if body and hasattr(body, "text") else "") or ""
        logger.error("list_ci | ci_class=%s | error=%s", params.ci_class, e)
        return {
            "success": False,
            "ci_class": params.ci_class,
            "error": str(e) + (f" | response: {body_text}" if body_text else ""),
        }


# ---------------------------------------------------------------------------
# get_ci
# ---------------------------------------------------------------------------


class GetCIParams(BaseModel):
    """Parameters for retrieving a single CI by sys_id."""

    sys_id: str = Field(..., description="32-character sys_id of the CI to retrieve.")
    ci_class: str = Field(
        default="cmdb_ci",
        description=(
            "CI class table. Use the specific subclass if known "
            "(e.g., 'cmdb_ci_server') for better field coverage, "
            "or leave as 'cmdb_ci' to query the base class."
        ),
    )


def get_ci(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: GetCIParams,
) -> Dict[str, Any]:
    """
    Retrieve a single Configuration Item by sys_id.

    Returns all fields for the CI. Specify the exact ci_class subtype
    (e.g., cmdb_ci_server) for complete field data including class-specific attributes.
    """
    url = f"{config.api_url}/table/{params.ci_class}/{params.sys_id}"
    try:
        response = requests.get(
            url,
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()
        ci = response.json().get("result", {})
        return {
            "success": True,
            "ci_class": params.ci_class,
            "sys_id": params.sys_id,
            "ci": ci,
        }
    except requests.RequestException as e:
        body = getattr(e, "response", None)
        body_text = (body.text[:2000] if body and hasattr(body, "text") else "") or ""
        logger.error("get_ci | ci_class=%s | sys_id=%s | error=%s", params.ci_class, params.sys_id, e)
        return {
            "success": False,
            "ci_class": params.ci_class,
            "sys_id": params.sys_id,
            "error": str(e) + (f" | response: {body_text}" if body_text else ""),
        }


# ---------------------------------------------------------------------------
# create_ci
# ---------------------------------------------------------------------------


class CreateCIParams(BaseModel):
    """Parameters for creating a new Configuration Item."""

    ci_class: str = Field(
        ...,
        description=(
            "CI class table to create the record in. Use the most specific subclass "
            "(e.g., 'cmdb_ci_server', 'cmdb_ci_appl'). Do not use 'cmdb_ci' directly "
            "unless the CI has no applicable subclass."
        ),
    )
    fields: Dict[str, Any] = Field(
        ...,
        description=(
            "Key-value pairs for the new CI. Required fields vary by class. "
            "Common fields: 'name' (required), 'ip_address', 'install_status' "
            "(1=Installed, 2=On Order, 6=In Maintenance), 'operational_status' "
            "(1=Operational, 2=Non-Operational), 'assigned_to', 'location', "
            "'manufacturer', 'model_id'."
        ),
    )


def create_ci(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: CreateCIParams,
) -> Dict[str, Any]:
    """
    Create a new Configuration Item in the CMDB.

    Always use the most specific CI subclass (e.g., cmdb_ci_server) rather
    than cmdb_ci directly to ensure proper class-specific fields are available.
    Use verify_fields after creation to confirm values persisted.
    """
    url = f"{config.api_url}/table/{params.ci_class}"
    try:
        response = requests.post(
            url,
            json=params.fields,
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()
        ci = response.json().get("result", {})
        return {
            "success": True,
            "ci_class": params.ci_class,
            "sys_id": ci.get("sys_id", ""),
            "ci": ci,
        }
    except requests.RequestException as e:
        body = getattr(e, "response", None)
        body_text = (body.text[:2000] if body and hasattr(body, "text") else "") or ""
        logger.error("create_ci | ci_class=%s | error=%s", params.ci_class, e)
        return {
            "success": False,
            "ci_class": params.ci_class,
            "error": str(e) + (f" | response: {body_text}" if body_text else ""),
        }


# ---------------------------------------------------------------------------
# update_ci
# ---------------------------------------------------------------------------


class UpdateCIParams(BaseModel):
    """Parameters for updating an existing CI."""

    sys_id: str = Field(..., description="sys_id of the CI to update.")
    ci_class: str = Field(
        default="cmdb_ci",
        description="CI class table. Use the specific subclass if known.",
    )
    fields: Dict[str, Any] = Field(
        ...,
        description=(
            "Key-value pairs of fields to update. Only provided fields are changed. "
            "Use get_field_metadata to verify a field is writable before including it."
        ),
    )


def update_ci(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: UpdateCIParams,
) -> Dict[str, Any]:
    """
    Update an existing Configuration Item via PATCH.

    Only provided fields are modified. Use verify_fields after the update to
    confirm values persisted — Discovery and other mechanisms may override writes.
    """
    url = f"{config.api_url}/table/{params.ci_class}/{params.sys_id}"
    try:
        response = requests.patch(
            url,
            json=params.fields,
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()
        ci = response.json().get("result", {})
        return {
            "success": True,
            "ci_class": params.ci_class,
            "sys_id": params.sys_id,
            "ci": ci,
        }
    except requests.RequestException as e:
        body = getattr(e, "response", None)
        body_text = (body.text[:2000] if body and hasattr(body, "text") else "") or ""
        logger.error("update_ci | ci_class=%s | sys_id=%s | error=%s", params.ci_class, params.sys_id, e)
        return {
            "success": False,
            "ci_class": params.ci_class,
            "sys_id": params.sys_id,
            "error": str(e) + (f" | response: {body_text}" if body_text else ""),
        }


# ---------------------------------------------------------------------------
# get_ci_relationships
# ---------------------------------------------------------------------------


class GetCIRelationshipsParams(BaseModel):
    """Parameters for getting CI relationships from cmdb_rel_ci."""

    sys_id: str = Field(
        ...,
        description="sys_id of the CI to retrieve relationships for.",
    )
    relationship_type: Optional[str] = Field(
        None,
        description=(
            "Filter by relationship type label (e.g., 'Runs on::Runs', 'Hosted on::Hosts', "
            "'Depends on::Used by'). Leave empty to return all relationship types."
        ),
    )
    direction: Optional[str] = Field(
        default="both",
        description=(
            "Which relationships to return: "
            "'parent' (CIs that this CI depends on), "
            "'child' (CIs that depend on this CI), "
            "'both' (all relationships). Default 'both'."
        ),
    )
    limit: int = Field(
        default=50,
        ge=1,
        le=500,
        description="Maximum number of relationships to return.",
    )


def get_ci_relationships(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: GetCIRelationshipsParams,
) -> Dict[str, Any]:
    """
    Get relationships for a CI from cmdb_rel_ci.

    Returns parent relationships (CIs this one depends on), child relationships
    (CIs that depend on this one), or both. Use this to map service dependencies,
    infrastructure topology, and impact chains.
    """
    url = f"{config.api_url}/table/cmdb_rel_ci"
    direction = (params.direction or "both").lower()
    results: List[Dict] = []

    def _fetch(query: str) -> List[Dict]:
        q_params: Dict[str, Any] = {
            "sysparm_query": query,
            "sysparm_limit": params.limit,
            "sysparm_display_value": "true",
        }
        if params.relationship_type:
            q_params["sysparm_query"] += f"^type.name={params.relationship_type}"
        try:
            resp = requests.get(
                url,
                params=q_params,
                headers=auth_manager.get_headers(),
                timeout=config.timeout,
            )
            resp.raise_for_status()
            return resp.json().get("result", [])
        except requests.RequestException as e:
            logger.error("get_ci_relationships | query=%s | error=%s", query, e)
            return []

    if direction in ("parent", "both"):
        # parent: this CI is the child — rows where child=sys_id
        for row in _fetch(f"child={params.sys_id}"):
            row["_direction"] = "parent"
            results.append(row)

    if direction in ("child", "both"):
        # child: this CI is the parent — rows where parent=sys_id
        for row in _fetch(f"parent={params.sys_id}"):
            row["_direction"] = "child"
            results.append(row)

    return {
        "success": True,
        "sys_id": params.sys_id,
        "relationship_count": len(results),
        "relationships": results,
    }
