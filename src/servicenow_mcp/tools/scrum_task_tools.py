"""
Scrum Task management tools for the ServiceNow MCP server.

Compound functions only. CRUD operations (create, update, list, get, assign
scrum tasks) have been removed as public tools — use the generic table_tools
(query_records, get_record, create_record, update_record, delete_record) with
the agile architecture blueprint instead.

States: -6=Draft, 1=Ready, 2=Work in progress, 3=Complete, 4=Cancelled
Types:  1=Analysis, 2=Coding, 3=Documentation, 4=Testing
"""

import logging
from typing import Any, Dict, Optional

import requests
from pydantic import BaseModel, Field

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.utils.config import ServerConfig

logger = logging.getLogger(__name__)

# Closed states — Complete (3) or Cancelled (4)
_CLOSED_STATES = {"3", "4"}


# ---------------------------------------------------------------------------
# Params models
# ---------------------------------------------------------------------------


class CloseScrumTaskParams(BaseModel):
    """Parameters for closing a scrum task."""

    scrum_task_id: str = Field(..., description="sys_id of the scrum task to close")
    work_notes: Optional[str] = Field(None, description="Optional closing notes")


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------


def close_scrum_task(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: CloseScrumTaskParams,
) -> Dict[str, Any]:
    """Close a scrum task by setting its state to Complete (3)."""
    # First fetch the current state to check guard condition
    get_url = f"{config.instance_url}/api/now/table/rm_scrum_task/{params.scrum_task_id}"

    try:
        get_response = requests.get(
            get_url,
            headers=auth_manager.get_headers(),
            params={"sysparm_fields": "sys_id,state", "sysparm_display_value": "false"},
            timeout=config.timeout,
        )
        if get_response.status_code == 404:
            return {
                "success": False,
                "message": "Scrum task not found",
            }
        get_response.raise_for_status()
        current = get_response.json().get("result")
        if not current:
            return {
                "success": False,
                "message": "Scrum task not found",
            }

        current_state = str(current.get("state") or "")
        if current_state in _CLOSED_STATES:
            return {
                "success": False,
                "message": "Scrum task is already closed (Complete or Cancelled)",
            }
    except requests.RequestException as e:
        logger.error("close_scrum_task (get phase) | task_id=%s | error=%s", params.scrum_task_id, e)
        return {
            "success": False,
            "message": f"Error retrieving scrum task: {e}",
        }

    # Now patch state to Complete
    patch_data: Dict[str, Any] = {"state": "3"}
    if params.work_notes:
        patch_data["work_notes"] = params.work_notes

    headers = auth_manager.get_headers()
    headers["Content-Type"] = "application/json"

    try:
        patch_response = requests.patch(
            get_url,
            json=patch_data,
            headers=headers,
            timeout=config.timeout,
        )
        patch_response.raise_for_status()
        return {
            "success": True,
            "message": "Scrum task closed",
            "scrum_task": patch_response.json()["result"],
        }
    except requests.RequestException as e:
        logger.error("close_scrum_task (patch phase) | task_id=%s | error=%s", params.scrum_task_id, e)
        return {
            "success": False,
            "message": f"Error closing scrum task: {e}",
        }
