# tests/integration/test_risks.py
"""
Integration tests for risk tools against a live ServiceNow instance.
READ-ONLY — no create/update operations.
Run with: SN_INTEGRATION_TESTS=1 pytest tests/integration/test_risks.py -v -s
"""
import json
import pytest

from servicenow_mcp.tools.risk_tools import (
    list_risks,
    get_risk,
    list_risk_criteria,
    ListRisksParams,
    GetRiskParams,
    ListRiskCriteriaParams,
)


@pytest.mark.integration
class TestRiskIntegration:

    def test_list_risks_returns_results(self, live_config, live_auth):
        """Verify list_risks connects and returns records."""
        params = ListRisksParams(limit=5)
        result = list_risks(live_config, live_auth, params)

        print("\n--- list_risks response ---")
        print(json.dumps(result, indent=2, default=str))

        assert result["success"] is True, f"Expected success, got: {result.get('message')}"
        assert "risks" in result
        assert isinstance(result["risks"], list)

    def test_list_risks_shape(self, live_config, live_auth):
        """Verify risk records have expected fields."""
        params = ListRisksParams(limit=3)
        result = list_risks(live_config, live_auth, params)

        assert result["success"] is True
        risks = result["risks"]

        if not risks:
            pytest.skip("No risks found on this instance.")

        first = risks[0]
        print("\n--- first risk fields ---")
        print(json.dumps(first, indent=2, default=str))

        assert "sys_id" in first, "Missing expected field: sys_id"

    def test_get_risk_by_sys_id(self, live_config, live_auth):
        """Verify get_risk returns full details by sys_id."""
        list_result = list_risks(live_config, live_auth, ListRisksParams(limit=1))
        assert list_result["success"] is True

        if not list_result["risks"]:
            pytest.skip("No risks on this instance.")

        sys_id = list_result["risks"][0]["sys_id"]

        params = GetRiskParams(sys_id=sys_id)  # NOTE: field is sys_id, not risk_id
        result = get_risk(live_config, live_auth, params)

        print(f"\n--- get_risk({sys_id}) response ---")
        print(json.dumps(result, indent=2, default=str))

        assert result["success"] is True
        assert "risk" in result

    def test_list_risk_criteria_returns_results(self, live_config, live_auth):
        """Verify list_risk_criteria returns structured data."""
        params = ListRiskCriteriaParams()
        result = list_risk_criteria(live_config, live_auth, params)

        print("\n--- list_risk_criteria response ---")
        print(json.dumps(result, indent=2, default=str))

        assert "success" in result

    def test_get_risk_not_found(self, live_config, live_auth):
        """Verify graceful not-found handling for a fake sys_id."""
        params = GetRiskParams(sys_id="00000000000000000000000000000000")
        result = get_risk(live_config, live_auth, params)

        print("\n--- not_found response ---")
        print(json.dumps(result, indent=2, default=str))

        assert result["success"] is False
        assert "message" in result
