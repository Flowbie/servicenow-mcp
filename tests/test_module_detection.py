"""Tests for detect_active_modules tool."""
from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import requests
import yaml

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.module_detection_tools import (
    DetectActiveModulesParams,
    ModuleClassification,
    detect_active_modules,
    _load_registry,
)
from servicenow_mcp.utils.config import ServerConfig


@pytest.fixture
def fake_registry(tmp_path: Path) -> Path:
    """A minimal on-disk registry for tests."""
    registry = {
        "modules": {
            "incident": {
                "plugins": ["com.snc.incident"],
                "primary_tables": ["incident"],
                "related_tables": ["task"],
                "license_marker": "com.snc.incident",
                "activity_days_override": None,
                "has_template": True,
            },
            "audit": {
                "plugins": ["com.sn_audit"],
                "primary_tables": ["sn_audit_engagement"],
                "related_tables": [],
                "license_marker": "com.sn_audit",
                "activity_days_override": 365,
                "has_template": False,
            },
        }
    }
    path = tmp_path / "module_registry.yaml"
    path.write_text(yaml.safe_dump(registry))
    return path


def test_load_registry_reads_yaml(fake_registry: Path) -> None:
    registry = _load_registry(fake_registry)
    assert "incident" in registry
    assert registry["incident"]["primary_tables"] == ["incident"]
    assert registry["audit"]["activity_days_override"] == 365


def _plugin_response(plugins_active: set[str]) -> callable:
    """Build a fake requests.get that returns plugin/activity rows."""

    def _get(url: str, **kwargs: Any) -> MagicMock:
        resp = MagicMock()
        resp.status_code = 200
        if "sys_plugins" in url:
            # Extract plugin name from the sysparm_query=name=X^state=active
            query = kwargs.get("params", {}).get("sysparm_query", "")
            plugin_name = ""
            for part in query.split("^"):
                if part.startswith("name="):
                    plugin_name = part.split("=", 1)[1]
                    break
            if plugin_name in plugins_active:
                resp.json.return_value = {
                    "result": [{"name": plugin_name, "state": "active", "version": "1.0"}]
                }
            else:
                resp.json.return_value = {"result": []}
        elif "sys_updated_on" in kwargs.get("params", {}).get("sysparm_query", ""):
            # Activity query — always return one recent row
            resp.json.return_value = {
                "result": [{"sys_id": "abc", "sys_updated_on": "2026-04-18 10:00:00"}]
            }
        else:
            resp.json.return_value = {"result": [{"sys_id": "x"}]}
        return resp

    return _get


@pytest.fixture
def fake_config() -> MagicMock:
    cfg = MagicMock(spec=ServerConfig)
    cfg.instance_url = "https://example.service-now.com"
    cfg.timeout = 30
    return cfg


@pytest.fixture
def fake_auth() -> MagicMock:
    auth = MagicMock(spec=AuthManager)
    auth.get_headers.return_value = {"Authorization": "Bearer test"}
    return auth


def test_active_plugin_with_activity_is_active_populated(
    fake_registry: Path, fake_config: MagicMock, fake_auth: MagicMock
) -> None:
    with patch(
        "servicenow_mcp.tools.module_detection_tools.REGISTRY_PATH", fake_registry
    ), patch(
        "servicenow_mcp.tools.module_detection_tools.requests.get",
        side_effect=_plugin_response({"com.snc.incident"}),
    ):
        result = detect_active_modules(
            fake_config, fake_auth, DetectActiveModulesParams(activity_days=90)
        )
    assert len(result["active_populated"]) == 1
    assert result["active_populated"][0]["domain"] == "incident"
    assert result["active_populated"][0]["has_template"] is True


def test_inactive_plugin_is_ignored(
    fake_registry: Path, fake_config: MagicMock, fake_auth: MagicMock
) -> None:
    with patch(
        "servicenow_mcp.tools.module_detection_tools.REGISTRY_PATH", fake_registry
    ), patch(
        "servicenow_mcp.tools.module_detection_tools.requests.get",
        side_effect=_plugin_response(set()),  # no plugins active
    ):
        result = detect_active_modules(
            fake_config, fake_auth, DetectActiveModulesParams()
        )
    assert {m["domain"] for m in result["ignored"]} == {"incident", "audit"}


def test_planned_module_is_declared_only(
    fake_registry: Path, fake_config: MagicMock, fake_auth: MagicMock
) -> None:
    with patch(
        "servicenow_mcp.tools.module_detection_tools.REGISTRY_PATH", fake_registry
    ), patch(
        "servicenow_mcp.tools.module_detection_tools.requests.get",
        side_effect=_plugin_response(set()),  # nothing active
    ):
        result = detect_active_modules(
            fake_config, fake_auth, DetectActiveModulesParams(planned=["audit"])
        )
    assert len(result["declared_only"]) == 1
    assert result["declared_only"][0]["domain"] == "audit"


def test_greenfield_uses_license_override(
    fake_registry: Path, fake_config: MagicMock, fake_auth: MagicMock
) -> None:
    with patch(
        "servicenow_mcp.tools.module_detection_tools.REGISTRY_PATH", fake_registry
    ), patch(
        "servicenow_mcp.tools.module_detection_tools.requests.get",
        side_effect=_plugin_response(set()),
    ):
        result = detect_active_modules(
            fake_config,
            fake_auth,
            DetectActiveModulesParams(
                greenfield=True, license_override=["incident"]
            ),
        )
    assert len(result["active_populated"]) == 1
    assert result["active_populated"][0]["domain"] == "incident"


def test_license_override_forces_brownfield_classification(
    fake_registry: Path, fake_config: MagicMock, fake_auth: MagicMock
) -> None:
    # Plugin inactive but user overrides via --licenses
    with patch(
        "servicenow_mcp.tools.module_detection_tools.REGISTRY_PATH", fake_registry
    ), patch(
        "servicenow_mcp.tools.module_detection_tools.requests.get",
        side_effect=_plugin_response(set()),
    ):
        result = detect_active_modules(
            fake_config,
            fake_auth,
            DetectActiveModulesParams(license_override=["audit"]),
        )
    assert len(result["active_populated"]) == 1
    assert result["active_populated"][0]["domain"] == "audit"


def test_plugin_query_error_marks_partial(
    fake_registry: Path, fake_config: MagicMock, fake_auth: MagicMock
) -> None:
    def _raise(*args: Any, **kwargs: Any) -> MagicMock:
        raise requests.ConnectionError("boom")

    with patch(
        "servicenow_mcp.tools.module_detection_tools.REGISTRY_PATH", fake_registry
    ), patch(
        "servicenow_mcp.tools.module_detection_tools.requests.get",
        side_effect=_raise,
    ):
        result = detect_active_modules(
            fake_config, fake_auth, DetectActiveModulesParams()
        )
    assert result["detection_partial"] is True
    assert result["errors"]
