# Scripting Tools in ServiceNow MCP

This document describes the scripting tools provided by the ServiceNow MCP server for executing background scripts and managing Script Includes.

## Overview

The scripting tools enable powerful, low-level operations against a ServiceNow instance:

- **Background scripts**: Execute arbitrary server-side JavaScript via the same mechanism as the “Background Script” module (`sys.scripts.do`) or a scripted REST API endpoint.
- **Script Includes**: List, create, update, and delete Script Includes using the Table API.

These tools are powerful and can cause data loss or instance instability if misused. Always follow your organization’s governance, use sub-production environments for testing, and consider DRY_RUN patterns and change management approvals before running destructive scripts.

## Background Script Execution

### Prerequisites

`run_background_script` supports two execution paths. The path used depends on whether
`script_execution_api_resource_path` is set in your MCP server config.

#### Path A — UI session (`sys.scripts.do`)

The MCP server logs in via `/login.do` and submits the script to `/sys.scripts.do`.
**This path silently fails for service accounts** — if the account cannot complete
the browser login flow, the tool returns `success: true` with empty output and no
error. There is no warning that execution was skipped.

Use this path only for personal dev accounts with browser-based login. It is not
suitable for automated or service-account-based use.

#### Path B — Scripted REST API (required for service accounts)

The MCP server calls a Scripted REST endpoint on the instance that executes the script
server-side. This path works for service accounts with OAuth or Basic auth.

**One-time instance setup required:**

1. In ServiceNow, navigate to **Scripted REST APIs** → **New**.
2. Create an API named `mcp_script_runner` (or any name you choose).
3. Add a resource:
   - **HTTP Method:** POST
   - **Relative path:** `/execute` (or any path you choose — must match your config)
   - **Script:**
     ```javascript
     (function process(request, response) {
         var body = JSON.parse(request.body.dataString);
         var script = body.script || '';
         var runner = new GlideScriptRunner();
         runner.run(script);
         response.setContentType('application/json');
         response.setBody(JSON.stringify({ status: 'ok' }));
     })(request, response);
     ```
   - **Requires authentication:** Yes
   - **Required roles:** admin (or a custom role with `background_script_runner` rights)
4. Set `script_execution_api_resource_path` in your `.mcp.json` to the full resource path,
   e.g. `"/api/x_mcp/mcp_script_runner/execute"`.

**Output capture on Path B:**

- `gs.info()`, `gs.warn()`, `gs.error()` → captured in `syslog_entries` (always available)
- `gs.print()` → NOT captured on Path B. `direct_output` will be empty.
  Use `gs.info()` for all diagnostic output when using the Scripted REST path.

---

### Tool: run_background_script

Executes a JavaScript background script in the instance and returns both **direct output** (from `gs.print`, Path A only) and **syslog entries** (from `gs.info` / `gs.warn` / `gs.error`).

**Tool Name:** `run_background_script`

**Parameters (RunBackgroundScriptParams):**

- `script` (string, required):
  JavaScript server-side script to execute.
  - Use `gs.info()`, `gs.warn()`, `gs.error()` for output captured in `syslog_entries` (works on both paths).
  - Use `gs.print()` only if you are certain the UI session path (Path A) is active — output is empty on Path B.
  - The variable `__MFCP_RUN_ID` is injected at the top of every script; include it in log messages to tag log entries for this run, e.g.
    `gs.info('MyModule | value=' + result + ' | run_id=' + __MFCP_RUN_ID);`

- `scope` (string, optional, default: `"global"`):
  Transaction scope for script execution.

**Returns (RunBackgroundScriptResult):**

- `success` (bool): Whether the script was executed successfully according to the transport layer. Note: on Path A (UI session), this can be `true` even if execution was silently skipped due to login failure.
- `run_id` (string): Correlation ID for this run; also stored in the script as `__MFCP_RUN_ID`.
- `http_status` (int): HTTP status code from the underlying request.
- `direct_output` (string): Text output captured from `gs.print()` calls. Only populated on Path A (UI session). Empty on Path B (Scripted REST).
- `syslog_entries` (list of SyslogEntry): Each entry includes:
  - `level` (string): Log level (e.g. `INFO`, `WARN`, `ERROR`).
  - `source` (string, optional): Source of the log entry.
  - `message` (string): Log message.
  - `created_on` (string): Timestamp (UTC).
- `message` (string): Human-readable summary, including errors if present.

**Execution paths (summary):**

- If `ServerConfig.script_execution_api_resource_path` is set → **Path B (Scripted REST API)**: works for service accounts; use `gs.info()` for all output.
- Otherwise → **Path A (UI session, `/sys.scripts.do`)**: works only for personal accounts with browser login; `gs.print()` output available; silently fails for service accounts.

### Example: Safe read-only background script

```python
result = await mcp.use_tool("servicenow", "run_background_script", {
    "script": """
        // Count active incidents and print the number
        var gr = new GlideRecord('incident');
        gr.addQuery('active', true);
        gr.setLimit(10);
        gr.query();
        var count = 0;
        while (gr.next()) {
            count++;
        }
        gs.print('Active incidents (sampled limit=10): ' + count);
        gs.info('ScriptingDemo | counted=' + count + ' | run_id=' + __MFCP_RUN_ID);
    """,
    "scope": "global"
})

print("HTTP status:", result["http_status"])
print("Direct output:")
print(result["direct_output"])
print("Syslog entries:")
for entry in result["syslog_entries"]:
    print(f"[{entry['created_on']}] {entry['level']}: {entry['message']}")
```

> **Warning:** Background scripts can change or delete data. Keep scripts as small and targeted as possible. Prefer read-only scripts and DRY_RUN patterns, and only run destructive scripts under strict governance.

---

## Script Include Management

The Script Include tools provide CRUD-style operations for `sys_script_include`. They are useful for managing reusable server-side logic from MCP.

### Tool: list_script_includes

List Script Includes with optional filters.

**Tool Name:** `list_script_includes`

**Parameters (ListScriptIncludesParams):**

- `limit` (int, optional, default: `10`): Maximum number of Script Includes to return.
- `offset` (int, optional, default: `0`): Offset for pagination.
- `active` (bool, optional): Filter by active status.
- `client_callable` (bool, optional): Filter by client-callable status.
- `query` (string, optional): Name search filter (e.g. `"MyUtil"`).

**Returns:**

A dictionary with:

- `success` (bool)
- `message` (string)
- `script_includes` (list): Each entry includes `sys_id`, `name`, `description`, `api_name`, `client_callable`, `active`, `access`, `created_on`, `updated_on`, `created_by`, `updated_by`.
- `total` (int): Count of returned Script Includes.
- `limit`, `offset` (ints): Echoed paging parameters.

### Tool: get_script_include

Get a single Script Include by sys_id or name.

**Tool Name:** `get_script_include`

**Parameters (GetScriptIncludeParams):**

- `script_include_id` (string, required):  
  - `"sys_id:<sys_id>"` to query by sys_id, or  
  - the Script Include `name` to query by name.

**Returns:**

- `success` (bool)
- `message` (string)
- `script_include` (dict, when found): Same shape as items from `list_script_includes` plus `script` content.

### Tool: create_script_include

Create a new Script Include.

**Tool Name:** `create_script_include`

**Parameters (CreateScriptIncludeParams):**

- `name` (string, required): Name of the Script Include.
- `script` (string, required): Full script content.
- `description` (string, optional): Description.
- `api_name` (string, optional): API name.
- `client_callable` (bool, optional, default: `false`): Whether the Script Include is client-callable.
- `active` (bool, optional, default: `true`): Whether it is active.
- `access` (string, optional, default: `"package_private"`): Access level.

**Returns (ScriptIncludeResponse):**

- `success` (bool)
- `message` (string)
- `script_include_id` (string, optional): sys_id of the created Script Include.
- `script_include_name` (string, optional): Name of the created Script Include.

### Tool: update_script_include

Update an existing Script Include.

**Tool Name:** `update_script_include`

**Parameters (UpdateScriptIncludeParams):**

- `script_include_id` (string, required): Script Include ID or name.
- `script` (string, optional): New script content.
- `description` (string, optional)
- `api_name` (string, optional)
- `client_callable` (bool, optional)
- `active` (bool, optional)
- `access` (string, optional)

**Returns (ScriptIncludeResponse):**

- `success` (bool)
- `message` (string)
- `script_include_id`, `script_include_name` (optional): Identifiers of the updated Script Include.

### Tool: delete_script_include

Delete an existing Script Include.

**Tool Name:** `delete_script_include`

**Parameters (DeleteScriptIncludeParams):**

- `script_include_id` (string, required): Script Include ID or name.

**Returns (ScriptIncludeResponse):**

- `success` (bool)
- `message` (string)
- `script_include_id`, `script_include_name` (optional): Identifiers of the deleted Script Include.

---

## Script Include Usage Examples

### List active Script Includes

```python
result = await mcp.use_tool("servicenow", "list_script_includes", {
    "limit": 5,
    "active": True
})

print(result["message"])
for si in result["script_includes"]:
    print(f"{si['sys_id']} | {si['name']} | client_callable={si['client_callable']}")
```

### Create a simple utility Script Include

```python
result = await mcp.use_tool("servicenow", "create_script_include", {
    "name": "McpDemoUtil",
    "description": "Utility functions created from MCP demo",
    "script": '''
        var McpDemoUtil = Class.create();
        McpDemoUtil.prototype = {
            initialize: function() {},

            hello: function(name) {
                return "Hello, " + name + " from MCP!";
            },

            type: "McpDemoUtil"
        };
    ''',
    "client_callable": False,
    "active": True,
    "access": "package_private"
})

print(result["message"])
print("Created Script Include ID:", result.get("script_include_id"))
```

### Update Script Include description

```python
result = await mcp.use_tool("servicenow", "update_script_include", {
    "script_include_id": "McpDemoUtil",
    "description": "Updated description from MCP scripting demo"
})

print(result["message"])
```

### Delete a Script Include (cleanup)

```python
result = await mcp.use_tool("servicenow", "delete_script_include", {
    "script_include_id": "McpDemoUtil"
})

print(result["message"])
```

---

## Best Practices

1. **Treat background scripts as dangerous by default**  
   Restrict them to sub-prod environments and ensure they go through your change management and review process. Prefer DRY_RUN-style scripts whenever possible.

2. **Use Script Includes for reusable logic**  
   Avoid embedding large business logic directly in background scripts. Encapsulate it in Script Includes and call those from controlled points (e.g. Business Rules, Scripted REST APIs).

3. **Name Script Includes clearly**  
   Use descriptive names, API names, and descriptions to make ownership and purpose obvious.

4. **Clean up demo and experimental Script Includes**  
   Use `delete_script_include` to remove proof-of-concept Script Includes when they are no longer needed.

5. **Avoid editing platform Script Includes blindly**  
   Prefer creating new Script Includes or extending behavior, and only modify existing ones when you fully understand their impact.

