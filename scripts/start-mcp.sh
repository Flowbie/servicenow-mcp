#!/bin/bash
# Wrapper to start the ServiceNow MCP server from its own directory
# so that load_dotenv() finds the .env file at the expected path.
cd "$(dirname "$0")/.." || exit 1
exec .venv/bin/python -m servicenow_mcp.cli "$@"
