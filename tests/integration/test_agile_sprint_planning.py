"""
Integration tests for agile sprint planning tools.
Run with: SN_INTEGRATION_TESTS=1 pytest tests/integration/test_agile_sprint_planning.py -v -s
"""
import json
import pytest
import requests

from servicenow_mcp.tools.agile_sprint_planning_tools import (
    recommend_sprint_stories,
    RecommendSprintStoriesParams,
)


def _get_real_sprint_id(live_config, live_auth):
    """Helper: get a real sprint sys_id from the instance, or skip."""
    resp = requests.get(
        f"{live_config.instance_url}/api/now/table/rm_sprint_2",
        headers=live_auth.get_headers(),
        params={"sysparm_fields": "sys_id,name,state", "sysparm_limit": 1},
        timeout=live_config.timeout,
    )
    sprints = resp.json().get("result", [])
    if not sprints:
        pytest.skip("No sprints available on this instance.")
    return sprints[0]["sys_id"]


@pytest.mark.integration
class TestSprintPlanningIntegration:

    def test_recommend_sprint_stories_returns_response(self, live_config, live_auth):
        """Verify recommend_sprint_stories returns a structured response."""
        sprint_id = _get_real_sprint_id(live_config, live_auth)
        params = RecommendSprintStoriesParams(sprint_id=sprint_id)
        result = recommend_sprint_stories(live_config, live_auth, params)

        print("\n--- recommend_sprint_stories response ---")
        print(json.dumps(result, indent=2, default=str))

        assert result["success"] is True, f"Expected success, got: {result.get('message')}"

    def test_recommend_sprint_stories_shape(self, live_config, live_auth):
        """Verify the response includes expected partition keys."""
        sprint_id = _get_real_sprint_id(live_config, live_auth)
        params = RecommendSprintStoriesParams(sprint_id=sprint_id)
        result = recommend_sprint_stories(live_config, live_auth, params)

        assert result["success"] is True, f"Expected success, got: {result.get('message')}"

        print("\n--- sprint recommendation shape ---")
        print(json.dumps(result, indent=2, default=str))

        # Verify partition keys exist in response
        assert "recommended" in result
        assert "blocked" in result
        assert "over_capacity" in result
        assert "summary" in result
