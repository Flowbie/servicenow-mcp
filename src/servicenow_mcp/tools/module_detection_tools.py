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
    primary_tables: list[str] = Field(
        default_factory=list,
        description="Primary tables owned by this module (from the registry).",
    )
    record_count: int = Field(
        default=0,
        description="Has-activity flag for the primary table: 0 (no recent rows) or 1 (recent rows found within activity window).",
    )
    last_update: str = Field(
        default="",
        description="sys_updated_on of the most recent row returned by the activity query. Empty if none.",
    )
    has_template: bool = Field(
        default=False,
        description="True if an OOB template blueprint exists for this module in architecture/templates/.",
    )
    reason: str = Field(
        default="",
        description="Human-readable explanation of why this module landed in its current bucket.",
    )
    missing_plugins: list[str] = Field(
        default_factory=list,
        description="Plugins the registry expects for this module that are not active on the instance.",
    )


class DetectActiveModulesParams(BaseModel):
    """Params for detect_active_modules."""

    activity_days: int = Field(
        default=90,
        description="Number of days of recent sys_updated_on activity that qualifies a module's primary table as populated. Overridden per-module by registry activity_days_override.",
    )
    license_override: list[str] | None = Field(
        default=None,
        description="Module domain names to force into active_populated regardless of plugin state. Used when the user has purchased a license but the plugin has not been activated yet.",
    )
    planned: list[str] | None = Field(
        default=None,
        description="Module domain names to route into declared_only. These will get OOB template copies but no live investigation.",
    )
    greenfield: bool = Field(
        default=False,
        description="If True, skip plugin-state and activity queries; classify using license_override and planned only. Use for fresh instances with no operational data.",
    )


class DetectActiveModulesResult(BaseModel):
    active_populated: list[ModuleClassification] = Field(
        default_factory=list,
        description="Modules whose plugin is active and whose primary table has recent activity. These get full investigation in the bootstrap flow.",
    )
    active_dormant: list[ModuleClassification] = Field(
        default_factory=list,
        description="Modules whose plugin is active but whose primary table has no recent activity. These get a template copy (or schema-only investigation when no template exists).",
    )
    declared_only: list[ModuleClassification] = Field(
        default_factory=list,
        description="Modules declared via the planned list but whose plugin is inactive. These get a template copy if one exists.",
    )
    ignored: list[ModuleClassification] = Field(
        default_factory=list,
        description="Modules whose plugin is inactive and which the user did not declare. No action taken.",
    )
    detection_partial: bool = Field(
        default=False,
        description="True if one or more plugin or activity queries failed. Classification is best-effort; see errors for details.",
    )
    errors: list[str] = Field(
        default_factory=list,
        description="Per-query error messages collected during classification. Does not halt the run.",
    )


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
