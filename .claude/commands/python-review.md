---
name: python-review
description: Review Python files in servicenow-mcp for PEP 8 compliance, type hints, MCP tool patterns, and test coverage. Invokes everything-claude-code:python-reviewer.
argument-hint: "[optional: specific file path, e.g. src/servicenow_mcp/tools/flow_tools.py]"
disable-model-invocation: true
---

# /python-review

## Intent

Run a comprehensive Python code review on servicenow-mcp source files. Delegates to
`everything-claude-code:python-reviewer` for standard checks, then applies a
project-specific overlay for MCP tool file/test file pairing.

---

## Scope

If `$ARGUMENTS` names a specific file, scope the review to that file only.

If no argument is provided, determine scope from:
```bash
git diff --name-only -- '*.py'
```
Review all Python files in the diff. If the diff is empty, ask the user which file(s) to review.

---

## Step 1 — Invoke python-reviewer

Invoke the `everything-claude-code:python-reviewer` agent on the scoped file(s).

Standard checks performed by the agent:
- PEP 8 compliance and style
- Type hint coverage and accuracy
- Pythonic idioms and anti-patterns
- Security issues (input validation, secrets handling)
- Function and module complexity
- Docstring presence for public functions

---

## Step 2 — Apply MCP tool file overlay

After receiving the agent's findings, apply this project-specific check:

For every file matching `src/servicenow_mcp/tools/<name>.py`:
- Verify that a corresponding `tests/test_<name>.py` exists.
- If missing: add a **MEDIUM** finding:
  > "MCP tool file `src/servicenow_mcp/tools/<name>.py` has no corresponding test file
  > `tests/test_<name>.py`. All MCP tool modules must have a dedicated test file."

---

## Step 3 — Aggregate and report

Combine the `everything-claude-code:python-reviewer` findings with any overlay findings.
Report in this structure:

```
## Python Review: <file or scope description>

### CRITICAL
<findings or "None">

### HIGH
<findings or "None">

### MEDIUM
<findings or "None">

### LOW / STYLE
<findings or "None">

### Verdict
PASS | PASS WITH MINOR ISSUES | FAIL

Action required for CRITICAL and HIGH before merge.
```
