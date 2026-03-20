"""
Tests for Phase 10 agile quick win: assign_stories_to_sprint.
"""

import unittest
from unittest.mock import MagicMock, call, patch

import requests

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.story_tools import (
    AssignStoriesToSprintParams,
    assign_stories_to_sprint,
)
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig


class TestAssignStoriesToSprint(unittest.TestCase):
    """Tests for assign_stories_to_sprint."""

    def setUp(self):
        self.auth_config = AuthConfig(
            type=AuthType.BASIC,
            basic=BasicAuthConfig(username="test_user", password="test_password"),
        )
        self.config = ServerConfig(
            instance_url="https://test.service-now.com",
            auth=self.auth_config,
        )
        self.auth_manager = MagicMock(spec=AuthManager)
        self.auth_manager.get_headers.return_value = {"Authorization": "Bearer FAKE_TOKEN"}

    @patch("servicenow_mcp.tools.story_tools.requests.put")
    def test_assign_all_stories_success(self, mock_put):
        """assign_stories_to_sprint assigns all stories and returns correct counts."""
        mock_put.return_value = MagicMock(**{
            "json.return_value": {"result": {"sys_id": "story1", "sprint": "sprint1"}},
            "raise_for_status": MagicMock(),
        })

        params = AssignStoriesToSprintParams(
            sprint_id="sprint1",
            story_ids=["story1", "story2", "story3"],
        )
        result = assign_stories_to_sprint(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        self.assertEqual(result["assigned"], 3)
        self.assertEqual(result["failed"], [])
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["sprint_id"], "sprint1")
        # Should have made 3 PATCH calls
        self.assertEqual(mock_put.call_count, 3)

    @patch("servicenow_mcp.tools.story_tools.requests.put")
    def test_assign_stories_sprint_id_in_payload(self, mock_put):
        """assign_stories_to_sprint passes sprint_id as sprint field in each PATCH."""
        mock_put.return_value = MagicMock(**{
            "json.return_value": {"result": {"sys_id": "s1"}},
            "raise_for_status": MagicMock(),
        })

        assign_stories_to_sprint(
            self.config, self.auth_manager,
            AssignStoriesToSprintParams(sprint_id="sprint42", story_ids=["s1"])
        )

        sent_data = mock_put.call_args[1]["json"]
        self.assertEqual(sent_data["sprint"], "sprint42")

    @patch("servicenow_mcp.tools.story_tools.requests.put")
    def test_assign_partial_failure(self, mock_put):
        """assign_stories_to_sprint tracks failed stories individually."""
        def side_effect(url, **kwargs):
            if "story_fail" in url:
                raise requests.RequestException("403 Forbidden")
            resp = MagicMock()
            resp.json.return_value = {"result": {"sys_id": "ok"}}
            resp.raise_for_status = MagicMock()
            return resp

        mock_put.side_effect = side_effect

        params = AssignStoriesToSprintParams(
            sprint_id="sprint1",
            story_ids=["story_ok", "story_fail"],
        )
        result = assign_stories_to_sprint(self.config, self.auth_manager, params)

        self.assertFalse(result["success"])
        self.assertEqual(result["assigned"], 1)
        self.assertEqual(result["failed"], ["story_fail"])
        self.assertEqual(len(result["errors"]), 1)

    @patch("servicenow_mcp.tools.story_tools.requests.put")
    def test_assign_all_fail(self, mock_put):
        """assign_stories_to_sprint returns success=False when all stories fail."""
        mock_put.side_effect = requests.RequestException("500 error")

        params = AssignStoriesToSprintParams(
            sprint_id="sprint1",
            story_ids=["s1", "s2"],
        )
        result = assign_stories_to_sprint(self.config, self.auth_manager, params)

        self.assertFalse(result["success"])
        self.assertEqual(result["assigned"], 0)
        self.assertEqual(len(result["failed"]), 2)
        self.assertEqual(len(result["errors"]), 2)

    @patch("servicenow_mcp.tools.story_tools.requests.put")
    def test_assign_single_story(self, mock_put):
        """assign_stories_to_sprint works for a single story."""
        mock_put.return_value = MagicMock(**{
            "json.return_value": {"result": {"sys_id": "s1"}},
            "raise_for_status": MagicMock(),
        })

        result = assign_stories_to_sprint(
            self.config, self.auth_manager,
            AssignStoriesToSprintParams(sprint_id="sp1", story_ids=["s1"])
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["assigned"], 1)

    @patch("servicenow_mcp.tools.story_tools.requests.put")
    def test_result_contains_required_keys(self, mock_put):
        """assign_stories_to_sprint result always contains all expected keys."""
        mock_put.return_value = MagicMock(**{
            "json.return_value": {"result": {"sys_id": "s1"}},
            "raise_for_status": MagicMock(),
        })

        result = assign_stories_to_sprint(
            self.config, self.auth_manager,
            AssignStoriesToSprintParams(sprint_id="sp1", story_ids=["s1"])
        )

        for key in ["success", "message", "sprint_id", "assigned", "failed", "errors"]:
            self.assertIn(key, result, f"Missing key: {key}")

    @patch("servicenow_mcp.tools.story_tools.requests.put")
    def test_assign_stories_each_story_patched_separately(self, mock_put):
        """assign_stories_to_sprint makes one PATCH call per story."""
        mock_put.return_value = MagicMock(**{
            "json.return_value": {"result": {"sys_id": "s1"}},
            "raise_for_status": MagicMock(),
        })

        story_ids = ["s1", "s2", "s3", "s4", "s5"]
        assign_stories_to_sprint(
            self.config, self.auth_manager,
            AssignStoriesToSprintParams(sprint_id="sp1", story_ids=story_ids)
        )

        self.assertEqual(mock_put.call_count, len(story_ids))
        # Each call should hit a different story URL
        called_urls = [c[0][0] for c in mock_put.call_args_list]
        for story_id in story_ids:
            self.assertTrue(
                any(story_id in url for url in called_urls),
                f"No PATCH call found for story {story_id}"
            )

    @patch("servicenow_mcp.tools.story_tools.requests.put")
    def test_message_includes_counts(self, mock_put):
        """assign_stories_to_sprint message includes assigned and total counts."""
        mock_put.return_value = MagicMock(**{
            "json.return_value": {"result": {"sys_id": "s1"}},
            "raise_for_status": MagicMock(),
        })

        result = assign_stories_to_sprint(
            self.config, self.auth_manager,
            AssignStoriesToSprintParams(sprint_id="sprint99", story_ids=["s1", "s2"])
        )

        self.assertIn("2/2", result["message"])
        self.assertIn("sprint99", result["message"])


if __name__ == "__main__":
    unittest.main()
