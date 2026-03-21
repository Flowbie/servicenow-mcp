# tests/integration/test_customization.py
"""
Integration tests for customization tools against a live ServiceNow instance.
READ-ONLY — list operations only, table-scoped to 'incident'.
Run with: SN_INTEGRATION_TESTS=1 pytest tests/integration/test_customization.py -v -s
"""
import pytest

from servicenow_mcp.tools.customization_tools import (
    list_business_rules,
    list_ui_policies,
    list_client_scripts,
    list_notifications,
    list_ui_actions,
    list_access_controls,
    ListBusinessRulesParams,
    ListUIPoliciesParams,
    ListClientScriptsParams,
    ListNotificationsParams,
    ListUIActionsParams,
    ListAccessControlsParams,
)


@pytest.mark.integration
class TestCustomizationIntegration:

    def test_list_business_rules_returns_results(self, live_config, live_auth):
        params = ListBusinessRulesParams(table="incident")
        result = list_business_rules(live_config, live_auth, params)
        print("\n--- list_business_rules response ---")
        print(result.model_dump())
        assert result.fetch_error is None, f"Expected no fetch error, got: {result.fetch_error}"
        assert isinstance(result.rules, list)

    def test_list_business_rules_item_shape(self, live_config, live_auth):
        params = ListBusinessRulesParams(table="incident")
        result = list_business_rules(live_config, live_auth, params)
        assert result.fetch_error is None
        if not result.rules:
            pytest.skip("No business rules found for incident table.")
        first = result.rules[0]
        print("\n--- first business rule ---")
        print(first)
        assert hasattr(first, "sys_id"), "Missing sys_id on business rule item"
        assert hasattr(first, "name"), "Missing name on business rule item"

    def test_list_business_rules_include_inactive(self, live_config, live_auth):
        active_params = ListBusinessRulesParams(table="incident", include_inactive=False)
        all_params = ListBusinessRulesParams(table="incident", include_inactive=True)
        active_result = list_business_rules(live_config, live_auth, active_params)
        all_result = list_business_rules(live_config, live_auth, all_params)
        print("\n--- active only total ---", active_result.total)
        print("--- all (include_inactive) total ---", all_result.total)
        assert all_result.fetch_error is None
        assert all_result.total >= active_result.total

    def test_list_ui_policies_returns_results(self, live_config, live_auth):
        params = ListUIPoliciesParams(table="incident")
        result = list_ui_policies(live_config, live_auth, params)
        print("\n--- list_ui_policies response ---")
        print(result.model_dump())
        assert result.fetch_error is None, f"Expected no fetch error, got: {result.fetch_error}"
        assert isinstance(result.policies, list)

    def test_list_ui_policies_api_relevant_flag(self, live_config, live_auth):
        params = ListUIPoliciesParams(table="incident")
        result = list_ui_policies(live_config, live_auth, params)
        assert result.fetch_error is None
        assert result.api_relevant is False

    def test_list_client_scripts_returns_results(self, live_config, live_auth):
        params = ListClientScriptsParams(table="incident")
        result = list_client_scripts(live_config, live_auth, params)
        print("\n--- list_client_scripts response ---")
        print(result.model_dump())
        assert result.fetch_error is None, f"Expected no fetch error, got: {result.fetch_error}"
        assert isinstance(result.scripts, list)

    def test_list_client_scripts_include_inactive(self, live_config, live_auth):
        params = ListClientScriptsParams(table="incident", include_inactive=True)
        result = list_client_scripts(live_config, live_auth, params)
        print("\n--- list_client_scripts (include_inactive) response ---")
        print(result.model_dump())
        assert result.fetch_error is None

    def test_list_notifications_returns_results(self, live_config, live_auth):
        params = ListNotificationsParams(table="incident")
        result = list_notifications(live_config, live_auth, params)
        print("\n--- list_notifications response ---")
        print(result.model_dump())
        assert result.fetch_error is None, f"Expected no fetch error, got: {result.fetch_error}"
        assert isinstance(result.notifications, list)

    def test_list_ui_actions_returns_results(self, live_config, live_auth):
        params = ListUIActionsParams(table="incident")
        result = list_ui_actions(live_config, live_auth, params)
        print("\n--- list_ui_actions response ---")
        print(result.model_dump())
        assert result.fetch_error is None, f"Expected no fetch error, got: {result.fetch_error}"
        assert isinstance(result.ui_actions, list)

    def test_list_access_controls_returns_results(self, live_config, live_auth):
        params = ListAccessControlsParams(table="incident")
        result = list_access_controls(live_config, live_auth, params)
        print("\n--- list_access_controls response ---")
        print(result.model_dump())
        assert result.fetch_error is None, f"Expected no fetch error, got: {result.fetch_error}"
        assert isinstance(result.acls, list)

    def test_list_access_controls_total_is_int(self, live_config, live_auth):
        params = ListAccessControlsParams(table="incident")
        result = list_access_controls(live_config, live_auth, params)
        assert result.fetch_error is None
        assert isinstance(result.total, int)
        assert result.total >= 0
