"""
Tests for CMDB compound tools.

Covers: get_ci_relationships, create_ci_relationship, get_ci_impact_graph.

Simple CI CRUD (list_ci, get_ci, create_ci, update_ci, search_ci) is handled
by table_tools; delete_ci_relationship and list_ci_relationship_types are CRUD
on cmdb_rel_ci / cmdb_rel_type and are also handled by table_tools.
"""

import unittest
from unittest.mock import MagicMock, patch

import requests

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.cmdb_tools import (
    CreateCIRelationshipParams,
    GetCIImpactGraphParams,
    GetCIRelationshipsParams,
    create_ci_relationship,
    get_ci_impact_graph,
    get_ci_relationships,
)
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig


class TestCMDBTools(unittest.TestCase):
    """Tests for CMDB compound tools."""

    def setUp(self):
        self.auth_config = AuthConfig(
            type=AuthType.BASIC,
            basic=BasicAuthConfig(username="test_user", password="test_password"),
        )
        self.config = ServerConfig(
            instance_url="https://test.service-now.com",
            auth=self.auth_config,
        )
        self.auth_manager = MagicMock(spec=AuthManager)
        self.auth_manager.get_headers.return_value = {"Authorization": "Bearer FAKE_TOKEN"}

    # -----------------------------------------------------------------------
    # get_ci_relationships
    # -----------------------------------------------------------------------

    @patch("servicenow_mcp.tools.cmdb_tools.requests.get")
    def test_get_ci_relationships_both_directions(self, mock_get):
        """get_ci_relationships issues child= and parent= queries for direction=both."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": [{"sys_id": "rel1"}]}
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        params = GetCIRelationshipsParams(sys_id="ci1", direction="both")
        result = get_ci_relationships(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        self.assertEqual(result["sys_id"], "ci1")
        self.assertGreaterEqual(result["relationship_count"], 1)
        self.assertEqual(mock_get.call_count, 2)  # parent + child

    @patch("servicenow_mcp.tools.cmdb_tools.requests.get")
    def test_get_ci_relationships_parent_only(self, mock_get):
        """get_ci_relationships with direction=parent issues one child= query."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": [{"sys_id": "rel2"}]}
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        params = GetCIRelationshipsParams(sys_id="ci1", direction="parent")
        result = get_ci_relationships(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        self.assertEqual(mock_get.call_count, 1)
        called_query = mock_get.call_args[1]["params"]["sysparm_query"]
        self.assertIn("child=ci1", called_query)

    @patch("servicenow_mcp.tools.cmdb_tools.requests.get")
    def test_get_ci_relationships_empty(self, mock_get):
        """get_ci_relationships returns success with zero relationships."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": []}
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        params = GetCIRelationshipsParams(sys_id="isolated_ci")
        result = get_ci_relationships(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        self.assertEqual(result["relationship_count"], 0)

    @patch("servicenow_mcp.tools.cmdb_tools.requests.get")
    def test_get_ci_relationships_type_filter(self, mock_get):
        """get_ci_relationships appends type.name filter to query."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": []}
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        params = GetCIRelationshipsParams(sys_id="ci1", relationship_type="Runs on::Runs", direction="child")
        get_ci_relationships(self.config, self.auth_manager, params)

        called_query = mock_get.call_args[1]["params"]["sysparm_query"]
        self.assertIn("type.name=Runs on::Runs", called_query)

    @patch("servicenow_mcp.tools.cmdb_tools.requests.get")
    def test_get_ci_relationships_http_error_returns_empty(self, mock_get):
        """get_ci_relationships returns success with empty list on HTTP error (graceful)."""
        mock_get.side_effect = requests.RequestException("500 error")

        params = GetCIRelationshipsParams(sys_id="ci1")
        result = get_ci_relationships(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        self.assertEqual(result["relationship_count"], 0)

    # -----------------------------------------------------------------------
    # create_ci_relationship
    # -----------------------------------------------------------------------

    @patch("servicenow_mcp.tools.cmdb_tools.requests.get")
    @patch("servicenow_mcp.tools.cmdb_tools.requests.post")
    def test_create_ci_relationship_success(self, mock_post, mock_get):
        """create_ci_relationship resolves type_name then POSTs to cmdb_rel_ci."""
        mock_type_resp = MagicMock()
        mock_type_resp.json.return_value = {
            "result": [{"sys_id": "type1", "name": "Runs on::Runs"}]
        }
        mock_type_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_type_resp

        mock_rel_resp = MagicMock()
        mock_rel_resp.json.return_value = {
            "result": {"sys_id": "rel1", "parent": "ci_parent", "child": "ci_child"}
        }
        mock_rel_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_rel_resp

        params = CreateCIRelationshipParams(
            parent_id="ci_parent",
            child_id="ci_child",
            type_name="Runs on::Runs",
        )
        result = create_ci_relationship(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        self.assertIn("rel1", result["sys_id"])
        sent_data = mock_post.call_args[1]["json"]
        self.assertEqual(sent_data["parent"], "ci_parent")
        self.assertEqual(sent_data["child"], "ci_child")
        self.assertEqual(sent_data["type"], "type1")
        called_url = mock_post.call_args[0][0]
        self.assertIn("cmdb_rel_ci", called_url)

    @patch("servicenow_mcp.tools.cmdb_tools.requests.get")
    def test_create_ci_relationship_type_not_found(self, mock_get):
        """create_ci_relationship returns error when type_name not found."""
        mock_type_resp = MagicMock()
        mock_type_resp.json.return_value = {"result": []}
        mock_type_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_type_resp

        params = CreateCIRelationshipParams(
            parent_id="ci_p", child_id="ci_c", type_name="Invalid Type"
        )
        result = create_ci_relationship(self.config, self.auth_manager, params)

        self.assertFalse(result["success"])
        self.assertIn("not found", result["error"])

    @patch("servicenow_mcp.tools.cmdb_tools.requests.get")
    def test_create_ci_relationship_type_lookup_error(self, mock_get):
        """create_ci_relationship handles type lookup HTTP errors."""
        mock_get.side_effect = requests.RequestException("500 error")
        params = CreateCIRelationshipParams(
            parent_id="ci_p", child_id="ci_c", type_name="Runs on::Runs"
        )
        result = create_ci_relationship(self.config, self.auth_manager, params)
        self.assertFalse(result["success"])
        self.assertIn("error", result)

    @patch("servicenow_mcp.tools.cmdb_tools.requests.get")
    @patch("servicenow_mcp.tools.cmdb_tools.requests.post")
    def test_create_ci_relationship_post_error(self, mock_post, mock_get):
        """create_ci_relationship handles POST HTTP errors."""
        mock_type_resp = MagicMock()
        mock_type_resp.json.return_value = {
            "result": [{"sys_id": "type1", "name": "Runs on::Runs"}]
        }
        mock_type_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_type_resp

        mock_post.side_effect = requests.RequestException("403 error")
        params = CreateCIRelationshipParams(
            parent_id="ci_p", child_id="ci_c", type_name="Runs on::Runs"
        )
        result = create_ci_relationship(self.config, self.auth_manager, params)
        self.assertFalse(result["success"])

    # -----------------------------------------------------------------------
    # get_ci_impact_graph
    # -----------------------------------------------------------------------

    @patch("servicenow_mcp.tools.cmdb_tools.requests.get")
    def test_get_ci_impact_graph_downstream(self, mock_get):
        """get_ci_impact_graph traverses downstream (parent= queries)."""
        responses = [
            MagicMock(
                **{
                    "json.return_value": {
                        "result": [
                            {
                                "sys_id": "rel1",
                                "parent": {"value": "root_ci"},
                                "child": {"value": "child_ci"},
                                "type": "t1",
                            }
                        ]
                    },
                    "raise_for_status": MagicMock(),
                }
            ),
            MagicMock(
                **{
                    "json.return_value": {"result": []},
                    "raise_for_status": MagicMock(),
                }
            ),
        ]
        mock_get.side_effect = responses

        params = GetCIImpactGraphParams(sys_id="root_ci", direction="downstream", max_depth=2)
        result = get_ci_impact_graph(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        self.assertEqual(result["root_sys_id"], "root_ci")
        self.assertGreaterEqual(result["node_count"], 2)
        self.assertEqual(result["edge_count"], 1)

    @patch("servicenow_mcp.tools.cmdb_tools.requests.get")
    def test_get_ci_impact_graph_no_relationships(self, mock_get):
        """get_ci_impact_graph returns root node only when no relationships exist."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": []}
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        params = GetCIImpactGraphParams(sys_id="isolated_ci")
        result = get_ci_impact_graph(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        self.assertEqual(result["node_count"], 1)
        self.assertEqual(result["edge_count"], 0)
        self.assertEqual(result["nodes"][0]["sys_id"], "isolated_ci")

    @patch("servicenow_mcp.tools.cmdb_tools.requests.get")
    def test_get_ci_impact_graph_max_depth_respected(self, mock_get):
        """get_ci_impact_graph stops at max_depth=1."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "result": [
                {"sys_id": "rel1", "parent": {"value": "root"}, "child": {"value": "level1"}, "type": "t1"}
            ]
        }
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        params = GetCIImpactGraphParams(sys_id="root", max_depth=1, direction="downstream")
        result = get_ci_impact_graph(self.config, self.auth_manager, params)

        self.assertEqual(mock_get.call_count, 1)
        self.assertTrue(result["success"])

    @patch("servicenow_mcp.tools.cmdb_tools.requests.get")
    def test_get_ci_impact_graph_both_directions(self, mock_get):
        """get_ci_impact_graph with direction='both' issues parent= and child= queries."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": []}
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        params = GetCIImpactGraphParams(sys_id="mid_ci", direction="both", max_depth=1)
        get_ci_impact_graph(self.config, self.auth_manager, params)

        all_queries = [
            c[1]["params"]["sysparm_query"] for c in mock_get.call_args_list
        ]
        self.assertTrue(any("parent=mid_ci" in q for q in all_queries))
        self.assertTrue(any("child=mid_ci" in q for q in all_queries))

    @patch("servicenow_mcp.tools.cmdb_tools.requests.get")
    def test_get_ci_impact_graph_http_error_graceful(self, mock_get):
        """get_ci_impact_graph continues gracefully on HTTP errors during traversal."""
        mock_get.side_effect = requests.RequestException("timeout")

        params = GetCIImpactGraphParams(sys_id="root_ci", max_depth=1)
        result = get_ci_impact_graph(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        self.assertEqual(result["node_count"], 1)

    @patch("servicenow_mcp.tools.cmdb_tools.requests.get")
    def test_get_ci_impact_graph_returns_structure(self, mock_get):
        """get_ci_impact_graph result contains expected top-level keys."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": []}
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        result = get_ci_impact_graph(
            self.config, self.auth_manager,
            GetCIImpactGraphParams(sys_id="ci1", max_depth=2)
        )

        for key in ["success", "root_sys_id", "direction", "max_depth", "node_count", "edge_count", "nodes", "edges"]:
            self.assertIn(key, result, f"Missing key: {key}")


if __name__ == "__main__":
    unittest.main()
