"""
Story management tools for the ServiceNow MCP server.

Compound functions only. CRUD operations (create, update, list, get story;
create/delete dependencies; assign; add comment; list blockers) have been
removed as public tools — use the generic table_tools with the agile
architecture blueprint instead.

Internal helpers (get_story, update_story) are kept because they are called
by the compound functions below.
"""

import logging
from typing import Any, Dict, List, Optional

import requests
from pydantic import BaseModel, Field

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.utils.config import ServerConfig

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Param models needed by internal helpers and compound functions
# ---------------------------------------------------------------------------


class UpdateStoryParams(BaseModel):
    """Parameters for updating a story (internal helper use)."""

    story_id: str = Field(..., description="Story IDNumber or sys_id. You will need to fetch the story to get the sys_id if you only have the story number")
    short_description: Optional[str] = Field(None, description="Short description of the story")
    acceptance_criteria: Optional[str] = Field(None, description="Acceptance criteria for the story")
    description: Optional[str] = Field(None, description="Detailed description of the story")
    state: Optional[str] = Field(None, description="State of story (-6 is Draft,-7 is Ready for Testing,-8 is Testing,1 is Ready, 2 is Work in progress, 3 is Complete, 4 is Cancelled)")
    assignment_group: Optional[str] = Field(None, description="Group assigned to the story")
    story_points: Optional[int] = Field(None, description="Points value for the story")
    assigned_to: Optional[str] = Field(None, description="User assigned to the story")
    epic: Optional[str] = Field(None, description="Epic that the story belongs to. It requires the System ID of the epic.")
    project: Optional[str] = Field(None, description="Project that the story belongs to. It requires the System ID of the project.")
    work_notes: Optional[str] = Field(None, description="Work notes to add to the story. Used for adding notes and comments to a story")
    priority: Optional[str] = Field(None, description="Priority (1=Critical, 2=High, 3=Moderate, 4=Low, 5=Planning)")
    sprint: Optional[str] = Field(None, description="Sprint sys_id to assign this story to. Set to empty string '' to remove from sprint (move to backlog).")


class GetStoryParams(BaseModel):
    """Parameters for getting a single story."""

    story_id: str = Field(..., description="Story sys_id or number (e.g. STRY0001234)")


class ArchiveStoryParams(BaseModel):
    """Parameters for archiving (cancelling) a story."""

    story_id: str = Field(..., description="Story sys_id or number")
    reason: Optional[str] = Field(None, description="Reason for archiving the story")


class MoveStoryStateParams(BaseModel):
    """Parameters for moving a story to a new lifecycle state."""

    story_id: str = Field(..., description="Story sys_id or number")
    target_state: str = Field(
        ...,
        description=(
            "Target state. Accepts name or numeric value. "
            "Names: draft, ready/backlog, in_progress, ready_for_testing, testing, complete/done, cancelled. "
            "Numeric values: -6 (Draft), 1 (Ready), 2 (In Progress), -7 (Ready for Testing), "
            "-8 (Testing), 3 (Complete), 4 (Cancelled)."
        ),
    )
    reason: Optional[str] = Field(
        None, description="Required when moving to 'cancelled'. Optional for other transitions."
    )


# ---------------------------------------------------------------------------
# State machine
# ---------------------------------------------------------------------------

# Maps friendly state names to ServiceNow numeric state values
_STORY_STATE_NAME_MAP: Dict[str, str] = {
    "draft": "-6",
    "ready": "1",
    "backlog": "1",
    "in_progress": "2",
    "work_in_progress": "2",
    "ready_for_testing": "-7",
    "testing": "-8",
    "complete": "3",
    "done": "3",
    "cancelled": "4",
    "canceled": "4",
}

# Allowed target states for each source state (using numeric string keys)
_STORY_STATE_TRANSITIONS: Dict[str, List[str]] = {
    "-6": ["1", "4"],       # Draft → Ready, Cancelled
    "1":  ["-6", "2", "4"], # Ready → Draft, In Progress, Cancelled
    "2":  ["-7", "4"],      # In Progress → Ready for Testing, Cancelled
    "-7": ["-8", "2"],      # Ready for Testing → Testing, back to In Progress
    "-8": ["3", "2"],       # Testing → Complete, back to In Progress
    "3":  [],               # Complete (terminal)
    "4":  [],               # Cancelled (terminal)
}

# Human-readable labels for error messages
_STORY_STATE_LABELS: Dict[str, str] = {
    "-6": "Draft",
    "1":  "Ready",
    "2":  "In Progress",
    "-7": "Ready for Testing",
    "-8": "Testing",
    "3":  "Complete",
    "4":  "Cancelled",
}


def _resolve_state(raw: str) -> Optional[str]:
    """Convert a friendly state name or numeric string to the canonical numeric string."""
    stripped = raw.strip()
    if stripped in _STORY_STATE_TRANSITIONS:
        return stripped
    return _STORY_STATE_NAME_MAP.get(stripped.lower())


# ---------------------------------------------------------------------------
# Internal helpers (not registered as MCP tools; used by compound functions)
# ---------------------------------------------------------------------------


def update_story(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: UpdateStoryParams,
) -> Dict[str, Any]:
    """
    Update an existing story in ServiceNow.

    Internal helper used by assign_stories_to_sprint.
    """
    data: Dict[str, Any] = {}

    if params.short_description:
        data["short_description"] = params.short_description
    if params.acceptance_criteria:
        data["acceptance_criteria"] = params.acceptance_criteria
    if params.description:
        data["description"] = params.description
    if params.state:
        data["state"] = params.state
    if params.assignment_group:
        data["assignment_group"] = params.assignment_group
    if params.story_points:
        data["story_points"] = params.story_points
    if params.epic:
        data["epic"] = params.epic
    if params.project:
        data["project"] = params.project
    if params.assigned_to:
        data["assigned_to"] = params.assigned_to
    if params.work_notes:
        data["work_notes"] = params.work_notes
    if params.priority:
        data["priority"] = params.priority
    # Allow sprint to be set to empty string to remove story from sprint (move to backlog)
    if params.sprint is not None:
        data["sprint"] = params.sprint

    url = f"{config.instance_url}/api/now/table/rm_story/{params.story_id}"
    headers = {**auth_manager.get_headers(), "Content-Type": "application/json"}

    try:
        response = requests.put(url, json=data, headers=headers, timeout=config.timeout)
        response.raise_for_status()

        result = response.json()

        return {
            "success": True,
            "message": "Story updated successfully",
            "story": result["result"],
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Error updating story: {e}")
        return {
            "success": False,
            "message": f"Error updating story: {str(e)}",
        }


def get_story(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: GetStoryParams,
) -> Dict[str, Any]:
    """
    Retrieve a single story by sys_id or story number.

    Internal helper used by archive_story and move_story_state.
    Accepts either a sys_id (32-char hex) or a number like STRY0001234.
    Returns the full story record.
    """
    story_id = params.story_id.strip()
    headers = auth_manager.get_headers()

    # Try direct lookup by sys_id first; fall back to number query
    url = f"{config.instance_url}/api/now/table/rm_story/{story_id}"
    try:
        response = requests.get(
            url,
            headers=headers,
            params={"sysparm_display_value": "true"},
            timeout=config.timeout,
        )
        if response.status_code == 404:
            # Retry by number field
            url = f"{config.instance_url}/api/now/table/rm_story"
            response = requests.get(
                url,
                headers=headers,
                params={
                    "sysparm_query": f"number={story_id}",
                    "sysparm_limit": 1,
                    "sysparm_display_value": "true",
                },
                timeout=config.timeout,
            )
            response.raise_for_status()
            records = response.json().get("result", [])
            if not records:
                return {
                    "success": False,
                    "error_code": "STORY_NOT_FOUND",
                    "message": f"No story found with id or number '{story_id}'",
                    "story_id": story_id,
                }
            story = records[0]
        else:
            response.raise_for_status()
            story = response.json().get("result", {})

        return {
            "success": True,
            "story": story,
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Error getting story {story_id}: {e}")
        body = getattr(e, "response", None)
        body_text = (body.text[:2000] if body and hasattr(body, "text") else "") or ""
        return {
            "success": False,
            "message": f"Error getting story: {str(e)}" + (f" | {body_text}" if body_text else ""),
        }


# ---------------------------------------------------------------------------
# Compound functions (registered as MCP tools)
# ---------------------------------------------------------------------------


def archive_story(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: ArchiveStoryParams,
) -> Dict[str, Any]:
    """
    Archive (cancel) a story by setting its state to Cancelled (4).

    Optionally records a reason in work_notes. Cannot archive a story that is
    already Complete or Cancelled.
    """
    story_id = params.story_id.strip()
    headers = {**auth_manager.get_headers(), "Content-Type": "application/json"}

    # Fetch current state to guard against archiving terminal records
    get_result = get_story(config, auth_manager, GetStoryParams(story_id=story_id))
    if not get_result["success"]:
        return get_result

    current_story = get_result["story"]
    # Display value may be a dict or a string depending on sysparm_display_value
    raw_state = current_story.get("state", {})
    current_state = raw_state.get("value", raw_state) if isinstance(raw_state, dict) else str(raw_state)

    if current_state in ("3", "4"):
        label = _STORY_STATE_LABELS.get(current_state, current_state)
        return {
            "success": False,
            "error_code": "STORY_ALREADY_TERMINAL",
            "message": f"Story is already in a terminal state: {label}. Cannot archive.",
            "story_id": story_id,
            "current_state": current_state,
        }

    data: Dict[str, Any] = {"state": "4"}
    if params.reason:
        data["work_notes"] = f"Archived: {params.reason}"

    url = f"{config.instance_url}/api/now/table/rm_story/{story_id}"
    try:
        response = requests.patch(url, json=data, headers=headers, timeout=config.timeout)
        response.raise_for_status()
        return {
            "success": True,
            "message": "Story archived (cancelled) successfully",
            "story_id": story_id,
            "previous_state": current_state,
            "new_state": "4",
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Error archiving story {story_id}: {e}")
        body = getattr(e, "response", None)
        body_text = (body.text[:2000] if body and hasattr(body, "text") else "") or ""
        return {
            "success": False,
            "message": f"Error archiving story: {str(e)}" + (f" | {body_text}" if body_text else ""),
        }


def move_story_state(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: MoveStoryStateParams,
) -> Dict[str, Any]:
    """
    Move a story to a new lifecycle state with transition validation.

    Enforces allowed transitions and business rules:
    - Moving to Cancelled requires a reason.
    - Moving to Complete requires acceptance_criteria to be populated.
    Terminal states (Complete, Cancelled) cannot be left.
    """
    story_id = params.story_id.strip()

    # Resolve target state to numeric string
    target_numeric = _resolve_state(params.target_state)
    if target_numeric is None:
        valid_names = ", ".join(sorted(_STORY_STATE_NAME_MAP.keys()))
        return {
            "success": False,
            "error_code": "INVALID_STATE",
            "message": (
                f"Unknown target state '{params.target_state}'. "
                f"Valid names: {valid_names}. "
                f"Valid numeric values: {', '.join(_STORY_STATE_TRANSITIONS.keys())}."
            ),
        }

    # Cancelled requires a reason
    if target_numeric == "4" and not params.reason:
        return {
            "success": False,
            "error_code": "REASON_REQUIRED",
            "message": "A reason is required when moving a story to Cancelled.",
        }

    headers = {**auth_manager.get_headers(), "Content-Type": "application/json"}

    # Fetch current story to get current state and acceptance_criteria
    get_result = get_story(config, auth_manager, GetStoryParams(story_id=story_id))
    if not get_result["success"]:
        return get_result

    current_story = get_result["story"]
    raw_state = current_story.get("state", {})
    current_numeric = raw_state.get("value", raw_state) if isinstance(raw_state, dict) else str(raw_state)

    # Validate transition is allowed
    allowed = _STORY_STATE_TRANSITIONS.get(current_numeric, [])
    if target_numeric not in allowed:
        current_label = _STORY_STATE_LABELS.get(current_numeric, current_numeric)
        target_label = _STORY_STATE_LABELS.get(target_numeric, target_numeric)
        allowed_labels = [
            f"{v} ({_STORY_STATE_LABELS.get(v, v)})" for v in allowed
        ] if allowed else ["none — terminal state"]
        return {
            "success": False,
            "error_code": "INVALID_TRANSITION",
            "message": (
                f"Cannot move story from '{current_label}' to '{target_label}'. "
                f"Allowed transitions: {', '.join(allowed_labels)}."
            ),
            "current_state": current_numeric,
            "target_state": target_numeric,
        }

    # Moving to Complete: acceptance_criteria must be populated
    if target_numeric == "3":
        ac = current_story.get("acceptance_criteria", "")
        if isinstance(ac, dict):
            ac = ac.get("value", ac.get("display_value", ""))
        if not ac or not str(ac).strip():
            return {
                "success": False,
                "error_code": "MISSING_ACCEPTANCE_CRITERIA",
                "message": "Story must have acceptance_criteria populated before moving to Complete.",
                "story_id": story_id,
            }

    data: Dict[str, Any] = {"state": target_numeric}
    if params.reason:
        data["work_notes"] = params.reason

    url = f"{config.instance_url}/api/now/table/rm_story/{story_id}"
    try:
        response = requests.patch(url, json=data, headers=headers, timeout=config.timeout)
        response.raise_for_status()
        current_label = _STORY_STATE_LABELS.get(current_numeric, current_numeric)
        target_label = _STORY_STATE_LABELS.get(target_numeric, target_numeric)
        return {
            "success": True,
            "message": f"Story state moved from '{current_label}' to '{target_label}'",
            "story_id": story_id,
            "previous_state": current_numeric,
            "previous_state_label": current_label,
            "new_state": target_numeric,
            "new_state_label": target_label,
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Error moving story state for {story_id}: {e}")
        body = getattr(e, "response", None)
        body_text = (body.text[:2000] if body and hasattr(body, "text") else "") or ""
        return {
            "success": False,
            "message": f"Error moving story state: {str(e)}" + (f" | {body_text}" if body_text else ""),
        }


# ---------------------------------------------------------------------------
# assign_stories_to_sprint
# ---------------------------------------------------------------------------


class AssignStoriesToSprintParams(BaseModel):
    """Parameters for bulk-assigning stories to a sprint."""

    sprint_id: str = Field(
        ...,
        description="sys_id of the rm_sprint_2 sprint to assign the stories to.",
    )
    story_ids: List[str] = Field(
        ...,
        min_length=1,
        description="List of story sys_ids (rm_story) to assign to the sprint.",
    )


def assign_stories_to_sprint(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: AssignStoriesToSprintParams,
) -> Dict[str, Any]:
    """
    Bulk-assign a list of stories to a sprint.

    Loops update_story for each story_id setting sprint=sprint_id.
    Returns a summary with assigned count, list of failed story_ids, and
    any error messages encountered.
    """
    assigned: int = 0
    failed: List[str] = []
    errors: List[str] = []

    for story_id in params.story_ids:
        result = update_story(
            config,
            auth_manager,
            UpdateStoryParams(story_id=story_id, sprint=params.sprint_id),
        )
        if result.get("success"):
            assigned += 1
        else:
            failed.append(story_id)
            errors.append(result.get("message", f"Unknown error for story {story_id}"))

    return {
        "success": len(failed) == 0,
        "message": (
            f"Assigned {assigned}/{len(params.story_ids)} stories to sprint {params.sprint_id}."
            + (f" Failed: {len(failed)}." if failed else "")
        ),
        "sprint_id": params.sprint_id,
        "assigned": assigned,
        "failed": failed,
        "errors": errors,
    }
