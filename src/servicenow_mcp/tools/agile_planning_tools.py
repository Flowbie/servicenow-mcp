"""
Agile planning tools for the ServiceNow MCP server.

Read-only tools that gather ServiceNow context to help Claude agents reason about
story breakdown, acceptance criteria, estimation, risk, and test scenario generation.
"""

import logging
from typing import Any, Dict, List, Optional

import requests

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.agile_constants import StoryIdParams
from servicenow_mcp.tools.agile_governance_tools import validate_story_dependencies
from servicenow_mcp.utils.config import ServerConfig

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Story/task state constants (local to this module)
# ---------------------------------------------------------------------------

# Scrum task type values (rm_scrum_task.type)
_SCRUM_TASK_TYPE_TESTING = "4"

_TASK_TYPE_GUIDE: Dict[str, str] = {
    "1": "development — implementation work, coding, unit tests",
    "2": "documentation — technical docs, runbooks, comments",
    "3": "design — UX wireframes, architecture diagrams, spikes",
    "4": "testing — manual and automated test execution",
    "5": "devops — CI/CD, infrastructure, deployment scripts",
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_story(
    config: ServerConfig,
    auth_manager: AuthManager,
    story_id: str,
) -> Optional[Dict[str, Any]]:
    """Return a single story record (display values) or None on error/not-found."""
    url = f"{config.instance_url}/api/now/table/rm_story/{story_id}"
    try:
        response = requests.get(
            url,
            headers=auth_manager.get_headers(),
            params={"sysparm_display_value": "true"},
            timeout=config.timeout,
        )
        if response.status_code == 200:
            return response.json().get("result") or None
    except requests.RequestException:
        pass
    return None


def _get_epic(
    config: ServerConfig,
    auth_manager: AuthManager,
    epic_ref: Any,
) -> Optional[Dict[str, Any]]:
    """Fetch an epic given a display-value dict or sys_id string. Returns None if missing."""
    if not epic_ref:
        return None
    epic_sys_id = (
        epic_ref.get("value") if isinstance(epic_ref, dict) else str(epic_ref)
    )
    if not epic_sys_id:
        return None
    url = f"{config.instance_url}/api/now/table/rm_epic/{epic_sys_id}"
    try:
        response = requests.get(
            url,
            headers=auth_manager.get_headers(),
            params={"sysparm_display_value": "true"},
            timeout=config.timeout,
        )
        if response.status_code == 200:
            return response.json().get("result") or None
    except requests.RequestException:
        pass
    return None


def _list_scrum_tasks(
    config: ServerConfig,
    auth_manager: AuthManager,
    story_sys_id: str,
    task_type: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Return scrum tasks for a story. Optionally filter by type."""
    url = f"{config.instance_url}/api/now/table/rm_scrum_task"
    query = f"story={story_sys_id}"
    if task_type:
        query += f"^type={task_type}"
    try:
        response = requests.get(
            url,
            headers=auth_manager.get_headers(),
            params={
                "sysparm_query": query,
                "sysparm_fields": "sys_id,number,short_description,state,type,story_points",
                "sysparm_display_value": "true",
                "sysparm_limit": 100,
            },
            timeout=config.timeout,
        )
        response.raise_for_status()
        return response.json().get("result", [])
    except requests.RequestException:
        return []


def _list_similar_stories(
    config: ServerConfig,
    auth_manager: AuthManager,
    epic_sys_id: str,
    exclude_story_id: str,
    limit: int = 5,
    extra_query: str = "",
) -> List[Dict[str, Any]]:
    """Return stories from the same epic (excluding the target story)."""
    url = f"{config.instance_url}/api/now/table/rm_story"
    query = f"epic={epic_sys_id}^sys_id!={exclude_story_id}"
    if extra_query:
        query += f"^{extra_query}"
    try:
        response = requests.get(
            url,
            headers=auth_manager.get_headers(),
            params={
                "sysparm_query": query,
                "sysparm_fields": (
                    "sys_id,number,short_description,state,story_points,"
                    "acceptance_criteria,description"
                ),
                "sysparm_display_value": "true",
                "sysparm_limit": limit,
            },
            timeout=config.timeout,
        )
        response.raise_for_status()
        return response.json().get("result", [])
    except requests.RequestException:
        return []


def _resolve_story_sys_id(story: Dict[str, Any]) -> str:
    """Extract plain sys_id string from a story record (handles display-value dict)."""
    raw = story.get("sys_id", {})
    return raw.get("value", raw) if isinstance(raw, dict) else str(raw)


def _resolve_epic_sys_id(epic_ref: Any) -> str:
    """Extract plain sys_id string from an epic reference field."""
    if isinstance(epic_ref, dict):
        return epic_ref.get("value", "")
    return str(epic_ref or "")


# ---------------------------------------------------------------------------
# story_breakdown
# ---------------------------------------------------------------------------


def story_breakdown(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: StoryIdParams,
) -> Dict[str, Any]:
    """
    Gather all context needed to break a story into tasks.

    Returns the story, its epic, existing tasks, similar stories from the same
    epic, a task type guide, and AI-oriented analysis hints.
    """
    story = _get_story(config, auth_manager, params.story_id)
    if not story:
        return {
            "success": False,
            "error_code": "STORY_NOT_FOUND",
            "message": f"No story found with sys_id '{params.story_id}'",
        }

    story_sys_id = _resolve_story_sys_id(story)
    epic = _get_epic(config, auth_manager, story.get("epic"))
    existing_tasks = _list_scrum_tasks(config, auth_manager, story_sys_id)

    similar_stories: List[Dict] = []
    if epic:
        epic_sys_id = _resolve_story_sys_id(epic)
        similar_stories = _list_similar_stories(
            config, auth_manager, epic_sys_id, story_sys_id, limit=5
        )

    analysis_hints = [
        "Review the story description and acceptance criteria before generating tasks.",
        "Match the granularity of similar stories' task lists if available.",
        "Ensure at least one testing task is included.",
        "Consider DevOps tasks if deployment steps are implied by the story.",
        "Each task should be independently deliverable within the sprint.",
    ]

    return {
        "success": True,
        "story": story,
        "epic": epic,
        "existing_tasks": existing_tasks,
        "similar_stories": similar_stories,
        "task_type_guide": _TASK_TYPE_GUIDE,
        "analysis_hints": analysis_hints,
    }


# ---------------------------------------------------------------------------
# generate_acceptance_criteria
# ---------------------------------------------------------------------------


def generate_acceptance_criteria(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: StoryIdParams,
) -> Dict[str, Any]:
    """
    Gather context for writing acceptance criteria for a story.

    Returns the story, its epic, current AC (if any), and AC from similar
    stories in the same epic as calibration examples.
    """
    story = _get_story(config, auth_manager, params.story_id)
    if not story:
        return {
            "success": False,
            "error_code": "STORY_NOT_FOUND",
            "message": f"No story found with sys_id '{params.story_id}'",
        }

    story_sys_id = _resolve_story_sys_id(story)
    epic = _get_epic(config, auth_manager, story.get("epic"))

    similar_stories_ac: List[Dict] = []
    if epic:
        epic_sys_id = _resolve_story_sys_id(epic)
        similar = _list_similar_stories(
            config, auth_manager, epic_sys_id, story_sys_id, limit=5
        )
        # Keep only fields useful for AC calibration
        similar_stories_ac = [
            {
                "number": s.get("number"),
                "short_description": s.get("short_description"),
                "acceptance_criteria": s.get("acceptance_criteria"),
            }
            for s in similar
            if s.get("acceptance_criteria")
        ]

    return {
        "success": True,
        "story": story,
        "epic": epic,
        "existing_acceptance_criteria": story.get("acceptance_criteria"),
        "similar_stories_ac": similar_stories_ac,
        "ac_format_hint": (
            "Use Given/When/Then (Gherkin) format for behaviour-driven criteria, "
            "or bullet points for simpler functional requirements. "
            "Each criterion should be independently testable."
        ),
    }


# ---------------------------------------------------------------------------
# estimate_story_points
# ---------------------------------------------------------------------------


def estimate_story_points(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: StoryIdParams,
) -> Dict[str, Any]:
    """
    Gather context for story point estimation.

    Returns the story, its epic, similar completed stories with their points
    as calibration anchors, existing task count, the Fibonacci scale, and
    calibration hints.
    """
    story = _get_story(config, auth_manager, params.story_id)
    if not story:
        return {
            "success": False,
            "error_code": "STORY_NOT_FOUND",
            "message": f"No story found with sys_id '{params.story_id}'",
        }

    story_sys_id = _resolve_story_sys_id(story)
    epic = _get_epic(config, auth_manager, story.get("epic"))
    existing_task_count = len(_list_scrum_tasks(config, auth_manager, story_sys_id))

    similar_with_points: List[Dict] = []
    if epic:
        epic_sys_id = _resolve_story_sys_id(epic)
        # Only fetch done stories that have points set
        similar = _list_similar_stories(
            config,
            auth_manager,
            epic_sys_id,
            story_sys_id,
            limit=10,
            extra_query="state=3^story_points>0",
        )
        similar_with_points = [
            {
                "number": s.get("number"),
                "short_description": s.get("short_description"),
                "story_points": s.get("story_points"),
                "description": s.get("description"),
            }
            for s in similar
        ]

    calibration_hints = [
        "1-2 pts: trivial change, no risk, well-understood implementation.",
        "3-5 pts: moderate work, some unknowns, 1-3 days effort.",
        "8-13 pts: complex, multiple areas, potential unknowns.",
        "21+ pts: too large — consider splitting.",
        f"This story currently has {existing_task_count} scrum task(s) already created.",
    ]

    return {
        "success": True,
        "story": story,
        "epic": epic,
        "similar_stories_with_points": similar_with_points,
        "existing_task_count": existing_task_count,
        "fibonacci_scale": [1, 2, 3, 5, 8, 13, 21, 34, 55, 89],
        "calibration_hints": calibration_hints,
    }


# ---------------------------------------------------------------------------
# identify_story_risks
# ---------------------------------------------------------------------------


def identify_story_risks(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: StoryIdParams,
) -> Dict[str, Any]:
    """
    Surface open blockers and risk signals for a story.

    Delegates the prerequisite dependency check to validate_story_dependencies
    and augments the result with planning-specific risk hints.
    """
    story = _get_story(config, auth_manager, params.story_id)
    if not story:
        return {
            "success": False,
            "error_code": "STORY_NOT_FOUND",
            "message": f"No story found with sys_id '{params.story_id}'",
        }

    story_sys_id = _resolve_story_sys_id(story)
    existing_task_count = len(_list_scrum_tasks(config, auth_manager, story_sys_id))

    # Delegate blocker resolution to the governance tool
    dep_result = validate_story_dependencies(config, auth_manager, params)
    if not dep_result.get("success"):
        open_blockers: List[Dict] = []
        logger.warning(
            "identify_story_risks | story=%s | dependency check failed: %s",
            story_sys_id,
            dep_result.get("message"),
        )
    else:
        # Remap governance open_blocker shape to planning output contract:
        # governance: {number, title, state}
        # planning:   {dependency_id, prerequisite_story_number, prerequisite_story_title, prerequisite_state}
        open_blockers = [
            {
                "dependency_id": None,
                "prerequisite_story_number": b.get("number"),
                "prerequisite_story_title": b.get("title"),
                "prerequisite_state": b.get("state"),
            }
            for b in dep_result.get("open_blockers", [])
        ]

    risk_analysis_hints = [
        "Blocked stories cannot safely start until all prerequisites are resolved.",
        "Stories with 0 tasks and no acceptance criteria are at risk of scope creep.",
        "Check sprint capacity if the story has a high point estimate.",
        "Identify integration dependencies with external teams early.",
    ]

    return {
        "success": True,
        "story": story,
        "open_blocker_count": len(open_blockers),
        "open_blockers": open_blockers,
        "existing_task_count": existing_task_count,
        "risk_analysis_hints": risk_analysis_hints,
    }


# ---------------------------------------------------------------------------
# generate_test_scenarios
# ---------------------------------------------------------------------------


def generate_test_scenarios(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: StoryIdParams,
) -> Dict[str, Any]:
    """
    Gather context for generating test scenarios for a story.

    Returns the story, its epic, any existing testing tasks, and structured
    hints for happy path, edge cases, error paths, and integration points.
    """
    story = _get_story(config, auth_manager, params.story_id)
    if not story:
        return {
            "success": False,
            "error_code": "STORY_NOT_FOUND",
            "message": f"No story found with sys_id '{params.story_id}'",
        }

    story_sys_id = _resolve_story_sys_id(story)
    epic = _get_epic(config, auth_manager, story.get("epic"))
    existing_testing_tasks = _list_scrum_tasks(
        config, auth_manager, story_sys_id, task_type=_SCRUM_TASK_TYPE_TESTING
    )

    test_scenario_hints = {
        "happy_path": "Test the primary success flow described in acceptance criteria.",
        "edge_cases": (
            "Test boundary values, empty inputs, maximum lengths, "
            "and unusual but valid combinations."
        ),
        "error_paths": (
            "Test invalid inputs, permission denials, missing required fields, "
            "and downstream failures."
        ),
        "integration_points": (
            "Test interactions with related records, Business Rules, "
            "notifications, and upstream/downstream systems."
        ),
    }

    return {
        "success": True,
        "story": story,
        "epic": epic,
        "existing_testing_tasks": existing_testing_tasks,
        "test_scenario_hints": test_scenario_hints,
    }
