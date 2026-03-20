# tests/integration/test_incidents.py
"""
Integration tests for incident tools against a live ServiceNow instance.
Run with: SN_INTEGRATION_TESTS=1 pytest tests/integration/test_incidents.py -v -s
"""
import json
import pytest

from servicenow_mcp.tools.incident_tools import (
    list_incidents,
    get_incident_by_number,
    ListIncidentsParams,
    GetIncidentByNumberParams,
)


@pytest.mark.integration
class TestIncidentIntegration:

    def test_list_incidents_returns_results(self, live_config, live_auth):
        """Verify list_incidents connects and returns records."""
        params = ListIncidentsParams(limit=5)
        result = list_incidents(live_config, live_auth, params)

        print("\n--- list_incidents response ---")
        print(json.dumps(result, indent=2, default=str))

        assert result["success"] is True, f"Expected success, got: {result.get('message')}"
        assert "incidents" in result
        assert isinstance(result["incidents"], list)

    def test_list_incidents_shape(self, live_config, live_auth):
        """Verify each incident record has the expected key fields."""
        params = ListIncidentsParams(limit=3)
        result = list_incidents(live_config, live_auth, params)

        assert result["success"] is True
        incidents = result["incidents"]

        if not incidents:
            pytest.skip("No incidents found on this instance — cannot verify shape.")

        first = incidents[0]
        print("\n--- first incident fields ---")
        print(json.dumps(first, indent=2, default=str))

        for field in ["sys_id", "number", "short_description", "state"]:
            assert field in first, f"Missing expected field: {field}"

    def test_list_incidents_limit_respected(self, live_config, live_auth):
        """Verify the limit parameter is respected."""
        params = ListIncidentsParams(limit=2)
        result = list_incidents(live_config, live_auth, params)

        assert result["success"] is True
        assert len(result["incidents"]) <= 2

    def test_get_incident_by_number(self, live_config, live_auth):
        """Verify get_incident_by_number returns a real incident."""
        list_result = list_incidents(live_config, live_auth, ListIncidentsParams(limit=1))
        assert list_result["success"] is True

        if not list_result["incidents"]:
            pytest.skip("No incidents on this instance to look up.")

        number = list_result["incidents"][0]["number"]

        params = GetIncidentByNumberParams(incident_number=number)
        result = get_incident_by_number(live_config, live_auth, params)

        print(f"\n--- get_incident_by_number({number}) response ---")
        print(json.dumps(result, indent=2, default=str))

        assert result["success"] is True
        assert result["incident"]["number"] == number

    def test_get_incident_not_found(self, live_config, live_auth):
        """Verify a graceful not-found response for a fake incident number."""
        params = GetIncidentByNumberParams(incident_number="INC9999999999")
        result = get_incident_by_number(live_config, live_auth, params)

        print("\n--- not_found response ---")
        print(json.dumps(result, indent=2, default=str))

        assert result["success"] is False
        assert "message" in result
