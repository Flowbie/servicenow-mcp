"""
Service Catalog tools for the ServiceNow MCP server.

Compound functions only. CRUD operations (list, get, create, update, delete catalog
items/categories/catalogs) have been removed — use the generic table_tools
(query_records, get_record, create_record, update_record, delete_record) with
the catalog architecture blueprint instead.
"""

import logging
from typing import List

import requests
from pydantic import BaseModel, Field

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.utils.config import ServerConfig

logger = logging.getLogger(__name__)


class MoveCatalogItemsParams(BaseModel):
    """Parameters for moving catalog items between categories."""

    item_ids: List[str] = Field(..., description="List of catalog item IDs to move")
    target_category_id: str = Field(..., description="Target category ID to move items to")


def move_catalog_items(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: MoveCatalogItemsParams,
) -> dict:
    """
    Move catalog items to a different category.

    Args:
        config: Server configuration
        auth_manager: Authentication manager
        params: Parameters for moving catalog items

    Returns:
        Response containing the result of the operation
    """
    logger.info(f"Moving {len(params.item_ids)} catalog items to category: {params.target_category_id}")

    # Build the API URL
    url = f"{config.instance_url}/api/now/table/sc_cat_item"

    # Make the API request for each item
    headers = auth_manager.get_headers()
    headers["Accept"] = "application/json"
    headers["Content-Type"] = "application/json"

    success_count = 0
    failed_items = []

    try:
        for item_id in params.item_ids:
            item_url = f"{url}/{item_id}"
            body = {
                "category": params.target_category_id
            }

            try:
                response = requests.patch(item_url, headers=headers, json=body)
                response.raise_for_status()
                success_count += 1
            except requests.exceptions.RequestException as e:
                logger.error(f"Error moving catalog item {item_id}: {str(e)}")
                failed_items.append({"item_id": item_id, "error": str(e)})

        # Prepare the response
        if success_count == len(params.item_ids):
            return {
                "success": True,
                "message": f"Successfully moved {success_count} catalog items to category {params.target_category_id}",
                "moved_count": success_count,
            }
        elif success_count > 0:
            return {
                "success": True,
                "message": f"Partially moved catalog items. {success_count} succeeded, {len(failed_items)} failed.",
                "moved_count": success_count,
                "failed_items": failed_items,
            }
        else:
            return {
                "success": False,
                "message": "Failed to move any catalog items",
                "failed_items": failed_items,
            }

    except Exception as e:
        logger.error(f"Error moving catalog items: {str(e)}")
        return {"success": False, "message": f"Error moving catalog items: {str(e)}"}
