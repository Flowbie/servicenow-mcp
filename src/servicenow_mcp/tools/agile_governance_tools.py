"""
Agile governance tools for the ServiceNow MCP server.

Read-only tools that validate story quality gates before state transitions
or promotions. All three tools are safe to call without write permissions.
"""

import logging
from typing import Any, Dict, List

import requests

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.agile_constants import STORY_TERMINAL_STATES, StoryIdParams
from servicenow_mcp.utils.config import ServerConfig

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# State constants
# ---------------------------------------------------------------------------

# Scrum tasks: Complete (3) or Cancelled (4) are done states
# -6=Draft, 1=Ready, 2=Work in progress, 3=Complete, 4=Cancelled
_SCRUM_TASK_DONE_STATES = {"3", "4"}


# ---------------------------------------------------------------------------
# validate_story_dependencies
# ---------------------------------------------------------------------------


def validate_story_dependencies(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: StoryIdParams,
) -> Dict[str, Any]:
    """
    Check that all prerequisite stories for this story are Complete or Cancelled.

    Queries m2m_story_dependencies where dependent_story=<story_id> and inspects
    the state of each prerequisite_story. Returns all_dependencies_met: true only
    when every prerequisite is in state 3 (Complete) or 4 (Cancelled).

    A story with no dependencies returns all_dependencies_met: true (vacuously satisfied).
    """
    url = f"{config.instance_url}/api/now/table/m2m_story_dependencies"

    try:
        response = requests.get(
            url,
            headers=auth_manager.get_headers(),
            params={
                "sysparm_query": f"dependent_story={params.story_id}",
                "sysparm_fields": (
                    "sys_id,prerequisite_story,prerequisite_story.number,"
                    "prerequisite_story.short_description,prerequisite_story.state"
                ),
                "sysparm_display_value": "false",
                "sysparm_limit": 200,
            },
            timeout=config.timeout,
        )
        response.raise_for_status()
        deps: List[Dict] = response.json().get("result", [])
    except requests.RequestException as e:
        body = getattr(e, "response", None)
        body_text = (body.text[:2000] if body and hasattr(body, "text") else "") or ""
        logger.error(
            "validate_story_dependencies | story_id=%s | error=%s",
            params.story_id,
            e,
        )
        return {
            "success": False,
            "message": f"Failed to fetch dependencies: {e}"
            + (f" | {body_text}" if body_text else ""),
        }

    open_blockers = []
    for dep in deps:
        state = str(dep.get("prerequisite_story.state") or "")
        if state not in STORY_TERMINAL_STATES:
            open_blockers.append(
                {
                    "sys_id": dep.get("sys_id"),
                    "number": dep.get("prerequisite_story.number"),
                    "title": dep.get("prerequisite_story.short_description"),
                    "state": state,
                }
            )

    return {
        "success": True,
        "story_id": params.story_id,
        "all_dependencies_met": len(open_blockers) == 0,
        "open_blockers": open_blockers,
    }


# ---------------------------------------------------------------------------
# validate_story_testing
# ---------------------------------------------------------------------------


def validate_story_testing(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: StoryIdParams,
) -> Dict[str, Any]:
    """
    Check that at least one testing task exists for this story and all are done.

    Queries rm_scrum_task where story=<story_id> AND type=4 (Testing).
    Returns testing_complete: true only when at least one testing task exists
    and every task is in state 3 (Complete) or 4 (Cancelled).
    """
    url = f"{config.instance_url}/api/now/table/rm_scrum_task"

    try:
        response = requests.get(
            url,
            headers=auth_manager.get_headers(),
            params={
                "sysparm_query": f"story={params.story_id}^type=4",
                "sysparm_fields": "sys_id,number,short_description,state,assigned_to",
                "sysparm_display_value": "false",
                "sysparm_limit": 200,
            },
            timeout=config.timeout,
        )
        response.raise_for_status()
        tasks: List[Dict] = response.json().get("result", [])
    except requests.RequestException as e:
        body = getattr(e, "response", None)
        body_text = (body.text[:2000] if body and hasattr(body, "text") else "") or ""
        logger.error(
            "validate_story_testing | story_id=%s | error=%s",
            params.story_id,
            e,
        )
        return {
            "success": False,
            "message": f"Failed to fetch scrum tasks: {e}"
            + (f" | {body_text}" if body_text else ""),
        }

    if not tasks:
        return {
            "success": True,
            "story_id": params.story_id,
            "testing_complete": False,
            "total_testing_tasks": 0,
            "incomplete_tasks": [],
            "message": "No testing tasks found for this story.",
        }

    incomplete = [
        {
            "number": t.get("number"),
            "title": t.get("short_description"),
            "state": t.get("state"),
            "assigned_to": t.get("assigned_to"),
        }
        for t in tasks
        if str(t.get("state") or "") not in _SCRUM_TASK_DONE_STATES
    ]

    return {
        "success": True,
        "story_id": params.story_id,
        "testing_complete": len(incomplete) == 0,
        "total_testing_tasks": len(tasks),
        "incomplete_tasks": incomplete,
    }


# ---------------------------------------------------------------------------
# validate_story_promotion_instructions
# ---------------------------------------------------------------------------


def validate_story_promotion_instructions(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: StoryIdParams,
) -> Dict[str, Any]:
    """
    Check that the story has non-empty promotion instructions.

    Queries rm_story for the promotion_instructions field. Returns
    has_promotion_instructions: true only when the field is present and
    contains non-whitespace content.
    """
    url = f"{config.instance_url}/api/now/table/rm_story/{params.story_id}"

    try:
        response = requests.get(
            url,
            headers=auth_manager.get_headers(),
            params={
                "sysparm_fields": "sys_id,number,promotion_instructions",
                "sysparm_display_value": "false",
            },
            timeout=config.timeout,
        )
        response.raise_for_status()
        result = response.json().get("result")
    except requests.RequestException as e:
        body = getattr(e, "response", None)
        body_text = (body.text[:2000] if body and hasattr(body, "text") else "") or ""
        logger.error(
            "validate_story_promotion_instructions | story_id=%s | error=%s",
            params.story_id,
            e,
        )
        return {
            "success": False,
            "message": f"Failed to fetch story: {e}"
            + (f" | {body_text}" if body_text else ""),
        }

    if not result:
        return {
            "success": False,
            "error_code": "STORY_NOT_FOUND",
            "message": f"No story found with sys_id: {params.story_id}",
        }

    raw_value = result.get("promotion_instructions") or ""
    if isinstance(raw_value, dict):
        raw_value = raw_value.get("value", "")
    field_value = str(raw_value).strip()

    return {
        "success": True,
        "story_id": params.story_id,
        "has_promotion_instructions": bool(field_value),
        "field_value": field_value,
    }
