# Incident management (Table API)

This fork does **not** expose incident-specific MCP tools (for example `create_incident` or `update_incident`). Incidents are rows on the **`incident`** table (which extends **`task`**). Use the generic Table API tools and your instance blueprint for field names, mandatory columns, and state values.

## Tools to use

- **`query_records`** – list and filter incidents (encoded query, limit, fields).
- **`get_record`** – fetch one row by `sys_id` from `incident` (or related table).
- **`create_record`** – create an incident; supply required task/incident fields per blueprint.
- **`update_record`** – update state, assignment, work notes, etc.
- **`delete_record`** – only when appropriate and allowed by policy (rare for production incidents).

Supporting protocol tools (when in your package): **`get_field_metadata`**, **`verify_fields`**, **`list_table_fields`**.

## Typical flows

### Resolve display number to sys_id

Use **`query_records`** on `incident` with something like `number=INC0010001`, then use the returned `sys_id` for **`get_record`** or **`update_record`**.

### Create an incident

Call **`create_record`** with `table="incident"` and a fields map. Common fields include `short_description`, `caller_id`, `category`, `subcategory`, `impact`, `urgency`, `priority`, `assignment_group`, `assigned_to` — **confirm on your instance** via dictionary or blueprint.

### Add work notes or comments

Usually **`update_record`** on `incident` with `work_notes` (append semantics depend on instance business rules) or journal fields as defined in your blueprint.

### Resolve or close

**`update_record`** with the correct `state`, `close_notes`, `close_code`, etc., per your instance’s choice list and workflow.

## State and priority reference

Numeric state values are common in many instances (verify with **`query_records`** on `sys_choice` or your blueprint):

**State (typical):**

- `1` New  
- `2` In Progress  
- `3` On Hold  
- `4` Resolved  
- `5` Closed  
- `6` Canceled  

**Priority (typical):**

- `1` Critical through `5` Planning  

## Related documentation

- [Table introspection](table_introspection.md) for field and relationship discovery  
- Root [README](../README.md) for the full tooling model (no thin wrappers)  
