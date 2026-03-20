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


# ---------------------------------------------------------------------------
# search_ci
# ---------------------------------------------------------------------------


class SearchCIParams(BaseModel):
    """Parameters for searching Configuration Items with filters."""

    ci_class: str = Field(
        default="cmdb_ci",
        description=(
            "CI class (table) to search. Common values: 'cmdb_ci' (all), "
            "'cmdb_ci_server' (servers), 'cmdb_ci_appl' (applications), "
            "'cmdb_ci_service' (services). Default 'cmdb_ci'."
        ),
    )
    name: Optional[str] = Field(
        None,
        description="Filter by name (case-insensitive substring match).",
    )
    install_status: Optional[str] = Field(
        None,
        description=(
            "Filter by install_status value: '1'=Installed, '2'=On Order, "
            "'3'=On Maintenance, '6'=In Maintenance, '7'=Retired."
        ),
    )
    environment: Optional[str] = Field(
        None,
        description=(
            "Filter by environment field value (e.g., 'Production', "
            "'Development', 'Test', 'Staging')."
        ),
    )
    limit: int = Field(
        default=20,
        ge=1,
        le=1000,
        description="Maximum number of CIs to return (1–1000). Default 20.",
    )
    offset: int = Field(
        default=0,
        ge=0,
        description="Zero-based offset for pagination.",
    )


def search_ci(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: SearchCIParams,
) -> Dict[str, Any]:
    """
    Search Configuration Items with flexible filters.

    Supports filtering by CI class, name (substring), install_status, and
    environment. Useful for targeted CMDB lookups without knowing a sys_id.
    """
    url = f"{config.api_url}/table/{params.ci_class}"
    query_parts: List[str] = []
    if params.name:
        query_parts.append(f"nameLIKE{params.name}")
    if params.install_status:
        query_parts.append(f"install_status={params.install_status}")
    if params.environment:
        query_parts.append(f"environment={params.environment}")

    q_params: Dict[str, Any] = {
        "sysparm_limit": params.limit,
        "sysparm_offset": params.offset,
        "sysparm_display_value": "true",
    }
    if query_parts:
        q_params["sysparm_query"] = "^".join(query_parts)

    try:
        response = requests.get(
            url,
            params=q_params,
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
        logger.error("search_ci | ci_class=%s | error=%s", params.ci_class, e)
        return {
            "success": False,
            "error": str(e) + (f" | response: {body_text}" if body_text else ""),
        }


# ---------------------------------------------------------------------------
# create_ci_relationship
# ---------------------------------------------------------------------------


class CreateCIRelationshipParams(BaseModel):
    """Parameters for creating a relationship between two CIs."""

    parent_id: str = Field(
        ...,
        description="sys_id of the parent CI (the CI that is depended upon).",
    )
    child_id: str = Field(
        ...,
        description="sys_id of the child CI (the CI that depends on the parent).",
    )
    type_name: str = Field(
        ...,
        description=(
            "Relationship type name from cmdb_rel_type "
            "(e.g., 'Runs on::Runs', 'Hosted on::Hosts', 'Depends on::Used by'). "
            "Use list_ci_relationship_types to see available types."
        ),
    )


def create_ci_relationship(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: CreateCIRelationshipParams,
) -> Dict[str, Any]:
    """
    Create a relationship between two CIs in cmdb_rel_ci.

    Resolves type_name to a cmdb_rel_type sys_id before creating the record.
    Use list_ci_relationship_types to discover available relationship type names.
    """
    headers = auth_manager.get_headers()
    # Resolve type_name → sys_id via cmdb_rel_type
    type_url = f"{config.api_url}/table/cmdb_rel_type"
    try:
        type_resp = requests.get(
            type_url,
            params={"sysparm_query": f"name={params.type_name}", "sysparm_limit": 1},
            headers=headers,
            timeout=config.timeout,
        )
        type_resp.raise_for_status()
        type_results = type_resp.json().get("result", [])
        if not type_results:
            return {
                "success": False,
                "error": f"Relationship type '{params.type_name}' not found in cmdb_rel_type.",
            }
        type_sys_id = type_results[0]["sys_id"]
    except requests.RequestException as e:
        logger.error("create_ci_relationship | type lookup | error=%s", e)
        return {"success": False, "error": f"Error resolving relationship type: {e}"}

    # Create the relationship
    rel_url = f"{config.api_url}/table/cmdb_rel_ci"
    try:
        response = requests.post(
            rel_url,
            json={"parent": params.parent_id, "child": params.child_id, "type": type_sys_id},
            headers=headers,
            timeout=config.timeout,
        )
        response.raise_for_status()
        rel = response.json().get("result", {})
        return {
            "success": True,
            "message": f"Relationship created: {params.parent_id} → {params.type_name} → {params.child_id}",
            "sys_id": rel.get("sys_id", ""),
            "relationship": rel,
        }
    except requests.RequestException as e:
        body = getattr(e, "response", None)
        body_text = (body.text[:2000] if body and hasattr(body, "text") else "") or ""
        logger.error("create_ci_relationship | error=%s", e)
        return {
            "success": False,
            "error": str(e) + (f" | response: {body_text}" if body_text else ""),
        }


# ---------------------------------------------------------------------------
# delete_ci_relationship
# ---------------------------------------------------------------------------


class DeleteCIRelationshipParams(BaseModel):
    """Parameters for deleting a CI relationship by sys_id."""

    sys_id: str = Field(
        ...,
        description="sys_id of the cmdb_rel_ci record to delete.",
    )


def delete_ci_relationship(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: DeleteCIRelationshipParams,
) -> Dict[str, Any]:
    """
    Delete a CI relationship record from cmdb_rel_ci.

    Permanently removes the relationship. Use get_ci_relationships to find
    the sys_id of the relationship before deleting.
    """
    url = f"{config.api_url}/table/cmdb_rel_ci/{params.sys_id}"
    try:
        response = requests.delete(
            url,
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()
        return {
            "success": True,
            "message": f"CI relationship {params.sys_id} deleted.",
            "sys_id": params.sys_id,
        }
    except requests.RequestException as e:
        body = getattr(e, "response", None)
        body_text = (body.text[:2000] if body and hasattr(body, "text") else "") or ""
        logger.error("delete_ci_relationship | sys_id=%s | error=%s", params.sys_id, e)
        return {
            "success": False,
            "error": str(e) + (f" | response: {body_text}" if body_text else ""),
        }


# ---------------------------------------------------------------------------
# list_ci_relationship_types
# ---------------------------------------------------------------------------


class ListCIRelationshipTypesParams(BaseModel):
    """Parameters for listing available CI relationship types."""

    name_filter: Optional[str] = Field(
        None,
        description="Filter by partial name match (e.g., 'Runs' returns 'Runs on::Runs').",
    )
    limit: int = Field(
        default=100,
        ge=1,
        le=500,
        description="Maximum number of relationship types to return. Default 100.",
    )


def list_ci_relationship_types(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: ListCIRelationshipTypesParams,
) -> Dict[str, Any]:
    """
    List available CI relationship types from cmdb_rel_type.

    Returns the full list of valid relationship type names for use with
    create_ci_relationship. Each type has an outbound label and an inbound label
    separated by '::' (e.g., 'Runs on::Runs').
    """
    url = f"{config.api_url}/table/cmdb_rel_type"
    q_params: Dict[str, Any] = {
        "sysparm_limit": params.limit,
        "sysparm_fields": "sys_id,name,outbound_description,inbound_description",
    }
    if params.name_filter:
        q_params["sysparm_query"] = f"nameLIKE{params.name_filter}"

    try:
        response = requests.get(
            url,
            params=q_params,
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()
        types: List[Dict] = response.json().get("result", [])
        return {
            "success": True,
            "count": len(types),
            "relationship_types": types,
        }
    except requests.RequestException as e:
        body = getattr(e, "response", None)
        body_text = (body.text[:2000] if body and hasattr(body, "text") else "") or ""
        logger.error("list_ci_relationship_types | error=%s", e)
        return {
            "success": False,
            "error": str(e) + (f" | response: {body_text}" if body_text else ""),
        }


# ---------------------------------------------------------------------------
# get_ci_impact_graph
# ---------------------------------------------------------------------------


class GetCIImpactGraphParams(BaseModel):
    """Parameters for traversing the CI impact graph."""

    sys_id: str = Field(
        ...,
        description="sys_id of the starting CI for the impact graph traversal.",
    )
    direction: str = Field(
        default="downstream",
        description=(
            "Traversal direction: "
            "'downstream' (follow child relationships — what this CI impacts), "
            "'upstream' (follow parent relationships — what impacts this CI), "
            "'both' (traverse in both directions)."
        ),
    )
    max_depth: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum traversal depth (1–10). Default 3.",
    )


def get_ci_impact_graph(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: GetCIImpactGraphParams,
) -> Dict[str, Any]:
    """
    Traverse the CI relationship graph to build an impact map.

    Uses breadth-first traversal through cmdb_rel_ci up to max_depth hops.
    Returns nodes (CIs visited) and edges (relationships traversed).
    Useful for impact analysis — e.g., which services are affected if a server fails.
    """
    headers = auth_manager.get_headers()
    url = f"{config.api_url}/table/cmdb_rel_ci"
    direction = params.direction.lower()

    nodes: Dict[str, Dict] = {params.sys_id: {"sys_id": params.sys_id, "depth": 0}}
    edges: List[Dict] = []
    frontier = {params.sys_id}

    for depth in range(1, params.max_depth + 1):
        if not frontier:
            break
        next_frontier: set = set()
        for ci_id in frontier:
            queries: List[str] = []
            if direction in ("downstream", "both"):
                queries.append(f"parent={ci_id}")
            if direction in ("upstream", "both"):
                queries.append(f"child={ci_id}")

            for query in queries:
                try:
                    resp = requests.get(
                        url,
                        params={
                            "sysparm_query": query,
                            "sysparm_limit": 100,
                            "sysparm_fields": "sys_id,parent,child,type",
                            "sysparm_display_value": "true",
                        },
                        headers=headers,
                        timeout=config.timeout,
                    )
                    resp.raise_for_status()
                    for row in resp.json().get("result", []):
                        edges.append(row)
                        # Determine the neighbour CI
                        if "parent=" in query:
                            neighbour = (row.get("child") or {})
                            neighbour_id = neighbour.get("value", "") if isinstance(neighbour, dict) else neighbour
                        else:
                            neighbour = (row.get("parent") or {})
                            neighbour_id = neighbour.get("value", "") if isinstance(neighbour, dict) else neighbour
                        if neighbour_id and neighbour_id not in nodes:
                            nodes[neighbour_id] = {"sys_id": neighbour_id, "depth": depth}
                            next_frontier.add(neighbour_id)
                except requests.RequestException as e:
                    logger.error("get_ci_impact_graph | depth=%d | query=%s | error=%s", depth, query, e)
        frontier = next_frontier

    return {
        "success": True,
        "root_sys_id": params.sys_id,
        "direction": params.direction,
        "max_depth": params.max_depth,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "nodes": list(nodes.values()),
        "edges": edges,
    }
