#!/usr/bin/env python3
"""
Flow Designer Demo

This script demonstrates how to use the ServiceNow MCP Flow Designer tools
to list available trigger types and create a simple Flow Designer flow.
"""

import os
import sys
import json
from datetime import datetime

from dotenv import load_dotenv

# Add the parent directory to the path so we can import the package
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig
from servicenow_mcp.tools.flow_tools import (
    list_trigger_types,
    create_flow,
    ListTriggerTypesParams,
    CreateFlowParams,
    TriggerInstanceParam,
)


def print_json(data):
    """Print JSON data in a readable format."""
    print(json.dumps(data, indent=2))


def main():
    """Main function to demonstrate Flow Designer tools."""
    # Load environment variables from .env file
    load_dotenv()

    # Get ServiceNow credentials from environment variables
    instance_url = os.getenv("SERVICENOW_INSTANCE_URL")
    username = os.getenv("SERVICENOW_USERNAME")
    password = os.getenv("SERVICENOW_PASSWORD")

    if not all([instance_url, username, password]):
        print("Error: Missing required environment variables.")
        print("Please set SERVICENOW_INSTANCE_URL, SERVICENOW_USERNAME, and SERVICENOW_PASSWORD.")
        sys.exit(1)

    # Create authentication configuration
    auth_config = AuthConfig(
        type=AuthType.BASIC,
        basic=BasicAuthConfig(username=username, password=password),
    )

    # Create server configuration
    server_config = ServerConfig(
        instance_url=instance_url,
        auth=auth_config,
    )

    # Create authentication manager
    auth_manager = AuthManager(auth_config)

    print("ServiceNow Flow Designer Demo")
    print("===================================")
    print(f"Instance URL: {instance_url}")
    print(f"Username: {username}")
    print()

    # Demo 1: List trigger types
    print("Listing Flow Designer trigger types...")
    trigger_params = ListTriggerTypesParams()
    trigger_result = list_trigger_types(
        server_config,
        auth_manager,
        trigger_params,
    )
    print_json(trigger_result.model_dump() if hasattr(trigger_result, "model_dump") else trigger_result)
    print()

    if not trigger_result.trigger_types:
        print("No trigger types returned. Cannot proceed with create_flow demo.")
        return

    # Try to find a record_create trigger, fall back to the first trigger type
    record_create = next(
        (t for t in trigger_result.trigger_types if (t.type_string or "").lower() == "record_create"),
        None,
    )
    chosen_trigger = record_create or trigger_result.trigger_types[0]

    print("Using trigger type:")
    print_json(
        chosen_trigger.model_dump() if hasattr(chosen_trigger, "model_dump") else chosen_trigger.__dict__
    )
    print()

    # Demo 2: Create a simple flow with a record_create (or chosen) trigger on incident
    flow_name = f"Demo Incident Flow {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    print(f"Creating flow: {flow_name}")

    trigger_type_string = (chosen_trigger.type_string or "").lower() or "record_create"

    create_params = CreateFlowParams(
        name=flow_name,
        description="A demo flow created by the ServiceNow MCP Flow Designer demo.",
        scope="global",
        run_as="user",
        access="public",
        flow_priority="MEDIUM",
        trigger=TriggerInstanceParam(
            type=trigger_type_string,
            table="incident",
            condition="active=true",
        ),
    )

    create_result = create_flow(
        server_config,
        auth_manager,
        create_params,
    )

    # create_result is a Pydantic model (CreateFlowResponse)
    print("create_flow result:")
    print_json(
        create_result.model_dump() if hasattr(create_result, "model_dump") else create_result.__dict__
    )
    print()

    if create_result.success:
        print(
            f"Flow created successfully: sys_id={create_result.flow_sys_id}, "
            f"name={create_result.flow_name}, internal_name={create_result.flow_internal_name}"
        )
    else:
        print(f"Flow creation failed: {create_result.message}")


if __name__ == "__main__":
    main()

