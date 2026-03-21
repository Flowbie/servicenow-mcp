"""
Integration tests for sprint tools against a live ServiceNow instance.
Run with: SN_INTEGRATION_TESTS=1 pytest tests/integration/test_sprints.py -v -s
"""
import json
import pytest
import requests

from servicenow_mcp.tools.sprint_tools import (
    get_sprint,
    get_sprint_summary,
    list_sprints,
    GetSprintParams,
    GetSprintSummaryParams,
    ListSprintsParams,
)


def _fetch_any_sprint_sys_id(live_config, live_auth):
    """
    Helper: query rm_sprint_2 directly via Table API to get one real sys_id.
    Returns None if no sprints exist on the instance.
    """
    url = f"{live_config.instance_url}/api/now/table/rm_sprint_2"
    headers = live_auth.get_headers()
    try:
        resp = requests.get(
            url,
            headers=headers,
            params={
                "sysparm_fields": "sys_id,name,number",
                "sysparm_limit": 1,
                "sysparm_display_value": "false",
            },
            timeout=live_config.timeout,
        )
        resp.raise_for_status()
        records = resp.json().get("result", [])
        if records:
            return records[0]["sys_id"]
    except requests.RequestException:
        pass
    return None


@pytest.mark.integration
class TestSprintIntegration:

    def test_list_sprints_via_table_api(self, live_config, live_auth):
        """Verify rm_sprint_2 Table API is accessible and returns records."""
        url = f"{live_config.instance_url}/api/now/table/rm_sprint_2"
        headers = live_auth.get_headers()

        resp = requests.get(
            url,
            headers=headers,
            params={
                "sysparm_fields": "sys_id,name,number,state",
                "sysparm_limit": 5,
                "sysparm_display_value": "true",
            },
            timeout=live_config.timeout,
        )

        print("\n--- rm_sprint_2 table API response ---")
        print(json.dumps(resp.json(), indent=2, default=str))

        if resp.status_code == 400 and "Invalid table" in resp.text:
            pytest.skip("rm_sprint_2 table not available on this instance.")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        result = resp.json().get("result")
        assert isinstance(result, list), "Expected result to be a list"

    def test_list_sprints_returns_expected_fields(self, live_config, live_auth):
        """Verify sprint records contain core fields."""
        url = f"{live_config.instance_url}/api/now/table/rm_sprint_2"
        headers = live_auth.get_headers()

        resp = requests.get(
            url,
            headers=headers,
            params={
                "sysparm_fields": "sys_id,name,number,state,start_date,end_date",
                "sysparm_limit": 3,
                "sysparm_display_value": "false",
            },
            timeout=live_config.timeout,
        )
        if resp.status_code == 400 and "Invalid table" in resp.text:
            pytest.skip("rm_sprint_2 table not available on this instance.")
        assert resp.status_code == 200
        records = resp.json().get("result", [])

        if not records:
            pytest.skip("No sprints found on this instance.")

        first = records[0]
        print("\n--- first sprint fields ---")
        print(json.dumps(first, indent=2, default=str))

        for field in ["sys_id", "name", "number", "state"]:
            assert field in first, f"Missing expected field: {field}"

    def test_get_sprint_by_sys_id(self, live_config, live_auth):
        """Verify get_sprint returns full sprint details for a real sys_id."""
        sys_id = _fetch_any_sprint_sys_id(live_config, live_auth)
        if sys_id is None:
            pytest.skip("No sprints found on this instance.")

        params = GetSprintParams(sprint_id=sys_id)
        result = get_sprint(live_config, live_auth, params)

        print(f"\n--- get_sprint({sys_id}) response ---")
        print(json.dumps(result, indent=2, default=str))

        assert result["success"] is True, f"Expected success, got: {result.get('message')}"
        assert "sprint" in result
        assert isinstance(result["sprint"], dict)

    def test_get_sprint_has_expected_fields(self, live_config, live_auth):
        """Verify the sprint record returned by get_sprint has key fields."""
        sys_id = _fetch_any_sprint_sys_id(live_config, live_auth)
        if sys_id is None:
            pytest.skip("No sprints found on this instance.")

        result = get_sprint(live_config, live_auth, GetSprintParams(sprint_id=sys_id))
        assert result["success"] is True

        sprint = result["sprint"]
        for field in ["sys_id", "name", "state"]:
            assert field in sprint, f"Missing expected field: {field}"

    def test_get_sprint_not_found(self, live_config, live_auth):
        """Verify graceful not-found handling for a nonexistent sprint id."""
        params = GetSprintParams(sprint_id="nonexistent_sys_id_00000000000000")
        result = get_sprint(live_config, live_auth, params)

        print("\n--- get_sprint not_found response ---")
        print(json.dumps(result, indent=2, default=str))

        assert result["success"] is False
        assert "message" in result

    def test_get_sprint_summary(self, live_config, live_auth):
        """Verify get_sprint_summary returns story counts and points for a real sprint."""
        sys_id = _fetch_any_sprint_sys_id(live_config, live_auth)
        if sys_id is None:
            pytest.skip("No sprints found on this instance.")

        params = GetSprintSummaryParams(sprint_id=sys_id)
        result = get_sprint_summary(live_config, live_auth, params)

        print(f"\n--- get_sprint_summary({sys_id}) response ---")
        print(json.dumps(result, indent=2, default=str))

        assert result["success"] is True, f"Expected success, got: {result.get('message')}"
        assert "sprint" in result
        assert "story_counts" in result
        assert "points" in result
        assert "completion_forecast" in result

    def test_get_sprint_summary_story_counts_shape(self, live_config, live_auth):
        """Verify story_counts block has expected keys."""
        sys_id = _fetch_any_sprint_sys_id(live_config, live_auth)
        if sys_id is None:
            pytest.skip("No sprints found on this instance.")

        result = get_sprint_summary(live_config, live_auth, GetSprintSummaryParams(sprint_id=sys_id))
        assert result["success"] is True

        counts = result["story_counts"]
        for key in ["total", "done", "in_progress", "backlog", "cancelled"]:
            assert key in counts, f"Missing story_counts key: {key}"
            assert isinstance(counts[key], int)

    def test_get_sprint_summary_points_shape(self, live_config, live_auth):
        """Verify points block has expected keys and non-negative values."""
        sys_id = _fetch_any_sprint_sys_id(live_config, live_auth)
        if sys_id is None:
            pytest.skip("No sprints found on this instance.")

        result = get_sprint_summary(live_config, live_auth, GetSprintSummaryParams(sprint_id=sys_id))
        assert result["success"] is True

        points = result["points"]
        for key in ["total", "completed", "remaining"]:
            assert key in points, f"Missing points key: {key}"
            assert points[key] >= 0, f"Expected non-negative value for points[{key}]"

    def test_get_sprint_summary_include_stories(self, live_config, live_auth):
        """Verify include_stories=True appends a stories list to the response."""
        sys_id = _fetch_any_sprint_sys_id(live_config, live_auth)
        if sys_id is None:
            pytest.skip("No sprints found on this instance.")

        params = GetSprintSummaryParams(sprint_id=sys_id, include_stories=True)
        result = get_sprint_summary(live_config, live_auth, params)

        assert result["success"] is True
        assert "stories" in result, "include_stories=True should add 'stories' key to response"
        assert isinstance(result["stories"], list)

    def test_get_sprint_summary_not_found(self, live_config, live_auth):
        """Verify get_sprint_summary gracefully handles a nonexistent sprint."""
        params = GetSprintSummaryParams(sprint_id="nonexistent_sys_id_00000000000000")
        result = get_sprint_summary(live_config, live_auth, params)

        print("\n--- get_sprint_summary not_found response ---")
        print(json.dumps(result, indent=2, default=str))

        assert result["success"] is False
        assert "message" in result

    def test_get_sprint_summary_forecast_values(self, live_config, live_auth):
        """Verify completion_forecast is one of the expected enum values."""
        sys_id = _fetch_any_sprint_sys_id(live_config, live_auth)
        if sys_id is None:
            pytest.skip("No sprints found on this instance.")

        result = get_sprint_summary(live_config, live_auth, GetSprintSummaryParams(sprint_id=sys_id))
        assert result["success"] is True

        valid_forecasts = {"no_stories", "complete", "on_track", "at_risk"}
        forecast = result["completion_forecast"]
        assert forecast in valid_forecasts, (
            f"Unexpected forecast value '{forecast}'. Expected one of {valid_forecasts}"
        )

    # list_sprints tests

    def _skip_if_table_unavailable(self, result):
        """Skip the test if rm_sprint_2 is not available on this instance."""
        if not result["success"]:
            msg = result.get("message", "")
            if "Invalid table" in msg or "400" in msg:
                pytest.skip(f"rm_sprint_2 table not available on this instance: {msg}")

    def test_list_sprints_returns_results(self, live_config, live_auth):
        """Verify list_sprints connects and returns a list."""
        params = ListSprintsParams(limit=5)
        result = list_sprints(live_config, live_auth, params)

        print("\n--- list_sprints response ---")
        print(json.dumps(result, indent=2, default=str))

        self._skip_if_table_unavailable(result)
        assert result["success"] is True, f"Expected success, got: {result.get('message')}"
        assert "sprints" in result
        assert isinstance(result["sprints"], list)
        assert "count" in result

    def test_list_sprints_shape(self, live_config, live_auth):
        """Verify sprint records have expected fields."""
        params = ListSprintsParams(limit=3)
        result = list_sprints(live_config, live_auth, params)

        self._skip_if_table_unavailable(result)
        assert result["success"] is True
        sprints = result["sprints"]

        if not sprints:
            pytest.skip("No sprints found on this instance.")

        first = sprints[0]
        print("\n--- first sprint fields ---")
        print(json.dumps(first, indent=2, default=str))

        for field in ["sys_id", "name", "state"]:
            assert field in first, f"Missing expected field: {field}"

    def test_list_sprints_limit_respected(self, live_config, live_auth):
        """Verify limit param is respected."""
        params = ListSprintsParams(limit=2)
        result = list_sprints(live_config, live_auth, params)

        self._skip_if_table_unavailable(result)
        assert result["success"] is True
        assert len(result["sprints"]) <= 2

    def test_list_sprints_filter_by_state(self, live_config, live_auth):
        """Verify state filter works — active sprints only."""
        params = ListSprintsParams(state="2", limit=10)  # state=2 is Active
        result = list_sprints(live_config, live_auth, params)

        print("\n--- list_sprints state=Active response ---")
        print(json.dumps(result, indent=2, default=str))

        self._skip_if_table_unavailable(result)
        assert result["success"] is True
        # If any active sprints come back, confirm they all have state=2
        for sprint in result["sprints"]:
            raw_state = sprint.get("state", {})
            state_val = raw_state.get("value", raw_state) if isinstance(raw_state, dict) else str(raw_state)
            assert state_val == "2", f"Expected state=2, got {state_val}"

