"""
Agile sprint planning tools for the ServiceNow MCP server.

Provides intelligent sprint story recommendation based on priority, dependency
readiness, story points versus sprint capacity, and optional objective alignment.
"""

import logging
from typing import Any, Dict, List, Optional, Set

import requests
from pydantic import BaseModel, Field

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.utils.config import ServerConfig

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Story states considered terminal — no longer active work
_STORY_TERMINAL_STATES = {"3", "4"}  # 3=Complete, 4=Cancelled

# Priority numeric values → score weights (higher = recommended first)
_PRIORITY_SCORE: Dict[str, int] = {
    "1": 50,  # Critical
    "2": 40,  # High
    "3": 30,  # Moderate
    "4": 20,  # Low
    "5": 10,  # Planning
}

_PRIORITY_LABELS: Dict[str, str] = {
    "1": "Critical",
    "2": "High",
    "3": "Moderate",
    "4": "Low",
    "5": "Planning",
}


# ---------------------------------------------------------------------------
# Params model
# ---------------------------------------------------------------------------


class RecommendSprintStoriesParams(BaseModel):
    """Parameters for recommending backlog stories for a sprint."""

    sprint_id: str = Field(..., description="sys_id of the target sprint.")
    capacity_override: Optional[int] = Field(
        None,
        description=(
            "Override the sprint capacity in story points. If not provided, "
            "uses the sprint's capacity field from rm_sprint_2."
        ),
    )
    objectives: Optional[str] = Field(
        None,
        description=(
            "Free-text sprint objectives or keywords. Stories whose title or "
            "epic description contain these terms receive a small relevance bonus."
        ),
    )
    limit: Optional[int] = Field(
        50,
        description="Maximum number of backlog stories to evaluate (default 50).",
    )


# ---------------------------------------------------------------------------
# recommend_sprint_stories
# ---------------------------------------------------------------------------


def recommend_sprint_stories(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: RecommendSprintStoriesParams,
) -> Dict[str, Any]:
    """
    Recommend backlog stories for a sprint based on priority, capacity, and
    dependency readiness.

    Algorithm:
      1. Fetch sprint details (capacity, state, name).
      2. Fetch backlog stories (sprint IS EMPTY, state not terminal).
      3. Batch-fetch dependency rows for all candidates in a single query.
      4. Score each story: priority + optional keyword bonus.
      5. Sort descending by score; partition into recommended / blocked / over_capacity.

    A story is blocked if any of its prerequisites are not Complete or Cancelled.
    A story is over_capacity if adding its points would exceed available capacity
    (only enforced when capacity > 0).
    """
    headers = auth_manager.get_headers()
    base_url = config.instance_url

    # ---- Step 1: fetch sprint details ----------------------------------------
    sprint_url = f"{base_url}/api/now/table/rm_sprint_2/{params.sprint_id}"
    try:
        resp = requests.get(
            sprint_url,
            headers=headers,
            params={"sysparm_fields": "sys_id,name,state,capacity"},
            timeout=config.timeout,
        )
        resp.raise_for_status()
        sprint = resp.json().get("result", {})
    except requests.RequestException as e:
        return {"success": False, "message": f"Failed to fetch sprint: {e}"}

    capacity = params.capacity_override
    if capacity is None:
        try:
            capacity = int(sprint.get("capacity") or 0)
        except (ValueError, TypeError):
            capacity = 0

    sprint_name = sprint.get("name", params.sprint_id)
    sprint_state = str(sprint.get("state") or "")

    # ---- Step 2: fetch backlog stories ---------------------------------------
    stories_url = f"{base_url}/api/now/table/rm_story"
    try:
        resp = requests.get(
            stories_url,
            headers=headers,
            params={
                # Stories with no sprint assigned and not in a terminal state
                "sysparm_query": "sprintISEMPTY^stateNOT IN3,4",
                "sysparm_fields": (
                    "sys_id,number,short_description,state,story_points,"
                    "priority,epic,epic.short_description,project,project.name,"
                    "assigned_to,assigned_to.name"
                ),
                "sysparm_display_value": "false",
                "sysparm_limit": params.limit,
                "sysparm_offset": 0,
            },
            timeout=config.timeout,
        )
        resp.raise_for_status()
        backlog: List[Dict] = resp.json().get("result", [])
    except requests.RequestException as e:
        return {"success": False, "message": f"Failed to fetch backlog stories: {e}"}

    if not backlog:
        return {
            "success": True,
            "sprint_id": params.sprint_id,
            "sprint_name": sprint_name,
            "sprint_state": sprint_state,
            "capacity": capacity,
            "recommended": [],
            "blocked": [],
            "over_capacity": [],
            "summary": {
                "recommended_count": 0,
                "blocked_count": 0,
                "over_capacity_count": 0,
                "total_evaluated": 0,
            },
            "message": "Backlog is empty — no stories to recommend.",
        }

    # ---- Step 3: batch-fetch dependency data --------------------------------
    # Single query for all prerequisite relationships across all candidate stories.
    story_ids = [s["sys_id"] for s in backlog if s.get("sys_id")]
    blocked_story_ids: Set[str] = set()
    blocker_details: Dict[str, List[Dict]] = {}

    if story_ids:
        try:
            deps_resp = requests.get(
                f"{base_url}/api/now/table/m2m_story_dependencies",
                headers=headers,
                params={
                    "sysparm_query": f"dependent_storyIN{','.join(story_ids)}",
                    "sysparm_fields": (
                        "dependent_story,prerequisite_story,"
                        "prerequisite_story.state,prerequisite_story.number,"
                        "prerequisite_story.short_description"
                    ),
                    "sysparm_display_value": "false",
                    "sysparm_limit": 1000,
                },
                timeout=config.timeout,
            )
            deps_resp.raise_for_status()
            deps: List[Dict] = deps_resp.json().get("result", [])

            for dep in deps:
                dep_story_id = dep.get("dependent_story") or ""
                prereq_state = str(dep.get("prerequisite_story.state") or "")
                if prereq_state not in _STORY_TERMINAL_STATES:
                    blocked_story_ids.add(dep_story_id)
                    if dep_story_id not in blocker_details:
                        blocker_details[dep_story_id] = []
                    blocker_details[dep_story_id].append(
                        {
                            "number": dep.get("prerequisite_story.number"),
                            "title": dep.get("prerequisite_story.short_description"),
                            "state": prereq_state,
                        }
                    )
        except requests.RequestException as e:
            # Non-fatal: proceed without dependency data; log the warning.
            logger.warning(
                "recommend_sprint_stories | dependency fetch failed: %s", e
            )

    # ---- Step 4: score stories -----------------------------------------------
    objective_keywords: List[str] = []
    if params.objectives:
        objective_keywords = [
            kw.lower().strip()
            for kw in params.objectives.split()
            if kw.strip()
        ]

    scored: List[Dict] = []
    for story in backlog:
        sys_id = story.get("sys_id", "")
        priority = str(story.get("priority") or "")
        try:
            points = int(story.get("story_points") or 0)
        except (ValueError, TypeError):
            points = 0

        # Base score from priority; unknown priority gets the mid-range score
        score = _PRIORITY_SCORE.get(priority, 25)

        # Objective keyword bonus — each matched keyword adds 3 points (capped at 10)
        if objective_keywords:
            text = (
                (story.get("short_description") or "")
                + " "
                + (story.get("epic.short_description") or "")
            ).lower()
            matched = sum(1 for kw in objective_keywords if kw in text)
            score += min(matched * 3, 10)

        scored.append(
            {
                "sys_id": sys_id,
                "number": story.get("number"),
                "title": story.get("short_description"),
                "state": story.get("state"),
                "story_points": points,
                "priority": priority,
                "priority_label": _PRIORITY_LABELS.get(priority, "Unknown"),
                "epic": story.get("epic.short_description") or story.get("epic") or "",
                "project": story.get("project.name") or story.get("project") or "",
                "assigned_to": story.get("assigned_to.name") or story.get("assigned_to") or "",
                "dependencies_clear": sys_id not in blocked_story_ids,
                "open_blockers": blocker_details.get(sys_id, []),
                "score": score,
            }
        )

    # Sort: highest score first; use points ascending as tiebreaker (smaller stories first)
    scored.sort(key=lambda s: (-s["score"], s["story_points"]))

    # ---- Step 5: partition into recommended / blocked / over_capacity --------
    recommended: List[Dict] = []
    blocked: List[Dict] = []
    over_capacity: List[Dict] = []

    points_used = 0
    for story in scored:
        if not story["dependencies_clear"]:
            blocked.append(story)
        elif capacity > 0 and points_used + story["story_points"] > capacity:
            over_capacity.append(story)
        else:
            recommended.append(story)
            points_used += story["story_points"]

    remaining = max(0, capacity - points_used) if capacity > 0 else None

    return {
        "success": True,
        "sprint_id": params.sprint_id,
        "sprint_name": sprint_name,
        "sprint_state": sprint_state,
        "capacity": capacity,
        "points_allocated": points_used,
        "remaining_capacity": remaining,
        "recommended": recommended,
        "blocked": blocked,
        "over_capacity": over_capacity,
        "summary": {
            "recommended_count": len(recommended),
            "blocked_count": len(blocked),
            "over_capacity_count": len(over_capacity),
            "total_evaluated": len(scored),
        },
    }
