# tests/integration/test_changes.py
"""
Integration tests for change request tools against a live ServiceNow instance.
READ-ONLY — no create/update/approve operations.
Run with: SN_INTEGRATION_TESTS=1 pytest tests/integration/test_changes.py -v -s
"""
import json
import pytest

from servicenow_mcp.tools.change_tools import (
    list_change_requests,
    get_change_request_details,
    ListChangeRequestsParams,
    GetChangeRequestDetailsParams,
)


@pytest.mark.integration
class TestChangeIntegration:

    def test_list_change_requests_returns_results(self, live_config, live_auth):
        """Verify list_change_requests connects and returns records."""
        params = ListChangeRequestsParams(limit=5)
        result = list_change_requests(live_auth, live_config, params)  # legacy: auth first

        print("\n--- list_change_requests response ---")
        print(json.dumps(result, indent=2, default=str))

        assert result["success"] is True, f"Expected success, got: {result.get('message')}"
        assert "change_requests" in result
        assert isinstance(result["change_requests"], list)

    def test_list_change_requests_shape(self, live_config, live_auth):
        """Verify change request records have expected fields."""
        params = ListChangeRequestsParams(limit=3)
        result = list_change_requests(live_auth, live_config, params)

        assert result["success"] is True
        changes = result["change_requests"]

        if not changes:
            pytest.skip("No change requests found on this instance.")

        first = changes[0]
        print("\n--- first change request fields ---")
        print(json.dumps(first, indent=2, default=str))

        for field in ["sys_id", "number", "short_description", "state"]:
            assert field in first, f"Missing expected field: {field}"

    def test_get_change_request_details(self, live_config, live_auth):
        """Verify get_change_request_details returns full record by sys_id."""
        list_result = list_change_requests(live_auth, live_config, ListChangeRequestsParams(limit=1))
        assert list_result["success"] is True

        if not list_result["change_requests"]:
            pytest.skip("No change requests on this instance.")

        # get_change_request_details takes change_id = sys_id
        sys_id = list_result["change_requests"][0]["sys_id"]

        params = GetChangeRequestDetailsParams(change_id=sys_id)
        result = get_change_request_details(live_auth, live_config, params)

        print(f"\n--- get_change_request_details({sys_id}) response ---")
        print(json.dumps(result, indent=2, default=str))

        assert result["success"] is True
        assert "change_request" in result

    def test_list_change_requests_limit_respected(self, live_config, live_auth):
        """Verify limit param is respected."""
        params = ListChangeRequestsParams(limit=2)
        result = list_change_requests(live_auth, live_config, params)

        assert result["success"] is True
        assert len(result["change_requests"]) <= 2

    def test_get_change_request_not_found(self, live_config, live_auth):
        """Verify graceful not-found handling for a fake sys_id."""
        params = GetChangeRequestDetailsParams(change_id="00000000000000000000000000000000")
        result = get_change_request_details(live_auth, live_config, params)

        print("\n--- not_found response ---")
        print(json.dumps(result, indent=2, default=str))

        # A 404 from ServiceNow causes requests.raise_for_status() → success: False
        assert result["success"] is False
        assert "message" in result
