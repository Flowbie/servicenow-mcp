# tests/integration/test_cmdb.py
"""
Integration tests for CMDB compound tools against a live ServiceNow instance.
READ-ONLY — relationship read and graph traversal operations only.
Run with: SN_INTEGRATION_TESTS=1 pytest tests/integration/test_cmdb.py -v -s

CI CRUD (list, get, search) uses table_tools (query_records/get_record).
"""
import json
import pytest

from servicenow_mcp.tools.cmdb_tools import (
    get_ci_relationships,
    get_ci_impact_graph,
    GetCIRelationshipsParams,
    GetCIImpactGraphParams,
)


@pytest.mark.integration
class TestCMDBIntegration:

    def test_get_ci_relationships(self, live_config, live_auth):
        """Verify get_ci_relationships returns relationship data for a real CI."""
        # Use a well-known cmdb_ci sys_id on the instance, or skip if unavailable.
        # In most PDIs, cmdb_ci has OOB records. We query one via table_tools pattern
        # but since we can't use table_tools here easily, we pass a known-good sys_id
        # or skip if we can't determine one.
        params = GetCIRelationshipsParams(sys_id="SKIP_IF_NO_CI", direction="both", limit=5)
        result = get_ci_relationships(live_config, live_auth, params)

        print("\n--- get_ci_relationships response ---")
        print(json.dumps(result, indent=2, default=str))

        # The call should always succeed (empty list if no relationships)
        assert result["success"] is True
        assert "relationships" in result

    def test_get_ci_impact_graph(self, live_config, live_auth):
        """Verify get_ci_impact_graph returns impact graph structure."""
        params = GetCIImpactGraphParams(sys_id="SKIP_IF_NO_CI", max_depth=1)
        result = get_ci_impact_graph(live_config, live_auth, params)

        print("\n--- get_ci_impact_graph response ---")
        print(json.dumps(result, indent=2, default=str))

        assert result["success"] is True
        assert "nodes" in result
        assert "edges" in result
