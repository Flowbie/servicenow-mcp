import json
from unittest.mock import MagicMock, patch

import requests as requests_lib

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.table_tools import (
    CreateRecordParams,
    DeleteRecordParams,
    GetRecordParams,
    QueryRecordsParams,
    UpdateRecordParams,
    create_record,
    delete_record,
    get_record,
    query_records,
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


def _dict_response(data: dict) -> MagicMock:
    """Return a mock requests.Response that yields data as JSON."""
    r = MagicMock()
    r.raise_for_status.return_value = None
    r.json.return_value = data
    return r


# ---------------------------------------------------------------------------
# update-set policy tests
# ---------------------------------------------------------------------------


@patch("servicenow_mcp.tools.table_tools.get_current_update_set")
@patch("servicenow_mcp.tools.table_tools.requests.get")
@patch("servicenow_mcp.tools.table_tools.requests.post")
def test_create_record_unknown_table_allowed_through(mock_post, mock_get, mock_get_update_set):
    """Unknown tables are now allowed; the mandatory-field check runs instead."""
    mock_get_update_set.return_value = {"success": False, "message": "no update set"}
    # sys_dictionary returns no mandatory fields → no block
    mock_get.return_value = _dict_response({"result": []})
    mock_post.return_value = _dict_response({"result": {"sys_id": "new-id"}})

    result = create_record(
        _server_config(),
        _auth_manager(),
        CreateRecordParams(table="x_custom_table", fields={"name": "test"}),
    )

    assert result["success"] is True


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
@patch("servicenow_mcp.tools.table_tools.resolve_identifier", side_effect=lambda cfg, auth, table, sid: sid)
@patch("servicenow_mcp.tools.table_tools.requests.delete")
def test_delete_record_allows_exempt_data_table(mock_delete, mock_resolve, mock_get_current_update_set):
    mock_get_current_update_set.return_value = {"success": False, "message": "not needed"}
    mock_delete.return_value = _dict_response({})

    result = delete_record(
        _server_config(),
        _auth_manager(),
        DeleteRecordParams(table="incident", sys_id="abc123"),
    )

    assert result["success"] is True
    assert result["table"] == "incident"
    mock_delete.assert_called_once()


# ---------------------------------------------------------------------------
# mandatory-field pre-flight tests
# ---------------------------------------------------------------------------


@patch("servicenow_mcp.tools.table_tools.get_current_update_set")
@patch("servicenow_mcp.tools.table_tools.requests.get")
def test_create_record_blocks_missing_mandatory_fields(mock_get, mock_get_update_set):
    mock_get_update_set.return_value = {"success": False}
    mock_get.return_value = _dict_response({
        "result": [
            {"element": "name", "default_value": ""},
            {"element": "category", "default_value": ""},
        ]
    })

    result = create_record(
        _server_config(),
        _auth_manager(),
        CreateRecordParams(table="sn_risk_advanced_event", fields={"short_description": "test"}),
    )

    assert result["success"] is False
    assert "missing_mandatory_fields" in result
    assert "name" in result["missing_mandatory_fields"]
    assert "category" in result["missing_mandatory_fields"]


@patch("servicenow_mcp.tools.table_tools.get_current_update_set")
@patch("servicenow_mcp.tools.table_tools.requests.get")
@patch("servicenow_mcp.tools.table_tools.requests.post")
def test_create_record_allows_when_all_mandatory_fields_present(mock_post, mock_get, mock_get_update_set):
    mock_get_update_set.return_value = {"success": False}
    mock_get.return_value = _dict_response({
        "result": [
            {"element": "name", "default_value": ""},
            {"element": "category", "default_value": ""},
        ]
    })
    mock_post.return_value = _dict_response({"result": {"sys_id": "abc"}})

    result = create_record(
        _server_config(),
        _auth_manager(),
        CreateRecordParams(
            table="sn_risk_advanced_event",
            fields={"name": "Event A", "category": "security", "short_description": "test"},
        ),
    )

    assert result["success"] is True
    mock_post.assert_called_once()


@patch("servicenow_mcp.tools.table_tools.get_current_update_set")
@patch("servicenow_mcp.tools.table_tools.requests.get")
@patch("servicenow_mcp.tools.table_tools.requests.post")
def test_create_record_skips_mandatory_field_with_default_value(mock_post, mock_get, mock_get_update_set):
    """A mandatory field that has a default_value should not be required in the payload."""
    mock_get_update_set.return_value = {"success": False}
    mock_get.return_value = _dict_response({
        "result": [
            {"element": "state", "default_value": "draft"},   # has default → skip
            {"element": "name", "default_value": ""},          # no default → required
        ]
    })
    mock_post.return_value = _dict_response({"result": {"sys_id": "abc"}})

    result = create_record(
        _server_config(),
        _auth_manager(),
        CreateRecordParams(table="sn_risk_advanced_event", fields={"name": "Event A"}),
    )

    assert result["success"] is True
    assert "missing_mandatory_fields" not in result


@patch("servicenow_mcp.tools.table_tools.get_current_update_set")
@patch("servicenow_mcp.tools.table_tools.requests.get")
@patch("servicenow_mcp.tools.table_tools.requests.post")
def test_create_record_fails_open_on_sys_dictionary_error(mock_post, mock_get, mock_get_update_set):
    """If sys_dictionary is unreachable, the write proceeds — don't block on uncertainty."""
    mock_get_update_set.return_value = {"success": False}
    mock_get.side_effect = requests_lib.RequestException("connection refused")
    mock_post.return_value = _dict_response({"result": {"sys_id": "abc"}})

    result = create_record(
        _server_config(),
        _auth_manager(),
        CreateRecordParams(table="sn_risk_advanced_event", fields={"name": "Event A"}),
    )

    assert result["success"] is True
    mock_post.assert_called_once()


@patch("servicenow_mcp.tools.table_tools.get_current_update_set")
@patch("servicenow_mcp.tools.table_tools.requests.get")
def test_create_record_checks_task_parent_for_task_hierarchy_table(mock_get, mock_get_update_set):
    """For task-hierarchy tables, sys_dictionary is queried for both the table and `task`."""
    mock_get_update_set.return_value = {"success": False}
    # Simulate: table-level returns nothing, task-level has a mandatory field
    mock_get.side_effect = [
        _dict_response({"result": []}),                                      # incident query
        _dict_response({"result": [{"element": "short_description", "default_value": ""}]}),  # task query
    ]

    result = create_record(
        _server_config(),
        _auth_manager(),
        CreateRecordParams(table="incident", fields={"category": "software"}),
    )

    assert result["success"] is False
    assert "short_description" in result["missing_mandatory_fields"]
    assert mock_get.call_count == 2


@patch("servicenow_mcp.tools.table_tools.get_current_update_set")
@patch("servicenow_mcp.tools.table_tools.resolve_identifier", side_effect=lambda cfg, auth, table, sid: sid)
@patch("servicenow_mcp.tools.table_tools.requests.patch")
def test_update_record_does_not_run_mandatory_field_check(mock_patch, mock_resolve, mock_get_update_set):
    """update_record is a partial PATCH — mandatory-field check must not run."""
    mock_get_update_set.return_value = {"success": False}
    mock_patch.return_value = _dict_response({"result": {"sys_id": "abc"}})

    result = update_record(
        _server_config(),
        _auth_manager(),
        UpdateRecordParams(table="sn_risk_advanced_event", sys_id="abc", fields={"state": "open"}),
    )

    assert result["success"] is True
    mock_patch.assert_called_once()


@patch("servicenow_mcp.tools.table_tools.resolve_identifier", side_effect=lambda cfg, auth, table, sid: sid)
@patch("servicenow_mcp.tools.table_tools.requests.get")
def test_get_record_not_found_returns_error_key(mock_get, mock_resolve):
    """get_record must return 'error' (SnowResponse envelope contract)."""
    resp = MagicMock()
    resp.raise_for_status.side_effect = requests_lib.HTTPError("404 Not Found")
    resp.text = "Not Found"
    mock_get.return_value = resp

    result = get_record(
        _server_config(),
        _auth_manager(),
        GetRecordParams(table="incident", sys_id="nonexistent000"),
    )

    assert result["success"] is False
    assert "error" in result


@patch("servicenow_mcp.tools.table_tools.resolve_identifier", side_effect=lambda cfg, auth, table, sid: sid)
@patch("servicenow_mcp.tools.table_tools.requests.get")
def test_get_record_success(mock_get, mock_resolve):
    mock_get.return_value = _dict_response(
        {"result": {"sys_id": "abc123", "short_description": "Test"}}
    )

    result = get_record(
        _server_config(),
        _auth_manager(),
        GetRecordParams(table="incident", sys_id="abc123"),
    )

    assert result["success"] is True
    assert result["data"]["sys_id"] == "abc123"


# ── Task 5: Envelope + identifier resolver tests ──────────────────────────

def _make_config_t5():
    config = MagicMock()
    config.api_url = "https://dev.service-now.com/api/now"
    config.instance_url = "https://dev.service-now.com"
    config.timeout = 30
    return config


def _make_auth_t5():
    auth = MagicMock()
    auth.get_headers.return_value = {"Authorization": "Basic dGVzdA=="}
    return auth


def _mock_get_response(data):
    resp = MagicMock()
    resp.status_code = 200
    resp.raise_for_status = MagicMock()
    resp.json.return_value = data
    return resp


def test_get_record_resolves_ticket_number_to_sys_id():
    config = _make_config_t5()
    auth = _make_auth_t5()
    resolved_sys_id = "a" * 32

    record_resp = _mock_get_response({"result": {"sys_id": resolved_sys_id, "number": "INC0012345"}})

    with patch("servicenow_mcp.tools.table_tools.resolve_identifier", return_value=resolved_sys_id) as mock_resolve, \
         patch("servicenow_mcp.tools.table_tools.requests.get", return_value=record_resp):
        result = get_record(config, auth, GetRecordParams(table="incident", sys_id="INC0012345"))

    mock_resolve.assert_called_once_with(config, auth, "incident", "INC0012345")
    assert result["success"] is True
    assert result["table"] == "incident"


def test_get_record_result_includes_envelope_fields():
    config = _make_config_t5()
    auth = _make_auth_t5()
    sys_id = "b" * 32
    record_resp = _mock_get_response({"result": {"sys_id": sys_id}})

    with patch("servicenow_mcp.tools.table_tools.resolve_identifier", return_value=sys_id), \
         patch("servicenow_mcp.tools.table_tools.requests.get", return_value=record_resp):
        result = get_record(config, auth, GetRecordParams(table="incident", sys_id=sys_id))

    assert "success" in result
    assert "data" in result
    assert result["operation"] == "get_record"


def test_update_record_resolves_ticket_number():
    config = _make_config_t5()
    auth = _make_auth_t5()
    resolved_sys_id = "c" * 32

    patch_resp = MagicMock()
    patch_resp.status_code = 200
    patch_resp.raise_for_status = MagicMock()
    patch_resp.json.return_value = {"result": {"sys_id": resolved_sys_id}}

    with patch("servicenow_mcp.tools.table_tools.resolve_identifier", return_value=resolved_sys_id) as mock_resolve, \
         patch("servicenow_mcp.tools.table_tools.requests.patch", return_value=patch_resp), \
         patch("servicenow_mcp.tools.table_tools._enforce_update_set_policy", return_value=None):
        result = update_record(
            config, auth,
            UpdateRecordParams(table="incident", sys_id="INC0012345", fields={"state": "6"}),
        )

    mock_resolve.assert_called_once_with(config, auth, "incident", "INC0012345")
    assert result["success"] is True


def test_query_records_include_query_info_echoes_encoded_query():
    config = _make_config_t5()
    auth = _make_auth_t5()
    resp = _mock_get_response({"result": []})

    with patch("servicenow_mcp.tools.table_tools.requests.get", return_value=resp):
        result = query_records(
            config, auth,
            QueryRecordsParams(table="incident", query="active=true^state=1", include_query_info=True),
        )

    assert "query_info" in result
    assert result["query_info"]["encoded_query"] == "active=true^state=1"
    assert result["query_info"]["table"] == "incident"


def test_query_records_no_query_info_by_default():
    config = _make_config_t5()
    auth = _make_auth_t5()
    resp = _mock_get_response({"result": []})

    with patch("servicenow_mcp.tools.table_tools.requests.get", return_value=resp):
        result = query_records(
            config, auth,
            QueryRecordsParams(table="incident", query="active=true"),
        )

    assert "query_info" not in result


def test_get_record_returns_error_when_ticket_not_found():
    config = _make_config_t5()
    auth = _make_auth_t5()

    with patch("servicenow_mcp.tools.table_tools.resolve_identifier",
               side_effect=ValueError("Record not found: incident/INC9999999")):
        result = get_record(config, auth, GetRecordParams(table="incident", sys_id="INC9999999"))

    assert result["success"] is False
    assert "not found" in result["error"].lower()
    assert result["operation"] == "get_record"


def test_update_record_returns_error_when_ticket_not_found():
    config = _make_config_t5()
    auth = _make_auth_t5()

    with patch("servicenow_mcp.tools.table_tools.resolve_identifier",
               side_effect=ValueError("Record not found: incident/INC9999999")), \
         patch("servicenow_mcp.tools.table_tools._enforce_update_set_policy", return_value=None):
        result = update_record(
            config, auth,
            UpdateRecordParams(table="incident", sys_id="INC9999999", fields={"state": "6"}),
        )

    assert result["success"] is False
    assert "not found" in result["error"].lower()


def test_delete_record_returns_error_when_ticket_not_found():
    config = _make_config_t5()
    auth = _make_auth_t5()

    with patch("servicenow_mcp.tools.table_tools.resolve_identifier",
               side_effect=ValueError("Record not found: incident/INC9999999")), \
         patch("servicenow_mcp.tools.table_tools._enforce_update_set_policy", return_value=None):
        result = delete_record(
            config, auth,
            DeleteRecordParams(table="incident", sys_id="INC9999999"),
        )

    assert result["success"] is False
    assert "not found" in result["error"].lower()
