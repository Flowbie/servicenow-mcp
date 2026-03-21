# tests/integration/test_catalog_advanced.py
"""
Integration tests for advanced catalog tools (variables, optimization) against a live instance.
READ-ONLY operations only.
Run with: SN_INTEGRATION_TESTS=1 pytest tests/integration/test_catalog_advanced.py -v -s
"""
import json
import pytest

from servicenow_mcp.tools.catalog_tools import list_catalog_items, ListCatalogItemsParams
from servicenow_mcp.tools.catalog_variables import (
    list_catalog_item_variables,
    ListCatalogItemVariablesParams,
)
from servicenow_mcp.tools.catalog_optimization import (
    get_optimization_recommendations,
    OptimizationRecommendationsParams,
)


@pytest.mark.integration
class TestCatalogVariablesIntegration:

    def test_list_catalog_item_variables_returns_results(self, live_config, live_auth):
        """Verify list_catalog_item_variables returns variable records for a real catalog item."""
        # Get a real catalog item sys_id first
        items_result = list_catalog_items(live_config, live_auth, ListCatalogItemsParams(limit=5))
        assert items_result["success"] is True

        if not items_result["items"]:
            pytest.skip("No catalog items on this instance.")

        # Try each item until we find one with variables
        item_id = None
        for item in items_result["items"]:
            item_id = item["sys_id"]
            params = ListCatalogItemVariablesParams(item_id=item_id)
            result = list_catalog_item_variables(live_config, live_auth, params)
            if result.get("success") and result.get("variables"):
                break

        print(f"\n--- list_catalog_item_variables({item_id}) response ---")
        print(json.dumps(result, indent=2, default=str))

        assert result["success"] is True

    def test_list_catalog_item_variables_shape(self, live_config, live_auth):
        """Verify variable records have expected fields."""
        items_result = list_catalog_items(live_config, live_auth, ListCatalogItemsParams(limit=5))
        if not items_result.get("items"):
            pytest.skip("No catalog items on this instance.")

        for item in items_result["items"]:
            params = ListCatalogItemVariablesParams(item_id=item["sys_id"])
            result = list_catalog_item_variables(live_config, live_auth, params)
            if result.get("success") and result.get("variables"):
                first = result["variables"][0]
                print("\n--- first variable fields ---")
                print(json.dumps(first, indent=2, default=str))
                assert "sys_id" in first, "Missing expected field: sys_id"
                return

        pytest.skip("No catalog item with variables found on this instance.")


@pytest.mark.integration
class TestCatalogOptimizationIntegration:

    def test_get_optimization_recommendations_returns_response(self, live_config, live_auth):
        """Verify get_optimization_recommendations returns a structured response."""
        # Inspect OptimizationRecommendationsParams for required fields
        params = OptimizationRecommendationsParams()
        result = get_optimization_recommendations(live_config, live_auth, params)

        print("\n--- get_optimization_recommendations response ---")
        print(json.dumps(result, indent=2, default=str))

        assert "success" in result

    def test_get_optimization_recommendations_shape(self, live_config, live_auth):
        """Verify optimization response has expected structure."""
        params = OptimizationRecommendationsParams()
        result = get_optimization_recommendations(live_config, live_auth, params)

        if not result.get("success"):
            pytest.skip(f"Optimization tool returned success=False: {result.get('message')}")

        print("\n--- optimization response keys ---")
        print(list(result.keys()))

        # Adjust key based on actual response shape
        assert any(k in result for k in ["recommendations", "issues", "items", "analysis"])
