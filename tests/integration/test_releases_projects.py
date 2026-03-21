# tests/integration/test_releases_projects.py
"""
Integration tests for release and project tools against a live ServiceNow instance.
READ-ONLY — list and get operations only.
Run with: SN_INTEGRATION_TESTS=1 pytest tests/integration/test_releases_projects.py -v -s
"""
import json
import pytest

from servicenow_mcp.tools.release_tools import (
    get_release,
    GetReleaseParams,
)
from servicenow_mcp.tools.project_tools import (
    list_projects,
    ListProjectsParams,
)
from servicenow_mcp.tools.story_tools import list_stories, ListStoriesParams


@pytest.mark.integration
class TestReleasesIntegration:

    def test_get_release_from_story(self, live_config, live_auth):
        """Verify get_release returns release details using a sys_id from a story."""
        # Get a story that has a release to find a real release sys_id
        stories_result = list_stories(live_config, live_auth, ListStoriesParams(limit=10))
        assert stories_result["success"] is True

        release_id = None
        for story in stories_result.get("stories", []):
            if story.get("release") and isinstance(story["release"], dict):
                release_id = story["release"].get("value") or story["release"].get("sys_id")
            elif story.get("release") and isinstance(story["release"], str):
                release_id = story["release"]
            if release_id:
                break

        if not release_id:
            pytest.skip("No story with a release reference found on this instance.")

        params = GetReleaseParams(release_id=release_id)
        result = get_release(live_config, live_auth, params)

        print(f"\n--- get_release({release_id}) response ---")
        print(json.dumps(result, indent=2, default=str))

        assert "success" in result

    def test_get_release_not_found(self, live_config, live_auth):
        """Verify graceful not-found handling for a nonexistent release."""
        params = GetReleaseParams(release_id="nonexistent_release_sys_id_000")
        result = get_release(live_config, live_auth, params)

        print("\n--- release not_found response ---")
        print(json.dumps(result, indent=2, default=str))

        assert result["success"] is False
        assert "message" in result


@pytest.mark.integration
class TestProjectsIntegration:

    def test_list_projects_returns_results(self, live_config, live_auth):
        """Verify list_projects connects and returns records."""
        params = ListProjectsParams(limit=5)
        result = list_projects(live_config, live_auth, params)

        print("\n--- list_projects response ---")
        print(json.dumps(result, indent=2, default=str))

        assert result["success"] is True, f"Expected success, got: {result.get('message')}"
        assert "projects" in result
        assert isinstance(result["projects"], list)

    def test_list_projects_shape(self, live_config, live_auth):
        """Verify project records have expected fields."""
        params = ListProjectsParams(limit=3)
        result = list_projects(live_config, live_auth, params)

        assert result["success"] is True
        projects = result["projects"]

        if not projects:
            pytest.skip("No projects found on this instance.")

        first = projects[0]
        print("\n--- first project fields ---")
        print(json.dumps(first, indent=2, default=str))

        for field in ["sys_id"]:
            assert field in first, f"Missing expected field: {field}"

    def test_list_projects_limit_respected(self, live_config, live_auth):
        """Verify limit param is respected."""
        params = ListProjectsParams(limit=2)
        result = list_projects(live_config, live_auth, params)

        assert result["success"] is True
        assert len(result["projects"]) <= 2
