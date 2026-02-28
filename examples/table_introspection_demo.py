#!/usr/bin/env python3
"""
Table Introspection Demo

This script demonstrates how to use the ServiceNow MCP table introspection tools
to inspect table metadata, fields, relationships, and child tables.
"""

import os
import sys
import json

from dotenv import load_dotenv

# Add the parent directory to the path so we can import the package
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig
from servicenow_mcp.tools.introspection_tools import (
    get_table_metadata,
    list_table_fields,
    list_table_relationships,
    list_child_tables,
    GetTableMetadataParams,
    ListTableFieldsParams,
    ListTableRelationshipsParams,
    ListChildTablesParams,
)


def print_json(data):
    """Print JSON data in a readable format."""
    print(json.dumps(data, indent=2))


def main():
    """Main function to demonstrate table introspection tools."""
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

    print("ServiceNow Table Introspection Demo")
    print("===================================")
    print(f"Instance URL: {instance_url}")
    print(f"Username: {username}")
    print()

    # Demo 1: Table metadata for incident
    table_name = "incident"
    print(f"Getting table metadata for '{table_name}'...")
    meta_params = GetTableMetadataParams(table=table_name)
    meta_result = get_table_metadata(
        server_config,
        auth_manager,
        meta_params,
    )
    print_json(meta_result.model_dump() if hasattr(meta_result, "model_dump") else meta_result.__dict__)
    print()

    if not meta_result.table_found:
        print(f"Table '{table_name}' not found. Exiting demo.")
        return

    # Demo 2: List non-system fields on incident
    print(f"Listing non-system fields on '{table_name}'...")
    fields_params = ListTableFieldsParams(table=table_name, include_system=False)
    fields_result = list_table_fields(
        server_config,
        auth_manager,
        fields_params,
    )
    # Print only the first 10 fields for brevity
    subset = fields_result.fields[:10]
    print_json(
        [f.model_dump() if hasattr(f, "model_dump") else f.__dict__ for f in subset]
    )
    print(f"Total fields returned (excluding sys_): {len(fields_result.fields)}")
    print()

    # Demo 3: List outbound relationships from incident
    print(f"Listing outbound relationships from '{table_name}'...")
    rel_params = ListTableRelationshipsParams(table=table_name)
    rel_result = list_table_relationships(
        server_config,
        auth_manager,
        rel_params,
    )
    print_json(rel_result.model_dump() if hasattr(rel_result, "model_dump") else rel_result.__dict__)
    print()

    # Demo 4: List child tables of task
    parent_table = "task"
    print(f"Listing child tables of '{parent_table}'...")
    child_params = ListChildTablesParams(parent_table=parent_table)
    child_result = list_child_tables(
        server_config,
        auth_manager,
        child_params,
    )
    print_json(child_result.model_dump() if hasattr(child_result, "model_dump") else child_result.__dict__)
    print()

    print("Table introspection demo completed.")


if __name__ == "__main__":
    main()

