# tests/integration/test_epics.py
"""
Integration tests for epic tools against a live ServiceNow instance.
Run with: SN_INTEGRATION_TESTS=1 pytest tests/integration/test_epics.py -v -s
"""
import json
import pytest

from servicenow_mcp.tools.epic_tools import (
    list_epics,
    ListEpicsParams,
)


@pytest.mark.integration
class TestEpicIntegration:

    def test_list_epics_returns_results(self, live_config, live_auth):
        """Verify list_epics connects and returns records."""
        params = ListEpicsParams(limit=5)
        result = list_epics(live_config, live_auth, params)

        print("\n--- list_epics response ---")
        print(json.dumps(result, indent=2, default=str))

        assert result["success"] is True, f"Expected success, got: {result.get('message')}"
        assert "epics" in result
        assert isinstance(result["epics"], list)

    def test_list_epics_shape(self, live_config, live_auth):
        """Verify epic records have expected fields."""
        params = ListEpicsParams(limit=3)
        result = list_epics(live_config, live_auth, params)

        assert result["success"] is True
        epics = result["epics"]

        if not epics:
            pytest.skip("No epics found on this instance.")

        first = epics[0]
        print("\n--- first epic fields ---")
        print(json.dumps(first, indent=2, default=str))

        for field in ["sys_id", "short_description"]:
            assert field in first, f"Missing expected field: {field}"

    def test_list_epics_limit_respected(self, live_config, live_auth):
        """Verify limit param is respected."""
        params = ListEpicsParams(limit=2)
        result = list_epics(live_config, live_auth, params)

        assert result["success"] is True
        assert len(result["epics"]) <= 2
