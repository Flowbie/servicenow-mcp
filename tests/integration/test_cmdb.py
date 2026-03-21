# tests/integration/test_cmdb.py
"""
Integration tests for CMDB tools against a live ServiceNow instance.
READ-ONLY — list, get, search, and relationship read operations only.
Run with: SN_INTEGRATION_TESTS=1 pytest tests/integration/test_cmdb.py -v -s
"""
import json
import pytest

from servicenow_mcp.tools.cmdb_tools import (
    list_ci,
    get_ci,
    search_ci,
    get_ci_relationships,
    list_ci_relationship_types,
    get_ci_impact_graph,
    ListCIParams,
    GetCIParams,
    SearchCIParams,
    GetCIRelationshipsParams,
    ListCIRelationshipTypesParams,
    GetCIImpactGraphParams,
)


@pytest.mark.integration
class TestCMDBIntegration:

    def test_list_ci_returns_results(self, live_config, live_auth):
        """Verify list_ci connects and returns CI records."""
        params = ListCIParams(limit=5)
        result = list_ci(live_config, live_auth, params)

        print("\n--- list_ci response ---")
        print(json.dumps(result, indent=2, default=str))

        assert result["success"] is True, f"Expected success, got: {result.get('message')}"
        assert "cis" in result
        assert isinstance(result["cis"], list)

    def test_list_ci_shape(self, live_config, live_auth):
        """Verify CI records have expected fields."""
        params = ListCIParams(limit=3)
        result = list_ci(live_config, live_auth, params)

        assert result["success"] is True
        cis = result["cis"]

        if not cis:
            pytest.skip("No CIs found on this instance.")

        first = cis[0]
        print("\n--- first CI fields ---")
        print(json.dumps(first, indent=2, default=str))

        for field in ["sys_id", "name"]:
            assert field in first, f"Missing expected field: {field}"

    def test_get_ci_by_sys_id(self, live_config, live_auth):
        """Verify get_ci returns full CI details."""
        list_result = list_ci(live_config, live_auth, ListCIParams(limit=1))
        assert list_result["success"] is True

        if not list_result["cis"]:
            pytest.skip("No CIs on this instance.")

        sys_id = list_result["cis"][0]["sys_id"]

        params = GetCIParams(ci_id=sys_id)
        result = get_ci(live_config, live_auth, params)

        print(f"\n--- get_ci({sys_id}) response ---")
        print(json.dumps(result, indent=2, default=str))

        assert result["success"] is True
        assert "ci" in result

    def test_search_ci_returns_results(self, live_config, live_auth):
        """Verify search_ci returns results for a broad search."""
        params = SearchCIParams(query="name CONTAINS a", limit=5)
        result = search_ci(live_config, live_auth, params)

        print("\n--- search_ci response ---")
        print(json.dumps(result, indent=2, default=str))

        assert "success" in result

    def test_list_ci_relationship_types(self, live_config, live_auth):
        """Verify list_ci_relationship_types returns OOB relationship type records."""
        params = ListCIRelationshipTypesParams()
        result = list_ci_relationship_types(live_config, live_auth, params)

        print("\n--- list_ci_relationship_types response ---")
        print(json.dumps(result, indent=2, default=str))

        assert result["success"] is True
        assert "relationship_types" in result
        assert len(result["relationship_types"]) > 0, "Expected at least one relationship type"

    def test_get_ci_relationships(self, live_config, live_auth):
        """Verify get_ci_relationships returns relationship data for a real CI."""
        list_result = list_ci(live_config, live_auth, ListCIParams(limit=1))
        assert list_result["success"] is True

        if not list_result["cis"]:
            pytest.skip("No CIs on this instance.")

        sys_id = list_result["cis"][0]["sys_id"]

        params = GetCIRelationshipsParams(ci_id=sys_id)
        result = get_ci_relationships(live_config, live_auth, params)

        print(f"\n--- get_ci_relationships({sys_id}) response ---")
        print(json.dumps(result, indent=2, default=str))

        assert "success" in result

    def test_get_ci_impact_graph(self, live_config, live_auth):
        """Verify get_ci_impact_graph returns impact data for a real CI."""
        list_result = list_ci(live_config, live_auth, ListCIParams(limit=1))
        assert list_result["success"] is True

        if not list_result["cis"]:
            pytest.skip("No CIs on this instance.")

        sys_id = list_result["cis"][0]["sys_id"]

        params = GetCIImpactGraphParams(ci_id=sys_id)
        result = get_ci_impact_graph(live_config, live_auth, params)

        print(f"\n--- get_ci_impact_graph({sys_id}) response ---")
        print(json.dumps(result, indent=2, default=str))

        assert "success" in result
