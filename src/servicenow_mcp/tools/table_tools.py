"""
Generic Table API tools for the ServiceNow MCP server.

Provides CRUD operations against any ServiceNow table via the Table REST API
(/api/now/table/{table_name}). Use these when no domain-specific tool exists
for the target table.
"""

import asyncio
import logging
import os
import threading
from typing import Any, Dict, List, Optional

import requests
from pydantic import BaseModel, Field

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.utils.config import ServerConfig

logger = logging.getLogger(__name__)


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
        return {
            "success": True,
            "table": params.table,
            "count": len(records),
            "records": records,
        }
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
    url = f"{config.api_url}/table/{params.table}/{params.sys_id}"
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
        return {
            "success": True,
            "table": params.table,
            "sys_id": params.sys_id,
            "record": record,
        }
    except requests.RequestException as e:
        body = getattr(e, "response", None)
        body_text = (body.text[:2000] if body and hasattr(body, "text") else "") or ""
        logger.error("get_record | table=%s | sys_id=%s | error=%s", params.table, params.sys_id, e)
        return {
            "success": False,
            "table": params.table,
            "sys_id": params.sys_id,
            "error": str(e) + (f" | response: {body_text}" if body_text else ""),
        }


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
    if os.environ.get("WORKBENCH_URL"):
        _decision_holder: list = []
        _exc_holder: list = []

        def _run():
            try:
                from servicenow_mcp.utils.approval_client import request_approval, ApprovalDecision
                _decision_holder.append(asyncio.run(request_approval(
                    "create_record",
                    params.model_dump(),
                    os.environ.get("WORKBENCH_PROJECT_ID", ""),
                )))
            except Exception as e:
                _exc_holder.append(e)

        t = threading.Thread(target=_run, daemon=True)
        t.start()
        t.join(timeout=330)
        if t.is_alive():
            return {"error": "Approval timed out", "approved": False}
        if _exc_holder:
            raise _exc_holder[0]
        _decision = _decision_holder[0] if _decision_holder else None
        from servicenow_mcp.utils.approval_client import ApprovalDecision
        if _decision is None or _decision != ApprovalDecision.APPROVED:
            return {"error": "Operation rejected by user", "approved": False}

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
    if os.environ.get("WORKBENCH_URL"):
        _decision_holder: list = []
        _exc_holder: list = []

        def _run():
            try:
                from servicenow_mcp.utils.approval_client import request_approval, ApprovalDecision
                _decision_holder.append(asyncio.run(request_approval(
                    "update_record",
                    params.model_dump(),
                    os.environ.get("WORKBENCH_PROJECT_ID", ""),
                )))
            except Exception as e:
                _exc_holder.append(e)

        t = threading.Thread(target=_run, daemon=True)
        t.start()
        t.join(timeout=330)
        if t.is_alive():
            return {"error": "Approval timed out", "approved": False}
        if _exc_holder:
            raise _exc_holder[0]
        _decision = _decision_holder[0] if _decision_holder else None
        from servicenow_mcp.utils.approval_client import ApprovalDecision
        if _decision is None or _decision != ApprovalDecision.APPROVED:
            return {"error": "Operation rejected by user", "approved": False}

    url = f"{config.api_url}/table/{params.table}/{params.sys_id}"
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
            "sys_id": params.sys_id,
            "record": record,
        }
    except requests.RequestException as e:
        body = getattr(e, "response", None)
        body_text = (body.text[:2000] if body and hasattr(body, "text") else "") or ""
        logger.error("update_record | table=%s | sys_id=%s | error=%s", params.table, params.sys_id, e)
        return {
            "success": False,
            "table": params.table,
            "sys_id": params.sys_id,
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
    if os.environ.get("WORKBENCH_URL"):
        _decision_holder: list = []
        _exc_holder: list = []

        def _run():
            try:
                from servicenow_mcp.utils.approval_client import request_approval, ApprovalDecision
                _decision_holder.append(asyncio.run(request_approval(
                    "delete_record",
                    params.model_dump(),
                    os.environ.get("WORKBENCH_PROJECT_ID", ""),
                )))
            except Exception as e:
                _exc_holder.append(e)

        t = threading.Thread(target=_run, daemon=True)
        t.start()
        t.join(timeout=330)
        if t.is_alive():
            return {"error": "Approval timed out", "approved": False}
        if _exc_holder:
            raise _exc_holder[0]
        _decision = _decision_holder[0] if _decision_holder else None
        from servicenow_mcp.utils.approval_client import ApprovalDecision
        if _decision is None or _decision != ApprovalDecision.APPROVED:
            return {"error": "Operation rejected by user", "approved": False}

    url = f"{config.api_url}/table/{params.table}/{params.sys_id}"
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
            "sys_id": params.sys_id,
            "message": f"Record {params.sys_id} deleted from {params.table}.",
        }
    except requests.RequestException as e:
        body = getattr(e, "response", None)
        body_text = (body.text[:2000] if body and hasattr(body, "text") else "") or ""
        logger.error("delete_record | table=%s | sys_id=%s | error=%s", params.table, params.sys_id, e)
        return {
            "success": False,
            "table": params.table,
            "sys_id": params.sys_id,
            "error": str(e) + (f" | response: {body_text}" if body_text else ""),
        }
