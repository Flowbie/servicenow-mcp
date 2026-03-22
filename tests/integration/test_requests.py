# tests/integration/test_requests.py
"""
Integration tests for request tools against a live ServiceNow instance.
READ-ONLY — get_ritm_variables only.
CRUD operations (list_requests, get_request, list_request_items, list_sc_tasks)
removed — use query_records with sc_request / sc_req_item / sc_task architecture blueprints.
Run with: SN_INTEGRATION_TESTS=1 pytest tests/integration/test_requests.py -v -s
"""
import json
import pytest

from servicenow_mcp.tools.request_tools import (
    get_ritm_variables,
    GetRitmVariablesParams,
)


@pytest.mark.integration
class TestRequestIntegration:

    def test_get_ritm_variables_requires_sys_id(self, live_config, live_auth):
        """Verify GetRitmVariablesParams requires ritm_sys_id."""
        with pytest.raises(Exception):
            GetRitmVariablesParams()

    def test_get_ritm_variables_empty_ritm(self, live_config, live_auth):
        """Verify get_ritm_variables handles a non-existent RITM gracefully."""
        params = GetRitmVariablesParams(ritm_sys_id="nonexistent_ritm_sys_id_000")
        result = get_ritm_variables(live_config, live_auth, params)

        print("\n--- get_ritm_variables(nonexistent) response ---")
        print(json.dumps(result, indent=2, default=str))

        assert "success" in result
        assert "variables" in result
        assert isinstance(result["variables"], list)
