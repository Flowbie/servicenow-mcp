"""
Tests for scrum task management tools:
  create_scrum_task, update_scrum_task, list_scrum_tasks,
  get_scrum_task, close_scrum_task, assign_scrum_task.
"""

import unittest
from unittest.mock import MagicMock, patch, call

import requests as req
from pydantic import ValidationError

from servicenow_mcp.tools.scrum_task_tools import (
    CreateScrumTaskParams,
    create_scrum_task,
    UpdateScrumTaskParams,
    update_scrum_task,
    ListScrumTasksParams,
    list_scrum_tasks,
    GetScrumTaskParams,
    get_scrum_task,
    CloseScrumTaskParams,
    close_scrum_task,
    AssignScrumTaskParams,
    assign_scrum_task,
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
    auth = MagicMock()
    auth.get_headers.return_value = {"Authorization": "Bearer FAKE"}
    return auth


def _ok(result):
    resp = MagicMock()
    resp.status_code = 200
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {"result": result}
    return resp


def _not_found():
    resp = MagicMock()
    resp.status_code = 404
    resp.raise_for_status = MagicMock(side_effect=req.HTTPError("404"))
    resp.json.return_value = {}
    return resp


def _request_error():
    err = req.RequestException("connection error")
    err.response = None
    return err


def _task_record(
    sys_id="task_001",
    story="story_abc",
    short_description="Write unit tests",
    state="1",
    type="4",
    assigned_to="user_001",
    assignment_group="group_001",
):
    return {
        "sys_id": sys_id,
        "story": story,
        "short_description": short_description,
        "state": state,
        "type": type,
        "assigned_to": assigned_to,
        "assignment_group": assignment_group,
    }


TASK_ID = "task_abc123"
STORY_ID = "story_xyz456"


# ---------------------------------------------------------------------------
# create_scrum_task
# ---------------------------------------------------------------------------


class TestCreateScrumTask(unittest.TestCase):

    @patch("servicenow_mcp.tools.scrum_task_tools.requests.post")
    def test_create_success(self, mock_post):
        """Creates a task and returns success with scrum_task dict."""
        mock_post.return_value = _ok(_task_record())
        params = CreateScrumTaskParams(story=STORY_ID, short_description="Write unit tests")
        result = create_scrum_task(_make_config(), _make_auth(), params)
        self.assertTrue(result["success"])
        self.assertIn("scrum_task", result)
        self.assertEqual(result["scrum_task"]["sys_id"], "task_001")

    def test_create_missing_required_fields_raises_validation_error(self):
        """Omitting required fields raises a Pydantic ValidationError."""
        with self.assertRaises(ValidationError):
            CreateScrumTaskParams(short_description="No story provided")  # missing story

    @patch("servicenow_mcp.tools.scrum_task_tools.requests.post")
    def test_create_network_error(self, mock_post):
        """Network error returns success=False with message."""
        mock_post.side_effect = _request_error()
        params = CreateScrumTaskParams(story=STORY_ID, short_description="Write unit tests")
        result = create_scrum_task(_make_config(), _make_auth(), params)
        self.assertFalse(result["success"])
        self.assertIn("Error creating scrum task", result["message"])

    @patch("servicenow_mcp.tools.scrum_task_tools.requests.post")
    def test_create_with_optional_fields(self, mock_post):
        """Optional fields are included in the POST body when provided."""
        mock_post.return_value = _ok(_task_record(type="2"))
        params = CreateScrumTaskParams(
            story=STORY_ID,
            short_description="Implement feature",
            type="2",
            priority="2",
            planned_hours=8,
        )
        result = create_scrum_task(_make_config(), _make_auth(), params)
        self.assertTrue(result["success"])
        # Verify call included optional fields
        _, kwargs = mock_post.call_args
        body = kwargs["json"]
        self.assertEqual(body["type"], "2")
        self.assertEqual(body["priority"], "2")
        self.assertEqual(body["planned_hours"], 8)


# ---------------------------------------------------------------------------
# update_scrum_task
# ---------------------------------------------------------------------------


class TestUpdateScrumTask(unittest.TestCase):

    @patch("servicenow_mcp.tools.scrum_task_tools.requests.put")
    def test_update_success(self, mock_put):
        """Full update returns success with updated scrum_task."""
        updated = _task_record(state="2", short_description="Updated desc")
        mock_put.return_value = _ok(updated)
        params = UpdateScrumTaskParams(
            scrum_task_id=TASK_ID,
            short_description="Updated desc",
            state="2",
        )
        result = update_scrum_task(_make_config(), _make_auth(), params)
        self.assertTrue(result["success"])
        self.assertEqual(result["scrum_task"]["state"], "2")

    @patch("servicenow_mcp.tools.scrum_task_tools.requests.put")
    def test_update_partial_fields_only(self, mock_put):
        """Only the provided fields are sent; others remain absent from body."""
        mock_put.return_value = _ok(_task_record())
        params = UpdateScrumTaskParams(scrum_task_id=TASK_ID, priority="1")
        result = update_scrum_task(_make_config(), _make_auth(), params)
        self.assertTrue(result["success"])
        _, kwargs = mock_put.call_args
        body = kwargs["json"]
        self.assertIn("priority", body)
        self.assertNotIn("short_description", body)
        self.assertNotIn("state", body)

    @patch("servicenow_mcp.tools.scrum_task_tools.requests.put")
    def test_update_not_found(self, mock_put):
        """404 response returns success=False with not-found message."""
        mock_put.return_value = _not_found()
        params = UpdateScrumTaskParams(scrum_task_id="nonexistent", state="3")
        result = update_scrum_task(_make_config(), _make_auth(), params)
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"].lower())


# ---------------------------------------------------------------------------
# list_scrum_tasks
# ---------------------------------------------------------------------------


class TestListScrumTasks(unittest.TestCase):

    @patch("servicenow_mcp.tools.scrum_task_tools.requests.get")
    def test_list_with_story_id_filter(self, mock_get):
        """story_id filter is passed as part of sysparm_query."""
        mock_get.return_value = _ok([_task_record(), _task_record(sys_id="task_002")])
        params = ListScrumTasksParams(story_id=STORY_ID)
        result = list_scrum_tasks(_make_config(), _make_auth(), params)
        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 2)
        _, kwargs = mock_get.call_args
        query = kwargs["params"]["sysparm_query"]
        self.assertIn(f"story={STORY_ID}", query)

    @patch("servicenow_mcp.tools.scrum_task_tools.requests.get")
    def test_list_empty_results(self, mock_get):
        """Empty list from API returns success=True, count=0."""
        mock_get.return_value = _ok([])
        params = ListScrumTasksParams()
        result = list_scrum_tasks(_make_config(), _make_auth(), params)
        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 0)
        self.assertEqual(result["scrum_tasks"], [])

    @patch("servicenow_mcp.tools.scrum_task_tools.requests.get")
    def test_list_without_filters(self, mock_get):
        """No filters: succeeds and returns whatever the API returns."""
        tasks = [_task_record(sys_id=f"task_{i}") for i in range(5)]
        mock_get.return_value = _ok(tasks)
        params = ListScrumTasksParams(limit=5)
        result = list_scrum_tasks(_make_config(), _make_auth(), params)
        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 5)

    @patch("servicenow_mcp.tools.scrum_task_tools.requests.get")
    def test_list_network_error(self, mock_get):
        """Network error returns success=False."""
        mock_get.side_effect = _request_error()
        params = ListScrumTasksParams()
        result = list_scrum_tasks(_make_config(), _make_auth(), params)
        self.assertFalse(result["success"])
        self.assertIn("Error listing scrum tasks", result["message"])


# ---------------------------------------------------------------------------
# get_scrum_task
# ---------------------------------------------------------------------------


class TestGetScrumTask(unittest.TestCase):

    @patch("servicenow_mcp.tools.scrum_task_tools.requests.get")
    def test_get_success(self, mock_get):
        """Existing task is returned with success=True."""
        mock_get.return_value = _ok(_task_record())
        params = GetScrumTaskParams(scrum_task_id=TASK_ID)
        result = get_scrum_task(_make_config(), _make_auth(), params)
        self.assertTrue(result["success"])
        self.assertIn("scrum_task", result)
        self.assertEqual(result["scrum_task"]["sys_id"], "task_001")

    @patch("servicenow_mcp.tools.scrum_task_tools.requests.get")
    def test_get_not_found_404(self, mock_get):
        """404 response returns success=False, not-found message."""
        not_found_resp = MagicMock()
        not_found_resp.status_code = 404
        not_found_resp.raise_for_status = MagicMock()
        mock_get.return_value = not_found_resp
        params = GetScrumTaskParams(scrum_task_id="nonexistent")
        result = get_scrum_task(_make_config(), _make_auth(), params)
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"].lower())

    @patch("servicenow_mcp.tools.scrum_task_tools.requests.get")
    def test_get_empty_result(self, mock_get):
        """API returning null result gives success=False, not-found message."""
        resp = MagicMock()
        resp.status_code = 200
        resp.raise_for_status = MagicMock()
        resp.json.return_value = {"result": None}
        mock_get.return_value = resp
        params = GetScrumTaskParams(scrum_task_id=TASK_ID)
        result = get_scrum_task(_make_config(), _make_auth(), params)
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"].lower())

    @patch("servicenow_mcp.tools.scrum_task_tools.requests.get")
    def test_get_network_error(self, mock_get):
        """Network error returns success=False."""
        mock_get.side_effect = _request_error()
        params = GetScrumTaskParams(scrum_task_id=TASK_ID)
        result = get_scrum_task(_make_config(), _make_auth(), params)
        self.assertFalse(result["success"])
        self.assertIn("Error retrieving scrum task", result["message"])


# ---------------------------------------------------------------------------
# close_scrum_task
# ---------------------------------------------------------------------------


class TestCloseScrumTask(unittest.TestCase):

    @patch("servicenow_mcp.tools.scrum_task_tools.requests.patch")
    @patch("servicenow_mcp.tools.scrum_task_tools.requests.get")
    def test_close_success(self, mock_get, mock_patch):
        """Open task is successfully closed — state set to 3."""
        mock_get.return_value = _ok({"sys_id": TASK_ID, "state": "1"})
        mock_patch.return_value = _ok(_task_record(state="3"))
        params = CloseScrumTaskParams(scrum_task_id=TASK_ID)
        result = close_scrum_task(_make_config(), _make_auth(), params)
        self.assertTrue(result["success"])
        self.assertEqual(result["message"], "Scrum task closed")
        self.assertIn("scrum_task", result)
        # Verify PATCH body contains state=3
        _, kwargs = mock_patch.call_args
        self.assertEqual(kwargs["json"]["state"], "3")

    @patch("servicenow_mcp.tools.scrum_task_tools.requests.get")
    def test_close_already_closed_guard(self, mock_get):
        """Task already Complete (state=3): returns success=False, already-closed message."""
        mock_get.return_value = _ok({"sys_id": TASK_ID, "state": "3"})
        params = CloseScrumTaskParams(scrum_task_id=TASK_ID)
        result = close_scrum_task(_make_config(), _make_auth(), params)
        self.assertFalse(result["success"])
        self.assertIn("already closed", result["message"].lower())

    @patch("servicenow_mcp.tools.scrum_task_tools.requests.get")
    def test_close_cancelled_guard(self, mock_get):
        """Task already Cancelled (state=4): returns success=False, already-closed message."""
        mock_get.return_value = _ok({"sys_id": TASK_ID, "state": "4"})
        params = CloseScrumTaskParams(scrum_task_id=TASK_ID)
        result = close_scrum_task(_make_config(), _make_auth(), params)
        self.assertFalse(result["success"])
        self.assertIn("already closed", result["message"].lower())

    @patch("servicenow_mcp.tools.scrum_task_tools.requests.get")
    def test_close_network_error_on_get(self, mock_get):
        """Network error during the GET phase returns success=False."""
        mock_get.side_effect = _request_error()
        params = CloseScrumTaskParams(scrum_task_id=TASK_ID)
        result = close_scrum_task(_make_config(), _make_auth(), params)
        self.assertFalse(result["success"])
        self.assertIn("Error retrieving scrum task", result["message"])

    @patch("servicenow_mcp.tools.scrum_task_tools.requests.patch")
    @patch("servicenow_mcp.tools.scrum_task_tools.requests.get")
    def test_close_with_work_notes(self, mock_get, mock_patch):
        """Work notes are included in the PATCH payload when provided."""
        mock_get.return_value = _ok({"sys_id": TASK_ID, "state": "2"})
        mock_patch.return_value = _ok(_task_record(state="3"))
        params = CloseScrumTaskParams(scrum_task_id=TASK_ID, work_notes="Closing — done.")
        result = close_scrum_task(_make_config(), _make_auth(), params)
        self.assertTrue(result["success"])
        _, kwargs = mock_patch.call_args
        self.assertEqual(kwargs["json"]["work_notes"], "Closing — done.")


# ---------------------------------------------------------------------------
# assign_scrum_task
# ---------------------------------------------------------------------------


class TestAssignScrumTask(unittest.TestCase):

    @patch("servicenow_mcp.tools.scrum_task_tools.requests.put")
    def test_assign_with_both_fields(self, mock_put):
        """Assigning both user and group succeeds."""
        mock_put.return_value = _ok(_task_record(assigned_to="user_abc", assignment_group="grp_xyz"))
        params = AssignScrumTaskParams(
            scrum_task_id=TASK_ID,
            assigned_to="user_abc",
            assignment_group="grp_xyz",
        )
        result = assign_scrum_task(_make_config(), _make_auth(), params)
        self.assertTrue(result["success"])
        self.assertEqual(result["message"], "Scrum task assigned")
        self.assertIn("scrum_task", result)
        _, kwargs = mock_put.call_args
        self.assertIn("assigned_to", kwargs["json"])
        self.assertIn("assignment_group", kwargs["json"])

    @patch("servicenow_mcp.tools.scrum_task_tools.requests.put")
    def test_assign_with_only_assigned_to(self, mock_put):
        """Assigning only a user (no group) succeeds."""
        mock_put.return_value = _ok(_task_record(assigned_to="user_abc"))
        params = AssignScrumTaskParams(scrum_task_id=TASK_ID, assigned_to="user_abc")
        result = assign_scrum_task(_make_config(), _make_auth(), params)
        self.assertTrue(result["success"])
        _, kwargs = mock_put.call_args
        body = kwargs["json"]
        self.assertIn("assigned_to", body)
        self.assertNotIn("assignment_group", body)

    def test_assign_both_none_returns_error(self):
        """Providing neither assigned_to nor assignment_group returns success=False without HTTP call."""
        params = AssignScrumTaskParams(scrum_task_id=TASK_ID)
        result = assign_scrum_task(_make_config(), _make_auth(), params)
        self.assertFalse(result["success"])
        self.assertIn("At least one of", result["message"])

    @patch("servicenow_mcp.tools.scrum_task_tools.requests.put")
    def test_assign_network_error(self, mock_put):
        """Network error returns success=False."""
        mock_put.side_effect = _request_error()
        params = AssignScrumTaskParams(scrum_task_id=TASK_ID, assigned_to="user_abc")
        result = assign_scrum_task(_make_config(), _make_auth(), params)
        self.assertFalse(result["success"])
        self.assertIn("Error assigning scrum task", result["message"])

    @patch("servicenow_mcp.tools.scrum_task_tools.requests.put")
    def test_assign_with_only_group(self, mock_put):
        """Assigning only a group (no user) succeeds."""
        mock_put.return_value = _ok(_task_record(assignment_group="grp_xyz"))
        params = AssignScrumTaskParams(scrum_task_id=TASK_ID, assignment_group="grp_xyz")
        result = assign_scrum_task(_make_config(), _make_auth(), params)
        self.assertTrue(result["success"])
        _, kwargs = mock_put.call_args
        body = kwargs["json"]
        self.assertIn("assignment_group", body)
        self.assertNotIn("assigned_to", body)


if __name__ == "__main__":
    unittest.main()
