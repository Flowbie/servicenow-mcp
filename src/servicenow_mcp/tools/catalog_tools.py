"""
Service Catalog tools for the ServiceNow MCP server.

This module provides tools for querying and viewing the service catalog in ServiceNow.
"""

import logging
from typing import Any, Dict, List, Optional

import requests
from pydantic import BaseModel, Field

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.utils.config import ServerConfig

logger = logging.getLogger(__name__)


class ListCatalogItemsParams(BaseModel):
    """Parameters for listing service catalog items."""
    
    limit: int = Field(10, description="Maximum number of catalog items to return")
    offset: int = Field(0, description="Offset for pagination")
    category: Optional[str] = Field(None, description="Filter by category")
    query: Optional[str] = Field(None, description="Search query for catalog items")
    active: bool = Field(True, description="Whether to only return active catalog items")


class GetCatalogItemParams(BaseModel):
    """Parameters for getting a specific service catalog item."""
    
    item_id: str = Field(..., description="Catalog item ID or sys_id")


class ListCatalogCategoriesParams(BaseModel):
    """Parameters for listing service catalog categories."""
    
    limit: int = Field(10, description="Maximum number of categories to return")
    offset: int = Field(0, description="Offset for pagination")
    query: Optional[str] = Field(None, description="Search query for categories")
    active: bool = Field(True, description="Whether to only return active categories")



class CreateCatalogCategoryParams(BaseModel):
    """Parameters for creating a new service catalog category."""
    
    title: str = Field(..., description="Title of the category")
    description: Optional[str] = Field(None, description="Description of the category")
    parent: Optional[str] = Field(None, description="Parent category sys_id")
    icon: Optional[str] = Field(None, description="Icon for the category")
    active: bool = Field(True, description="Whether the category is active")
    order: Optional[int] = Field(None, description="Order of the category")


class UpdateCatalogCategoryParams(BaseModel):
    """Parameters for updating a service catalog category."""
    
    category_id: str = Field(..., description="Category ID or sys_id")
    title: Optional[str] = Field(None, description="Title of the category")
    description: Optional[str] = Field(None, description="Description of the category")
    parent: Optional[str] = Field(None, description="Parent category sys_id")
    icon: Optional[str] = Field(None, description="Icon for the category")
    active: Optional[bool] = Field(None, description="Whether the category is active")
    order: Optional[int] = Field(None, description="Order of the category")


class MoveCatalogItemsParams(BaseModel):
    """Parameters for moving catalog items between categories."""
    
    item_ids: List[str] = Field(..., description="List of catalog item IDs to move")
    target_category_id: str = Field(..., description="Target category ID to move items to")


def list_catalog_items(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: ListCatalogItemsParams,
) -> Dict[str, Any]:
    """
    List service catalog items from ServiceNow.

    Args:
        config: Server configuration
        auth_manager: Authentication manager
        params: Parameters for listing catalog items

    Returns:
        Dictionary containing catalog items and metadata
    """
    logger.info("Listing service catalog items")
    
    # Build the API URL
    url = f"{config.instance_url}/api/now/table/sc_cat_item"
    
    # Prepare query parameters
    query_params = {
        "sysparm_limit": params.limit,
        "sysparm_offset": params.offset,
        "sysparm_display_value": "true",
        "sysparm_exclude_reference_link": "true",
    }
    
    # Add filters
    filters = []
    if params.active:
        filters.append("active=true")
    if params.category:
        filters.append(f"category={params.category}")
    if params.query:
        filters.append(f"short_descriptionLIKE{params.query}^ORnameLIKE{params.query}")
    
    if filters:
        query_params["sysparm_query"] = "^".join(filters)
    
    # Make the API request
    headers = auth_manager.get_headers()
    headers["Accept"] = "application/json"
    
    try:
        response = requests.get(url, headers=headers, params=query_params)
        response.raise_for_status()
        
        # Process the response
        result = response.json()
        items = result.get("result", [])
        
        # Format the response
        formatted_items = []
        for item in items:
            formatted_items.append({
                "sys_id": item.get("sys_id", ""),
                "name": item.get("name", ""),
                "short_description": item.get("short_description", ""),
                "category": item.get("category", ""),
                "price": item.get("price", ""),
                "picture": item.get("picture", ""),
                "active": item.get("active", ""),
                "order": item.get("order", ""),
            })
        
        return {
            "success": True,
            "message": f"Retrieved {len(formatted_items)} catalog items",
            "items": formatted_items,
            "total": len(formatted_items),
            "limit": params.limit,
            "offset": params.offset,
        }
    
    except requests.exceptions.RequestException as e:
        logger.error(f"Error listing catalog items: {str(e)}")
        return {
            "success": False,
            "message": f"Error listing catalog items: {str(e)}",
            "items": [],
            "total": 0,
            "limit": params.limit,
            "offset": params.offset,
        }


def get_catalog_item(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: GetCatalogItemParams,
) -> dict:
    """
    Get a specific service catalog item from ServiceNow.

    Args:
        config: Server configuration
        auth_manager: Authentication manager
        params: Parameters for getting a catalog item

    Returns:
        Response containing the catalog item details
    """
    logger.info(f"Getting service catalog item: {params.item_id}")
    
    # Build the API URL
    url = f"{config.instance_url}/api/now/table/sc_cat_item/{params.item_id}"
    
    # Prepare query parameters
    query_params = {
        "sysparm_display_value": "true",
        "sysparm_exclude_reference_link": "true",
    }
    
    # Make the API request
    headers = auth_manager.get_headers()
    headers["Accept"] = "application/json"
    
    try:
        response = requests.get(url, headers=headers, params=query_params)
        response.raise_for_status()
        
        # Process the response
        result = response.json()
        item = result.get("result", {})
        
        if not item:
            return {"success": False, "message": f"Catalog item not found: {params.item_id}"}
        
        # Format the response
        formatted_item = {
            "sys_id": item.get("sys_id", ""),
            "name": item.get("name", ""),
            "short_description": item.get("short_description", ""),
            "description": item.get("description", ""),
            "category": item.get("category", ""),
            "price": item.get("price", ""),
            "picture": item.get("picture", ""),
            "active": item.get("active", ""),
            "order": item.get("order", ""),
            "delivery_time": item.get("delivery_time", ""),
            "availability": item.get("availability", ""),
            "variables": get_catalog_item_variables(config, auth_manager, params.item_id),
        }
        
        return {
            "success": True,
            "message": f"Retrieved catalog item: {item.get('name', '')}",
            "item": formatted_item,
        }

    except requests.exceptions.RequestException as e:
        logger.error(f"Error getting catalog item: {str(e)}")
        return {"success": False, "message": f"Error getting catalog item: {str(e)}"}


def get_catalog_item_variables(
    config: ServerConfig,
    auth_manager: AuthManager,
    item_id: str,
) -> List[Dict[str, Any]]:
    """
    Get variables for a specific service catalog item.

    Args:
        config: Server configuration
        auth_manager: Authentication manager
        item_id: Catalog item ID or sys_id

    Returns:
        List of variables for the catalog item
    """
    logger.info(f"Getting variables for catalog item: {item_id}")
    
    # Build the API URL
    url = f"{config.instance_url}/api/now/table/item_option_new"
    
    # Prepare query parameters
    query_params = {
        "sysparm_query": f"cat_item={item_id}^ORDERBYorder",
        "sysparm_display_value": "true",
        "sysparm_exclude_reference_link": "true",
    }
    
    # Make the API request
    headers = auth_manager.get_headers()
    headers["Accept"] = "application/json"
    
    try:
        response = requests.get(url, headers=headers, params=query_params)
        response.raise_for_status()
        
        # Process the response
        result = response.json()
        variables = result.get("result", [])
        
        # Format the response
        formatted_variables = []
        for variable in variables:
            formatted_variables.append({
                "sys_id": variable.get("sys_id", ""),
                "name": variable.get("name", ""),
                "label": variable.get("question_text", ""),
                "type": variable.get("type", ""),
                "mandatory": variable.get("mandatory", ""),
                "default_value": variable.get("default_value", ""),
                "help_text": variable.get("help_text", ""),
                "order": variable.get("order", ""),
            })
        
        return formatted_variables
    
    except requests.exceptions.RequestException as e:
        logger.error(f"Error getting catalog item variables: {str(e)}")
        return []


def list_catalog_categories(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: ListCatalogCategoriesParams,
) -> Dict[str, Any]:
    """
    List service catalog categories from ServiceNow.

    Args:
        config: Server configuration
        auth_manager: Authentication manager
        params: Parameters for listing catalog categories

    Returns:
        Dictionary containing catalog categories and metadata
    """
    logger.info("Listing service catalog categories")
    
    # Build the API URL
    url = f"{config.instance_url}/api/now/table/sc_category"
    
    # Prepare query parameters
    query_params = {
        "sysparm_limit": params.limit,
        "sysparm_offset": params.offset,
        "sysparm_display_value": "true",
        "sysparm_exclude_reference_link": "true",
    }
    
    # Add filters
    filters = []
    if params.active:
        filters.append("active=true")
    if params.query:
        filters.append(f"titleLIKE{params.query}^ORdescriptionLIKE{params.query}")
    
    if filters:
        query_params["sysparm_query"] = "^".join(filters)
    
    # Make the API request
    headers = auth_manager.get_headers()
    headers["Accept"] = "application/json"
    
    try:
        response = requests.get(url, headers=headers, params=query_params)
        response.raise_for_status()
        
        # Process the response
        result = response.json()
        categories = result.get("result", [])
        
        # Format the response
        formatted_categories = []
        for category in categories:
            formatted_categories.append({
                "sys_id": category.get("sys_id", ""),
                "title": category.get("title", ""),
                "description": category.get("description", ""),
                "parent": category.get("parent", ""),
                "icon": category.get("icon", ""),
                "active": category.get("active", ""),
                "order": category.get("order", ""),
            })
        
        return {
            "success": True,
            "message": f"Retrieved {len(formatted_categories)} catalog categories",
            "categories": formatted_categories,
            "total": len(formatted_categories),
            "limit": params.limit,
            "offset": params.offset,
        }
    
    except requests.exceptions.RequestException as e:
        logger.error(f"Error listing catalog categories: {str(e)}")
        return {
            "success": False,
            "message": f"Error listing catalog categories: {str(e)}",
            "categories": [],
            "total": 0,
            "limit": params.limit,
            "offset": params.offset,
        }


def create_catalog_category(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: CreateCatalogCategoryParams,
) -> dict:
    """
    Create a new service catalog category in ServiceNow.

    Args:
        config: Server configuration
        auth_manager: Authentication manager
        params: Parameters for creating a catalog category

    Returns:
        Response containing the result of the operation
    """
    logger.info("Creating new service catalog category")
    
    # Build the API URL
    url = f"{config.instance_url}/api/now/table/sc_category"
    
    # Prepare request body
    body = {
        "title": params.title,
    }
    
    if params.description is not None:
        body["description"] = params.description
    if params.parent is not None:
        body["parent"] = params.parent
    if params.icon is not None:
        body["icon"] = params.icon
    if params.active is not None:
        body["active"] = str(params.active).lower()
    if params.order is not None:
        body["order"] = str(params.order)
    
    # Make the API request
    headers = auth_manager.get_headers()
    headers["Accept"] = "application/json"
    headers["Content-Type"] = "application/json"
    
    try:
        response = requests.post(url, headers=headers, json=body)
        response.raise_for_status()
        
        # Process the response
        result = response.json()
        category = result.get("result", {})
        
        # Format the response
        formatted_category = {
            "sys_id": category.get("sys_id", ""),
            "title": category.get("title", ""),
            "description": category.get("description", ""),
            "parent": category.get("parent", ""),
            "icon": category.get("icon", ""),
            "active": category.get("active", ""),
            "order": category.get("order", ""),
        }
        
        return {
            "success": True,
            "message": f"Created catalog category: {params.title}",
            "category": formatted_category,
        }

    except requests.exceptions.RequestException as e:
        logger.error(f"Error creating catalog category: {str(e)}")
        return {"success": False, "message": f"Error creating catalog category: {str(e)}"}


def update_catalog_category(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: UpdateCatalogCategoryParams,
) -> dict:
    """
    Update an existing service catalog category in ServiceNow.

    Args:
        config: Server configuration
        auth_manager: Authentication manager
        params: Parameters for updating a catalog category

    Returns:
        Response containing the result of the operation
    """
    logger.info(f"Updating service catalog category: {params.category_id}")
    
    # Build the API URL
    url = f"{config.instance_url}/api/now/table/sc_category/{params.category_id}"
    
    # Prepare request body with only the provided parameters
    body = {}
    if params.title is not None:
        body["title"] = params.title
    if params.description is not None:
        body["description"] = params.description
    if params.parent is not None:
        body["parent"] = params.parent
    if params.icon is not None:
        body["icon"] = params.icon
    if params.active is not None:
        body["active"] = str(params.active).lower()
    if params.order is not None:
        body["order"] = str(params.order)
    
    # Make the API request
    headers = auth_manager.get_headers()
    headers["Accept"] = "application/json"
    headers["Content-Type"] = "application/json"
    
    try:
        response = requests.patch(url, headers=headers, json=body)
        response.raise_for_status()
        
        # Process the response
        result = response.json()
        category = result.get("result", {})
        
        # Format the response
        formatted_category = {
            "sys_id": category.get("sys_id", ""),
            "title": category.get("title", ""),
            "description": category.get("description", ""),
            "parent": category.get("parent", ""),
            "icon": category.get("icon", ""),
            "active": category.get("active", ""),
            "order": category.get("order", ""),
        }
        
        return {
            "success": True,
            "message": f"Updated catalog category: {params.category_id}",
            "category": formatted_category,
        }

    except requests.exceptions.RequestException as e:
        logger.error(f"Error updating catalog category: {str(e)}")
        return {"success": False, "message": f"Error updating catalog category: {str(e)}"}


class UpdateCatalogItemParams(BaseModel):
    """Parameters for updating a catalog item."""

    item_id: str
    name: Optional[str] = None
    short_description: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    price: Optional[str] = None
    active: Optional[bool] = None
    order: Optional[int] = None


def update_catalog_item(
    config: ServerConfig, auth_manager: AuthManager, params: UpdateCatalogItemParams
) -> dict:
    """
    Update a catalog item.

    Args:
        config: The server configuration
        auth_manager: The authentication manager
        params: The parameters for updating the catalog item

    Returns:
        A dictionary containing the result of the update operation
    """
    logger.info(f"Updating catalog item: {params.item_id}")

    try:
        # Build the request body with only the provided parameters
        body = {}
        if params.name is not None:
            body["name"] = params.name
        if params.short_description is not None:
            body["short_description"] = params.short_description
        if params.description is not None:
            body["description"] = params.description
        if params.category is not None:
            body["category"] = params.category
        if params.price is not None:
            body["price"] = params.price
        if params.active is not None:
            body["active"] = str(params.active).lower()
        if params.order is not None:
            body["order"] = str(params.order)

        # Make the API request
        url = f"{config.instance_url}/api/now/table/sc_cat_item/{params.item_id}"
        headers = auth_manager.get_headers()
        headers["Content-Type"] = "application/json"

        response = requests.patch(url, headers=headers, json=body)
        response.raise_for_status()

        return {
            "success": True,
            "message": "Catalog item updated successfully",
            "item": response.json()["result"],
        }

    except Exception as e:
        logger.error(f"Error updating catalog item: {e}")
        return {
            "success": False,
            "message": f"Error updating catalog item: {str(e)}",
        }


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


class CreateCatalogItemParams(BaseModel):
    """Parameters for creating a catalog item."""

    name: str = Field(..., description="Name of the catalog item")
    short_description: str = Field(..., description="Short description")
    description: Optional[str] = Field(None, description="Detailed description")
    category: Optional[str] = Field(None, description="Category sys_id")
    price: Optional[str] = Field(None, description="Price (e.g. '0' or '99.99')")
    active: bool = Field(True, description="Whether the item is active")
    order: Optional[int] = Field(None, description="Display order")


class DeleteCatalogItemParams(BaseModel):
    """Parameters for deleting a catalog item."""

    item_id: str = Field(..., description="Catalog item sys_id")


class ListCatalogsParams(BaseModel):
    """Parameters for listing service catalogs."""

    limit: int = Field(10, description="Maximum number to return")
    offset: int = Field(0, description="Pagination offset")
    active: Optional[bool] = Field(None, description="Filter by active status")


class CreateCatalogParams(BaseModel):
    """Parameters for creating a service catalog."""

    title: str = Field(..., description="Catalog title")
    description: Optional[str] = Field(None, description="Catalog description")
    active: bool = Field(True, description="Whether active")


def create_catalog_item(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: CreateCatalogItemParams,
) -> Dict[str, Any]:
    """
    Create a new catalog item in ServiceNow.

    Args:
        config: Server configuration
        auth_manager: Authentication manager
        params: Parameters for creating the catalog item

    Returns:
        Dictionary containing the result of the operation
    """
    logger.info(f"Creating catalog item: {params.name}")

    url = f"{config.instance_url}/api/now/table/sc_cat_item"

    body: Dict[str, Any] = {
        "name": params.name,
        "short_description": params.short_description,
        "active": str(params.active).lower(),
    }
    if params.description is not None:
        body["description"] = params.description
    if params.category is not None:
        body["category"] = params.category
    if params.price is not None:
        body["price"] = params.price
    if params.order is not None:
        body["order"] = str(params.order)

    headers = auth_manager.get_headers()
    headers["Accept"] = "application/json"
    headers["Content-Type"] = "application/json"

    try:
        response = requests.post(url, headers=headers, json=body)
        response.raise_for_status()

        result = response.json().get("result", {})
        return {
            "success": True,
            "message": "Catalog item created",
            "item": result,
        }

    except requests.exceptions.RequestException as e:
        logger.error(f"Error creating catalog item: {str(e)}")
        return {
            "success": False,
            "message": f"Error creating catalog item: {str(e)}",
            "item": None,
        }


def delete_catalog_item(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: DeleteCatalogItemParams,
) -> Dict[str, Any]:
    """
    Delete a catalog item from ServiceNow.

    Args:
        config: Server configuration
        auth_manager: Authentication manager
        params: Parameters for deleting the catalog item

    Returns:
        Dictionary containing the result of the operation
    """
    logger.info(f"Deleting catalog item: {params.item_id}")

    url = f"{config.instance_url}/api/now/table/sc_cat_item/{params.item_id}"

    headers = auth_manager.get_headers()
    headers["Accept"] = "application/json"

    try:
        response = requests.delete(url, headers=headers)
        response.raise_for_status()

        return {
            "success": True,
            "message": "Catalog item deleted",
        }

    except requests.exceptions.RequestException as e:
        logger.error(f"Error deleting catalog item: {str(e)}")
        return {
            "success": False,
            "message": f"Error deleting catalog item: {str(e)}",
        }


def list_catalogs(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: ListCatalogsParams,
) -> Dict[str, Any]:
    """
    List service catalogs from ServiceNow.

    Args:
        config: Server configuration
        auth_manager: Authentication manager
        params: Parameters for listing catalogs

    Returns:
        Dictionary containing the catalogs and metadata
    """
    logger.info("Listing service catalogs")

    url = f"{config.instance_url}/api/now/table/sc_catalog"

    query_params: Dict[str, Any] = {
        "sysparm_limit": params.limit,
        "sysparm_offset": params.offset,
        "sysparm_display_value": "true",
        "sysparm_exclude_reference_link": "true",
    }

    if params.active is not None:
        query_params["sysparm_query"] = f"active={str(params.active).lower()}"

    headers = auth_manager.get_headers()
    headers["Accept"] = "application/json"

    try:
        response = requests.get(url, headers=headers, params=query_params)
        response.raise_for_status()

        items = response.json().get("result", [])
        return {
            "success": True,
            "message": f"Found {len(items)} catalog(s)",
            "catalogs": items,
        }

    except requests.exceptions.RequestException as e:
        logger.error(f"Error listing catalogs: {str(e)}")
        return {
            "success": False,
            "message": f"Error listing catalogs: {str(e)}",
            "catalogs": [],
        }


def create_catalog(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: CreateCatalogParams,
) -> Dict[str, Any]:
    """
    Create a new service catalog in ServiceNow.

    Args:
        config: Server configuration
        auth_manager: Authentication manager
        params: Parameters for creating the catalog

    Returns:
        Dictionary containing the result of the operation
    """
    logger.info(f"Creating service catalog: {params.title}")

    url = f"{config.instance_url}/api/now/table/sc_catalog"

    body: Dict[str, Any] = {
        "title": params.title,
        "active": str(params.active).lower(),
    }
    if params.description is not None:
        body["description"] = params.description

    headers = auth_manager.get_headers()
    headers["Accept"] = "application/json"
    headers["Content-Type"] = "application/json"

    try:
        response = requests.post(url, headers=headers, json=body)
        response.raise_for_status()

        result = response.json().get("result", {})
        return {
            "success": True,
            "message": "Catalog created",
            "catalog": result,
        }

    except requests.exceptions.RequestException as e:
        logger.error(f"Error creating catalog: {str(e)}")
        return {
            "success": False,
            "message": f"Error creating catalog: {str(e)}",
            "catalog": None,
        }