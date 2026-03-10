"""
Sprint management tools for the ServiceNow MCP server.

Provides create, get, and summary operations against the rm_sprint_2 table.
Sprint-to-story association is handled via update_story(sprint=sprint_id).
"""

import logging
from datetime import date
from typing import Any, Dict, List, Optional

import requests
from pydantic import BaseModel, Field

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.utils.config import ServerConfig

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Sprint state constants (rm_sprint_2.state)
# ---------------------------------------------------------------------------

# Numeric state values for rm_sprint_2
SPRINT_STATE_PLANNING = "1"
SPRINT_STATE_ACTIVE = "2"
SPRINT_STATE_COMPLETED = "3"
SPRINT_STATE_CANCELLED = "4"

_SPRINT_STATE_LABELS: Dict[str, str] = {
    SPRINT_STATE_PLANNING:  "Planning",
    SPRINT_STATE_ACTIVE:    "Active",
    SPRINT_STATE_COMPLETED: "Completed",
    SPRINT_STATE_CANCELLED: "Cancelled",
}

# States in which a sprint can still receive stories
_SPRINT_OPEN_STATES = {SPRINT_STATE_PLANNING, SPRINT_STATE_ACTIVE}

# Story state groupings (rm_story.state numeric values)
_STORY_DONE_STATES       = {"3"}
_STORY_IN_PROGRESS_STATES = {"2", "-7", "-8"}
_STORY_BACKLOG_STATES    = {"-6", "1"}
_STORY_CANCELLED_STATES  = {"4"}


# ---------------------------------------------------------------------------
# Params models
# ---------------------------------------------------------------------------

class CreateSprintParams(BaseModel):
    """Parameters for creating a new sprint."""

    name: str = Field(..., description="Human-readable sprint name (e.g. 'Sprint 14')")
    start_date: str = Field(
        ..., description="Sprint start date in YYYY-MM-DD format"
    )
    end_date: str = Field(
        ..., description="Sprint end date in YYYY-MM-DD format (must be after start_date)"
    )
    release_id: Optional[str] = Field(
        None,
        description="sys_id of the parent rm_release record. Recommended but not required.",
    )
    goal: Optional[str] = Field(
        None, description="Sprint goal statement (what the team commits to deliver)"
    )
    capacity: Optional[int] = Field(
        None,
        ge=0,
        description="Team capacity in story points for this sprint",
    )


class GetSprintParams(BaseModel):
    """Parameters for retrieving a single sprint."""

    sprint_id: str = Field(
        ...,
        description=(
            "Sprint sys_id, sprint number (e.g. SPRINT0001234), or sprint name "
            "(e.g. 'Sprint 14'). sys_id lookup is tried first; number/name query "
            "is used as a fallback."
        ),
    )


class GetSprintSummaryParams(BaseModel):
    """Parameters for retrieving a sprint summary with story aggregates."""

    sprint_id: str = Field(
        ...,
        description=(
            "Sprint sys_id, sprint number, or sprint name. "
            "Returns story counts grouped by state and total/completed/remaining story points."
        ),
    )
    include_stories: bool = Field(
        default=False,
        description=(
            "When true, includes the full list of stories in the response in addition to "
            "the aggregate counts. Defaults to false."
        ),
    )


class StartSprintParams(BaseModel):
    """Parameters for starting a sprint."""

    sprint_id: str = Field(
        ...,
        description="sys_id of the rm_sprint_2 record to start. Sprint must be in Planning state.",
    )


class CloseSprintParams(BaseModel):
    """Parameters for closing a sprint."""

    sprint_id: str = Field(
        ...,
        description="sys_id of the rm_sprint_2 record to close. Sprint must be in Active state.",
    )
    force: bool = Field(
        default=False,
        description=(
            "When false (default), the operation fails if open stories remain. "
            "When true, closes the sprint even if stories are still open."
        ),
    )


# ---------------------------------------------------------------------------
# create_sprint
# ---------------------------------------------------------------------------

def create_sprint(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: CreateSprintParams,
) -> Dict[str, Any]:
    """
    Create a new sprint in ServiceNow (rm_sprint_2).

    Validates that end_date is after start_date. The sprint is created in
    Planning state (1). Associate it with a release by providing release_id.
    """
    # Validate date range
    try:
        start = date.fromisoformat(params.start_date)
        end = date.fromisoformat(params.end_date)
    except ValueError as exc:
        return {
            "success": False,
            "error_code": "INVALID_DATE_FORMAT",
            "message": f"Dates must be in YYYY-MM-DD format. {exc}",
        }

    if end <= start:
        return {
            "success": False,
            "error_code": "INVALID_DATE_RANGE",
            "message": (
                f"end_date ({params.end_date}) must be after start_date ({params.start_date})."
            ),
            "start_date": params.start_date,
            "end_date": params.end_date,
        }

    data: Dict[str, Any] = {
        "name": params.name,
        "start_date": params.start_date,
        "end_date": params.end_date,
        "state": SPRINT_STATE_PLANNING,
    }
    if params.release_id:
        data["release"] = params.release_id
    if params.goal:
        data["goal"] = params.goal
    if params.capacity is not None:
        data["capacity"] = params.capacity

    url = f"{config.instance_url}/api/now/table/rm_sprint_2"
    headers = {**auth_manager.get_headers(), "Content-Type": "application/json"}

    try:
        response = requests.post(url, json=data, headers=headers, timeout=config.timeout)
        response.raise_for_status()
        result = response.json().get("result", {})
        return {
            "success": True,
            "message": f"Sprint '{params.name}' created successfully",
            "sprint_id": result.get("sys_id"),
            "sprint_number": result.get("number"),
            "name": result.get("name"),
            "state": SPRINT_STATE_PLANNING,
            "state_label": _SPRINT_STATE_LABELS[SPRINT_STATE_PLANNING],
            "start_date": params.start_date,
            "end_date": params.end_date,
        }
    except requests.RequestException as e:
        body = getattr(e, "response", None)
        body_text = (body.text[:2000] if body and hasattr(body, "text") else "") or ""
        logger.error("create_sprint | name=%s | error=%s", params.name, e)
        return {
            "success": False,
            "message": f"Failed to create sprint: {e}" + (f" | {body_text}" if body_text else ""),
        }


# ---------------------------------------------------------------------------
# get_sprint
# ---------------------------------------------------------------------------

def get_sprint(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: GetSprintParams,
) -> Dict[str, Any]:
    """
    Retrieve a single sprint by sys_id, sprint number, or sprint name.

    Attempts a direct sys_id lookup first. If the server returns 404 or no
    result, falls back to querying by number then by name.
    """
    sprint_id = params.sprint_id.strip()
    headers = auth_manager.get_headers()
    base_url = f"{config.instance_url}/api/now/table/rm_sprint_2"

    # Attempt 1: direct sys_id lookup
    try:
        response = requests.get(
            f"{base_url}/{sprint_id}",
            headers=headers,
            params={"sysparm_display_value": "true"},
            timeout=config.timeout,
        )
        if response.status_code == 200:
            result = response.json().get("result", {})
            if result:
                return {"success": True, "sprint": result}
    except requests.RequestException:
        pass  # fall through to query-based lookup

    # Attempt 2: query by number or name
    try:
        response = requests.get(
            base_url,
            headers=headers,
            params={
                "sysparm_query": f"number={sprint_id}^ORname={sprint_id}",
                "sysparm_limit": 1,
                "sysparm_display_value": "true",
            },
            timeout=config.timeout,
        )
        response.raise_for_status()
        records: List[Dict] = response.json().get("result", [])
        if not records:
            return {
                "success": False,
                "error_code": "SPRINT_NOT_FOUND",
                "message": f"No sprint found with id, number, or name '{sprint_id}'",
                "sprint_id": sprint_id,
            }
        return {"success": True, "sprint": records[0]}
    except requests.RequestException as e:
        body = getattr(e, "response", None)
        body_text = (body.text[:2000] if body and hasattr(body, "text") else "") or ""
        logger.error("get_sprint | sprint_id=%s | error=%s", sprint_id, e)
        return {
            "success": False,
            "message": f"Failed to fetch sprint: {e}" + (f" | {body_text}" if body_text else ""),
        }


# ---------------------------------------------------------------------------
# get_sprint_summary
# ---------------------------------------------------------------------------

def get_sprint_summary(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: GetSprintSummaryParams,
) -> Dict[str, Any]:
    """
    Return a sprint summary: story counts by state group and story point totals.

    Story groupings:
      done        — Complete (state 3)
      in_progress — Work in Progress / Ready for Testing / Testing (states 2, -7, -8)
      backlog     — Draft / Ready (states -6, 1)
      cancelled   — Cancelled (state 4)

    Optionally includes the full story list when include_stories=True.
    """
    # Resolve the sprint to get its sys_id
    sprint_result = get_sprint(
        config,
        auth_manager,
        GetSprintParams(sprint_id=params.sprint_id),
    )
    if not sprint_result["success"]:
        return sprint_result

    sprint = sprint_result["sprint"]
    # sys_id may be a plain string or a display-value dict
    raw_sys_id = sprint.get("sys_id", {})
    sprint_sys_id = (
        raw_sys_id.get("value", raw_sys_id)
        if isinstance(raw_sys_id, dict)
        else str(raw_sys_id)
    )

    # Fetch all stories in this sprint using raw state values for grouping
    url = f"{config.instance_url}/api/now/table/rm_story"
    headers = auth_manager.get_headers()

    try:
        response = requests.get(
            url,
            headers=headers,
            params={
                "sysparm_query": f"sprint={sprint_sys_id}",
                "sysparm_fields": "sys_id,number,short_description,state,story_points,assigned_to",
                "sysparm_limit": 500,
                "sysparm_display_value": "false",
            },
            timeout=config.timeout,
        )
        response.raise_for_status()
        stories: List[Dict] = response.json().get("result", [])
    except requests.RequestException as e:
        body = getattr(e, "response", None)
        body_text = (body.text[:2000] if body and hasattr(body, "text") else "") or ""
        logger.error("get_sprint_summary | sprint_sys_id=%s | error=%s", sprint_sys_id, e)
        return {
            "success": False,
            "message": f"Failed to fetch stories for sprint: {e}" + (f" | {body_text}" if body_text else ""),
        }

    # Aggregate counts and points
    counts: Dict[str, int] = {
        "total": 0,
        "done": 0,
        "in_progress": 0,
        "backlog": 0,
        "cancelled": 0,
    }
    points: Dict[str, int] = {"total": 0, "completed": 0, "remaining": 0}

    for story in stories:
        counts["total"] += 1
        state = str(story.get("state", ""))
        pts = int(story.get("story_points") or 0)
        points["total"] += pts

        if state in _STORY_DONE_STATES:
            counts["done"] += 1
            points["completed"] += pts
        elif state in _STORY_IN_PROGRESS_STATES:
            counts["in_progress"] += 1
            points["remaining"] += pts
        elif state in _STORY_BACKLOG_STATES:
            counts["backlog"] += 1
            points["remaining"] += pts
        elif state in _STORY_CANCELLED_STATES:
            counts["cancelled"] += 1
            # cancelled stories don't count toward remaining

    # Derive a simple forecast signal
    total = counts["total"]
    done = counts["done"]
    if total == 0:
        forecast = "no_stories"
    elif done == total:
        forecast = "complete"
    elif counts["backlog"] == 0 and counts["in_progress"] > 0:
        forecast = "on_track"
    elif counts["backlog"] > 0:
        forecast = "at_risk"
    else:
        forecast = "on_track"

    result: Dict[str, Any] = {
        "success": True,
        "sprint": {
            "sys_id": sprint_sys_id,
            "name": sprint.get("name"),
            "state": sprint.get("state"),
            "start_date": sprint.get("start_date"),
            "end_date": sprint.get("end_date"),
            "goal": sprint.get("goal"),
        },
        "story_counts": counts,
        "points": points,
        "completion_forecast": forecast,
    }
    if params.include_stories:
        result["stories"] = stories

    return result


# ---------------------------------------------------------------------------
# start_sprint
# ---------------------------------------------------------------------------


def start_sprint(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: StartSprintParams,
) -> Dict[str, Any]:
    """
    Transition a sprint from Planning → Active.

    Validates the sprint is in Planning state before patching.
    Returns an open story count as an informational warning.
    """
    # Resolve sprint
    sprint_result = get_sprint(config, auth_manager, GetSprintParams(sprint_id=params.sprint_id))
    if not sprint_result["success"]:
        return sprint_result

    sprint = sprint_result["sprint"]
    raw_sys_id = sprint.get("sys_id", {})
    sprint_sys_id = raw_sys_id.get("value", raw_sys_id) if isinstance(raw_sys_id, dict) else str(raw_sys_id)

    # Validate state
    raw_state = sprint.get("state", {})
    current_state = raw_state.get("value", raw_state) if isinstance(raw_state, dict) else str(raw_state)
    if current_state != SPRINT_STATE_PLANNING:
        return {
            "success": False,
            "error_code": "INVALID_TRANSITION",
            "message": (
                f"Cannot start sprint: expected state Planning ({SPRINT_STATE_PLANNING}), "
                f"got {current_state} ({_SPRINT_STATE_LABELS.get(current_state, 'Unknown')})."
            ),
            "sprint_id": sprint_sys_id,
            "current_state": current_state,
        }

    # Count open stories before transitioning
    story_url = f"{config.instance_url}/api/now/table/rm_story"
    open_story_count = 0
    try:
        resp = requests.get(
            story_url,
            headers=auth_manager.get_headers(),
            params={
                "sysparm_query": (
                    f"sprint={sprint_sys_id}"
                    f"^state!={SPRINT_STATE_COMPLETED}"
                    f"^state!={SPRINT_STATE_CANCELLED}"
                ),
                "sysparm_fields": "sys_id",
                "sysparm_limit": 500,
            },
            timeout=config.timeout,
        )
        resp.raise_for_status()
        open_story_count = len(resp.json().get("result", []))
    except requests.RequestException:
        pass  # non-fatal; proceed with the transition

    # Patch sprint to Active
    url = f"{config.instance_url}/api/now/table/rm_sprint_2/{sprint_sys_id}"
    headers = {**auth_manager.get_headers(), "Content-Type": "application/json"}
    try:
        response = requests.patch(url, json={"state": SPRINT_STATE_ACTIVE}, headers=headers, timeout=config.timeout)
        response.raise_for_status()
    except requests.RequestException as e:
        body = getattr(e, "response", None)
        body_text = (body.text[:2000] if body and hasattr(body, "text") else "") or ""
        logger.error("start_sprint | sprint_sys_id=%s | error=%s", sprint_sys_id, e)
        return {
            "success": False,
            "message": f"Failed to start sprint: {e}" + (f" | {body_text}" if body_text else ""),
        }

    return {
        "success": True,
        "sprint_id": sprint_sys_id,
        "previous_state": SPRINT_STATE_PLANNING,
        "previous_state_label": _SPRINT_STATE_LABELS[SPRINT_STATE_PLANNING],
        "new_state": SPRINT_STATE_ACTIVE,
        "new_state_label": _SPRINT_STATE_LABELS[SPRINT_STATE_ACTIVE],
        "open_story_count": open_story_count,
        "message": (
            f"Sprint started successfully. {open_story_count} open story/stories in sprint."
        ),
    }


# ---------------------------------------------------------------------------
# close_sprint
# ---------------------------------------------------------------------------


def close_sprint(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: CloseSprintParams,
) -> Dict[str, Any]:
    """
    Transition a sprint from Active → Completed.

    If open stories exist and force=False, returns OPEN_STORIES_BLOCKING_CLOSE.
    Set force=True to close regardless of open stories.
    """
    # Resolve sprint
    sprint_result = get_sprint(config, auth_manager, GetSprintParams(sprint_id=params.sprint_id))
    if not sprint_result["success"]:
        return sprint_result

    sprint = sprint_result["sprint"]
    raw_sys_id = sprint.get("sys_id", {})
    sprint_sys_id = raw_sys_id.get("value", raw_sys_id) if isinstance(raw_sys_id, dict) else str(raw_sys_id)

    # Validate state
    raw_state = sprint.get("state", {})
    current_state = raw_state.get("value", raw_state) if isinstance(raw_state, dict) else str(raw_state)
    if current_state != SPRINT_STATE_ACTIVE:
        return {
            "success": False,
            "error_code": "INVALID_TRANSITION",
            "message": (
                f"Cannot close sprint: expected state Active ({SPRINT_STATE_ACTIVE}), "
                f"got {current_state} ({_SPRINT_STATE_LABELS.get(current_state, 'Unknown')})."
            ),
            "sprint_id": sprint_sys_id,
            "current_state": current_state,
        }

    # Count open stories (not done=3, not cancelled=4)
    story_url = f"{config.instance_url}/api/now/table/rm_story"
    open_story_count = 0
    try:
        resp = requests.get(
            story_url,
            headers=auth_manager.get_headers(),
            params={
                "sysparm_query": f"sprint={sprint_sys_id}^state!=3^state!=4",
                "sysparm_fields": "sys_id",
                "sysparm_limit": 500,
            },
            timeout=config.timeout,
        )
        resp.raise_for_status()
        open_story_count = len(resp.json().get("result", []))
    except requests.RequestException:
        pass  # non-fatal; proceed

    if open_story_count > 0 and not params.force:
        return {
            "success": False,
            "error_code": "OPEN_STORIES_BLOCKING_CLOSE",
            "message": (
                f"{open_story_count} open story/stories remain in this sprint. "
                "Resolve them or use force=True to close anyway."
            ),
            "sprint_id": sprint_sys_id,
            "open_stories_count": open_story_count,
        }

    # Patch sprint to Completed
    url = f"{config.instance_url}/api/now/table/rm_sprint_2/{sprint_sys_id}"
    headers = {**auth_manager.get_headers(), "Content-Type": "application/json"}
    try:
        response = requests.patch(url, json={"state": SPRINT_STATE_COMPLETED}, headers=headers, timeout=config.timeout)
        response.raise_for_status()
    except requests.RequestException as e:
        body = getattr(e, "response", None)
        body_text = (body.text[:2000] if body and hasattr(body, "text") else "") or ""
        logger.error("close_sprint | sprint_sys_id=%s | error=%s", sprint_sys_id, e)
        return {
            "success": False,
            "message": f"Failed to close sprint: {e}" + (f" | {body_text}" if body_text else ""),
        }

    return {
        "success": True,
        "sprint_id": sprint_sys_id,
        "previous_state": SPRINT_STATE_ACTIVE,
        "previous_state_label": _SPRINT_STATE_LABELS[SPRINT_STATE_ACTIVE],
        "new_state": SPRINT_STATE_COMPLETED,
        "new_state_label": _SPRINT_STATE_LABELS[SPRINT_STATE_COMPLETED],
        "open_stories_carried_over": open_story_count,
        "message": (
            f"Sprint closed. {open_story_count} story/stories were still open at close time."
        ),
    }
