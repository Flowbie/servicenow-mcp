# tests/integration/test_requests.py
"""
Integration tests for request tools against a live ServiceNow instance.
READ-ONLY — no update operations.
Run with: SN_INTEGRATION_TESTS=1 pytest tests/integration/test_requests.py -v -s
"""
import json
import pytest

from servicenow_mcp.tools.request_tools import (
    list_requests,
    get_request,
    list_request_items,
    list_sc_tasks,
    get_ritm_variables,
    ListRequestsParams,
    GetRequestParams,
    ListRequestItemsParams,
    ListScTasksParams,
    GetRitmVariablesParams,
)


@pytest.mark.integration
class TestRequestIntegration:

    def test_list_requests_returns_results(self, live_config, live_auth):
        """Verify list_requests connects and returns records."""
        params = ListRequestsParams(limit=5)
        result = list_requests(live_config, live_auth, params)

        print("\n--- list_requests response ---")
        print(json.dumps(result, indent=2, default=str))

        assert result["success"] is True, f"Expected success, got: {result.get('message')}"
        assert "requests" in result
        assert isinstance(result["requests"], list)

    def test_list_requests_respects_limit(self, live_config, live_auth):
        """Verify limit parameter is honored."""
        params = ListRequestsParams(limit=3)
        result = list_requests(live_config, live_auth, params)

        assert result["success"] is True
        assert len(result["requests"]) <= 3

    def test_list_requests_response_structure(self, live_config, live_auth):
        """Verify response contains expected metadata fields."""
        params = ListRequestsParams(limit=1)
        result = list_requests(live_config, live_auth, params)

        assert result["success"] is True
        assert "requests" in result
        assert "total" in result
        assert "limit" in result
        assert "offset" in result

    def test_list_request_items_returns_results(self, live_config, live_auth):
        """Verify list_request_items returns records."""
        params = ListRequestItemsParams(limit=5)
        result = list_request_items(live_config, live_auth, params)

        print("\n--- list_request_items response ---")
        print(json.dumps(result, indent=2, default=str))

        assert result["success"] is True, f"Expected success, got: {result.get('message')}"
        assert "items" in result
        assert isinstance(result["items"], list)

    def test_list_request_items_response_structure(self, live_config, live_auth):
        """Verify list_request_items response contains metadata fields."""
        params = ListRequestItemsParams(limit=1)
        result = list_request_items(live_config, live_auth, params)

        assert result["success"] is True
        assert "items" in result
        assert "total" in result
        assert "limit" in result
        assert "offset" in result

    def test_list_request_items_respects_limit(self, live_config, live_auth):
        """Verify limit is applied to request items."""
        params = ListRequestItemsParams(limit=2)
        result = list_request_items(live_config, live_auth, params)

        assert result["success"] is True
        assert len(result["items"]) <= 2

    def test_list_sc_tasks_returns_results(self, live_config, live_auth):
        """Verify list_sc_tasks returns records."""
        params = ListScTasksParams(limit=5)
        result = list_sc_tasks(live_config, live_auth, params)

        print("\n--- list_sc_tasks response ---")
        print(json.dumps(result, indent=2, default=str))

        assert result["success"] is True, f"Expected success, got: {result.get('message')}"
        assert "tasks" in result
        assert isinstance(result["tasks"], list)

    def test_list_sc_tasks_response_structure(self, live_config, live_auth):
        """Verify list_sc_tasks response contains metadata fields."""
        params = ListScTasksParams(limit=1)
        result = list_sc_tasks(live_config, live_auth, params)

        assert result["success"] is True
        assert "tasks" in result
        assert "total" in result
        assert "limit" in result
        assert "offset" in result

    def test_get_request_by_number(self, live_config, live_auth):
        """Verify get_request returns full request details."""
        list_result = list_requests(live_config, live_auth, ListRequestsParams(limit=1))
        assert list_result["success"] is True

        if not list_result["requests"]:
            pytest.skip("No requests on this instance.")

        number = list_result["requests"][0]["number"]

        params = GetRequestParams(request_number=number)
        result = get_request(live_config, live_auth, params)

        print(f"\n--- get_request({number}) response ---")
        print(json.dumps(result, indent=2, default=str))

        assert result["success"] is True
        assert "request" in result
        assert result["request"] is not None

    def test_get_request_by_sys_id(self, live_config, live_auth):
        """Verify get_request works with sys_id lookup."""
        list_result = list_requests(live_config, live_auth, ListRequestsParams(limit=1))
        assert list_result["success"] is True

        if not list_result["requests"]:
            pytest.skip("No requests on this instance.")

        sys_id = list_result["requests"][0]["sys_id"]

        params = GetRequestParams(request_sys_id=sys_id)
        result = get_request(live_config, live_auth, params)

        print(f"\n--- get_request(sys_id={sys_id}) response ---")
        print(json.dumps(result, indent=2, default=str))

        assert result["success"] is True
        assert "request" in result
        assert result["request"] is not None

    def test_get_request_not_found(self, live_config, live_auth):
        """Verify get_request handles non-existent request gracefully."""
        params = GetRequestParams(request_number="REQ9999999999")
        result = get_request(live_config, live_auth, params)

        print("\n--- get_request(not found) response ---")
        print(json.dumps(result, indent=2, default=str))

        # Either success=False or success=True with None request — both are valid responses
        assert "success" in result
        if result["success"] is True:
            assert result.get("request") is None
        else:
            assert "message" in result

    def test_get_ritm_variables(self, live_config, live_auth):
        """Verify get_ritm_variables returns variables for a real RITM."""
        items_result = list_request_items(live_config, live_auth, ListRequestItemsParams(limit=1))
        assert items_result["success"] is True

        if not items_result["items"]:
            pytest.skip("No request items on this instance.")

        ritm_sys_id = items_result["items"][0]["sys_id"]

        params = GetRitmVariablesParams(ritm_sys_id=ritm_sys_id)  # field is ritm_sys_id, not ritm_id
        result = get_ritm_variables(live_config, live_auth, params)

        print(f"\n--- get_ritm_variables({ritm_sys_id}) response ---")
        print(json.dumps(result, indent=2, default=str))

        assert "success" in result
        assert result["success"] is True
        assert "variables" in result
        assert isinstance(result["variables"], list)
