# Legacy Workflow engine (Table API)

This document covers the **classic Workflow** engine (`wf_*` tables), not **Flow Designer**. For Flow Designer authoring and test execution, use **`flow_tools`** and [flow_designer.md](flow_designer.md).

## No dedicated workflow MCP tools

This fork does **not** expose tools such as `list_workflows`, `create_workflow`, or `add_workflow_activity`. Inspecting or editing legacy workflow definitions is done with the **generic Table API** (and **`run_background_script`** only when you have a justified compound need).

## Tables you will touch (examples)

Exact names depend on your instance and version; confirm with **`list_table_relationships`** / **`query_records`** on `sys_db_object`:

- `wf_workflow` – workflow definitions  
- `wf_workflow_version` – versions  
- Activity and transition rows live in related `wf_*` tables — map them in your architecture blueprint before bulk edits.

## Read patterns

- **List workflows:** `query_records` on `wf_workflow` with filters (`active=true`, name contains, etc.).  
- **Versions for a workflow:** `query_records` on `wf_workflow_version` with `workflow` = parent `sys_id`.  
- **Activities:** `query_records` on the appropriate `wf_*` activity table keyed by workflow version, per blueprint.

## Write patterns

Prefer **update sets**, sub-production instances, and **`verify_fields`** after writes. Use **`create_record`** / **`update_record`** only with explicit field maps from a validated blueprint; legacy workflow graphs are easy to corrupt with partial updates.

## Flow Designer vs legacy Workflow

| Area            | Use |
|-----------------|-----|
| New automation  | `flow_tools` + [flow_designer.md](flow_designer.md) |
| Legacy `wf_*`   | Table API + blueprint |

## References

- [ServiceNow Workflow administration](https://docs.servicenow.com/) (release-specific)  
- [README](../README.md)  
