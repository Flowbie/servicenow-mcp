# Flow Designer in ServiceNow MCP

This document provides detailed information about the Flow Designer tools available in the ServiceNow MCP server.

## Overview

ServiceNow Flow Designer is a low-code automation engine that lets you build flows composed of triggers and actions. The Flow Designer tools in the ServiceNow MCP server allow you to:

- Discover available Flow Designer trigger types on your instance.
- Programmatically create Flow Designer flows (including triggers and, when configured, action instances) using the internal `processflow` API rather than the standard Table API.

These tools are intended for advanced automation scenarios where you want to generate flows from higher-level instructions. They should be used carefully and only in non-production environments unless you have strong governance in place.

## Available Tools

### 1. list_trigger_types

Lists all available Flow Designer trigger types from the `sys_hub_trigger_definition` table.

**Tool Name:** `list_trigger_types`

**Parameters:**
- *(no required parameters)*

**Behavior:**
- Queries `sys_hub_trigger_definition` (the authoritative registry of trigger types) and returns:
  - `trigger_types`: a list of objects with:
    - `sys_id`: sys_id of the trigger definition (used as `trigger_definition_id` in `create_flow`).
    - `name`: display name (e.g. `"Created"`, `"Created or Updated"`).
    - `type_string`: internal type string (e.g. `"record_create"`, `"record_create_or_update"`, `"record_update"`, `"recurrence"`).
  - `message`: a summary string, e.g. `"Found N trigger type(s). Use sys_id as trigger_definition_id in create_flow."`

> **Important:** Do NOT use `sys_hub_trigger_type` to resolve trigger definition sys_ids. That table
> has only 4 rows (Created, Created or Updated, Updated, Recurrence) and its sys_ids are different
> from those in `sys_hub_trigger_definition`. `list_trigger_types` and the internal
> `_resolve_trigger_definition_id` function both query `sys_hub_trigger_definition` by the `type`
> field. There are 15 active trigger definitions covering record, schedule, service catalog, email,
> SLA, and other trigger categories.

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
  - `trigger_definition_id` (string, optional): sys_id of the trigger type definition (`sys_hub_trigger_definition`).
    If omitted, `create_flow` resolves it automatically from `type` by querying `sys_hub_trigger_definition`. Use `list_trigger_types` to inspect trigger types and their sys_ids.
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

`create_flow` performs the following 6 steps via the `processflow` API and supporting endpoints:

1. **Create flow shell**
   `POST /api/now/processflow/flow`
   Creates a draft flow shell with the provided name, scope, access, and description.
   Returns `result.data.id` (flow_sys_id) and `result.data.internalName`.

2. **Initial autosave**
   `POST /api/now/processflow/versioning/create_version` with `type: "Autosave"`
   Creates an autosave version immediately after the shell. Required before the PUT.
   Non-fatal if it fails — shell still exists.

3. **Attach trigger and actions (PUT)**
   `PUT /api/now/processflow/flow`
   Saves trigger instances and action instances onto the flow. The full flow payload
   (from Step 1's response) is the PUT body, augmented with `triggerInstances` and
   `actionInstances`. The flow `id` is in the body, not the URL path.

4. **Save version**
   `POST /api/now/processflow/versioning/create_version` with `type: "Save"`
   Creates the final Save version after trigger/actions are attached. Both Autosave
   (Step 2) and Save (Step 4) are required — Save without a prior Autosave can leave
   the flow in an inconsistent state in the UI.

5. **Release edit lock (GraphQL)**
   `POST /api/now/graphql` with the `safeEdit` mutation (`delete: flow_sys_id`)
   Releases the edit lock that the processflow API sets during creation. Without this,
   the flow appears read-only (locked) in the Flow Designer UI immediately after creation.

6. **Patch fTriggerType (Table API, non-fatal)**
   `PATCH /api/now/table/sys_hub_flow_version/{version_sys_id}`
   Sets `fTriggerType` in the version payload to `"Record"` (or the appropriate category).
   The version is identified by querying `sys_hub_flow_version` filtered to
   `flow={flow_sys_id}^type=Save`. Non-fatal if it fails — the flow functions correctly
   but Advanced Options may render incorrectly in the Flow Designer UI.

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
# First, list trigger types (queries sys_hub_trigger_definition)
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

> **Note:** Configuring action instances (`actions`) requires instance-specific parameter definition sys_ids from `sys_hub_action_type_base_element`. For safety and portability, start with flows that only define triggers unless you have confirmed parameter IDs for your instance. See the **Trigger Input Reference** and **Action Reference** sections below for confirmed values.

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

## Trigger Input Reference

Record-trigger flows require all 8 trigger inputs to be present in the `triggerInstances`
payload. Missing inputs cause a `renderInput` TypeError in the Flow Designer UI even though
the flow functions correctly. Each input's `parameter.id` must match the `sys_id` from
`sys_hub_trigger_input` on the instance.

### record_create trigger inputs

| parameter.id | name | label | internalType | mandatory | order |
|---|---|---|---|---|---|
| `cfca92e0c31322002841b63b12d3ae00` | `table` | Table | `table_name` | true | 1 |
| `66aadea0c31322002841b63b12d3aebf` | `condition` | Condition | `conditions` | false | 100 |
| `11ffbef2072200103bf10705afd300c2` | `run_on_extended` | Run On Extended Tables | `choice` | false | 100 |
| `3f1b9e4e0f103300b599bca2ff767e21` | `run_flow_in` | Run flow In | `choice` | false | 100 |
| `f89c5177c7002300f4eba1425a976385` | `run_when_user_list` | Run When User List | `glide_list` | false | 100 |
| `1e4859f3c7002300f4eba1425a9763f9` | `run_when_setting` | Run When Session Setting | `choice` | false | 100 |
| `ed7a5537c7002300f4eba1425a976391` | `run_when_user_setting` | Run When User Setting | `choice` | false | 100 |
| `2b9def50c31132002841b63b12d3ae5b` | `trigger_strategy` | Run Trigger | `choice` | false | 200 |

`trigger_strategy` (order=200) must be the last input in the list.

### Choice values for record_create inputs

| input name | value | label |
|---|---|---|
| `run_on_extended` | `false` | Run only on current table |
| `run_on_extended` | `true` | Run on current and extended tables |
| `run_flow_in` | `background` | Run flow in background (default) |
| `run_flow_in` | `foreground` | Run flow in foreground |
| `run_when_setting` | `non_interactive` | Only Run for Non-Interactive Session |
| `run_when_setting` | `interactive` | Only Run for User Interactive Session |
| `run_when_setting` | `both` | Run for Both Interactive and Non-Interactive Sessions |
| `run_when_user_setting` | `not_one_of` | Do not run if triggered by the following users |
| `run_when_user_setting` | `one_of` | Only Run if triggered by the following users |
| `run_when_user_setting` | `any` | Run for any user |
| `trigger_strategy` | `once` | Once |
| `trigger_strategy` | `unique_changes` | For each unique change |
| `trigger_strategy` | `always` | Only if not currently running |
| `trigger_strategy` | `every` | For every update |

> These parameter.id values were confirmed on instance dev296536. Use
> `addQuery('name', 'CONTAINS', triggerDefSysId)` on `sys_hub_trigger_input` to verify
> or retrieve the IDs for `record_create_or_update` and `record_update` on other instances.

---

## Action Reference

Action inputs require parameter definition sys_ids from `sys_hub_action_type_base_element`.
The values below were confirmed on instance dev296536. Verify on other instances before use.

### Look Up Record

- `action_type_sys_id`: `9d09f99587003300663ca1bb36cb0ba3`
- `parent_action_type_id`: `b93f42810b30030085c083eb37673a63`

| input name | parameter.id | internalType | default |
|---|---|---|---|
| `table` | `d909f99587003300663ca1bb36cb0ba4` | `table_name` | — |
| `conditions` | `d509f99587003300663ca1bb36cb0ba9` | `conditions` | — |
| `sort_column` | `1d09f99587003300663ca1bb36cb0bad` | `field_name` | — |
| `sort_type` | `5d09f99587003300663ca1bb36cb0bb1` | `choice` | `sort_asc` |
| `if_multiple_records_are_found_action` | `1909f99587003300663ca1bb36cb0bb9` | `choice` | `use_first_record` |
| `__snc_dont_fail_on_error` | `ceab42a673110010d70877186bf6a74f` | `boolean` | `0` |

Outputs: `record` (document_id), `Table` (table_name), `status` (0=Success/1=Error), `error_message` (string).

### Create Record

- `action_type_sys_id`: `02f0b88cc3c632002841b63b12d3aeff`

---

## Troubleshooting

### Error: "Failed to fetch trigger types"

- Cause: Network or permission issue when calling `sys_hub_trigger_definition` via `list_trigger_types`.
- Resolution: Verify credentials and that the user has read access to `sys_hub_trigger_definition`. Retry in sub-prod.

### Error: "No trigger type found with name='...'"

- Cause: The requested trigger type string could not be resolved in `sys_hub_trigger_definition`.
- Resolution: Call `list_trigger_types` and choose one of the returned types; ensure you use a supported `type` string (`record_create`, `record_update`, etc.).

### Error: "Flow shell was created but the PUT to attach trigger/actions failed"

- Cause: The initial shell POST succeeded, but the PUT that attaches trigger and actions returned an error (e.g. invalid payload, missing parameter IDs).
- Resolution:
  - Inspect the `message` field from `create_flow` for details.
  - Verify trigger configuration (table, condition) and any action parameter IDs.
  - Consider re-running with a simpler configuration (trigger-only) first.

### Flow appears read-only (locked) immediately after creation

- Cause: The `processflow` API sets an edit lock during creation. Step 5 of the create sequence (the `safeEdit` GraphQL mutation) releases it. If Step 5 fails or is skipped, the flow is left in a locked state.
- Resolution: The lock is stored in `sys_hub_trigger_safe_edit`. It can be cleared manually by deleting the lock record for the flow’s sys_id, or by running the `safeEdit delete` GraphQL mutation:
  ```json
  {
    "operationName": "safeEdit",
    "query": "mutation safeEdit($safeEditInput: SafeEditInput!) { snFlowDesigner { safeEdit(safeEditInput: $safeEditInput) } }",
    "variables": { "safeEditInput": { "delete": "<flow_sys_id>" } }
  }
  ```
  Post this to `/api/now/graphql` with admin credentials.

### Flow Designer shows "renderInput" TypeError on an otherwise functional flow

- Cause: One or more trigger inputs are missing from the trigger instance payload. All 8 inputs for record-based triggers must be present (see **Trigger Input Reference** above). If any are absent, the Flow Designer UI fails to render the trigger configuration panel.
- Resolution: The flow executes correctly despite the UI error. To fix the display, re-save the flow via the processflow PUT with all 8 inputs populated. The `parameter.id` values must match those in `sys_hub_trigger_input` for the trigger definition.

### Flows not visible in Flow Designer

- Cause: Flow created in a different scope or with access restrictions, or creation failed silently after shell creation.
- Resolution:
  - Confirm `scope` and `access` parameters.
  - Check the instance’s Flow Designer UI for drafts in the expected application scope.
  - If necessary, use instance-side debugging (e.g. `processflow` API calls) to inspect the underlying records.

## Additional Resources

- ServiceNow docs — Flow Designer overview and reference  
  (Search for *Flow Designer reference* and *API access for Flow Designer* in the official documentation for your release.)

