"""Detect which ServiceNow modules an instance actively uses.

Classifies modules into four buckets based on plugin state and table activity:
- active_populated: plugin active + primary table has recent writes
- active_dormant:   plugin active + no recent activity
- declared_only:    plugin inactive but user explicitly declared it (planned)
- ignored:          plugin inactive, not declared

Reads config/module_registry.yaml for the plugin->tables mapping.
Used by the /bootstrap-architecture slash command.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import requests
import yaml
from pydantic import BaseModel, Field

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.utils.config import ServerConfig

logger = logging.getLogger(__name__)

REGISTRY_PATH = (
    Path(__file__).parent.parent.parent.parent / "config" / "module_registry.yaml"
)


class ModuleClassification(BaseModel):
    """Classification entry for one module."""

    domain: str = Field(..., description="Module identifier from the registry.")
    plugin: str = Field(default="", description="License-marker plugin name.")
    primary_tables: list[str] = Field(default_factory=list)
    record_count: int = Field(default=0)
    last_update: str = Field(default="")
    has_template: bool = Field(default=False)
    reason: str = Field(default="")
    missing_plugins: list[str] = Field(default_factory=list)


class DetectActiveModulesParams(BaseModel):
    """Params for detect_active_modules."""

    activity_days: int = Field(default=90)
    license_override: list[str] | None = Field(default=None)
    planned: list[str] | None = Field(default=None)
    greenfield: bool = Field(default=False)


class DetectActiveModulesResult(BaseModel):
    active_populated: list[ModuleClassification] = Field(default_factory=list)
    active_dormant: list[ModuleClassification] = Field(default_factory=list)
    declared_only: list[ModuleClassification] = Field(default_factory=list)
    ignored: list[ModuleClassification] = Field(default_factory=list)
    detection_partial: bool = Field(default=False)
    errors: list[str] = Field(default_factory=list)


def _load_registry(path: Path = REGISTRY_PATH) -> dict[str, dict[str, Any]]:
    """Load the module registry YAML file."""
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    return data.get("modules", {})


def _query_plugin_active(
    config: ServerConfig, auth_manager: AuthManager, plugin: str
) -> tuple[bool, str | None]:
    """Return (is_active, error_message_or_None)."""
    url = f"{config.instance_url.rstrip('/')}/api/now/table/sys_plugins"
    params = {
        "sysparm_query": f"name={plugin}^state=active",
        "sysparm_fields": "name,state,version",
        "sysparm_limit": 1,
    }
    try:
        resp = requests.get(
            url,
            headers=auth_manager.get_headers(),
            params=params,
            timeout=config.timeout,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        return (False, f"sys_plugins query failed for {plugin}: {exc}")
    rows = resp.json().get("result", [])
    return (bool(rows), None)


def _query_table_activity(
    config: ServerConfig,
    auth_manager: AuthManager,
    table: str,
    activity_days: int,
) -> tuple[int, str, str | None]:
    """Return (record_count_estimate, last_update_iso_or_empty, error_or_None).

    record_count_estimate is 0, 1 (has recent rows), or N if the platform returns one.
    """
    cutoff = (date.today() - timedelta(days=activity_days)).isoformat()
    url = f"{config.instance_url.rstrip('/')}/api/now/table/{table}"
    params = {
        "sysparm_query": (
            f"sys_updated_on>=javascript:gs.dateGenerate('{cutoff}','00:00:00')"
            "^ORDERBYDESCsys_updated_on"
        ),
        "sysparm_fields": "sys_id,sys_updated_on",
        "sysparm_limit": 1,
    }
    try:
        resp = requests.get(
            url,
            headers=auth_manager.get_headers(),
            params=params,
            timeout=config.timeout,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        return (0, "", f"{table} activity query failed: {exc}")
    rows = resp.json().get("result", [])
    if not rows:
        return (0, "", None)
    return (1, rows[0].get("sys_updated_on", ""), None)


def detect_active_modules(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: DetectActiveModulesParams,
) -> dict:
    registry = _load_registry(REGISTRY_PATH)
    result = DetectActiveModulesResult()
    license_set = set(params.license_override or [])
    planned_set = set(params.planned or [])

    for domain, module in registry.items():
        classification = ModuleClassification(
            domain=domain,
            plugin=module.get("license_marker", ""),
            primary_tables=module.get("primary_tables", []),
            has_template=module.get("has_template", False),
        )

        if params.greenfield:
            if domain in license_set:
                classification.reason = "greenfield license override"
                result.active_populated.append(classification)
            elif domain in planned_set:
                classification.reason = "planned"
                result.declared_only.append(classification)
            else:
                classification.reason = "greenfield not in license set"
                result.ignored.append(classification)
            continue

        # Brownfield path
        license_marker = module.get("license_marker", "")
        plugin_active, err = _query_plugin_active(config, auth_manager, license_marker)
        if err:
            result.detection_partial = True
            result.errors.append(err)

        if domain in license_set:
            classification.reason = "license override"
            result.active_populated.append(classification)
            continue

        if not plugin_active:
            if domain in planned_set:
                classification.reason = "plugin inactive, planned"
                result.declared_only.append(classification)
            else:
                classification.reason = "plugin inactive"
                result.ignored.append(classification)
            continue

        # Plugin is active — check activity
        effective_days = module.get("activity_days_override") or params.activity_days
        primary = (module.get("primary_tables") or [""])[0]
        count, last_update, err = _query_table_activity(
            config, auth_manager, primary, effective_days
        )
        if err:
            result.detection_partial = True
            result.errors.append(err)

        classification.record_count = count
        classification.last_update = last_update
        if count > 0:
            classification.reason = f"plugin active, recent activity ({effective_days}d)"
            result.active_populated.append(classification)
        else:
            classification.reason = (
                f"plugin active, no activity within {effective_days}d"
            )
            result.active_dormant.append(classification)

    return result.model_dump()
