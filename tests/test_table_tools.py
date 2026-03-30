from unittest.mock import MagicMock, patch

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.table_tools import (
    CreateRecordParams,
    DeleteRecordParams,
    UpdateRecordParams,
    create_record,
    delete_record,
    update_record,
)
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig


def _server_config() -> ServerConfig:
    auth_config = AuthConfig(
        type=AuthType.BASIC,
        basic=BasicAuthConfig(username="test_user", password="test_password"),
    )
    return ServerConfig(instance_url="https://test.service-now.com", auth=auth_config)


def _auth_manager() -> MagicMock:
    auth_manager = MagicMock(spec=AuthManager)
    auth_manager.get_headers.return_value = {"Authorization": "Bearer test"}
    return auth_manager


@patch("servicenow_mcp.tools.table_tools.get_current_update_set")
def test_create_record_blocks_unknown_table(mock_get_current_update_set):
    mock_get_current_update_set.return_value = {"success": False, "message": "no update set"}

    result = create_record(
        _server_config(),
        _auth_manager(),
        CreateRecordParams(table="x_custom_table", fields={"name": "test"}),
    )

    assert result["success"] is False
    assert result["governance"]["classification"] == "unknown"


@patch("servicenow_mcp.tools.table_tools.get_current_update_set")
def test_update_record_blocks_required_table_on_default_update_set(mock_get_current_update_set):
    mock_get_current_update_set.return_value = {
        "success": True,
        "update_set": {
            "name": "Default",
            "sys_id": "default-id",
            "state": "in progress",
            "is_default": True,
        },
    }

    result = update_record(
        _server_config(),
        _auth_manager(),
        UpdateRecordParams(table="sys_script_include", sys_id="abc123", fields={"name": "New Name"}),
    )

    assert result["success"] is False
    assert result["governance"]["classification"] == "required"
    assert "default update set" in result["error"].lower()


@patch("servicenow_mcp.tools.table_tools.get_current_update_set")
@patch("servicenow_mcp.tools.table_tools.requests.delete")
def test_delete_record_allows_exempt_data_table(mock_delete, mock_get_current_update_set):
    mock_get_current_update_set.return_value = {"success": False, "message": "not needed"}
    response = MagicMock()
    response.raise_for_status.return_value = None
    mock_delete.return_value = response

    result = delete_record(
        _server_config(),
        _auth_manager(),
        DeleteRecordParams(table="incident", sys_id="abc123"),
    )

    assert result["success"] is True
    assert result["table"] == "incident"
    mock_delete.assert_called_once()
