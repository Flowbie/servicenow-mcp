"""
Tests for agile planning tools:
    story_breakdown, generate_acceptance_criteria, estimate_story_points,
    identify_story_risks, generate_test_scenarios.
"""

import unittest
from unittest.mock import MagicMock, patch

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.agile_constants import StoryIdParams
from servicenow_mcp.tools.agile_planning_tools import (
    story_breakdown,
    generate_acceptance_criteria,
    estimate_story_points,
    identify_story_risks,
    generate_test_scenarios,
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


def _story_fixture(sys_id="story_001", epic_sys_id="epic_001"):
    return {
        "sys_id": sys_id,
        "number": "STRY0001234",
        "short_description": "Implement login page",
        "state": "1",
        "story_points": "5",
        "acceptance_criteria": "Given user is on login page, when...",
        "description": "Full description here",
        "epic": {"value": epic_sys_id, "display_value": "Auth Epic"},
    }


def _epic_fixture(sys_id="epic_001"):
    return {
        "sys_id": sys_id,
        "number": "EPIC0001",
        "short_description": "Authentication",
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
# story_breakdown
# ---------------------------------------------------------------------------


class TestStoryBreakdown(unittest.TestCase):

    @patch("requests.get")
    def test_success_with_epic(self, mock_get):
        mock_get.side_effect = [
            _ok_response(_story_fixture()),      # story lookup
            _ok_response(_epic_fixture()),       # epic lookup
            _ok_response([]),                    # existing tasks
            _ok_response([]),                    # similar stories
        ]
        result = story_breakdown(_make_config(), _make_auth(), StoryIdParams(story_id="story_001"))

        self.assertTrue(result["success"])
        self.assertIn("story", result)
        self.assertIn("epic", result)
        self.assertIn("existing_tasks", result)
        self.assertIn("similar_stories", result)
        self.assertIn("task_type_guide", result)
        self.assertIn("analysis_hints", result)
        self.assertIsInstance(result["analysis_hints"], list)
        self.assertGreater(len(result["analysis_hints"]), 0)

    @patch("requests.get")
    def test_story_not_found(self, mock_get):
        mock_get.return_value = _not_found_response()

        result = story_breakdown(_make_config(), _make_auth(), StoryIdParams(story_id="bad_id"))

        self.assertFalse(result["success"])
        self.assertEqual(result["error_code"], "STORY_NOT_FOUND")

    @patch("requests.get")
    def test_no_epic_skips_similar_stories(self, mock_get):
        story = _story_fixture()
        story["epic"] = None

        mock_get.side_effect = [
            _ok_response(story),   # story lookup
            _ok_response([]),      # tasks (no epic lookup, no similar stories)
        ]
        result = story_breakdown(_make_config(), _make_auth(), StoryIdParams(story_id="story_001"))

        self.assertTrue(result["success"])
        self.assertIsNone(result["epic"])
        self.assertEqual(result["similar_stories"], [])

    @patch("requests.get")
    def test_task_type_guide_has_expected_keys(self, mock_get):
        mock_get.side_effect = [
            _ok_response(_story_fixture()),
            _ok_response(_epic_fixture()),
            _ok_response([]),
            _ok_response([]),
        ]
        result = story_breakdown(_make_config(), _make_auth(), StoryIdParams(story_id="story_001"))

        guide = result["task_type_guide"]
        self.assertIn("1", guide)  # development
        self.assertIn("4", guide)  # testing


# ---------------------------------------------------------------------------
# generate_acceptance_criteria
# ---------------------------------------------------------------------------


class TestGenerateAcceptanceCriteria(unittest.TestCase):

    @patch("requests.get")
    def test_success_with_similar_ac(self, mock_get):
        similar = [
            {
                "number": "STRY002",
                "short_description": "Another story",
                "acceptance_criteria": "Given X, When Y, Then Z",
                "sys_id": "story_002",
                "state": "3",
                "story_points": "3",
                "description": "",
            }
        ]
        mock_get.side_effect = [
            _ok_response(_story_fixture()),
            _ok_response(_epic_fixture()),
            _ok_response(similar),
        ]
        result = generate_acceptance_criteria(
            _make_config(), _make_auth(), StoryIdParams(story_id="story_001")
        )

        self.assertTrue(result["success"])
        self.assertIn("existing_acceptance_criteria", result)
        self.assertIn("similar_stories_ac", result)
        self.assertIn("ac_format_hint", result)
        self.assertEqual(len(result["similar_stories_ac"]), 1)

    @patch("requests.get")
    def test_similar_without_ac_filtered_out(self, mock_get):
        similar = [
            {
                "number": "STRY002",
                "short_description": "No AC story",
                "acceptance_criteria": "",
                "sys_id": "story_002",
                "state": "1",
                "story_points": "2",
                "description": "",
            }
        ]
        mock_get.side_effect = [
            _ok_response(_story_fixture()),
            _ok_response(_epic_fixture()),
            _ok_response(similar),
        ]
        result = generate_acceptance_criteria(
            _make_config(), _make_auth(), StoryIdParams(story_id="story_001")
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["similar_stories_ac"], [])

    @patch("requests.get")
    def test_story_not_found(self, mock_get):
        mock_get.return_value = _not_found_response()

        result = generate_acceptance_criteria(
            _make_config(), _make_auth(), StoryIdParams(story_id="bad_id")
        )

        self.assertFalse(result["success"])
        self.assertEqual(result["error_code"], "STORY_NOT_FOUND")


# ---------------------------------------------------------------------------
# estimate_story_points
# ---------------------------------------------------------------------------


class TestEstimateStoryPoints(unittest.TestCase):

    @patch("requests.get")
    def test_success_with_calibration_stories(self, mock_get):
        similar_done = [
            {
                "number": "STRY002",
                "short_description": "Done story",
                "story_points": "8",
                "description": "Something complex",
                "sys_id": "story_002",
                "state": "3",
                "acceptance_criteria": "",
            }
        ]
        mock_get.side_effect = [
            _ok_response(_story_fixture()),
            _ok_response(_epic_fixture()),
            _ok_response([]),           # tasks
            _ok_response(similar_done), # similar done stories
        ]
        result = estimate_story_points(
            _make_config(), _make_auth(), StoryIdParams(story_id="story_001")
        )

        self.assertTrue(result["success"])
        self.assertIn("fibonacci_scale", result)
        self.assertIn("calibration_hints", result)
        self.assertIn("similar_stories_with_points", result)
        self.assertEqual(result["fibonacci_scale"][0], 1)
        self.assertEqual(len(result["similar_stories_with_points"]), 1)

    @patch("requests.get")
    def test_existing_task_count_included(self, mock_get):
        tasks = [{"sys_id": "t1"}, {"sys_id": "t2"}]
        mock_get.side_effect = [
            _ok_response(_story_fixture()),
            _ok_response(_epic_fixture()),
            _ok_response(tasks),   # tasks
            _ok_response([]),      # similar done stories
        ]
        result = estimate_story_points(
            _make_config(), _make_auth(), StoryIdParams(story_id="story_001")
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["existing_task_count"], 2)

    @patch("requests.get")
    def test_story_not_found(self, mock_get):
        mock_get.return_value = _not_found_response()

        result = estimate_story_points(
            _make_config(), _make_auth(), StoryIdParams(story_id="bad_id")
        )

        self.assertFalse(result["success"])
        self.assertEqual(result["error_code"], "STORY_NOT_FOUND")


# ---------------------------------------------------------------------------
# identify_story_risks
# ---------------------------------------------------------------------------


class TestIdentifyStoryRisks(unittest.TestCase):

    @patch("requests.get")
    def test_no_blockers(self, mock_get):
        mock_get.side_effect = [
            _ok_response(_story_fixture()),
            _ok_response([]),   # tasks
            _ok_response([]),   # dependencies
        ]
        result = identify_story_risks(
            _make_config(), _make_auth(), StoryIdParams(story_id="story_001")
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["open_blocker_count"], 0)
        self.assertEqual(result["open_blockers"], [])

    @patch("requests.get")
    def test_open_blockers_detected(self, mock_get):
        deps = [
            {
                "sys_id": "dep_001",
                "prerequisite_story": "prereq_001",
                "prerequisite_story.number": "STRY0000001",
                "prerequisite_story.short_description": "Prerequisite story",
                "prerequisite_story.state": "2",  # In Progress — not done
            }
        ]
        mock_get.side_effect = [
            _ok_response(_story_fixture()),
            _ok_response([]),   # tasks
            _ok_response(deps), # dependencies
        ]
        result = identify_story_risks(
            _make_config(), _make_auth(), StoryIdParams(story_id="story_001")
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["open_blocker_count"], 1)
        self.assertEqual(result["open_blockers"][0]["prerequisite_story_number"], "STRY0000001")

    @patch("requests.get")
    def test_done_prerequisite_not_counted_as_blocker(self, mock_get):
        deps = [
            {
                "sys_id": "dep_001",
                "prerequisite_story": "prereq_001",
                "prerequisite_story.number": "STRY0000001",
                "prerequisite_story.short_description": "Done prereq",
                "prerequisite_story.state": "3",  # Complete — not a blocker
            }
        ]
        mock_get.side_effect = [
            _ok_response(_story_fixture()),
            _ok_response([]),   # tasks
            _ok_response(deps), # dependencies
        ]
        result = identify_story_risks(
            _make_config(), _make_auth(), StoryIdParams(story_id="story_001")
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["open_blocker_count"], 0)

    @patch("requests.get")
    def test_cancelled_prerequisite_not_counted_as_blocker(self, mock_get):
        deps = [
            {
                "sys_id": "dep_001",
                "prerequisite_story": "prereq_001",
                "prerequisite_story.number": "STRY0000001",
                "prerequisite_story.short_description": "Cancelled prereq",
                "prerequisite_story.state": "4",  # Cancelled — not a blocker
            }
        ]
        mock_get.side_effect = [
            _ok_response(_story_fixture()),
            _ok_response([]),
            _ok_response(deps),
        ]
        result = identify_story_risks(
            _make_config(), _make_auth(), StoryIdParams(story_id="story_001")
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["open_blocker_count"], 0)

    @patch("requests.get")
    def test_story_not_found(self, mock_get):
        mock_get.return_value = _not_found_response()

        result = identify_story_risks(
            _make_config(), _make_auth(), StoryIdParams(story_id="bad_id")
        )

        self.assertFalse(result["success"])
        self.assertEqual(result["error_code"], "STORY_NOT_FOUND")

    @patch("requests.get")
    def test_risk_analysis_hints_present(self, mock_get):
        mock_get.side_effect = [
            _ok_response(_story_fixture()),
            _ok_response([]),
            _ok_response([]),
        ]
        result = identify_story_risks(
            _make_config(), _make_auth(), StoryIdParams(story_id="story_001")
        )

        self.assertIn("risk_analysis_hints", result)
        self.assertIsInstance(result["risk_analysis_hints"], list)
        self.assertGreater(len(result["risk_analysis_hints"]), 0)


# ---------------------------------------------------------------------------
# generate_test_scenarios
# ---------------------------------------------------------------------------


class TestGenerateTestScenarios(unittest.TestCase):

    @patch("requests.get")
    def test_success_no_existing_testing_tasks(self, mock_get):
        mock_get.side_effect = [
            _ok_response(_story_fixture()),
            _ok_response(_epic_fixture()),
            _ok_response([]),  # testing tasks
        ]
        result = generate_test_scenarios(
            _make_config(), _make_auth(), StoryIdParams(story_id="story_001")
        )

        self.assertTrue(result["success"])
        self.assertIn("story", result)
        self.assertIn("epic", result)
        self.assertIn("existing_testing_tasks", result)
        self.assertIn("test_scenario_hints", result)
        self.assertEqual(result["existing_testing_tasks"], [])

    @patch("requests.get")
    def test_existing_testing_tasks_returned(self, mock_get):
        testing_tasks = [
            {"sys_id": "t1", "short_description": "Verify login success", "type": "4"}
        ]
        mock_get.side_effect = [
            _ok_response(_story_fixture()),
            _ok_response(_epic_fixture()),
            _ok_response(testing_tasks),
        ]
        result = generate_test_scenarios(
            _make_config(), _make_auth(), StoryIdParams(story_id="story_001")
        )

        self.assertTrue(result["success"])
        self.assertEqual(len(result["existing_testing_tasks"]), 1)

    @patch("requests.get")
    def test_test_scenario_hints_has_expected_keys(self, mock_get):
        mock_get.side_effect = [
            _ok_response(_story_fixture()),
            _ok_response(_epic_fixture()),
            _ok_response([]),
        ]
        result = generate_test_scenarios(
            _make_config(), _make_auth(), StoryIdParams(story_id="story_001")
        )

        hints = result["test_scenario_hints"]
        self.assertIn("happy_path", hints)
        self.assertIn("edge_cases", hints)
        self.assertIn("error_paths", hints)
        self.assertIn("integration_points", hints)

    @patch("requests.get")
    def test_story_not_found(self, mock_get):
        mock_get.return_value = _not_found_response()

        result = generate_test_scenarios(
            _make_config(), _make_auth(), StoryIdParams(story_id="bad_id")
        )

        self.assertFalse(result["success"])
        self.assertEqual(result["error_code"], "STORY_NOT_FOUND")

    @patch("requests.get")
    def test_no_epic_still_succeeds(self, mock_get):
        story = _story_fixture()
        story["epic"] = None

        mock_get.side_effect = [
            _ok_response(story),
            _ok_response([]),  # testing tasks (no epic fetched)
        ]
        result = generate_test_scenarios(
            _make_config(), _make_auth(), StoryIdParams(story_id="story_001")
        )

        self.assertTrue(result["success"])
        self.assertIsNone(result["epic"])


if __name__ == "__main__":
    unittest.main()
