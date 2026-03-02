---
name: security-review
description: Security review for servicenow-mcp. Checks credential handling, REST parameter injection, and OWASP issues in MCP tool functions. Invokes everything-claude-code:security-reviewer.
argument-hint: "[optional: specific file or area, e.g. src/servicenow_mcp/auth/]"
disable-model-invocation: true
---

# /security-review

## Intent

Run a security review on servicenow-mcp source files. Applies three MCP-specific
checks before delegating to `everything-claude-code:security-reviewer` for the full
OWASP pass.

---

## Scope

If `$ARGUMENTS` names a specific file or directory, scope to it. Otherwise, scope to
all files in `src/servicenow_mcp/`.

---

## Step 1 — MCP-specific pre-checks

Before invoking the agent, perform these three checks manually on the scoped files:

**Check 1 — No credentials in source**
Scan for any hardcoded ServiceNow credentials. Credentials must come exclusively from
`python-dotenv` / `.env` and be accessed via environment variables.

Flag as **CRITICAL** if any of the following appear outside of `.env.example` or test
fixtures that use obvious placeholder values:
- Literal strings matching URL patterns for ServiceNow instances
- Strings that look like passwords, tokens, or Basic Auth encoded values
- Direct assignments to variables named `password`, `token`, `api_key`, `secret`

**Check 2 — No parameter injection into URLs or queries**
Scan every function in `src/servicenow_mcp/tools/` that accepts caller-supplied
parameters. Verify that no function string-interpolates those parameters directly
into a URL path or query string.

Flag as **HIGH** if a caller-supplied value is concatenated into:
- `f"...{param}..."` inside a URL or encoded query
- `"..." + param + "..."` inside a URL or encoded query

All caller-supplied parameters must be passed as structured request payload fields
(JSON body or typed query parameters), not interpolated into the URL.

**Check 3 — Timeouts on all outbound HTTP calls**
Scan every `httpx` call in `src/servicenow_mcp/`. Verify that every call sets a
`timeout` argument explicitly.

Flag as **MEDIUM** if any `httpx.get`, `httpx.post`, `httpx.request`, or
`httpx.AsyncClient` call does not set `timeout`.

---

## Step 2 — Invoke security-reviewer

Invoke `everything-claude-code:security-reviewer` on the scoped files for the full
OWASP Top 10 pass, including:
- Injection vulnerabilities
- Broken authentication
- Sensitive data exposure
- Security misconfiguration
- Insecure deserialization

---

## Step 3 — Aggregate and report

Combine the pre-check findings with the agent's findings:

```
## Security Review: <scope>

### CRITICAL
<findings or "None">

### HIGH
<findings or "None">

### MEDIUM
<findings or "None">

### LOW
<findings or "None">

### Verdict
SECURE | CONDITIONALLY SECURE (minor issues only) | BLOCKED (CRITICAL or HIGH outstanding)
```

Do not proceed with any commit or promotion if CRITICAL or HIGH findings are unresolved.
