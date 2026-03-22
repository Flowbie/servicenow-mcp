"""
Tests for the ServiceNow MCP server workflow management integration.
"""

import unittest

from servicenow_mcp.utils.tool_utils import get_tool_definitions

WORKFLOW_TOOLS = [
    "list_workflows",
    "get_workflow_details",
    "list_workflow_versions",
    "get_workflow_activities",
    "create_workflow",
    "update_workflow",
    "activate_workflow",
    "deactivate_workflow",
    "add_workflow_activity",
    "update_workflow_activity",
    "delete_workflow_activity",
    "reorder_workflow_activities",
]


class TestServerWorkflow(unittest.TestCase):
    """Tests that workflow tools are registered in get_tool_definitions."""

    def setUp(self):
        self.tool_definitions = get_tool_definitions()

    def test_register_workflow_tools(self):
        """All expected workflow tools must be present in tool_definitions."""
        tool_names = set(self.tool_definitions.keys())
        for tool in WORKFLOW_TOOLS:
            self.assertIn(tool, tool_names, f"Expected workflow tool '{tool}' to be registered")

    def test_workflow_tool_count(self):
        """At least 12 workflow tools must be registered."""
        registered = [t for t in WORKFLOW_TOOLS if t in self.tool_definitions]
        self.assertGreaterEqual(len(registered), 12,
                                f"Expected >= 12 workflow tools, found {len(registered)}")


if __name__ == "__main__":
    unittest.main()
