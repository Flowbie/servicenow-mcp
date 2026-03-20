"""
GRC Risk tools for the ServiceNow MCP server.

Provides tools for managing risks in the ServiceNow GRC Risk module.
All risk records live in sn_risk_risk. Likelihood, impact, and score fields
are references to sn_risk_criteria — NOT plain integers. State and response
are string labels, not numeric codes.
"""

import logging
from typing import Any, Dict, List, Optional

import requests
from pydantic import BaseModel, Field

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.utils.config import ServerConfig

logger = logging.getLogger(__name__)

# Valid state values for sn_risk_risk (string labels, not integers)
_VALID_STATES = {"draft", "assess", "respond", "monitor", "review", "retired"}

# Valid treatment/response values
_VALID_RESPONSES = {"Accept", "Avoid", "Mitigate", "Transfer"}


# ---------------------------------------------------------------------------
# list_risks
# ---------------------------------------------------------------------------


class ListRisksParams(BaseModel):
    """Parameters for listing risks."""

    state: Optional[str] = Field(
        None,
        description=(
            "Filter by risk state. Valid values: "
            "'draft', 'assess', 'respond', 'monitor', 'review', 'retired'."
        ),
    )
    framework: Optional[str] = Field(
        None,
        description="Filter by risk framework name or sys_id.",
    )
    limit: int = Field(
        default=20,
        ge=1,
        le=1000,
        description="Maximum number of risks to return (1–1000). Default 20.",
    )
    offset: int = Field(
        default=0,
        ge=0,
        description="Zero-based offset for pagination.",
    )


def list_risks(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: ListRisksParams,
) -> Dict[str, Any]:
    """
    List risks from sn_risk_risk with optional filters.

    Supports filtering by state (string label) and framework. Returns risk
    records with display values for reference fields.
    """
    url = f"{config.api_url}/table/sn_risk_risk"
    query_parts: List[str] = []
    if params.state:
        query_parts.append(f"state={params.state}")
    if params.framework:
        query_parts.append(f"frameworkLIKE{params.framework}")

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
        risks: List[Dict] = response.json().get("result", [])
        return {
            "success": True,
            "count": len(risks),
            "risks": risks,
        }
    except requests.RequestException as e:
        body = getattr(e, "response", None)
        body_text = (body.text[:2000] if body and hasattr(body, "text") else "") or ""
        logger.error("list_risks | error=%s", e)
        return {
            "success": False,
            "message": str(e) + (f" | response: {body_text}" if body_text else ""),
        }


# ---------------------------------------------------------------------------
# get_risk
# ---------------------------------------------------------------------------


class GetRiskParams(BaseModel):
    """Parameters for retrieving a single risk by sys_id."""

    sys_id: str = Field(..., description="sys_id of the sn_risk_risk record.")


def get_risk(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: GetRiskParams,
) -> Dict[str, Any]:
    """
    Retrieve a single risk record by sys_id.

    Returns all fields with display values for reference fields such as
    likelihood, impact, score (all references to sn_risk_criteria).
    """
    url = f"{config.api_url}/table/sn_risk_risk/{params.sys_id}"
    try:
        response = requests.get(
            url,
            params={"sysparm_display_value": "true"},
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()
        risk = response.json().get("result", {})
        return {
            "success": True,
            "sys_id": params.sys_id,
            "risk": risk,
        }
    except requests.RequestException as e:
        body = getattr(e, "response", None)
        body_text = (body.text[:2000] if body and hasattr(body, "text") else "") or ""
        logger.error("get_risk | sys_id=%s | error=%s", params.sys_id, e)
        return {
            "success": False,
            "message": str(e) + (f" | response: {body_text}" if body_text else ""),
        }


# ---------------------------------------------------------------------------
# create_risk
# ---------------------------------------------------------------------------


class CreateRiskParams(BaseModel):
    """Parameters for creating a new risk."""

    name: str = Field(..., description="Short description / name of the risk.")
    description: Optional[str] = Field(
        None, description="Detailed description of the risk."
    )
    state: Optional[str] = Field(
        default="draft",
        description=(
            "Initial state. Valid values: "
            "'draft', 'assess', 'respond', 'monitor', 'review', 'retired'. "
            "Default 'draft'."
        ),
    )
    owner: Optional[str] = Field(
        None, description="sys_id of the risk owner (sys_user)."
    )
    framework: Optional[str] = Field(
        None, description="sys_id of the risk framework (sn_risk_framework)."
    )
    category: Optional[str] = Field(
        None, description="Risk category sys_id or label."
    )
    likelihood: Optional[str] = Field(
        None,
        description=(
            "sys_id of the likelihood sn_risk_criteria record. "
            "Use list_risk_criteria to resolve a label to a sys_id."
        ),
    )
    impact: Optional[str] = Field(
        None,
        description=(
            "sys_id of the impact sn_risk_criteria record. "
            "Use list_risk_criteria to resolve a label to a sys_id."
        ),
    )


def create_risk(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: CreateRiskParams,
) -> Dict[str, Any]:
    """
    Create a new risk record in sn_risk_risk.

    Likelihood and impact must be sys_ids from sn_risk_criteria — use
    list_risk_criteria to resolve label names to sys_ids before calling this tool.
    """
    if params.state and params.state not in _VALID_STATES:
        return {
            "success": False,
            "message": (
                f"Invalid state '{params.state}'. "
                f"Valid values: {', '.join(sorted(_VALID_STATES))}."
            ),
        }

    url = f"{config.api_url}/table/sn_risk_risk"
    data: Dict[str, Any] = {"name": params.name}
    if params.description:
        data["description"] = params.description
    if params.state:
        data["state"] = params.state
    if params.owner:
        data["owner"] = params.owner
    if params.framework:
        data["framework"] = params.framework
    if params.category:
        data["category"] = params.category
    if params.likelihood:
        data["likelihood"] = params.likelihood
    if params.impact:
        data["impact"] = params.impact

    try:
        response = requests.post(
            url,
            json=data,
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()
        risk = response.json().get("result", {})
        return {
            "success": True,
            "message": f"Risk '{params.name}' created.",
            "sys_id": risk.get("sys_id", ""),
            "risk": risk,
        }
    except requests.RequestException as e:
        body = getattr(e, "response", None)
        body_text = (body.text[:2000] if body and hasattr(body, "text") else "") or ""
        logger.error("create_risk | name=%s | error=%s", params.name, e)
        return {
            "success": False,
            "message": str(e) + (f" | response: {body_text}" if body_text else ""),
        }


# ---------------------------------------------------------------------------
# update_risk_state
# ---------------------------------------------------------------------------


class UpdateRiskStateParams(BaseModel):
    """Parameters for updating the state of a risk."""

    sys_id: str = Field(..., description="sys_id of the sn_risk_risk record.")
    state: str = Field(
        ...,
        description=(
            "New state. Valid values: "
            "'draft', 'assess', 'respond', 'monitor', 'review', 'retired'."
        ),
    )


def update_risk_state(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: UpdateRiskStateParams,
) -> Dict[str, Any]:
    """
    Update the state of an existing risk record.

    State must be a string label (e.g., 'assess'), NOT a numeric code.
    Valid transitions: draft → assess → respond → monitor → review → retired.
    """
    if params.state not in _VALID_STATES:
        return {
            "success": False,
            "message": (
                f"Invalid state '{params.state}'. "
                f"Valid values: {', '.join(sorted(_VALID_STATES))}."
            ),
        }

    url = f"{config.api_url}/table/sn_risk_risk/{params.sys_id}"
    try:
        response = requests.patch(
            url,
            json={"state": params.state},
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()
        risk = response.json().get("result", {})
        return {
            "success": True,
            "message": f"Risk {params.sys_id} state updated to '{params.state}'.",
            "sys_id": params.sys_id,
            "risk": risk,
        }
    except requests.RequestException as e:
        body = getattr(e, "response", None)
        body_text = (body.text[:2000] if body and hasattr(body, "text") else "") or ""
        logger.error("update_risk_state | sys_id=%s | error=%s", params.sys_id, e)
        return {
            "success": False,
            "message": str(e) + (f" | response: {body_text}" if body_text else ""),
        }


# ---------------------------------------------------------------------------
# list_risk_criteria
# ---------------------------------------------------------------------------


class ListRiskCriteriaParams(BaseModel):
    """Parameters for listing risk criteria (likelihood/impact/score references)."""

    criteria_type: Optional[str] = Field(
        None,
        description=(
            "Filter by criteria type field (e.g., 'likelihood', 'impact', 'score'). "
            "Leave empty to return all criteria."
        ),
    )
    label: Optional[str] = Field(
        None,
        description="Filter by partial label match to resolve a label to a sys_id.",
    )
    limit: int = Field(
        default=50,
        ge=1,
        le=500,
        description="Maximum number of criteria records to return. Default 50.",
    )


def list_risk_criteria(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: ListRiskCriteriaParams,
) -> Dict[str, Any]:
    """
    List risk criteria from sn_risk_criteria.

    Use this to resolve likelihood, impact, or score label names to sys_ids
    before passing them to create_risk or assign_risk_response. Returns
    sys_id, label, and type for each criteria record.
    """
    url = f"{config.api_url}/table/sn_risk_criteria"
    query_parts: List[str] = []
    if params.criteria_type:
        query_parts.append(f"type={params.criteria_type}")
    if params.label:
        query_parts.append(f"labelLIKE{params.label}")

    q_params: Dict[str, Any] = {
        "sysparm_limit": params.limit,
        "sysparm_fields": "sys_id,label,type,value,order",
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
        criteria: List[Dict] = response.json().get("result", [])
        return {
            "success": True,
            "count": len(criteria),
            "criteria": criteria,
        }
    except requests.RequestException as e:
        body = getattr(e, "response", None)
        body_text = (body.text[:2000] if body and hasattr(body, "text") else "") or ""
        logger.error("list_risk_criteria | error=%s", e)
        return {
            "success": False,
            "message": str(e) + (f" | response: {body_text}" if body_text else ""),
        }


# ---------------------------------------------------------------------------
# assign_risk_response
# ---------------------------------------------------------------------------


class AssignRiskResponseParams(BaseModel):
    """Parameters for assigning a treatment response to a risk."""

    sys_id: str = Field(..., description="sys_id of the sn_risk_risk record.")
    response: str = Field(
        ...,
        description=(
            "Risk treatment response. Valid string values: "
            "'Accept', 'Avoid', 'Mitigate', 'Transfer'. "
            "These are string labels, NOT numeric codes."
        ),
    )


def assign_risk_response(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: AssignRiskResponseParams,
) -> Dict[str, Any]:
    """
    Assign a treatment response to a risk record.

    Response must be a string label: 'Accept', 'Avoid', 'Mitigate', or 'Transfer'.
    These are NOT numeric codes — pass the string directly to the treatment field.
    """
    if params.response not in _VALID_RESPONSES:
        return {
            "success": False,
            "message": (
                f"Invalid response '{params.response}'. "
                f"Valid values: {', '.join(sorted(_VALID_RESPONSES))}."
            ),
        }

    url = f"{config.api_url}/table/sn_risk_risk/{params.sys_id}"
    try:
        response = requests.patch(
            url,
            json={"treatment": params.response},
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()
        risk = response.json().get("result", {})
        return {
            "success": True,
            "message": f"Risk {params.sys_id} response set to '{params.response}'.",
            "sys_id": params.sys_id,
            "risk": risk,
        }
    except requests.RequestException as e:
        body = getattr(e, "response", None)
        body_text = (body.text[:2000] if body and hasattr(body, "text") else "") or ""
        logger.error("assign_risk_response | sys_id=%s | error=%s", params.sys_id, e)
        return {
            "success": False,
            "message": str(e) + (f" | response: {body_text}" if body_text else ""),
        }
