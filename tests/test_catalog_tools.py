"""
Tests for the ServiceNow MCP catalog tools.
"""

import unittest
from unittest.mock import MagicMock, patch

import requests

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.catalog_tools import (
    GetCatalogItemParams,
    ListCatalogCategoriesParams,
    ListCatalogItemsParams,
    CreateCatalogCategoryParams,
    UpdateCatalogCategoryParams,
    MoveCatalogItemsParams,
    get_catalog_item,
    get_catalog_item_variables,
    list_catalog_categories,
    list_catalog_items,
    create_catalog_category,
    update_catalog_category,
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

    # --- list_catalog_items tests ---

    @patch("servicenow_mcp.tools.catalog_tools.requests.get")
    def test_list_catalog_items(self, mock_get):
        """Test listing catalog items."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": [
                {
                    "sys_id": "item1",
                    "name": "Laptop",
                    "short_description": "Request a new laptop",
                    "category": "Hardware",
                    "price": "1000",
                    "picture": "laptop.jpg",
                    "active": "true",
                    "order": "100",
                }
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        params = ListCatalogItemsParams(
            limit=10,
            offset=0,
            category="Hardware",
            query="laptop",
            active=True,
        )
        result = list_catalog_items(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        self.assertEqual(len(result["items"]), 1)
        self.assertEqual(result["items"][0]["name"], "Laptop")
        self.assertEqual(result["items"][0]["category"], "Hardware")

        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        self.assertEqual(args[0], "https://example.service-now.com/api/now/table/sc_cat_item")
        self.assertEqual(kwargs["params"]["sysparm_limit"], 10)
        self.assertEqual(kwargs["params"]["sysparm_offset"], 0)
        self.assertIn("sysparm_query", kwargs["params"])
        self.assertIn("active=true", kwargs["params"]["sysparm_query"])
        self.assertIn("category=Hardware", kwargs["params"]["sysparm_query"])
        self.assertIn("short_descriptionLIKElaptop^ORnameLIKElaptop", kwargs["params"]["sysparm_query"])

    @patch("servicenow_mcp.tools.catalog_tools.requests.get")
    def test_list_catalog_items_empty_results(self, mock_get):
        """Test listing catalog items when no items are returned."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": []}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        params = ListCatalogItemsParams(limit=10, offset=0)
        result = list_catalog_items(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        self.assertEqual(len(result["items"]), 0)
        self.assertEqual(result["total"], 0)

    @patch("servicenow_mcp.tools.catalog_tools.requests.get")
    def test_list_catalog_items_error(self, mock_get):
        """Test listing catalog items with an error."""
        mock_get.side_effect = requests.exceptions.RequestException("Error")

        params = ListCatalogItemsParams(limit=10, offset=0)
        result = list_catalog_items(self.config, self.auth_manager, params)

        self.assertFalse(result["success"])
        self.assertEqual(len(result["items"]), 0)
        self.assertIn("Error", result["message"])

    @patch("servicenow_mcp.tools.catalog_tools.requests.get")
    def test_list_catalog_items_network_error(self, mock_get):
        """Test listing catalog items with a network-level connection error."""
        mock_get.side_effect = requests.exceptions.ConnectionError("Connection refused")

        params = ListCatalogItemsParams(limit=5, offset=0)
        result = list_catalog_items(self.config, self.auth_manager, params)

        self.assertFalse(result["success"])
        self.assertEqual(len(result["items"]), 0)
        self.assertIn("Error listing catalog items", result["message"])

    @patch("servicenow_mcp.tools.catalog_tools.requests.get")
    def test_list_catalog_items_no_query_filter(self, mock_get):
        """Test listing catalog items with only active filter (no query or category)."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": [{"sys_id": "item1", "name": "Mouse"}]}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        params = ListCatalogItemsParams(limit=10, offset=0, active=True)
        result = list_catalog_items(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        args, kwargs = mock_get.call_args
        self.assertIn("sysparm_query", kwargs["params"])
        self.assertEqual(kwargs["params"]["sysparm_query"], "active=true")

    # --- get_catalog_item tests ---

    @patch("servicenow_mcp.tools.catalog_tools.get_catalog_item_variables")
    @patch("servicenow_mcp.tools.catalog_tools.requests.get")
    def test_get_catalog_item(self, mock_get, mock_get_variables):
        """Test getting a specific catalog item."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": {
                "sys_id": "item1",
                "name": "Laptop",
                "short_description": "Request a new laptop",
                "description": "Request a new laptop for work",
                "category": "Hardware",
                "price": "1000",
                "picture": "laptop.jpg",
                "active": "true",
                "order": "100",
                "delivery_time": "3 days",
                "availability": "In Stock",
            }
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        mock_get_variables.return_value = [
            {
                "sys_id": "var1",
                "name": "model",
                "label": "Laptop Model",
                "type": "string",
                "mandatory": "true",
                "default_value": "MacBook Pro",
                "help_text": "Select the laptop model",
                "order": "100",
            }
        ]

        params = GetCatalogItemParams(item_id="item1")
        result = get_catalog_item(self.config, self.auth_manager, params)

        self.assertTrue(result.success)
        self.assertEqual(result.data["name"], "Laptop")
        self.assertEqual(result.data["category"], "Hardware")
        self.assertEqual(len(result.data["variables"]), 1)
        self.assertEqual(result.data["variables"][0]["name"], "model")

        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        self.assertEqual(args[0], "https://example.service-now.com/api/now/table/sc_cat_item/item1")

    @patch("servicenow_mcp.tools.catalog_tools.requests.get")
    def test_get_catalog_item_not_found(self, mock_get):
        """Test getting a catalog item that doesn't exist."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": {}}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        params = GetCatalogItemParams(item_id="nonexistent")
        result = get_catalog_item(self.config, self.auth_manager, params)

        self.assertFalse(result.success)
        self.assertIn("not found", result.message)
        self.assertIsNone(result.data)

    @patch("servicenow_mcp.tools.catalog_tools.requests.get")
    def test_get_catalog_item_error(self, mock_get):
        """Test getting a catalog item with an error."""
        mock_get.side_effect = requests.exceptions.RequestException("Error")

        params = GetCatalogItemParams(item_id="item1")
        result = get_catalog_item(self.config, self.auth_manager, params)

        self.assertFalse(result.success)
        self.assertIn("Error", result.message)
        self.assertIsNone(result.data)

    @patch("servicenow_mcp.tools.catalog_tools.requests.get")
    def test_get_catalog_item_network_error(self, mock_get):
        """Test getting a catalog item with a network-level error."""
        mock_get.side_effect = requests.exceptions.ConnectionError("Connection refused")

        params = GetCatalogItemParams(item_id="item1")
        result = get_catalog_item(self.config, self.auth_manager, params)

        self.assertFalse(result.success)
        self.assertIsNone(result.data)
        self.assertIn("Error getting catalog item", result.message)

    @patch("servicenow_mcp.tools.catalog_tools.get_catalog_item_variables")
    @patch("servicenow_mcp.tools.catalog_tools.requests.get")
    def test_get_catalog_item_includes_all_fields(self, mock_get, mock_get_variables):
        """Test that get_catalog_item returns all expected fields."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": {
                "sys_id": "item2",
                "name": "Monitor",
                "short_description": "Request a monitor",
                "description": "External display",
                "category": "Hardware",
                "price": "500",
                "picture": "",
                "active": "true",
                "order": "200",
                "delivery_time": "1 day",
                "availability": "In Stock",
            }
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response
        mock_get_variables.return_value = []

        params = GetCatalogItemParams(item_id="item2")
        result = get_catalog_item(self.config, self.auth_manager, params)

        self.assertTrue(result.success)
        expected_fields = ["sys_id", "name", "short_description", "description",
                           "category", "price", "picture", "active", "order",
                           "delivery_time", "availability", "variables"]
        for field in expected_fields:
            self.assertIn(field, result.data, f"Missing field: {field}")

    # --- get_catalog_item_variables tests ---

    @patch("servicenow_mcp.tools.catalog_tools.requests.get")
    def test_get_catalog_item_variables(self, mock_get):
        """Test getting variables for a catalog item."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": [
                {
                    "sys_id": "var1",
                    "name": "model",
                    "question_text": "Laptop Model",
                    "type": "string",
                    "mandatory": "true",
                    "default_value": "MacBook Pro",
                    "help_text": "Select the laptop model",
                    "order": "100",
                }
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = get_catalog_item_variables(self.config, self.auth_manager, "item1")

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "model")
        self.assertEqual(result[0]["label"], "Laptop Model")
        self.assertEqual(result[0]["type"], "string")

        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        self.assertEqual(args[0], "https://example.service-now.com/api/now/table/item_option_new")
        self.assertEqual(kwargs["params"]["sysparm_query"], "cat_item=item1^ORDERBYorder")

    @patch("servicenow_mcp.tools.catalog_tools.requests.get")
    def test_get_catalog_item_variables_error(self, mock_get):
        """Test getting variables for a catalog item with an error."""
        mock_get.side_effect = requests.exceptions.RequestException("Error")

        result = get_catalog_item_variables(self.config, self.auth_manager, "item1")

        self.assertEqual(len(result), 0)

    @patch("servicenow_mcp.tools.catalog_tools.requests.get")
    def test_get_catalog_item_variables_empty(self, mock_get):
        """Test getting variables for an item with no variables."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": []}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = get_catalog_item_variables(self.config, self.auth_manager, "item1")

        self.assertEqual(len(result), 0)

    # --- list_catalog_categories tests ---

    @patch("servicenow_mcp.tools.catalog_tools.requests.get")
    def test_list_catalog_categories(self, mock_get):
        """Test listing catalog categories."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": [
                {
                    "sys_id": "cat1",
                    "title": "Hardware",
                    "description": "Hardware requests",
                    "parent": "",
                    "icon": "hardware.png",
                    "active": "true",
                    "order": "100",
                }
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        params = ListCatalogCategoriesParams(
            limit=10,
            offset=0,
            query="hardware",
            active=True,
        )
        result = list_catalog_categories(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        self.assertEqual(len(result["categories"]), 1)
        self.assertEqual(result["categories"][0]["title"], "Hardware")
        self.assertEqual(result["categories"][0]["description"], "Hardware requests")

        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        self.assertEqual(args[0], "https://example.service-now.com/api/now/table/sc_category")
        self.assertEqual(kwargs["params"]["sysparm_limit"], 10)
        self.assertEqual(kwargs["params"]["sysparm_offset"], 0)
        self.assertIn("sysparm_query", kwargs["params"])
        self.assertIn("active=true", kwargs["params"]["sysparm_query"])
        self.assertIn("titleLIKEhardware^ORdescriptionLIKEhardware", kwargs["params"]["sysparm_query"])

    @patch("servicenow_mcp.tools.catalog_tools.requests.get")
    def test_list_catalog_categories_empty(self, mock_get):
        """Test listing catalog categories when no categories exist."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": []}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        params = ListCatalogCategoriesParams(limit=10, offset=0)
        result = list_catalog_categories(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        self.assertEqual(len(result["categories"]), 0)
        self.assertEqual(result["total"], 0)

    @patch("servicenow_mcp.tools.catalog_tools.requests.get")
    def test_list_catalog_categories_error(self, mock_get):
        """Test listing catalog categories with an error."""
        mock_get.side_effect = requests.exceptions.RequestException("Error")

        params = ListCatalogCategoriesParams(limit=10, offset=0)
        result = list_catalog_categories(self.config, self.auth_manager, params)

        self.assertFalse(result["success"])
        self.assertEqual(len(result["categories"]), 0)
        self.assertIn("Error", result["message"])

    @patch("servicenow_mcp.tools.catalog_tools.requests.get")
    def test_list_catalog_categories_network_error(self, mock_get):
        """Test listing catalog categories with a network-level error."""
        mock_get.side_effect = requests.exceptions.ConnectionError("Connection refused")

        params = ListCatalogCategoriesParams(limit=10, offset=0)
        result = list_catalog_categories(self.config, self.auth_manager, params)

        self.assertFalse(result["success"])
        self.assertIn("Error listing catalog categories", result["message"])

    @patch("servicenow_mcp.tools.catalog_tools.requests.get")
    def test_list_catalog_categories_multiple(self, mock_get):
        """Test listing multiple catalog categories."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": [
                {"sys_id": "cat1", "title": "Hardware", "description": "Hardware requests",
                 "parent": "", "icon": "", "active": "true", "order": "100"},
                {"sys_id": "cat2", "title": "Software", "description": "Software requests",
                 "parent": "", "icon": "", "active": "true", "order": "200"},
                {"sys_id": "cat3", "title": "Services", "description": "Service requests",
                 "parent": "", "icon": "", "active": "true", "order": "300"},
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        params = ListCatalogCategoriesParams(limit=10, offset=0)
        result = list_catalog_categories(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        self.assertEqual(len(result["categories"]), 3)
        self.assertEqual(result["total"], 3)
        titles = [c["title"] for c in result["categories"]]
        self.assertIn("Hardware", titles)
        self.assertIn("Software", titles)
        self.assertIn("Services", titles)

    # --- create_catalog_category tests ---

    @patch("servicenow_mcp.tools.catalog_tools.requests.post")
    def test_create_catalog_category(self, mock_post):
        """Test creating a catalog category."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": {
                "sys_id": "test_sys_id",
                "title": "Test Category",
                "description": "Test Description",
                "parent": "",
                "icon": "icon-test",
                "active": "true",
                "order": "100",
            }
        }
        mock_post.return_value = mock_response

        params = CreateCatalogCategoryParams(
            title="Test Category",
            description="Test Description",
            icon="icon-test",
            active=True,
            order=100,
        )
        result = create_catalog_category(self.config, self.auth_manager, params)

        self.assertTrue(result.success)
        self.assertEqual(result.data["title"], "Test Category")
        self.assertEqual(result.data["sys_id"], "test_sys_id")

        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertEqual(args[0], "https://example.service-now.com/api/now/table/sc_category")
        self.assertEqual(kwargs["json"]["title"], "Test Category")
        self.assertEqual(kwargs["json"]["description"], "Test Description")

    @patch("servicenow_mcp.tools.catalog_tools.requests.post")
    def test_create_catalog_category_minimal(self, mock_post):
        """Test creating a catalog category with only required fields."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": {
                "sys_id": "cat_min",
                "title": "Minimal Category",
                "description": "",
                "parent": "",
                "icon": "",
                "active": "true",
                "order": "",
            }
        }
        mock_post.return_value = mock_response

        params = CreateCatalogCategoryParams(title="Minimal Category")
        result = create_catalog_category(self.config, self.auth_manager, params)

        self.assertTrue(result.success)
        self.assertEqual(result.data["title"], "Minimal Category")

    @patch("servicenow_mcp.tools.catalog_tools.requests.post")
    def test_create_catalog_category_network_error(self, mock_post):
        """Test creating a catalog category with a network error."""
        mock_post.side_effect = requests.exceptions.RequestException("Network error")

        params = CreateCatalogCategoryParams(title="Test Category")
        result = create_catalog_category(self.config, self.auth_manager, params)

        self.assertFalse(result.success)
        self.assertIsNone(result.data)
        self.assertIn("Error creating catalog category", result.message)

    # --- update_catalog_category tests ---

    @patch("servicenow_mcp.tools.catalog_tools.requests.patch")
    def test_update_catalog_category(self, mock_patch):
        """Test updating a catalog category."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": {
                "sys_id": "test_sys_id",
                "title": "Updated Category",
                "description": "Updated Description",
                "parent": "",
                "icon": "icon-test",
                "active": "true",
                "order": "200",
            }
        }
        mock_patch.return_value = mock_response

        params = UpdateCatalogCategoryParams(
            category_id="test_sys_id",
            title="Updated Category",
            description="Updated Description",
            order=200,
        )
        result = update_catalog_category(self.config, self.auth_manager, params)

        self.assertTrue(result.success)
        self.assertEqual(result.data["title"], "Updated Category")
        self.assertEqual(result.data["description"], "Updated Description")
        self.assertEqual(result.data["order"], "200")

        mock_patch.assert_called_once()
        args, kwargs = mock_patch.call_args
        self.assertEqual(args[0], "https://example.service-now.com/api/now/table/sc_category/test_sys_id")
        self.assertEqual(kwargs["json"]["title"], "Updated Category")
        self.assertEqual(kwargs["json"]["description"], "Updated Description")
        self.assertEqual(kwargs["json"]["order"], "200")

    @patch("servicenow_mcp.tools.catalog_tools.requests.patch")
    def test_update_catalog_category_partial_update(self, mock_patch):
        """Test updating a catalog category with only some optional fields."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": {
                "sys_id": "cat_partial",
                "title": "Same Title",
                "description": "New Description",
                "parent": "",
                "icon": "",
                "active": "true",
                "order": "100",
            }
        }
        mock_patch.return_value = mock_response

        # Only provide description, leave other fields as None
        params = UpdateCatalogCategoryParams(
            category_id="cat_partial",
            description="New Description",
        )
        result = update_catalog_category(self.config, self.auth_manager, params)

        self.assertTrue(result.success)
        args, kwargs = mock_patch.call_args
        # Only description should be in the body
        self.assertIn("description", kwargs["json"])
        self.assertNotIn("title", kwargs["json"])
        self.assertNotIn("order", kwargs["json"])

    @patch("servicenow_mcp.tools.catalog_tools.requests.patch")
    def test_update_catalog_category_network_error(self, mock_patch):
        """Test updating a catalog category with a network error."""
        mock_patch.side_effect = requests.exceptions.RequestException("Network error")

        params = UpdateCatalogCategoryParams(
            category_id="test_sys_id",
            title="Updated Category",
        )
        result = update_catalog_category(self.config, self.auth_manager, params)

        self.assertFalse(result.success)
        self.assertIsNone(result.data)
        self.assertIn("Error updating catalog category", result.message)

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

        self.assertTrue(result.success)
        self.assertEqual(result.data["moved_items_count"], 3)

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
        self.assertTrue(result.success)
        self.assertEqual(result.data["moved_items_count"], 1)
        self.assertIn("failed_items", result.data)

    @patch("servicenow_mcp.tools.catalog_tools.requests.patch")
    def test_move_catalog_items_all_fail(self, mock_patch):
        """Test moving catalog items where all fail."""
        mock_patch.side_effect = requests.exceptions.RequestException("Error")

        params = MoveCatalogItemsParams(
            item_ids=["item1", "item2"],
            target_category_id="target_category_id",
        )
        result = move_catalog_items(self.config, self.auth_manager, params)

        self.assertFalse(result.success)
        self.assertIn("Failed to move any catalog items", result.message)

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

        self.assertTrue(result.success)
        self.assertEqual(result.data["moved_items_count"], 1)
        mock_patch.assert_called_once()


if __name__ == "__main__":
    unittest.main()
