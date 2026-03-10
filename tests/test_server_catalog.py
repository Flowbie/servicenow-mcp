"""
Tests for the ServiceNow MCP server integration with catalog functionality.
"""

import unittest
from unittest.mock import MagicMock, patch

from servicenow_mcp.server import ServiceNowMCP
from servicenow_mcp.tools.catalog_tools import (
    GetCatalogItemParams,
    ListCatalogCategoriesParams,
    ListCatalogItemsParams,
)
from servicenow_mcp.tools.catalog_tools import (
    get_catalog_item as get_catalog_item_tool,
)
from servicenow_mcp.tools.catalog_tools import (
    list_catalog_categories as list_catalog_categories_tool,
)
from servicenow_mcp.tools.catalog_tools import (
    list_catalog_items as list_catalog_items_tool,
)
from servicenow_mcp.utils.tool_utils import get_tool_definitions
from servicenow_mcp.tools.knowledge_base import (
    create_category as create_kb_category,
    list_categories as list_kb_categories,
)


class TestServerCatalog(unittest.TestCase):
    """Test cases for the server integration with catalog functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.config = {
            "instance_url": "https://example.service-now.com",
            "auth": {
                "type": "basic",
                "basic": {
                    "username": "admin",
                    "password": "password",
                },
            },
        }
        self.server = ServiceNowMCP(self.config)
        self.tool_definitions = get_tool_definitions(create_kb_category, list_kb_categories)

    @unittest.skip("requires resources module — see story 7.2")
    def test_register_catalog_resources(self):
        """Test that catalog resources are registered correctly."""
        self.server._register_resources()
        resource_calls = self.server.mcp_server.resource.call_args_list
        resource_paths = [call[0][0] for call in resource_calls]
        self.assertIn("catalog://items", resource_paths)
        self.assertIn("catalog://categories", resource_paths)
        self.assertIn("catalog://{item_id}", resource_paths)

    def test_catalog_tools_registered(self):
        """Test that catalog tools are present in get_tool_definitions."""
        tool_names = set(self.tool_definitions.keys())
        self.assertIn("list_catalog_items", tool_names)
        self.assertIn("get_catalog_item", tool_names)
        self.assertIn("list_catalog_categories", tool_names)

    @patch("servicenow_mcp.tools.catalog_tools.list_catalog_items")
    def test_list_catalog_items_tool(self, mock_list_catalog_items):
        """Test the list_catalog_items tool is callable via tool_definitions."""
        mock_list_catalog_items.return_value = {
            "success": True,
            "message": "Retrieved 1 catalog items",
            "items": [{"sys_id": "item1", "name": "Laptop"}],
        }
        self.assertIn("list_catalog_items", self.tool_definitions)

    @patch("servicenow_mcp.tools.catalog_tools.get_catalog_item")
    def test_get_catalog_item_tool(self, mock_get_catalog_item):
        """Test the get_catalog_item tool is callable via tool_definitions."""
        mock_get_catalog_item.return_value = {
            "success": True,
            "message": "Retrieved catalog item: Laptop",
            "data": {"sys_id": "item1", "name": "Laptop"},
        }
        self.assertIn("get_catalog_item", self.tool_definitions)

    @patch("servicenow_mcp.tools.catalog_tools.list_catalog_categories")
    def test_list_catalog_categories_tool(self, mock_list_catalog_categories):
        """Test the list_catalog_categories tool is callable via tool_definitions."""
        mock_list_catalog_categories.return_value = {
            "success": True,
            "message": "Retrieved 1 catalog categories",
            "categories": [{"sys_id": "cat1", "title": "Hardware"}],
        }
        self.assertIn("list_catalog_categories", self.tool_definitions)


if __name__ == "__main__":
    unittest.main()
