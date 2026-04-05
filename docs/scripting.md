# Scripting Tools in ServiceNow MCP

This document describes the scripting tools provided by the ServiceNow MCP server for executing background scripts and managing Script Includes.

## Overview

The scripting tools enable powerful, low-level operations against a ServiceNow instance:

- **Background scripts**: Execute arbitrary server-side JavaScript via the same mechanism as the “Background Script” module (`sys.scripts.do`) or a scripted REST API endpoint.
- **Script Includes**: Manage `sys_script_include` rows with the **generic Table API** tools (`query_records`, `get_record`, `create_record`, `update_record`, `delete_record`). Dedicated `list_script_include` / `create_script_include` MCP tools are **not** registered in this fork.

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

## Script Include management (Table API)

Use **`query_records`** / **`get_record`** / **`create_record`** / **`update_record`** / **`delete_record`** on table **`sys_script_include`**. Field names and mandatory columns depend on scope and instance; use **`list_table_fields`** and your blueprint before writes.

### List Script Includes (example)

```python
result = await mcp.use_tool("servicenow", "query_records", {
    "table": "sys_script_include",
    "query": "active=true",
    "limit": 5,
})
for row in result.get("records", []):
    print(row.get("sys_id"), row.get("name"), row.get("client_callable"))
```

### Create / update / delete

- **Create:** `create_record` with `name`, `script`, and other required fields.  
- **Update:** `update_record` with `sys_id` and changed fields (often `script`, `description`, `active`).  
- **Delete:** `delete_record` when governance allows.

Follow update-set and scope rules enforced by the MCP write path.

---

## Best Practices

1. **Treat background scripts as dangerous by default**  
   Restrict them to sub-prod environments and ensure they go through your change management and review process. Prefer DRY_RUN-style scripts whenever possible.

2. **Use Script Includes for reusable logic**  
   Avoid embedding large business logic directly in background scripts. Encapsulate it in Script Includes and call those from controlled points (e.g. Business Rules, Scripted REST APIs).

3. **Name Script Includes clearly**  
   Use descriptive names, API names, and descriptions to make ownership and purpose obvious.

4. **Clean up demo and experimental Script Includes**  
   Use `delete_record` on `sys_script_include` (when allowed) to remove proof-of-concept artifacts.

5. **Avoid editing platform Script Includes blindly**  
   Prefer creating new Script Includes or extending behavior, and only modify existing ones when you fully understand their impact.

