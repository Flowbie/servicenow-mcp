---
name: build-fix
description: Fix failing ruff, mypy, or pytest errors in servicenow-mcp. Invokes everything-claude-code:build-error-resolver with the Python diagnostic commands.
argument-hint: "[paste the error output or describe what failed, e.g. 'mypy type errors in tools/incident_tools.py']"
disable-model-invocation: true
---

# /build-fix

## Intent

Resolve failing linting, type checking, formatting, or test errors in servicenow-mcp.
Delegates to `everything-claude-code:build-error-resolver` with the project's
diagnostic command set.

---

## Diagnostic Command Set

Pass this to the `everything-claude-code:build-error-resolver` agent:

```bash
# Run from servicenow-mcp/ with the venv active or via uv run

ruff check src/          # linting
mypy src/                # type checking
black --check src/       # formatting (check only — do not auto-format)
pytest tests/ -x         # tests, stop on first failure
```

Order of execution: ruff → mypy → black → pytest. Fix errors in this order unless
`$ARGUMENTS` identifies a specific failing command.

---

## Step 1 — Identify the failure

If `$ARGUMENTS` contains error output or identifies a specific tool, pass that
directly to the agent as the starting point.

If no arguments are provided, run the diagnostic commands in order and pass the
first failing output to the agent.

---

## Step 2 — Invoke build-error-resolver

Invoke `everything-claude-code:build-error-resolver` with:
- The error output (from `$ARGUMENTS` or from Step 1)
- The diagnostic command set above
- The instruction: "Make minimal fixes only — no refactoring. Re-run the failing
  command after each fix before moving to the next error."

The agent must:
1. Fix one error at a time
2. Re-run the specific failing command after each fix to verify resolution
3. Stop when all four commands pass cleanly

---

## Step 3 — Verify clean build

After the agent completes, confirm all four commands pass:

```bash
ruff check src/ && mypy src/ && black --check src/ && pytest tests/ -x
```

If any command still fails, invoke the agent again with the remaining error output.
