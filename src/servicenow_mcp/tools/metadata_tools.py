"""
Metadata and verification tools for the ServiceNow MCP server.

Provides three categories of tools:

1. Write verification (verify_fields)
   Re-fetch a record after a write and compare field values against what was
   intended. HTTP 200 from the write tool does not guarantee persistence.

2. Metadata discovery (get_field_metadata, get_field_choices)
   Query sys_dictionary and sys_choice before writing to determine whether a
   field is writable and what values are valid. This replaces hardcoded
   static registries with live instance queries.

3. Diagnostic escalation (get_data_lookup_rules, get_business_rules,
   get_data_policies, get_ui_policies)
   Called after a verify_fields mismatch to identify which server-side
   mechanism overrode the write. Investigation order: sys_data_policy2
   (server-enforced) → dl_definition (data lookup) → sys_script (business
   rule) → sys_ui_policy (client-side only, never the API cause).

Together these tools implement: discover → write → verify → diagnose.
"""

import logging
from typing import Optional

import requests
from pydantic import BaseModel, Field

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.utils.config import ServerConfig

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


def _parse_snow_bool(value: str) -> bool:
    """
    Normalise ServiceNow boolean field representations to Python bool.

    sys_dictionary boolean columns can come back as "true"/"false",
    "1"/"0", "Yes"/"No" depending on the sysparm_display_value setting.
    """
    return value.strip().lower() in ("true", "1", "yes")


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
    read_only = _parse_snow_bool(_extract_field_value(record.get("read_only", "false")))
    calculated = _parse_snow_bool(_extract_field_value(record.get("calculated", "false")))
    mandatory = _parse_snow_bool(_extract_field_value(record.get("mandatory", "false")))

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


# ---------------------------------------------------------------------------
# get_field_choices
# ---------------------------------------------------------------------------

class FieldChoicesParams(BaseModel):
    """Parameters for querying the valid choice values for a field."""

    table: str = Field(
        ...,
        description=(
            "ServiceNow table name (e.g., 'incident'). Choice entries in sys_choice "
            "are stored under the table name where they are defined — for task-hierarchy "
            "fields this is usually 'task', not the child table."
        ),
    )
    field: str = Field(
        ...,
        description="Column name to look up choices for (e.g., 'state', 'category').",
    )
    language: str = Field(
        "en",
        description="Language code for choice labels. Defaults to 'en'.",
    )
    include_inactive: bool = Field(
        False,
        description=(
            "When True, inactive choices are included in the results. "
            "Default False returns only active choices suitable for writing."
        ),
    )


class FieldChoice(BaseModel):
    """A single valid choice value for a field."""

    value: str = Field(..., description="Raw stored value to use when writing the field.")
    label: str = Field(..., description="Human-readable label shown in the UI.")
    inactive: bool = Field(
        False, description="True if this choice is inactive and should not be written."
    )


class FieldChoicesResult(BaseModel):
    """Valid choice values for a field from sys_choice."""

    table: str
    field: str
    choices: list[FieldChoice] = Field(default_factory=list)
    choices_found: bool = Field(
        ...,
        description=(
            "False when no sys_choice entries exist for this table+field combination. "
            "If False and the field internal_type is 'choice', try the parent table "
            "(e.g., 'task' for incident fields)."
        ),
    )
    fetch_error: Optional[str] = Field(None)


def get_field_choices(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: FieldChoicesParams,
) -> FieldChoicesResult:
    """
    Query sys_choice for the valid values of a choice field.

    Call this when get_field_metadata returns internal_type='choice', or when
    the user provides a label (e.g., 'High') that needs to be resolved to a
    raw value before writing.

    Choice entries in sys_choice are keyed by the table where they are defined.
    For task-hierarchy fields (state, priority, impact, urgency), the table is
    usually 'task', not 'incident'. If this query returns choices_found=False,
    retry with table='task'.

    Does not modify any records.

    Args:
        config: Server configuration.
        auth_manager: Authentication manager.
        params: Table, field, and language to look up.

    Returns:
        FieldChoicesResult with a list of {value, label, inactive} entries.
    """
    url = f"{config.api_url}/table/sys_choice"

    query_parts = [
        f"name={params.table}",
        f"element={params.field}",
        f"language={params.language}",
    ]
    if not params.include_inactive:
        query_parts.append("inactive=false")

    query_params = {
        "sysparm_query": "^".join(query_parts) + "^ORDERBYvalue",
        "sysparm_fields": "value,label,inactive",
        "sysparm_limit": 200,
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
            f"get_field_choices | fetch failed "
            f"| table={params.table} | field={params.field} | error={e}"
            + (f" | body={_body}" if _body else "")
        )
        return FieldChoicesResult(
            table=params.table,
            field=params.field,
            choices_found=False,
            fetch_error=f"sys_choice query failed: {str(e)}" + (f" | response: {_body}" if _body else ""),
        )

    raw_results = response.json().get("result", [])
    if not raw_results:
        logger.debug(
            f"get_field_choices | no choices found "
            f"| table={params.table} | field={params.field}"
        )
        return FieldChoicesResult(
            table=params.table,
            field=params.field,
            choices_found=False,
        )

    choices = []
    for row in raw_results:
        value = str(row.get("value", ""))
        label = str(row.get("label", ""))
        inactive_raw = str(row.get("inactive", "false")).strip().lower()
        inactive = inactive_raw in ("true", "1", "yes")
        choices.append(FieldChoice(value=value, label=label, inactive=inactive))

    logger.info(
        f"get_field_choices | found {len(choices)} choices "
        f"| table={params.table} | field={params.field}"
    )

    return FieldChoicesResult(
        table=params.table,
        field=params.field,
        choices=choices,
        choices_found=True,
    )


# ---------------------------------------------------------------------------
# get_data_lookup_rules
# ---------------------------------------------------------------------------

class DataLookupRulesParams(BaseModel):
    """Parameters for querying active Data Lookup rules for a table."""

    table: str = Field(
        ...,
        description="ServiceNow table to inspect (e.g., 'incident').",
    )
    output_field: str = Field(
        "",
        description=(
            "Optional. Filter results to rules that set this specific field "
            "(e.g., 'priority'). Leave empty to return all data lookup rules "
            "for the table."
        ),
    )


class DataLookupRule(BaseModel):
    """A single active Data Lookup rule definition."""

    sys_id: str
    name: str
    output_field: str = Field(
        ...,
        description="The field this rule sets after a record insert or update.",
    )
    on_insert: bool
    on_update: bool
    active: bool


class DataLookupRulesResult(BaseModel):
    """Active Data Lookup rules for a table from dl_definition."""

    table: str
    output_field_filter: str = Field(
        "",
        description="The output_field filter applied, if any. Empty means all rules returned.",
    )
    rules: list[DataLookupRule] = Field(default_factory=list)
    rules_found: bool
    note: str = Field(
        "",
        description=(
            "The actual lookup matrix rows (which input values produce which output) "
            "are stored in a related table and are not returned here. Use the rule "
            "name and output_field to locate the full matrix in the ServiceNow UI "
            "under System Policy > Data Lookup Definitions."
        ),
    )
    fetch_error: Optional[str] = Field(None)


def get_data_lookup_rules(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: DataLookupRulesParams,
) -> DataLookupRulesResult:
    """
    Query dl_definition for active Data Lookup rules that set fields on a table.

    Data Lookup rules execute server-side after every insert or update and can
    silently override written field values. This is a common cause of write
    mismatches on derived fields such as incident.priority (set by a lookup
    rule reading impact and urgency).

    Call this as part of diagnostic escalation when verify_fields returns a
    mismatch and get_field_metadata indicates the field is calculated.

    Also call this as the instance verification step for entries in
    FIELD_CONTROL_GRAPH.md that have mechanism='data_lookup'.

    Does not modify any records.

    Args:
        config: Server configuration.
        auth_manager: Authentication manager.
        params: Table and optional output field filter.

    Returns:
        DataLookupRulesResult listing active rules with name and output field.
    """
    url = f"{config.api_url}/table/dl_definition"

    query_parts = ["active=true", f"applies_to.name={params.table}"]
    if params.output_field:
        query_parts.append(f"field={params.output_field}")

    query_params = {
        "sysparm_query": "^".join(query_parts),
        "sysparm_fields": "sys_id,name,field,on_insert,on_update,active",
        "sysparm_display_value": "true",
        "sysparm_limit": 50,
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
            f"get_data_lookup_rules | fetch failed | table={params.table} | error={e}"
            + (f" | body={_body}" if _body else "")
        )
        return DataLookupRulesResult(
            table=params.table,
            output_field_filter=params.output_field,
            rules_found=False,
            fetch_error=f"dl_definition query failed: {str(e)}" + (f" | response: {_body}" if _body else ""),
        )

    raw_results = response.json().get("result", [])
    if not raw_results:
        logger.debug(
            f"get_data_lookup_rules | no rules found | table={params.table} "
            f"| output_field={params.output_field!r}"
        )
        return DataLookupRulesResult(
            table=params.table,
            output_field_filter=params.output_field,
            rules_found=False,
        )

    rules = []
    for row in raw_results:
        sys_id = _extract_field_value(row.get("sys_id", ""))
        name = _extract_field_value(row.get("name", ""), prefer_display=True)
        output_field = _extract_field_value(row.get("field", ""), prefer_display=True)
        on_insert = _parse_snow_bool(_extract_field_value(row.get("on_insert", "false")))
        on_update = _parse_snow_bool(_extract_field_value(row.get("on_update", "false")))
        active = _parse_snow_bool(_extract_field_value(row.get("active", "true")))
        rules.append(DataLookupRule(
            sys_id=sys_id,
            name=name,
            output_field=output_field,
            on_insert=on_insert,
            on_update=on_update,
            active=active,
        ))

    logger.info(
        f"get_data_lookup_rules | found {len(rules)} rules | table={params.table} "
        f"| output_field={params.output_field!r}"
    )

    return DataLookupRulesResult(
        table=params.table,
        output_field_filter=params.output_field,
        rules=rules,
        rules_found=True,
        note=(
            "The lookup matrix rows are stored in a related table and are not "
            "returned here. Locate the full matrix via "
            "System Policy > Data Lookup Definitions in the ServiceNow UI."
        ),
    )


# ---------------------------------------------------------------------------
# get_business_rules
# ---------------------------------------------------------------------------

class BusinessRulesParams(BaseModel):
    """Parameters for querying active Business Rules on a table."""

    table: str = Field(
        ...,
        description="ServiceNow table to inspect (e.g., 'incident').",
    )
    field: Optional[str] = Field(
        None,
        description=(
            "Field name to search for in Business Rule scripts (e.g., 'priority'). "
            "When provided, only rules whose script body contains this string are returned. "
            "When omitted, all active Business Rules for the table are returned. "
            "The search is a substring match — short or common field names may return false positives."
        ),
    )


class BusinessRule(BaseModel):
    """A single active Business Rule that references the target field."""

    name: str
    timing: str = Field(
        ...,
        description="Execution timing: 'before', 'after', 'async', or 'display'.",
    )
    action_insert: bool
    action_update: bool
    active: bool
    condition: str = Field(
        "",
        description="Condition expression. Empty means the rule runs unconditionally.",
    )
    script_preview: str = Field(
        ...,
        description=(
            "First 500 characters of the rule script. Check whether the rule "
            "sets the target field unconditionally or conditionally."
        ),
    )


class BusinessRulesResult(BaseModel):
    """Active Business Rules on a table, optionally filtered by field reference."""

    table: str
    field: Optional[str] = None
    rules: list[BusinessRule] = Field(default_factory=list)
    rules_found: bool
    search_note: str = Field(
        "",
        description=(
            "The search uses a substring match on the script body. A rule appearing "
            "here may READ the field rather than SET it. Review script_preview to "
            "determine whether the rule is the cause of the write override."
        ),
    )
    fetch_error: Optional[str] = Field(None)


def get_business_rules(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: BusinessRulesParams,
) -> BusinessRulesResult:
    """
    Query sys_script for active Business Rules on a table that reference a field.

    Business Rules with 'before' or 'after' timing can set or override field
    values as part of the same transaction as the API write. This makes them
    a common cause of write mismatches that survive verify_fields.

    The search uses a CONTAINS operator on the script body. Review the
    script_preview in each result to determine whether the rule is setting
    the field or merely reading it.

    Does not modify any records.

    Args:
        config: Server configuration.
        auth_manager: Authentication manager.
        params: Table and field to search for.

    Returns:
        BusinessRulesResult with matching rules and truncated script previews.
    """
    url = f"{config.api_url}/table/sys_script"

    snquery = f"collection={params.table}^active=true"
    if params.field:
        snquery += f"^scriptCONTAINS{params.field}"

    query_params = {
        "sysparm_query": snquery,
        "sysparm_fields": "name,when,action_insert,action_update,active,condition,script",
        "sysparm_limit": 50,
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
            f"get_business_rules | fetch failed | table={params.table} "
            f"| field={params.field or 'all'} | error={e}"
            + (f" | body={_body}" if _body else "")
        )
        return BusinessRulesResult(
            table=params.table,
            field=params.field,
            rules_found=False,
            fetch_error=f"sys_script query failed: {str(e)}" + (f" | response: {_body}" if _body else ""),
        )

    raw_results = response.json().get("result", [])
    if not raw_results:
        logger.debug(
            f"get_business_rules | no rules found | table={params.table} "
            f"| field={params.field or 'all'}"
        )
        return BusinessRulesResult(
            table=params.table,
            field=params.field,
            rules_found=False,
            search_note=(
                f"No active Business Rules on '{params.table}' with '{params.field}' "
                "in the script body were found."
            ),
        )

    rules = []
    for row in raw_results:
        name = str(row.get("name", ""))
        timing = str(row.get("when", ""))
        action_insert = _parse_snow_bool(str(row.get("action_insert", "false")))
        action_update = _parse_snow_bool(str(row.get("action_update", "false")))
        active = _parse_snow_bool(str(row.get("active", "true")))
        condition = str(row.get("condition", ""))
        script_full = str(row.get("script", ""))
        script_preview = script_full[:500] + ("..." if len(script_full) > 500 else "")
        rules.append(BusinessRule(
            name=name,
            timing=timing,
            action_insert=action_insert,
            action_update=action_update,
            active=active,
            condition=condition,
            script_preview=script_preview,
        ))

    logger.info(
        f"get_business_rules | found {len(rules)} rules | table={params.table} "
        f"| field={params.field or 'all'}"
    )

    return BusinessRulesResult(
        table=params.table,
        field=params.field,
        rules=rules,
        rules_found=True,
        search_note=(
            "Results use substring match on script body. A rule may appear here "
            "because it reads the field, not because it sets it. "
            "Review script_preview to confirm the rule's effect on the field."
        ),
    )


# ---------------------------------------------------------------------------
# get_data_policies
# ---------------------------------------------------------------------------

class DataPoliciesParams(BaseModel):
    """Parameters for querying active Data Policies for a table and field."""

    table: str = Field(
        ...,
        description="ServiceNow table to inspect (e.g., 'incident').",
    )
    field: str = Field(
        ...,
        description="Field name to check for active data policy constraints.",
    )


class DataPolicyRule(BaseModel):
    """A single field-level rule from an active Data Policy (sys_data_policy2)."""

    policy_name: str = Field(
        ...,
        description="Name of the parent sys_data_policy2 record.",
    )
    field: str = Field(
        ...,
        description="Field name this rule applies to.",
    )
    mandatory: bool = Field(
        ...,
        description="True if this policy enforces the field as mandatory.",
    )
    read_only: bool = Field(
        ...,
        description=(
            "True if this policy enforces the field as read-only. "
            "A read_only=True data policy rule discards API writes silently — "
            "this is a server-side enforcement that cannot be bypassed via the API."
        ),
    )


class DataPoliciesResult(BaseModel):
    """Active Data Policy rules affecting a field from sys_data_policy2."""

    table: str
    field: str
    rules: list[DataPolicyRule] = Field(default_factory=list)
    rules_found: bool
    fetch_error: Optional[str] = Field(None)


def get_data_policies(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: DataPoliciesParams,
) -> DataPoliciesResult:
    """
    Query sys_data_policy_rule for active Data Policy constraints on a field.

    Data Policies (sys_data_policy2) enforce field constraints server-side.
    A read_only=True rule on a field causes the platform to discard any write
    to that field, including writes via the REST API. Unlike UI Policies, Data
    Policies are NOT client-side — they apply regardless of how the data is
    submitted.

    Does not modify any records.

    Args:
        config: Server configuration.
        auth_manager: Authentication manager.
        params: Table and field to check.

    Returns:
        DataPoliciesResult with any active read_only or mandatory constraints.
    """
    url = f"{config.api_url}/table/sys_data_policy_rule"

    query_params = {
        "sysparm_query": (
            f"policy.applies_to.name={params.table}"
            f"^policy.active=true"
        ),
        "sysparm_fields": "policy.name,field,mandatory,read_only",
        "sysparm_display_value": "true",
        "sysparm_limit": 200,
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
            f"get_data_policies | fetch failed | table={params.table} "
            f"| field={params.field} | error={e}"
            + (f" | body={_body}" if _body else "")
        )
        return DataPoliciesResult(
            table=params.table,
            field=params.field,
            rules_found=False,
            fetch_error=f"sys_data_policy_rule query failed: {str(e)}" + (f" | response: {_body}" if _body else ""),
        )

    raw_results = response.json().get("result", [])

    # Filter client-side: match on the field display value
    matching_rules = []
    for row in raw_results:
        row_field = _extract_field_value(row.get("field", ""), prefer_display=True)
        if row_field.lower() != params.field.lower():
            continue

        policy_name = _extract_field_value(
            row.get("policy.name", row.get("policy", {}).get("display_value", "")),
            prefer_display=True,
        )
        mandatory = _parse_snow_bool(
            _extract_field_value(row.get("mandatory", "false"))
        )
        read_only = _parse_snow_bool(
            _extract_field_value(row.get("read_only", "false"))
        )

        matching_rules.append(DataPolicyRule(
            policy_name=policy_name,
            field=row_field,
            mandatory=mandatory,
            read_only=read_only,
        ))

        if read_only:
            logger.warning(
                f"get_data_policies | read_only constraint found "
                f"| table={params.table} | field={params.field} "
                f"| policy={policy_name}"
            )

    if not matching_rules:
        logger.debug(
            f"get_data_policies | no constraints | table={params.table} "
            f"| field={params.field}"
        )
        return DataPoliciesResult(
            table=params.table,
            field=params.field,
            rules_found=False,
        )

    logger.info(
        f"get_data_policies | found {len(matching_rules)} rules "
        f"| table={params.table} | field={params.field}"
    )

    return DataPoliciesResult(
        table=params.table,
        field=params.field,
        rules=matching_rules,
        rules_found=True,
    )


# ---------------------------------------------------------------------------
# get_ui_policies
# ---------------------------------------------------------------------------

class UIPoliciesParams(BaseModel):
    """Parameters for querying active UI Policies for a table and field."""

    table: str = Field(
        ...,
        description="ServiceNow table to inspect (e.g., 'incident').",
    )
    field: str = Field(
        ...,
        description="Field name to check for UI Policy actions.",
    )


class UIPolicyAction(BaseModel):
    """A single field-level action from an active UI Policy (sys_ui_policy)."""

    policy_name: str = Field(
        ...,
        description="Name of the parent sys_ui_policy record.",
    )
    field: str = Field(
        ...,
        description="Field name this action applies to.",
    )
    visible: str = Field(
        "",
        description="'true' = shown, 'false' = hidden, '' = no change.",
    )
    mandatory: str = Field(
        "",
        description="'true' = mandatory, 'false' = not mandatory, '' = no change.",
    )
    read_only: str = Field(
        "",
        description="'true' = read-only in UI, 'false' = editable in UI, '' = no change.",
    )


class UIPoliciesResult(BaseModel):
    """Active UI Policy actions affecting a field from sys_ui_policy."""

    table: str
    field: str
    actions: list[UIPolicyAction] = Field(default_factory=list)
    actions_found: bool
    api_relevant: bool = Field(
        False,
        description=(
            "Always False. UI Policies are enforced client-side in the browser "
            "form only. They do NOT affect REST API writes. A field that is "
            "read-only via a UI Policy is still writable via the Table API. "
            "Never cite a UI Policy as the cause of a REST API write failure."
        ),
    )
    fetch_error: Optional[str] = Field(None)


def get_ui_policies(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: UIPoliciesParams,
) -> UIPoliciesResult:
    """
    Query sys_ui_policy_action for active UI Policy constraints on a field.

    UI Policies are enforced exclusively in the browser form. They have NO
    effect on REST API writes. This tool is called as the final step in
    diagnostic escalation to confirm (or rule out) UI policy involvement,
    and to provide supplemental context about why a field appears read-only
    in the form even if the API write would succeed.

    Do NOT report a UI Policy finding as the cause of an API write mismatch.
    If this tool finds a UI policy but no server-side rule was found in the
    earlier escalation steps, continue searching — the true cause is elsewhere.

    Does not modify any records.

    Args:
        config: Server configuration.
        auth_manager: Authentication manager.
        params: Table and field to check.

    Returns:
        UIPoliciesResult with api_relevant always False.
    """
    url = f"{config.api_url}/table/sys_ui_policy_action"

    query_params = {
        "sysparm_query": (
            f"ui_policy.applies_to.name={params.table}"
            f"^ui_policy.active=true"
        ),
        "sysparm_fields": "ui_policy.name,field,visible,mandatory,read_only",
        "sysparm_display_value": "true",
        "sysparm_limit": 200,
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
            f"get_ui_policies | fetch failed | table={params.table} "
            f"| field={params.field} | error={e}"
            + (f" | body={_body}" if _body else "")
        )
        return UIPoliciesResult(
            table=params.table,
            field=params.field,
            actions_found=False,
            fetch_error=f"sys_ui_policy_action query failed: {str(e)}" + (f" | response: {_body}" if _body else ""),
        )

    raw_results = response.json().get("result", [])

    # Filter client-side: match on the field display value
    matching_actions = []
    for row in raw_results:
        row_field = _extract_field_value(row.get("field", ""), prefer_display=True)
        if row_field.lower() != params.field.lower():
            continue

        policy_name = _extract_field_value(
            row.get("ui_policy.name", row.get("ui_policy", {}).get("display_value", "")),
            prefer_display=True,
        )
        visible = _extract_field_value(row.get("visible", ""), prefer_display=True)
        mandatory = _extract_field_value(row.get("mandatory", ""), prefer_display=True)
        read_only = _extract_field_value(row.get("read_only", ""), prefer_display=True)

        matching_actions.append(UIPolicyAction(
            policy_name=policy_name,
            field=row_field,
            visible=visible,
            mandatory=mandatory,
            read_only=read_only,
        ))

    if not matching_actions:
        logger.debug(
            f"get_ui_policies | no actions found | table={params.table} "
            f"| field={params.field}"
        )
        return UIPoliciesResult(
            table=params.table,
            field=params.field,
            actions_found=False,
        )

    logger.info(
        f"get_ui_policies | found {len(matching_actions)} actions "
        f"| table={params.table} | field={params.field} "
        f"| note=client-side only, not relevant to API writes"
    )

    return UIPoliciesResult(
        table=params.table,
        field=params.field,
        actions=matching_actions,
        actions_found=True,
    )
