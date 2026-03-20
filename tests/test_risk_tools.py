"""
Tests for Phase 9 GRC Risk tools.

Covers: list_risks, get_risk, create_risk, update_risk_state,
list_risk_criteria, assign_risk_response.
"""

import unittest
from unittest.mock import MagicMock, patch

import requests

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.risk_tools import (
    AssignRiskResponseParams,
    CreateRiskParams,
    GetRiskParams,
    ListRiskCriteriaParams,
    ListRisksParams,
    UpdateRiskStateParams,
    assign_risk_response,
    create_risk,
    get_risk,
    list_risk_criteria,
    list_risks,
    update_risk_state,
)
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig


class TestRiskTools(unittest.TestCase):
    """Tests for Phase 9 GRC Risk tools."""

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
    # list_risks
    # -----------------------------------------------------------------------

    @patch("servicenow_mcp.tools.risk_tools.requests.get")
    def test_list_risks_no_filters(self, mock_get):
        """list_risks with no filters returns all risks."""
        mock_get.return_value = MagicMock(**{
            "json.return_value": {
                "result": [
                    {"sys_id": "r1", "name": "Data Breach", "state": "assess"},
                    {"sys_id": "r2", "name": "System Outage", "state": "draft"},
                ]
            },
            "raise_for_status": MagicMock(),
        })

        result = list_risks(self.config, self.auth_manager, ListRisksParams())

        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 2)
        called_url = mock_get.call_args[0][0]
        self.assertIn("sn_risk_risk", called_url)

    @patch("servicenow_mcp.tools.risk_tools.requests.get")
    def test_list_risks_state_filter(self, mock_get):
        """list_risks passes state filter in sysparm_query."""
        mock_get.return_value = MagicMock(**{
            "json.return_value": {"result": [{"sys_id": "r1"}]},
            "raise_for_status": MagicMock(),
        })

        list_risks(self.config, self.auth_manager, ListRisksParams(state="assess"))

        query = mock_get.call_args[1]["params"]["sysparm_query"]
        self.assertIn("state=assess", query)

    @patch("servicenow_mcp.tools.risk_tools.requests.get")
    def test_list_risks_framework_filter(self, mock_get):
        """list_risks passes framework filter using LIKE."""
        mock_get.return_value = MagicMock(**{
            "json.return_value": {"result": []},
            "raise_for_status": MagicMock(),
        })

        list_risks(self.config, self.auth_manager, ListRisksParams(framework="ISO 27001"))

        query = mock_get.call_args[1]["params"]["sysparm_query"]
        self.assertIn("frameworkLIKEISO 27001", query)

    @patch("servicenow_mcp.tools.risk_tools.requests.get")
    def test_list_risks_http_error(self, mock_get):
        """list_risks handles HTTP errors."""
        mock_get.side_effect = requests.RequestException("500 error")
        result = list_risks(self.config, self.auth_manager, ListRisksParams())
        self.assertFalse(result["success"])

    # -----------------------------------------------------------------------
    # get_risk
    # -----------------------------------------------------------------------

    @patch("servicenow_mcp.tools.risk_tools.requests.get")
    def test_get_risk_success(self, mock_get):
        """get_risk retrieves a single risk by sys_id with display values."""
        mock_get.return_value = MagicMock(**{
            "json.return_value": {
                "result": {
                    "sys_id": "r1",
                    "name": "Data Breach",
                    "state": "assess",
                    "likelihood": {"display_value": "High"},
                }
            },
            "raise_for_status": MagicMock(),
        })

        result = get_risk(self.config, self.auth_manager, GetRiskParams(sys_id="r1"))

        self.assertTrue(result["success"])
        self.assertEqual(result["sys_id"], "r1")
        self.assertIn("risk", result)
        called_url = mock_get.call_args[0][0]
        self.assertIn("sn_risk_risk/r1", called_url)
        # Verify display values requested
        q_params = mock_get.call_args[1]["params"]
        self.assertEqual(q_params["sysparm_display_value"], "true")

    @patch("servicenow_mcp.tools.risk_tools.requests.get")
    def test_get_risk_http_error(self, mock_get):
        """get_risk handles HTTP errors."""
        mock_get.side_effect = requests.RequestException("404 error")
        result = get_risk(self.config, self.auth_manager, GetRiskParams(sys_id="missing"))
        self.assertFalse(result["success"])

    # -----------------------------------------------------------------------
    # create_risk
    # -----------------------------------------------------------------------

    @patch("servicenow_mcp.tools.risk_tools.requests.post")
    def test_create_risk_success(self, mock_post):
        """create_risk POSTs to sn_risk_risk and returns sys_id."""
        mock_post.return_value = MagicMock(**{
            "json.return_value": {"result": {"sys_id": "r_new", "name": "New Risk"}},
            "raise_for_status": MagicMock(),
        })

        params = CreateRiskParams(
            name="New Risk",
            description="A test risk",
            state="draft",
            likelihood="crit_likelihood_1",
        )
        result = create_risk(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        self.assertEqual(result["sys_id"], "r_new")
        sent_data = mock_post.call_args[1]["json"]
        self.assertEqual(sent_data["name"], "New Risk")
        self.assertEqual(sent_data["state"], "draft")
        self.assertEqual(sent_data["likelihood"], "crit_likelihood_1")
        called_url = mock_post.call_args[0][0]
        self.assertIn("sn_risk_risk", called_url)

    @patch("servicenow_mcp.tools.risk_tools.requests.post")
    def test_create_risk_minimal(self, mock_post):
        """create_risk works with only required field (name)."""
        mock_post.return_value = MagicMock(**{
            "json.return_value": {"result": {"sys_id": "r2"}},
            "raise_for_status": MagicMock(),
        })

        result = create_risk(self.config, self.auth_manager, CreateRiskParams(name="Min Risk"))
        self.assertTrue(result["success"])

    @patch("servicenow_mcp.tools.risk_tools.requests.post")
    def test_create_risk_http_error(self, mock_post):
        """create_risk handles HTTP errors."""
        mock_post.side_effect = requests.RequestException("403 error")
        result = create_risk(self.config, self.auth_manager, CreateRiskParams(name="Fail Risk"))
        self.assertFalse(result["success"])

    # -----------------------------------------------------------------------
    # update_risk_state
    # -----------------------------------------------------------------------

    @patch("servicenow_mcp.tools.risk_tools.requests.patch")
    def test_update_risk_state_success(self, mock_patch):
        """update_risk_state PATCHes state as string label."""
        mock_patch.return_value = MagicMock(**{
            "json.return_value": {"result": {"sys_id": "r1", "state": "assess"}},
            "raise_for_status": MagicMock(),
        })

        result = update_risk_state(
            self.config, self.auth_manager,
            UpdateRiskStateParams(sys_id="r1", state="assess")
        )

        self.assertTrue(result["success"])
        sent_data = mock_patch.call_args[1]["json"]
        self.assertEqual(sent_data["state"], "assess")
        called_url = mock_patch.call_args[0][0]
        self.assertIn("sn_risk_risk/r1", called_url)

    def test_update_risk_state_invalid(self):
        """update_risk_state rejects invalid state values."""
        result = update_risk_state(
            self.config, self.auth_manager,
            UpdateRiskStateParams(sys_id="r1", state="3")  # numeric not valid
        )
        self.assertFalse(result["success"])
        self.assertIn("Invalid state", result["message"])

    @patch("servicenow_mcp.tools.risk_tools.requests.patch")
    def test_update_risk_state_all_valid_states(self, mock_patch):
        """update_risk_state accepts all 6 valid state values."""
        mock_patch.return_value = MagicMock(**{
            "json.return_value": {"result": {"sys_id": "r1"}},
            "raise_for_status": MagicMock(),
        })
        for state in ["draft", "assess", "respond", "monitor", "review", "retired"]:
            result = update_risk_state(
                self.config, self.auth_manager,
                UpdateRiskStateParams(sys_id="r1", state=state)
            )
            self.assertTrue(result["success"], f"State '{state}' should be valid")

    @patch("servicenow_mcp.tools.risk_tools.requests.patch")
    def test_update_risk_state_http_error(self, mock_patch):
        """update_risk_state handles HTTP errors."""
        mock_patch.side_effect = requests.RequestException("500 error")
        result = update_risk_state(
            self.config, self.auth_manager,
            UpdateRiskStateParams(sys_id="r1", state="assess")
        )
        self.assertFalse(result["success"])

    # -----------------------------------------------------------------------
    # list_risk_criteria
    # -----------------------------------------------------------------------

    @patch("servicenow_mcp.tools.risk_tools.requests.get")
    def test_list_risk_criteria_success(self, mock_get):
        """list_risk_criteria queries sn_risk_criteria."""
        mock_get.return_value = MagicMock(**{
            "json.return_value": {
                "result": [
                    {"sys_id": "c1", "label": "High", "type": "likelihood"},
                    {"sys_id": "c2", "label": "Medium", "type": "likelihood"},
                ]
            },
            "raise_for_status": MagicMock(),
        })

        result = list_risk_criteria(
            self.config, self.auth_manager, ListRiskCriteriaParams()
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 2)
        called_url = mock_get.call_args[0][0]
        self.assertIn("sn_risk_criteria", called_url)

    @patch("servicenow_mcp.tools.risk_tools.requests.get")
    def test_list_risk_criteria_label_filter(self, mock_get):
        """list_risk_criteria label filter uses labelLIKE."""
        mock_get.return_value = MagicMock(**{
            "json.return_value": {"result": [{"sys_id": "c1", "label": "High"}]},
            "raise_for_status": MagicMock(),
        })

        list_risk_criteria(
            self.config, self.auth_manager, ListRiskCriteriaParams(label="High")
        )

        query = mock_get.call_args[1]["params"]["sysparm_query"]
        self.assertIn("labelLIKEHigh", query)

    @patch("servicenow_mcp.tools.risk_tools.requests.get")
    def test_list_risk_criteria_type_filter(self, mock_get):
        """list_risk_criteria type filter uses type= query."""
        mock_get.return_value = MagicMock(**{
            "json.return_value": {"result": []},
            "raise_for_status": MagicMock(),
        })

        list_risk_criteria(
            self.config, self.auth_manager,
            ListRiskCriteriaParams(criteria_type="likelihood")
        )

        query = mock_get.call_args[1]["params"]["sysparm_query"]
        self.assertIn("type=likelihood", query)

    @patch("servicenow_mcp.tools.risk_tools.requests.get")
    def test_list_risk_criteria_http_error(self, mock_get):
        """list_risk_criteria handles HTTP errors."""
        mock_get.side_effect = requests.RequestException("500 error")
        result = list_risk_criteria(
            self.config, self.auth_manager, ListRiskCriteriaParams()
        )
        self.assertFalse(result["success"])

    # -----------------------------------------------------------------------
    # assign_risk_response
    # -----------------------------------------------------------------------

    @patch("servicenow_mcp.tools.risk_tools.requests.patch")
    def test_assign_risk_response_success(self, mock_patch):
        """assign_risk_response PATCHes treatment field as string label."""
        mock_patch.return_value = MagicMock(**{
            "json.return_value": {"result": {"sys_id": "r1", "treatment": "Mitigate"}},
            "raise_for_status": MagicMock(),
        })

        result = assign_risk_response(
            self.config, self.auth_manager,
            AssignRiskResponseParams(sys_id="r1", response="Mitigate")
        )

        self.assertTrue(result["success"])
        sent_data = mock_patch.call_args[1]["json"]
        self.assertEqual(sent_data["treatment"], "Mitigate")
        called_url = mock_patch.call_args[0][0]
        self.assertIn("sn_risk_risk/r1", called_url)

    @patch("servicenow_mcp.tools.risk_tools.requests.patch")
    def test_assign_risk_response_all_valid_values(self, mock_patch):
        """assign_risk_response accepts all 4 valid response values."""
        mock_patch.return_value = MagicMock(**{
            "json.return_value": {"result": {"sys_id": "r1"}},
            "raise_for_status": MagicMock(),
        })
        for resp in ["Accept", "Avoid", "Mitigate", "Transfer"]:
            result = assign_risk_response(
                self.config, self.auth_manager,
                AssignRiskResponseParams(sys_id="r1", response=resp)
            )
            self.assertTrue(result["success"], f"Response '{resp}' should be valid")

    def test_assign_risk_response_invalid(self):
        """assign_risk_response rejects invalid response values."""
        result = assign_risk_response(
            self.config, self.auth_manager,
            AssignRiskResponseParams(sys_id="r1", response="1")  # numeric not valid
        )
        self.assertFalse(result["success"])
        self.assertIn("Invalid response", result["message"])

    @patch("servicenow_mcp.tools.risk_tools.requests.patch")
    def test_assign_risk_response_http_error(self, mock_patch):
        """assign_risk_response handles HTTP errors."""
        mock_patch.side_effect = requests.RequestException("500 error")
        result = assign_risk_response(
            self.config, self.auth_manager,
            AssignRiskResponseParams(sys_id="r1", response="Accept")
        )
        self.assertFalse(result["success"])


    def test_create_risk_invalid_state_rejected(self):
        """create_risk rejects state values outside the valid set."""
        params = CreateRiskParams(name="Test Risk", state="5")
        result = create_risk(self.config, self.auth_manager, params)
        self.assertFalse(result["success"])
        self.assertIn("Invalid state", result["message"])

    @patch("servicenow_mcp.tools.risk_tools.requests.post")
    def test_create_risk_valid_states_accepted(self, mock_post):
        """create_risk accepts all 6 valid state values without validation error."""
        mock_post.return_value = MagicMock(**{
            "json.return_value": {"result": {"sys_id": "r1"}},
            "raise_for_status": MagicMock(),
        })
        for state in ["draft", "assess", "respond", "monitor", "review", "retired"]:
            params = CreateRiskParams(name="Test Risk", state=state)
            result = create_risk(self.config, self.auth_manager, params)
            self.assertTrue(result["success"], f"state='{state}' should be accepted")


if __name__ == "__main__":
    unittest.main()
