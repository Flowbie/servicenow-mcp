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
            json={"tool_name": tool_name, "params": params, "project_id": project_id},
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
                    _decision_holder.append(asyncio.run(request_approval(
                        tool_name,
                        raw_params,
                        os.environ.get("WORKBENCH_PROJECT_ID", ""),
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
