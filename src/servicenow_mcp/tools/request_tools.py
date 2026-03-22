"""
Service Request tools for the ServiceNow MCP server.

This module provides compound tools for service requests.
CRUD operations (list_requests, get_request, list_request_items, update_request_item,
list_sc_tasks, update_sc_task) are handled by table_tools (query_records / update_record)
using the sc_request / sc_req_item / sc_task architecture blueprints.
"""

import logging
from typing import Any, Dict, List

import requests
from pydantic import BaseModel, Field

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.utils.config import ServerConfig

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Param models
# ---------------------------------------------------------------------------


class GetRitmVariablesParams(BaseModel):
    """Parameters for getting RITM variable answers."""

    ritm_sys_id: str = Field(..., description="RITM sys_id")


# ---------------------------------------------------------------------------
# Tool functions
# ---------------------------------------------------------------------------


def get_ritm_variables(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: GetRitmVariablesParams,
) -> Dict[str, Any]:
    """
    Get variable answers for a RITM via the sc_item_option_mtom indirect join.

    Fetches sc_item_option_mtom rows for the RITM, then retrieves the actual
    sc_item_option record for each link to get the variable name, label, and value.

    Args:
        config: Server configuration
        auth_manager: Authentication manager
        params: Parameters containing the RITM sys_id

    Returns:
        Dictionary with a list of {name, label, value} variable answers
    """
    logger.info(f"Getting RITM variables for: {params.ritm_sys_id}")

    headers = auth_manager.get_headers()
    headers["Accept"] = "application/json"

    try:
        # Step 1 – get mtom join rows for this RITM
        mtom_url = f"{config.instance_url}/api/now/table/sc_item_option_mtom"
        mtom_response = requests.get(
            mtom_url,
            headers=headers,
            params={
                "sysparm_query": f"request_item={params.ritm_sys_id}",
                "sysparm_display_value": "true",
                "sysparm_exclude_reference_link": "true",
            },
        )
        mtom_response.raise_for_status()
        mtom_rows = mtom_response.json().get("result", [])

        if not mtom_rows:
            return {
                "success": True,
                "message": "No variables found for this RITM",
                "variables": [],
            }

        # Step 2 – for each mtom row, fetch the sc_item_option record
        variables: List[Dict[str, Any]] = []
        for row in mtom_rows:
            # The sc_item_option sys_id is stored in the sc_item_option field
            option_ref = row.get("sc_item_option", "")
            if not option_ref:
                continue

            # When display_value=true, reference fields may be dicts or plain strings
            option_sys_id = (
                option_ref.get("value", option_ref)
                if isinstance(option_ref, dict)
                else option_ref
            )

            option_url = f"{config.instance_url}/api/now/table/sc_item_option"
            option_response = requests.get(
                option_url,
                headers=headers,
                params={
                    "sys_id": option_sys_id,
                    "sysparm_display_value": "true",
                    "sysparm_exclude_reference_link": "true",
                },
            )
            option_response.raise_for_status()
            option_results = option_response.json().get("result", [])

            if not option_results:
                continue

            opt = option_results[0] if isinstance(option_results, list) else option_results

            # item_option_new holds the variable definition; value is in sc_item_option
            variables.append(
                {
                    "name": opt.get("item_option_new", {}).get("name", "")
                    if isinstance(opt.get("item_option_new"), dict)
                    else opt.get("item_option_new", ""),
                    "label": opt.get("item_option_new", {}).get("question_text", "")
                    if isinstance(opt.get("item_option_new"), dict)
                    else "",
                    "value": opt.get("value", ""),
                }
            )

        return {
            "success": True,
            "message": f"Found {len(variables)} variable(s) for RITM",
            "variables": variables,
        }

    except requests.exceptions.RequestException as e:
        logger.error(f"Error getting RITM variables: {str(e)}")
        return {
            "success": False,
            "message": f"Error getting RITM variables: {str(e)}",
            "variables": [],
        }
