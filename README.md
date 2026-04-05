[![MseeP.ai Security Assessment Badge](https://mseep.net/pr/osomai-servicenow-mcp-badge.png)](https://mseep.ai/app/osomai-servicenow-mcp)

# ServiceNow MCP Server

A Model Completion Protocol (MCP) server implementation for ServiceNow, allowing Claude to interact with ServiceNow instances.

<a href="https://glama.ai/mcp/servers/@osomai/servicenow-mcp">
  <img width="380" height="200" src="https://glama.ai/mcp/servers/@osomai/servicenow-mcp/badge" alt="ServiceNow Server MCP server" />
</a>

## Overview

This project implements an MCP server that enables Claude to connect to ServiceNow instances, retrieve data, and perform actions through the ServiceNow API. It serves as a bridge between Claude and ServiceNow, allowing for seamless integration.

## Governance Ownership

This server is the authoritative mutation-governance layer in the ServiceNow agent stack.

- `servicenow-claude-os` owns conversational behavior, workflow phases, and chat discipline
- `servicenow-mcp` owns authoritative write enforcement and authoritative approval payloads
- `servicenow-workbench` owns UX, visibility, and user control surfaces

In the current governance model:

- generic CRUD writes on configuration/metadata tables are enforced here against update-set policy
- unknown tables fail closed until classified
- exempt tables are allowed without update-set enforcement
- approval payloads for key write tools are built here and passed through by Workbench

This means Workbench should not be treated as the only place where write safety lives. Even if Workbench is bypassed, MCP policy should still reject non-compliant governed writes.

## Features

- Connect to ServiceNow instances using various authentication methods (Basic, OAuth, API Key)
- Query ServiceNow records and tables (generic Table API tools)
- Create, update, and delete records on any supported table (with update-set and mandatory-field governance on writes)
- Execute background scripts and use Flow Designer authoring tools (`flow_tools`)
- Access and query the Service Catalog (CRUD via Table API; catalog helpers where packaged)
- Analyze and optimize the ServiceNow Service Catalog
- Debug mode for troubleshooting
- Support for both stdio and Server-Sent Events (SSE) communication

## Installation

### Prerequisites

- Python 3.11 or higher
- A ServiceNow instance with appropriate access credentials

### Setup

1. Clone your checkout of this repository (fork or monorepo submodule) and enter `servicenow-mcp`:
   ```
   cd servicenow-mcp
   ```

2. Create a virtual environment and install the package:
   ```
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -e .
   ```

3. Create a `.env` file with your ServiceNow credentials:
   ```
   SERVICENOW_INSTANCE_URL=https://your-instance.service-now.com
   SERVICENOW_USERNAME=your-username
   SERVICENOW_PASSWORD=your-password
   SERVICENOW_AUTH_TYPE=basic  # or oauth, api_key
   ```

## Usage

### Standard (stdio) Mode

To start the MCP server:

```
python -m servicenow_mcp.cli
```

Or with environment variables:

```
SERVICENOW_INSTANCE_URL=https://your-instance.service-now.com SERVICENOW_USERNAME=your-username SERVICENOW_PASSWORD=your-password SERVICENOW_AUTH_TYPE=basic python -m servicenow_mcp.cli
```

### Server-Sent Events (SSE) Mode

The ServiceNow MCP server can also run as a web server using Server-Sent Events (SSE) for communication, which allows for more flexible integration options.

#### Starting the SSE Server

You can start the SSE server using the provided CLI:

```
servicenow-mcp-sse --instance-url=https://your-instance.service-now.com --username=your-username --password=your-password
```

By default, the server will listen on `0.0.0.0:8080`. You can customize the host and port:

```
servicenow-mcp-sse --host=127.0.0.1 --port=8000
```

#### Connecting to the SSE Server

The SSE server exposes two main endpoints:

- `/sse` - The SSE connection endpoint
- `/messages/` - The endpoint for sending messages to the server

#### Example

See the `examples/sse_server_example.py` file for a complete example of setting up and running the SSE server.

```python
from servicenow_mcp.server import ServiceNowMCP
from servicenow_mcp.server_sse import create_starlette_app
from servicenow_mcp.utils.config import ServerConfig, AuthConfig, AuthType, BasicAuthConfig
import uvicorn

# Create server configuration
config = ServerConfig(
    instance_url="https://your-instance.service-now.com",
    auth=AuthConfig(
        type=AuthType.BASIC,
        config=BasicAuthConfig(
            username="your-username",
            password="your-password"
        )
    ),
    debug=True,
)

# Create ServiceNow MCP server
servicenow_mcp = ServiceNowMCP(config)

# Create Starlette app with SSE transport
app = create_starlette_app(servicenow_mcp, debug=True)

# Start the web server
uvicorn.run(app, host="0.0.0.0", port=8080)
```

## Tool Packaging (Optional)

To manage the number of tools exposed to the language model (especially in environments with limits), the ServiceNow MCP server supports loading subsets of tools called "packages". This is controlled via the `MCP_TOOL_PACKAGE` environment variable.

### Configuration

1.  **Environment Variable:** Set the `MCP_TOOL_PACKAGE` environment variable to the name of the desired package.
    ```bash
    export MCP_TOOL_PACKAGE=catalog_builder
    ```
2.  **Package Definitions:** The available packages and the tools they include are defined in `config/tool_packages.yaml`. You can customize this file to create your own packages.

### Behavior

-   If `MCP_TOOL_PACKAGE` is set to a valid package name defined in `config/tool_packages.yaml`, only the tools listed in that package will be loaded.
-   If `MCP_TOOL_PACKAGE` is **not set** or is empty, the `full` package (containing all tools) is loaded by default.
-   If `MCP_TOOL_PACKAGE` is set to an invalid package name, the `none` package is loaded (no tools except `list_tool_packages`), and a warning is logged.
-   Setting `MCP_TOOL_PACKAGE=none` explicitly loads no tools (except `list_tool_packages`).

### Available Packages (Default)

The default `config/tool_packages.yaml` includes the following role-based packages:

-   `service_desk`: Generic Table API for incidents, tasks, and other ITSM tables (no incident-specific MCP wrappers).
-   `catalog_builder`: Table API for catalog tables plus `move_catalog_items` and `get_optimization_recommendations`.
-   `change_coordinator`: `submit_change_for_approval` / `approve_change` / `reject_change` plus Table API for `change_request` and related rows.
-   `knowledge_author`: Generic Table API for knowledge tables (`kb_knowledge`, `kb_knowledge_base`, `kb_category`, etc.); see `docs/knowledge_base.md`.
-   `platform_developer`: Flow Designer (`flow_tools`), `run_background_script`, update-set session tools, introspection, and Table API for scripting tables (e.g. `sys_script_include`, `sys_ui_policy`).
-   `system_administrator`: Table API for users/groups/membership rows; role grant/revoke tools; introspection and write-safety tools.
-   `agile_management`: Tools for managing user stories, epics, scrum tasks, and projects.
-   `full`: Includes all available tools (default).
-   `none`: Includes no tools (except `list_tool_packages`).

### Introspection Tool

-   **`list_tool_packages`**: Lists all available tool package names defined in the configuration and shows the currently loaded package. This tool is available in all packages except `none`.

## Available Tools

**Authoritative list:** Tool names and descriptions are registered in `src/servicenow_mcp/utils/tool_utils.py`. The active subset is selected by `MCP_TOOL_PACKAGE` and `config/tool_packages.yaml`. After connecting, call **`list_tool_packages`** to see what is loaded in your session.

### Tooling model (no per-table thin wrappers)

This fork **removed** upstream-style MCP tools that were thin facades over the same Table API (for example `list_articles`, `create_incident`, `list_workflows`, `create_user`). Those operations are performed with the **generic Table API** tools against the correct ServiceNow table, using architecture blueprints (in `servicenow-claude-os/architecture/`) for field names, states, and derived-field rules.

**What remains as named tools:**

- **Compound** operations that coordinate multiple steps or special APIs (change approval, Flow Designer `flow_tools`, agile helpers, role grant/revoke, `move_catalog_items`, `get_ritm_variables`, CMDB relationship helpers, etc.).
- **Protocol** tools: `verify_fields`, `get_field_metadata`, `list_table_fields`, `list_table_relationships`, `list_tool_packages`, `run_background_script`.
- **Update set session:** `get_current_update_set`, `set_current_update_set`, `get_current_scope`, `set_current_scope`, `get_changeset_details` (listing or creating update sets themselves uses **`query_records` / `create_record` on `sys_update_set`**).

### Generic Table API (primary path for most tables)

`query_records`, `get_record`, `create_record`, `update_record`, `delete_record`

These call `/api/now/table/{table}` and enforce **update-set policy** and **mandatory-field preflight** on writes where configured. Use them for:

- **ITSM:** `incident`, `change_request`, `problem`, `task`, `sc_task`, etc.
- **Knowledge:** `kb_knowledge_base`, `kb_category`, `kb_knowledge` (see `docs/knowledge_base.md`)
- **Users and groups:** `sys_user`, `sys_user_group`, `sys_user_grmember` (see `docs/user_management.md`)
- **Catalog:** `sc_cat_item`, `sc_category`, `catalog_script_client`, variable rows on `item_option_new`, etc.
- **Scripting / UI:** `sys_script_include`, `sys_ui_policy`, `sys_ui_policy_action`, `sys_script`, business rules, etc.
- **Legacy Workflow engine:** `wf_workflow`, `wf_workflow_version`, related tables (see `docs/workflow_management.md`)
- **Update sets:** `sys_update_set`, `sys_update_xml` (see `docs/changeset_management.md`)

### Change management

- **Compound:** `submit_change_for_approval`, `approve_change`, `reject_change`
- **CRUD on `change_request` and related rows:** Table API tools (see `docs/change_management.md`)

### Catalog helpers

- `move_catalog_items`, `get_optimization_recommendations`, `get_ritm_variables` (other catalog operations: Table API)

### Flow Designer (`flow_tools`)

Full authoring and test-execution surface for Flow Designer (for example `create_flow`, `clone_flow`, `list_flows`, `publish_flow`, `execute_flow`, `get_flow_execution_detail`, …). Details: `docs/flow_designer.md`.

### CMDB relationship tools

`get_ci_relationships`, `create_ci_relationship`, `get_ci_impact_graph` — base CI list/get/create/update uses **Table API** on the appropriate `cmdb_ci` subclass when your package includes generic CRUD.

### Integration inspection

`get_rest_message`, `get_scripted_rest_api` — other integration records use Table API with your integration blueprint.

### Agile / release (named tools + Table API)

Compound and planning tools include `archive_story`, `move_story_state`, `assign_stories_to_sprint`, `close_scrum_task`, sprint lifecycle (`create_sprint`, `get_sprint`, `start_sprint`, `close_sprint`, …), release helpers (`get_release`, `validate_release_readiness`, `compile_release_notes`, …), `story_breakdown`, governance validators, `get_blocked_work`, `recommend_sprint_stories`, etc. **Story, epic, project, and scrum task list/create/update** use **Table API** on the relevant `rm_*` / agile tables when not covered by a compound tool. See `config/tool_packages.yaml` package `agile_management`.

### User and group role assignment (compound only)

`grant_role_to_user`, `revoke_role_from_user`, `grant_role_to_group`, `revoke_role_from_group`

### System

`get_current_user`. For **system properties**, use `query_records` on `sys_properties` (or `get_record` by `sys_id` when known).

### Using the MCP CLI

The ServiceNow MCP server can be installed with the MCP CLI, which provides a convenient way to register the server with Claude.

```bash
# Install the ServiceNow MCP server with environment variables from .env file
mcp install src/servicenow_mcp/server.py -f .env
```

This command will register the ServiceNow MCP server with Claude and configure it to use the environment variables from the .env file.

### Integration with Claude Desktop

To configure the ServiceNow MCP server in Claude Desktop:

1. Edit the Claude Desktop configuration file at `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or the appropriate path for your OS:

```json
{
  "mcpServers": {
    "ServiceNow": {
      "command": "/Users/yourusername/dev/servicenow-mcp/.venv/bin/python",
      "args": [
        "-m",
        "servicenow_mcp.cli"
      ],
      "env": {
        "SERVICENOW_INSTANCE_URL": "https://your-instance.service-now.com",
        "SERVICENOW_USERNAME": "your-username",
        "SERVICENOW_PASSWORD": "your-password",
        "SERVICENOW_AUTH_TYPE": "basic"
      }
    }
  }
}
```

2. Restart Claude Desktop to apply the changes

### Example Usage with Claude

Natural-language requests are implemented with **`query_records` / `get_record` / `create_record` / `update_record`** (and compound tools where listed above). The agent should follow your instance blueprint for field names and state values.

#### Incident and ITSM (Table API)
- "Create a new incident for a network outage in the east region" (e.g. `create_record` on `incident` with required task fields)
- "List all active P1 incidents for the Network team" (`query_records` on `incident` with encoded query)
- "Update incident INC0010001 priority" (`query_records` to resolve number to `sys_id`, then `update_record`)

#### Service Catalog (Table API + helpers)
- "Show me all items in the service catalog"
- "List all service catalog categories"
- "Get details about the laptop request catalog item"
- "Show me all catalog items in the Hardware category"
- "Search for 'software' in the service catalog"
- "Create a new category called 'Cloud Services' in the service catalog"
- "Update the 'Hardware' category to rename it to 'IT Equipment'"
- "Move the 'Virtual Machine' catalog item to the 'Cloud Services' category"
- "Create a subcategory called 'Monitors' under the 'IT Equipment' category"
- "Reorganize our catalog by moving all software items to the 'Software' category"
- "Create a description field for the laptop request catalog item"
- "Add a dropdown field for selecting laptop models to catalog item"
- "List all form fields for the VPN access request catalog item"
- "Make the department field mandatory in the software request form"
- "Update the help text for the cost center field"
- "Show me all service catalogs in the system"
- "List all hardware catalog items."
- "Find the catalog item for 'New Laptop Request'."
- "Show me the variables for the 'New Laptop Request' item."
- "Create a new variable named 'department_code' for the 'New Hire Setup' catalog item. Make it a mandatory string field."

#### Catalog Optimization Examples
- "Analyze our service catalog and identify opportunities for improvement"
- "Find catalog items with poor descriptions that need improvement"
- "Identify catalog items with low usage that we might want to retire"
- "Find catalog items with high abandonment rates"
- "Optimize our Hardware category to improve user experience"

#### Change Management Examples
- "Create a normal change for server maintenance" (`create_record` on `change_request` per blueprint)
- "Submit change CHG0012345 for approval" (`submit_change_for_approval` when in package)
- "Approve the database upgrade change with comment: plan looks thorough" (`approve_change`)
- "List emergency changes this week" (`query_records` on `change_request` with encoded query)

#### Agile Management Examples

##### Story Management
- "Create a new user story for implementing a new reporting dashboard"
- "Update the 'Implement a new reporting dashboard' story to set it as blocked"
- "List all user stories assigned to the Data Analytics team"
- "Create a dependency between the 'Implement a new reporting dashboard' story and the 'Develop data extraction pipeline' story"
- "Delete the dependency between the 'Implement a new reporting dashboard' story and the 'Develop data extraction pipeline' story"
- "Create a new epic called 'Data Analytics Initiatives'"
- "Update the 'Data Analytics Initiatives' epic to set it as completed"
- "List all epics in the 'Data Analytics' project"
- "Create a new scrum task for the 'Implement a new reporting dashboard' story"
- "Update the 'Develop data extraction pipeline' scrum task to set it as completed"
- "List all scrum tasks in the 'Implement a new reporting dashboard' story"
- "Create a new project called 'Data Analytics Initiatives'"
- "Update the 'Data Analytics Initiatives' project to set it as completed"
- "List all projects in the 'Data Analytics' epic"

##### Sprint Lifecycle
- "Start the Q2 Sprint 3 sprint so the team can begin work"
- "Close sprint SPR0001234 now that all stories are complete"
- "Get a summary of story counts and points for sprint SPR0001234"

##### AI Planning Tools
- "Break down the story 'Build single sign-on integration' into implementation sub-tasks"
- "Generate acceptance criteria for the story 'Migrate incident data to new schema'"
- "Estimate story points for 'Add bulk export to the reporting dashboard' based on its description"
- "Identify the main risks for story STRY0080729 before we start the sprint"
- "Generate test scenarios for the story 'Implement password expiry notifications'"

##### Release Management
- "Create a new release called 'Q2 2026 Platform Release' targeting the production instance"
- "Get the details of release REL0000123"
- "Check whether release REL0000123 is ready to ship — are all stories complete and tested?"
- "Compile release notes for REL0000123 summarizing all completed stories"

##### Agile Reporting
- "Show me all the stories and tasks currently assigned to me"
- "Which stories in the current sprint are blocked by unresolved dependencies?"
- "Give me a status summary of all stories in release REL0000123"

##### Sprint Planning
- "Recommend which backlog stories should be pulled into the next sprint based on priority and capacity"

##### Agile Governance
- "Check whether all dependencies for story STRY0080729 are satisfied before we promote it"
- "Validate that story STRY0080729 has sufficient test coverage to be marked ready for testing"
- "Verify that story STRY0080729 has complete promotion instructions before we move it to production"

#### Flow Designer Examples
- "Clone flow sys_id A to a new draft named 'Copy of A' using clone_flow"
- "Add subflow sys_id S as a step to parent flow F with add_subflow_step_to_flow (use list_flow_io on S for input sys_ids)"
- "List input and output variables for subflow sys_id X using list_flow_io"
- "Run flow sys_id Y for testing with execute_flow and optional input key/value pairs"
- "Show step-level rows for execution sys_id Z using get_flow_execution_detail"

#### Legacy Workflow engine (Table API)
- "List active legacy workflows" (`query_records` on `wf_workflow` — see `docs/workflow_management.md`)
- "Show workflow version rows for workflow sys_id ..." (`query_records` on `wf_workflow_version` or related tables)

#### Update sets and captured changes
- "Activate the update set named 'STRY0080729 - Incident Email Scripts'" (`set_current_update_set` or `create_record`/`update_record` on `sys_update_set` per workflow)
- "List in-progress update sets for developer X" (`query_records` on `sys_update_set`)
- "Show captured XML rows for update set sys_id ..." (`get_changeset_details` when available, or `query_records` on `sys_update_xml`)

#### Knowledge Base Examples (Table API)
- "Create a new knowledge base for the IT department"
- "List all knowledge bases in the organization"
- "Create a category called 'Network Troubleshooting' in the IT knowledge base"
- "Write an article about VPN setup in the Network Troubleshooting category"
- "Update the VPN setup article to include mobile device instructions"
- "Publish the VPN setup article so it's visible to all users"
- "List all articles in the Network Troubleshooting category"
- "Show me the details of the VPN setup article"
- "Find knowledge articles containing 'password reset' in the IT knowledge base"
- "Create a subcategory called 'Wireless Networks' under the Network Troubleshooting category"

#### Users and groups (Table API + role tools)
- "Create user Alice in Radiology" (`create_record` on `sys_user` per blueprint)
- "List users in department Radiology" (`query_records` on `sys_user`)
- "Grant ITIL to user sys_id ..." (`grant_role_to_user`)
- "Add Bob to group sys_id ..." (`create_record` on `sys_user_grmember` per blueprint)

#### Generic Table API Examples
- "Query the sys_db_object table for all tables whose name starts with 'sys_hub'"
- "Get the record with sys_id abc123 from the cmdb_ci_server table"
- "Create a record on the x_custom_table with short_description 'Test entry'"
- "Update the record with sys_id abc123 on the problem table to set state to 4"

#### CMDB Examples
- "List all Windows server CIs in the production environment"
- "Get the details of CI with sys_id abc123"
- "Create a new Linux server CI named 'prod-web-01' in the Data Center location"
- "Update the support group on CI abc123 to 'Unix Team'"
- "Show me all upstream and downstream relationships for the payment processing server"

#### System Examples
- "Who am I authenticated as on this ServiceNow instance?" (`get_current_user`)
- "What is glide.smtp.active?" (`query_records` on `sys_properties` with `name=glide.smtp.active`)

#### UI policy and catalog client (Table API)
- "Create a UI policy on catalog item sys_id ..." (`create_record` on `sys_ui_policy` / related rows per blueprint)
- "Add a UI policy action to show and mandate business_justification" (`create_record` on `sys_ui_policy_action`)

### Example Scripts

Examples that align with the current tool surface:

- **examples/table_introspection_demo.py** - Blueprint-style discovery (verify against `tool_utils.py`; some older symbol names may differ)
- **examples/flow_designer_demo.py** - Flow Designer (`flow_tools`)
- **examples/catalog_optimization_example.py** - Catalog optimization helpers
- **examples/scripting_demo.py** - Background script and scripting-table workflows

Older scripts under `examples/` may still import removed upstream-style wrapper functions; treat them as historical unless updated.

## Authentication Methods

### Basic Authentication

```
SERVICENOW_AUTH_TYPE=basic
SERVICENOW_USERNAME=your-username
SERVICENOW_PASSWORD=your-password
```

### OAuth Authentication

```
SERVICENOW_AUTH_TYPE=oauth
SERVICENOW_CLIENT_ID=your-client-id
SERVICENOW_CLIENT_SECRET=your-client-secret
SERVICENOW_TOKEN_URL=https://your-instance.service-now.com/oauth_token.do
```

### API Key Authentication

```
SERVICENOW_AUTH_TYPE=api_key
SERVICENOW_API_KEY=your-api-key
```

## Development

### Documentation

Additional documentation is available in the `docs` directory:

- [Table introspection](docs/table_introspection.md) - `list_table_fields`, `list_table_relationships`, and `query_records` patterns for `sys_db_object` / `sys_dictionary`
- [Catalog integration](docs/catalog.md) - Service Catalog integration
- [Catalog optimization](docs/catalog_optimization_plan.md) - Catalog optimization plan
- [Change management](docs/change_management.md) - Compound approval tools plus Table API on `change_request`
- [Incident management](docs/incident_management.md) - Incidents via generic Table API (`incident` / `task`)
- [Knowledge base](docs/knowledge_base.md) - KB tables via Table API (`kb_*`)
- [User and group management](docs/user_management.md) - `sys_user`, groups, membership, and role grant tools
- [Update sets / changesets](docs/changeset_management.md) - Session tools plus Table API on `sys_update_set` / `sys_update_xml`
- [Legacy Workflow engine](docs/workflow_management.md) - `wf_*` metadata via Table API (not Flow Designer)
- [Flow Designer](docs/flow_designer.md) - `flow_tools` authoring and execution
- [Scripting](docs/scripting.md) - `run_background_script` and Script Includes via Table API

### Troubleshooting

#### Table API writes rejected or missing fields

1. **Update-set or governance rejection**  
   Writes run through `create_record` / `update_record` / `delete_record` with instance policy. Ensure the correct update set is current (`set_current_update_set` / `get_current_update_set` when those tools are in your package) and that the table is allowed for governed writes.

2. **Mandatory or derived fields**  
   Use `get_field_metadata`, `list_table_fields`, and post-write `verify_fields` (when available in your package). Follow your architecture blueprint for required columns and read-only or calculated fields.

3. **Wrong reference values**  
   Reference fields need valid `sys_id` values (or display values only if the instance and API accept them). Resolve users, groups, and CI rows with `query_records` first.

#### Change approval compound tools

- `submit_change_for_approval`, `approve_change`, and `reject_change` expect a change `sys_id` (or identifier your instance accepts). Resolve `CHG...` to `sys_id` with `query_records` on `change_request` if needed.

### Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### License

This project is licensed under the MIT License - see the LICENSE file for details.
