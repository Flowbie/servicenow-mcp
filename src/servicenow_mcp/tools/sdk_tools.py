"""
Tier 1 tooling: NowSDK Fluent (@servicenow/sdk) CLI wrappers.

Three-tier development routing:
  Tier 1 (here): NowSDK Fluent — scaffold, build, deploy metadata-as-code
  Tier 2: MCP REST tools — runtime CRUD, update sets, queries
  Tier 3: run_background_script(execution_method='fix_script') — manual fallback

Requires Node.js 20+ and @servicenow/sdk v4.6.0+.
"""
import json
import os
import subprocess
from pathlib import Path
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

from servicenow_mcp.auth import AuthManager
from servicenow_mcp.utils.config import ServerConfig
from servicenow_mcp.utils.response_envelope import SnowResponse


# ── Templates ─────────────────────────────────────────────────────────────────

def _tables_template(scope: str, app_name: str) -> str:
    return f"""\
// src/fluent/tables.now.ts
// Tier 1: NowSDK Fluent — Table definitions for {app_name}
// Run 'npx @servicenow/sdk explain Table --format=raw' for full API reference.
import {{
  Table, StringColumn, IntegerColumn, BooleanColumn,
  DateColumn, ReferenceColumn
}} from '@servicenow/sdk/core'

export const {scope}_record = Table({{
  name: '{scope}_record',
  schema: {{
    title: StringColumn({{ mandatory: true, label: 'Title', maxLength: 200 }}),
    priority: IntegerColumn({{ mandatory: true, label: 'Priority' }}),
    active: BooleanColumn({{ mandatory: true, label: 'Active', default: true }}),
    assigned_to: ReferenceColumn({{
      label: 'Assigned To',
      referenceTable: 'sys_user',
    }}),
  }},
}})
"""


def _flows_template(scope: str, app_name: str) -> str:
    return f"""\
// src/fluent/flows.now.ts
// Tier 1: NowSDK Fluent — Flow definitions for {app_name}
// Run 'npx @servicenow/sdk explain Flow --format=raw' for full API reference.
// NOTE: After 'now-sdk deploy', flows must be compiled manually in Flow Designer UI (Tier 3).
import {{ action, Flow, wfa, trigger }} from '@servicenow/sdk/automation'

export const {scope}_example_flow = Flow(
  {{
    $id: Now.ID['{scope}_example_flow'],
    name: '{app_name} Example Flow',
    description: 'Replace with your flow description',
  }},
  wfa.trigger(
    trigger.record.created,
    {{ $id: Now.ID['{scope}_example_trigger'] }},
    {{
      table: '{scope}_record',
      condition: 'active=true',
      run_flow_in: 'background',
    }}
  ),
  (params) => {{
    wfa.action(
      action.core.log,
      {{ $id: Now.ID['{scope}_log_action'] }},
      {{
        log_level: 'info',
        log_message: 'Flow triggered for record: ' + wfa.dataPill(params.trigger.current.sys_id, 'string'),
      }}
    )
  }}
)
"""


def _rules_template(scope: str, app_name: str) -> str:
    return f"""\
// src/fluent/rules.now.ts
// Tier 1: NowSDK Fluent — Business Rule definitions for {app_name}
// Run 'npx @servicenow/sdk explain BusinessRule --format=raw' for full API reference.
import {{ BusinessRule }} from '@servicenow/sdk/core'

export const {scope}_validate = BusinessRule({{
  $id: Now.ID['{scope}_validate'],
  name: 'Validate {app_name} Record',
  active: true,
  table: '{scope}_record',
  when: 'before',
  insert: true,
  update: true,
  script: Now.include('./validate.server.js'),
}})
"""


def _validate_server_template(scope: str) -> str:
    return f"""\
// src/fluent/validate.server.js
// Server-side script for {scope}_validate business rule.
(function executeRule(current, previous) {{
  // Add validation logic here
  if (!current.title) {{
    gs.addErrorMessage('Title is required');
    current.setAbortAction(true);
  }}
}})(current, previous);
"""


def _catalog_template(scope: str, app_name: str) -> str:
    return f"""\
// src/fluent/catalog.now.ts
// Tier 1: NowSDK Fluent — Catalog Item definitions for {app_name}
// Run 'npx @servicenow/sdk explain CatalogItem --format=raw' for full API reference.
import {{
  CatalogItem, VariableSet, SingleLineTextVariable,
  MultiLineTextVariable, RequestedForVariable
}} from '@servicenow/sdk/core'

const {scope}_varset = VariableSet({{
  $id: Now.ID['{scope}_varset'],
  title: '{app_name} Details',
  internalName: '{scope}_varset',
  type: 'singleRow',
  order: 100,
  displayTitle: true,
  version: 1,
  variables: {{
    requestTitle: SingleLineTextVariable({{
      question: 'Title',
      mandatory: true,
      order: 100,
    }}),
    requestDescription: MultiLineTextVariable({{
      question: 'Description',
      mandatory: false,
      order: 200,
    }}),
  }},
  name: '{app_name} Details',
}})

export const {scope}_catalog_item = CatalogItem({{
  $id: Now.ID['{scope}_catalog_item'],
  name: '{app_name}',
  shortDescription: 'Submit a {app_name} request',
  catalogs: ['e0d08b13c3330100c8b837659bba8fb4'],
  variableSets: [{{ variableSet: {scope}_varset, order: 100 }}],
  variables: {{
    requestedFor: RequestedForVariable({{ order: 1, question: 'Requested For' }}),
  }},
}})
"""


# ── Parameter Models ──────────────────────────────────────────────────────────

class SdkScaffoldParams(BaseModel):
    scope: str = Field(
        ...,
        description=(
            "Application scope prefix (e.g., 'x_myco_app'). "
            "Must start with 'x_' for custom scoped apps. "
            "This becomes the table prefix and namespace for all artifacts."
        ),
    )
    app_name: str = Field(..., description="Display name for the application (e.g., 'My Custom App')")
    project_path: str = Field(
        ...,
        description=(
            "Absolute path where the SDK project directory should be created. "
            "Directory will be created if it does not exist."
        ),
    )
    include_tables: bool = Field(default=True, description="Generate tables.now.ts template")
    include_flows: bool = Field(default=False, description="Generate flows.now.ts template")
    include_business_rules: bool = Field(default=False, description="Generate rules.now.ts and validate.server.js templates")
    include_catalog: bool = Field(default=False, description="Generate catalog.now.ts template")


class SdkExplainParams(BaseModel):
    topic: Optional[str] = Field(
        default=None,
        description=(
            "SDK topic to explain. Examples: 'BusinessRule', 'Flow', 'ScriptInclude', "
            "'Table', 'Acl', 'CatalogItem', 'naming', 'structure', 'build'. "
            "Omit to list all available topics."
        ),
    )
    peek: bool = Field(
        default=True,
        description="ALWAYS use peek=True first to preview before loading full content.",
    )
    list_topics: bool = Field(default=False, description="List all available topics. Overrides topic.")


class SdkRunCommandParams(BaseModel):
    command: Literal["build", "deploy"] = Field(
        ...,
        description=(
            "'build': Validate and compile project metadata. Run before deploy. "
            "'deploy': Deploy compiled metadata to the authenticated ServiceNow instance. "
            "After deploy, flows must be compiled manually in Flow Designer (Tier 3 fallback)."
        ),
    )
    project_path: str = Field(
        ...,
        description="Absolute path to the SDK project directory (must contain now.config.json).",
    )
    dry_run: bool = Field(
        default=True,
        description="Validate without executing. Default True — set False for actual execution.",
    )


# ── Tool Implementations ──────────────────────────────────────────────────────

def sdk_scaffold(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: SdkScaffoldParams,
) -> dict:
    """
    Scaffold a new @servicenow/sdk Fluent project.
    Creates now.config.json, package.json, src/fluent/ directory, and
    template files for the requested artifact types.
    """
    root = Path(params.project_path)
    try:
        root.mkdir(parents=True, exist_ok=True)
        fluent_dir = root / "src" / "fluent"
        fluent_dir.mkdir(parents=True, exist_ok=True)

        files_created: List[str] = []

        config_path = root / "now.config.json"
        config_path.write_text(
            json.dumps({"scope": params.scope, "scopeId": ""}, indent=2) + "\n"
        )
        files_created.append(str(config_path))

        pkg_path = root / "package.json"
        pkg_path.write_text(
            json.dumps(
                {
                    "name": params.scope.replace("_", "-"),
                    "version": "1.0.0",
                    "scripts": {"build": "now-sdk build", "deploy": "now-sdk deploy"},
                    "devDependencies": {
                        "@servicenow/glide": "catalog:",
                        "@servicenow/sdk": "catalog:",
                        "typescript": "catalog:",
                    },
                },
                indent=2,
            )
            + "\n"
        )
        files_created.append(str(pkg_path))

        templates = []
        if params.include_tables:
            templates.append(("tables.now.ts", _tables_template(params.scope, params.app_name)))
        if params.include_flows:
            templates.append(("flows.now.ts", _flows_template(params.scope, params.app_name)))
        if params.include_business_rules:
            templates.append(("rules.now.ts", _rules_template(params.scope, params.app_name)))
            templates.append(("validate.server.js", _validate_server_template(params.scope)))
        if params.include_catalog:
            templates.append(("catalog.now.ts", _catalog_template(params.scope, params.app_name)))

        for filename, content in templates:
            path = fluent_dir / filename
            path.write_text(content)
            files_created.append(str(path))
    except OSError as e:
        return SnowResponse(
            success=False,
            error=f"Failed to scaffold project at {params.project_path}: {e}",
            operation="sdk_scaffold",
        ).to_dict()

    return SnowResponse(
        success=True,
        data={
            "project_path": str(root),
            "scope": params.scope,
            "files_created": files_created,
            "next_steps": [
                "1. cd into project_path",
                "2. Run: npm install",
                "3. Run: now-sdk auth  (authenticate to your instance)",
                "4. Edit the generated template files with your artifact definitions",
                "5. Run sdk_run_command(command='build', dry_run=True) to validate",
                "6. Run sdk_run_command(command='deploy', dry_run=False) to deploy",
                "7. For flows: compile manually in Flow Designer after deploy (Tier 3 fallback)",
            ],
        },
        operation="sdk_scaffold",
    ).to_dict()


def sdk_explain(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: SdkExplainParams,
) -> dict:
    """
    Fetch @servicenow/sdk documentation via 'npx @servicenow/sdk explain'.
    Always peek=True first; read full content only when topic is confirmed relevant.
    Requires Node.js 20+ and @servicenow/sdk v4.6.0+.
    """
    if params.list_topics:
        cmd = ["npx", "--yes", "@servicenow/sdk", "explain", "--list"]
    elif params.topic:
        cmd = ["npx", "--yes", "@servicenow/sdk", "explain", params.topic]
        cmd.append("--peek" if params.peek else "--format=raw")
    else:
        cmd = ["npx", "--yes", "@servicenow/sdk", "explain", "--list"]

    cmd_str = " ".join(cmd)
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if proc.returncode == 0:
            return SnowResponse(
                success=True,
                data={"output": proc.stdout, "command": cmd_str},
                operation="sdk_explain",
            ).to_dict()
        return SnowResponse(
            success=False,
            data={"command": cmd_str, "output": proc.stdout},
            error=proc.stderr or f"Exit code {proc.returncode}",
            operation="sdk_explain",
        ).to_dict()
    except subprocess.TimeoutExpired:
        return SnowResponse(
            success=False,
            data={"command": cmd_str},
            error="sdk explain timed out after 60 seconds. Try a more specific topic.",
            operation="sdk_explain",
        ).to_dict()
    except FileNotFoundError:
        return SnowResponse(
            success=False,
            data={"command": cmd_str},
            error=(
                "npx not found. Node.js 20+ is required. "
                "Run the 'now-sdk-setup' skill to configure your environment."
            ),
            operation="sdk_explain",
        ).to_dict()


def sdk_run_command(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: SdkRunCommandParams,
) -> dict:
    """
    Run 'now-sdk build' or 'now-sdk deploy' against a local Fluent project.
    Validates now.config.json exists before executing.
    dry_run=True by default — set False for actual build/deploy.

    After 'deploy': flows require manual compilation in Flow Designer (Tier 3 fallback).
    """
    config_file = os.path.join(params.project_path, "now.config.json")
    if not os.path.isfile(config_file):
        return SnowResponse(
            success=False,
            error=(
                f"now.config.json not found at {params.project_path}. "
                "Use sdk_scaffold to create a new project, or verify the path is correct."
            ),
            operation="sdk_run_command",
        ).to_dict()

    cmd = ["npx", "--yes", "@servicenow/sdk", params.command]
    if params.dry_run:
        cmd.append("--dry-run")

    warnings = []
    if params.dry_run:
        warnings.append("dry_run=True — no changes were made. Set dry_run=False for actual execution.")
    if params.command == "deploy" and not params.dry_run:
        warnings.append(
            "Deploy complete. If this project includes Flows, compile them manually in "
            "Flow Designer UI (sys_hub_flow) — flow compilation cannot be automated (Tier 3 fallback)."
        )

    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=120, cwd=params.project_path
        )
        success = proc.returncode == 0
        return SnowResponse(
            success=success,
            data={"command": " ".join(cmd), "project_path": params.project_path, "output": proc.stdout},
            error=proc.stderr if not success else None,
            operation="sdk_run_command",
            warnings=warnings,
        ).to_dict()
    except subprocess.TimeoutExpired:
        return SnowResponse(success=False, error="SDK command timed out after 120 seconds.", operation="sdk_run_command").to_dict()
    except FileNotFoundError:
        return SnowResponse(success=False, error="npx not found. Node.js 20+ required.", operation="sdk_run_command").to_dict()
