# Flow Designer MCP Tooling Gap Analysis and Implementation Plan

## Objective

Define a complete plan to evolve the MCP from legacy **Workflow** support to comprehensive **Flow Designer** support so prompts can create and modify production-grade automation the same way a ServiceNow engineer would.

## Investigation Summary

### Current state in this repository

- The repo currently exposes `workflow_tools.py` (legacy Workflow engine), not `flow_tools.py`.
- Existing workflow support is limited to:
  - Workflow CRUD-lite (`list`, `get`, `create`, `update`, `activate`, `deactivate`)
  - Workflow activity CRUD-lite (`add`, `update`, `delete`, `reorder`)
- Tool registration in `tool_utils.py` and exports in `tools/__init__.py` only include workflow-oriented functions.
- Existing docs (`docs/workflow_management.md`) describe legacy workflow features and do not cover Flow Designer objects (flows, subflows, actions, spokes, playbooks, decision tables, or modern flow logic controls).

### Key gap

The MCP does not currently model Flow Designer primitives and cannot perform most requested actions such as creating subflows/actions/script steps, adding decision/parallel/loop/wait logic, or updating an in-progress flow graph.

---

## Design Principles for the New `flow_tools.py`

1. **Graph-first model**: treat a flow/subflow/action as a graph of steps and branches, not a flat list.
2. **Idempotent updates**: support safe prompt retries using stable external IDs and patch semantics.
3. **Composable tool surface**: separate artifact-level CRUD (flow/subflow/action) from step-level graph mutation tools.
4. **Discoverability first**: include read/list tools for available actions/spokes/inputs/outputs before mutation tools.
5. **Human-debuggable outputs**: every mutation returns resolved sys_ids, changed nodes, and validation warnings.

---

## Proposed Capability Matrix

Legend: ✅ present, ❌ missing, 🧩 partial.

| Capability Area | Create | Read/List | Update | Notes |
|---|---:|---:|---:|---|
| Flows | ❌ | ❌ | ❌ | No Flow Designer artifact tools today |
| Subflows | ❌ | ❌ | ❌ | Needed for reusable automation |
| Actions | ❌ | ❌ | ❌ | Includes custom action metadata |
| Scripted actions / script steps | ❌ | ❌ | ❌ | Must support script body + inputs/outputs |
| Available action catalog (spokes/actions) | ❌ | ❌ | N/A | Needed to ground LLM choices |
| Decision tables | ❌ | ❌ | ❌ | For `make a decision` + governance logic |
| Playbooks | ❌ | ❌ | ❌ | Requested explicitly |
| If / Else logic | ❌ | ❌ | ❌ | Step-level graph branching |
| For each | ❌ | ❌ | ❌ | Loop control block |
| Do until | ❌ | ❌ | ❌ | Loop-until block |
| Parallel branches | ❌ | ❌ | ❌ | Fan-out/fan-in support |
| Wait for duration | ❌ | ❌ | ❌ | Timed pause step |
| Call workflow | ❌ | ❌ | ❌ | Legacy workflow invocation step |
| Dynamic flow invocation | ❌ | ❌ | ❌ | Runtime flow/subflow selection |
| End flow | ❌ | ❌ | ❌ | Explicit termination/result status |
| Flow outputs | ❌ | ❌ | ❌ | Required for subflows/actions |
| Set/append flow variables | ❌ | ❌ | ❌ | Data mutation helpers |
| Try / Catch | ❌ | ❌ | ❌ | Error-handling branch construct |

---

## Proposed Tool Set (MCP Functions)

### 1) Artifact lifecycle tools (top-level entities)

- `create_flow`, `get_flow`, `list_flows`, `update_flow`, `publish_flow`
- `create_subflow`, `get_subflow`, `list_subflows`, `update_subflow`, `publish_subflow`
- `create_action`, `get_action`, `list_actions`, `update_action`, `publish_action`
- `create_playbook`, `get_playbook`, `list_playbooks`, `update_playbook`
- `create_decision_table`, `get_decision_table`, `list_decision_tables`, `update_decision_table`

### 2) Discovery tools (for grounding)

- `list_available_spokes`
- `list_available_actions`
- `get_action_signature` (inputs, outputs, required roles, runtime constraints)
- `search_actions` (keyword + capability filters)

### 3) Flow graph mutation tools

- `add_flow_step` (generic dispatcher by step type)
- `update_flow_step`
- `delete_flow_step`
- `move_flow_step`
- `connect_flow_steps` / `disconnect_flow_steps`
- `validate_flow_graph`
- `get_flow_graph`

### 4) Specialized logic-step tools

- `add_if_branch_step` / `update_if_branch_step`
- `add_for_each_step` / `update_for_each_step`
- `add_do_until_step` / `update_do_until_step`
- `add_parallel_step` / `update_parallel_step`
- `add_decision_step` / `update_decision_step`
- `add_wait_duration_step` / `update_wait_duration_step`
- `add_call_workflow_step` / `update_call_workflow_step`
- `add_dynamic_flow_step` / `update_dynamic_flow_step`
- `add_end_flow_step` / `update_end_flow_step`
- `add_try_catch_step` / `update_try_catch_step`

### 5) Data and contract tools

- `set_flow_variable`, `append_flow_variable`
- `create_flow_output`, `update_flow_output`, `list_flow_outputs`
- `create_action_input_output_contract`, `update_action_input_output_contract`
- `create_script_step`, `update_script_step` (script + bindings + lint/validation)

---

## API/Implementation Strategy

## Phase 0 — Foundation (required first)

1. Create `src/servicenow_mcp/tools/flow_tools.py` with:
   - Shared request helpers (`_get_auth_and_config`, `_unwrap_params`) aligned with existing tool conventions.
   - Consistent error model and response envelope.
2. Add new param models for all initial Flow Designer tools.
3. Register tools in:
   - `src/servicenow_mcp/utils/tool_utils.py`
   - `src/servicenow_mcp/tools/__init__.py`
4. Add docs:
   - `docs/flow_designer_management.md` (authoritative usage guide)

## Phase 1 — Core Flow/Subflow/Action lifecycle

Deliver minimal viable parity for day-1 prompts:

- Create/list/get/update/publish for flow/subflow/action.
- Read flow graph and basic step insertion (`action`, `script`, `if`, `wait`, `end`).
- Flow validation endpoint/tool.

## Phase 2 — Advanced logic and runtime controls

- `for each`, `do until`, parallel branches, decision steps.
- Dynamic flow invocation, call workflow, try/catch.
- Step reordering and branch rewiring with topological validation.

## Phase 3 — Decision tables and playbooks

- Decision table CRUD + row/rule operations.
- Playbook CRUD + stage/task orchestration.
- Integration tools for invoking decision tables from flow steps.

## Phase 4 — Contract/data ergonomics

- Inputs/outputs schema management for subflows/actions.
- Variable management (`set`, `append`) with expression helpers.
- Read outputs, map data pills, and inspect unresolved references.

## Phase 5 — Reliability and developer UX

- Dry-run mode and diff preview for updates.
- Idempotency keys and optimistic concurrency checks.
- Optional rollback tooling for failed multi-step mutations.

---

## Cross-Cutting Requirements

1. **Update support for all create operations**
   - Every entity/step created in MCP must have a corresponding update function.
2. **Round-trip fidelity**
   - `get_*` output must include enough state to reconstruct or patch with MCP tools.
3. **Prompt-safe operations**
   - Add guardrails against destructive operations without explicit confirmation flags.
4. **Validation-first execution**
   - Validate references (action IDs, variable paths, branch targets) before mutation.
5. **Versioning/publish model**
   - Distinguish draft edits from publish actions for flows/subflows/actions.

---

## Suggested Initial Backlog (prioritized)

### P0

- `flow_tools.py` scaffold + common helper utilities.
- Flow/Subflow/Action create-get-list-update tools.
- Tool registration + docs.

### P1

- Read available actions/spokes/signatures.
- Add/update script steps.
- Add/update if + wait + end steps.
- Graph read + validation.

### P2

- Loop, parallel, decision, try/catch blocks.
- Variable set/append + output contract tools.

### P3

- Decision table and playbook lifecycle.
- Dynamic flow + call workflow step tooling.

---

## Acceptance Criteria

1. A prompt can create a new flow with triggers, actions, conditions, waits, and outputs.
2. A prompt can modify an existing flow without rebuilding it from scratch.
3. A prompt can discover valid available actions before adding one.
4. A prompt can create/update subflows and custom actions with scripted logic.
5. A prompt can represent control-flow constructs: if, for-each, do-until, parallel, decision, try/catch, and end.
6. A prompt can manage decision tables and playbooks used by flows.
7. All create operations have matching update operations.

---

## Immediate Next Steps

1. Implement `flow_tools.py` with P0 scope.
2. Wire tools into `tool_utils.py` and `tools/__init__.py`.
3. Add unit/integration tests for create/update/read lifecycles and step graph validation.
4. Add `docs/flow_designer_management.md` with examples for each supported construct.
