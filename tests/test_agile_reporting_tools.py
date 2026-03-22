"""
Tests for agile reporting tools: get_blocked_work, get_release_status.
"""

import unittest
from unittest.mock import MagicMock, patch

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.agile_reporting_tools import (
    GetBlockedWorkParams,
    GetReleaseStatusParams,
    get_blocked_work,
    get_release_status,
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


def _story_fixture(sys_id="story_001", state="1", points=5):
    return {
        "sys_id": sys_id,
        "number": "STRY0001234",
        "short_description": "Test story",
        "state": state,
        "story_points": str(points),
        "sprint": "sprint_001",
        "epic": "epic_001",
        "assigned_to": "user_001",
    }


def _release_fixture(sys_id="rel_001"):
    return {
        "sys_id": sys_id,
        "name": "v2.4.0",
        "planned_date": "2026-04-01",
    }


def _sprint_fixture(sys_id="sprint_001", state="2"):
    return {"sys_id": sys_id, "state": state, "name": "Sprint 14"}



# ---------------------------------------------------------------------------
# get_blocked_work
# ---------------------------------------------------------------------------


class TestGetBlockedWork(unittest.TestCase):

    @patch("requests.get")
    def test_no_blocked_stories(self, mock_get):
        """All prerequisites are done — no blocked stories."""
        deps = [
            {
                "sys_id": "dep_001",
                "dependent_story": "story_001",
                "dependent_story.number": "STRY001",
                "dependent_story.short_description": "Some story",
                "dependent_story.state": "1",
                "dependent_story.sprint": "sprint_001",
                "prerequisite_story": "prereq_001",
                "prerequisite_story.number": "PREREQ001",
                "prerequisite_story.short_description": "Done prereq",
                "prerequisite_story.state": "3",  # Done — not a blocker
            }
        ]
        mock_get.return_value = _ok_response(deps)

        result = get_blocked_work(_make_config(), _make_auth(), GetBlockedWorkParams())

        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 0)

    @patch("requests.get")
    def test_open_blockers_detected(self, mock_get):
        deps = [
            {
                "sys_id": "dep_001",
                "dependent_story": "story_001",
                "dependent_story.number": "STRY001",
                "dependent_story.short_description": "Blocked story",
                "dependent_story.state": "1",
                "dependent_story.sprint": "sprint_001",
                "prerequisite_story": "prereq_001",
                "prerequisite_story.number": "PREREQ001",
                "prerequisite_story.short_description": "In-progress prereq",
                "prerequisite_story.state": "2",  # In Progress — a blocker
            }
        ]
        mock_get.return_value = _ok_response(deps)

        result = get_blocked_work(_make_config(), _make_auth(), GetBlockedWorkParams())

        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["blocked_stories"][0]["story_number"], "STRY001")
        self.assertEqual(len(result["blocked_stories"][0]["blockers"]), 1)

    @patch("requests.get")
    def test_deduplicates_by_dependent_story(self, mock_get):
        """Same story blocked by two prerequisites should appear once."""
        deps = [
            {
                "sys_id": "dep_001",
                "dependent_story": "story_001",
                "dependent_story.number": "STRY001",
                "dependent_story.short_description": "Blocked story",
                "dependent_story.state": "1",
                "dependent_story.sprint": "sprint_001",
                "prerequisite_story": "prereq_001",
                "prerequisite_story.number": "PREREQ001",
                "prerequisite_story.short_description": "Prereq 1",
                "prerequisite_story.state": "2",
            },
            {
                "sys_id": "dep_002",
                "dependent_story": "story_001",
                "dependent_story.number": "STRY001",
                "dependent_story.short_description": "Blocked story",
                "dependent_story.state": "1",
                "dependent_story.sprint": "sprint_001",
                "prerequisite_story": "prereq_002",
                "prerequisite_story.number": "PREREQ002",
                "prerequisite_story.short_description": "Prereq 2",
                "prerequisite_story.state": "1",
            },
        ]
        mock_get.return_value = _ok_response(deps)

        result = get_blocked_work(_make_config(), _make_auth(), GetBlockedWorkParams())

        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 1)
        self.assertEqual(len(result["blocked_stories"][0]["blockers"]), 2)

    @patch("requests.get")
    def test_sprint_filter_applied(self, mock_get):
        """Stories in a different sprint should be excluded when sprint_id is set."""
        deps = [
            {
                "sys_id": "dep_001",
                "dependent_story": "story_001",
                "dependent_story.number": "STRY001",
                "dependent_story.short_description": "Blocked story",
                "dependent_story.state": "1",
                "dependent_story.sprint": "sprint_OTHER",  # different sprint
                "prerequisite_story": "prereq_001",
                "prerequisite_story.number": "PREREQ001",
                "prerequisite_story.short_description": "Prereq",
                "prerequisite_story.state": "2",
            }
        ]
        mock_get.return_value = _ok_response(deps)

        result = get_blocked_work(
            _make_config(), _make_auth(), GetBlockedWorkParams(sprint_id="sprint_001")
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 0)

    @patch("requests.get")
    def test_cancelled_prerequisite_not_a_blocker(self, mock_get):
        deps = [
            {
                "sys_id": "dep_001",
                "dependent_story": "story_001",
                "dependent_story.number": "STRY001",
                "dependent_story.short_description": "Story",
                "dependent_story.state": "1",
                "dependent_story.sprint": "sprint_001",
                "prerequisite_story": "prereq_001",
                "prerequisite_story.number": "PREREQ001",
                "prerequisite_story.short_description": "Cancelled prereq",
                "prerequisite_story.state": "4",  # Cancelled — not a blocker
            }
        ]
        mock_get.return_value = _ok_response(deps)

        result = get_blocked_work(_make_config(), _make_auth(), GetBlockedWorkParams())

        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 0)


# ---------------------------------------------------------------------------
# get_release_status
# ---------------------------------------------------------------------------


class TestGetReleaseStatus(unittest.TestCase):

    def _setup_mocks(self, mock_get, release=None, sprints=None, sprint_sys_ids=None, stories=None):
        release = release or _release_fixture()
        sprints = sprints or [_sprint_fixture(state="2")]
        sprint_sys_ids = sprint_sys_ids or [{"sys_id": "sprint_001"}]
        stories = stories or [_story_fixture(state="2", points=5)]

        mock_get.side_effect = [
            _ok_response(release),          # release lookup
            _ok_response(sprints),          # sprint fetch
            _ok_response(sprint_sys_ids),   # sprint sys_ids for _fetch_release_stories
            _ok_response(stories),          # stories
        ]

    @patch("requests.get")
    def test_success_returns_all_fields(self, mock_get):
        self._setup_mocks(mock_get)

        result = get_release_status(
            _make_config(), _make_auth(), GetReleaseStatusParams(release_id="rel_001")
        )

        self.assertTrue(result["success"])
        self.assertIn("release", result)
        self.assertIn("sprint_counts", result)
        self.assertIn("story_counts", result)
        self.assertIn("points", result)
        self.assertIn("overall_status", result)

    @patch("requests.get")
    def test_overall_status_complete(self, mock_get):
        self._setup_mocks(
            mock_get,
            sprints=[_sprint_fixture(state="3")],  # Completed sprint
            stories=[_story_fixture(state="3", points=5)],  # Done story
        )

        result = get_release_status(
            _make_config(), _make_auth(), GetReleaseStatusParams(release_id="rel_001")
        )

        self.assertEqual(result["overall_status"], "complete")

    @patch("requests.get")
    def test_overall_status_not_started(self, mock_get):
        self._setup_mocks(
            mock_get,
            sprints=[_sprint_fixture(state="1")],  # Planning sprint
            stories=[_story_fixture(state="1", points=5)],  # Backlog story
        )

        result = get_release_status(
            _make_config(), _make_auth(), GetReleaseStatusParams(release_id="rel_001")
        )

        self.assertEqual(result["overall_status"], "not_started")

    @patch("requests.get")
    def test_overall_status_at_risk(self, mock_get):
        self._setup_mocks(
            mock_get,
            sprints=[_sprint_fixture(state="2")],  # Active sprint
            stories=[
                _story_fixture(sys_id="s1", state="3", points=3),  # done
                _story_fixture(sys_id="s2", state="1", points=5),  # backlog — risk
            ],
        )

        result = get_release_status(
            _make_config(), _make_auth(), GetReleaseStatusParams(release_id="rel_001")
        )

        self.assertEqual(result["overall_status"], "at_risk")

    @patch("requests.get")
    def test_sprint_counts_correct(self, mock_get):
        sprints = [
            _sprint_fixture(sys_id="s1", state="3"),  # completed
            _sprint_fixture(sys_id="s2", state="2"),  # active
            _sprint_fixture(sys_id="s3", state="1"),  # planning
        ]
        self._setup_mocks(mock_get, sprints=sprints)

        result = get_release_status(
            _make_config(), _make_auth(), GetReleaseStatusParams(release_id="rel_001")
        )

        self.assertEqual(result["sprint_counts"]["total"], 3)
        self.assertEqual(result["sprint_counts"]["completed"], 1)
        self.assertEqual(result["sprint_counts"]["active"], 1)
        self.assertEqual(result["sprint_counts"]["planning"], 1)

    @patch("requests.get")
    def test_story_point_totals(self, mock_get):
        stories = [
            _story_fixture(sys_id="s1", state="3", points=5),   # done
            _story_fixture(sys_id="s2", state="2", points=8),   # in progress
            _story_fixture(sys_id="s3", state="1", points=3),   # backlog
            _story_fixture(sys_id="s4", state="4", points=2),   # cancelled
        ]
        self._setup_mocks(mock_get, stories=stories)

        result = get_release_status(
            _make_config(), _make_auth(), GetReleaseStatusParams(release_id="rel_001")
        )

        self.assertEqual(result["points"]["total"], 18)
        self.assertEqual(result["points"]["completed"], 5)
        self.assertEqual(result["points"]["remaining"], 11)  # 8 + 3 (cancelled excluded)

    @patch("requests.get")
    def test_release_not_found(self, mock_get):
        mock_get.side_effect = [_not_found_response(), _ok_response([])]

        result = get_release_status(
            _make_config(), _make_auth(), GetReleaseStatusParams(release_id="bad_id")
        )

        self.assertFalse(result["success"])
        self.assertEqual(result["error_code"], "RELEASE_NOT_FOUND")


if __name__ == "__main__":
    unittest.main()
