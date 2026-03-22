"""
CMDB tools for the ServiceNow MCP server.

Provides compound tools for managing CI relationships and traversing the
Configuration Management Database (CMDB) impact graph.

Simple CI CRUD (list, get, create, update) is handled by table_tools
(query_records, get_record, create_record, update_record) using the CMDB
architecture blueprint for field guidance.
"""

import logging
from typing import Any, Dict, List, Optional

import requests
from pydantic import BaseModel, Field

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.utils.config import ServerConfig

logger = logging.getLogger(__name__)


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
            "Use query_records on cmdb_rel_type to see available types."
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
    Use query_records on cmdb_rel_type to discover available relationship type names.
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
