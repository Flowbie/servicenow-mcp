---
name: tdd
description: Test-driven development for servicenow-mcp Python tools. Write failing pytest tests first, then implement. Use when adding or fixing MCP tool functions.
argument-hint: "[what to build or fix, e.g. 'add bulk-delete to incident_tools.py']"
disable-model-invocation: true
---

# /tdd

## Intent

Enforce test-driven development for servicenow-mcp. Delegates to
`everything-claude-code:tdd-guide` pre-loaded with this project's toolchain so the
agent does not default to TypeScript/Jest patterns.

---

## Project Toolchain Context

Pass this context to the `everything-claude-code:tdd-guide` agent at invocation:

```
Project: servicenow-mcp (Python MCP server)
Language: Python 3.11
Test runner: pytest
Run tests: .venv/bin/python -m pytest tests/ OR uv run pytest tests/
Run with coverage: uv run pytest tests/ --cov=src/servicenow_mcp --cov-report=term-missing
Coverage target: 80% minimum
Test file convention: tests/test_<tool_name>.py for each src/servicenow_mcp/tools/<tool_name>.py
Fixtures: use pytest fixtures in conftest.py; mock HTTP calls with unittest.mock or pytest-mock
Do NOT use Jest, vitest, or any JavaScript testing patterns.
```

---

## Step 1 — Clarify the task

If `$ARGUMENTS` is provided, use it as the task description. If not, ask:

> "What are you building or fixing? (e.g. 'add bulk-delete endpoint to incident_tools.py')"

---

## Step 2 — Invoke tdd-guide

Invoke `everything-claude-code:tdd-guide` with:
- The task description from Step 1
- The project toolchain context above
- The instruction to follow the RED → GREEN → IMPROVE cycle

The agent will:
1. **RED**: Scaffold the test file (`tests/test_<name>.py`) with failing tests
2. **GREEN**: Write minimal implementation to pass the tests
3. **IMPROVE**: Refactor while keeping tests passing

---

## Step 3 — Coverage gate

After implementation, run:
```bash
uv run pytest tests/ --cov=src/servicenow_mcp --cov-report=term-missing
```

If coverage for the new/modified module is below 80%, flag it and ask the agent to
add tests for the uncovered branches before marking the task complete.

---

## Step 4 — Handoff to /python-review

After TDD cycle is complete and coverage gate passes, run `/python-review` on the
new files to catch style and type hint issues.
