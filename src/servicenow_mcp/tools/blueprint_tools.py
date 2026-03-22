"""
Introspection tools for the ServiceNow MCP server.

Provides field- and relationship-level discovery from sys_dictionary for
architecture blueprint generation. Used by the Investigator Agent to
reverse-engineer table fields and outbound reference relationships.

Note: get_table_metadata and list_child_tables have been removed.
Use query_records on sys_db_object instead:
- Table metadata: query_records on sys_db_object (filter: name=<table_name>)
- Child tables: query_records on sys_db_object (filter: super_class.name=<parent_table>)

All tools are read-only and do not modify any records.
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
    source_table: str = Field(
        default="",
        description=(
            "Table where this field is defined. "
            "Populated when include_inherited=True to distinguish own fields from inherited ones."
        ),
    )


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
    include_inherited: bool = Field(
        default=False,
        description=(
            "If True, also return fields from all parent tables in the inheritance chain "
            "(walks super_class_name until no parent is found). "
            "Child-table fields take precedence over parent fields with the same name. "
            "Each field's source_table indicates which table in the chain defines it. "
            "Use this for inheritance-heavy modules (e.g. Flow Designer, CMDB) where "
            "significant fields live on a parent class."
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


def _extract_display_or_value(raw: Any) -> str:
    """Extract string from a display_value/value dict or return str(raw)."""
    if isinstance(raw, dict):
        return (raw.get("display_value") or raw.get("value") or "").strip()
    return str(raw).strip() if raw is not None else ""


def _get_parent_name(
    config: ServerConfig,
    auth_manager: AuthManager,
    table: str,
) -> str:
    """Return the parent table name (super_class) for a table, or '' if none."""
    try:
        response = requests.get(
            f"{config.api_url}/table/sys_db_object",
            params={
                "sysparm_query": f"name={table}",
                "sysparm_fields": "super_class",
                "sysparm_limit": 1,
                "sysparm_display_value": "all",
            },
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()
        results = response.json().get("result", [])
        if not results:
            return ""
        sc = results[0].get("super_class")
        if isinstance(sc, dict):
            return (sc.get("display_value") or sc.get("value") or "").strip()
        return str(sc).strip() if sc else ""
    except Exception:
        return ""


def _query_dict_for_table(
    config: ServerConfig,
    auth_manager: AuthManager,
    table: str,
    include_system: bool,
) -> tuple:
    """
    Query sys_dictionary for one table's field rows.

    Filters out collection rows (the per-table header row in sys_dictionary that
    has internal_type='collection' and a null element). Returns (fields, error_or_None).
    """
    try:
        query = f"name={table}^active=true^internal_type!=collection"
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
            element = _extract_display_or_value(rec.get("element"))
            if not element:
                continue
            if not include_system and str(element).startswith("sys_"):
                continue
            internal_type = _extract_display_or_value(rec.get("internal_type")) or ""
            reference = _extract_display_or_value(rec.get("reference")) or ""
            read_only = parse_snow_bool(rec.get("read_only", False))
            calculated = parse_snow_bool(rec.get("calculated", False))
            mandatory = parse_snow_bool(rec.get("mandatory", False))
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
                    source_table=table,
                )
            )
        return fields, None
    except requests.RequestException as e:
        body = getattr(e, "response", None)
        body_text = (body.text[:2000] if body and hasattr(body, "text") else "") or ""
        return [], str(e) + (f" | response: {body_text}" if body_text else "")


def list_table_fields(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: ListTableFieldsParams,
) -> ListTableFieldsResult:
    """
    Query sys_dictionary for all columns of a table.

    Returns field name, internal_type, reference (for reference fields), read_only,
    calculated, mandatory, and default_value. Collection rows (the per-table header
    row in sys_dictionary) are filtered out automatically.

    When include_inherited=True, also returns fields from all parent tables in the
    inheritance chain. Child fields take precedence over same-named parent fields.
    Each field's source_table indicates which table in the chain defines it.

    Args:
        config: Server configuration.
        auth_manager: Authentication manager.
        params: Table name, include_system flag, and include_inherited flag.

    Returns:
        ListTableFieldsResult with list of TableFieldInfo.
    """
    fields, error = _query_dict_for_table(config, auth_manager, params.table, params.include_system)
    if error:
        logger.error(
            "list_table_fields | failed | table=%s | error=%s",
            params.table,
            error,
        )
        return ListTableFieldsResult(table=params.table, fetch_error=error)

    if params.include_inherited:
        seen_tables = {params.table}
        seen_fields = {f.field for f in fields}
        current = params.table
        for _ in range(10):  # guard against circular inheritance (max 10 levels)
            parent = _get_parent_name(config, auth_manager, current)
            if not parent or parent in seen_tables:
                break
            seen_tables.add(parent)
            parent_fields, _ = _query_dict_for_table(
                config, auth_manager, parent, params.include_system
            )
            for f in parent_fields:
                if f.field not in seen_fields:
                    fields.append(f)
                    seen_fields.add(f.field)
            current = parent

    return ListTableFieldsResult(table=params.table, fields=fields)


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
    include_inherited: bool = Field(
        default=False,
        description=(
            "If True, also include reference fields from parent tables in the inheritance chain. "
            "Use for inheritance-heavy modules where outbound relationships are defined on a parent class."
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
    list_params = ListTableFieldsParams(
        table=params.table,
        include_system=False,
        include_inherited=params.include_inherited,
    )
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
                    from_table=f.source_table or params.table,
                    from_field=f.field,
                    to_table=f.reference,
                )
            )
    return ListTableRelationshipsResult(
        table=params.table,
        relationships=relationships,
    )

