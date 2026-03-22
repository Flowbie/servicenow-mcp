"""
Agile reporting tools for the ServiceNow MCP server.

Read-focused tools that surface blocked stories and release status dashboards for teams.
"""

import logging
from typing import Any, Dict, List, Optional

import requests
from pydantic import BaseModel, Field

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.utils.config import ServerConfig
from servicenow_mcp.tools.release_tools import (
    _resolve_release,
    _fetch_release_stories,
    _extract_sys_id,
)
from servicenow_mcp.tools.agile_constants import (
    STORY_DONE_STATES,
    STORY_CANCELLED_STATES,
    STORY_IN_PROGRESS_STATES,
    STORY_BACKLOG_STATES,
    SPRINT_COMPLETED_STATE,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Params models
# ---------------------------------------------------------------------------



class GetBlockedWorkParams(BaseModel):
    """Parameters for retrieving stories that are blocked by unfinished prerequisites."""

    sprint_id: Optional[str] = Field(
        None,
        description=(
            "Optional sprint sys_id to restrict results to a single sprint. "
            "When omitted, returns blocked stories across all sprints."
        ),
    )
    limit: int = Field(
        default=25,
        ge=1,
        le=200,
        description="Maximum number of blocked stories to return. Defaults to 25.",
    )


class GetReleaseStatusParams(BaseModel):
    """Parameters for a release status dashboard."""

    release_id: str = Field(
        ...,
        description="Release sys_id, number, or name.",
    )



# ---------------------------------------------------------------------------
# get_blocked_work
# ---------------------------------------------------------------------------


def get_blocked_work(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: GetBlockedWorkParams,
) -> Dict[str, Any]:
    """
    Return stories that are blocked by unfinished prerequisites.

    Queries m2m_story_dependencies with dot-walked state fields to allow
    server-side efficiency, then filters in Python to confirm open blockers.
    Optionally restricts results to a single sprint.
    """
    dep_url = f"{config.instance_url}/api/now/table/m2m_story_dependencies"
    headers = auth_manager.get_headers()

    try:
        response = requests.get(
            dep_url,
            headers=headers,
            params={
                "sysparm_fields": (
                    "sys_id,dependent_story,dependent_story.number,"
                    "dependent_story.short_description,dependent_story.state,"
                    "dependent_story.sprint,"
                    "prerequisite_story,prerequisite_story.number,"
                    "prerequisite_story.short_description,prerequisite_story.state"
                ),
                "sysparm_limit": 500,
            },
            timeout=config.timeout,
        )
        response.raise_for_status()
        all_deps: List[Dict] = response.json().get("result", [])
    except requests.RequestException as e:
        body = getattr(e, "response", None)
        body_text = (body.text[:2000] if body and hasattr(body, "text") else "") or ""
        logger.error("get_blocked_work | error=%s", e)
        return {
            "success": False,
            "message": f"Failed to fetch dependencies: {e}" + (f" | {body_text}" if body_text else ""),
        }

    # Filter: keep rows where prerequisite is NOT done or cancelled
    open_deps = [
        dep for dep in all_deps
        if str(dep.get("prerequisite_story.state") or "") not in (
            STORY_DONE_STATES | STORY_CANCELLED_STATES
        )
    ]

    # Group by dependent_story sys_id (dedup)
    grouped: Dict[str, Dict[str, Any]] = {}
    for dep in open_deps:
        dep_story_id = str(dep.get("dependent_story") or "")
        if not dep_story_id:
            continue

        dep_sprint_raw = dep.get("dependent_story.sprint") or ""
        dep_sprint_id = (
            dep_sprint_raw.get("value", dep_sprint_raw)
            if isinstance(dep_sprint_raw, dict)
            else str(dep_sprint_raw)
        )

        # Optional sprint filter
        if params.sprint_id and dep_sprint_id != params.sprint_id:
            continue

        if dep_story_id not in grouped:
            grouped[dep_story_id] = {
                "story_id": dep_story_id,
                "story_number": dep.get("dependent_story.number"),
                "title": dep.get("dependent_story.short_description"),
                "sprint": dep_sprint_id,
                "blockers": [],
            }

        grouped[dep_story_id]["blockers"].append(
            {
                "prerequisite_story_number": dep.get("prerequisite_story.number"),
                "prerequisite_story_title": dep.get(
                    "prerequisite_story.short_description"
                ),
                "prerequisite_state": dep.get("prerequisite_story.state"),
            }
        )

    blocked_stories = list(grouped.values())[: params.limit]

    return {
        "success": True,
        "count": len(blocked_stories),
        "blocked_stories": blocked_stories,
    }


# ---------------------------------------------------------------------------
# get_release_status
# ---------------------------------------------------------------------------


def get_release_status(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: GetReleaseStatusParams,
) -> Dict[str, Any]:
    """
    Return a status dashboard for a release: sprint counts, story counts,
    point totals, and an overall_status signal.

    overall_status values:
      not_started  — no active/completed sprints and no in-progress stories
      on_track     — sprints active, stories progressing normally
      at_risk      — some stories in backlog with sprint(s) active
      complete     — all sprints completed and all stories done/cancelled
    """
    release = _resolve_release(config, auth_manager, params.release_id.strip())
    if not release:
        return {
            "success": False,
            "error_code": "RELEASE_NOT_FOUND",
            "message": f"No release found: '{params.release_id}'",
        }

    release_sys_id = _extract_sys_id(release)
    headers = auth_manager.get_headers()

    # Fetch sprints
    sprint_url = f"{config.instance_url}/api/now/table/rm_sprint_2"
    try:
        resp = requests.get(
            sprint_url,
            headers=headers,
            params={
                "sysparm_query": f"release={release_sys_id}",
                "sysparm_fields": "sys_id,state,name",
                "sysparm_limit": 100,
            },
            timeout=config.timeout,
        )
        resp.raise_for_status()
        sprints = resp.json().get("result", [])
    except requests.RequestException as e:
        logger.error("get_release_status | sprint fetch | error=%s", e)
        sprints = []

    # Sprint counts by state
    sprint_counts: Dict[str, int] = {
        "total": len(sprints),
        "planning": 0,
        "active": 0,
        "completed": 0,
        "cancelled": 0,
    }
    _sprint_state_map = {"1": "planning", "2": "active", "3": "completed", "4": "cancelled"}
    for sprint in sprints:
        label = _sprint_state_map.get(str(sprint.get("state", "")), "planning")
        sprint_counts[label] += 1

    # Fetch stories
    stories = _fetch_release_stories(
        config,
        auth_manager,
        release_sys_id,
        fields="sys_id,number,state,story_points",
        limit=500,
    )

    # Story counts and points
    story_counts: Dict[str, int] = {
        "total": len(stories),
        "done": 0,
        "in_progress": 0,
        "backlog": 0,
        "cancelled": 0,
    }
    points: Dict[str, int] = {"total": 0, "completed": 0, "remaining": 0}

    for story in stories:
        state = str(story.get("state", ""))
        pts = int(story.get("story_points") or 0)
        points["total"] += pts

        if state in STORY_DONE_STATES:
            story_counts["done"] += 1
            points["completed"] += pts
        elif state in STORY_IN_PROGRESS_STATES:
            story_counts["in_progress"] += 1
            points["remaining"] += pts
        elif state in STORY_BACKLOG_STATES:
            story_counts["backlog"] += 1
            points["remaining"] += pts
        elif state in STORY_CANCELLED_STATES:
            story_counts["cancelled"] += 1

    # Derive overall status
    non_cancelled_stories = story_counts["total"] - story_counts["cancelled"]
    all_done = non_cancelled_stories > 0 and story_counts["done"] >= non_cancelled_stories
    all_sprints_done = sprint_counts["total"] > 0 and sprint_counts["completed"] == sprint_counts["total"]

    if all_done and all_sprints_done:
        overall_status = "complete"
    elif sprint_counts["active"] == 0 and story_counts["in_progress"] == 0 and story_counts["done"] == 0:
        overall_status = "not_started"
    elif story_counts["backlog"] > 0 and sprint_counts["active"] > 0:
        overall_status = "at_risk"
    else:
        overall_status = "on_track"

    # Normalise display fields
    release_name = release.get("name") or ""
    if isinstance(release_name, dict):
        release_name = release_name.get("display_value") or release_name.get("value", "")

    planned_date = release.get("planned_date") or ""
    if isinstance(planned_date, dict):
        planned_date = planned_date.get("display_value") or planned_date.get("value", "")

    return {
        "success": True,
        "release": {
            "sys_id": release_sys_id,
            "name": release_name,
            "planned_date": planned_date,
        },
        "sprint_counts": sprint_counts,
        "story_counts": story_counts,
        "points": points,
        "overall_status": overall_status,
    }
