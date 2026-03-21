"""
Integration tests for agile reporting tools.
Run with: SN_INTEGRATION_TESTS=1 pytest tests/integration/test_agile_reporting.py -v -s
"""
import json
import os
import pytest
import requests

from servicenow_mcp.tools.agile_reporting_tools import (
    get_my_work,
    get_blocked_work,
    get_release_status,
    GetMyWorkParams,
    GetBlockedWorkParams,
    GetReleaseStatusParams,
)


def _get_real_user_id(live_config, live_auth):
    """Helper: get the sys_id of the authenticated user, or skip."""
    username = os.environ.get("SERVICENOW_USERNAME", "")
    if not username:
        pytest.skip("SERVICENOW_USERNAME env var not set.")
    resp = requests.get(
        f"{live_config.instance_url}/api/now/table/sys_user",
        headers=live_auth.get_headers(),
        params={
            "sysparm_query": f"user_name={username}",
            "sysparm_fields": "sys_id",
            "sysparm_limit": 1,
        },
        timeout=live_config.timeout,
    )
    users = resp.json().get("result", [])
    if not users:
        pytest.skip("Could not find sys_user record for current user.")
    return users[0]["sys_id"]


def _get_real_release_id(live_config, live_auth):
    """Helper: get a real release sys_id from the instance, or skip."""
    resp = requests.get(
        f"{live_config.instance_url}/api/now/table/rm_release",
        headers=live_auth.get_headers(),
        params={"sysparm_fields": "sys_id,name", "sysparm_limit": 1},
        timeout=live_config.timeout,
    )
    releases = resp.json().get("result", [])
    if not releases:
        pytest.skip("No releases available on this instance.")
    return releases[0]["sys_id"]


@pytest.mark.integration
class TestAgileReportingIntegration:

    def test_get_my_work_returns_response(self, live_config, live_auth):
        """Verify get_my_work returns structured data for the authenticated user."""
        user_id = _get_real_user_id(live_config, live_auth)
        params = GetMyWorkParams(user_id=user_id)
        result = get_my_work(live_config, live_auth, params)

        print("\n--- get_my_work response ---")
        print(json.dumps(result, indent=2, default=str))

        assert result["success"] is True, f"Expected success, got: {result.get('message')}"

    def test_get_my_work_shape(self, live_config, live_auth):
        """Verify get_my_work response has expected structure."""
        user_id = _get_real_user_id(live_config, live_auth)
        params = GetMyWorkParams(user_id=user_id)
        result = get_my_work(live_config, live_auth, params)

        assert result["success"] is True, f"Expected success, got: {result.get('message')}"
        print("\n--- get_my_work keys ---")
        print(list(result.keys()))

        assert "stories" in result
        assert "count" in result

    def test_get_blocked_work_returns_response(self, live_config, live_auth):
        """Verify get_blocked_work returns structured data."""
        params = GetBlockedWorkParams()
        result = get_blocked_work(live_config, live_auth, params)

        print("\n--- get_blocked_work response ---")
        print(json.dumps(result, indent=2, default=str))

        assert result["success"] is True, f"Expected success, got: {result.get('message')}"

    def test_get_release_status_returns_response(self, live_config, live_auth):
        """Verify get_release_status returns structured data."""
        release_id = _get_real_release_id(live_config, live_auth)
        params = GetReleaseStatusParams(release_id=release_id)
        result = get_release_status(live_config, live_auth, params)

        print("\n--- get_release_status response ---")
        print(json.dumps(result, indent=2, default=str))

        assert result["success"] is True, f"Expected success, got: {result.get('message')}"

    def test_get_blocked_work_shape(self, live_config, live_auth):
        """Verify blocked work response includes blocked_stories list."""
        params = GetBlockedWorkParams()
        result = get_blocked_work(live_config, live_auth, params)

        assert result["success"] is True, f"Expected success, got: {result.get('message')}"
        print("\n--- blocked_work keys ---")
        print(list(result.keys()))

        assert "blocked_stories" in result
        assert "count" in result
