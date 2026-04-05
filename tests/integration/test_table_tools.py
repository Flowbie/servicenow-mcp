# tests/integration/test_table_tools.py
"""
Integration tests for the generic table API tools against a live ServiceNow instance.
READ-ONLY — covers query_records and get_record only.
Run with: SN_INTEGRATION_TESTS=1 pytest tests/integration/test_table_tools.py -v -s
"""
import json
import pytest

from servicenow_mcp.tools.table_tools import (
    query_records,
    get_record,
    QueryRecordsParams,
    GetRecordParams,
)


@pytest.mark.integration
class TestTableToolsIntegration:

    def test_query_records_incident_table(self, live_config, live_auth):
        """Verify query_records works against the incident table."""
        params = QueryRecordsParams(table="incident", limit=5)
        result = query_records(live_config, live_auth, params)

        print("\n--- query_records(incident) response ---")
        print(json.dumps(result, indent=2, default=str))

        assert result["success"] is True, f"Expected success, got: {result.get('message')}"
        assert "records" in result
        assert isinstance(result["records"], list)

    def test_query_records_sys_user_table(self, live_config, live_auth):
        """Verify query_records works against sys_user table."""
        params = QueryRecordsParams(table="sys_user", limit=3)
        result = query_records(live_config, live_auth, params)

        print("\n--- query_records(sys_user) response ---")
        print(json.dumps(result, indent=2, default=str))

        assert result["success"] is True
        assert "records" in result

    def test_query_records_with_query_filter(self, live_config, live_auth):
        """Verify query filter is applied."""
        params = QueryRecordsParams(
            table="incident",
            limit=5,
            query="active=true",
        )
        result = query_records(live_config, live_auth, params)

        print("\n--- query_records(incident, active=true) response ---")
        print(json.dumps(result, indent=2, default=str))

        assert result["success"] is True

    def test_get_record_by_sys_id(self, live_config, live_auth):
        """Verify get_record returns a specific record by sys_id."""
        list_result = query_records(live_config, live_auth, QueryRecordsParams(table="incident", limit=1))
        assert list_result["success"] is True

        if not list_result["records"]:
            pytest.skip("No incident records found.")

        sys_id = list_result["records"][0]["sys_id"]

        params = GetRecordParams(table="incident", sys_id=sys_id)
        result = get_record(live_config, live_auth, params)

        print(f"\n--- get_record(incident, {sys_id}) response ---")
        print(json.dumps(result, indent=2, default=str))

        assert result["success"] is True
        assert "record" in result
        assert result["record"]["sys_id"] == sys_id

    def test_get_record_not_found(self, live_config, live_auth):
        """Verify graceful not-found handling."""
        params = GetRecordParams(table="incident", sys_id="nonexistent_sys_id_000000000")
        result = get_record(live_config, live_auth, params)

        print("\n--- not_found response ---")
        print(json.dumps(result, indent=2, default=str))

        assert result["success"] is False
        assert "message" in result, f"get_record must return 'message' on failure, got keys: {list(result.keys())}"
        assert "error" not in result

    def test_query_records_limit_respected(self, live_config, live_auth):
        """Verify limit param is respected."""
        params = QueryRecordsParams(table="incident", limit=2)
        result = query_records(live_config, live_auth, params)

        assert result["success"] is True
        assert len(result["records"]) <= 2
