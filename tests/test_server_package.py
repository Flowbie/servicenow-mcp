"""Tests for default tool package behavior."""
import os
from unittest.mock import patch

import pytest


def test_default_package_is_executor(tmp_path, monkeypatch):
    """When MCP_TOOL_PACKAGE is not set, the default package should be 'executor'."""
    from servicenow_mcp.auth.auth_manager import AuthManager
    from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig

    auth = AuthConfig(
        type=AuthType.BASIC,
        basic=BasicAuthConfig(username="u", password="p"),
    )
    config = ServerConfig(instance_url="https://test.service-now.com", auth=auth)

    monkeypatch.delenv("MCP_TOOL_PACKAGE", raising=False)

    from servicenow_mcp.server import ServiceNowMCP
    server = ServiceNowMCP(config)

    assert server.current_package_name == "executor", (
        f"Expected default package 'executor', got '{server.current_package_name}'"
    )


def test_full_package_explicit(monkeypatch):
    """When MCP_TOOL_PACKAGE=full, the full package should load."""
    from servicenow_mcp.auth.auth_manager import AuthManager
    from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig

    auth = AuthConfig(
        type=AuthType.BASIC,
        basic=BasicAuthConfig(username="u", password="p"),
    )
    config = ServerConfig(instance_url="https://test.service-now.com", auth=auth)

    monkeypatch.setenv("MCP_TOOL_PACKAGE", "full")

    from servicenow_mcp.server import ServiceNowMCP
    server = ServiceNowMCP(config)

    assert server.current_package_name == "full"
