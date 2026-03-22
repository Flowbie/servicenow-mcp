"""
Tests for release tools: get_release, validate_release_readiness, compile_release_notes.
"""

import unittest
from unittest.mock import MagicMock, patch

import requests

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.release_tools import (
    GetReleaseParams,
    ValidateReleaseReadinessParams,
    CompileReleaseNotesParams,
    get_release,
    validate_release_readiness,
    compile_release_notes,
    _fetch_release_stories,
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


def _release_fixture(sys_id="rel_001", name="v2.4.0", state="1"):
    return {
        "sys_id": sys_id,
        "number": "REL0001234",
        "name": name,
        "state": state,
        "planned_date": "2026-04-01",
        "description": "Q2 release",
    }


def _sprint_fixture(sys_id="sprint_001", state="3"):
    return {"sys_id": sys_id, "state": state, "name": "Sprint 14"}


def _story_fixture(sys_id="story_001", state="3", points=5, epic=None, ac="Given X"):
    return {
        "sys_id": sys_id,
        "number": "STRY0001",
        "short_description": "Test story",
        "state": state,
        "story_points": str(points),
        "acceptance_criteria": ac,
        "epic": epic or {"value": "epic_001", "display_value": "Auth Epic"},
    }


def _ok_response(result):
    resp = MagicMock()
    resp.status_code = 200
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {"result": result}
    return resp


def _not_found_response():
    resp = MagicMock()
    resp.status_code = 404
    resp.json.return_value = {}
    return resp



# ---------------------------------------------------------------------------
# get_release
# ---------------------------------------------------------------------------


class TestGetRelease(unittest.TestCase):

    @patch("requests.get")
    def test_success_by_sys_id(self, mock_get):
        mock_get.return_value = _ok_response(_release_fixture())

        result = get_release(_make_config(), _make_auth(), GetReleaseParams(release_id="rel_001"))

        self.assertTrue(result["success"])
        self.assertEqual(result["release"]["sys_id"], "rel_001")

    @patch("requests.get")
    def test_fallback_to_number_query(self, mock_get):
        not_found = _not_found_response()
        found = _ok_response([_release_fixture()])
        mock_get.side_effect = [not_found, found]

        result = get_release(
            _make_config(), _make_auth(), GetReleaseParams(release_id="REL0001234")
        )

        self.assertTrue(result["success"])

    @patch("requests.get")
    def test_not_found_returns_error(self, mock_get):
        not_found = _not_found_response()
        empty = _ok_response([])
        mock_get.side_effect = [not_found, empty]

        result = get_release(
            _make_config(), _make_auth(), GetReleaseParams(release_id="bad_id")
        )

        self.assertFalse(result["success"])
        self.assertEqual(result["error_code"], "RELEASE_NOT_FOUND")


# ---------------------------------------------------------------------------
# validate_release_readiness
# ---------------------------------------------------------------------------


class TestValidateReleaseReadiness(unittest.TestCase):

    def _setup_mocks(self, mock_get, release=None, sprints=None, sprint_sys_ids=None, stories=None):
        """
        Set up get mocks for: release lookup, sprint fetch, story fetch.
        Stories are fetched via _fetch_release_stories which does:
          1. sprint sys_id list (for the release)
          2. story query
        """
        release = release or _release_fixture()
        sprints = sprints or [_sprint_fixture()]
        stories = stories or [_story_fixture()]
        sprint_sys_ids = sprint_sys_ids or [{"sys_id": "sprint_001"}]

        mock_get.side_effect = [
            _ok_response(release),          # release lookup (direct sys_id)
            _ok_response(sprints),          # sprint fetch for checks
            _ok_response(sprint_sys_ids),   # sprint sys_ids for _fetch_release_stories
            _ok_response(stories),          # story fetch
        ]

    @patch("requests.get")
    def test_all_checks_pass(self, mock_get):
        self._setup_mocks(mock_get)

        result = validate_release_readiness(
            _make_config(), _make_auth(), ValidateReleaseReadinessParams(release_id="rel_001")
        )

        self.assertTrue(result["success"])
        self.assertTrue(result["ready"])
        self.assertTrue(all(c["passed"] for c in result["checks"]))

    @patch("requests.get")
    def test_not_ready_when_stories_in_progress(self, mock_get):
        in_progress_story = _story_fixture(state="2", ac="Some AC")
        self._setup_mocks(
            mock_get,
            stories=[in_progress_story],
        )

        result = validate_release_readiness(
            _make_config(), _make_auth(), ValidateReleaseReadinessParams(release_id="rel_001")
        )

        self.assertTrue(result["success"])
        self.assertFalse(result["ready"])

        no_in_progress_check = next(c for c in result["checks"] if c["check"] == "no_in_progress_stories")
        self.assertFalse(no_in_progress_check["passed"])

    @patch("requests.get")
    def test_not_ready_missing_acceptance_criteria(self, mock_get):
        story_no_ac = _story_fixture(state="3", ac="")
        self._setup_mocks(mock_get, stories=[story_no_ac])

        result = validate_release_readiness(
            _make_config(), _make_auth(), ValidateReleaseReadinessParams(release_id="rel_001")
        )

        self.assertTrue(result["success"])
        self.assertFalse(result["ready"])

        ac_check = next(c for c in result["checks"] if c["check"] == "acceptance_criteria_populated")
        self.assertFalse(ac_check["passed"])

    @patch("requests.get")
    def test_not_ready_incomplete_sprint(self, mock_get):
        active_sprint = _sprint_fixture(state="2")  # Active, not completed
        self._setup_mocks(mock_get, sprints=[active_sprint])

        result = validate_release_readiness(
            _make_config(), _make_auth(), ValidateReleaseReadinessParams(release_id="rel_001")
        )

        self.assertTrue(result["success"])
        self.assertFalse(result["ready"])

        sprint_check = next(c for c in result["checks"] if c["check"] == "all_sprints_completed")
        self.assertFalse(sprint_check["passed"])

    @patch("requests.get")
    def test_release_not_found(self, mock_get):
        mock_get.side_effect = [_not_found_response(), _ok_response([])]

        result = validate_release_readiness(
            _make_config(), _make_auth(), ValidateReleaseReadinessParams(release_id="bad_id")
        )

        self.assertFalse(result["success"])
        self.assertEqual(result["error_code"], "RELEASE_NOT_FOUND")

    @patch("requests.get")
    def test_cancelled_stories_excluded_from_ac_check(self, mock_get):
        """Cancelled stories should not fail the acceptance_criteria_populated check."""
        cancelled_story = _story_fixture(state="4", ac="")
        self._setup_mocks(mock_get, stories=[cancelled_story])

        result = validate_release_readiness(
            _make_config(), _make_auth(), ValidateReleaseReadinessParams(release_id="rel_001")
        )

        ac_check = next(c for c in result["checks"] if c["check"] == "acceptance_criteria_populated")
        self.assertTrue(ac_check["passed"])


# ---------------------------------------------------------------------------
# compile_release_notes
# ---------------------------------------------------------------------------


class TestCompileReleaseNotes(unittest.TestCase):

    @patch("requests.get")
    def test_success_groups_by_epic(self, mock_get):
        stories = [
            _story_fixture(sys_id="s1", state="3", points=5, epic={"value": "e1", "display_value": "Epic A"}),
            _story_fixture(sys_id="s2", state="3", points=3, epic={"value": "e1", "display_value": "Epic A"}),
            _story_fixture(sys_id="s3", state="3", points=8, epic={"value": "e2", "display_value": "Epic B"}),
        ]
        mock_get.side_effect = [
            _ok_response(_release_fixture()),       # release lookup
            _ok_response([{"sys_id": "sprint_001"}]),  # sprint sys_ids for _fetch_release_stories
            _ok_response(stories),                  # stories
        ]

        result = compile_release_notes(
            _make_config(), _make_auth(), CompileReleaseNotesParams(release_id="rel_001")
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["story_count"], 3)
        self.assertEqual(result["total_points"], 16)
        self.assertEqual(len(result["stories_by_epic"]), 2)

    @patch("requests.get")
    def test_only_done_stories_included(self, mock_get):
        stories = [
            _story_fixture(sys_id="s1", state="3", points=5),   # done
            _story_fixture(sys_id="s2", state="2", points=3),   # in progress — excluded
            _story_fixture(sys_id="s3", state="4", points=8),   # cancelled — excluded
        ]
        mock_get.side_effect = [
            _ok_response(_release_fixture()),
            _ok_response([{"sys_id": "sprint_001"}]),
            _ok_response(stories),
        ]

        result = compile_release_notes(
            _make_config(), _make_auth(), CompileReleaseNotesParams(release_id="rel_001")
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["story_count"], 1)
        self.assertEqual(result["total_points"], 5)

    @patch("requests.get")
    def test_no_done_stories_returns_empty(self, mock_get):
        mock_get.side_effect = [
            _ok_response(_release_fixture()),
            _ok_response([{"sys_id": "sprint_001"}]),
            _ok_response([]),
        ]

        result = compile_release_notes(
            _make_config(), _make_auth(), CompileReleaseNotesParams(release_id="rel_001")
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["story_count"], 0)
        self.assertEqual(result["stories_by_epic"], [])

    @patch("requests.get")
    def test_release_not_found(self, mock_get):
        mock_get.side_effect = [_not_found_response(), _ok_response([])]

        result = compile_release_notes(
            _make_config(), _make_auth(), CompileReleaseNotesParams(release_id="bad_id")
        )

        self.assertFalse(result["success"])
        self.assertEqual(result["error_code"], "RELEASE_NOT_FOUND")

    @patch("requests.get")
    def test_release_info_included(self, mock_get):
        mock_get.side_effect = [
            _ok_response(_release_fixture(name="v2.4.0")),
            _ok_response([{"sys_id": "sprint_001"}]),
            _ok_response([_story_fixture(state="3", points=5)]),
        ]

        result = compile_release_notes(
            _make_config(), _make_auth(), CompileReleaseNotesParams(release_id="rel_001")
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["release"]["name"], "v2.4.0")
        self.assertIn("planned_date", result["release"])


if __name__ == "__main__":
    unittest.main()
