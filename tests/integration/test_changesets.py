# tests/integration/test_changesets.py
"""
Integration tests for changeset (update set) tools against a live ServiceNow instance.
READ-ONLY — list and get operations only.
commit_changeset and publish_changeset are excluded (write operations).
Run with: SN_INTEGRATION_TESTS=1 pytest tests/integration/test_changesets.py -v -s
"""
import json
import pytest

from servicenow_mcp.tools.changeset_tools import (
    list_changesets,
    get_changeset_details,
    ListChangesetsParams,
    GetChangesetDetailsParams,
)


def _extract_sys_id(field_value) -> str:
    """
    ServiceNow raw records may return sys_id as a plain string or as a
    dict with 'value' / 'display_value' keys. Handle both defensively.
    """
    if isinstance(field_value, dict):
        return field_value.get("value") or field_value.get("display_value", "")
    return str(field_value)


@pytest.mark.integration
class TestChangesetIntegration:

    def test_list_changesets_returns_results(self, live_config, live_auth):
        params = ListChangesetsParams(limit=5)
        result = list_changesets(live_auth, live_config, params)
        print("\n--- list_changesets response ---")
        print(json.dumps(result, indent=2, default=str))
        assert result["success"] is True, f"Expected success, got: {result.get('message')}"
        assert "changesets" in result
        assert isinstance(result["changesets"], list)

    def test_list_changesets_shape(self, live_config, live_auth):
        params = ListChangesetsParams(limit=5)
        result = list_changesets(live_auth, live_config, params)
        assert result["success"] is True
        changesets = result["changesets"]
        if not changesets:
            pytest.skip("No changesets found on this instance.")
        first = changesets[0]
        print("\n--- first changeset fields ---")
        print(json.dumps(first, indent=2, default=str))
        for field in ["sys_id", "name"]:
            assert field in first, f"Missing expected field: {field}"

    def test_get_changeset_details_by_sys_id(self, live_config, live_auth):
        list_result = list_changesets(live_auth, live_config, ListChangesetsParams(limit=1))
        assert list_result["success"] is True
        if not list_result["changesets"]:
            pytest.skip("No changesets found on this instance.")
        raw_sys_id = list_result["changesets"][0]["sys_id"]
        sys_id = _extract_sys_id(raw_sys_id)
        params = GetChangesetDetailsParams(changeset_id=sys_id)
        result = get_changeset_details(live_auth, live_config, params)
        print(f"\n--- get_changeset_details({sys_id}) response ---")
        print(json.dumps(result, indent=2, default=str))
        assert result["success"] is True, f"Expected success, got: {result.get('message')}"
        assert "changeset" in result
        assert "changes" in result

    def test_list_changesets_limit_respected(self, live_config, live_auth):
        params = ListChangesetsParams(limit=2)
        result = list_changesets(live_auth, live_config, params)
        assert result["success"] is True
        assert len(result["changesets"]) <= 2
