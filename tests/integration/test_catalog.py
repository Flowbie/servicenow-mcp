# tests/integration/test_catalog.py
"""
Integration tests for catalog tools against a live ServiceNow instance.
Run with: SN_INTEGRATION_TESTS=1 pytest tests/integration/test_catalog.py -v -s
"""
import json
import pytest

from servicenow_mcp.tools.catalog_tools import (
    list_catalogs,
    list_catalog_items,
    get_catalog_item,
    ListCatalogsParams,
    ListCatalogItemsParams,
    GetCatalogItemParams,
)


@pytest.mark.integration
class TestCatalogIntegration:

    def test_list_catalogs(self, live_config, live_auth):
        """Verify catalogs are returned from the live instance."""
        params = ListCatalogsParams()
        result = list_catalogs(live_config, live_auth, params)

        print("\n--- list_catalogs response ---")
        print(json.dumps(result, indent=2, default=str))

        assert result["success"] is True, f"Expected success, got: {result.get('message')}"
        assert "catalogs" in result
        assert isinstance(result["catalogs"], list)

    def test_list_catalog_items(self, live_config, live_auth):
        """Verify catalog items are returned."""
        params = ListCatalogItemsParams(limit=5)
        result = list_catalog_items(live_config, live_auth, params)

        print("\n--- list_catalog_items response ---")
        print(json.dumps(result, indent=2, default=str))

        assert result["success"] is True, f"Expected success, got: {result.get('message')}"
        assert "items" in result
        assert isinstance(result["items"], list)

    def test_catalog_item_shape(self, live_config, live_auth):
        """Verify each catalog item has expected fields."""
        params = ListCatalogItemsParams(limit=3)
        result = list_catalog_items(live_config, live_auth, params)

        assert result["success"] is True
        items = result["items"]

        if not items:
            pytest.skip("No catalog items found on this instance.")

        first = items[0]
        print("\n--- first catalog item fields ---")
        print(json.dumps(first, indent=2, default=str))

        for field in ["sys_id", "name"]:
            assert field in first, f"Missing expected field: {field}"

    def test_get_catalog_item(self, live_config, live_auth):
        """Verify get_catalog_item returns full item details.

        Note: get_catalog_item returns a CatalogResponse Pydantic model, not a plain
        dict. Access result fields via attribute access (.success, .data, .message).
        """
        list_result = list_catalog_items(live_config, live_auth, ListCatalogItemsParams(limit=1))
        assert list_result["success"] is True

        if not list_result["items"]:
            pytest.skip("No catalog items on this instance.")

        sys_id = list_result["items"][0]["sys_id"]

        params = GetCatalogItemParams(item_id=sys_id)
        result = get_catalog_item(live_config, live_auth, params)

        # get_catalog_item returns a CatalogResponse Pydantic model
        print(f"\n--- get_catalog_item({sys_id}) response ---")
        print(json.dumps(result.model_dump(), indent=2, default=str))

        assert result.success is True, f"Expected success, got: {result.message}"
        assert result.data is not None, "Expected data payload, got None"
        assert result.data["sys_id"] == sys_id

    def test_list_catalog_items_active_filter(self, live_config, live_auth):
        """Verify active=True filter runs without error."""
        params = ListCatalogItemsParams(limit=5, active=True)
        result = list_catalog_items(live_config, live_auth, params)

        print("\n--- list_catalog_items(active=True) response ---")
        print(json.dumps(result, indent=2, default=str))

        assert result["success"] is True
