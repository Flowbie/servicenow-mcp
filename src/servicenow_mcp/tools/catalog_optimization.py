"""
Tools for optimizing the ServiceNow Service Catalog.

This module provides tools for analyzing and optimizing the ServiceNow Service Catalog,
including identifying inactive items and items with poor descriptions.
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

import requests
from pydantic import BaseModel, Field

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.utils.config import ServerConfig

logger = logging.getLogger(__name__)


class OptimizationRecommendationsParams(BaseModel):
    """Parameters for getting optimization recommendations.

    Valid values for recommendation_types:
      - "inactive_items": catalog items where active=false
      - "description_quality": active items with missing, short, or low-quality descriptions
    """

    recommendation_types: List[str]
    category_id: Optional[str] = None


def get_optimization_recommendations(
    config: ServerConfig, auth_manager: AuthManager, params: OptimizationRecommendationsParams
) -> Dict:
    """
    Get optimization recommendations for the ServiceNow Service Catalog.

    Args:
        config: The server configuration
        auth_manager: The authentication manager
        params: The parameters for getting optimization recommendations

    Returns:
        A dictionary containing the optimization recommendations
    """
    logger.info("Getting catalog optimization recommendations")
    
    recommendations = []
    category_id = params.category_id
    
    try:
        # Get recommendations based on the requested types
        for rec_type in params.recommendation_types:
            if rec_type == "inactive_items":
                items = _get_inactive_items(config, auth_manager, category_id)
                if items:
                    recommendations.append({
                        "type": "inactive_items",
                        "title": "Inactive Catalog Items",
                        "description": "Items that are currently inactive in the catalog",
                        "items": items,
                        "impact": "medium",
                        "effort": "low",
                        "action": "Review and either update or remove these items",
                    })
            
            elif rec_type == "description_quality":
                items = _get_poor_description_items(config, auth_manager, category_id)
                if items:
                    recommendations.append({
                        "type": "description_quality",
                        "title": "Poor Description Quality",
                        "description": "Items with missing, short, or low-quality descriptions",
                        "items": items,
                        "impact": "medium",
                        "effort": "low",
                        "action": "Improve the descriptions to better explain the item's purpose and benefits",
                    })
        
        return {
            "success": True,
            "recommendations": recommendations,
        }
    
    except Exception as e:
        logger.error(f"Error getting optimization recommendations: {e}")
        return {
            "success": False,
            "message": f"Error getting optimization recommendations: {str(e)}",
            "recommendations": [],
        }


def _get_inactive_items(
    config: ServerConfig, auth_manager: AuthManager, category_id: Optional[str] = None
) -> List[Dict]:
    """
    Get inactive catalog items.

    Args:
        config: The server configuration
        auth_manager: The authentication manager
        category_id: Optional category ID to filter by

    Returns:
        A list of inactive catalog items
    """
    try:
        # Build the query
        query = "active=false"
        if category_id:
            query += f"^category={category_id}"
        
        # Make the API request
        url = f"{config.instance_url}/api/now/table/sc_cat_item"
        headers = auth_manager.get_headers()
        params = {
            "sysparm_query": query,
            "sysparm_fields": "sys_id,name,short_description,category",
            "sysparm_limit": "50",
        }
        
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        
        return response.json()["result"]
    
    except Exception as e:
        logger.error(f"Error getting inactive items: {e}")
        return []


def _get_poor_description_items(
    config: ServerConfig, auth_manager: AuthManager, category_id: Optional[str] = None
) -> List[Dict]:
    """
    Get catalog items with poor description quality.

    Args:
        config: The server configuration
        auth_manager: The authentication manager
        category_id: Optional category ID to filter by

    Returns:
        A list of catalog items with poor description quality
    """
    try:
        # Build the query
        query = "active=true"
        if category_id:
            query += f"^category={category_id}"
        
        # Make the API request
        url = f"{config.instance_url}/api/now/table/sc_cat_item"
        headers = auth_manager.get_headers()
        params = {
            "sysparm_query": query,
            "sysparm_fields": "sys_id,name,short_description,category",
            "sysparm_limit": "50",
        }
        
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        
        items = response.json()["result"]
        poor_description_items = []
        
        # Analyze each item's description quality
        for item in items:
            description = item.get("short_description", "")
            quality_issues = []
            quality_score = 100  # Start with perfect score
            
            # Check for empty description
            if not description:
                quality_issues.append("Missing description")
                quality_score = 0
            else:
                # Check for short description
                if len(description) < 30:
                    quality_issues.append("Description too short")
                    quality_issues.append("Lacks detail")
                    quality_score -= 70
                
                # Check for instructional language instead of descriptive
                if "click here" in description.lower() or "request this" in description.lower():
                    quality_issues.append("Uses instructional language instead of descriptive")
                    quality_score -= 50
                
                # Check for vague terms
                vague_terms = ["etc", "and more", "and so on", "stuff", "things"]
                if any(term in description.lower() for term in vague_terms):
                    quality_issues.append("Contains vague terms")
                    quality_score -= 30
            
            # Ensure score is between 0 and 100
            quality_score = max(0, min(100, quality_score))
            
            # Add to poor description items if quality is below threshold
            if quality_score < 80:
                item["description_quality"] = quality_score
                item["quality_issues"] = quality_issues
                poor_description_items.append(item)
        
        return poor_description_items
    
    except Exception as e:
        logger.error(f"Error getting poor description items: {e}")
        return [] 