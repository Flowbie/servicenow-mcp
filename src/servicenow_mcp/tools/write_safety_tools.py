"""
Metadata and verification tools for the ServiceNow MCP server.

Provides two categories of tools:

1. Write verification (verify_fields)
   Re-fetch a record after a write and compare field values against what was
   intended. HTTP 200 from the write tool does not guarantee persistence.

2. Metadata discovery (get_field_metadata)
   Query sys_dictionary before writing to determine whether a field is
   writable. This replaces hardcoded static registries with live instance
   queries.

Removed tools (use query_records directly instead):
- get_field_choices      → query_records on sys_choice
                           (filter: name=<table>^element=<field>^inactive=false)
- get_data_policies      → query_records on sys_data_policy2
                           (filter: applies_to=<table>)
- get_data_lookup_rules  → query_records on dl_definition
                           (filter: active=true^table=<table>)
- get_business_rules     → query_records on sys_script
                           (filter: collection=<table>^active=true)
- get_ui_policies        → query_records on sys_ui_policy_action
                           (filter: table=<table>^field_name=<field>)

Together these tools implement: discover → write → verify → diagnose.
"""

import logging
from typing import Optional

import requests
from pydantic import BaseModel, Field

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.utils.config import ServerConfig
from servicenow_mcp.utils.snow_utils import parse_snow_bool

logger = logging.getLogger(__name__)


class VerifyFieldsParams(BaseModel):
    """Parameters for verifying field values on a ServiceNow record after a write."""

    table: str = Field(
        ...,
        description="ServiceNow table name (e.g., 'incident', 'change_request', 'sc_task').",
    )
    record_id: str = Field(
        ...,
        description=(
            "Record sys_id (32-character hex string) or record number "
            "(e.g., 'INC0007001', 'CHG0030001'). For tables without a 'number' "
            "field, always provide the sys_id."
        ),
    )
    expected: dict = Field(
        ...,
        description=(
            "Mapping of field names to their expected values after the write. "
            "Values are compared as strings against the raw stored value. "
            "Example: {\"state\": \"2\", \"impact\": \"3\", \"urgency\": \"2\"}"
        ),
    )
    use_display_values: bool = Field(
        False,
        description=(
            "When True, fetch and compare display values (e.g., 'High' instead of '1'). "
            "Default False uses raw stored values, which is more reliable for exact "
            "comparison after a write."
        ),
    )


class FieldMismatch(BaseModel):
    """A single field that did not match the expected value after a write."""

    field: str = Field(..., description="Field name that did not match.")
    expected: str = Field(..., description="Value that was intended to be written.")
    actual: str = Field(..., description="Value that was actually found on the record.")


class VerifyFieldsResult(BaseModel):
    """Result of a post-write field verification check."""

    table: str
    record_id: str
    verified: list[str] = Field(
        default_factory=list,
        description="Field names where actual value matches expected value.",
    )
    mismatched: list[FieldMismatch] = Field(
        default_factory=list,
        description=(
            "Fields where actual value differs from expected. Each entry includes "
            "the field name, what was expected, and what was actually found. "
            "A non-empty mismatched list means server-side logic overrode the write."
        ),
    )
    all_verified: bool = Field(
        ...,
        description=(
            "True only when every field in 'expected' was confirmed on the live record. "
            "False if any field mismatched or if the record could not be fetched."
        ),
    )
    fetch_error: Optional[str] = Field(
        None,
        description=(
            "Set when the record could not be fetched for verification. "
            "all_verified will be False. The write may or may not have succeeded."
        ),
    )


def verify_fields(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: VerifyFieldsParams,
) -> VerifyFieldsResult:
    """
    Re-fetch a ServiceNow record and compare specified fields against expected values.

    Call this after every write operation to confirm the change actually persisted.
    HTTP 200 from the Table API does not guarantee a field was saved — server-side
    Business Rules, Data Policies, and Data Lookup rules can silently override
    written values after the API acknowledges the request.

    This tool does not modify any records.

    Args:
        config: Server configuration.
        auth_manager: Authentication manager.
        params: Verification parameters including table, record identifier,
                and the dict of field → expected_value pairs to check.

    Returns:
        VerifyFieldsResult with verified/mismatched field lists and all_verified flag.
    """
    # Determine whether record_id is a sys_id (32 lowercase hex chars) or a number
    is_sys_id = (
        len(params.record_id) == 32
        and all(c in "0123456789abcdef" for c in params.record_id.lower())
    )

    fields_param = ",".join(params.expected.keys())

    if is_sys_id:
        fetch_url = f"{config.api_url}/table/{params.table}/{params.record_id}"
        fetch_params: dict = {"sysparm_fields": fields_param}
    else:
        fetch_url = f"{config.api_url}/table/{params.table}"
        fetch_params = {
            "sysparm_query": f"number={params.record_id}",
            "sysparm_limit": 1,
            "sysparm_fields": fields_param,
        }

    if params.use_display_values:
        fetch_params["sysparm_display_value"] = "true"

    # Fetch the record
    try:
        response = requests.get(
            fetch_url,
            params=fetch_params,
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()
    except requests.RequestException as e:
        _body = e.response.text[:2000] if getattr(e, "response", None) is not None else ""
        logger.error(
            f"verify_fields | fetch failed | table={params.table} "
            f"| record_id={params.record_id} | error={e}"
            + (f" | body={_body}" if _body else "")
        )
        return VerifyFieldsResult(
            table=params.table,
            record_id=params.record_id,
            all_verified=False,
            fetch_error=f"Failed to fetch record for verification: {str(e)}" + (f" | response: {_body}" if _body else ""),
        )

    # Extract the record dict from the response
    data = response.json()
    if is_sys_id:
        record = data.get("result", {})
        if not record:
            return VerifyFieldsResult(
                table=params.table,
                record_id=params.record_id,
                all_verified=False,
                fetch_error=f"Record not found: {params.record_id}",
            )
    else:
        results = data.get("result", [])
        if not results:
            return VerifyFieldsResult(
                table=params.table,
                record_id=params.record_id,
                all_verified=False,
                fetch_error=f"Record not found by number: {params.record_id}",
            )
        record = results[0]

    # Compare each expected field against the actual fetched value
    verified: list[str] = []
    mismatched: list[FieldMismatch] = []

    for field_name, expected_value in params.expected.items():
        raw = record.get(field_name)

        # ServiceNow returns a dict for reference fields when use_display_values=True
        if isinstance(raw, dict):
            actual_value = (
                raw.get("display_value") if params.use_display_values else raw.get("value")
            )
        else:
            actual_value = raw

        # Normalize both sides to string; treat None as empty string
        actual_str = str(actual_value) if actual_value is not None else ""
        expected_str = str(expected_value) if expected_value is not None else ""

        if actual_str == expected_str:
            verified.append(field_name)
        else:
            mismatched.append(
                FieldMismatch(field=field_name, expected=expected_str, actual=actual_str)
            )
            logger.warning(
                f"verify_fields | mismatch | table={params.table} "
                f"| record={params.record_id} | field={field_name} "
                f"| expected={expected_str!r} | actual={actual_str!r}"
            )

    all_verified = len(mismatched) == 0

    if all_verified:
        logger.info(
            f"verify_fields | all verified | table={params.table} "
            f"| record={params.record_id} | fields={verified}"
        )
    else:
        logger.warning(
            f"verify_fields | mismatches detected | table={params.table} "
            f"| record={params.record_id} "
            f"| mismatched_fields={[m.field for m in mismatched]}"
        )

    return VerifyFieldsResult(
        table=params.table,
        record_id=params.record_id,
        verified=verified,
        mismatched=mismatched,
        all_verified=all_verified,
    )


# ---------------------------------------------------------------------------
# Metadata helpers
# ---------------------------------------------------------------------------

def _extract_field_value(raw, prefer_display: bool = False) -> str:
    """
    Extract a scalar string from a sys_display_value=all field response.

    ServiceNow returns each field as either a plain string/number or a dict
    of {"value": ..., "display_value": ...} when sysparm_display_value=all.
    """
    if isinstance(raw, dict):
        key = "display_value" if prefer_display else "value"
        return str(raw.get(key, raw.get("value", "")))
    return str(raw) if raw is not None else ""


# ---------------------------------------------------------------------------
# get_field_metadata
# ---------------------------------------------------------------------------

# Tables in the task hierarchy. If a field is not found on the requested
# table we fall back to 'task' before giving up, because most task-based
# tables (incident, change_request, problem, sc_task) inherit their field
# definitions from the task parent in sys_dictionary.
_TASK_CHILD_TABLES = {
    "incident", "change_request", "problem", "sc_task",
    "sn_si_incident", "sm_order", "hr_case",
}


class FieldMetadataParams(BaseModel):
    """Parameters for querying sys_dictionary metadata for a single field."""

    table: str = Field(
        ...,
        description=(
            "ServiceNow table name to look up (e.g., 'incident', 'change_request'). "
            "If the field is defined on a parent table (e.g., task), the tool "
            "automatically falls back to the parent."
        ),
    )
    field: str = Field(
        ...,
        description="Column name to look up in sys_dictionary (e.g., 'priority', 'state').",
    )


class FieldMetadataResult(BaseModel):
    """
    Metadata for a single field from sys_dictionary.

    Use read_only and calculated to determine whether a direct write is safe.
    Use internal_type to identify choice fields that need get_field_choices.
    """

    table: str = Field(..., description="Table the dictionary entry was found on.")
    field: str = Field(..., description="Field name that was looked up.")
    resolved_table: str = Field(
        ...,
        description=(
            "Actual table where the sys_dictionary entry was found. May differ "
            "from 'table' when the field is inherited (e.g., resolved_table='task' "
            "for incident.priority)."
        ),
    )
    field_found: bool = Field(
        ...,
        description=(
            "False when no sys_dictionary entry exists for this field on the "
            "requested table or its task parent. The field may still exist as a "
            "custom or plugin field with no explicit dictionary record."
        ),
    )
    read_only: bool = Field(
        False,
        description="True if the field is marked read-only in sys_dictionary.",
    )
    calculated: bool = Field(
        False,
        description=(
            "True if the field value is computed by a formula or data lookup. "
            "Calculated fields silently discard direct writes."
        ),
    )
    mandatory: bool = Field(
        False,
        description="True if the field is mandatory on this table.",
    )
    max_length: Optional[int] = Field(
        None,
        description="Maximum character length for string fields. None if not applicable.",
    )
    internal_type: str = Field(
        "",
        description=(
            "Field data type as stored in sys_glide_object "
            "(e.g., 'string', 'integer', 'choice', 'reference', 'boolean', "
            "'glide_date_time'). 'choice' indicates the field has a restricted "
            "value set — call get_field_choices before writing."
        ),
    )
    attributes: str = Field(
        "",
        description=(
            "Raw attributes string from sys_dictionary. Pipe-delimited key=value "
            "pairs used by the platform for advanced field behaviour."
        ),
    )
    default_value: str = Field(
        "",
        description="Default value configured on the field, if any.",
    )
    fetch_error: Optional[str] = Field(
        None,
        description="Set if the sys_dictionary query failed. field_found will be False.",
    )


def get_field_metadata(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: FieldMetadataParams,
) -> FieldMetadataResult:
    """
    Query sys_dictionary for a field's metadata before attempting a write.

    Determines whether the field is read_only or calculated (do not write),
    and what internal_type it is (use get_field_choices for 'choice' fields).

    Automatically falls back to the 'task' parent table if the field is not
    found on the requested table directly (covers incident, change_request,
    problem, sc_task and similar task-hierarchy tables).

    Does not modify any records.

    Args:
        config: Server configuration.
        auth_manager: Authentication manager.
        params: Table and field name to look up.

    Returns:
        FieldMetadataResult with writability flags and type information.
    """
    tables_to_try = [params.table]
    if params.table in _TASK_CHILD_TABLES and params.table != "task":
        tables_to_try.append("task")

    for candidate_table in tables_to_try:
        result = _query_sys_dictionary(config, auth_manager, candidate_table, params.field)
        if result is not None:
            # Unpack the raw record into a typed result
            return _build_metadata_result(
                requested_table=params.table,
                field=params.field,
                resolved_table=candidate_table,
                record=result,
            )
        if isinstance(result, str):
            # _query_sys_dictionary returns a string only on fetch error
            return FieldMetadataResult(
                table=params.table,
                field=params.field,
                resolved_table=params.table,
                field_found=False,
                fetch_error=result,
            )

    # Field not found on any candidate table
    return FieldMetadataResult(
        table=params.table,
        field=params.field,
        resolved_table=params.table,
        field_found=False,
    )


def _query_sys_dictionary(
    config: ServerConfig,
    auth_manager: AuthManager,
    table: str,
    field: str,
) -> Optional[dict]:
    """
    Fetch one sys_dictionary record for table+field.

    Returns the raw result dict if found, None if not found, or raises on
    network error (caller should convert to fetch_error string).
    """
    url = f"{config.api_url}/table/sys_dictionary"
    query_params = {
        "sysparm_query": f"name={table}^element={field}^active=true",
        "sysparm_limit": 1,
        "sysparm_fields": (
            "read_only,calculated,mandatory,max_length,"
            "internal_type,attributes,default_value,element,name"
        ),
        "sysparm_display_value": "all",
    }

    try:
        response = requests.get(
            url,
            params=query_params,
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()
    except requests.RequestException as e:
        _body = e.response.text[:2000] if getattr(e, "response", None) is not None else ""
        logger.error(
            f"get_field_metadata | sys_dictionary fetch failed "
            f"| table={table} | field={field} | error={e}"
            + (f" | body={_body}" if _body else "")
        )
        # Return sentinel string so the caller can distinguish error from not-found
        return f"sys_dictionary query failed: {str(e)}" + (f" | response: {_body}" if _body else "")  # type: ignore[return-value]

    results = response.json().get("result", [])
    if not results:
        logger.debug(
            f"get_field_metadata | field not found in sys_dictionary "
            f"| table={table} | field={field}"
        )
        return None

    return results[0]


def _build_metadata_result(
    requested_table: str,
    field: str,
    resolved_table: str,
    record: dict,
) -> FieldMetadataResult:
    """Build a FieldMetadataResult from a raw sys_dictionary record dict."""
    read_only = parse_snow_bool(_extract_field_value(record.get("read_only", "false")))
    calculated = parse_snow_bool(_extract_field_value(record.get("calculated", "false")))
    mandatory = parse_snow_bool(_extract_field_value(record.get("mandatory", "false")))

    max_length_raw = _extract_field_value(record.get("max_length", ""))
    max_length: Optional[int] = None
    if max_length_raw.isdigit():
        max_length = int(max_length_raw)

    # internal_type is a reference to sys_glide_object — use display_value for
    # the human-readable type name (e.g., "choice", "string", "reference").
    internal_type = _extract_field_value(record.get("internal_type", ""), prefer_display=True)
    attributes = _extract_field_value(record.get("attributes", ""))
    default_value = _extract_field_value(record.get("default_value", ""))

    logger.info(
        f"get_field_metadata | found | table={resolved_table} | field={field} "
        f"| read_only={read_only} | calculated={calculated} | type={internal_type}"
    )

    return FieldMetadataResult(
        table=requested_table,
        field=field,
        resolved_table=resolved_table,
        field_found=True,
        read_only=read_only,
        calculated=calculated,
        mandatory=mandatory,
        max_length=max_length,
        internal_type=internal_type,
        attributes=attributes,
        default_value=default_value,
    )


