"""
Integration tests for agile governance tools.
Run with: SN_INTEGRATION_TESTS=1 pytest tests/integration/test_agile_governance.py -v -s
"""
import json
import pytest

from servicenow_mcp.tools.story_tools import list_stories, ListStoriesParams
from servicenow_mcp.tools.agile_governance_tools import (
    validate_story_dependencies,
    validate_story_testing,
    validate_story_promotion_instructions,
    StoryIdParams,
)


def _get_real_story_id(live_config, live_auth):
    """Helper: get a real story sys_id from the instance, or skip."""
    result = list_stories(live_config, live_auth, ListStoriesParams(limit=1))
    if not result.get("success") or not result.get("stories"):
        pytest.skip("No stories available on this instance.")
    return result["stories"][0]["sys_id"]


@pytest.mark.integration
class TestAgileGovernanceIntegration:

    def test_validate_story_dependencies_returns_response(self, live_config, live_auth):
        """Verify validate_story_dependencies returns a structured response."""
        sys_id = _get_real_story_id(live_config, live_auth)
        params = StoryIdParams(story_id=sys_id)
        result = validate_story_dependencies(live_config, live_auth, params)

        print(f"\n--- validate_story_dependencies({sys_id}) response ---")
        print(json.dumps(result, indent=2, default=str))

        assert result["success"] is True, f"Expected success, got: {result.get('message')}"

    def test_validate_story_testing_returns_response(self, live_config, live_auth):
        """Verify validate_story_testing returns a structured response."""
        sys_id = _get_real_story_id(live_config, live_auth)
        params = StoryIdParams(story_id=sys_id)
        result = validate_story_testing(live_config, live_auth, params)

        print(f"\n--- validate_story_testing({sys_id}) response ---")
        print(json.dumps(result, indent=2, default=str))

        assert result["success"] is True, f"Expected success, got: {result.get('message')}"

    def test_validate_story_promotion_instructions_returns_response(self, live_config, live_auth):
        """Verify validate_story_promotion_instructions returns a structured response."""
        sys_id = _get_real_story_id(live_config, live_auth)
        params = StoryIdParams(story_id=sys_id)
        result = validate_story_promotion_instructions(live_config, live_auth, params)

        print(f"\n--- validate_story_promotion_instructions({sys_id}) response ---")
        print(json.dumps(result, indent=2, default=str))

        assert result["success"] is True, f"Expected success, got: {result.get('message')}"
