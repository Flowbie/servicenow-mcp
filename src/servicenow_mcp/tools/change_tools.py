"""
Change management tools for the ServiceNow MCP server.

This module provides compound tools for change request approval workflows.
CRUD operations (create, update, list, get, add_task, etc.) are handled by
table_tools (query_records, get_record, create_record, update_record, delete_record)
using the change_request architecture blueprint as the field reference.
"""

import logging
from typing import Any, Dict, List, Optional, Type, TypeVar

import requests
from pydantic import BaseModel, Field

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.utils.config import ServerConfig

logger = logging.getLogger(__name__)

# Type variable for Pydantic models
T = TypeVar('T', bound=BaseModel)


class SubmitChangeForApprovalParams(BaseModel):
    """Parameters for submitting a change request for approval."""

    change_id: str = Field(..., description="Change request ID or sys_id")
    approval_comments: Optional[str] = Field(None, description="Comments for the approval request")


class ApproveChangeParams(BaseModel):
    """Parameters for approving a change request."""

    change_id: str = Field(..., description="Change request ID or sys_id")
    approver_id: Optional[str] = Field(None, description="ID of the approver")
    approval_comments: Optional[str] = Field(None, description="Comments for the approval")


class RejectChangeParams(BaseModel):
    """Parameters for rejecting a change request."""

    change_id: str = Field(..., description="Change request ID or sys_id")
    approver_id: Optional[str] = Field(None, description="ID of the approver")
    rejection_reason: str = Field(..., description="Reason for rejection")


def _unwrap_and_validate_params(params: Any, model_class: Type[T], required_fields: List[str] = None) -> Dict[str, Any]:
    """
    Helper function to unwrap and validate parameters.
    
    Args:
        params: The parameters to unwrap and validate.
        model_class: The Pydantic model class to validate against.
        required_fields: List of required field names.
        
    Returns:
        A tuple of (success, result) where result is either the validated parameters or an error message.
    """
    # Handle case where params might be wrapped in another dictionary
    if isinstance(params, dict) and len(params) == 1 and "params" in params and isinstance(params["params"], dict):
        logger.warning("Detected params wrapped in a 'params' key. Unwrapping...")
        params = params["params"]
    
    # Handle case where params might be a Pydantic model object
    if not isinstance(params, dict):
        try:
            # Try to convert to dict if it's a Pydantic model
            logger.warning("Params is not a dictionary. Attempting to convert...")
            params = params.dict() if hasattr(params, "dict") else dict(params)
        except Exception as e:
            logger.error(f"Failed to convert params to dictionary: {e}")
            return {
                "success": False,
                "message": f"Invalid parameters format. Expected a dictionary, got {type(params).__name__}",
            }
    
    # Validate required parameters are present
    if required_fields:
        for field in required_fields:
            if field not in params:
                return {
                    "success": False,
                    "message": f"Missing required parameter '{field}'",
                }
    
    try:
        # Validate parameters against the model
        validated_params = model_class(**params)
        return {
            "success": True,
            "params": validated_params,
        }
    except Exception as e:
        logger.error(f"Error validating parameters: {e}")
        return {
            "success": False,
            "message": f"Error validating parameters: {str(e)}",
        }


def _get_instance_url(auth_manager: AuthManager, server_config: ServerConfig) -> Optional[str]:
    """
    Helper function to get the instance URL from either server_config or auth_manager.
    
    Args:
        auth_manager: The authentication manager.
        server_config: The server configuration.
        
    Returns:
        The instance URL if found, None otherwise.
    """
    if hasattr(server_config, 'instance_url'):
        return server_config.instance_url
    elif hasattr(auth_manager, 'instance_url'):
        return auth_manager.instance_url
    else:
        logger.error("Cannot find instance_url in either server_config or auth_manager")
        return None


def _get_headers(auth_manager: Any, server_config: Any) -> Optional[Dict[str, str]]:
    """
    Helper function to get headers from either auth_manager or server_config.
    
    Args:
        auth_manager: The authentication manager or object passed as auth_manager.
        server_config: The server configuration or object passed as server_config.
        
    Returns:
        The headers if found, None otherwise.
    """
    # Try to get headers from auth_manager
    if hasattr(auth_manager, 'get_headers'):
        return auth_manager.get_headers()
    
    # If auth_manager doesn't have get_headers, try server_config
    if hasattr(server_config, 'get_headers'):
        return server_config.get_headers()
    
    # If neither has get_headers, check if auth_manager is actually a ServerConfig
    # and server_config is actually an AuthManager (parameters swapped)
    if hasattr(server_config, 'get_headers') and not hasattr(auth_manager, 'get_headers'):
        return server_config.get_headers()
    
    logger.error("Cannot find get_headers method in either auth_manager or server_config")
    return None


def submit_change_for_approval(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Submit a change request for approval in ServiceNow.

    Args:
        auth_manager: The authentication manager.
        server_config: The server configuration.
        params: The parameters for submitting a change request for approval.

    Returns:
        The result of the submission.
    """
    # Unwrap and validate parameters
    result = _unwrap_and_validate_params(
        params, 
        SubmitChangeForApprovalParams,
        required_fields=["change_id"]
    )
    
    if not result["success"]:
        return result
    
    validated_params = result["params"]
    
    # Prepare the request data
    data = {
        "state": "assess",  # Set state to "assess" to submit for approval
    }
    
    # Add approval comments if provided
    if validated_params.approval_comments:
        data["work_notes"] = validated_params.approval_comments
    
    # Get the instance URL
    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {
            "success": False,
            "message": "Cannot find instance_url in either server_config or auth_manager",
        }
    
    # Get the headers
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {
            "success": False,
            "message": "Cannot find get_headers method in either auth_manager or server_config",
        }
    
    # Add Content-Type header
    headers["Content-Type"] = "application/json"
    
    # Make the API request
    url = f"{instance_url}/api/now/table/change_request/{validated_params.change_id}"
    
    try:
        response = requests.patch(url, json=data, headers=headers)
        response.raise_for_status()
        
        # Now, create an approval request
        approval_url = f"{instance_url}/api/now/table/sysapproval_approver"
        approval_data = {
            "document_id": validated_params.change_id,
            "source_table": "change_request",
            "state": "requested",
        }
        
        approval_response = requests.post(approval_url, json=approval_data, headers=headers)
        approval_response.raise_for_status()
        
        approval_result = approval_response.json()
        
        return {
            "success": True,
            "message": "Change request submitted for approval successfully",
            "approval": approval_result["result"],
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Error submitting change for approval: {e}")
        return {
            "success": False,
            "message": f"Error submitting change for approval: {str(e)}",
        }


def approve_change(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Approve a change request in ServiceNow.

    Args:
        auth_manager: The authentication manager.
        server_config: The server configuration.
        params: The parameters for approving a change request.

    Returns:
        The result of the approval.
    """
    # Unwrap and validate parameters
    result = _unwrap_and_validate_params(
        params, 
        ApproveChangeParams,
        required_fields=["change_id"]
    )
    
    if not result["success"]:
        return result
    
    validated_params = result["params"]
    
    # Get the instance URL
    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {
            "success": False,
            "message": "Cannot find instance_url in either server_config or auth_manager",
        }
    
    # Get the headers
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {
            "success": False,
            "message": "Cannot find get_headers method in either auth_manager or server_config",
        }
    
    # First, find the approval record
    approval_query_url = f"{instance_url}/api/now/table/sysapproval_approver"
    
    query_params = {
        "sysparm_query": f"document_id={validated_params.change_id}",
        "sysparm_limit": 1,
    }
    
    try:
        approval_response = requests.get(approval_query_url, headers=headers, params=query_params)
        approval_response.raise_for_status()
        
        approval_result = approval_response.json()
        
        if not approval_result.get("result") or len(approval_result["result"]) == 0:
            return {
                "success": False,
                "message": "No approval record found for this change request",
            }
        
        approval_id = approval_result["result"][0]["sys_id"]
        
        # Now, update the approval record to approved
        approval_update_url = f"{instance_url}/api/now/table/sysapproval_approver/{approval_id}"
        headers["Content-Type"] = "application/json"
        
        approval_data = {
            "state": "approved",
        }
        
        if validated_params.approval_comments:
            approval_data["comments"] = validated_params.approval_comments
        
        approval_update_response = requests.patch(approval_update_url, json=approval_data, headers=headers)
        approval_update_response.raise_for_status()
        
        # Finally, update the change request state to "implement"
        change_url = f"{instance_url}/api/now/table/change_request/{validated_params.change_id}"
        
        change_data = {
            "state": "implement",  # This may vary depending on ServiceNow configuration
        }
        
        change_response = requests.patch(change_url, json=change_data, headers=headers)
        change_response.raise_for_status()
        
        return {
            "success": True,
            "message": "Change request approved successfully",
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Error approving change: {e}")
        return {
            "success": False,
            "message": f"Error approving change: {str(e)}",
        }


def reject_change(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Reject a change request in ServiceNow.

    Args:
        auth_manager: The authentication manager.
        server_config: The server configuration.
        params: The parameters for rejecting a change request.

    Returns:
        The result of the rejection.
    """
    # Unwrap and validate parameters
    result = _unwrap_and_validate_params(
        params, 
        RejectChangeParams,
        required_fields=["change_id", "rejection_reason"]
    )
    
    if not result["success"]:
        return result
    
    validated_params = result["params"]
    
    # Get the instance URL
    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {
            "success": False,
            "message": "Cannot find instance_url in either server_config or auth_manager",
        }
    
    # Get the headers
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {
            "success": False,
            "message": "Cannot find get_headers method in either auth_manager or server_config",
        }
    
    # First, find the approval record
    approval_query_url = f"{instance_url}/api/now/table/sysapproval_approver"
    
    query_params = {
        "sysparm_query": f"document_id={validated_params.change_id}",
        "sysparm_limit": 1,
    }
    
    try:
        approval_response = requests.get(approval_query_url, headers=headers, params=query_params)
        approval_response.raise_for_status()
        
        approval_result = approval_response.json()
        
        if not approval_result.get("result") or len(approval_result["result"]) == 0:
            return {
                "success": False,
                "message": "No approval record found for this change request",
            }
        
        approval_id = approval_result["result"][0]["sys_id"]
        
        # Now, update the approval record to rejected
        approval_update_url = f"{instance_url}/api/now/table/sysapproval_approver/{approval_id}"
        headers["Content-Type"] = "application/json"
        
        approval_data = {
            "state": "rejected",
            "comments": validated_params.rejection_reason,
        }
        
        approval_update_response = requests.patch(approval_update_url, json=approval_data, headers=headers)
        approval_update_response.raise_for_status()
        
        # Finally, update the change request state to "canceled"
        change_url = f"{instance_url}/api/now/table/change_request/{validated_params.change_id}"
        
        change_data = {
            "state": "canceled",  # This may vary depending on ServiceNow configuration
            "work_notes": f"Change request rejected: {validated_params.rejection_reason}",
        }
        
        change_response = requests.patch(change_url, json=change_data, headers=headers)
        change_response.raise_for_status()
        
        return {
            "success": True,
            "message": "Change request rejected successfully",
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Error rejecting change: {e}")
        return {
            "success": False,
            "message": f"Error rejecting change: {str(e)}",
        }


