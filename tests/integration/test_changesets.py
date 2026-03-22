# tests/integration/test_changesets.py
"""
Integration tests for changeset (update set) tools against a live ServiceNow instance.
READ-ONLY — get_changeset_details only (list_changesets removed; use query_records instead).
Run with: SN_INTEGRATION_TESTS=1 pytest tests/integration/test_changesets.py -v -s
"""
import json
import pytest

from servicenow_mcp.tools.changeset_tools import (
    get_changeset_details,
    GetChangesetDetailsParams,
)


@pytest.mark.integration
class TestChangesetIntegration:

    def test_get_changeset_details_requires_sys_id(self, live_config, live_auth):
        """Verify get_changeset_details rejects missing changeset_id."""
        params = {}
        result = get_changeset_details(live_config, live_auth, params)
        assert result["success"] is False
        assert "message" in result
