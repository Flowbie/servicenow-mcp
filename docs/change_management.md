# Change management (compound approval + Table API)

Change workflows use a **small set of compound MCP tools** for approval actions, plus the **generic Table API** for `change_request` and related task rows.

## Compound tools (registered)

These are implemented in `change_tools` and registered in `tool_utils.py`:

1. **`submit_change_for_approval`** – submit a change for approval (`change_id`, optional comments).  
2. **`approve_change`** – approve (`change_id`, optional approver and comments).  
3. **`reject_change`** – reject (`change_id`, `rejection_reason`, optional approver).

Parameters use **change request identifiers** your instance accepts; resolve `CHG...` numbers to **`sys_id`** with **`query_records`** on `change_request` when needed.

## Everything else: Table API

There are **no** registered MCP tools named `create_change_request`, `update_change_request`, `list_change_requests`, `get_change_request_details`, or `add_change_task` in this fork. Instead:

| Goal | Approach |
|------|----------|
| Create change | `create_record` on `change_request` with required fields from your blueprint |
| Update fields / state | `update_record` |
| List / filter | `query_records` with encoded query |
| One row detail | `get_record` |
| Change tasks | `create_record` / `update_record` on `change_task` (or your instance’s task table) per blueprint |

Use **`get_field_metadata`**, **`list_table_fields`**, and **`verify_fields`** (when in package) around writes.

## Example natural language (Claude)

Same intents as before, but implementation is Table API + the three compound tools above — for example:

- "Create a normal change for server maintenance" → `create_record` on `change_request`.  
- "Submit CHG0012345 for approval" → resolve sys_id, then `submit_change_for_approval`.  
- "Approve the change with comment …" → `approve_change`.  
- "List emergency changes this week" → `query_records` on `change_request`.

## Programmatic note

Example scripts that import `create_change_request` from `change_tools` may be **out of date** relative to the current registration. Prefer calling the MCP tools (`create_record` / compound tools) or read `src/servicenow_mcp/utils/tool_utils.py` for the live list.

## Customization

Instance-specific states, choice values, and approval flows should be captured in your **architecture blueprint** and validated with **`query_records`** on `sys_choice` where needed.

## See also

- [README](../README.md)  
- [Incident management](incident_management.md) (same Table API pattern)  
