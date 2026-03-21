"""
Integration tests for scrum task tools against a live ServiceNow instance.
Run with: SN_INTEGRATION_TESTS=1 pytest tests/integration/test_scrum_tasks.py -v -s
"""
import json
import pytest

from servicenow_mcp.tools.scrum_task_tools import (
    list_scrum_tasks,
    get_scrum_task,
    ListScrumTasksParams,
    GetScrumTaskParams,
)


@pytest.mark.integration
class TestScrumTaskIntegration:

    def test_list_scrum_tasks_returns_results(self, live_config, live_auth):
        """Verify list_scrum_tasks connects and returns records."""
        params = ListScrumTasksParams(limit=5)
        result = list_scrum_tasks(live_config, live_auth, params)

        print("\n--- list_scrum_tasks response ---")
        print(json.dumps(result, indent=2, default=str))

        assert result["success"] is True, f"Expected success, got: {result.get('message')}"
        assert "scrum_tasks" in result
        assert isinstance(result["scrum_tasks"], list)

    def test_list_scrum_tasks_shape(self, live_config, live_auth):
        """Verify scrum task records have expected fields."""
        params = ListScrumTasksParams(limit=3)
        result = list_scrum_tasks(live_config, live_auth, params)

        assert result["success"] is True
        scrum_tasks = result["scrum_tasks"]

        if not scrum_tasks:
            pytest.skip("No scrum tasks found on this instance.")

        first = scrum_tasks[0]
        print("\n--- first scrum task fields ---")
        print(json.dumps(first, indent=2, default=str))

        for field in ["sys_id", "short_description"]:
            assert field in first, f"Missing expected field: {field}"

    def test_get_scrum_task_by_sys_id(self, live_config, live_auth):
        """Verify get_scrum_task returns full details."""
        list_result = list_scrum_tasks(live_config, live_auth, ListScrumTasksParams(limit=1))
        assert list_result["success"] is True

        if not list_result["scrum_tasks"]:
            pytest.skip("No scrum tasks on this instance.")

        sys_id = list_result["scrum_tasks"][0]["sys_id"]

        params = GetScrumTaskParams(scrum_task_id=sys_id)
        result = get_scrum_task(live_config, live_auth, params)

        print(f"\n--- get_scrum_task({sys_id}) response ---")
        print(json.dumps(result, indent=2, default=str))

        assert result["success"] is True
        assert "scrum_task" in result

    def test_list_scrum_tasks_limit_respected(self, live_config, live_auth):
        """Verify limit param is respected."""
        params = ListScrumTasksParams(limit=2)
        result = list_scrum_tasks(live_config, live_auth, params)

        assert result["success"] is True
        assert len(result["scrum_tasks"]) <= 2

    def test_get_scrum_task_not_found(self, live_config, live_auth):
        """Verify graceful not-found handling."""
        params = GetScrumTaskParams(scrum_task_id="nonexistent_task_sys_id_0000000")
        result = get_scrum_task(live_config, live_auth, params)

        print("\n--- not_found response ---")
        print(json.dumps(result, indent=2, default=str))

        assert result["success"] is False
        assert "message" in result
