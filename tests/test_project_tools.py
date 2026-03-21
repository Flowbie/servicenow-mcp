"""
Tests for project tools: create_project, update_project, list_projects, get_project.
"""

import unittest
from unittest.mock import MagicMock, patch

import requests

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.project_tools import (
    CreateProjectParams,
    UpdateProjectParams,
    ListProjectsParams,
    GetProjectParams,
    create_project,
    update_project,
    list_projects,
    get_project,
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


def _project_fixture(sys_id="proj_001", name="Test Project", state="1"):
    return {
        "sys_id": sys_id,
        "number": "PRJ0001234",
        "short_description": name,
        "state": state,
        "status": "green",
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
    resp.raise_for_status.side_effect = requests.exceptions.HTTPError("404")
    resp.json.return_value = {}
    return resp


# ---------------------------------------------------------------------------
# get_project
# ---------------------------------------------------------------------------


class TestGetProject(unittest.TestCase):

    @patch("requests.get")
    def test_success_by_sys_id(self, mock_get):
        """Direct sys_id lookup succeeds and returns project."""
        mock_get.return_value = _ok_response(_project_fixture())

        result = get_project(_make_config(), _make_auth(), GetProjectParams(project_id="proj_001"))

        self.assertTrue(result["success"])
        self.assertIn("project", result)
        self.assertEqual(result["project"]["sys_id"], "proj_001")

    @patch("requests.get")
    def test_fallback_to_number_query(self, mock_get):
        """Falls back to number query when sys_id lookup returns 404."""
        not_found = _not_found_response()
        not_found.raise_for_status = MagicMock()  # don't raise on the direct lookup path
        not_found.json.return_value = {"result": {}}  # empty result triggers fallback
        found = _ok_response([_project_fixture()])
        mock_get.side_effect = [not_found, found]

        result = get_project(
            _make_config(), _make_auth(), GetProjectParams(project_id="PRJ0001234")
        )

        self.assertTrue(result["success"])
        self.assertIn("project", result)

    @patch("requests.get")
    def test_not_found_returns_error(self, mock_get):
        """Returns PROJECT_NOT_FOUND when neither lookup finds a record."""
        empty_direct = _ok_response({})
        empty_list = _ok_response([])
        mock_get.side_effect = [empty_direct, empty_list]

        result = get_project(
            _make_config(), _make_auth(), GetProjectParams(project_id="nonexistent_000")
        )

        self.assertFalse(result["success"])
        self.assertEqual(result["error_code"], "PROJECT_NOT_FOUND")
        self.assertIn("message", result)

    @patch("requests.get")
    def test_network_error_in_fallback(self, mock_get):
        """Network error in fallback query returns PROJECT_NOT_FOUND."""
        empty_direct = _ok_response({})
        mock_get.side_effect = [
            empty_direct,
            requests.exceptions.RequestException("timeout"),
        ]

        result = get_project(
            _make_config(), _make_auth(), GetProjectParams(project_id="proj_bad")
        )

        self.assertFalse(result["success"])
        self.assertEqual(result["error_code"], "PROJECT_NOT_FOUND")


# ---------------------------------------------------------------------------
# list_projects
# ---------------------------------------------------------------------------


class TestListProjects(unittest.TestCase):

    @patch("requests.get")
    def test_returns_projects(self, mock_get):
        """Returns success with list of projects."""
        mock_get.return_value = _ok_response([_project_fixture("p1"), _project_fixture("p2")])

        result = list_projects(_make_config(), _make_auth(), ListProjectsParams())

        self.assertTrue(result["success"])
        self.assertEqual(len(result["projects"]), 2)

    @patch("requests.get")
    def test_empty_list(self, mock_get):
        """Returns success with empty list when no projects exist."""
        mock_get.return_value = _ok_response([])

        result = list_projects(_make_config(), _make_auth(), ListProjectsParams())

        self.assertTrue(result["success"])
        self.assertEqual(result["projects"], [])
        self.assertEqual(result["count"], 0)

    @patch("requests.get")
    def test_state_filter_in_query(self, mock_get):
        """State filter is included in sysparm_query."""
        mock_get.return_value = _ok_response([])

        list_projects(_make_config(), _make_auth(), ListProjectsParams(state="1"))

        call_params = (
            mock_get.call_args.kwargs.get("params")
            or mock_get.call_args[1].get("params", {})
        )
        self.assertIn("state=1", call_params["sysparm_query"])

    @patch("requests.get")
    def test_http_error_returns_failure(self, mock_get):
        """Network error returns success=False."""
        mock_get.side_effect = requests.exceptions.RequestException("connection refused")

        result = list_projects(_make_config(), _make_auth(), ListProjectsParams())

        self.assertFalse(result["success"])
        self.assertIn("message", result)
