"""Tests for default tool package behavior."""
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
