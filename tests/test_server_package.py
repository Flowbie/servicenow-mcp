"""Tests for default tool package behavior."""
import asyncio

import pytest
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig


def _make_config():
    auth = AuthConfig(
        type=AuthType.BASIC,
        basic=BasicAuthConfig(username="u", password="p"),
    )
    return ServerConfig(instance_url="https://test.service-now.com", auth=auth)


def test_default_package_is_executor(monkeypatch):
    """When MCP_TOOL_PACKAGE is not set, the default package should be 'executor'."""
    monkeypatch.delenv("MCP_TOOL_PACKAGE", raising=False)

    from servicenow_mcp.server import ServiceNowMCP
    server = ServiceNowMCP(_make_config())

    assert server.current_package_name == "executor", (
        f"Expected default package 'executor', got '{server.current_package_name}'"
    )


def test_full_package_explicit(monkeypatch):
    """When MCP_TOOL_PACKAGE=full, the full package should load."""
    monkeypatch.setenv("MCP_TOOL_PACKAGE", "full")

    from servicenow_mcp.server import ServiceNowMCP
    server = ServiceNowMCP(_make_config())

    assert server.current_package_name == "full"


def test_empty_string_package_defaults_to_executor(monkeypatch):
    """When MCP_TOOL_PACKAGE is empty string, should default to 'executor'."""
    monkeypatch.setenv("MCP_TOOL_PACKAGE", "")

    from servicenow_mcp.server import ServiceNowMCP
    server = ServiceNowMCP(_make_config())

    assert server.current_package_name == "executor"


def test_call_tool_raises_on_success_false(monkeypatch):
    """_call_tool_impl raises RuntimeError when a tool returns success=False."""
    from unittest.mock import MagicMock

    monkeypatch.setenv("MCP_TOOL_PACKAGE", "full")

    from servicenow_mcp.server import ServiceNowMCP
    sn = ServiceNowMCP(_make_config())

    # Find a tool whose required fields are all plain strings so we can pass "test" for each
    tool_name = None
    for name in sn.enabled_tool_names:
        defn = sn.tool_definitions.get(name)
        if defn is None:
            continue
        schema = defn[1].model_json_schema()
        required = schema.get("required", [])
        props = schema.get("properties", {})
        if all(props.get(r, {}).get("type") == "string" for r in required):
            tool_name = name
            break

    assert tool_name is not None, "Could not find a tool with all-string required fields"
    original_def = sn.tool_definitions[tool_name]

    # Replace the impl function with one that returns success=False
    error_impl = MagicMock(return_value={"success": False, "error": "test error"})
    sn.tool_definitions[tool_name] = (
        error_impl,
        original_def[1],
        original_def[2],
        original_def[3],
        original_def[4],
    )

    # Build minimal valid args from the model's schema
    schema = original_def[1].model_json_schema()
    required = schema.get("required", [])
    args = {k: "test" for k in required}

    with pytest.raises(RuntimeError, match="test error"):
        asyncio.run(sn._call_tool_impl(tool_name, args))


def test_new_update_set_tools_registered():
    from servicenow_mcp.utils.tool_utils import get_tool_definitions
    tools = get_tool_definitions()
    assert "move_records_to_update_set" in tools
    assert "inspect_update_set" in tools
    assert "clone_update_set" in tools


def test_sdk_tools_registered():
    from servicenow_mcp.utils.tool_utils import get_tool_definitions
    tools = get_tool_definitions()
    assert "sdk_scaffold" in tools
    assert "sdk_explain" in tools
    assert "sdk_run_command" in tools


def test_all_registered_tool_definitions_are_5_tuples():
    from servicenow_mcp.utils.tool_utils import get_tool_definitions
    tools = get_tool_definitions()
    new_tools = [
        "move_records_to_update_set",
        "inspect_update_set",
        "clone_update_set",
        "sdk_scaffold",
        "sdk_explain",
        "sdk_run_command",
    ]
    for name in new_tools:
        defn = tools[name]
        assert len(defn) == 5, f"{name} definition should be a 5-tuple"
        func, params_model, return_type, description, serialization = defn
        assert callable(func), f"{name} first element must be callable"
        assert isinstance(description, str) and len(description) > 10, f"{name} needs a real description"
