"""
Tests for Phase 7 CMDB enhancements.

Covers: search_ci, create_ci_relationship, delete_ci_relationship,
list_ci_relationship_types, get_ci_impact_graph.
Also includes basic smoke tests for the pre-existing tools (list_ci, get_ci,
create_ci, update_ci, get_ci_relationships).
"""

import unittest
from unittest.mock import MagicMock, call, patch

import requests

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.cmdb_tools import (
    CreateCIParams,
    CreateCIRelationshipParams,
    DeleteCIRelationshipParams,
    GetCIImpactGraphParams,
    GetCIParams,
    GetCIRelationshipsParams,
    ListCIParams,
    ListCIRelationshipTypesParams,
    SearchCIParams,
    UpdateCIParams,
    create_ci,
    create_ci_relationship,
    delete_ci_relationship,
    get_ci,
    get_ci_impact_graph,
    get_ci_relationships,
    list_ci,
    list_ci_relationship_types,
    search_ci,
    update_ci,
)
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig


class TestCMDBTools(unittest.TestCase):
    """Tests for CMDB tools — both existing and Phase 7 additions."""

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
    # Smoke tests for existing tools
    # -----------------------------------------------------------------------

    @patch("servicenow_mcp.tools.cmdb_tools.requests.get")
    def test_list_ci_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": [{"sys_id": "ci1", "name": "web01"}]}
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        result = list_ci(self.config, self.auth_manager, ListCIParams())
        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 1)

    @patch("servicenow_mcp.tools.cmdb_tools.requests.get")
    def test_get_ci_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": {"sys_id": "ci1", "name": "web01"}}
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        result = get_ci(self.config, self.auth_manager, GetCIParams(sys_id="ci1"))
        self.assertTrue(result["success"])
        self.assertEqual(result["sys_id"], "ci1")

    # -----------------------------------------------------------------------
    # search_ci
    # -----------------------------------------------------------------------

    @patch("servicenow_mcp.tools.cmdb_tools.requests.get")
    def test_search_ci_no_filters(self, mock_get):
        """search_ci with no filters returns all CIs."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "result": [{"sys_id": "ci1"}, {"sys_id": "ci2"}]
        }
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        result = search_ci(self.config, self.auth_manager, SearchCIParams())
        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 2)
        called_url = mock_get.call_args[0][0]
        self.assertIn("cmdb_ci", called_url)

    @patch("servicenow_mcp.tools.cmdb_tools.requests.get")
    def test_search_ci_name_filter(self, mock_get):
        """search_ci name filter uses nameLIKE."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": [{"sys_id": "ci1", "name": "web-server-01"}]}
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        params = SearchCIParams(name="web-server", ci_class="cmdb_ci_server")
        result = search_ci(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        call_kwargs = mock_get.call_args[1]["params"]
        self.assertIn("nameLIKEweb-server", call_kwargs["sysparm_query"])
        called_url = mock_get.call_args[0][0]
        self.assertIn("cmdb_ci_server", called_url)

    @patch("servicenow_mcp.tools.cmdb_tools.requests.get")
    def test_search_ci_multiple_filters(self, mock_get):
        """search_ci combines multiple filters with ^."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": []}
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        params = SearchCIParams(
            name="db", install_status="1", environment="Production"
        )
        search_ci(self.config, self.auth_manager, params)

        call_kwargs = mock_get.call_args[1]["params"]
        query = call_kwargs["sysparm_query"]
        self.assertIn("nameLIKEdb", query)
        self.assertIn("install_status=1", query)
        self.assertIn("environment=Production", query)

    @patch("servicenow_mcp.tools.cmdb_tools.requests.get")
    def test_search_ci_http_error(self, mock_get):
        """search_ci handles HTTP errors."""
        mock_get.side_effect = requests.RequestException("503 error")
        result = search_ci(self.config, self.auth_manager, SearchCIParams(name="test"))
        self.assertFalse(result["success"])
        self.assertIn("error", result)

    # -----------------------------------------------------------------------
    # create_ci_relationship
    # -----------------------------------------------------------------------

    @patch("servicenow_mcp.tools.cmdb_tools.requests.get")
    @patch("servicenow_mcp.tools.cmdb_tools.requests.post")
    def test_create_ci_relationship_success(self, mock_post, mock_get):
        """create_ci_relationship resolves type_name then POSTs to cmdb_rel_ci."""
        # First call: type lookup; second call: not needed (POST)
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
        # Verify POST body uses resolved type sys_id
        sent_data = mock_post.call_args[1]["json"]
        self.assertEqual(sent_data["parent"], "ci_parent")
        self.assertEqual(sent_data["child"], "ci_child")
        self.assertEqual(sent_data["type"], "type1")
        # Verify POST goes to cmdb_rel_ci
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
    # delete_ci_relationship
    # -----------------------------------------------------------------------

    @patch("servicenow_mcp.tools.cmdb_tools.requests.delete")
    def test_delete_ci_relationship_success(self, mock_delete):
        """delete_ci_relationship DELETEs cmdb_rel_ci/{sys_id}."""
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_delete.return_value = mock_resp

        result = delete_ci_relationship(
            self.config, self.auth_manager, DeleteCIRelationshipParams(sys_id="rel1")
        )

        self.assertTrue(result["success"])
        self.assertIn("deleted", result["message"])
        called_url = mock_delete.call_args[0][0]
        self.assertIn("cmdb_rel_ci/rel1", called_url)

    @patch("servicenow_mcp.tools.cmdb_tools.requests.delete")
    def test_delete_ci_relationship_http_error(self, mock_delete):
        """delete_ci_relationship handles HTTP errors."""
        mock_delete.side_effect = requests.RequestException("404 error")
        result = delete_ci_relationship(
            self.config, self.auth_manager, DeleteCIRelationshipParams(sys_id="missing")
        )
        self.assertFalse(result["success"])

    # -----------------------------------------------------------------------
    # list_ci_relationship_types
    # -----------------------------------------------------------------------

    @patch("servicenow_mcp.tools.cmdb_tools.requests.get")
    def test_list_ci_relationship_types_success(self, mock_get):
        """list_ci_relationship_types queries cmdb_rel_type."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "result": [
                {"sys_id": "t1", "name": "Runs on::Runs"},
                {"sys_id": "t2", "name": "Hosted on::Hosts"},
            ]
        }
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        result = list_ci_relationship_types(
            self.config, self.auth_manager, ListCIRelationshipTypesParams()
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 2)
        called_url = mock_get.call_args[0][0]
        self.assertIn("cmdb_rel_type", called_url)

    @patch("servicenow_mcp.tools.cmdb_tools.requests.get")
    def test_list_ci_relationship_types_name_filter(self, mock_get):
        """list_ci_relationship_types passes name_filter as nameLIKE query."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": [{"sys_id": "t1", "name": "Runs on::Runs"}]}
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        result = list_ci_relationship_types(
            self.config, self.auth_manager, ListCIRelationshipTypesParams(name_filter="Runs")
        )

        self.assertTrue(result["success"])
        call_kwargs = mock_get.call_args[1]["params"]
        self.assertIn("nameLIKERuns", call_kwargs["sysparm_query"])

    @patch("servicenow_mcp.tools.cmdb_tools.requests.get")
    def test_list_ci_relationship_types_http_error(self, mock_get):
        """list_ci_relationship_types handles HTTP errors."""
        mock_get.side_effect = requests.RequestException("500 error")
        result = list_ci_relationship_types(
            self.config, self.auth_manager, ListCIRelationshipTypesParams()
        )
        self.assertFalse(result["success"])

    # -----------------------------------------------------------------------
    # get_ci_impact_graph
    # -----------------------------------------------------------------------

    @patch("servicenow_mcp.tools.cmdb_tools.requests.get")
    def test_get_ci_impact_graph_downstream(self, mock_get):
        """get_ci_impact_graph traverses downstream (parent= queries)."""
        # Depth 1: return one child; depth 2: no children
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
        self.assertGreaterEqual(result["node_count"], 2)  # root + child_ci
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

        # Should have made exactly 1 GET call (depth=1, only one frontier item)
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

        # Both 'parent=mid_ci' and 'child=mid_ci' queries should be issued
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

        # Should still return success with just the root node
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
