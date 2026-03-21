# tests/integration/test_workflows.py
"""
Integration tests for legacy workflow tools against a live ServiceNow instance.
READ-ONLY — no create/update/activate/deactivate operations.
Run with: SN_INTEGRATION_TESTS=1 pytest tests/integration/test_workflows.py -v -s

NOTE: workflow_tools uses a legacy signature (auth_manager, server_config, params: Dict)
but _get_auth_and_config() detects and handles swapped arguments, so we can call with
(live_config, live_auth, params) and it will self-correct. _unwrap_params() handles
Pydantic model instances as well as plain dicts.

Return format has NO 'success' key — check for 'error' absence instead:
  success path:  {"workflows": [...], "count": N, "total": N}
  error path:    {"error": "..."}
"""
import json
import pytest

from servicenow_mcp.tools.workflow_tools import (
    list_workflows,
    get_workflow_details,
    list_workflow_versions,
    get_workflow_activities,
    ListWorkflowsParams,
    GetWorkflowDetailsParams,
    ListWorkflowVersionsParams,
    GetWorkflowActivitiesParams,
)


@pytest.mark.integration
class TestWorkflowIntegration:

    def test_list_workflows_returns_results(self, live_config, live_auth):
        """Verify list_workflows connects and returns records."""
        params = ListWorkflowsParams(limit=5)
        result = list_workflows(live_config, live_auth, params)

        print("\n--- list_workflows response ---")
        print(json.dumps(result, indent=2, default=str))

        assert "error" not in result, f"Unexpected error: {result.get('error')}"
        assert "workflows" in result
        assert isinstance(result["workflows"], list)

    def test_list_workflows_shape(self, live_config, live_auth):
        """Verify workflow records have expected fields."""
        params = ListWorkflowsParams(limit=3)
        result = list_workflows(live_config, live_auth, params)

        assert "error" not in result, f"Unexpected error: {result.get('error')}"
        workflows = result["workflows"]

        if not workflows:
            pytest.skip("No workflows found on this instance.")

        first = workflows[0]
        print("\n--- first workflow fields ---")
        print(json.dumps(first, indent=2, default=str))

        assert "sys_id" in first, "Missing expected field: sys_id"
        assert "name" in first, "Missing expected field: name"

    def test_list_workflows_limit_respected(self, live_config, live_auth):
        """Verify limit param is respected."""
        params = ListWorkflowsParams(limit=2)
        result = list_workflows(live_config, live_auth, params)

        assert "error" not in result
        assert len(result["workflows"]) <= 2

    def test_list_workflows_count_field(self, live_config, live_auth):
        """Verify count and total fields are present in response."""
        params = ListWorkflowsParams(limit=5)
        result = list_workflows(live_config, live_auth, params)

        assert "error" not in result
        assert "count" in result
        assert "total" in result
        assert isinstance(result["count"], int)
        assert isinstance(result["total"], int)

    def test_get_workflow_details(self, live_config, live_auth):
        """Verify get_workflow_details returns full workflow info."""
        list_result = list_workflows(live_config, live_auth, ListWorkflowsParams(limit=1))
        assert "error" not in list_result

        if not list_result["workflows"]:
            pytest.skip("No workflows on this instance.")

        sys_id = list_result["workflows"][0]["sys_id"]

        params = GetWorkflowDetailsParams(workflow_id=sys_id)
        result = get_workflow_details(live_config, live_auth, params)

        print(f"\n--- get_workflow_details({sys_id}) response ---")
        print(json.dumps(result, indent=2, default=str))

        assert "error" not in result, f"Unexpected error: {result.get('error')}"
        assert "workflow" in result

    def test_get_workflow_details_shape(self, live_config, live_auth):
        """Verify workflow detail record has expected fields."""
        list_result = list_workflows(live_config, live_auth, ListWorkflowsParams(limit=1))
        assert "error" not in list_result

        if not list_result["workflows"]:
            pytest.skip("No workflows on this instance.")

        sys_id = list_result["workflows"][0]["sys_id"]
        result = get_workflow_details(live_config, live_auth, GetWorkflowDetailsParams(workflow_id=sys_id))

        assert "error" not in result
        workflow = result["workflow"]
        assert "sys_id" in workflow, "Missing sys_id in workflow detail"
        assert "name" in workflow, "Missing name in workflow detail"

    def test_list_workflow_versions(self, live_config, live_auth):
        """Verify list_workflow_versions returns version history."""
        list_result = list_workflows(live_config, live_auth, ListWorkflowsParams(limit=1))
        assert "error" not in list_result

        if not list_result["workflows"]:
            pytest.skip("No workflows on this instance.")

        sys_id = list_result["workflows"][0]["sys_id"]

        params = ListWorkflowVersionsParams(workflow_id=sys_id)
        result = list_workflow_versions(live_config, live_auth, params)

        print(f"\n--- list_workflow_versions({sys_id}) response ---")
        print(json.dumps(result, indent=2, default=str))

        assert "error" not in result, f"Unexpected error: {result.get('error')}"
        assert "versions" in result
        assert isinstance(result["versions"], list)

    def test_get_workflow_activities(self, live_config, live_auth):
        """Verify get_workflow_activities returns activity steps."""
        list_result = list_workflows(live_config, live_auth, ListWorkflowsParams(limit=1))
        assert "error" not in list_result

        if not list_result["workflows"]:
            pytest.skip("No workflows on this instance.")

        sys_id = list_result["workflows"][0]["sys_id"]

        params = GetWorkflowActivitiesParams(workflow_id=sys_id)
        result = get_workflow_activities(live_config, live_auth, params)

        print(f"\n--- get_workflow_activities({sys_id}) response ---")
        print(json.dumps(result, indent=2, default=str))

        assert "error" not in result, f"Unexpected error: {result.get('error')}"
        assert "activities" in result
        assert isinstance(result["activities"], list)

    def test_list_workflows_active_filter(self, live_config, live_auth):
        """Verify active=True filter works."""
        params = ListWorkflowsParams(limit=5, active=True)
        result = list_workflows(live_config, live_auth, params)

        print("\n--- list_workflows(active=True) response ---")
        print(json.dumps(result, indent=2, default=str))

        assert "error" not in result
        assert "workflows" in result

    def test_list_workflows_name_filter(self, live_config, live_auth):
        """Verify name filter param is accepted without error."""
        params = ListWorkflowsParams(limit=5, name="")
        result = list_workflows(live_config, live_auth, params)

        assert "error" not in result
        assert "workflows" in result
