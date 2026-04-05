# Service Catalog (Table API + helpers)

Most catalog authoring and queries use the **generic Table API** against standard catalog tables. This fork does **not** register thin MCP tools such as `list_catalog_items` or `create_catalog_category` from older upstream examples.

## Named MCP tools (when in your package)

- **`move_catalog_items`** – bulk move catalog items to another category.  
- **`get_optimization_recommendations`** – catalog analysis / optimization suggestions.  
- **`get_ritm_variables`** – variables for a requested item (RITM) / related record per implementation.

Authoritative names: `src/servicenow_mcp/utils/tool_utils.py`.

## Tables (typical)

| Area | Table(s) (examples) |
|------|----------------------|
| Categories | `sc_category` |
| Catalog items | `sc_cat_item` |
| Variables / options | `item_option_new`, related variable tables |
| Client scripts | `catalog_script_client` |

Use **`query_records`**, **`get_record`**, **`create_record`**, **`update_record`** with your architecture blueprint for mandatory fields and references.

## Example intents

- List categories: `query_records` on `sc_category` with `active=true` and ordering as needed.  
- List items in a category: `query_records` on `sc_cat_item` with encoded query on the category reference field.  
- Item detail: `get_record` on `sc_cat_item` by `sys_id`.  
- Reorganize items: **`move_catalog_items`** with item sys_ids and target category.  
- Improve catalog quality: **`get_optimization_recommendations`**.

## Example scripts

`examples/catalog_integration_test.py` and `examples/claude_catalog_demo.py` may assume legacy Python helpers still exposed as MCP tools. Prefer **`tool_utils.py`** and the Table API when wiring new automation.

## See also

- [Catalog optimization plan](catalog_optimization_plan.md)  
- [Catalog variables](catalog_variables.md) if present for your version  
- [README](../README.md)  
