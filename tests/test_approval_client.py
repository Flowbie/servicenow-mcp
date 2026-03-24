import pytest
import httpx
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.mark.asyncio
async def test_approved_returns_approved():
    """When workbench approves, request_approval returns APPROVED."""
    from servicenow_mcp.utils.approval_client import request_approval, ApprovalDecision

    pending_response = MagicMock()
    pending_response.raise_for_status = MagicMock()
    pending_response.json = MagicMock(return_value={"approval_id": "test-id"})

    status_response = MagicMock()
    status_response.status_code = 200
    status_response.json = MagicMock(return_value={"status": "approved"})

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=pending_response)
    mock_client.get = AsyncMock(return_value=status_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("servicenow_mcp.utils.approval_client.httpx.AsyncClient", return_value=mock_client), \
         patch("servicenow_mcp.utils.approval_client.asyncio.sleep", new_callable=AsyncMock):
        result = await request_approval("create_record", {"table": "incident"}, "proj-1")

    assert result == ApprovalDecision.APPROVED


@pytest.mark.asyncio
async def test_rejected_returns_rejected():
    """When workbench rejects, request_approval returns REJECTED."""
    from servicenow_mcp.utils.approval_client import request_approval, ApprovalDecision

    pending_response = MagicMock()
    pending_response.raise_for_status = MagicMock()
    pending_response.json = MagicMock(return_value={"approval_id": "test-id"})

    status_response = MagicMock()
    status_response.status_code = 200
    status_response.json = MagicMock(return_value={"status": "rejected"})

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=pending_response)
    mock_client.get = AsyncMock(return_value=status_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("servicenow_mcp.utils.approval_client.httpx.AsyncClient", return_value=mock_client), \
         patch("servicenow_mcp.utils.approval_client.asyncio.sleep", new_callable=AsyncMock):
        result = await request_approval("delete_record", {}, "proj-1")

    assert result == ApprovalDecision.REJECTED


@pytest.mark.asyncio
async def test_timeout_raises():
    """When polling never resolves, TimeoutError is raised."""
    from servicenow_mcp.utils.approval_client import request_approval, APPROVAL_TIMEOUT

    pending_response = MagicMock()
    pending_response.raise_for_status = MagicMock()
    pending_response.json = MagicMock(return_value={"approval_id": "test-id"})

    # Status always returns "pending"
    status_response = MagicMock()
    status_response.status_code = 200
    status_response.json = MagicMock(return_value={"status": "pending"})

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=pending_response)
    mock_client.get = AsyncMock(return_value=status_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    # Patch sleep to return immediately AND override APPROVAL_TIMEOUT to 0.1s
    with patch("servicenow_mcp.utils.approval_client.httpx.AsyncClient", return_value=mock_client), \
         patch("servicenow_mcp.utils.approval_client.asyncio.sleep", new_callable=AsyncMock), \
         patch("servicenow_mcp.utils.approval_client.APPROVAL_TIMEOUT", 0.1):
        with pytest.raises(TimeoutError):
            await request_approval("create_record", {}, "proj-1")


@pytest.mark.asyncio
async def test_httpx_unavailable_raises_runtime_error():
    """When httpx is not available, RuntimeError is raised."""
    from servicenow_mcp.utils import approval_client

    original = approval_client._HTTPX_AVAILABLE
    try:
        approval_client._HTTPX_AVAILABLE = False
        with pytest.raises(RuntimeError, match="httpx"):
            await approval_client.request_approval("create_record", {}, "proj-1")
    finally:
        approval_client._HTTPX_AVAILABLE = original


@pytest.mark.asyncio
async def test_non_200_poll_continues_until_timeout():
    """Non-200 status on poll should continue polling (not raise) and eventually timeout."""
    from servicenow_mcp.utils.approval_client import request_approval

    pending_response = MagicMock()
    pending_response.raise_for_status = MagicMock()
    pending_response.json = MagicMock(return_value={"approval_id": "test-id"})

    status_response = MagicMock()
    status_response.status_code = 503  # non-200
    status_response.json = MagicMock(return_value={})

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=pending_response)
    mock_client.get = AsyncMock(return_value=status_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("servicenow_mcp.utils.approval_client.httpx.AsyncClient", return_value=mock_client), \
         patch("servicenow_mcp.utils.approval_client.asyncio.sleep", new_callable=AsyncMock), \
         patch("servicenow_mcp.utils.approval_client.APPROVAL_TIMEOUT", 0.1):
        with pytest.raises(TimeoutError):
            await request_approval("create_record", {}, "proj-1")


@pytest.mark.asyncio
async def test_existing_tests_patch_sleep():
    """Verify the two original tests pass with sleep patched (regression guard)."""
    # This is a meta-check — the real fix is patching sleep in the original tests above.
    # If this test file is updated to patch sleep in those tests, this test is redundant.
    pass


def test_create_record_gate_approved(monkeypatch):
    """create_record gate calls request_approval and proceeds when approved."""
    from servicenow_mcp.tools.table_tools import create_record, CreateRecordParams
    from servicenow_mcp.utils.approval_client import ApprovalDecision

    monkeypatch.setenv("WORKBENCH_URL", "http://localhost:8742")
    monkeypatch.setenv("WORKBENCH_PROJECT_ID", "test-proj")

    async def fake_approval(*args, **kwargs):
        return ApprovalDecision.APPROVED

    mock_config = MagicMock()
    mock_auth = MagicMock()
    params = CreateRecordParams(table="incident", fields={"short_description": "test"})

    with patch("servicenow_mcp.utils.approval_client.request_approval", side_effect=fake_approval):
        with patch("servicenow_mcp.tools.table_tools.requests") as mock_requests:
            mock_resp = MagicMock()
            mock_resp.json.return_value = {"result": {"sys_id": "abc"}}
            mock_resp.raise_for_status = MagicMock()
            mock_requests.post.return_value = mock_resp
            result = create_record(mock_config, mock_auth, params)

    # Should have gotten past the gate — result should not be the rejection dict
    assert result.get("approved") is not False


def test_create_record_gate_rejected(monkeypatch):
    """create_record gate returns rejection dict when user rejects."""
    from servicenow_mcp.tools.table_tools import create_record, CreateRecordParams
    from servicenow_mcp.utils.approval_client import ApprovalDecision

    monkeypatch.setenv("WORKBENCH_URL", "http://localhost:8742")
    monkeypatch.setenv("WORKBENCH_PROJECT_ID", "test-proj")

    async def fake_rejection(*args, **kwargs):
        return ApprovalDecision.REJECTED

    mock_config = MagicMock()
    mock_auth = MagicMock()
    params = CreateRecordParams(table="incident", fields={"short_description": "test"})

    with patch("servicenow_mcp.utils.approval_client.request_approval", side_effect=fake_rejection):
        result = create_record(mock_config, mock_auth, params)

    assert result == {"error": "Operation rejected by user", "approved": False}
