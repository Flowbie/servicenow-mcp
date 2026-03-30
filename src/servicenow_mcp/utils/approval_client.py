"""
Approval gate client for the ServiceNow Cloud OS Workbench.

When WORKBENCH_URL is set, write tools must call request_approval() before
executing. This suspends the tool until the user approves or rejects the
operation in the workbench UI.

If WORKBENCH_URL is not set, this module is never imported by tool code and
the gate is fully transparent — backward-compatible with direct CLI usage.
"""

import asyncio
import os
import threading
from enum import Enum
from typing import Any, Callable, Optional

import requests

try:
    import httpx
    _HTTPX_AVAILABLE = True
except ImportError:
    _HTTPX_AVAILABLE = False


class ApprovalDecision(str, Enum):
    APPROVED = "approved"
    REJECTED = "rejected"


APPROVAL_POLL_INTERVAL = 0.5  # seconds
APPROVAL_TIMEOUT = 300.0  # 5 minutes

# All MCP tools that mutate ServiceNow state and require user approval.
# Applied centrally in tool_utils.py — individual tool files must NOT
# implement their own approval logic.
WRITE_TOOLS = {
    # Generic table API
    "create_record",
    "update_record",
    "delete_record",
    # Background script execution
    "run_background_script",
    # Flow Designer
    "create_flow",
    "update_flow",
    "publish_flow",
    "create_subflow",
    "update_subflow",
    "publish_subflow",
    "create_action",
    "update_action",
    "publish_action",
    # Story management
    "archive_story",
    "move_story_state",
    "assign_stories_to_sprint",
    # Scrum tasks
    "close_scrum_task",
    # Sprint management
    "create_sprint",
    "start_sprint",
    "close_sprint",
    # User/group role management
    "grant_role_to_user",
    "revoke_role_from_user",
    "grant_role_to_group",
    "revoke_role_from_group",
    # Change management
    "submit_change_for_approval",
    "approve_change",
    "reject_change",
    # Catalog
    "move_catalog_items",
    # Update sets
    "set_current_update_set",
    # CMDB relationships
    "create_ci_relationship",
}


async def request_approval(
    tool_name: str,
    params: dict,
    project_id: str,
    payload: Optional[dict] = None,
    workbench_url: Optional[str] = None,
) -> ApprovalDecision:
    """
    POST an approval request to the workbench backend, then poll until resolved.

    Suspends the calling MCP tool handler until the user approves or rejects.
    Falls back gracefully if httpx is not available or workbench is unreachable.
    """
    if not _HTTPX_AVAILABLE:
        raise RuntimeError("httpx is required for approval gate — install it in the venv")

    url = workbench_url or os.environ.get("WORKBENCH_URL", "http://localhost:8742")

    async with httpx.AsyncClient() as client:
        # Register the pending approval
        resp = await client.post(
            f"{url}/approvals/pending",
            json={
                "tool_name": tool_name,
                "params": params,
                "project_id": project_id,
                "payload": payload or {},
            },
            timeout=10.0,
        )
        resp.raise_for_status()
        approval_id = resp.json()["approval_id"]

        # Poll for decision
        elapsed = 0.0
        while elapsed < APPROVAL_TIMEOUT:
            await asyncio.sleep(APPROVAL_POLL_INTERVAL)
            elapsed += APPROVAL_POLL_INTERVAL
            status_resp = await client.get(
                f"{url}/approvals/{approval_id}/status",
                timeout=5.0,
            )
            if status_resp.status_code == 200:
                status = status_resp.json().get("status")
                if status == "approved":
                    return ApprovalDecision.APPROVED
                if status == "rejected":
                    return ApprovalDecision.REJECTED

        raise TimeoutError(f"Approval timed out after {APPROVAL_TIMEOUT}s for tool '{tool_name}'")


def wrap_write_tool(tool_name: str, func: Callable) -> Callable:
    """Wrap a write tool to require workbench approval before execution.

    When WORKBENCH_URL is not set (direct CLI usage) the wrapper is a no-op and
    the tool executes immediately — fully backward-compatible.

    Applied once at registration time in tool_utils.py. Individual tool files
    must not implement their own approval logic.
    """
    def wrapped(config: Any, auth_manager: Any, params: Any) -> Any:
        if os.environ.get("WORKBENCH_URL"):
            _decision_holder: list = []
            _exc_holder: list = []

            def _run() -> None:
                try:
                    raw_params = params.model_dump() if hasattr(params, "model_dump") else dict(params)
                    payload = build_approval_payload(tool_name, config, auth_manager, raw_params)
                    _decision_holder.append(asyncio.run(request_approval(
                        tool_name,
                        raw_params,
                        os.environ.get("WORKBENCH_PROJECT_ID", ""),
                        payload=payload,
                    )))
                except Exception as exc:
                    _exc_holder.append(exc)

            t = threading.Thread(target=_run, daemon=True)
            t.start()
            t.join(timeout=330)
            if t.is_alive():
                return {"error": "Approval timed out", "approved": False}
            if _exc_holder:
                raise _exc_holder[0]
            decision = _decision_holder[0] if _decision_holder else None
            if decision is None or decision != ApprovalDecision.APPROVED:
                return {"error": "Operation rejected by user", "approved": False}

        return func(config, auth_manager, params)

    wrapped.__name__ = func.__name__
    wrapped.__doc__ = func.__doc__
    return wrapped


def build_approval_payload(
    tool_name: str,
    config: Any,
    auth_manager: Any,
    raw_params: dict,
) -> dict:
    builders = {
        "create_record": _build_create_record_payload,
        "update_record": _build_update_record_payload,
        "delete_record": _build_delete_record_payload,
        "set_current_update_set": _build_set_current_update_set_payload,
        "run_background_script": _build_background_script_payload,
    }
    builder = builders.get(tool_name)
    if not builder:
        return {
            "tool_name": tool_name,
            "operation": "write",
            "raw_params": raw_params,
            "fields": {},
        }
    try:
        return builder(config, auth_manager, raw_params)
    except Exception:
        return {
            "tool_name": tool_name,
            "operation": "write",
            "raw_params": raw_params,
            "fields": {},
        }


def _guess_record_identifier(record: dict | None, fallback: str | None = None) -> str | None:
    if isinstance(record, dict):
        for key in ("number", "name", "short_description", "display_name", "sys_id"):
            value = record.get(key)
            if isinstance(value, str) and value:
                return value
    return fallback


def _fetch_table_record(config: Any, auth_manager: Any, table: str, sys_id: str) -> dict:
    response = requests.get(
        f"{config.api_url}/table/{table}/{sys_id}",
        headers=auth_manager.get_headers(),
        timeout=getattr(config, "timeout", 30),
    )
    response.raise_for_status()
    result = response.json().get("result", {})
    return result if isinstance(result, dict) else {}


def _build_field_diff(fields: dict, before_record: dict | None = None) -> dict:
    diffs: dict[str, dict[str, Any]] = {}
    for field, after_value in (fields or {}).items():
        before_value = None
        if isinstance(before_record, dict):
            before_value = before_record.get(field)
        diffs[field] = {
            "before": before_value,
            "after": after_value,
        }
    return diffs


def _build_create_record_payload(config: Any, auth_manager: Any, raw_params: dict) -> dict:
    table = raw_params.get("table", "")
    fields = raw_params.get("fields", {}) or {}
    return {
        "tool_name": "create_record",
        "operation": "create",
        "table": table,
        "record_identifier": _guess_record_identifier(fields),
        "fields": _build_field_diff(fields),
        "raw_params": raw_params,
    }


def _build_update_record_payload(config: Any, auth_manager: Any, raw_params: dict) -> dict:
    table = raw_params.get("table", "")
    sys_id = raw_params.get("sys_id", "")
    before_record = _fetch_table_record(config, auth_manager, table, sys_id)
    fields = raw_params.get("fields", {}) or {}
    return {
        "tool_name": "update_record",
        "operation": "update",
        "table": table,
        "record_identifier": _guess_record_identifier(before_record, sys_id),
        "fields": _build_field_diff(fields, before_record),
        "raw_params": raw_params,
    }


def _build_delete_record_payload(config: Any, auth_manager: Any, raw_params: dict) -> dict:
    table = raw_params.get("table", "")
    sys_id = raw_params.get("sys_id", "")
    before_record = _fetch_table_record(config, auth_manager, table, sys_id)
    return {
        "tool_name": "delete_record",
        "operation": "delete",
        "table": table,
        "record_identifier": _guess_record_identifier(before_record, sys_id),
        "fields": {},
        "raw_params": raw_params,
    }


def _build_set_current_update_set_payload(config: Any, auth_manager: Any, raw_params: dict) -> dict:
    changeset_id = raw_params.get("changeset_id", "")
    update_set = {}
    if changeset_id:
        response = requests.get(
            f"{config.instance_url}/api/now/table/sys_update_set/{changeset_id}",
            headers=auth_manager.get_headers(),
            timeout=getattr(config, "timeout", 30),
        )
        response.raise_for_status()
        result = response.json().get("result", {})
        update_set = result if isinstance(result, dict) else {}
    return {
        "tool_name": "set_current_update_set",
        "operation": "activate_update_set",
        "table": "sys_update_set",
        "record_identifier": _guess_record_identifier(update_set, changeset_id),
        "fields": {},
        "raw_params": raw_params,
    }


def _build_background_script_payload(config: Any, auth_manager: Any, raw_params: dict) -> dict:
    script = raw_params.get("script", "")
    return {
        "tool_name": "run_background_script",
        "operation": "execute_script",
        "table": "",
        "record_identifier": None,
        "fields": {},
        "raw_params": raw_params,
        "script_preview": script[:500] if isinstance(script, str) else "",
    }
