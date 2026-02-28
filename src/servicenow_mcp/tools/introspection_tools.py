"""
Introspection tools for the ServiceNow MCP server.

Provides table- and module-level discovery from sys_db_object and sys_dictionary
for architecture blueprint generation. Used by the Investigator Agent to
reverse-engineer table hierarchy, fields, and relationships.

All tools are read-only and do not modify any records.
"""

import logging
from typing import Any, List, Optional

import requests
from pydantic import BaseModel, Field

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.utils.config import ServerConfig

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# get_table_metadata
# ---------------------------------------------------------------------------


class GetTableMetadataParams(BaseModel):
    """Parameters for querying sys_db_object for a single table's metadata."""

    table: str = Field(
        ...,
        description=(
            "ServiceNow table name (e.g., 'incident', 'change_request', 'task'). "
            "Returns label, extends (parent table), and scope/application info."
        ),
    )


class GetTableMetadataResult(BaseModel):
    """Metadata for a single table from sys_db_object."""

    table: str = Field(..., description="Table name that was queried.")
    table_found: bool = Field(
        ...,
        description="True if sys_db_object returned a record for this table.",
    )
    label: str = Field(
        default="",
        description="Human-readable table label from sys_db_object.",
    )
    extends: str = Field(
        default="",
        description=(
            "Parent table name (super_class). Empty if this table does not extend another. "
            "Use list_child_tables on the parent to enumerate children."
        ),
    )
    scope: str = Field(
        default="",
        description="Application scope or sys_scope label if available.",
    )
    fetch_error: Optional[str] = Field(
        None,
        description="Set if the sys_db_object query failed.",
    )


def get_table_metadata(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: GetTableMetadataParams,
) -> GetTableMetadataResult:
    """
    Query sys_db_object for a table's metadata: label, extends (parent table), scope.

    Use this to build a table hierarchy and human-readable labels for architecture
    blueprints. Does not modify any records.

    Args:
        config: Server configuration.
        auth_manager: Authentication manager.
        params: Table name to look up.

    Returns:
        GetTableMetadataResult with label, extends, and scope when found.
    """
    try:
        response = requests.get(
            f"{config.api_url}/table/sys_db_object",
            params={
                "sysparm_query": f"name={params.table}",
                "sysparm_fields": "name,label,super_class,sys_scope",
                "sysparm_limit": 1,
                "sysparm_display_value": "all",
            },
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()
        results = response.json().get("result", [])
        if not results:
            return GetTableMetadataResult(
                table=params.table,
                table_found=False,
            )
        rec = results[0]
        # super_class is a reference; may return {"value": "sys_id", "display_value": "task"}
        super_class = rec.get("super_class")
        extends = ""
        if isinstance(super_class, dict):
            extends = (super_class.get("display_value") or super_class.get("value") or "").strip()
        elif isinstance(super_class, str):
            extends = super_class.strip()
        sys_scope = rec.get("sys_scope")
        scope = ""
        if isinstance(sys_scope, dict):
            scope = (sys_scope.get("display_value") or sys_scope.get("value") or "").strip()
        elif isinstance(sys_scope, str):
            scope = sys_scope.strip()
        label = (rec.get("label") or "").strip() or params.table.replace("_", " ").title()
        return GetTableMetadataResult(
            table=params.table,
            table_found=True,
            label=label,
            extends=extends,
            scope=scope,
        )
    except requests.RequestException as e:
        body = getattr(e, "response", None)
        body_text = (body.text[:2000] if body and hasattr(body, "text") else "") or ""
        logger.error(
            "get_table_metadata | failed | table=%s | error=%s%s",
            params.table,
            e,
            f" | body={body_text}" if body_text else "",
        )
        return GetTableMetadataResult(
            table=params.table,
            table_found=False,
            fetch_error=str(e) + (f" | response: {body_text}" if body_text else ""),
        )


# ---------------------------------------------------------------------------
# list_table_fields
# ---------------------------------------------------------------------------


class TableFieldInfo(BaseModel):
    """One field from sys_dictionary for a table."""

    field: str = Field(..., description="Field (element) name.")
    internal_type: str = Field(default="", description="Data type (string, choice, reference, etc.).")
    reference: str = Field(
        default="",
        description="Target table name for reference fields. Empty otherwise.",
    )
    read_only: bool = Field(default=False, description="True if field is read-only.")
    calculated: bool = Field(default=False, description="True if field is calculated.")
    mandatory: bool = Field(default=False, description="True if field is mandatory.")
    default_value: str = Field(default="", description="Default value if set.")


class ListTableFieldsParams(BaseModel):
    """Parameters for listing all fields of a table from sys_dictionary."""

    table: str = Field(
        ...,
        description=(
            "ServiceNow table name (e.g., 'incident', 'task'). "
            "Returns all active columns with type, reference target, and writability hints."
        ),
    )
    include_system: bool = Field(
        default=False,
        description=(
            "If True, include system/internal columns (name starting with sys_). "
            "Default False returns business and custom fields only."
        ),
    )


class ListTableFieldsResult(BaseModel):
    """Result of listing table fields from sys_dictionary."""

    table: str = Field(..., description="Table that was queried.")
    fields: List[TableFieldInfo] = Field(
        default_factory=list,
        description="List of field metadata for the table.",
    )
    fetch_error: Optional[str] = Field(
        None,
        description="Set if the sys_dictionary query failed.",
    )


def _parse_snow_bool(value: Any) -> bool:
    """Normalize ServiceNow boolean to Python bool."""
    if value is None:
        return False
    s = str(value).strip().lower()
    return s in ("true", "1", "yes")


def _extract_display_or_value(raw: Any) -> str:
    """Extract string from a display_value/value dict or return str(raw)."""
    if isinstance(raw, dict):
        return (raw.get("display_value") or raw.get("value") or "").strip()
    return str(raw).strip() if raw is not None else ""


def list_table_fields(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: ListTableFieldsParams,
) -> ListTableFieldsResult:
    """
    Query sys_dictionary for all columns of a table.

    Returns field name, internal_type, reference (for reference fields), read_only,
    calculated, mandatory, and default_value. Use this to build architecture
    blueprints and relationship maps. Does not modify any records.

    Args:
        config: Server configuration.
        auth_manager: Authentication manager.
        params: Table name and optional include_system flag.

    Returns:
        ListTableFieldsResult with list of TableFieldInfo.
    """
    try:
        query = f"name={params.table}^active=true"
        response = requests.get(
            f"{config.api_url}/table/sys_dictionary",
            params={
                "sysparm_query": query,
                "sysparm_fields": (
                    "element,internal_type,reference,read_only,calculated,mandatory,default_value"
                ),
                "sysparm_order_by": "element",
                "sysparm_limit": 5000,
                "sysparm_display_value": "all",
            },
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()
        results = response.json().get("result", [])
        fields: List[TableFieldInfo] = []
        for rec in results:
            element = _extract_display_or_value(rec.get("element")) or rec.get("element")
            if not element:
                continue
            if not params.include_system and str(element).startswith("sys_"):
                continue
            internal_type = _extract_display_or_value(rec.get("internal_type")) or ""
            reference = _extract_display_or_value(rec.get("reference")) or ""
            read_only = _parse_snow_bool(rec.get("read_only", False))
            calculated = _parse_snow_bool(rec.get("calculated", False))
            mandatory = _parse_snow_bool(rec.get("mandatory", False))
            default_value = _extract_display_or_value(rec.get("default_value")) or ""
            fields.append(
                TableFieldInfo(
                    field=element,
                    internal_type=internal_type,
                    reference=reference,
                    read_only=read_only,
                    calculated=calculated,
                    mandatory=mandatory,
                    default_value=default_value,
                )
            )
        return ListTableFieldsResult(table=params.table, fields=fields)
    except requests.RequestException as e:
        body = getattr(e, "response", None)
        body_text = (body.text[:2000] if body and hasattr(body, "text") else "") or ""
        logger.error(
            "list_table_fields | failed | table=%s | error=%s%s",
            params.table,
            e,
            f" | body={body_text}" if body_text else "",
        )
        return ListTableFieldsResult(
            table=params.table,
            fetch_error=str(e) + (f" | response: {body_text}" if body_text else ""),
        )


# ---------------------------------------------------------------------------
# list_table_relationships
# ---------------------------------------------------------------------------


class TableRelationship(BaseModel):
    """A relationship from one table to another via a reference field."""

    from_table: str = Field(..., description="Table that owns the reference field.")
    from_field: str = Field(..., description="Reference field name.")
    to_table: str = Field(..., description="Target table of the reference.")


class ListTableRelationshipsParams(BaseModel):
    """Parameters for listing reference relationships for a table."""

    table: str = Field(
        ...,
        description=(
            "ServiceNow table name. Returns all reference fields and their target tables "
            "from sys_dictionary (outbound relationships)."
        ),
    )


class ListTableRelationshipsResult(BaseModel):
    """Result of listing table relationships."""

    table: str = Field(..., description="Table that was queried.")
    relationships: List[TableRelationship] = Field(
        default_factory=list,
        description="Outbound reference relationships (from_field -> to_table).",
    )
    fetch_error: Optional[str] = Field(
        None,
        description="Set if the query failed.",
    )


def list_table_relationships(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: ListTableRelationshipsParams,
) -> ListTableRelationshipsResult:
    """
    Derive outbound relationships for a table from sys_dictionary reference fields.

    Queries sys_dictionary for the table and returns each reference-type field
    with its target table. Use this to build relationship graphs for architecture
    blueprints. Does not modify any records.

    Args:
        config: Server configuration.
        auth_manager: Authentication manager.
        params: Table name.

    Returns:
        ListTableRelationshipsResult with list of TableRelationship.
    """
    list_params = ListTableFieldsParams(table=params.table, include_system=False)
    list_result = list_table_fields(config, auth_manager, list_params)
    if list_result.fetch_error:
        return ListTableRelationshipsResult(
            table=params.table,
            fetch_error=list_result.fetch_error,
        )
    relationships: List[TableRelationship] = []
    for f in list_result.fields:
        if (f.internal_type or "").lower() == "reference" and f.reference:
            relationships.append(
                TableRelationship(
                    from_table=params.table,
                    from_field=f.field,
                    to_table=f.reference,
                )
            )
    return ListTableRelationshipsResult(
        table=params.table,
        relationships=relationships,
    )


# ---------------------------------------------------------------------------
# list_child_tables
# ---------------------------------------------------------------------------


class ListChildTablesParams(BaseModel):
    """Parameters for listing child tables that extend a parent (sys_db_object.super_class)."""

    parent_table: str = Field(
        ...,
        description=(
            "Parent table name (e.g., 'task', 'cmdb_ci'). "
            "Returns all tables whose super_class (extends) is this table."
        ),
    )


class ListChildTablesResult(BaseModel):
    """Result of listing child tables."""

    parent_table: str = Field(..., description="Parent table that was queried.")
    child_tables: List[str] = Field(
        default_factory=list,
        description="List of table names that extend the parent.",
    )
    fetch_error: Optional[str] = Field(
        None,
        description="Set if the sys_db_object query failed.",
    )


def list_child_tables(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: ListChildTablesParams,
) -> ListChildTablesResult:
    """
    Query sys_db_object for all tables that extend (super_class) a given parent table.

    Use this to discover table hierarchy for architecture blueprints (e.g. all
    tables extending task or cmdb_ci). Does not modify any records.

    Args:
        config: Server configuration.
        auth_manager: Authentication manager.
        params: Parent table name.

    Returns:
        ListChildTablesResult with list of child table names.
    """
    try:
        # super_class is a reference; query by display_value or value
        response = requests.get(
            f"{config.api_url}/table/sys_db_object",
            params={
                "sysparm_query": f"super_class.name={params.parent_table}",
                "sysparm_fields": "name",
                "sysparm_limit": 500,
                "sysparm_order_by": "name",
            },
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()
        results = response.json().get("result", [])
        child_tables = [r.get("name", "").strip() for r in results if r.get("name")]
        return ListChildTablesResult(
            parent_table=params.parent_table,
            child_tables=child_tables,
        )
    except requests.RequestException as e:
        body = getattr(e, "response", None)
        body_text = (body.text[:2000] if body and hasattr(body, "text") else "") or ""
        logger.error(
            "list_child_tables | failed | parent=%s | error=%s%s",
            params.parent_table,
            e,
            f" | body={body_text}" if body_text else "",
        )
        return ListChildTablesResult(
            parent_table=params.parent_table,
            fetch_error=str(e) + (f" | response: {body_text}" if body_text else ""),
        )
