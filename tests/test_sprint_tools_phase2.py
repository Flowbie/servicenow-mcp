"""
Tests for Phase 2 sprint tools: start_sprint, close_sprint.
"""

import unittest
from unittest.mock import MagicMock, patch

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.sprint_tools import (
    StartSprintParams,
    CloseSprintParams,
    start_sprint,
    close_sprint,
)
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig


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


def _sprint_fixture(state="1", sys_id="sprint_001", name="Sprint 14"):
    return {
        "sys_id": sys_id,
        "number": "SPRINT0001234",
        "name": name,
        "state": state,
        "start_date": "2026-03-01",
        "end_date": "2026-03-14",
    }


def _mock_sprint_lookup(mock_get, sprint_record):
    """Return sprint record on direct sys_id lookup."""
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"result": sprint_record}
    return resp


def _mock_open_stories(mock_get, count=0):
    """Return a story count response."""
    stories = [{"sys_id": f"s{i}"} for i in range(count)]
    resp = MagicMock()
    resp.status_code = 200
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {"result": stories}
    return resp


def _mock_patch_ok():
    resp = MagicMock()
    resp.status_code = 200
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {"result": {}}
    return resp


# ---------------------------------------------------------------------------
# start_sprint
# ---------------------------------------------------------------------------


class TestStartSprint(unittest.TestCase):

    @patch("requests.patch")
    @patch("requests.get")
    def test_success_from_planning(self, mock_get, mock_patch):
        config = _make_config()
        auth = _make_auth()

        mock_get.side_effect = [
            _mock_sprint_lookup(mock_get, _sprint_fixture(state="1")),
            _mock_open_stories(mock_get, count=3),
        ]
        mock_patch.return_value = _mock_patch_ok()

        result = start_sprint(config, auth, StartSprintParams(sprint_id="sprint_001"))

        self.assertTrue(result["success"])
        self.assertEqual(result["previous_state"], "1")
        self.assertEqual(result["new_state"], "2")
        self.assertEqual(result["open_story_count"], 3)

    @patch("requests.patch")
    @patch("requests.get")
    def test_invalid_transition_from_active(self, mock_get, mock_patch):
        """Cannot start an already-active sprint."""
        config = _make_config()
        auth = _make_auth()

        mock_get.return_value = _mock_sprint_lookup(mock_get, _sprint_fixture(state="2"))

        result = start_sprint(config, auth, StartSprintParams(sprint_id="sprint_001"))

        self.assertFalse(result["success"])
        self.assertEqual(result["error_code"], "INVALID_TRANSITION")
        mock_patch.assert_not_called()

    @patch("requests.patch")
    @patch("requests.get")
    def test_invalid_transition_from_completed(self, mock_get, mock_patch):
        """Cannot start a completed sprint."""
        config = _make_config()
        auth = _make_auth()

        mock_get.return_value = _mock_sprint_lookup(mock_get, _sprint_fixture(state="3"))

        result = start_sprint(config, auth, StartSprintParams(sprint_id="sprint_001"))

        self.assertFalse(result["success"])
        self.assertEqual(result["error_code"], "INVALID_TRANSITION")

    @patch("requests.patch")
    @patch("requests.get")
    def test_sprint_not_found(self, mock_get, mock_patch):
        not_found = MagicMock()
        not_found.status_code = 404

        empty = MagicMock()
        empty.status_code = 200
        empty.raise_for_status = MagicMock()
        empty.json.return_value = {"result": []}

        mock_get.side_effect = [not_found, empty]

        result = start_sprint(_make_config(), _make_auth(), StartSprintParams(sprint_id="bad_id"))

        self.assertFalse(result["success"])
        self.assertEqual(result["error_code"], "SPRINT_NOT_FOUND")
        mock_patch.assert_not_called()

    @patch("requests.patch")
    @patch("requests.get")
    def test_open_story_count_zero_still_succeeds(self, mock_get, mock_patch):
        config = _make_config()
        auth = _make_auth()

        mock_get.side_effect = [
            _mock_sprint_lookup(mock_get, _sprint_fixture(state="1")),
            _mock_open_stories(mock_get, count=0),
        ]
        mock_patch.return_value = _mock_patch_ok()

        result = start_sprint(config, auth, StartSprintParams(sprint_id="sprint_001"))

        self.assertTrue(result["success"])
        self.assertEqual(result["open_story_count"], 0)

    @patch("requests.patch")
    @patch("requests.get")
    def test_patches_correct_state(self, mock_get, mock_patch):
        """Verify the PATCH body sets state='2' (Active)."""
        config = _make_config()
        auth = _make_auth()

        mock_get.side_effect = [
            _mock_sprint_lookup(mock_get, _sprint_fixture(state="1")),
            _mock_open_stories(mock_get, count=0),
        ]
        mock_patch.return_value = _mock_patch_ok()

        start_sprint(config, auth, StartSprintParams(sprint_id="sprint_001"))

        patched_body = mock_patch.call_args.kwargs.get("json") or mock_patch.call_args[1].get("json", {})
        self.assertEqual(patched_body.get("state"), "2")


# ---------------------------------------------------------------------------
# close_sprint
# ---------------------------------------------------------------------------


class TestCloseSprint(unittest.TestCase):

    @patch("requests.patch")
    @patch("requests.get")
    def test_success_no_open_stories(self, mock_get, mock_patch):
        config = _make_config()
        auth = _make_auth()

        mock_get.side_effect = [
            _mock_sprint_lookup(mock_get, _sprint_fixture(state="2")),
            _mock_open_stories(mock_get, count=0),
        ]
        mock_patch.return_value = _mock_patch_ok()

        result = close_sprint(config, auth, CloseSprintParams(sprint_id="sprint_001"))

        self.assertTrue(result["success"])
        self.assertEqual(result["previous_state"], "2")
        self.assertEqual(result["new_state"], "3")
        self.assertEqual(result["open_stories_carried_over"], 0)

    @patch("requests.patch")
    @patch("requests.get")
    def test_blocked_by_open_stories_without_force(self, mock_get, mock_patch):
        config = _make_config()
        auth = _make_auth()

        mock_get.side_effect = [
            _mock_sprint_lookup(mock_get, _sprint_fixture(state="2")),
            _mock_open_stories(mock_get, count=4),
        ]

        result = close_sprint(config, auth, CloseSprintParams(sprint_id="sprint_001", force=False))

        self.assertFalse(result["success"])
        self.assertEqual(result["error_code"], "OPEN_STORIES_BLOCKING_CLOSE")
        self.assertEqual(result["open_stories_count"], 4)
        mock_patch.assert_not_called()

    @patch("requests.patch")
    @patch("requests.get")
    def test_force_closes_with_open_stories(self, mock_get, mock_patch):
        config = _make_config()
        auth = _make_auth()

        mock_get.side_effect = [
            _mock_sprint_lookup(mock_get, _sprint_fixture(state="2")),
            _mock_open_stories(mock_get, count=2),
        ]
        mock_patch.return_value = _mock_patch_ok()

        result = close_sprint(config, auth, CloseSprintParams(sprint_id="sprint_001", force=True))

        self.assertTrue(result["success"])
        self.assertEqual(result["open_stories_carried_over"], 2)
        mock_patch.assert_called_once()

    @patch("requests.patch")
    @patch("requests.get")
    def test_invalid_transition_from_planning(self, mock_get, mock_patch):
        """Cannot close a sprint that is still in Planning."""
        config = _make_config()
        auth = _make_auth()

        mock_get.return_value = _mock_sprint_lookup(mock_get, _sprint_fixture(state="1"))

        result = close_sprint(config, auth, CloseSprintParams(sprint_id="sprint_001"))

        self.assertFalse(result["success"])
        self.assertEqual(result["error_code"], "INVALID_TRANSITION")
        mock_patch.assert_not_called()

    @patch("requests.patch")
    @patch("requests.get")
    def test_invalid_transition_from_completed(self, mock_get, mock_patch):
        config = _make_config()
        auth = _make_auth()

        mock_get.return_value = _mock_sprint_lookup(mock_get, _sprint_fixture(state="3"))

        result = close_sprint(config, auth, CloseSprintParams(sprint_id="sprint_001"))

        self.assertFalse(result["success"])
        self.assertEqual(result["error_code"], "INVALID_TRANSITION")

    @patch("requests.patch")
    @patch("requests.get")
    def test_sprint_not_found(self, mock_get, mock_patch):
        not_found = MagicMock()
        not_found.status_code = 404

        empty = MagicMock()
        empty.status_code = 200
        empty.raise_for_status = MagicMock()
        empty.json.return_value = {"result": []}

        mock_get.side_effect = [not_found, empty]

        result = close_sprint(_make_config(), _make_auth(), CloseSprintParams(sprint_id="bad_id"))

        self.assertFalse(result["success"])
        self.assertEqual(result["error_code"], "SPRINT_NOT_FOUND")

    @patch("requests.patch")
    @patch("requests.get")
    def test_patches_correct_state(self, mock_get, mock_patch):
        """Verify the PATCH body sets state='3' (Completed)."""
        config = _make_config()
        auth = _make_auth()

        mock_get.side_effect = [
            _mock_sprint_lookup(mock_get, _sprint_fixture(state="2")),
            _mock_open_stories(mock_get, count=0),
        ]
        mock_patch.return_value = _mock_patch_ok()

        close_sprint(config, auth, CloseSprintParams(sprint_id="sprint_001"))

        patched_body = mock_patch.call_args.kwargs.get("json") or mock_patch.call_args[1].get("json", {})
        self.assertEqual(patched_body.get("state"), "3")


if __name__ == "__main__":
    unittest.main()
