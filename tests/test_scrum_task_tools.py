"""
Tests for scrum task management tools (compound functions only).

Covers: close_scrum_task.
CRUD wrappers (create_scrum_task, update_scrum_task, list_scrum_tasks,
get_scrum_task, assign_scrum_task) have been removed from the module.
"""

import unittest
from unittest.mock import MagicMock, patch

import requests as req

from servicenow_mcp.tools.scrum_task_tools import (
    CloseScrumTaskParams,
    close_scrum_task,
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


if __name__ == "__main__":
    unittest.main()
