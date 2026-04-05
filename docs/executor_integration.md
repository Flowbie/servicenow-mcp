# Executor Agent Integration Contract

This document describes the MCP tool contract used by the `executor` agent in
`servicenow-claude-os`. It defines which tools the Executor calls, in what order,
and what guarantees each tool must provide.

## The Executor Pattern

The Executor agent (`servicenow-claude-os/agents/executor.md`) is the exclusive
consumer of MCP write tools. All ServiceNow writes from `servicenow-claude-os` flow
through the Executor, which runs the following sequence for every write operation:

```
1. list_tool_packages()          — confirm active package and tool availability
2. get_field_metadata(table, field) — pre-flight: check writability
3. get_field_choices(table, field)  — pre-flight: validate choice values (if choice type)
4. <write tool>(params)          — execute the write
5. verify_fields(table, record_id, expected) — post-write verification
6. [diagnostic escalation if verify_fields returns mismatched]
```

No step may be skipped. Steps 2 and 3 results are cached per field per session.

## Tool Guarantees Required

### list_tool_packages

- Must always be available regardless of active package (it is).
- Returns: current_package, current_package_tools, available_packages.
- The Executor checks this at the start of every session to confirm that
  verify_fields, get_field_metadata, and get_field_choices are in the active package.
  If missing, the Executor halts and reports the gap — it does not skip verification.

### get_field_metadata(table, field)

- Must return: read_only, calculated, field_found, fetch_error.
- A fetch_error does not abort the write — the Executor falls back to
  FIELD_CONTROL_GRAPH.md and runs verify_fields unconditionally after the write.
- read_only=true or calculated=true halts the write and triggers derived field handling.

### get_field_choices(table, field)

- Must return: choices_found, choices list with value/label pairs.
- If choices_found=false, the Executor retries with table='task' (ServiceNow inheritance).
- If no match found after retry: the Executor stops and reports valid choices to the user.

### verify_fields(table, record_id, expected)

- Must return: all_verified, mismatched (list), fetch_error.
- The Executor interprets results as follows:
  - all_verified=true: report success.
  - mismatched non-empty: do NOT report success. Enter Diagnostic Escalation.
  - fetch_error: report the fetch error. Do not assume success or failure.
- This tool must never be skipped after a write. HTTP 200 from a write tool is NOT
  sufficient confirmation of persistence.

### Diagnostic Escalation Tools

Used only when verify_fields returns mismatched. Called in this order:

1. get_data_policies(table, field)
2. get_data_lookup_rules(table, output_field=field)
3. get_business_rules(table, field)
4. get_ui_policies(table, field)

Each tool must return enough information to identify whether server-side logic is
overriding the written value. See SERVICENOW_MCP_RULES.md for escalation logic.

## Active Package Requirement

The Executor requires these tools to be in the active package:

**Always required (protocol tools):**
- verify_fields
- get_field_metadata
- get_field_choices
- get_data_lookup_rules
- get_business_rules
- get_data_policies
- get_ui_policies

**Required for blueprint-first workflow:**
- get_table_metadata
- list_table_fields
- list_table_relationships
- list_child_tables

**Required per task type (representative):**
- Scripting tasks: `create_record` / `update_record` on scripting tables (for example `sys_script_include`) per blueprint; optional `run_background_script` when justified
- Change management: `create_record` / `update_record` on `change_request` (and related rows); compound approval: `submit_change_for_approval`, `approve_change`, `reject_change`
- Incident management: `query_records` / `create_record` / `update_record` on `incident` (no incident-specific MCP tools)
- Update set / changeset session: `get_current_update_set`, `set_current_update_set`, `get_changeset_details`; listing or creating update sets: Table API on `sys_update_set`
- Flow tasks: `flow_tools` (for example `create_flow`, `clone_flow`, …) when included in the active package

The `executor` tool package in `config/tool_packages.yaml` provides the minimum
required set for scripting tasks. For other domains, use `platform_developer`
or `full`.

## Package Selection by Project Type

| Project Type | Recommended Package |
|---|---|
| NEW_FEATURE (scripting) | executor or platform_developer |
| NEW_FEATURE (Flow Designer) | platform_developer |
| BUG_FIX | executor or platform_developer |
| BULK_DATA | platform_developer (run_background_script) |
| INTEGRATION | platform_developer |
| UPGRADE | platform_developer |

## Error Handling Contract

The MCP server returns errors in the response body, not as HTTP error codes in all cases.
The Executor must:

1. Check the response for error indicators even when HTTP 200 is returned.
2. Never retry a failed write without diagnosing the cause first.
3. Surface all MCP errors to the user with: tool name, parameters sent, error received.
4. On verify_fields mismatch: never retry the same write. Diagnose, explain, confirm.
