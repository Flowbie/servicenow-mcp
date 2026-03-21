# tests/integration/test_automation.py
"""
Integration tests for automation (scheduled job) tools against a live ServiceNow instance.
READ-ONLY — list and get operations only. run_scheduled_job_now is excluded.
Run with: SN_INTEGRATION_TESTS=1 pytest tests/integration/test_automation.py -v -s
"""
import json
import pytest

from servicenow_mcp.tools.automation_tools import (
    list_scheduled_jobs,
    get_scheduled_job,
    list_scheduled_imports,
    list_scheduled_exports,
    ListScheduledJobsParams,
    GetScheduledJobParams,
    ListScheduledImportsParams,
    ListScheduledExportsParams,
)


@pytest.mark.integration
class TestAutomationIntegration:

    def test_list_scheduled_jobs_returns_results(self, live_config, live_auth):
        """Verify list_scheduled_jobs connects and returns records."""
        params = ListScheduledJobsParams(limit=5)
        result = list_scheduled_jobs(live_config, live_auth, params)

        print("\n--- list_scheduled_jobs response ---")
        print(json.dumps(result, indent=2, default=str))

        assert result["success"] is True, f"Expected success, got: {result.get('message')}"
        assert "scheduled_jobs" in result
        assert isinstance(result["scheduled_jobs"], list)

    def test_list_scheduled_jobs_shape(self, live_config, live_auth):
        """Verify scheduled job records have expected fields."""
        params = ListScheduledJobsParams(limit=3)
        result = list_scheduled_jobs(live_config, live_auth, params)

        assert result["success"] is True
        jobs = result["scheduled_jobs"]

        if not jobs:
            pytest.skip("No scheduled jobs found on this instance.")

        first = jobs[0]
        print("\n--- first scheduled job fields ---")
        print(json.dumps(first, indent=2, default=str))

        for field in ["sys_id", "name"]:
            assert field in first, f"Missing expected field: {field}"

    def test_get_scheduled_job_by_sys_id(self, live_config, live_auth):
        """Verify get_scheduled_job returns full job details."""
        list_result = list_scheduled_jobs(live_config, live_auth, ListScheduledJobsParams(limit=1))
        assert list_result["success"] is True

        if not list_result["scheduled_jobs"]:
            pytest.skip("No scheduled jobs on this instance.")

        sys_id = list_result["scheduled_jobs"][0]["sys_id"]

        params = GetScheduledJobParams(job_sys_id=sys_id)
        result = get_scheduled_job(live_config, live_auth, params)

        print(f"\n--- get_scheduled_job({sys_id}) response ---")
        print(json.dumps(result, indent=2, default=str))

        assert result["success"] is True
        assert "scheduled_job" in result

    def test_list_scheduled_imports_returns_results(self, live_config, live_auth):
        """Verify list_scheduled_imports returns records."""
        params = ListScheduledImportsParams(limit=5)
        result = list_scheduled_imports(live_config, live_auth, params)

        print("\n--- list_scheduled_imports response ---")
        print(json.dumps(result, indent=2, default=str))

        assert result["success"] is True
        assert "scheduled_imports" in result
        assert isinstance(result["scheduled_imports"], list)

    def test_list_scheduled_exports_returns_results(self, live_config, live_auth):
        """Verify list_scheduled_exports returns records."""
        params = ListScheduledExportsParams(limit=5)
        result = list_scheduled_exports(live_config, live_auth, params)

        print("\n--- list_scheduled_exports response ---")
        print(json.dumps(result, indent=2, default=str))

        assert result["success"] is True
        assert "scheduled_exports" in result
        assert isinstance(result["scheduled_exports"], list)

    def test_list_scheduled_jobs_limit_respected(self, live_config, live_auth):
        """Verify limit param is respected."""
        params = ListScheduledJobsParams(limit=2)
        result = list_scheduled_jobs(live_config, live_auth, params)

        assert result["success"] is True
        assert len(result["scheduled_jobs"]) <= 2
