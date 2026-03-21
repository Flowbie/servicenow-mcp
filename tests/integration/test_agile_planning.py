"""
Integration tests for agile planning tools against a live ServiceNow instance.
Run with: SN_INTEGRATION_TESTS=1 pytest tests/integration/test_agile_planning.py -v -s

Note: These tools may call the Claude API internally. If they require ANTHROPIC_API_KEY,
tests will skip when the key is absent.
"""
import json
import os
import pytest

from servicenow_mcp.tools.story_tools import list_stories, ListStoriesParams
from servicenow_mcp.tools.agile_planning_tools import (
    story_breakdown,
    generate_acceptance_criteria,
    estimate_story_points,
    identify_story_risks,
    generate_test_scenarios,
    StoryIdParams,
)


def _get_real_story_id(live_config, live_auth):
    """Helper: get a real story sys_id from the instance, or skip."""
    result = list_stories(live_config, live_auth, ListStoriesParams(limit=1))
    if not result.get("success") or not result.get("stories"):
        pytest.skip("No stories available on this instance.")
    return result["stories"][0]["sys_id"]


@pytest.mark.integration
class TestAgilePlanningIntegration:

    def test_story_breakdown_returns_response(self, live_config, live_auth):
        """Verify story_breakdown connects and returns a structured response."""
        sys_id = _get_real_story_id(live_config, live_auth)
        params = StoryIdParams(story_id=sys_id)
        result = story_breakdown(live_config, live_auth, params)

        print(f"\n--- story_breakdown({sys_id}) response ---")
        print(json.dumps(result, indent=2, default=str))

        assert "success" in result

    def test_generate_acceptance_criteria_returns_response(self, live_config, live_auth):
        """Verify generate_acceptance_criteria returns a structured response."""
        sys_id = _get_real_story_id(live_config, live_auth)
        params = StoryIdParams(story_id=sys_id)
        result = generate_acceptance_criteria(live_config, live_auth, params)

        print(f"\n--- generate_acceptance_criteria({sys_id}) response ---")
        print(json.dumps(result, indent=2, default=str))

        assert "success" in result

    def test_estimate_story_points_returns_response(self, live_config, live_auth):
        """Verify estimate_story_points returns a structured response."""
        sys_id = _get_real_story_id(live_config, live_auth)
        params = StoryIdParams(story_id=sys_id)
        result = estimate_story_points(live_config, live_auth, params)

        print(f"\n--- estimate_story_points({sys_id}) response ---")
        print(json.dumps(result, indent=2, default=str))

        assert "success" in result

    def test_identify_story_risks_returns_response(self, live_config, live_auth):
        """Verify identify_story_risks returns a structured response."""
        sys_id = _get_real_story_id(live_config, live_auth)
        params = StoryIdParams(story_id=sys_id)
        result = identify_story_risks(live_config, live_auth, params)

        print(f"\n--- identify_story_risks({sys_id}) response ---")
        print(json.dumps(result, indent=2, default=str))

        assert "success" in result

    def test_generate_test_scenarios_returns_response(self, live_config, live_auth):
        """Verify generate_test_scenarios returns a structured response."""
        sys_id = _get_real_story_id(live_config, live_auth)
        params = StoryIdParams(story_id=sys_id)
        result = generate_test_scenarios(live_config, live_auth, params)

        print(f"\n--- generate_test_scenarios({sys_id}) response ---")
        print(json.dumps(result, indent=2, default=str))

        assert "success" in result
