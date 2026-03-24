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

    with patch("servicenow_mcp.utils.approval_client.httpx.AsyncClient", return_value=mock_client):
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

    with patch("servicenow_mcp.utils.approval_client.httpx.AsyncClient", return_value=mock_client):
        result = await request_approval("delete_record", {}, "proj-1")

    assert result == ApprovalDecision.REJECTED
