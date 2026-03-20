# tests/integration/test_stories.py
"""
Integration tests for story tools against a live ServiceNow instance.
Run with: SN_INTEGRATION_TESTS=1 pytest tests/integration/test_stories.py -v -s
"""
import json
import pytest

from servicenow_mcp.tools.story_tools import (
    list_stories,
    get_story,
    ListStoriesParams,
    GetStoryParams,
)


@pytest.mark.integration
class TestStoryIntegration:

    def test_list_stories_returns_results(self, live_config, live_auth):
        """Verify list_stories connects and returns records."""
        params = ListStoriesParams(limit=5)
        result = list_stories(live_config, live_auth, params)

        print("\n--- list_stories response ---")
        print(json.dumps(result, indent=2, default=str))

        assert result["success"] is True, f"Expected success, got: {result.get('message')}"
        assert "stories" in result
        assert isinstance(result["stories"], list)

    def test_list_stories_shape(self, live_config, live_auth):
        """Verify story records have expected fields."""
        params = ListStoriesParams(limit=3)
        result = list_stories(live_config, live_auth, params)

        assert result["success"] is True
        stories = result["stories"]

        if not stories:
            pytest.skip("No stories found on this instance.")

        first = stories[0]
        print("\n--- first story fields ---")
        print(json.dumps(first, indent=2, default=str))

        for field in ["sys_id", "number", "short_description", "state"]:
            assert field in first, f"Missing expected field: {field}"

    def test_get_story_by_sys_id(self, live_config, live_auth):
        """Verify get_story returns full story details."""
        list_result = list_stories(live_config, live_auth, ListStoriesParams(limit=1))
        assert list_result["success"] is True

        if not list_result["stories"]:
            pytest.skip("No stories on this instance.")

        sys_id = list_result["stories"][0]["sys_id"]

        params = GetStoryParams(story_id=sys_id)
        result = get_story(live_config, live_auth, params)

        print(f"\n--- get_story({sys_id}) response ---")
        print(json.dumps(result, indent=2, default=str))

        assert result["success"] is True
        assert "story" in result
        assert result["story"]["sys_id"] == sys_id

    def test_list_stories_limit_respected(self, live_config, live_auth):
        """Verify limit param is respected."""
        params = ListStoriesParams(limit=2)
        result = list_stories(live_config, live_auth, params)

        assert result["success"] is True
        assert len(result["stories"]) <= 2

    def test_get_story_not_found(self, live_config, live_auth):
        """Verify graceful not-found handling."""
        params = GetStoryParams(story_id="nonexistent_sys_id_00000000000")
        result = get_story(live_config, live_auth, params)

        print("\n--- not_found response ---")
        print(json.dumps(result, indent=2, default=str))

        assert result["success"] is False
        assert "message" in result
