# Flow Designer in ServiceNow MCP

This document provides detailed information about the Flow Designer tools available in the ServiceNow MCP server.

## Overview

ServiceNow Flow Designer is a low-code automation engine that lets you build flows composed of triggers and actions. The Flow Designer tools in the ServiceNow MCP server allow you to:

- Discover available Flow Designer trigger types on your instance.
- Programmatically create Flow Designer flows (including triggers and, when configured, action instances) using the internal `processflow` API rather than the standard Table API.

These tools are intended for advanced automation scenarios where you want to generate flows from higher-level instructions. They should be used carefully and only in non-production environments unless you have strong governance in place.

## Available Tools

### 1. list_trigger_types

Lists all available Flow Designer trigger types from the `sys_hub_trigger_type` table.

**Tool Name:** `list_trigger_types`

**Parameters:**
- *(no required parameters)*

**Behavior:**
- Queries `sys_hub_trigger_type` and returns:
  - `trigger_types`: a list of objects with:
    - `sys_id`: sys_id of the trigger type (used as `trigger_definition_id` in `create_flow`).
    - `name`: display name (e.g. `"Created"`, `"Created or Updated"`).
    - `type_string`: internal type string (e.g. `"record_create"`, `"record_create_or_update"`, `"record_update"`, `"recurrence"`).
  - `message`: a summary string, e.g. `"Found N trigger type(s). Use sys_id as trigger_definition_id in create_flow."`

**Common Use Cases:**
- Discovering which trigger types are available on the instance before creating flows.
- Resolving trigger type sys_ids for `create_flow` when you want to specify `trigger_definition_id` explicitly.

### 2. create_flow

Creates a new Flow Designer flow using the internal `/api/now/processflow/` API. This is the only mechanism that can persist Flow Designer trigger instances and action instances (`sys_hub_flow_snapshot` is read-only via the Table API).

**Tool Name:** `create_flow`

**Parameters (CreateFlowParams):**

- `name` (string, required):  
  Flow name as it will appear in Flow Designer.

- `description` (string, optional):  
  Flow description.

- `scope` (string, optional, default: `"global"`):  
  Application scope. Use `"global"` for global scope or a scope sys_id.

- `run_as` (string, optional, default: `"user"`):  
  Execution context:
  - `"user"` — run as the triggering user.
  - `"system"` — run as system.

- `access` (string, optional, default: `"public"`):  
  Access level:
  - `"public"`
  - `"package_private"`
  - `"private"`

- `flow_priority` (string, optional, default: `"MEDIUM"`):  
  Flow priority: `"LOW"`, `"MEDIUM"`, or `"HIGH"`.

- `trigger` (TriggerInstanceParam, optional):  
  Trigger configuration for the flow. If omitted, the flow is created as a **subflow** (no trigger; callable from other flows or the REST API).

  **TriggerInstanceParam fields:**
  - `type` (string, required): Trigger type string. Common values:
    - `"record_create"`
    - `"record_create_or_update"`
    - `"record_update"`
    - `"recurrence"`
  - `trigger_definition_id` (string, optional): sys_id of the trigger type definition (`sys_hub_trigger_type`).  
    If omitted, `create_flow` resolves it automatically from `type` by querying `sys_hub_trigger_type`. Use `list_trigger_types` to inspect trigger types explicitly.
  - `name` (string, optional): Display name for the trigger (e.g. `"Created"`, `"Created or Updated"`). Defaults to the `type` value if omitted.
  - `table` (string, optional): Table name to trigger on (e.g. `"incident"`). Convenience field; maps to the `"table"` trigger input.
  - `condition` (string, optional): Encoded query condition (e.g. `"active=true"`). Convenience field; maps to the `"condition"` trigger input.
  - `inputs` (list of TriggerInputParam, optional): Full trigger inputs list. If provided, overrides `table` and `condition` and is used as-is.

- `actions` (list of ActionInstanceParam, optional):  
  Action steps to add to the flow. This requires instance-specific parameter definition sys_ids.

  **ActionInstanceParam fields (subset):**
  - `action_type_sys_id` (string, required):  
    sys_id of the action type definition (`sys_hub_action_type_definition`).  
    Example: Look Up Record, Create Record, etc. Discover via `/api/now/hub/actionpicker/...` or sys_hub_action_type tables.
  - `name` (string, required): Display name for this action step (e.g. `"Look Up Record"`).
  - `order` (int, required): Execution order (1-based).
  - `internal_name` (string, optional): Internal name of the action type (e.g. `"look_up_record"`). Used for display only.
  - `parent_action_type_id` (string, optional): Parent action type sys_id. If unknown, the platform can usually resolve it.
  - `inputs` (list of ActionInputParam, required for non-trivial actions):  
    Each `ActionInputParam` includes:
    - `id` (string): Parameter definition sys_id (`sys_hub_action_type_base_element.sys_id`). **Must match** the instance’s configuration.
    - `name` (string): Parameter name (e.g. `"table"`, `"conditions"`).
    - `value` (string): Parameter value (string; boolean and numeric values are represented as strings, e.g. `"1"`, `"0"`).

**Flow Creation Sequence (internal):**

`create_flow` performs the following steps via the `processflow` API:

1. **Create flow shell**  
   `POST /api/now/processflow/flow`  
   Creates a draft flow shell with the provided name, scope, access, and description.

2. **Initial autosave**  
   `POST /api/now/processflow/versioning/create_version`  
   Creates an autosave version for the draft (non-fatal if it fails; shell still exists).

3. **Attach trigger and actions**  
   `PUT /api/now/processflow/flow`  
   Saves the trigger and action instances onto the flow using the shell payload as a base.

4. **Final autosave**  
   `POST /api/now/processflow/versioning/create_version`  
   Creates a final autosave version after trigger/actions are attached (non-fatal if it fails).

**Return (CreateFlowResponse):**

- `success` (bool): Whether the flow was created successfully.
- `message` (string): Human-readable result description (includes error context if any step failed).
- `flow_sys_id` (string, optional): sys_id of the created flow (`sys_hub_flow`).
- `flow_name` (string, optional): Flow name.
- `flow_internal_name` (string, optional): Auto-generated internal name of the flow.

## Usage Examples

> These examples show conceptual usage as MCP tools from an LLM environment. In raw Python, use the `flow_tools` functions with `ServerConfig`, `AuthManager`, and the appropriate params models.

### List all trigger types

```python
result = await mcp.use_tool("servicenow", "list_trigger_types", {})

for t in result["trigger_types"]:
    print(f"{t['sys_id']} | {t['name']} | {t.get('type_string')}")
```

### Create a simple record-create flow on incident

This example creates a Flow Designer flow that triggers when an incident is created. It uses the `type` field and lets `create_flow` resolve the trigger definition sys_id automatically.

```python
result = await mcp.use_tool("servicenow", "create_flow", {
    "name": "Demo Incident Create Flow",
    "description": "Flow created via ServiceNow MCP for incident record creation.",
    "scope": "global",
    "run_as": "user",
    "access": "public",
    "flow_priority": "MEDIUM",
    "trigger": {
        "type": "record_create",
        "table": "incident",
        "condition": "active=true"
    }
})

if result["success"]:
    print(f"Flow created: sys_id={result['flow_sys_id']}, name={result['flow_name']}")
else:
    print(f"Flow creation failed: {result['message']}")
```

### Discover trigger types, then create a flow with an explicit trigger_definition_id

```python
# First, list trigger types
triggers = await mcp.use_tool("servicenow", "list_trigger_types", {})

record_create = next(
    (t for t in triggers["trigger_types"] if t.get("type_string") == "record_create"),
    None,
)

if not record_create:
    raise RuntimeError("No record_create trigger type found. Check Flow Designer configuration.")

trigger_sys_id = record_create["sys_id"]

# Now create a flow using that trigger_definition_id
result = await mcp.use_tool("servicenow", "create_flow", {
    "name": "Incident Create Flow (explicit trigger sys_id)",
    "description": "Flow created with an explicit trigger_definition_id.",
    "trigger": {
        "type": "record_create",
        "trigger_definition_id": trigger_sys_id,
        "table": "incident"
    }
})
```

> **Note:** Configuring action instances (`actions`) requires instance-specific parameter definition sys_ids from `sys_hub_action_type_base_element`. For safety and portability, start with flows that only define triggers unless you have confirmed parameter IDs for your instance.

## Trigger Types

Common trigger type strings:

- `record_create` — Trigger when a record is created.
- `record_create_or_update` — Trigger on create or update.
- `record_update` — Trigger when a record is updated.
- `recurrence` — Time-based trigger according to a schedule.

Use `list_trigger_types` to see the full set of trigger types and their display names on your instance.

## Best Practices

1. **Use sub-prod first**  
   Always test Flow Designer creation in a non-production environment before enabling in production.

2. **Resolve trigger types explicitly**  
   Use `list_trigger_types` to inspect available trigger types and confirm which sys_ids and type strings exist on your instance.

3. **Start with trigger-only flows**  
   Before adding complex actions, create flows with just the trigger to verify that the `processflow` API calls succeed and the flow appears in Flow Designer.

4. **Be careful with action inputs**  
   Action inputs require exact parameter definition sys_ids. When in doubt, inspect an existing manually created flow on your instance and copy those IDs, or consult internal platform documentation.

5. **Document generated flows**  
   Record which flows were generated via MCP (e.g. in story-level documentation) and ensure they are tracked in your change management process.

## Troubleshooting

### Error: "Failed to fetch trigger types"

- Cause: Network or permission issue when calling `sys_hub_trigger_type` via `list_trigger_types`.
- Resolution: Verify credentials and that the user has access to `sys_hub_trigger_type`. Retry in sub-prod.

### Error: "No trigger type found with name='...'"

- Cause: The requested trigger type string could not be resolved to a display name in `sys_hub_trigger_type`.
- Resolution: Call `list_trigger_types` and choose one of the returned types; ensure you use a supported `type` string (`record_create`, `record_update`, etc.).

### Error: "Flow shell was created but the PUT to attach trigger/actions failed"

- Cause: The initial shell POST succeeded, but the PUT that attaches trigger and actions returned an error (e.g. invalid payload, missing parameter IDs).
- Resolution:
  - Inspect the `message` field from `create_flow` for details.
  - Verify trigger configuration (table, condition) and any action parameter IDs.
  - Consider re-running with a simpler configuration (trigger-only) first.

### Flows not visible in Flow Designer

- Cause: Flow created in a different scope or with access restrictions, or creation failed silently after shell creation.
- Resolution:
  - Confirm `scope` and `access` parameters.
  - Check the instance’s Flow Designer UI for drafts in the expected application scope.
  - If necessary, use instance-side debugging (e.g. `processflow` API calls) to inspect the underlying records.

## Additional Resources

- ServiceNow docs — Flow Designer overview and reference  
  (Search for *Flow Designer reference* and *API access for Flow Designer* in the official documentation for your release.)

