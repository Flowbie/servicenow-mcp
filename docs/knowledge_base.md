# Knowledge base (Table API)

Knowledge operations use the **generic Table API** against ServiceNow KB tables. This fork does **not** register upstream-style tools such as `create_knowledge_base`, `list_articles`, or `publish_article`.

## Primary tables

| Purpose        | Table name           |
|----------------|----------------------|
| Knowledge base | `kb_knowledge_base`  |
| Category       | `kb_category`        |
| Article        | `kb_knowledge`       |

REST path shape: `/api/now/table/{table}` — surfaced by **`query_records`**, **`get_record`**, **`create_record`**, **`update_record`**, **`delete_record`**.

## Operations (conceptual)

### Knowledge base

- **List / search:** `query_records` on `kb_knowledge_base` with `sysparm_query` as needed.  
- **Create:** `create_record` with fields such as `title`, `description`, owner references — **per your blueprint**.  
- **Update:** `update_record` with `sys_id` and changed fields.

### Categories

- **Create:** `create_record` on `kb_category` with `kb_knowledge_base` reference and optional `parent_category`.  
- **List:** `query_records` filtering on base and parent.

### Articles

- **Create:** `create_record` on `kb_knowledge` with `short_description`, body/text fields, category, and base references as required by your instance.  
- **Update:** `update_record` for content or metadata.  
- **Publish / workflow state:** set the appropriate workflow or state fields your instance uses (often choice or workflow-driven); use **`get_field_metadata`** and **`list_table_fields`** to avoid writing read-only columns.

### List and filter articles

Use **`query_records`** on `kb_knowledge` with encoded queries (for example by `kb_category`, `workflow_state`, or text search fields your blueprint documents).

## Error handling

Table API responses are returned by the MCP tools as structured results. On failure, check the tool output for HTTP or ServiceNow error messages, missing mandatory fields, or governance blocks.

## See also

- [README](../README.md) – tooling model  
- [ServiceNow Knowledge Management](https://docs.servicenow.com/) – product documentation for your release  
