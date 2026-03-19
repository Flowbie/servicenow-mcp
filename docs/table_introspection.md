# Table and Field Introspection in ServiceNow MCP

This document describes the table and field introspection tools provided by the ServiceNow MCP server for discovering schema metadata directly from your instance.

## Overview

The introspection tools expose read-only views of ServiceNow table metadata and data dictionary information via the `sys_db_object` and `sys_dictionary` tables. They are primarily intended for:

- Building **architecture blueprints** for modules (tables, hierarchy, fields, and relationships).
- Understanding how a table is structured before designing changes.
- Exploring relationships between tables via reference fields.

All tools are **read-only** and safe to use in production for discovery (but you should still prefer sub-prod when experimenting).

## Available Tools

### 1. get_table_metadata

Query `sys_db_object` for high-level metadata about a single table.

**Tool Name:** `get_table_metadata`

**Parameters (GetTableMetadataParams):**
- `table` (string, required):  
  ServiceNow table name (e.g. `"incident"`, `"change_request"`, `"task"`).

**Returns (GetTableMetadataResult):**
- `table` (string): The table name that was queried.
- `table_found` (bool): Whether a matching `sys_db_object` record was found.
- `label` (string): Human-readable table label (e.g. `"Incident"`).
- `extends` (string): Parent table name (value of `super_class`). Empty if the table does not extend another.
- `scope` (string): Application scope or scope label if available.
- `fetch_error` (string, optional): Error message if the query failed.

**Typical uses:**
- Confirm what a table extends (e.g. `incident` extends `task`).
- Build table hierarchy overviews for a module.

---

### 2. list_table_fields

Query `sys_dictionary` for all fields on a table.

**Tool Name:** `list_table_fields`

**Parameters (ListTableFieldsParams):**
- `table` (string, required):  
  ServiceNow table name (e.g. `"incident"`, `"task"`).
- `include_system` (bool, optional, default: `false`):  
  - `false` — include only business and custom fields (exclude fields starting with `sys_`).  
  - `true` — include system/internal fields as well.

**Returns (ListTableFieldsResult):**
- `table` (string): Table that was queried.
- `fields` (list of TableFieldInfo): Each entry includes:
  - `field` (string): Field/element name.
  - `internal_type` (string): Data type (e.g. `"string"`, `"integer"`, `"choice"`, `"reference"`).
  - `reference` (string): Target table name for reference fields; empty otherwise.
  - `read_only` (bool): Whether the field is marked read-only in `sys_dictionary`.
  - `calculated` (bool): Whether the field is calculated.
  - `mandatory` (bool): Whether the field is mandatory.
  - `default_value` (string): Default value if configured.
- `fetch_error` (string, optional): Error message if the query failed.

**Typical uses:**
- Generate a fields table for a module’s architecture blueprint.
- Identify reference fields and candidate relationship edges.
- Spot mandatory and calculated fields before making design changes.

---

### 3. list_table_relationships

Derive **outbound relationships** for a table from its reference fields in `sys_dictionary`.

**Tool Name:** `list_table_relationships`

**Parameters (ListTableRelationshipsParams):**
- `table` (string, required):  
  ServiceNow table name whose outbound relationships you want to inspect.

**Returns (ListTableRelationshipsResult):**
- `table` (string): Table that was queried.
- `relationships` (list of TableRelationship):
  - `from_table` (string): Table that owns the reference field.
  - `from_field` (string): Reference field name.
  - `to_table` (string): Target table name for the reference.
- `fetch_error` (string, optional): Error message if the underlying dictionary query failed.

**Typical uses:**
- Build relationship graphs (ER-style diagrams) for a module.
- See which tables a table references via standard reference fields.

---

### 4. list_child_tables

List all tables that **extend** (inherit from) a parent table via `sys_db_object.super_class`.

**Tool Name:** `list_child_tables`

**Parameters (ListChildTablesParams):**
- `parent_table` (string, required):  
  Parent table name (e.g. `"task"`, `"cmdb_ci"`).

**Returns (ListChildTablesResult):**
- `parent_table` (string): Parent table that was queried.
- `child_tables` (list of string): Names of tables whose `super_class` is the parent.
- `fetch_error` (string, optional): Error message if the query failed.

**Typical uses:**
- Discover all task-hierarchy tables (`incident`, `problem`, `change_request`, etc.).
- Inspect CMDB inheritance trees (e.g. under `cmdb_ci`).

---

## Usage Examples

> The examples below show conceptual usage via MCP. In Python, call the functions in `servicenow_mcp.tools.blueprint_tools` with `ServerConfig`, `AuthManager`, and the appropriate params models.

### Get table metadata for `incident`

```python
result = await mcp.use_tool("servicenow", "get_table_metadata", {
    "table": "incident"
})

if result["table_found"]:
    print(f"Table: {result['table']} (label={result['label']})")
    print(f"Extends: {result['extends'] or 'none'}")
    print(f"Scope: {result['scope'] or 'unknown'}")
else:
    print("Table not found or fetch_error:", result.get("fetch_error"))
```

### List non-system fields on `incident`

```python
result = await mcp.use_tool("servicenow", "list_table_fields", {
    "table": "incident",
    "include_system": False
})

for field in result["fields"]:
    print(
        f"{field['field']}: type={field['internal_type']}, "
        f"ref={field.get('reference') or '-'}, "
        f"read_only={field['read_only']}, calculated={field['calculated']}, "
        f"mandatory={field['mandatory']}"
    )
```

### List outbound relationships from `incident`

```python
result = await mcp.use_tool("servicenow", "list_table_relationships", {
    "table": "incident"
})

for rel in result["relationships"]:
    print(f"{rel['from_table']}.{rel['from_field']} -> {rel['to_table']}")
```

### List child tables of `task`

```python
result = await mcp.use_tool("servicenow", "list_child_tables", {
    "parent_table": "task"
})

print(f"Child tables of task ({len(result['child_tables'])}):")
for name in result["child_tables"]:
    print(f"- {name}")
```

---

## Best Practices

1. **Use for discovery, not enforcement**  
   These tools show the current state of `sys_db_object` and `sys_dictionary`. Treat them as discovery inputs for design or architecture, not as hard-coded schemas.

2. **Prefer non-production where possible**  
   While the tools are read-only, you will often do follow-up work (like design or refactors). Run those iterations in sub-prod before applying changes in production.

3. **Combine tools for a complete picture**  
   Use:
   - `get_table_metadata` for high-level table info and hierarchy.
   - `list_table_fields` for detailed field definitions.
   - `list_table_relationships` for outbound relationships.
   - `list_child_tables` to understand inheritance trees.

4. **Feed results into blueprints and diagrams**  
   The outputs are ideal inputs for:
   - Architecture blueprints (e.g. the Investigator Agent).
   - Diagram-generation agents (ER diagrams and relationship graphs).

---

## Troubleshooting

### fetch_error is set

- Cause: The underlying call to `sys_db_object` or `sys_dictionary` failed (permissions, network, or instance configuration).
- Resolution:
  - Confirm credentials and that the user has access to the relevant tables.
  - Check the instance logs for REST API errors.

### table_found is false (get_table_metadata)

- Cause: There is no `sys_db_object` record with the given `name`.
- Resolution:
  - Confirm the table name is correct.
  - For scoped tables, check the full name (e.g. `x_scope_app_table`).

### No relationships returned (list_table_relationships)

- Cause: The table has no reference fields or they are filtered out (e.g. only system fields).
- Resolution:
  - Confirm there are reference fields on the table.
  - If needed, call `list_table_fields` and manually inspect which fields are `internal_type == "reference"`.

---

## Related Documentation

- See [flow_designer.md](flow_designer.md) for creating flows once you have understood table structure.
- See your project’s architecture blueprint docs for how these tools feed the Investigator and Diagram agents.

