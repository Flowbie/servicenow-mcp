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
from enum import Enum
from typing import Optional

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
