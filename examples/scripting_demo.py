#!/usr/bin/env python3
"""
Scripting Demo

This script demonstrates how to use the ServiceNow MCP scripting tools:
- run_background_script (background script execution)
- Script Include management (list, create, update, delete)
"""

import os
import sys
import json

from dotenv import load_dotenv

# Add the parent directory to the path so we can import the package
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig
from servicenow_mcp.tools.script_tools import (
    run_background_script,
    RunBackgroundScriptParams,
)
from servicenow_mcp.tools.script_include_tools import (
    list_script_includes,
    get_script_include,
    create_script_include,
    update_script_include,
    delete_script_include,
    ListScriptIncludesParams,
    GetScriptIncludeParams,
    CreateScriptIncludeParams,
    UpdateScriptIncludeParams,
    DeleteScriptIncludeParams,
)


def print_json(data):
    """Print JSON data in a readable format."""
    print(json.dumps(data, indent=2))


def main():
    """Main function to demonstrate scripting tools."""
    # Load environment variables from .env file
    load_dotenv()

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

    print("ServiceNow Scripting Demo")
    print("===================================")
    print(f"Instance URL: {instance_url}")
    print(f"Username: {username}")
    print()

    # ------------------------------------------------------------------
    # Demo 1: Safe background script (read-only)
    # ------------------------------------------------------------------
    print("Running a safe background script (read-only)...")
    background_script = """
        // Sample read-only script: count a few active incidents
        var gr = new GlideRecord('incident');
        gr.addQuery('active', true);
        gr.setLimit(5);
        gr.query();
        var count = 0;
        while (gr.next()) {
            count++;
        }
        gs.print('Active incidents (sample limit=5): ' + count);
        gs.info('ScriptingDemo | counted=' + count + ' | run_id=' + __MFCP_RUN_ID);
    """
    bg_params = RunBackgroundScriptParams(script=background_script, scope="global")
    bg_result = run_background_script(
        server_config,
        auth_manager,
        bg_params,
    )

    print("Background script result:")
    print_json(bg_result.model_dump() if hasattr(bg_result, "model_dump") else bg_result.__dict__)
    print()

    # ------------------------------------------------------------------
    # Demo 2: Script Include management
    # ------------------------------------------------------------------
    demo_name = "McpDemoUtil"
    print(f"Listing a few active Script Includes before creating {demo_name}...")
    list_params = ListScriptIncludesParams(limit=5, active=True)
    list_result = list_script_includes(
        server_config,
        auth_manager,
        list_params,
    )
    print_json(list_result)
    print()

    print(f"Creating Script Include {demo_name}...")
    create_params = CreateScriptIncludeParams(
        name=demo_name,
        description="Utility Script Include created by the ServiceNow MCP scripting demo.",
        script="""
            var McpDemoUtil = Class.create();
            McpDemoUtil.prototype = {
                initialize: function() {},

                hello: function(name) {
                    return "Hello, " + name + " from MCP!";
                },

                type: "McpDemoUtil"
            };
        """,
        client_callable=False,
        active=True,
        access="package_private",
    )
    create_result = create_script_include(
        server_config,
        auth_manager,
        create_params,
    )
    print_json(create_result)
    print()

    if not create_result.get("success"):
        print("Create Script Include failed, skipping update/delete demo.")
        return

    # Get Script Include by name
    print(f"Getting Script Include {demo_name} by name...")
    get_params = GetScriptIncludeParams(script_include_id=demo_name)
    get_result = get_script_include(
        server_config,
        auth_manager,
        get_params,
    )
    print_json(get_result)
    print()

    # Update Script Include description
    print(f"Updating Script Include {demo_name} description...")
    update_params = UpdateScriptIncludeParams(
        script_include_id=demo_name,
        description="Updated description from ServiceNow MCP scripting demo.",
    )
    update_result = update_script_include(
        server_config,
        auth_manager,
        update_params,
    )
    print_json(update_result.model_dump() if hasattr(update_result, "model_dump") else update_result.__dict__)
    print()

    # Delete Script Include (cleanup)
    print(f"Deleting Script Include {demo_name} (cleanup)...")
    delete_params = DeleteScriptIncludeParams(script_include_id=demo_name)
    delete_result = delete_script_include(
        server_config,
        auth_manager,
        delete_params,
    )
    print_json(delete_result.model_dump() if hasattr(delete_result, "model_dump") else delete_result.__dict__)
    print()

    print("Scripting demo completed.")


if __name__ == "__main__":
    main()

