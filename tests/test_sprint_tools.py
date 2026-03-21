"""
Tests for Phase 1 sprint tools: create_sprint, get_sprint, get_sprint_summary.
"""

import unittest
from unittest.mock import MagicMock, call, patch

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.sprint_tools import (
    CreateSprintParams,
    GetSprintParams,
    GetSprintSummaryParams,
    create_sprint,
    get_sprint,
    get_sprint_summary,
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


def _sprint_fixture(state="1", sys_id="sprint_sys_id_001", name="Sprint 14"):
    return {
        "sys_id": sys_id,
        "number": "SPRINT0001234",
        "name": name,
        "state": state,
        "start_date": "2026-03-01",
        "end_date": "2026-03-14",
        "goal": "Ship the login flow",
        "release": {"value": "rel_001"},
    }


def _story_fixture(state, story_points=5):
    return {
        "sys_id": "story_001",
        "number": "STRY0001234",
        "short_description": "Test story",
        "state": state,
        "story_points": str(story_points),
    }


# ---------------------------------------------------------------------------
# create_sprint
# ---------------------------------------------------------------------------

class TestCreateSprint(unittest.TestCase):

    @patch("requests.post")
    def test_success(self, mock_post):
        config = _make_config()
        auth = _make_auth()

        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"result": _sprint_fixture()}
        mock_post.return_value = mock_response

        params = CreateSprintParams(
            name="Sprint 14",
            start_date="2026-03-01",
            end_date="2026-03-14",
            release_id="rel_001",
            goal="Ship the login flow",
        )
        result = create_sprint(config, auth, params)

        self.assertTrue(result["success"])
        self.assertEqual(result["sprint_id"], "sprint_sys_id_001")
        self.assertEqual(result["state"], "1")
        self.assertEqual(result["state_label"], "Planning")

    @patch("requests.post")
    def test_end_before_start_rejected(self, mock_post):
        config = _make_config()
        auth = _make_auth()

        params = CreateSprintParams(
            name="Bad Sprint",
            start_date="2026-03-14",
            end_date="2026-03-01",
        )
        result = create_sprint(config, auth, params)

        self.assertFalse(result["success"])
        self.assertEqual(result["error_code"], "INVALID_DATE_RANGE")
        mock_post.assert_not_called()

    @patch("requests.post")
    def test_same_start_and_end_rejected(self, mock_post):
        params = CreateSprintParams(
            name="Bad Sprint",
            start_date="2026-03-01",
            end_date="2026-03-01",
        )
        result = create_sprint(_make_config(), _make_auth(), params)

        self.assertFalse(result["success"])
        self.assertEqual(result["error_code"], "INVALID_DATE_RANGE")
        mock_post.assert_not_called()

    def test_invalid_date_format_rejected(self):
        params = CreateSprintParams(
            name="Bad Sprint",
            start_date="01-03-2026",  # wrong format
            end_date="14-03-2026",
        )
        result = create_sprint(_make_config(), _make_auth(), params)

        self.assertFalse(result["success"])
        self.assertEqual(result["error_code"], "INVALID_DATE_FORMAT")

    @patch("requests.post")
    def test_optional_fields_omitted(self, mock_post):
        """Sprint can be created with just name and dates."""
        config = _make_config()
        auth = _make_auth()

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"result": _sprint_fixture()}
        mock_post.return_value = mock_response

        params = CreateSprintParams(name="Minimal Sprint", start_date="2026-03-01", end_date="2026-03-14")
        result = create_sprint(config, auth, params)

        self.assertTrue(result["success"])

        # Confirm release/goal not included in posted payload
        posted_data = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json", {})
        self.assertNotIn("release", posted_data)
        self.assertNotIn("goal", posted_data)


# ---------------------------------------------------------------------------
# get_sprint
# ---------------------------------------------------------------------------

class TestGetSprint(unittest.TestCase):

    @patch("requests.get")
    def test_success_by_sys_id(self, mock_get):
        config = _make_config()
        auth = _make_auth()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": _sprint_fixture()}
        mock_get.return_value = mock_response

        result = get_sprint(config, auth, GetSprintParams(sprint_id="sprint_sys_id_001"))

        self.assertTrue(result["success"])
        self.assertEqual(result["sprint"]["sys_id"], "sprint_sys_id_001")

    @patch("requests.get")
    def test_fallback_to_number_query(self, mock_get):
        """When direct lookup returns 404, query by number/name."""
        config = _make_config()
        auth = _make_auth()

        not_found = MagicMock()
        not_found.status_code = 404
        not_found.json.return_value = {}

        found = MagicMock()
        found.status_code = 200
        found.raise_for_status = MagicMock()
        found.json.return_value = {"result": [_sprint_fixture()]}

        mock_get.side_effect = [not_found, found]

        result = get_sprint(config, auth, GetSprintParams(sprint_id="SPRINT0001234"))

        self.assertTrue(result["success"])
        self.assertEqual(result["sprint"]["number"], "SPRINT0001234")

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

        result = get_sprint(config, auth, GetSprintParams(sprint_id="nonexistent"))

        self.assertFalse(result["success"])
        self.assertEqual(result["error_code"], "SPRINT_NOT_FOUND")

    @patch("requests.get")
    def test_found_by_name(self, mock_get):
        """Query by name falls through the same path as number."""
        config = _make_config()
        auth = _make_auth()

        not_found = MagicMock()
        not_found.status_code = 404

        found = MagicMock()
        found.status_code = 200
        found.raise_for_status = MagicMock()
        found.json.return_value = {"result": [_sprint_fixture(name="Sprint 14")]}

        mock_get.side_effect = [not_found, found]

        result = get_sprint(config, auth, GetSprintParams(sprint_id="Sprint 14"))

        self.assertTrue(result["success"])
        self.assertEqual(result["sprint"]["name"], "Sprint 14")


# ---------------------------------------------------------------------------
# get_sprint_summary
# ---------------------------------------------------------------------------

class TestGetSprintSummary(unittest.TestCase):

    def _mock_sprint_get(self, mock_get, sprint=None, stories=None, sprint_status=200):
        """Configure mock_get for: [sprint lookup, story query]."""
        sprint_record = sprint or _sprint_fixture()
        story_list = stories or []

        sprint_resp = MagicMock()
        sprint_resp.status_code = sprint_status
        sprint_resp.json.return_value = {"result": sprint_record}

        story_resp = MagicMock()
        story_resp.status_code = 200
        story_resp.raise_for_status = MagicMock()
        story_resp.json.return_value = {"result": story_list}

        mock_get.side_effect = [sprint_resp, story_resp]

    @patch("requests.get")
    def test_empty_sprint(self, mock_get):
        config = _make_config()
        auth = _make_auth()
        self._mock_sprint_get(mock_get, stories=[])

        result = get_sprint_summary(
            config, auth, GetSprintSummaryParams(sprint_id="sprint_sys_id_001")
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["story_counts"]["total"], 0)
        self.assertEqual(result["points"]["total"], 0)
        self.assertEqual(result["completion_forecast"], "no_stories")

    @patch("requests.get")
    def test_counts_and_points(self, mock_get):
        config = _make_config()
        auth = _make_auth()

        stories = [
            _story_fixture("3", story_points=5),   # done
            _story_fixture("3", story_points=3),   # done
            _story_fixture("2", story_points=8),   # in_progress
            _story_fixture("-7", story_points=5),  # in_progress (ready for testing)
            _story_fixture("1", story_points=5),   # backlog
            _story_fixture("4", story_points=2),   # cancelled
        ]
        self._mock_sprint_get(mock_get, stories=stories)

        result = get_sprint_summary(
            config, auth, GetSprintSummaryParams(sprint_id="sprint_sys_id_001")
        )

        self.assertTrue(result["success"])
        counts = result["story_counts"]
        self.assertEqual(counts["total"], 6)
        self.assertEqual(counts["done"], 2)
        self.assertEqual(counts["in_progress"], 2)
        self.assertEqual(counts["backlog"], 1)
        self.assertEqual(counts["cancelled"], 1)

        pts = result["points"]
        self.assertEqual(pts["total"], 28)
        self.assertEqual(pts["completed"], 8)    # 5 + 3
        self.assertEqual(pts["remaining"], 18)   # 8 + 5 + 5 (cancelled excluded)

    @patch("requests.get")
    def test_forecast_complete(self, mock_get):
        config = _make_config()
        auth = _make_auth()

        stories = [_story_fixture("3", 5), _story_fixture("3", 3)]
        self._mock_sprint_get(mock_get, stories=stories)

        result = get_sprint_summary(
            config, auth, GetSprintSummaryParams(sprint_id="sprint_sys_id_001")
        )

        self.assertEqual(result["completion_forecast"], "complete")

    @patch("requests.get")
    def test_forecast_at_risk_when_backlog_remaining(self, mock_get):
        config = _make_config()
        auth = _make_auth()

        stories = [_story_fixture("3", 5), _story_fixture("1", 5)]  # 1 done, 1 still in backlog
        self._mock_sprint_get(mock_get, stories=stories)

        result = get_sprint_summary(
            config, auth, GetSprintSummaryParams(sprint_id="sprint_sys_id_001")
        )

        self.assertEqual(result["completion_forecast"], "at_risk")

    @patch("requests.get")
    def test_include_stories_false_by_default(self, mock_get):
        config = _make_config()
        auth = _make_auth()
        self._mock_sprint_get(mock_get, stories=[_story_fixture("2", 5)])

        result = get_sprint_summary(
            config, auth, GetSprintSummaryParams(sprint_id="sprint_sys_id_001")
        )

        self.assertNotIn("stories", result)

    @patch("requests.get")
    def test_include_stories_true(self, mock_get):
        config = _make_config()
        auth = _make_auth()
        stories = [_story_fixture("2", 5), _story_fixture("3", 3)]
        self._mock_sprint_get(mock_get, stories=stories)

        result = get_sprint_summary(
            config,
            auth,
            GetSprintSummaryParams(sprint_id="sprint_sys_id_001", include_stories=True),
        )

        self.assertIn("stories", result)
        self.assertEqual(len(result["stories"]), 2)

    @patch("requests.get")
    def test_sprint_not_found_propagates(self, mock_get):
        """If get_sprint fails, get_sprint_summary should propagate the error."""
        config = _make_config()
        auth = _make_auth()

        not_found = MagicMock()
        not_found.status_code = 404

        empty = MagicMock()
        empty.status_code = 200
        empty.raise_for_status = MagicMock()
        empty.json.return_value = {"result": []}

        mock_get.side_effect = [not_found, empty]

        result = get_sprint_summary(
            config, auth, GetSprintSummaryParams(sprint_id="nonexistent")
        )

        self.assertFalse(result["success"])
        self.assertEqual(result["error_code"], "SPRINT_NOT_FOUND")

    @patch("requests.get")
    def test_story_points_none_treated_as_zero(self, mock_get):
        """Stories with null story_points should not raise errors."""
        config = _make_config()
        auth = _make_auth()

        stories = [
            {"sys_id": "s1", "number": "STRY1", "state": "3", "story_points": None},
            {"sys_id": "s2", "number": "STRY2", "state": "2", "story_points": ""},
        ]
        self._mock_sprint_get(mock_get, stories=stories)

        result = get_sprint_summary(
            config, auth, GetSprintSummaryParams(sprint_id="sprint_sys_id_001")
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["points"]["total"], 0)


# ---------------------------------------------------------------------------
# list_sprints
# ---------------------------------------------------------------------------

from servicenow_mcp.tools.sprint_tools import ListSprintsParams, list_sprints


class TestListSprints(unittest.TestCase):

    @patch("requests.get")
    def test_returns_sprints(self, mock_get):
        config = _make_config()
        auth = _make_auth()
        sprints = [_sprint_fixture(state="2"), _sprint_fixture(state="1", sys_id="s2", name="Sprint 13")]

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"result": sprints}
        mock_get.return_value = mock_response

        result = list_sprints(config, auth, ListSprintsParams())

        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 2)
        self.assertEqual(len(result["sprints"]), 2)

    @patch("requests.get")
    def test_empty_list(self, mock_get):
        config = _make_config()
        auth = _make_auth()

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"result": []}
        mock_get.return_value = mock_response

        result = list_sprints(config, auth, ListSprintsParams())

        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 0)
        self.assertEqual(result["sprints"], [])

    @patch("requests.get")
    def test_state_filter_passed_in_query(self, mock_get):
        config = _make_config()
        auth = _make_auth()

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"result": [_sprint_fixture(state="2")]}
        mock_get.return_value = mock_response

        result = list_sprints(config, auth, ListSprintsParams(state="2"))

        self.assertTrue(result["success"])
        call_kwargs = mock_get.call_args
        query = call_kwargs[1]["params"]["sysparm_query"]
        self.assertIn("state=2", query)

    @patch("requests.get")
    def test_release_filter_passed_in_query(self, mock_get):
        config = _make_config()
        auth = _make_auth()

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"result": []}
        mock_get.return_value = mock_response

        result = list_sprints(config, auth, ListSprintsParams(release_id="rel_001"))

        self.assertTrue(result["success"])
        call_kwargs = mock_get.call_args
        query = call_kwargs[1]["params"]["sysparm_query"]
        self.assertIn("release=rel_001", query)

    @patch("requests.get")
    def test_limit_passed_to_api(self, mock_get):
        config = _make_config()
        auth = _make_auth()

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"result": []}
        mock_get.return_value = mock_response

        list_sprints(config, auth, ListSprintsParams(limit=5))

        call_kwargs = mock_get.call_args
        self.assertEqual(call_kwargs[1]["params"]["sysparm_limit"], 5)

    @patch("requests.get")
    def test_request_error_returns_failure(self, mock_get):
        import requests as req
        config = _make_config()
        auth = _make_auth()
        mock_get.side_effect = req.RequestException("connection refused")

        result = list_sprints(config, auth, ListSprintsParams())

        self.assertFalse(result["success"])
        self.assertIn("message", result)


if __name__ == "__main__":
    unittest.main()
