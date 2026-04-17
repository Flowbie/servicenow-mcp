"""
Generic Table API tools for the ServiceNow MCP server.

Provides CRUD operations against any ServiceNow table via the Table REST API
(/api/now/table/{table_name}). Use these when no domain-specific tool exists
for the target table.
"""

import logging
from typing import Any, Dict, List, Optional, Set, Tuple

import requests
from pydantic import BaseModel, Field

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.update_set_tools import get_current_update_set
from servicenow_mcp.utils.config import ServerConfig
from servicenow_mcp.utils.identifier_resolver import resolve_identifier
from servicenow_mcp.utils.response_envelope import SnowResponse
from servicenow_mcp.utils.update_set_policy import (
    UpdateSetInfo,
    assert_update_set_compliance_for_write,
)

logger = logging.getLogger(__name__)

# Tables that extend `task` — mandatory fields may live on the parent table.
_TASK_CHILD_TABLES: frozenset = frozenset({
    "incident", "change_request", "problem", "sc_task",
    "sn_si_incident", "sm_order", "hr_case",
    "sn_risk_response_task", "sn_risk_avoidance_task",
    "sn_risk_acceptance_task", "sn_risk_mitigation_task",
    "sn_risk_transfer_task", "sn_risk_response_sub_task",
})


def _enforce_update_set_policy(
    config: ServerConfig,
    auth_manager: AuthManager,
    table: str,
) -> Dict[str, Any] | None:
    try:
        current_update_set_result = get_current_update_set(config, auth_manager, {})
    except Exception:
        logger.warning("_enforce_update_set_policy: get_current_update_set raised unexpectedly; skipping policy check")
        current_update_set_result = {}
    current_update_set = None
    if current_update_set_result.get("success"):
        update_set = current_update_set_result.get("update_set", {})
        if isinstance(update_set, dict):
            current_update_set = UpdateSetInfo(
                name=update_set.get("name"),
                sys_id=update_set.get("sys_id"),
                state=update_set.get("state"),
                is_default=bool(update_set.get("is_default")),
            )
    compliance = assert_update_set_compliance_for_write(
        table=table,
        current_update_set=current_update_set,
    )
    if compliance.allowed:
        return None
    return {
        "success": False,
        "table": table,
        "error": compliance.reason,
        "governance": {
            "classification": compliance.classification.value,
            "blocked_by": "update_set_policy",
        },
    }


def _fetch_mandatory_fields(
    config: ServerConfig,
    auth_manager: AuthManager,
    table: str,
) -> Tuple[Set[str], Optional[str]]:
    """
    Query sys_dictionary for mandatory fields on `table` that have no default value.

    Returns (mandatory_fields, fetch_error).
    - mandatory_fields: field names that are mandatory and have no configured default.
      Fields with a default_value are excluded — ServiceNow will populate them automatically.
    - fetch_error: set if sys_dictionary was unreachable; None on success.

    Also checks the `task` parent table for known task-hierarchy tables so that
    mandatory inherited fields (e.g. short_description on incident) are caught.
    """
    tables_to_check = [table]
    if table in _TASK_CHILD_TABLES:
        tables_to_check.append("task")

    mandatory: Set[str] = set()
    for t in tables_to_check:
        url = f"{config.api_url}/table/sys_dictionary"
        query_params = {
            "sysparm_query": f"name={t}^mandatory=true^active=true",
            "sysparm_fields": "element,default_value",
            "sysparm_limit": 200,
        }
        try:
            response = requests.get(
                url,
                params=query_params,
                headers=auth_manager.get_headers(),
                timeout=config.timeout,
            )
            response.raise_for_status()
            for rec in response.json().get("result", []):
                element = rec.get("element", "").strip()
                default_value = rec.get("default_value", "")
                if element and not default_value:
                    mandatory.add(element)
        except requests.RequestException as e:
            logger.warning("_fetch_mandatory_fields | table=%s | error=%s", t, e)
            return set(), str(e)

    return mandatory, None


# ---------------------------------------------------------------------------
# query_records
# ---------------------------------------------------------------------------


class QueryRecordsParams(BaseModel):
    """Parameters for querying records from any ServiceNow table."""

    table: str = Field(
        ...,
        description=(
            "ServiceNow table name (e.g., 'incident', 'cmdb_ci', 'sc_request', "
            "'sn_hr_core_case'). Any table accessible via the Table REST API."
        ),
    )
    query: Optional[str] = Field(
        None,
        description=(
            "Encoded query string using ServiceNow query syntax "
            "(e.g., 'active=true^state=1^assigned_toISEMPTY'). "
            "Leave empty to return all records up to the limit."
        ),
    )
    fields: Optional[str] = Field(
        None,
        description=(
            "Comma-separated list of fields to return "
            "(e.g., 'sys_id,number,short_description,state'). "
            "Leave empty to return all fields."
        ),
    )
    limit: int = Field(
        default=10,
        ge=1,
        le=1000,
        description="Maximum number of records to return (1–1000). Default 10.",
    )
    offset: int = Field(
        default=0,
        ge=0,
        description="Zero-based offset for pagination.",
    )
    order_by: Optional[str] = Field(
        None,
        description="Field name to sort by (e.g., 'sys_created_on').",
    )
    order_direction: Optional[str] = Field(
        default="asc",
        description="Sort direction: 'asc' or 'desc'. Default 'asc'.",
    )
    include_query_info: bool = Field(
        default=False,
        description=(
            "If True, include 'query_info' in the response showing the exact encoded query "
            "sent to ServiceNow, the table queried, and the limit applied. "
            "Use this to debug empty results or unexpected matches."
        ),
    )


def query_records(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: QueryRecordsParams,
) -> Dict[str, Any]:
    """
    Query records from any ServiceNow table using the Table REST API.

    Returns a list of records matching the query, with optional field selection
    and pagination. Use this when no domain-specific tool covers the target table.
    """
    url = f"{config.api_url}/table/{params.table}"
    query_params: Dict[str, Any] = {
        "sysparm_limit": params.limit,
        "sysparm_offset": params.offset,
    }
    if params.query:
        query_params["sysparm_query"] = params.query
    if params.fields:
        query_params["sysparm_fields"] = params.fields
    if params.order_by:
        direction = (params.order_direction or "asc").upper()
        query_params["sysparm_query"] = (
            (query_params.get("sysparm_query", "") + f"^ORDERBY{'DESC' if direction == 'DESC' else ''}{params.order_by}").lstrip("^")
        )

    try:
        response = requests.get(
            url,
            params=query_params,
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()
        records: List[Dict] = response.json().get("result", [])
        result = {
            "success": True,
            "table": params.table,
            "operation": "query_records",
            "data": {
                "count": len(records),
                "records": records,
            },
        }
        if params.include_query_info:
            result["query_info"] = {
                "table": params.table,
                "encoded_query": params.query or "",
                "limit": params.limit,
                "offset": params.offset,
                "fields": params.fields,
            }
        return result
    except requests.RequestException as e:
        body = getattr(e, "response", None)
        body_text = (body.text[:2000] if body and hasattr(body, "text") else "") or ""
        logger.error("query_records | table=%s | error=%s", params.table, e)
        return {
            "success": False,
            "table": params.table,
            "error": str(e) + (f" | response: {body_text}" if body_text else ""),
        }


# ---------------------------------------------------------------------------
# get_record
# ---------------------------------------------------------------------------


class GetRecordParams(BaseModel):
    """Parameters for retrieving a single record by sys_id."""

    table: str = Field(..., description="ServiceNow table name.")
    sys_id: str = Field(..., description="32-character sys_id of the record to retrieve.")
    fields: Optional[str] = Field(
        None,
        description="Comma-separated field list to return. Leave empty for all fields.",
    )


def get_record(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: GetRecordParams,
) -> Dict[str, Any]:
    """
    Retrieve a single record from any ServiceNow table by sys_id.
    """
    try:
        sys_id = resolve_identifier(config, auth_manager, params.table, params.sys_id)
    except ValueError as e:
        return SnowResponse(
            success=False,
            error=str(e),
            table=params.table,
            operation="get_record",
        ).to_dict()

    url = f"{config.api_url}/table/{params.table}/{sys_id}"
    query_params: Dict[str, Any] = {}
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
        record = response.json().get("result", {})
        return SnowResponse(
            success=True,
            data=record,
            table=params.table,
            operation="get_record",
        ).to_dict()
    except requests.RequestException as e:
        body = getattr(e, "response", None)
        body_text = (body.text[:2000] if body and hasattr(body, "text") else "") or ""
        logger.error("get_record | table=%s | sys_id=%s | error=%s", params.table, sys_id, e)
        return SnowResponse(
            success=False,
            error=str(e) + (f" | response: {body_text}" if body_text else ""),
            table=params.table,
            operation="get_record",
        ).to_dict()


# ---------------------------------------------------------------------------
# create_record
# ---------------------------------------------------------------------------


class CreateRecordParams(BaseModel):
    """Parameters for creating a new record in any ServiceNow table."""

    table: str = Field(..., description="ServiceNow table name to insert the record into.")
    fields: Dict[str, Any] = Field(
        ...,
        description=(
            "Key-value pairs of field names and values to set on the new record "
            "(e.g., {\"short_description\": \"Test\", \"state\": \"1\"}). "
            "Use get_field_metadata to verify a field is writable before including it."
        ),
    )


def create_record(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: CreateRecordParams,
) -> Dict[str, Any]:
    """
    Create a new record in any ServiceNow table.

    Returns the sys_id and full record of the created row. Use verify_fields
    after creation to confirm field values persisted as intended.
    """
    policy_error = _enforce_update_set_policy(config, auth_manager, params.table)
    if policy_error:
        return policy_error

    mandatory_fields, fetch_error = _fetch_mandatory_fields(config, auth_manager, params.table)
    if not fetch_error and mandatory_fields:
        missing = sorted(mandatory_fields - set(params.fields.keys()))
        if missing:
            return {
                "success": False,
                "table": params.table,
                "error": (
                    f"Missing mandatory fields: {missing}. "
                    "Populate all mandatory fields before calling create_record. "
                    "Use get_field_metadata to inspect each field if needed."
                ),
                "missing_mandatory_fields": missing,
            }

    url = f"{config.api_url}/table/{params.table}"
    try:
        response = requests.post(
            url,
            json=params.fields,
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()
        record = response.json().get("result", {})
        return {
            "success": True,
            "table": params.table,
            "sys_id": record.get("sys_id", ""),
            "record": record,
        }
    except requests.RequestException as e:
        body = getattr(e, "response", None)
        body_text = (body.text[:2000] if body and hasattr(body, "text") else "") or ""
        logger.error("create_record | table=%s | error=%s", params.table, e)
        return {
            "success": False,
            "table": params.table,
            "error": str(e) + (f" | response: {body_text}" if body_text else ""),
        }


# ---------------------------------------------------------------------------
# update_record
# ---------------------------------------------------------------------------


class UpdateRecordParams(BaseModel):
    """Parameters for updating an existing record in any ServiceNow table."""

    table: str = Field(..., description="ServiceNow table name.")
    sys_id: str = Field(..., description="sys_id of the record to update.")
    fields: Dict[str, Any] = Field(
        ...,
        description=(
            "Key-value pairs of fields to update. Only included fields are changed — "
            "omitted fields are left as-is. Use get_field_metadata to verify writeability."
        ),
    )


def update_record(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: UpdateRecordParams,
) -> Dict[str, Any]:
    """
    Update an existing record in any ServiceNow table via PATCH.

    Only provided fields are modified. Use verify_fields after the update to
    confirm values persisted — server-side rules may override written values.
    """
    policy_error = _enforce_update_set_policy(config, auth_manager, params.table)
    if policy_error:
        return policy_error
    try:
        sys_id = resolve_identifier(config, auth_manager, params.table, params.sys_id)
    except ValueError as e:
        return {
            "success": False,
            "table": params.table,
            "sys_id": params.sys_id,
            "error": str(e),
        }
    url = f"{config.api_url}/table/{params.table}/{sys_id}"
    try:
        response = requests.patch(
            url,
            json=params.fields,
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()
        record = response.json().get("result", {})
        return {
            "success": True,
            "table": params.table,
            "sys_id": sys_id,
            "record": record,
        }
    except requests.RequestException as e:
        body = getattr(e, "response", None)
        body_text = (body.text[:2000] if body and hasattr(body, "text") else "") or ""
        logger.error("update_record | table=%s | sys_id=%s | error=%s", params.table, sys_id, e)
        return {
            "success": False,
            "table": params.table,
            "sys_id": sys_id,
            "error": str(e) + (f" | response: {body_text}" if body_text else ""),
        }


# ---------------------------------------------------------------------------
# delete_record
# ---------------------------------------------------------------------------


class DeleteRecordParams(BaseModel):
    """Parameters for deleting a record from any ServiceNow table."""

    table: str = Field(..., description="ServiceNow table name.")
    sys_id: str = Field(..., description="sys_id of the record to delete.")


def delete_record(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: DeleteRecordParams,
) -> Dict[str, Any]:
    """
    Delete a record from any ServiceNow table by sys_id.

    This is a destructive operation. Confirm the sys_id and table before calling.
    """
    policy_error = _enforce_update_set_policy(config, auth_manager, params.table)
    if policy_error:
        return policy_error
    try:
        sys_id = resolve_identifier(config, auth_manager, params.table, params.sys_id)
    except ValueError as e:
        return {
            "success": False,
            "table": params.table,
            "sys_id": params.sys_id,
            "error": str(e),
        }
    url = f"{config.api_url}/table/{params.table}/{sys_id}"
    try:
        response = requests.delete(
            url,
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()
        return {
            "success": True,
            "table": params.table,
            "sys_id": sys_id,
            "message": f"Record {sys_id} deleted from {params.table}.",
        }
    except requests.RequestException as e:
        body = getattr(e, "response", None)
        body_text = (body.text[:2000] if body and hasattr(body, "text") else "") or ""
        logger.error("delete_record | table=%s | sys_id=%s | error=%s", params.table, sys_id, e)
        return {
            "success": False,
            "table": params.table,
            "sys_id": sys_id,
            "error": str(e) + (f" | response: {body_text}" if body_text else ""),
        }
