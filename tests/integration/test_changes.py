# tests/integration/test_changes.py
"""
Integration tests for change management tools against a live ServiceNow instance.
READ-ONLY — no approve/reject operations against live data.
Run with: SN_INTEGRATION_TESTS=1 pytest tests/integration/test_changes.py -v -s

Note: CRUD operations (list_change_requests, get_change_request_details, etc.) have been
removed from change_tools.py. Use table_tools (query_records / get_record) with the
change_request architecture blueprint for those operations.
"""
import pytest

from servicenow_mcp.tools.change_tools import (
    approve_change,
    reject_change,
    submit_change_for_approval,
)


@pytest.mark.integration
class TestChangeApprovalIntegration:

    def test_approve_change_missing_record(self, live_config, live_auth):
        """Verify approve_change returns a graceful error for a non-existent change."""
        params = {"change_id": "00000000000000000000000000000000"}
        result = approve_change(live_auth, live_config, params)  # legacy: auth first

        # Either no approval record found, or a 404 → success: False
        assert result["success"] is False
        assert "message" in result

    def test_reject_change_missing_record(self, live_config, live_auth):
        """Verify reject_change returns a graceful error for a non-existent change."""
        params = {
            "change_id": "00000000000000000000000000000000",
            "rejection_reason": "Integration test — fake sys_id",
        }
        result = reject_change(live_auth, live_config, params)  # legacy: auth first

        assert result["success"] is False
        assert "message" in result
