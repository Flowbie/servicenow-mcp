# tests/integration/test_flows.py
"""
Integration tests for Flow Designer tools against a live ServiceNow instance.
Run with: SN_INTEGRATION_TESTS=1 pytest tests/integration/test_flows.py -v -s
"""
import json
import pytest

from servicenow_mcp.tools.flow_tools import (
    list_flows,
    get_flow,
    get_flow_triggers,
    get_flow_actions,
    get_flow_version,
    list_trigger_types,
    list_subflows,
    list_actions,
    ListFlowsParams,
    GetFlowParams,
    GetFlowTriggersParams,
    GetFlowActionsParams,
    GetFlowVersionParams,
    ListTriggerTypesParams,
    ListSubflowsParams,
    ListActionsParams,
)


@pytest.mark.integration
class TestFlowIntegration:

    def test_list_flows_returns_results(self, live_config, live_auth):
        """Verify list_flows connects and returns records."""
        params = ListFlowsParams(limit=5)
        result = list_flows(live_config, live_auth, params)

        print("\n--- list_flows response ---")
        print(json.dumps(result, indent=2, default=str))

        assert result["success"] is True, f"Expected success, got: {result.get('message')}"
        assert "flows" in result
        assert isinstance(result["flows"], list)

    def test_list_flows_shape(self, live_config, live_auth):
        """Verify each flow record has the expected key fields."""
        params = ListFlowsParams(limit=3)
        result = list_flows(live_config, live_auth, params)

        assert result["success"] is True
        flows = result["flows"]

        if not flows:
            pytest.skip("No flows found on this instance — cannot verify shape.")

        first = flows[0]
        print("\n--- first flow fields ---")
        print(json.dumps(first, indent=2, default=str))

        assert "sys_id" in first, "Missing expected field: sys_id"
        assert "name" in first, "Missing expected field: name"

    def test_list_flows_limit_respected(self, live_config, live_auth):
        """Verify the limit parameter is respected."""
        params = ListFlowsParams(limit=2)
        result = list_flows(live_config, live_auth, params)

        assert result["success"] is True
        assert len(result["flows"]) <= 2

    def test_get_flow_by_sys_id(self, live_config, live_auth):
        """Verify get_flow returns a real flow by sys_id."""
        list_result = list_flows(live_config, live_auth, ListFlowsParams(limit=1))
        assert list_result["success"] is True

        if not list_result["flows"]:
            pytest.skip("No flows on this instance to look up.")

        sys_id = list_result["flows"][0]["sys_id"]

        params = GetFlowParams(flow_sys_id=sys_id)
        result = get_flow(live_config, live_auth, params)

        print(f"\n--- get_flow({sys_id}) response ---")
        print(json.dumps(result, indent=2, default=str))

        assert result["success"] is True, f"Expected success, got: {result.get('message')}"
        assert "flow" in result

    def test_get_flow_triggers(self, live_config, live_auth):
        """Verify get_flow_triggers returns trigger data for a known flow."""
        list_result = list_flows(live_config, live_auth, ListFlowsParams(limit=1))
        assert list_result["success"] is True

        if not list_result["flows"]:
            pytest.skip("No flows on this instance to inspect triggers.")

        sys_id = list_result["flows"][0]["sys_id"]

        params = GetFlowTriggersParams(flow_sys_id=sys_id)
        result = get_flow_triggers(live_config, live_auth, params)

        print(f"\n--- get_flow_triggers({sys_id}) response ---")
        print(json.dumps(result, indent=2, default=str))

        assert result["success"] is True, f"Expected success, got: {result.get('message')}"
        assert "triggers" in result

    def test_get_flow_actions(self, live_config, live_auth):
        """Verify get_flow_actions returns action data for a known flow."""
        list_result = list_flows(live_config, live_auth, ListFlowsParams(limit=1))
        assert list_result["success"] is True

        if not list_result["flows"]:
            pytest.skip("No flows on this instance to inspect actions.")

        sys_id = list_result["flows"][0]["sys_id"]

        params = GetFlowActionsParams(flow_sys_id=sys_id)
        result = get_flow_actions(live_config, live_auth, params)

        print(f"\n--- get_flow_actions({sys_id}) response ---")
        print(json.dumps(result, indent=2, default=str))

        assert result["success"] is True, f"Expected success, got: {result.get('message')}"
        assert "actions" in result

    def test_get_flow_version(self, live_config, live_auth):
        """
        Verify get_flow_version handles both success and no-version-found responses.
        Not all flows have a published version, so both outcomes are acceptable.
        """
        list_result = list_flows(live_config, live_auth, ListFlowsParams(limit=1))
        assert list_result["success"] is True

        if not list_result["flows"]:
            pytest.skip("No flows on this instance to check versions.")

        sys_id = list_result["flows"][0]["sys_id"]

        params = GetFlowVersionParams(flow_sys_id=sys_id)
        result = get_flow_version(live_config, live_auth, params)

        print(f"\n--- get_flow_version({sys_id}) response ---")
        print(json.dumps(result, indent=2, default=str))

        # Both outcomes are acceptable: version found or no version exists
        if result["success"] is True:
            assert "version" in result
        else:
            assert "message" in result
            # Accept the known no-version message pattern
            assert "version" in result.get("message", "").lower() or "No" in result.get("message", "")

    def test_list_trigger_types(self, live_config, live_auth):
        """Verify list_trigger_types returns a Pydantic model with trigger_types list."""
        params = ListTriggerTypesParams()
        result = list_trigger_types(live_config, live_auth, params)

        print("\n--- list_trigger_types response ---")
        # result is a Pydantic model, not a dict
        print(result.model_dump_json(indent=2))

        assert hasattr(result, "trigger_types"), "Result missing 'trigger_types' attribute"
        assert isinstance(result.trigger_types, list)

    def test_list_subflows_returns_results(self, live_config, live_auth):
        """Verify list_subflows returns a Pydantic model with artifacts list."""
        params = ListSubflowsParams(limit=5)
        result = list_subflows(live_config, live_auth, params)

        print("\n--- list_subflows response ---")
        print(result.model_dump_json(indent=2))

        assert hasattr(result, "artifacts"), "Result missing 'artifacts' attribute"
        assert isinstance(result.artifacts, list)

    def test_list_actions_returns_results(self, live_config, live_auth):
        """Verify list_actions returns a Pydantic model with artifacts list."""
        params = ListActionsParams(limit=5)
        result = list_actions(live_config, live_auth, params)

        print("\n--- list_actions response ---")
        print(result.model_dump_json(indent=2))

        assert hasattr(result, "artifacts"), "Result missing 'artifacts' attribute"
        assert isinstance(result.artifacts, list)
