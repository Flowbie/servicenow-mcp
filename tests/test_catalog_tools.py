"""
Tests for the ServiceNow MCP catalog tools.

Only compound functions remain: move_catalog_items.
CRUD functions (list, get, create, update, delete) have been removed from the module.
"""

import unittest
from unittest.mock import MagicMock, patch

import requests

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.catalog_tools import (
    MoveCatalogItemsParams,
    move_catalog_items,
)
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig


class TestCatalogTools(unittest.TestCase):
    """Test cases for the catalog tools."""

    def setUp(self):
        """Set up test fixtures."""
        self.config = ServerConfig(
            instance_url="https://example.service-now.com",
            auth=AuthConfig(
                type=AuthType.BASIC,
                basic=BasicAuthConfig(username="admin", password="password"),
            ),
        )

        self.auth_manager = MagicMock(spec=AuthManager)
        self.auth_manager.get_headers.return_value = {"Authorization": "Basic YWRtaW46cGFzc3dvcmQ="}

    # --- move_catalog_items tests ---

    @patch("servicenow_mcp.tools.catalog_tools.requests.patch")
    def test_move_catalog_items(self, mock_patch):
        """Test moving catalog items."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": {"sys_id": "item_id", "category": "target_category_id"}}
        mock_patch.return_value = mock_response

        params = MoveCatalogItemsParams(
            item_ids=["item1", "item2", "item3"],
            target_category_id="target_category_id",
        )
        result = move_catalog_items(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        self.assertEqual(result["moved_count"], 3)

        self.assertEqual(mock_patch.call_count, 3)
        for i, call in enumerate(mock_patch.call_args_list):
            args, kwargs = call
            self.assertEqual(
                args[0],
                f"https://example.service-now.com/api/now/table/sc_cat_item/{params.item_ids[i]}"
            )
            self.assertEqual(kwargs["json"]["category"], "target_category_id")

    @patch("servicenow_mcp.tools.catalog_tools.requests.patch")
    def test_move_catalog_items_partial_failure(self, mock_patch):
        """Test moving catalog items where some fail."""
        success_response = MagicMock()
        success_response.raise_for_status = MagicMock()
        success_response.json.return_value = {"result": {"sys_id": "item1", "category": "target"}}

        fail_response = MagicMock()
        fail_response.raise_for_status.side_effect = requests.exceptions.RequestException("Not found")

        mock_patch.side_effect = [success_response, fail_response]

        params = MoveCatalogItemsParams(
            item_ids=["item1", "item2"],
            target_category_id="target_category_id",
        )
        result = move_catalog_items(self.config, self.auth_manager, params)

        # Partial success still returns success=True
        self.assertTrue(result["success"])
        self.assertEqual(result["moved_count"], 1)
        self.assertIn("failed_items", result)

    @patch("servicenow_mcp.tools.catalog_tools.requests.patch")
    def test_move_catalog_items_all_fail(self, mock_patch):
        """Test moving catalog items where all fail."""
        mock_patch.side_effect = requests.exceptions.RequestException("Error")

        params = MoveCatalogItemsParams(
            item_ids=["item1", "item2"],
            target_category_id="target_category_id",
        )
        result = move_catalog_items(self.config, self.auth_manager, params)

        self.assertFalse(result["success"])
        self.assertIn("Failed to move any catalog items", result["message"])

    @patch("servicenow_mcp.tools.catalog_tools.requests.patch")
    def test_move_catalog_items_single_item(self, mock_patch):
        """Test moving a single catalog item."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"result": {"sys_id": "item1", "category": "target"}}
        mock_patch.return_value = mock_response

        params = MoveCatalogItemsParams(
            item_ids=["item1"],
            target_category_id="new_category",
        )
        result = move_catalog_items(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        self.assertEqual(result["moved_count"], 1)
        mock_patch.assert_called_once()


if __name__ == "__main__":
    unittest.main()
