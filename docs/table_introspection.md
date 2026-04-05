# Table and Field Introspection in ServiceNow MCP

This document describes the table and field introspection tools provided by the ServiceNow MCP server for discovering schema metadata directly from your instance.

## Overview

The introspection tools expose read-only views of ServiceNow table metadata and data dictionary information via the `sys_db_object` and `sys_dictionary` tables. They are primarily intended for:

- Building **architecture blueprints** for modules (tables, hierarchy, fields, and relationships).
- Understanding how a table is structured before designing changes.
- Exploring relationships between tables via reference fields.

All tools are **read-only** and safe to use in production for discovery (but you should still prefer sub-prod when experimenting).

## Available tools

Dedicated blueprint helpers:

### 1. Table metadata via `query_records` (`sys_db_object`)

The **`get_table_metadata`** and **`list_child_tables`** MCP tools were removed. Use **`query_records`** on **`sys_db_object`** instead.

**Single table (label, super_class, scope):**

- Table: `sys_db_object`  
- Encoded query example: `name=incident` (use `sysparm_fields` to limit columns: `name,label,super_class,sys_scope` as needed).

**Typical uses:**

- Confirm what a table extends (e.g. `incident` extends `task` via `super_class` reference).  
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

### 4. Child tables via `query_records` (`sys_db_object.super_class`)

List tables that **extend** a parent by querying `sys_db_object` where **`super_class`** points at the parent table’s `sys_db_object` row.

**Approach:**

1. **`query_records`** on `sys_db_object` with `name=<parent_table>` to get the parent row’s **`sys_id`**.  
2. **`query_records`** on `sys_db_object` with `super_class=<that_sys_id>` (or your instance’s equivalent encoded query) to list direct child table names.

**Typical uses:**

- Discover task-hierarchy tables (`incident`, `problem`, `change_request`, etc.).  
- Inspect CMDB inheritance trees under `cmdb_ci`.

---

## Usage Examples

> The examples below show conceptual usage via MCP. In Python, call the functions in `servicenow_mcp.tools.blueprint_tools` with `ServerConfig`, `AuthManager`, and the appropriate params models.

### Get table metadata for `incident` (via `query_records`)

```python
result = await mcp.use_tool("servicenow", "query_records", {
    "table": "sys_db_object",
    "query": "name=incident",
    "limit": 1
})
# Inspect result["records"][0] for label, super_class, sys_scope, etc.
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

### List child tables of `task` (two-step `query_records`)

```python
parent = await mcp.use_tool("servicenow", "query_records", {
    "table": "sys_db_object",
    "query": "name=task",
    "limit": 1,
})
parent_id = parent["records"][0]["sys_id"]
children = await mcp.use_tool("servicenow", "query_records", {
    "table": "sys_db_object",
    "query": f"super_class={parent_id}",
    "limit": 500,
})
for row in children["records"]:
    print(row.get("name"))
```

---

## Best Practices

1. **Use for discovery, not enforcement**  
   These tools show the current state of `sys_db_object` and `sys_dictionary`. Treat them as discovery inputs for design or architecture, not as hard-coded schemas.

2. **Prefer non-production where possible**  
   While the tools are read-only, you will often do follow-up work (like design or refactors). Run those iterations in sub-prod before applying changes in production.

3. **Combine tools for a complete picture**  
   Use:
   - `query_records` on `sys_db_object` for high-level table info and hierarchy.
   - `list_table_fields` for detailed field definitions.
   - `list_table_relationships` for outbound relationships.
   - `query_records` on `sys_db_object` (via `super_class`) to understand inheritance trees.

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

### No row returned for a table name (`sys_db_object`)

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

