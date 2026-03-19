"""
Customization discovery tools for the ServiceNow MCP server.

Provides table-centric read-only inspection of all customizations active on a
ServiceNow table: business rules, UI policies, client scripts, notifications,
UI actions, and access control rules (ACLs).

These tools answer "what automation, form behaviour, and security rules exist
for this table?" and are used primarily for architecture blueprint generation,
pre-implementation research, and root cause investigation.

Contrast with the field-centric diagnostic tools in write_safety_tools.py
(get_business_rules, get_ui_policies) which require a field name and are used
during write-mismatch escalation. The tools here take only a table name and
return all customizations for that table.

All tools are read-only. None modify any records.
"""

import logging
from typing import Any, List, Optional

import requests
from pydantic import BaseModel, Field

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.utils.config import ServerConfig
from servicenow_mcp.utils.snow_utils import parse_snow_bool

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _str(value: Any) -> str:
    """Extract a string from a ServiceNow field (plain or display_value dict)."""
    if isinstance(value, dict):
        return (value.get("display_value") or value.get("value") or "").strip()
    return str(value).strip() if value is not None else ""


def _preview(script: Any, max_chars: int = 500) -> str:
    """Truncate a script field to max_chars characters."""
    text = _str(script)
    return text[:max_chars] + ("..." if len(text) > max_chars else "")


def _request_error(e: requests.RequestException) -> str:
    """Build an error string that includes the response body when available."""
    body = getattr(e, "response", None)
    body_text = (body.text[:2000] if body and hasattr(body, "text") else "") or ""
    return str(e) + (f" | response: {body_text}" if body_text else "")


# ---------------------------------------------------------------------------
# list_business_rules
# ---------------------------------------------------------------------------


class ListBusinessRulesParams(BaseModel):
    """Parameters for listing all Business Rules on a table."""

    table: str = Field(
        ...,
        description=(
            "ServiceNow table name (e.g., 'incident', 'change_request'). "
            "Returns all Business Rules from sys_script whose 'collection' "
            "matches this table."
        ),
    )
    include_inactive: bool = Field(
        default=False,
        description="If True, include inactive Business Rules. Default: active only.",
    )


class BusinessRuleSummary(BaseModel):
    """Summary of one Business Rule from sys_script."""

    sys_id: str
    name: str
    timing: str = Field(
        ...,
        description="Execution timing: 'before', 'after', 'async', or 'display'.",
    )
    action_insert: bool
    action_update: bool
    action_delete: bool
    action_query: bool
    active: bool
    condition: str = Field(
        default="",
        description="Condition expression. Empty means the rule runs unconditionally.",
    )
    script_preview: str = Field(
        ...,
        description="First 500 characters of the rule script.",
    )


class ListBusinessRulesResult(BaseModel):
    """All Business Rules on a table from sys_script."""

    table: str
    rules: List[BusinessRuleSummary] = Field(default_factory=list)
    total: int = Field(default=0, description="Number of rules returned.")
    fetch_error: Optional[str] = Field(None)


def list_business_rules(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: ListBusinessRulesParams,
) -> ListBusinessRulesResult:
    """
    Query sys_script for all Business Rules on a table.

    Returns all rules with timing, trigger flags (insert/update/delete/query),
    condition, and a script preview. Use this for architecture blueprints and
    pre-implementation research to understand what automation already exists on
    a table.

    To investigate a specific field write mismatch, use get_business_rules
    (write_safety_tools) which filters by field name. This tool returns ALL rules
    on the table without a field filter.

    Does not modify any records.
    """
    query = f"collection={params.table}"
    if not params.include_inactive:
        query += "^active=true"

    try:
        response = requests.get(
            f"{config.api_url}/table/sys_script",
            params={
                "sysparm_query": query,
                "sysparm_fields": (
                    "sys_id,name,when,action_insert,action_update,"
                    "action_delete,action_query,active,condition,script"
                ),
                "sysparm_limit": 200,
                "sysparm_order_by": "when",
            },
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()
        results = response.json().get("result", [])
        rules = [
            BusinessRuleSummary(
                sys_id=_str(row.get("sys_id")),
                name=_str(row.get("name")),
                timing=_str(row.get("when")),
                action_insert=parse_snow_bool(row.get("action_insert")),
                action_update=parse_snow_bool(row.get("action_update")),
                action_delete=parse_snow_bool(row.get("action_delete")),
                action_query=parse_snow_bool(row.get("action_query")),
                active=parse_snow_bool(row.get("active")),
                condition=_str(row.get("condition")),
                script_preview=_preview(row.get("script")),
            )
            for row in results
        ]
        logger.info("list_business_rules | table=%s | count=%d", params.table, len(rules))
        return ListBusinessRulesResult(table=params.table, rules=rules, total=len(rules))
    except requests.RequestException as e:
        err = _request_error(e)
        logger.error("list_business_rules | failed | table=%s | error=%s", params.table, err)
        return ListBusinessRulesResult(table=params.table, fetch_error=err)


# ---------------------------------------------------------------------------
# list_ui_policies
# ---------------------------------------------------------------------------


class ListUIPoliciesParams(BaseModel):
    """Parameters for listing all UI Policies on a table."""

    table: str = Field(
        ...,
        description=(
            "ServiceNow table name. Returns all UI Policies from sys_ui_policy "
            "whose 'applies_to' matches this table. UI Policies are browser-form "
            "only — they have no effect on REST API reads or writes."
        ),
    )
    include_inactive: bool = Field(
        default=False,
        description="If True, include inactive UI Policies. Default: active only.",
    )


class UIPolicySummary(BaseModel):
    """Summary of one UI Policy from sys_ui_policy."""

    sys_id: str
    name: str
    active: bool
    run_scripts: bool = Field(
        default=False,
        description="True if this policy also runs associated script actions.",
    )
    short_description: str = Field(default="")


class ListUIPoliciesResult(BaseModel):
    """All UI Policies on a table from sys_ui_policy."""

    table: str
    policies: List[UIPolicySummary] = Field(default_factory=list)
    total: int = Field(default=0)
    api_relevant: bool = Field(
        default=False,
        description=(
            "Always False. UI Policies are browser-form-only and have no effect "
            "on REST API reads or writes."
        ),
    )
    fetch_error: Optional[str] = Field(None)


def list_ui_policies(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: ListUIPoliciesParams,
) -> ListUIPoliciesResult:
    """
    Query sys_ui_policy for all UI Policies on a table.

    Returns policy name, active state, run_scripts flag, and short description.
    UI Policies are enforced exclusively in the browser form — they have no
    effect on REST API writes.

    To check a specific field's visibility, mandatory, or read-only state in
    the form use get_ui_policies (write_safety_tools) which filters by field name
    via sys_ui_policy_action. This tool returns all policies on the table.

    Does not modify any records.
    """
    query = f"applies_to.name={params.table}"
    if not params.include_inactive:
        query += "^active=true"

    try:
        response = requests.get(
            f"{config.api_url}/table/sys_ui_policy",
            params={
                "sysparm_query": query,
                "sysparm_fields": "sys_id,name,active,run_scripts,short_description",
                "sysparm_limit": 200,
                "sysparm_order_by": "name",
            },
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()
        results = response.json().get("result", [])
        policies = [
            UIPolicySummary(
                sys_id=_str(row.get("sys_id")),
                name=_str(row.get("name")),
                active=parse_snow_bool(row.get("active")),
                run_scripts=parse_snow_bool(row.get("run_scripts")),
                short_description=_str(row.get("short_description")),
            )
            for row in results
        ]
        logger.info("list_ui_policies | table=%s | count=%d", params.table, len(policies))
        return ListUIPoliciesResult(table=params.table, policies=policies, total=len(policies))
    except requests.RequestException as e:
        err = _request_error(e)
        logger.error("list_ui_policies | failed | table=%s | error=%s", params.table, err)
        return ListUIPoliciesResult(table=params.table, fetch_error=err)


# ---------------------------------------------------------------------------
# list_client_scripts
# ---------------------------------------------------------------------------


class ListClientScriptsParams(BaseModel):
    """Parameters for listing all Client Scripts on a table."""

    table: str = Field(
        ...,
        description=(
            "ServiceNow table name. Returns all Client Scripts from "
            "sys_script_client (onChange, onLoad, onSubmit) for this table."
        ),
    )
    include_inactive: bool = Field(
        default=False,
        description="If True, include inactive Client Scripts. Default: active only.",
    )


class ClientScriptSummary(BaseModel):
    """Summary of one Client Script from sys_script_client."""

    sys_id: str
    name: str
    script_type: str = Field(
        ...,
        description="onChange, onLoad, onSubmit, or onCellEdit.",
    )
    field_name: str = Field(
        default="",
        description="Field this onChange script watches. Empty for onLoad/onSubmit.",
    )
    active: bool
    script_preview: str = Field(..., description="First 500 characters of the script.")


class ListClientScriptsResult(BaseModel):
    """All Client Scripts on a table from sys_script_client."""

    table: str
    scripts: List[ClientScriptSummary] = Field(default_factory=list)
    total: int = Field(default=0)
    fetch_error: Optional[str] = Field(None)


def list_client_scripts(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: ListClientScriptsParams,
) -> ListClientScriptsResult:
    """
    Query sys_script_client for all Client Scripts on a table.

    Returns name, script type (onChange/onLoad/onSubmit), the watched field
    (for onChange), active state, and a script preview. Client scripts run in
    the browser and do not affect server-side API writes.

    Does not modify any records.
    """
    query = f"table={params.table}"
    if not params.include_inactive:
        query += "^active=true"

    try:
        response = requests.get(
            f"{config.api_url}/table/sys_script_client",
            params={
                "sysparm_query": query,
                "sysparm_fields": "sys_id,name,type,field_name,active,script",
                "sysparm_limit": 200,
                "sysparm_order_by": "type",
            },
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()
        results = response.json().get("result", [])
        scripts = [
            ClientScriptSummary(
                sys_id=_str(row.get("sys_id")),
                name=_str(row.get("name")),
                script_type=_str(row.get("type")),
                field_name=_str(row.get("field_name")),
                active=parse_snow_bool(row.get("active")),
                script_preview=_preview(row.get("script")),
            )
            for row in results
        ]
        logger.info("list_client_scripts | table=%s | count=%d", params.table, len(scripts))
        return ListClientScriptsResult(table=params.table, scripts=scripts, total=len(scripts))
    except requests.RequestException as e:
        err = _request_error(e)
        logger.error("list_client_scripts | failed | table=%s | error=%s", params.table, err)
        return ListClientScriptsResult(table=params.table, fetch_error=err)


# ---------------------------------------------------------------------------
# list_notifications
# ---------------------------------------------------------------------------


class ListNotificationsParams(BaseModel):
    """Parameters for listing all Notifications configured for a table."""

    table: str = Field(
        ...,
        description=(
            "ServiceNow table name. Returns all Notifications from "
            "sysevent_email_action whose 'collection' matches this table."
        ),
    )
    include_inactive: bool = Field(
        default=False,
        description="If True, include inactive Notifications. Default: active only.",
    )


class NotificationSummary(BaseModel):
    """Summary of one Notification from sysevent_email_action."""

    sys_id: str
    name: str
    active: bool
    event_name: str = Field(
        default="",
        description=(
            "Platform event that triggers this notification "
            "(e.g., 'incident.updated'). Empty for condition-based notifications."
        ),
    )
    subject: str = Field(default="", description="Email subject template.")
    condition: str = Field(
        default="",
        description="GlideRecord filter condition controlling when this fires.",
    )


class ListNotificationsResult(BaseModel):
    """All Notifications for a table from sysevent_email_action."""

    table: str
    notifications: List[NotificationSummary] = Field(default_factory=list)
    total: int = Field(default=0)
    fetch_error: Optional[str] = Field(None)


def list_notifications(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: ListNotificationsParams,
) -> ListNotificationsResult:
    """
    Query sysevent_email_action for all Notifications configured for a table.

    Returns notification name, triggering event, email subject template, and
    filter condition. Use this for architecture blueprints to understand what
    outbound communications are triggered by record changes on the table.

    Does not modify any records.
    """
    query = f"collection={params.table}"
    if not params.include_inactive:
        query += "^active=true"

    try:
        response = requests.get(
            f"{config.api_url}/table/sysevent_email_action",
            params={
                "sysparm_query": query,
                "sysparm_fields": "sys_id,name,active,event_name,subject,condition",
                "sysparm_limit": 200,
                "sysparm_order_by": "name",
                "sysparm_display_value": "all",
            },
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()
        results = response.json().get("result", [])
        notifications = [
            NotificationSummary(
                sys_id=_str(row.get("sys_id")),
                name=_str(row.get("name")),
                active=parse_snow_bool(row.get("active")),
                event_name=_str(row.get("event_name")),
                subject=_str(row.get("subject")),
                condition=_str(row.get("condition")),
            )
            for row in results
        ]
        logger.info(
            "list_notifications | table=%s | count=%d", params.table, len(notifications)
        )
        return ListNotificationsResult(
            table=params.table, notifications=notifications, total=len(notifications)
        )
    except requests.RequestException as e:
        err = _request_error(e)
        logger.error("list_notifications | failed | table=%s | error=%s", params.table, err)
        return ListNotificationsResult(table=params.table, fetch_error=err)


# ---------------------------------------------------------------------------
# list_ui_actions
# ---------------------------------------------------------------------------


class ListUIActionsParams(BaseModel):
    """Parameters for listing all UI Actions on a table."""

    table: str = Field(
        ...,
        description=(
            "ServiceNow table name. Returns all UI Actions from sys_ui_action "
            "(form buttons, context menu items, list actions) for this table."
        ),
    )
    include_inactive: bool = Field(
        default=False,
        description="If True, include inactive UI Actions. Default: active only.",
    )


class UIActionSummary(BaseModel):
    """Summary of one UI Action from sys_ui_action."""

    sys_id: str
    name: str
    action_name: str = Field(
        default="",
        description="Internal action name used in scripts and references.",
    )
    form_button: bool = Field(default=False, description="True if shown as a form button.")
    form_context_menu: bool = Field(
        default=False, description="True if shown in the form context menu."
    )
    list_choice: bool = Field(
        default=False, description="True if shown as a list action choice."
    )
    active: bool
    condition: str = Field(default="", description="Condition controlling visibility.")
    script_preview: str = Field(..., description="First 500 characters of the action script.")


class ListUIActionsResult(BaseModel):
    """All UI Actions on a table from sys_ui_action."""

    table: str
    actions: List[UIActionSummary] = Field(default_factory=list)
    total: int = Field(default=0)
    fetch_error: Optional[str] = Field(None)


def list_ui_actions(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: ListUIActionsParams,
) -> ListUIActionsResult:
    """
    Query sys_ui_action for all UI Actions on a table.

    Returns buttons, context menu items, and list actions with their visibility
    conditions and script previews. Use this to understand what user-initiated
    actions (and their server-side scripts) are available on the table.

    Does not modify any records.
    """
    query = f"table={params.table}"
    if not params.include_inactive:
        query += "^active=true"

    try:
        response = requests.get(
            f"{config.api_url}/table/sys_ui_action",
            params={
                "sysparm_query": query,
                "sysparm_fields": (
                    "sys_id,name,action_name,form_button,form_context_menu,"
                    "list_choice,active,condition,script"
                ),
                "sysparm_limit": 200,
                "sysparm_order_by": "name",
            },
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()
        results = response.json().get("result", [])
        actions = [
            UIActionSummary(
                sys_id=_str(row.get("sys_id")),
                name=_str(row.get("name")),
                action_name=_str(row.get("action_name")),
                form_button=parse_snow_bool(row.get("form_button")),
                form_context_menu=parse_snow_bool(row.get("form_context_menu")),
                list_choice=parse_snow_bool(row.get("list_choice")),
                active=parse_snow_bool(row.get("active")),
                condition=_str(row.get("condition")),
                script_preview=_preview(row.get("script")),
            )
            for row in results
        ]
        logger.info("list_ui_actions | table=%s | count=%d", params.table, len(actions))
        return ListUIActionsResult(table=params.table, actions=actions, total=len(actions))
    except requests.RequestException as e:
        err = _request_error(e)
        logger.error("list_ui_actions | failed | table=%s | error=%s", params.table, err)
        return ListUIActionsResult(table=params.table, fetch_error=err)


# ---------------------------------------------------------------------------
# list_access_controls
# ---------------------------------------------------------------------------


class ListAccessControlsParams(BaseModel):
    """Parameters for listing all Access Control rules (ACLs) for a table."""

    table: str = Field(
        ...,
        description=(
            "ServiceNow table name. Returns ACL records from sys_security_acl "
            "whose name starts with '<table>.' — covers both record-level ACLs "
            "(e.g., 'incident.read') and field-level ACLs "
            "(e.g., 'incident.caller_id.write')."
        ),
    )
    include_inactive: bool = Field(
        default=False,
        description="If True, include inactive ACL records. Default: active only.",
    )


class AccessControlSummary(BaseModel):
    """Summary of one ACL rule from sys_security_acl."""

    sys_id: str
    name: str = Field(
        ...,
        description=(
            "ACL name — format '<table>.<operation>' (record-level) or "
            "'<table>.<field>.<operation>' (field-level)."
        ),
    )
    acl_type: str = Field(
        default="",
        description="'record' for table-level, 'field' for field-level ACLs.",
    )
    operation: str = Field(
        default="",
        description="Access operation: read, write, create, delete, or execute.",
    )
    active: bool
    roles: str = Field(
        default="",
        description=(
            "Comma-separated list of roles required. "
            "Empty means no role restriction (condition/script only)."
        ),
    )
    condition: str = Field(default="", description="GlideRecord condition expression.")
    script_preview: str = Field(
        ...,
        description=(
            "First 500 characters of the ACL script. "
            "May be empty if the ACL uses only roles and conditions."
        ),
    )


class ListAccessControlsResult(BaseModel):
    """All Access Control rules for a table from sys_security_acl."""

    table: str
    rules: List[AccessControlSummary] = Field(default_factory=list)
    total: int = Field(default=0)
    fetch_error: Optional[str] = Field(None)


def list_access_controls(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: ListAccessControlsParams,
) -> ListAccessControlsResult:
    """
    Query sys_security_acl for all Access Control rules for a table.

    Uses a STARTSWITH query on the ACL name field so both record-level ACLs
    (e.g., 'incident.read') and field-level ACLs (e.g., 'incident.caller_id.write')
    are returned. A client-side prefix check filters out any unintended matches
    (e.g., 'incident_task' when querying for 'incident').

    Returns operation, required roles, condition, and script preview. Use this
    for architecture blueprints and security reviews.

    Does not modify any records.
    """
    query = f"nameSTARTSWITH{params.table}."
    if not params.include_inactive:
        query += "^active=true"

    try:
        response = requests.get(
            f"{config.api_url}/table/sys_security_acl",
            params={
                "sysparm_query": query,
                "sysparm_fields": "sys_id,name,type,operation,active,roles,condition,script",
                "sysparm_limit": 500,
                "sysparm_order_by": "name",
                "sysparm_display_value": "all",
            },
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()
        results = response.json().get("result", [])

        # Client-side exact-prefix filter to exclude tables like 'incident_task'
        # when querying for 'incident'.
        prefix = params.table + "."
        rules = []
        for row in results:
            acl_name = _str(row.get("name"))
            if not acl_name.startswith(prefix):
                continue
            roles_raw = row.get("roles")
            if isinstance(roles_raw, list):
                roles_str = ", ".join(_str(r) for r in roles_raw)
            else:
                roles_str = _str(roles_raw)
            rules.append(
                AccessControlSummary(
                    sys_id=_str(row.get("sys_id")),
                    name=acl_name,
                    acl_type=_str(row.get("type")),
                    operation=_str(row.get("operation")),
                    active=parse_snow_bool(row.get("active")),
                    roles=roles_str,
                    condition=_str(row.get("condition")),
                    script_preview=_preview(row.get("script")),
                )
            )

        logger.info("list_access_controls | table=%s | count=%d", params.table, len(rules))
        return ListAccessControlsResult(table=params.table, rules=rules, total=len(rules))
    except requests.RequestException as e:
        err = _request_error(e)
        logger.error("list_access_controls | failed | table=%s | error=%s", params.table, err)
        return ListAccessControlsResult(table=params.table, fetch_error=err)
