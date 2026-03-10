"""
Tests for agile governance tools:
  validate_story_dependencies, validate_story_testing,
  validate_story_promotion_instructions.
"""

import unittest
from unittest.mock import MagicMock, patch

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.agile_governance_tools import (
    StoryIdParams,
    validate_story_dependencies,
    validate_story_testing,
    validate_story_promotion_instructions,
)
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config() -> ServerConfig:
    auth_config = AuthConfig(
        type=AuthType.BASIC,
        basic=BasicAuthConfig(username="test", password="test"),
    )
    return ServerConfig(instance_url="https://dev12345.service-now.com", auth=auth_config)


def _make_auth() -> MagicMock:
    auth = MagicMock(spec=AuthManager)
    auth.get_headers.return_value = {"Authorization": "Bearer FAKE"}
    return auth


def _ok(result):
    resp = MagicMock()
    resp.status_code = 200
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {"result": result}
    return resp


def _ok_single(result):
    """For endpoints that return a single object (not a list)."""
    resp = MagicMock()
    resp.status_code = 200
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {"result": result}
    return resp


def _request_error():
    import requests as req
    err = req.RequestException("connection error")
    err.response = None
    return err


def _dep(prereq_id="pre_001", prereq_number="STRY0001", title="Prereq story", state="1"):
    return {
        "sys_id": "dep_001",
        "prerequisite_story": prereq_id,
        "prerequisite_story.number": prereq_number,
        "prerequisite_story.short_description": title,
        "prerequisite_story.state": state,
    }


def _task(number="TASK0001", state="1", title="Test the feature"):
    return {
        "sys_id": "task_001",
        "number": number,
        "short_description": title,
        "state": state,
        "assigned_to": "user_001",
    }


def _story(promotion_instructions="Deploy via update set XYZ"):
    return {
        "sys_id": "story_001",
        "number": "STRY0001234",
        "promotion_instructions": promotion_instructions,
    }


STORY_ID = "story_abc123"
PARAMS = StoryIdParams(story_id=STORY_ID)


# ---------------------------------------------------------------------------
# validate_story_dependencies
# ---------------------------------------------------------------------------


class TestValidateStoryDependencies(unittest.TestCase):

    @patch("servicenow_mcp.tools.agile_governance_tools.requests.get")
    def test_no_dependencies_returns_met(self, mock_get):
        """Story with no dependencies: all_dependencies_met=True, open_blockers=[]."""
        mock_get.return_value = _ok([])
        result = validate_story_dependencies(_make_config(), _make_auth(), PARAMS)
        self.assertTrue(result["success"])
        self.assertTrue(result["all_dependencies_met"])
        self.assertEqual(result["open_blockers"], [])

    @patch("servicenow_mcp.tools.agile_governance_tools.requests.get")
    def test_all_prerequisites_complete(self, mock_get):
        """All prerequisites in state 3 (Complete): all_dependencies_met=True."""
        mock_get.return_value = _ok([_dep(state="3"), _dep(state="3")])
        result = validate_story_dependencies(_make_config(), _make_auth(), PARAMS)
        self.assertTrue(result["success"])
        self.assertTrue(result["all_dependencies_met"])
        self.assertEqual(len(result["open_blockers"]), 0)

    @patch("servicenow_mcp.tools.agile_governance_tools.requests.get")
    def test_all_prerequisites_cancelled(self, mock_get):
        """All prerequisites in state 4 (Cancelled): all_dependencies_met=True."""
        mock_get.return_value = _ok([_dep(state="4")])
        result = validate_story_dependencies(_make_config(), _make_auth(), PARAMS)
        self.assertTrue(result["success"])
        self.assertTrue(result["all_dependencies_met"])

    @patch("servicenow_mcp.tools.agile_governance_tools.requests.get")
    def test_open_blocker_returns_not_met(self, mock_get):
        """One prerequisite still In Progress: all_dependencies_met=False."""
        mock_get.return_value = _ok([_dep(state="2", prereq_number="STRY0002", title="Blocker")])
        result = validate_story_dependencies(_make_config(), _make_auth(), PARAMS)
        self.assertTrue(result["success"])
        self.assertFalse(result["all_dependencies_met"])
        self.assertEqual(len(result["open_blockers"]), 1)
        self.assertEqual(result["open_blockers"][0]["number"], "STRY0002")
        self.assertEqual(result["open_blockers"][0]["state"], "2")

    @patch("servicenow_mcp.tools.agile_governance_tools.requests.get")
    def test_mixed_complete_and_open(self, mock_get):
        """One complete, one open: all_dependencies_met=False, one blocker."""
        mock_get.return_value = _ok([_dep(state="3"), _dep(state="1", prereq_number="STRY0099")])
        result = validate_story_dependencies(_make_config(), _make_auth(), PARAMS)
        self.assertFalse(result["all_dependencies_met"])
        self.assertEqual(len(result["open_blockers"]), 1)

    @patch("servicenow_mcp.tools.agile_governance_tools.requests.get")
    def test_request_error_returns_failure(self, mock_get):
        """Network error: success=False with message."""
        mock_get.side_effect = _request_error()
        result = validate_story_dependencies(_make_config(), _make_auth(), PARAMS)
        self.assertFalse(result["success"])
        self.assertIn("Failed to fetch", result["message"])

    @patch("servicenow_mcp.tools.agile_governance_tools.requests.get")
    def test_story_id_in_response(self, mock_get):
        """story_id is always echoed back in success response."""
        mock_get.return_value = _ok([])
        result = validate_story_dependencies(_make_config(), _make_auth(), PARAMS)
        self.assertEqual(result["story_id"], STORY_ID)


# ---------------------------------------------------------------------------
# validate_story_testing
# ---------------------------------------------------------------------------


class TestValidateStoryTesting(unittest.TestCase):

    @patch("servicenow_mcp.tools.agile_governance_tools.requests.get")
    def test_no_testing_tasks_returns_incomplete(self, mock_get):
        """No testing tasks: testing_complete=False, total=0."""
        mock_get.return_value = _ok([])
        result = validate_story_testing(_make_config(), _make_auth(), PARAMS)
        self.assertTrue(result["success"])
        self.assertFalse(result["testing_complete"])
        self.assertEqual(result["total_testing_tasks"], 0)
        self.assertIn("No testing tasks", result["message"])

    @patch("servicenow_mcp.tools.agile_governance_tools.requests.get")
    def test_all_tasks_complete(self, mock_get):
        """All tasks in state 3 (Complete): testing_complete=True."""
        mock_get.return_value = _ok([_task(state="3"), _task(state="3")])
        result = validate_story_testing(_make_config(), _make_auth(), PARAMS)
        self.assertTrue(result["success"])
        self.assertTrue(result["testing_complete"])
        self.assertEqual(result["total_testing_tasks"], 2)
        self.assertEqual(result["incomplete_tasks"], [])

    @patch("servicenow_mcp.tools.agile_governance_tools.requests.get")
    def test_all_tasks_cancelled(self, mock_get):
        """All tasks in state 4 (Cancelled): testing_complete=True."""
        mock_get.return_value = _ok([_task(state="4")])
        result = validate_story_testing(_make_config(), _make_auth(), PARAMS)
        self.assertTrue(result["testing_complete"])

    @patch("servicenow_mcp.tools.agile_governance_tools.requests.get")
    def test_one_incomplete_task(self, mock_get):
        """One task still In Progress: testing_complete=False, incomplete_tasks populated."""
        mock_get.return_value = _ok([_task(state="3"), _task(number="TASK0002", state="2")])
        result = validate_story_testing(_make_config(), _make_auth(), PARAMS)
        self.assertFalse(result["testing_complete"])
        self.assertEqual(result["total_testing_tasks"], 2)
        self.assertEqual(len(result["incomplete_tasks"]), 1)
        self.assertEqual(result["incomplete_tasks"][0]["number"], "TASK0002")

    @patch("servicenow_mcp.tools.agile_governance_tools.requests.get")
    def test_all_tasks_incomplete(self, mock_get):
        """All tasks open: testing_complete=False, all returned in incomplete_tasks."""
        mock_get.return_value = _ok([_task(state="1"), _task(state="2")])
        result = validate_story_testing(_make_config(), _make_auth(), PARAMS)
        self.assertFalse(result["testing_complete"])
        self.assertEqual(len(result["incomplete_tasks"]), 2)

    @patch("servicenow_mcp.tools.agile_governance_tools.requests.get")
    def test_request_error_returns_failure(self, mock_get):
        """Network error: success=False."""
        mock_get.side_effect = _request_error()
        result = validate_story_testing(_make_config(), _make_auth(), PARAMS)
        self.assertFalse(result["success"])
        self.assertIn("Failed to fetch", result["message"])

    @patch("servicenow_mcp.tools.agile_governance_tools.requests.get")
    def test_story_id_echoed(self, mock_get):
        """story_id is always present in response."""
        mock_get.return_value = _ok([])
        result = validate_story_testing(_make_config(), _make_auth(), PARAMS)
        self.assertEqual(result["story_id"], STORY_ID)


# ---------------------------------------------------------------------------
# validate_story_promotion_instructions
# ---------------------------------------------------------------------------


class TestValidateStoryPromotionInstructions(unittest.TestCase):

    @patch("servicenow_mcp.tools.agile_governance_tools.requests.get")
    def test_instructions_present(self, mock_get):
        """Story has promotion instructions: has_promotion_instructions=True."""
        mock_get.return_value = _ok_single(_story("Deploy via update set ABC"))
        result = validate_story_promotion_instructions(_make_config(), _make_auth(), PARAMS)
        self.assertTrue(result["success"])
        self.assertTrue(result["has_promotion_instructions"])
        self.assertEqual(result["field_value"], "Deploy via update set ABC")

    @patch("servicenow_mcp.tools.agile_governance_tools.requests.get")
    def test_instructions_empty_string(self, mock_get):
        """Empty string: has_promotion_instructions=False."""
        mock_get.return_value = _ok_single(_story(""))
        result = validate_story_promotion_instructions(_make_config(), _make_auth(), PARAMS)
        self.assertTrue(result["success"])
        self.assertFalse(result["has_promotion_instructions"])
        self.assertEqual(result["field_value"], "")

    @patch("servicenow_mcp.tools.agile_governance_tools.requests.get")
    def test_instructions_whitespace_only(self, mock_get):
        """Whitespace-only string: has_promotion_instructions=False."""
        mock_get.return_value = _ok_single(_story("   \n  "))
        result = validate_story_promotion_instructions(_make_config(), _make_auth(), PARAMS)
        self.assertFalse(result["has_promotion_instructions"])
        self.assertEqual(result["field_value"], "")

    @patch("servicenow_mcp.tools.agile_governance_tools.requests.get")
    def test_instructions_none(self, mock_get):
        """None field: has_promotion_instructions=False."""
        mock_get.return_value = _ok_single(_story(None))
        result = validate_story_promotion_instructions(_make_config(), _make_auth(), PARAMS)
        self.assertFalse(result["has_promotion_instructions"])

    @patch("servicenow_mcp.tools.agile_governance_tools.requests.get")
    def test_story_not_found(self, mock_get):
        """result=None: success=False, STORY_NOT_FOUND error code."""
        mock_get.return_value = _ok_single(None)
        result = validate_story_promotion_instructions(_make_config(), _make_auth(), PARAMS)
        self.assertFalse(result["success"])
        self.assertEqual(result["error_code"], "STORY_NOT_FOUND")

    @patch("servicenow_mcp.tools.agile_governance_tools.requests.get")
    def test_instructions_as_dict_value(self, mock_get):
        """ServiceNow display_value dict format is handled correctly."""
        story = {
            "sys_id": "story_001",
            "number": "STRY0001234",
            "promotion_instructions": {"value": "Run update set XYZ", "display_value": "Run update set XYZ"},
        }
        mock_get.return_value = _ok_single(story)
        result = validate_story_promotion_instructions(_make_config(), _make_auth(), PARAMS)
        self.assertTrue(result["has_promotion_instructions"])
        self.assertEqual(result["field_value"], "Run update set XYZ")

    @patch("servicenow_mcp.tools.agile_governance_tools.requests.get")
    def test_request_error_returns_failure(self, mock_get):
        """Network error: success=False."""
        mock_get.side_effect = _request_error()
        result = validate_story_promotion_instructions(_make_config(), _make_auth(), PARAMS)
        self.assertFalse(result["success"])
        self.assertIn("Failed to fetch", result["message"])

    @patch("servicenow_mcp.tools.agile_governance_tools.requests.get")
    def test_story_id_echoed(self, mock_get):
        """story_id is always echoed in success response."""
        mock_get.return_value = _ok_single(_story("Deploy"))
        result = validate_story_promotion_instructions(_make_config(), _make_auth(), PARAMS)
        self.assertEqual(result["story_id"], STORY_ID)


if __name__ == "__main__":
    unittest.main()
