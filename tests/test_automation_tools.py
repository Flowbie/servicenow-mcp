"""
Tests for automation platform tools (sys_trigger, scheduled imports/exports).
"""

import unittest
from unittest.mock import MagicMock, patch

import requests

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.automation_tools import (
    CreateScheduledScriptParams,
    DeleteScheduledJobParams,
    DisableScheduledJobParams,
    EnableScheduledJobParams,
    GetScheduledJobParams,
    ListScheduledExportsParams,
    ListScheduledImportsParams,
    ListScheduledJobsParams,
    RunScheduledJobNowParams,
    UpdateScheduledJobParams,
    create_scheduled_script,
    delete_scheduled_job,
    disable_scheduled_job,
    enable_scheduled_job,
    get_scheduled_job,
    list_scheduled_exports,
    list_scheduled_imports,
    list_scheduled_jobs,
    run_scheduled_job_now,
    update_scheduled_job,
)
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig


class TestAutomationTools(unittest.TestCase):
    """Tests for automation platform tools."""

    def setUp(self):
        self.auth_config = AuthConfig(
            type=AuthType.BASIC,
            basic=BasicAuthConfig(username="test_user", password="test_password"),
        )
        self.config = ServerConfig(
            instance_url="https://test.service-now.com",
            auth=self.auth_config,
        )
        self.auth_manager = MagicMock(spec=AuthManager)
        self.auth_manager.get_headers.return_value = {"Authorization": "Bearer FAKE_TOKEN"}

    # --- list_scheduled_jobs ---

    @patch("servicenow_mcp.tools.automation_tools.requests.get")
    def test_list_scheduled_jobs_success(self, mock_get):
        """Test listing scheduled jobs returns results."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": [
                {"sys_id": "job1", "name": "Daily Cleanup", "trigger_type": "0", "active": "true"},
                {"sys_id": "job2", "name": "Weekly Report", "trigger_type": "1", "active": "true"},
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        params = ListScheduledJobsParams()
        result = list_scheduled_jobs(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 2)
        self.assertEqual(result["scheduled_jobs"][0]["name"], "Daily Cleanup")

    @patch("servicenow_mcp.tools.automation_tools.requests.get")
    def test_list_scheduled_jobs_with_type_filter(self, mock_get):
        """Test listing with trigger_type filter builds correct query."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": []}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        params = ListScheduledJobsParams(trigger_type="3", active=True)
        result = list_scheduled_jobs(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        call_kwargs = mock_get.call_args[1]["params"]
        self.assertIn("trigger_type=3", call_kwargs["sysparm_query"])
        self.assertIn("active=true", call_kwargs["sysparm_query"])

    @patch("servicenow_mcp.tools.automation_tools.requests.get")
    def test_list_scheduled_jobs_http_error(self, mock_get):
        """Test list_scheduled_jobs handles HTTP errors."""
        mock_get.side_effect = requests.HTTPError("500 Server Error")
        params = ListScheduledJobsParams()
        result = list_scheduled_jobs(self.config, self.auth_manager, params)
        self.assertFalse(result["success"])
        self.assertIn("HTTP error", result["message"])

    # --- get_scheduled_job ---

    @patch("servicenow_mcp.tools.automation_tools.requests.get")
    def test_get_scheduled_job_by_sys_id(self, mock_get):
        """Test getting a job by sys_id hits the record endpoint directly."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": {"sys_id": "job1", "name": "Daily Cleanup"}}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        params = GetScheduledJobParams(job_sys_id="job1")
        result = get_scheduled_job(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        self.assertEqual(result["scheduled_job"]["sys_id"], "job1")
        # Verify it hits the direct record URL
        called_url = mock_get.call_args[0][0]
        self.assertIn("job1", called_url)

    @patch("servicenow_mcp.tools.automation_tools.requests.get")
    def test_get_scheduled_job_by_name(self, mock_get):
        """Test getting a job by name uses query."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": [{"sys_id": "job2", "name": "Weekly Report"}]}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        params = GetScheduledJobParams(job_name="Weekly Report")
        result = get_scheduled_job(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        self.assertEqual(result["scheduled_job"]["name"], "Weekly Report")

    @patch("servicenow_mcp.tools.automation_tools.requests.get")
    def test_get_scheduled_job_not_found_by_name(self, mock_get):
        """Test that not-found by name returns failure."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": []}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        params = GetScheduledJobParams(job_name="Nonexistent")
        result = get_scheduled_job(self.config, self.auth_manager, params)

        self.assertFalse(result["success"])
        self.assertIn("Nonexistent", result["message"])

    def test_get_scheduled_job_requires_identifier(self):
        """Test that providing neither name nor sys_id raises validation error."""
        with self.assertRaises(Exception):
            GetScheduledJobParams()

    # --- enable_scheduled_job ---

    @patch("servicenow_mcp.tools.automation_tools.requests.patch")
    def test_enable_scheduled_job_success(self, mock_patch):
        """Test enabling a scheduled job sets active=true."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": {"sys_id": "job1", "active": "true"}}
        mock_response.raise_for_status = MagicMock()
        mock_patch.return_value = mock_response

        params = EnableScheduledJobParams(job_sys_id="job1")
        result = enable_scheduled_job(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        self.assertIn("enabled", result["message"])
        # Verify active=true was sent
        sent_data = mock_patch.call_args[1]["json"]
        self.assertEqual(sent_data["active"], "true")

    @patch("servicenow_mcp.tools.automation_tools.requests.patch")
    def test_enable_scheduled_job_http_error(self, mock_patch):
        """Test enable_scheduled_job handles HTTP errors."""
        mock_patch.side_effect = requests.HTTPError("403 Forbidden")
        params = EnableScheduledJobParams(job_sys_id="job1")
        result = enable_scheduled_job(self.config, self.auth_manager, params)
        self.assertFalse(result["success"])

    # --- disable_scheduled_job ---

    @patch("servicenow_mcp.tools.automation_tools.requests.patch")
    def test_disable_scheduled_job_sets_trigger_type(self, mock_patch):
        """Test disabling sets trigger_type=2, not active=false."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": {"sys_id": "job1", "trigger_type": "2"}}
        mock_response.raise_for_status = MagicMock()
        mock_patch.return_value = mock_response

        params = DisableScheduledJobParams(job_sys_id="job1")
        result = disable_scheduled_job(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        sent_data = mock_patch.call_args[1]["json"]
        self.assertEqual(sent_data["trigger_type"], "2")
        self.assertNotIn("active", sent_data)  # must NOT set active=false

    @patch("servicenow_mcp.tools.automation_tools.requests.patch")
    def test_disable_scheduled_job_http_error(self, mock_patch):
        """Test disable_scheduled_job handles HTTP errors."""
        mock_patch.side_effect = requests.HTTPError("500 error")
        params = DisableScheduledJobParams(job_sys_id="job1")
        result = disable_scheduled_job(self.config, self.auth_manager, params)
        self.assertFalse(result["success"])

    # --- create_scheduled_script ---

    @patch("servicenow_mcp.tools.automation_tools.requests.post")
    def test_create_scheduled_script_success(self, mock_post):
        """Test creating a scheduled script with all required fields."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": {"sys_id": "newjob1", "name": "My Script", "time_zone": "US/Eastern"}
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        params = CreateScheduledScriptParams(
            name="My Script",
            script="gs.info('hello');",
            time_zone="US/Eastern",
            trigger_type=3,
            run_period="00:30:00",
        )
        result = create_scheduled_script(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        self.assertIn("created", result["message"])
        sent_data = mock_post.call_args[1]["json"]
        self.assertEqual(sent_data["time_zone"], "US/Eastern")
        self.assertEqual(sent_data["run_period"], "00:30:00")

    def test_create_scheduled_script_invalid_run_dates(self):
        """Test that run_start >= run_end raises validation error."""
        with self.assertRaises(Exception):
            CreateScheduledScriptParams(
                name="Bad Dates",
                script="gs.info('x');",
                time_zone="UTC",
                run_start="2026-04-02 00:00:00",
                run_end="2026-04-01 00:00:00",
            )

    @patch("servicenow_mcp.tools.automation_tools.requests.post")
    def test_create_scheduled_script_http_error(self, mock_post):
        """Test create_scheduled_script handles HTTP errors."""
        mock_post.side_effect = requests.HTTPError("400 Bad Request")
        params = CreateScheduledScriptParams(
            name="My Script", script="gs.info('x');", time_zone="UTC"
        )
        result = create_scheduled_script(self.config, self.auth_manager, params)
        self.assertFalse(result["success"])

    # --- delete_scheduled_job ---

    @patch("servicenow_mcp.tools.automation_tools.requests.delete")
    @patch("servicenow_mcp.tools.automation_tools.requests.get")
    def test_delete_scheduled_job_success(self, mock_get, mock_delete):
        """Test deleting a regular job succeeds."""
        mock_get_response = MagicMock()
        mock_get_response.json.return_value = {
            "result": {"sys_id": "job1", "name": "My Job", "system_id": "node-abc"}
        }
        mock_get_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_get_response

        mock_delete_response = MagicMock()
        mock_delete_response.raise_for_status = MagicMock()
        mock_delete.return_value = mock_delete_response

        params = DeleteScheduledJobParams(job_sys_id="job1")
        result = delete_scheduled_job(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        self.assertIn("deleted", result["message"])

    @patch("servicenow_mcp.tools.automation_tools.requests.get")
    def test_delete_scheduled_job_refuses_all_nodes(self, mock_get):
        """Test that deleting a job with system_id='ALL NODES' is refused."""
        mock_get_response = MagicMock()
        mock_get_response.json.return_value = {
            "result": {"sys_id": "job1", "name": "Parent Job", "system_id": "ALL NODES"}
        }
        mock_get_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_get_response

        params = DeleteScheduledJobParams(job_sys_id="job1")
        result = delete_scheduled_job(self.config, self.auth_manager, params)

        self.assertFalse(result["success"])
        self.assertIn("ALL NODES", result["message"])

    @patch("servicenow_mcp.tools.automation_tools.requests.get")
    def test_delete_scheduled_job_refuses_active_nodes(self, mock_get):
        """Test that deleting a job with system_id='ACTIVE NODES' is refused."""
        mock_get_response = MagicMock()
        mock_get_response.json.return_value = {
            "result": {"sys_id": "job2", "name": "Active Job", "system_id": "ACTIVE NODES"}
        }
        mock_get_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_get_response

        params = DeleteScheduledJobParams(job_sys_id="job2")
        result = delete_scheduled_job(self.config, self.auth_manager, params)

        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.automation_tools.requests.get")
    def test_delete_scheduled_job_refuses_primary_nodes(self, mock_get):
        """Test that deleting a job with system_id='PRIMARY NODES' is refused."""
        mock_get_response = MagicMock()
        mock_get_response.json.return_value = {
            "result": {"sys_id": "job3", "name": "Primary Job", "system_id": "PRIMARY NODES"}
        }
        mock_get_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_get_response

        params = DeleteScheduledJobParams(job_sys_id="job3")
        result = delete_scheduled_job(self.config, self.auth_manager, params)

        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.automation_tools.requests.get")
    def test_delete_scheduled_job_http_error_on_fetch(self, mock_get):
        """Test delete_scheduled_job handles HTTP errors during pre-fetch."""
        mock_get.side_effect = requests.HTTPError("404 Not Found")
        params = DeleteScheduledJobParams(job_sys_id="missing")
        result = delete_scheduled_job(self.config, self.auth_manager, params)
        self.assertFalse(result["success"])

    # --- list_scheduled_imports ---

    @patch("servicenow_mcp.tools.automation_tools.requests.get")
    def test_list_scheduled_imports_success(self, mock_get):
        """Test listing scheduled import sets."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": [
                {"sys_id": "imp1", "name": "HR Import", "active": "true"},
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        params = ListScheduledImportsParams()
        result = list_scheduled_imports(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 1)
        called_url = mock_get.call_args[0][0]
        self.assertIn("scheduled_import_set", called_url)

    @patch("servicenow_mcp.tools.automation_tools.requests.get")
    def test_list_scheduled_imports_with_active_filter(self, mock_get):
        """Test listing imports with active=false filter."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": []}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        params = ListScheduledImportsParams(active=False)
        result = list_scheduled_imports(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        call_kwargs = mock_get.call_args[1]["params"]
        self.assertIn("active=false", call_kwargs["sysparm_query"])

    @patch("servicenow_mcp.tools.automation_tools.requests.get")
    def test_list_scheduled_imports_http_error(self, mock_get):
        """Test list_scheduled_imports handles HTTP errors."""
        mock_get.side_effect = requests.HTTPError("500 error")
        params = ListScheduledImportsParams()
        result = list_scheduled_imports(self.config, self.auth_manager, params)
        self.assertFalse(result["success"])

    # --- list_scheduled_exports ---

    @patch("servicenow_mcp.tools.automation_tools.requests.get")
    def test_list_scheduled_exports_success(self, mock_get):
        """Test listing scheduled data exports."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": [
                {"sys_id": "exp1", "name": "Nightly Export", "active": "true"},
                {"sys_id": "exp2", "name": "Weekly Export", "active": "true"},
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        params = ListScheduledExportsParams()
        result = list_scheduled_exports(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 2)
        called_url = mock_get.call_args[0][0]
        self.assertIn("scheduled_data_export", called_url)

    @patch("servicenow_mcp.tools.automation_tools.requests.get")
    def test_list_scheduled_exports_http_error(self, mock_get):
        """Test list_scheduled_exports handles HTTP errors."""
        mock_get.side_effect = requests.HTTPError("503 error")
        params = ListScheduledExportsParams()
        result = list_scheduled_exports(self.config, self.auth_manager, params)
        self.assertFalse(result["success"])

    # --- update_scheduled_job ---

    @patch("servicenow_mcp.tools.automation_tools.requests.patch")
    def test_update_scheduled_job_success(self, mock_patch):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": {"sys_id": "job1", "name": "Updated Job", "script": "gs.info('updated');"}
        }
        mock_response.raise_for_status = MagicMock()
        mock_patch.return_value = mock_response

        params = UpdateScheduledJobParams(job_sys_id="job1", name="Updated Job")
        result = update_scheduled_job(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        self.assertEqual(result["scheduled_job"]["name"], "Updated Job")

    @patch("servicenow_mcp.tools.automation_tools.requests.patch")
    def test_update_scheduled_job_updates_script(self, mock_patch):
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": {"sys_id": "job1", "script": "gs.info('new');"}}
        mock_response.raise_for_status = MagicMock()
        mock_patch.return_value = mock_response

        params = UpdateScheduledJobParams(job_sys_id="job1", script="gs.info('new');")
        result = update_scheduled_job(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        call_payload = mock_patch.call_args[1]["json"]
        self.assertIn("script", call_payload)

    @patch("servicenow_mcp.tools.automation_tools.requests.patch")
    def test_update_scheduled_job_http_error(self, mock_patch):
        mock_patch.side_effect = requests.HTTPError("Timeout")
        params = UpdateScheduledJobParams(job_sys_id="job1", name="Fail")
        result = update_scheduled_job(self.config, self.auth_manager, params)
        self.assertFalse(result["success"])
        self.assertIn("message", result)

    @patch("servicenow_mcp.tools.automation_tools.requests.patch")
    def test_run_scheduled_job_now_success(self, mock_patch):
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": {"sys_id": "job1", "name": "My Job"}}
        mock_response.raise_for_status = MagicMock()
        mock_patch.return_value = mock_response

        params = RunScheduledJobNowParams(job_sys_id="job1")
        result = run_scheduled_job_now(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        call_payload = mock_patch.call_args[1]["json"]
        self.assertIn("trigger", call_payload)

    @patch("servicenow_mcp.tools.automation_tools.requests.patch")
    def test_run_scheduled_job_now_http_error(self, mock_patch):
        mock_patch.side_effect = requests.HTTPError("Connection refused")
        params = RunScheduledJobNowParams(job_sys_id="job1")
        result = run_scheduled_job_now(self.config, self.auth_manager, params)
        self.assertFalse(result["success"])
        self.assertIn("message", result)


if __name__ == "__main__":
    unittest.main()
