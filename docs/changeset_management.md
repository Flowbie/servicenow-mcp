# Update sets and changesets (session tools + Table API)

In ServiceNow, **update sets** are stored on **`sys_update_set`**; captured rows appear in tables such as **`sys_update_xml`**. This fork does **not** provide MCP wrappers like `list_changesets`, `create_changeset`, or `commit_changeset` — those operations use the **Table API** unless the platform requires a different path documented in your blueprint.

## Named MCP tools (update-set session)

When included in your `MCP_TOOL_PACKAGE`, these tools help with **session** context:

- **`get_current_update_set`** – which update set is active for the session user.  
- **`set_current_update_set`** – set the active update set (by `sys_id` or identifier the tool accepts).  
- **`get_current_scope`** / **`set_current_scope`** – application scope session where applicable.  
- **`get_changeset_details`** – inspect captured changes for a given update set (implementation wraps the relevant table/API).

Resolve update set **names** to **`sys_id`** with **`query_records`** on `sys_update_set` when needed.

## Table API patterns

### List update sets

`query_records` on `sys_update_set` with encoded query, for example:

- By state (`state=in progress` or your instance’s values)  
- By user (`sys_created_by=...`)  
- By name  

### Create or rename an update set

`create_record` or `update_record` on `sys_update_set` with fields your instance requires (name, application scope, etc.).

### Inspect captured XML / rows

- **`get_changeset_details`** when available.  
- Or **`query_records`** on `sys_update_xml` (or related tables) filtered by update set reference — align with blueprint.

### Complete or publish

State transitions and deployment to other instances are **process-specific** (preview, commit, retrieve, merge). Use Table API only where your governance allows; many teams use UI or guided migration tools for promotion.

## Best practices

1. Keep one logical feature per update set.  
2. Name update sets so they are searchable (`query_records`).  
3. Always confirm **current** update set before configuration writes (`get_current_update_set`).  
4. Prefer sub-production for experiments.

## Troubleshooting

- **Wrong update set active:** `get_current_update_set` then `set_current_update_set` to correct.  
- **Empty details:** confirm `sys_id`, permissions, and that captures exist in `sys_update_xml`.  
- **Write blocked:** see governance / mandatory-field messages from `create_record` / `update_record`.

## See also

- [README](../README.md)  
- [Table introspection](table_introspection.md)  
