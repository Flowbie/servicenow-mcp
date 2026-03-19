"""
Release management tools for the ServiceNow MCP server.

Provides create, get, readiness validation, and release notes compilation
against the rm_release table, with sprint/story aggregation helpers.
"""

import logging
from typing import Any, Dict, List, Optional

import requests
from pydantic import BaseModel, Field

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.utils.config import ServerConfig
from servicenow_mcp.tools.agile_constants import (
    STORY_DONE_STATES,
    STORY_CANCELLED_STATES,
    STORY_IN_PROGRESS_STATES,
    SPRINT_COMPLETED_STATE,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Params models
# ---------------------------------------------------------------------------


class CreateReleaseParams(BaseModel):
    """Parameters for creating a new release."""

    name: str = Field(..., description="Human-readable release name (e.g. 'v2.4.0')")
    planned_date: Optional[str] = Field(
        None, description="Planned release date in YYYY-MM-DD format."
    )
    description: Optional[str] = Field(
        None, description="Optional description or goal for the release."
    )


class GetReleaseParams(BaseModel):
    """Parameters for retrieving a single release."""

    release_id: str = Field(
        ...,
        description=(
            "Release sys_id, release number (e.g. REL0001234), or release name. "
            "sys_id lookup is tried first; number/name query is used as fallback."
        ),
    )


class ValidateReleaseReadinessParams(BaseModel):
    """Parameters for validating whether a release is ready to ship."""

    release_id: str = Field(
        ...,
        description="Release sys_id, number, or name to validate.",
    )


class CompileReleaseNotesParams(BaseModel):
    """Parameters for compiling release notes from completed stories."""

    release_id: str = Field(
        ...,
        description="Release sys_id, number, or name.",
    )


# ---------------------------------------------------------------------------
# Internal helper — _fetch_release_stories
# ---------------------------------------------------------------------------


def _fetch_release_stories(
    config: ServerConfig,
    auth_manager: AuthManager,
    release_sys_id: str,
    fields: Optional[str] = None,
    limit: int = 500,
) -> List[Dict[str, Any]]:
    """
    Fetch all rm_story records associated with a release via its sprints.

    Steps:
      1. Fetch sprints for the release → collect sprint sys_ids.
      2. Build OR-query across sprint sys_ids.
      3. Fetch stories matching that query.
    Returns an empty list if no sprints or stories found.
    """
    headers = auth_manager.get_headers()

    # Step 1: get sprint sys_ids for this release
    sprint_url = f"{config.instance_url}/api/now/table/rm_sprint_2"
    try:
        response = requests.get(
            sprint_url,
            headers=headers,
            params={
                "sysparm_query": f"release={release_sys_id}",
                "sysparm_fields": "sys_id",
                "sysparm_limit": 50,
            },
            timeout=config.timeout,
        )
        response.raise_for_status()
        sprints = response.json().get("result", [])
    except requests.RequestException as e:
        logger.warning(
            "_fetch_release_stories | release=%s | sprint fetch error: %s",
            release_sys_id,
            e,
        )
        return []

    if not sprints:
        return []

    # Step 2: build OR-query
    sprint_ids = [
        s["sys_id"].get("value", s["sys_id"]) if isinstance(s["sys_id"], dict) else s["sys_id"]
        for s in sprints
        if s.get("sys_id")
    ]
    if not sprint_ids:
        return []

    story_query = "^OR".join(f"sprint={sid}" for sid in sprint_ids)

    # Step 3: fetch stories
    story_url = f"{config.instance_url}/api/now/table/rm_story"
    params: Dict[str, Any] = {
        "sysparm_query": story_query,
        "sysparm_limit": limit,
        "sysparm_display_value": "true",
    }
    if fields:
        params["sysparm_fields"] = fields

    try:
        response = requests.get(
            story_url,
            headers=headers,
            params=params,
            timeout=config.timeout,
        )
        response.raise_for_status()
        return response.json().get("result", [])
    except requests.RequestException as e:
        logger.warning(
            "_fetch_release_stories | release=%s | story fetch error: %s",
            release_sys_id,
            e,
        )
        return []


# ---------------------------------------------------------------------------
# Internal helper — _resolve_release
# ---------------------------------------------------------------------------


def _resolve_release(
    config: ServerConfig,
    auth_manager: AuthManager,
    release_id: str,
) -> Optional[Dict[str, Any]]:
    """
    Look up a release record by sys_id, number, or name.
    Returns the record dict (with display values) or None.
    """
    headers = auth_manager.get_headers()
    base_url = f"{config.instance_url}/api/now/table/rm_release"

    # Try direct sys_id lookup first
    try:
        response = requests.get(
            f"{base_url}/{release_id}",
            headers=headers,
            params={"sysparm_display_value": "true"},
            timeout=config.timeout,
        )
        if response.status_code == 200:
            result = response.json().get("result", {})
            if result:
                return result
    except requests.RequestException:
        pass

    # Fallback: query by number or name
    try:
        response = requests.get(
            base_url,
            headers=headers,
            params={
                "sysparm_query": f"number={release_id}^ORname={release_id}",
                "sysparm_limit": 1,
                "sysparm_display_value": "true",
            },
            timeout=config.timeout,
        )
        response.raise_for_status()
        records = response.json().get("result", [])
        return records[0] if records else None
    except requests.RequestException:
        return None


def _extract_sys_id(record: Dict[str, Any]) -> str:
    """Extract plain sys_id string from a record (handles display-value dict)."""
    raw = record.get("sys_id", {})
    return raw.get("value", raw) if isinstance(raw, dict) else str(raw)


# ---------------------------------------------------------------------------
# create_release
# ---------------------------------------------------------------------------


def create_release(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: CreateReleaseParams,
) -> Dict[str, Any]:
    """
    Create a new release in ServiceNow (rm_release).

    Returns the new release's sys_id, number, and name.
    """
    data: Dict[str, Any] = {"name": params.name}
    if params.planned_date:
        data["planned_date"] = params.planned_date
    if params.description:
        data["description"] = params.description

    url = f"{config.instance_url}/api/now/table/rm_release"
    headers = {**auth_manager.get_headers(), "Content-Type": "application/json"}

    try:
        response = requests.post(url, json=data, headers=headers, timeout=config.timeout)
        response.raise_for_status()
        result = response.json().get("result", {})
        return {
            "success": True,
            "message": f"Release '{params.name}' created successfully.",
            "release_id": result.get("sys_id"),
            "release_number": result.get("number"),
            "name": result.get("name"),
        }
    except requests.RequestException as e:
        body = getattr(e, "response", None)
        body_text = (body.text[:2000] if body and hasattr(body, "text") else "") or ""
        logger.error("create_release | name=%s | error=%s", params.name, e)
        return {
            "success": False,
            "message": f"Failed to create release: {e}" + (f" | {body_text}" if body_text else ""),
        }


# ---------------------------------------------------------------------------
# get_release
# ---------------------------------------------------------------------------


def get_release(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: GetReleaseParams,
) -> Dict[str, Any]:
    """
    Retrieve a single release by sys_id, release number, or name.

    Attempts a direct sys_id lookup first; falls back to a query by number/name.
    """
    release = _resolve_release(config, auth_manager, params.release_id.strip())
    if release:
        return {"success": True, "release": release}
    return {
        "success": False,
        "error_code": "RELEASE_NOT_FOUND",
        "message": f"No release found with id, number, or name '{params.release_id}'",
        "release_id": params.release_id,
    }


# ---------------------------------------------------------------------------
# validate_release_readiness
# ---------------------------------------------------------------------------


def validate_release_readiness(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: ValidateReleaseReadinessParams,
) -> Dict[str, Any]:
    """
    Run a readiness checklist against a release.

    Checks:
      1. all_stories_done — all stories are Complete or Cancelled.
      2. acceptance_criteria_populated — non-cancelled stories have non-empty AC.
      3. all_sprints_completed — every sprint in the release is Completed.
      4. planned_date_set — the release has a planned_date.
      5. no_in_progress_stories — no stories are in an in-progress state.
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
        logger.error("validate_release_readiness | sprint fetch | error=%s", e)
        sprints = []

    # Fetch stories via sprint join
    stories = _fetch_release_stories(
        config,
        auth_manager,
        release_sys_id,
        fields="sys_id,number,state,acceptance_criteria",
        limit=500,
    )

    # Run checks
    non_cancelled = [
        s for s in stories
        if str(s.get("state", "")) not in STORY_CANCELLED_STATES
    ]

    # 1. All stories done
    all_done = all(
        str(s.get("state", "")) in STORY_DONE_STATES | STORY_CANCELLED_STATES
        for s in stories
    )
    not_done_count = sum(
        1 for s in stories
        if str(s.get("state", "")) not in STORY_DONE_STATES | STORY_CANCELLED_STATES
    )

    # 2. AC populated on non-cancelled stories
    missing_ac = [
        s.get("number") for s in non_cancelled
        if not (s.get("acceptance_criteria") or "").strip()
    ]
    ac_ok = len(missing_ac) == 0

    # 3. All sprints completed
    incomplete_sprints = [
        s.get("name") for s in sprints
        if str(s.get("state", "")) != SPRINT_COMPLETED_STATE
    ]
    all_sprints_completed = len(incomplete_sprints) == 0

    # 4. Planned date set
    planned_date = release.get("planned_date") or ""
    planned_date_value = (
        planned_date.get("value", "") if isinstance(planned_date, dict) else planned_date
    )
    planned_date_set = bool(planned_date_value)

    # 5. No in-progress stories
    in_progress = [
        s.get("number") for s in stories
        if str(s.get("state", "")) in STORY_IN_PROGRESS_STATES
    ]
    no_in_progress = len(in_progress) == 0

    checks = [
        {
            "check": "all_stories_done",
            "passed": all_done,
            "detail": (
                f"{not_done_count} story/stories not yet complete."
                if not all_done
                else "All stories are Complete or Cancelled."
            ),
        },
        {
            "check": "acceptance_criteria_populated",
            "passed": ac_ok,
            "detail": (
                f"Missing AC on: {', '.join(missing_ac)}"
                if not ac_ok
                else "All non-cancelled stories have acceptance criteria."
            ),
        },
        {
            "check": "all_sprints_completed",
            "passed": all_sprints_completed,
            "detail": (
                f"Incomplete sprints: {', '.join(str(s) for s in incomplete_sprints)}"
                if not all_sprints_completed
                else "All sprints are Completed."
            ),
        },
        {
            "check": "planned_date_set",
            "passed": planned_date_set,
            "detail": (
                "Release planned_date is not set."
                if not planned_date_set
                else f"Planned date: {planned_date_value}"
            ),
        },
        {
            "check": "no_in_progress_stories",
            "passed": no_in_progress,
            "detail": (
                f"In-progress stories: {', '.join(str(s) for s in in_progress)}"
                if not no_in_progress
                else "No in-progress stories."
            ),
        },
    ]

    ready = all(c["passed"] for c in checks)

    return {
        "success": True,
        "release": release,
        "ready": ready,
        "checks": checks,
    }


# ---------------------------------------------------------------------------
# compile_release_notes
# ---------------------------------------------------------------------------


def compile_release_notes(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: CompileReleaseNotesParams,
) -> Dict[str, Any]:
    """
    Compile release notes from completed stories, grouped by epic.

    Returns story count, total points, and stories organised by epic title.
    """
    release = _resolve_release(config, auth_manager, params.release_id.strip())
    if not release:
        return {
            "success": False,
            "error_code": "RELEASE_NOT_FOUND",
            "message": f"No release found: '{params.release_id}'",
        }

    release_sys_id = _extract_sys_id(release)
    stories = _fetch_release_stories(
        config,
        auth_manager,
        release_sys_id,
        fields="sys_id,number,short_description,state,story_points,epic",
        limit=500,
    )

    # Filter to done stories only
    done_stories = [
        s for s in stories
        if str(s.get("state", "")) in STORY_DONE_STATES
    ]

    # Group by epic
    groups: Dict[str, Dict[str, Any]] = {}
    total_points = 0

    for story in done_stories:
        epic_ref = story.get("epic") or {}
        if isinstance(epic_ref, dict):
            epic_title = epic_ref.get("display_value") or epic_ref.get("value") or "No Epic"
        else:
            epic_title = str(epic_ref) if epic_ref else "No Epic"

        pts = int(story.get("story_points") or 0)
        total_points += pts

        if epic_title not in groups:
            groups[epic_title] = {"epic_title": epic_title, "stories": []}
        groups[epic_title]["stories"].append(
            {
                "number": story.get("number"),
                "title": story.get("short_description"),
                "story_points": pts,
            }
        )

    # Build release summary fields
    release_planned_date = release.get("planned_date") or ""
    if isinstance(release_planned_date, dict):
        release_planned_date = release_planned_date.get("display_value") or release_planned_date.get("value", "")

    release_name = release.get("name") or ""
    if isinstance(release_name, dict):
        release_name = release_name.get("display_value") or release_name.get("value", "")

    return {
        "success": True,
        "release": {
            "name": release_name,
            "planned_date": release_planned_date,
        },
        "story_count": len(done_stories),
        "stories_by_epic": list(groups.values()),
        "total_points": total_points,
    }
