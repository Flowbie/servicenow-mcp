"""
Tests for story_tools.py compound functions and internal helpers.

Covers: get_story (internal helper), archive_story, move_story_state.
CRUD wrappers (create_story, update_story, list_stories, list_story_dependencies,
create_story_dependency, delete_story_dependency, assign_story, add_story_comment,
list_story_blockers) have been removed from the module.
"""

import unittest
from unittest.mock import MagicMock, patch

from pydantic import ValidationError

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.story_tools import (
    ArchiveStoryParams,
    GetStoryParams,
    MoveStoryStateParams,
    archive_story,
    get_story,
    move_story_state,
)
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig


def _make_config() -> ServerConfig:
    auth_config = AuthConfig(
        type=AuthType.BASIC,
        basic=BasicAuthConfig(username="test", password="test"),
    )
    return ServerConfig(instance_url="https://dev12345.service-now.com", auth=auth_config)


def _make_auth() -> MagicMock:
    auth_manager = MagicMock(spec=AuthManager)
    auth_manager.get_headers.return_value = {"Authorization": "Bearer FAKE_TOKEN"}
    return auth_manager


def _story_fixture(state="1", acceptance_criteria="AC text", sys_id="story_sys_id_001"):
    return {
        "sys_id": sys_id,
        "number": "STRY0001234",
        "short_description": "Test story",
        "state": {"value": state, "display_value": state},
        "acceptance_criteria": acceptance_criteria,
        "assigned_to": {"value": "", "display_value": ""},
        "assignment_group": {"value": "", "display_value": ""},
        "story_points": 5,
    }


# ---------------------------------------------------------------------------
# get_story
# ---------------------------------------------------------------------------

class TestGetStory(unittest.TestCase):

    @patch("requests.get")
    def test_success_by_sys_id(self, mock_get):
        config = _make_config()
        auth = _make_auth()
        story = _story_fixture()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": story}
        mock_get.return_value = mock_response

        result = get_story(config, auth, GetStoryParams(story_id="story_sys_id_001"))

        self.assertTrue(result["success"])
        self.assertEqual(result["story"]["sys_id"], "story_sys_id_001")

    @patch("requests.get")
    def test_fallback_to_number_lookup(self, mock_get):
        config = _make_config()
        auth = _make_auth()
        story = _story_fixture()

        not_found = MagicMock()
        not_found.status_code = 404
        not_found.json.return_value = {}

        found = MagicMock()
        found.status_code = 200
        found.raise_for_status = MagicMock()
        found.json.return_value = {"result": [story]}

        mock_get.side_effect = [not_found, found]

        result = get_story(config, auth, GetStoryParams(story_id="STRY0001234"))

        self.assertTrue(result["success"])
        self.assertEqual(result["story"]["number"], "STRY0001234")

    @patch("requests.get")
    def test_not_found_returns_error_code(self, mock_get):
        config = _make_config()
        auth = _make_auth()

        not_found = MagicMock()
        not_found.status_code = 404

        empty = MagicMock()
        empty.status_code = 200
        empty.raise_for_status = MagicMock()
        empty.json.return_value = {"result": []}

        mock_get.side_effect = [not_found, empty]

        result = get_story(config, auth, GetStoryParams(story_id="STRY9999999"))

        self.assertFalse(result["success"])
        self.assertEqual(result["error_code"], "STORY_NOT_FOUND")

    def test_missing_story_id(self):
        with self.assertRaises(ValidationError):
            GetStoryParams()


# ---------------------------------------------------------------------------
# archive_story
# ---------------------------------------------------------------------------

class TestArchiveStory(unittest.TestCase):

    @patch("requests.patch")
    @patch("requests.get")
    def test_success(self, mock_get, mock_patch):
        config = _make_config()
        auth = _make_auth()
        story = _story_fixture(state="2")  # In Progress

        get_response = MagicMock()
        get_response.status_code = 200
        get_response.json.return_value = {"result": story}
        mock_get.return_value = get_response

        patch_response = MagicMock()
        patch_response.status_code = 200
        patch_response.raise_for_status = MagicMock()
        mock_patch.return_value = patch_response

        result = archive_story(config, auth, ArchiveStoryParams(story_id="story_sys_id_001", reason="Scope cut"))

        self.assertTrue(result["success"])
        self.assertEqual(result["new_state"], "4")
        self.assertEqual(result["previous_state"], "2")

    @patch("requests.get")
    def test_already_complete_blocked(self, mock_get):
        config = _make_config()
        auth = _make_auth()

        get_response = MagicMock()
        get_response.status_code = 200
        get_response.json.return_value = {"result": _story_fixture(state="3")}  # Complete
        mock_get.return_value = get_response

        result = archive_story(config, auth, ArchiveStoryParams(story_id="story_sys_id_001"))

        self.assertFalse(result["success"])
        self.assertEqual(result["error_code"], "STORY_ALREADY_TERMINAL")

    @patch("requests.get")
    def test_already_cancelled_blocked(self, mock_get):
        config = _make_config()
        auth = _make_auth()

        get_response = MagicMock()
        get_response.status_code = 200
        get_response.json.return_value = {"result": _story_fixture(state="4")}  # Cancelled
        mock_get.return_value = get_response

        result = archive_story(config, auth, ArchiveStoryParams(story_id="story_sys_id_001"))

        self.assertFalse(result["success"])
        self.assertEqual(result["error_code"], "STORY_ALREADY_TERMINAL")


# ---------------------------------------------------------------------------
# move_story_state
# ---------------------------------------------------------------------------

class TestMoveStoryState(unittest.TestCase):

    @patch("requests.patch")
    @patch("requests.get")
    def test_valid_transition_by_name(self, mock_get, mock_patch):
        config = _make_config()
        auth = _make_auth()

        get_response = MagicMock()
        get_response.status_code = 200
        get_response.json.return_value = {"result": _story_fixture(state="1")}  # Ready
        mock_get.return_value = get_response

        patch_response = MagicMock()
        patch_response.status_code = 200
        patch_response.raise_for_status = MagicMock()
        mock_patch.return_value = patch_response

        result = move_story_state(config, auth, MoveStoryStateParams(story_id="story_sys_id_001", target_state="in_progress"))

        self.assertTrue(result["success"])
        self.assertEqual(result["new_state"], "2")
        self.assertEqual(result["previous_state"], "1")

    @patch("requests.get")
    def test_invalid_transition_blocked(self, mock_get):
        config = _make_config()
        auth = _make_auth()

        get_response = MagicMock()
        get_response.status_code = 200
        get_response.json.return_value = {"result": _story_fixture(state="3")}  # Complete
        mock_get.return_value = get_response

        result = move_story_state(config, auth, MoveStoryStateParams(story_id="s1", target_state="in_progress"))

        self.assertFalse(result["success"])
        self.assertEqual(result["error_code"], "INVALID_TRANSITION")

    def test_cancelled_requires_reason(self):
        # Should be rejected before even fetching the story
        with patch("requests.get") as mock_get:
            result = move_story_state(
                _make_config(), _make_auth(),
                MoveStoryStateParams(story_id="s1", target_state="cancelled")
            )

            self.assertFalse(result["success"])
            self.assertEqual(result["error_code"], "REASON_REQUIRED")
            mock_get.assert_not_called()

    @patch("requests.get")
    def test_complete_requires_acceptance_criteria(self, mock_get):
        config = _make_config()
        auth = _make_auth()

        get_response = MagicMock()
        get_response.status_code = 200
        get_response.json.return_value = {
            "result": _story_fixture(state="-8", acceptance_criteria="")  # Testing, no AC
        }
        mock_get.return_value = get_response

        result = move_story_state(config, auth, MoveStoryStateParams(story_id="s1", target_state="complete"))

        self.assertFalse(result["success"])
        self.assertEqual(result["error_code"], "MISSING_ACCEPTANCE_CRITERIA")

    def test_unknown_state_returns_error(self):
        result = move_story_state(
            _make_config(), _make_auth(),
            MoveStoryStateParams(story_id="s1", target_state="flying")
        )
        self.assertFalse(result["success"])
        self.assertEqual(result["error_code"], "INVALID_STATE")

    @patch("requests.patch")
    @patch("requests.get")
    def test_accepts_numeric_state_value(self, mock_get, mock_patch):
        config = _make_config()
        auth = _make_auth()

        get_response = MagicMock()
        get_response.status_code = 200
        get_response.json.return_value = {"result": _story_fixture(state="1")}
        mock_get.return_value = get_response

        patch_response = MagicMock()
        patch_response.status_code = 200
        patch_response.raise_for_status = MagicMock()
        mock_patch.return_value = patch_response

        result = move_story_state(config, auth, MoveStoryStateParams(story_id="s1", target_state="2"))

        self.assertTrue(result["success"])
        self.assertEqual(result["new_state"], "2")


if __name__ == "__main__":
    unittest.main()
