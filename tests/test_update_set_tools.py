"""
Tests for the changeset tools.

Only compound tool tests are retained here.
CRUD operations (list, create, update, commit, publish, add_file) have been
removed — those are handled by table_tools + sys_update_set architecture blueprint.
"""

import unittest
from unittest.mock import MagicMock, patch

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.update_set_tools import (
    GetCurrentScopeParams,
    GetCurrentUpdateSetParams,
    GetChangesetDetailsParams,
    SetCurrentScopeParams,
    SetCurrentUpdateSetParams,
    get_current_scope,
    get_current_update_set,
    get_changeset_details,
    set_current_scope,
    set_current_update_set,
)
from servicenow_mcp.utils.config import ServerConfig, AuthConfig, AuthType, BasicAuthConfig


def _make_bg_result(direct_output: str, success: bool = True):
    """Build a minimal RunBackgroundScriptResult-like mock."""
    result = MagicMock()
    result.success = success
    result.direct_output = direct_output
    result.message = "" if success else "script error"
    return result


class TestGetCurrentUpdateSet(unittest.TestCase):
    def setUp(self):
        auth_config = AuthConfig(
            type=AuthType.BASIC,
            basic=BasicAuthConfig(username="svc_account", password="pw"),
        )
        self.config = ServerConfig(instance_url="https://test.service-now.com", auth=auth_config)
        self.auth = MagicMock(spec=AuthManager)

    @patch("servicenow_mcp.tools.script_tools.run_background_script")
    def test_success(self, mock_bg):
        output = '[INFO] {"success": true, "name": "STRY0012345 - Test", "sys_id": "us1", "state": "in progress", "is_default": false} | run_id=abc123'
        mock_bg.return_value = _make_bg_result(output)

        result = get_current_update_set(self.config, self.auth, {})

        self.assertTrue(result["success"])
        self.assertEqual(result["name"], "STRY0012345 - Test")
        self.assertEqual(result["sys_id"], "us1")
        self.assertEqual(result["state"], "in progress")
        self.assertFalse(result["is_default"])

    @patch("servicenow_mcp.tools.script_tools.run_background_script")
    def test_no_active_update_set(self, mock_bg):
        output = '[INFO] {"success": false, "message": "No active update set found for current user (gs.getPreference returned empty)"} | run_id=abc123'
        mock_bg.return_value = _make_bg_result(output)

        result = get_current_update_set(self.config, self.auth, {})

        self.assertFalse(result["success"])
        self.assertIn("No active update set", result["message"])

    @patch("servicenow_mcp.tools.script_tools.run_background_script")
    def test_background_script_failure(self, mock_bg):
        mock_bg.return_value = _make_bg_result("", success=False)

        result = get_current_update_set(self.config, self.auth, {})

        self.assertFalse(result["success"])
        self.assertIn("Background script failed", result["message"])

    @patch("servicenow_mcp.tools.script_tools.run_background_script")
    def test_unparseable_output(self, mock_bg):
        mock_bg.return_value = _make_bg_result("[INFO] unexpected non-json | run_id=abc123")

        result = get_current_update_set(self.config, self.auth, {})

        self.assertFalse(result["success"])
        self.assertIn("Could not parse", result["message"])

    @patch("servicenow_mcp.tools.script_tools.run_background_script")
    def test_default_update_set_flagged(self, mock_bg):
        output = '[INFO] {"success": true, "name": "Default", "sys_id": "def1", "state": "in progress", "is_default": true} | run_id=abc123'
        mock_bg.return_value = _make_bg_result(output)

        result = get_current_update_set(self.config, self.auth, {})

        self.assertTrue(result["success"])
        self.assertTrue(result["is_default"])

    @patch("servicenow_mcp.tools.script_tools.run_background_script")
    def test_numeric_level_prefix_parsed(self, mock_bg):
        """Syslog level field is a numeric string ('0', '1', etc.) on the instance.
        _extract_syslog_output formats lines as [0], [1], etc. — verify these parse."""
        output = '[0] {"success": true, "name": "STRY0099 - Feature", "sys_id": "us2", "state": "in progress", "is_default": false} | run_id=abc123'
        mock_bg.return_value = _make_bg_result(output)

        result = get_current_update_set(self.config, self.auth, {})

        self.assertTrue(result["success"])
        self.assertEqual(result["name"], "STRY0099 - Feature")


class TestScopePickerTools(unittest.TestCase):
    def setUp(self):
        auth_config = AuthConfig(
            type=AuthType.BASIC,
            basic=BasicAuthConfig(username="svc_account", password="pw"),
        )
        self.config = ServerConfig(instance_url="https://test.service-now.com", auth=auth_config)
        self.auth = MagicMock(spec=AuthManager)

    @patch("servicenow_mcp.tools.script_tools.run_background_script")
    def test_get_current_scope_success(self, mock_bg):
        output = '[INFO] {"success": true, "app_id": "53f81621cb200200829cf865734c9c58", "scope_name": "sn_grc", "scope_display_name": "GRC: Profiles"} | run_id=abc'
        mock_bg.return_value = _make_bg_result(output)

        result = get_current_scope(self.config, self.auth, GetCurrentScopeParams())

        self.assertTrue(result["success"])
        self.assertEqual(result["app_id"], "53f81621cb200200829cf865734c9c58")
        self.assertEqual(result["scope_name"], "sn_grc")
        self.assertEqual(result["scope_display_name"], "GRC: Profiles")

    @patch("servicenow_mcp.tools.script_tools.run_background_script")
    def test_get_current_scope_no_scope(self, mock_bg):
        output = '[INFO] {"success": false, "message": "No current application scope"} | run_id=abc'
        mock_bg.return_value = _make_bg_result(output)

        result = get_current_scope(self.config, self.auth, {})

        self.assertFalse(result["success"])
        self.assertIn("No current application scope", result["message"])

    @patch("servicenow_mcp.tools.script_tools.run_background_script")
    def test_get_current_scope_script_failure(self, mock_bg):
        mock_bg.return_value = _make_bg_result("", success=False)

        result = get_current_scope(self.config, self.auth, {})

        self.assertFalse(result["success"])
        self.assertIn("Background script failed", result["message"])

    @patch("servicenow_mcp.tools.script_tools.run_background_script")
    def test_get_current_scope_unparseable_output(self, mock_bg):
        mock_bg.return_value = _make_bg_result("[INFO] unexpected non-json | run_id=abc")

        result = get_current_scope(self.config, self.auth, {})

        self.assertFalse(result["success"])
        self.assertIn("Could not parse", result["message"])

    @patch("servicenow_mcp.tools.script_tools.run_background_script")
    def test_set_current_scope_success_by_scope_name(self, mock_bg):
        output = '[INFO] {"success": true, "app_id": "53f81621cb200200829cf865734c9c58", "scope_name": "sn_grc", "scope_display_name": "GRC: Profiles"} | run_id=abc'
        mock_bg.return_value = _make_bg_result(output)

        result = set_current_scope(
            self.config, self.auth,
            SetCurrentScopeParams(app_id="sn_grc"),
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["app_id"], "53f81621cb200200829cf865734c9c58")
        self.assertEqual(result["scope_name"], "sn_grc")
        self.assertIn("GRC: Profiles", result["message"])

    @patch("servicenow_mcp.tools.script_tools.run_background_script")
    def test_set_current_scope_success_by_sys_id(self, mock_bg):
        output = '[INFO] {"success": true, "app_id": "53f81621cb200200829cf865734c9c58", "scope_name": "sn_grc", "scope_display_name": "GRC: Profiles"} | run_id=abc'
        mock_bg.return_value = _make_bg_result(output)

        result = set_current_scope(
            self.config, self.auth,
            SetCurrentScopeParams(app_id="53f81621cb200200829cf865734c9c58"),
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["app_id"], "53f81621cb200200829cf865734c9c58")

    @patch("servicenow_mcp.tools.script_tools.run_background_script")
    def test_set_current_scope_not_found(self, mock_bg):
        output = '[INFO] {"success": false, "message": "Application scope not found: unknown_scope"} | run_id=abc'
        mock_bg.return_value = _make_bg_result(output)

        result = set_current_scope(
            self.config, self.auth,
            SetCurrentScopeParams(app_id="unknown_scope"),
        )

        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    def test_set_current_scope_rejects_blank_app_id(self):
        result = set_current_scope(self.config, self.auth, {"app_id": "   "})
        self.assertFalse(result["success"])
        self.assertIn("cannot be empty", result["message"])

    def test_set_current_scope_rejects_invalid_chars(self):
        result = set_current_scope(self.config, self.auth, {"app_id": "'; DROP TABLE--"})
        self.assertFalse(result["success"])
        self.assertIn("Invalid app_id", result["message"])

    @patch("servicenow_mcp.tools.script_tools.run_background_script")
    def test_set_current_scope_script_failure(self, mock_bg):
        mock_bg.return_value = _make_bg_result("", success=False)

        result = set_current_scope(self.config, self.auth, {"app_id": "sn_grc"})

        self.assertFalse(result["success"])
        self.assertIn("Background script failed", result["message"])


class TestSetCurrentUpdateSet(unittest.TestCase):
    def setUp(self):
        auth_config = AuthConfig(
            type=AuthType.BASIC,
            basic=BasicAuthConfig(username="svc_account", password="pw"),
        )
        self.config = ServerConfig(instance_url="https://test.service-now.com", auth=auth_config)
        self.auth = MagicMock(spec=AuthManager)

    @patch("servicenow_mcp.tools.script_tools.run_background_script")
    def test_success(self, mock_bg):
        output = '[INFO] {"success": true, "name": "STRY0012345 - My Story", "sys_id": "abc123def456abc123def456abc12345", "state": "in progress", "is_default": false} | run_id=xyz'
        mock_bg.return_value = _make_bg_result(output)

        result = set_current_update_set(
            self.config, self.auth,
            SetCurrentUpdateSetParams(changeset_id="abc123def456abc123def456abc12345"),
        )

        self.assertTrue(result["success"])
        self.assertIn("STRY0012345 - My Story", result["message"])
        self.assertEqual(result["sys_id"], "abc123def456abc123def456abc12345")

    @patch("servicenow_mcp.tools.script_tools.run_background_script")
    def test_wrong_state(self, mock_bg):
        output = '[INFO] {"success": false, "message": "Update set state is \\"complete\\", must be \\"in progress\\""} | run_id=xyz'
        mock_bg.return_value = _make_bg_result(output)

        result = set_current_update_set(
            self.config, self.auth,
            SetCurrentUpdateSetParams(changeset_id="abc123def456abc123def456abc12345"),
        )

        self.assertFalse(result["success"])
        self.assertIn("complete", result["message"])

    @patch("servicenow_mcp.tools.script_tools.run_background_script")
    def test_update_set_not_found(self, mock_bg):
        output = '[INFO] {"success": false, "message": "Update set not found: abc123def456abc123def456abc12345"} | run_id=xyz'
        mock_bg.return_value = _make_bg_result(output)

        result = set_current_update_set(
            self.config, self.auth,
            SetCurrentUpdateSetParams(changeset_id="abc123def456abc123def456abc12345"),
        )

        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    @patch("servicenow_mcp.tools.script_tools.run_background_script")
    def test_background_script_failure(self, mock_bg):
        mock_bg.return_value = _make_bg_result("", success=False)

        result = set_current_update_set(
            self.config, self.auth,
            SetCurrentUpdateSetParams(changeset_id="abc123def456abc123def456abc12345"),
        )

        self.assertFalse(result["success"])
        self.assertIn("Background script failed", result["message"])

    def test_invalid_changeset_id_rejected(self):
        """Changeset IDs with invalid chars are rejected before script execution."""
        result = set_current_update_set(
            self.config, self.auth,
            SetCurrentUpdateSetParams(changeset_id="'; DROP TABLE sys_update_set; --"),
        )
        self.assertFalse(result["success"])
        self.assertIn("Invalid changeset_id", result["message"])

    def test_missing_changeset_id(self):
        with self.assertRaises(Exception):
            SetCurrentUpdateSetParams()

    @patch("servicenow_mcp.tools.script_tools.run_background_script")
    def test_numeric_level_prefix_parsed(self, mock_bg):
        """Syslog level is numeric on instance — output format is [0] not [INFO]."""
        output = '[0] {"success": true, "name": "STRY0099 - Feature", "sys_id": "abc123def456abc123def456abc12345", "state": "in progress", "is_default": false} | run_id=xyz'
        mock_bg.return_value = _make_bg_result(output)

        result = set_current_update_set(
            self.config, self.auth,
            SetCurrentUpdateSetParams(changeset_id="abc123def456abc123def456abc12345"),
        )

        self.assertTrue(result["success"])
        self.assertIn("STRY0099 - Feature", result["message"])


class TestGetChangesetDetails(unittest.TestCase):
    def setUp(self):
        auth_config = AuthConfig(
            type=AuthType.BASIC,
            basic=BasicAuthConfig(username="svc_account", password="pw"),
        )
        self.config = ServerConfig(instance_url="https://test.service-now.com", auth=auth_config)
        self.auth = MagicMock(spec=AuthManager)
        self.auth.get_headers.return_value = {"Authorization": "Bearer test"}

    @patch("servicenow_mcp.tools.update_set_tools.requests.get")
    def test_success(self, mock_get):
        changeset_resp = MagicMock()
        changeset_resp.raise_for_status.return_value = None
        changeset_resp.json.return_value = {
            "result": {"sys_id": "123", "name": "Test Changeset", "state": "in_progress"}
        }

        changes_resp = MagicMock()
        changes_resp.raise_for_status.return_value = None
        changes_resp.json.return_value = {
            "result": [{"sys_id": "456", "name": "test_file.py", "update_set": "123"}]
        }

        def side_effect(*args, **kwargs):
            url = args[0]
            return changeset_resp if "sys_update_set" in url else changes_resp

        mock_get.side_effect = side_effect

        result = get_changeset_details(self.config, self.auth, {"changeset_id": "123"})

        self.assertTrue(result["success"])
        self.assertEqual(result["changeset"]["sys_id"], "123")
        self.assertEqual(len(result["changes"]), 1)

    @patch("servicenow_mcp.tools.update_set_tools.requests.get")
    def test_missing_id(self, mock_get):
        result = get_changeset_details(self.config, self.auth, {})
        self.assertFalse(result["success"])
        mock_get.assert_not_called()


class TestChangesetToolsParams(unittest.TestCase):
    def test_get_changeset_details_params(self):
        params = GetChangesetDetailsParams(changeset_id="123")
        self.assertEqual(params.changeset_id, "123")

    def test_set_current_update_set_params(self):
        params = SetCurrentUpdateSetParams(changeset_id="abc")
        self.assertEqual(params.changeset_id, "abc")

    def test_set_current_update_set_params_requires_id(self):
        with self.assertRaises(Exception):
            SetCurrentUpdateSetParams()

    def test_get_current_update_set_params(self):
        params = GetCurrentUpdateSetParams()
        self.assertIsInstance(params, GetCurrentUpdateSetParams)

    def test_get_current_scope_params(self):
        params = GetCurrentScopeParams()
        self.assertIsInstance(params, GetCurrentScopeParams)

    def test_set_current_scope_params(self):
        params = SetCurrentScopeParams(app_id="scope123")
        self.assertEqual(params.app_id, "scope123")


if __name__ == "__main__":
    unittest.main()


# ── Task 6: New update set tools ──────────────────────────────────────────
import pytest
from unittest.mock import MagicMock, patch
from servicenow_mcp.tools.update_set_tools import (
    move_records_to_update_set,
    inspect_update_set,
    clone_update_set,
    MoveRecordsToUpdateSetParams,
    InspectUpdateSetParams,
    CloneUpdateSetParams,
)


def _make_config_t6():
    config = MagicMock()
    config.api_url = "https://dev.service-now.com/api/now"
    config.instance_url = "https://dev.service-now.com"
    config.timeout = 30
    return config


def _make_auth_t6():
    auth = MagicMock()
    auth.get_headers.return_value = {"Authorization": "Basic dGVzdA=="}
    return auth


def _resp(status, data):
    r = MagicMock()
    r.status_code = status
    r.raise_for_status = MagicMock()
    r.json.return_value = data
    return r


# ── MoveRecordsToUpdateSetParams validation ────────────────────────────────

def test_move_params_requires_at_least_one_filter():
    with pytest.raises(ValueError, match="at least one filter"):
        MoveRecordsToUpdateSetParams(target_update_set_sys_id="a" * 32)


def test_move_params_accepts_source_update_set_filter():
    params = MoveRecordsToUpdateSetParams(
        target_update_set_sys_id="a" * 32,
        source_update_set_sys_id="b" * 32,
    )
    assert params.source_update_set_sys_id == "b" * 32


def test_move_params_accepts_sys_ids_filter():
    params = MoveRecordsToUpdateSetParams(
        target_update_set_sys_id="a" * 32,
        record_sys_ids=["c" * 32, "d" * 32],
    )
    assert len(params.record_sys_ids) == 2


def test_move_params_accepts_time_range_filter():
    params = MoveRecordsToUpdateSetParams(
        target_update_set_sys_id="a" * 32,
        time_range_start="2026-01-01T00:00:00Z",
        time_range_end="2026-01-31T23:59:59Z",
    )
    assert params.time_range_start is not None


# ── inspect_update_set ────────────────────────────────────────────────────

def test_inspect_update_set_returns_component_summary():
    config = _make_config_t6()
    auth = _make_auth_t6()

    xml_records = [
        {"sys_id": "x1", "name": "sys_script_include_abc", "type": "Script Include", "action": "INSERT_OR_UPDATE"},
        {"sys_id": "x2", "name": "sys_ui_action_def", "type": "UI Action", "action": "INSERT_OR_UPDATE"},
    ]
    us_record = {"sys_id": "a" * 32, "name": "My Update Set", "state": "in progress", "application": {"value": "b" * 32}}

    with patch("servicenow_mcp.tools.update_set_tools.requests.get") as mock_get:
        mock_get.side_effect = [
            _resp(200, {"result": [us_record]}),
            _resp(200, {"result": xml_records}),
        ]
        result = inspect_update_set(
            config, auth,
            InspectUpdateSetParams(update_set_sys_id="a" * 32),
        )

    assert result["success"] is True
    assert result["data"]["total_records"] == 2
    assert "Script Include" in result["data"]["by_type"]


# ── clone_update_set ──────────────────────────────────────────────────────

def test_clone_update_set_creates_new_set_and_copies_xml():
    config = _make_config_t6()
    auth = _make_auth_t6()

    source_us = {"sys_id": "a" * 32, "name": "Source Set", "application": {"value": "app123"}}
    new_us = {"sys_id": "e" * 32, "name": "Cloned Set"}
    xml_records = [{"sys_id": "x1"}, {"sys_id": "x2"}]

    with patch("servicenow_mcp.tools.update_set_tools.requests.get") as mock_get, \
         patch("servicenow_mcp.tools.update_set_tools.requests.post") as mock_post, \
         patch("servicenow_mcp.tools.update_set_tools.requests.patch") as mock_patch:
        mock_get.side_effect = [
            _resp(200, {"result": [source_us]}),
            _resp(200, {"result": xml_records}),
        ]
        mock_post.return_value = _resp(201, {"result": new_us})
        mock_patch.return_value = _resp(200, {"result": {}})

        result = clone_update_set(
            config, auth,
            CloneUpdateSetParams(source_sys_id="a" * 32, new_name="Cloned Set"),
        )

    assert result["success"] is True
    assert result["data"]["new_update_set_sys_id"] == "e" * 32
    assert result["data"]["records_copied"] == 2


def test_move_records_returns_moved_count_on_success():
    config = _make_config_t6()
    auth = _make_auth_t6()

    xml_records = [{"sys_id": "r1", "name": "Script Include", "type": "Script Include"}]

    with patch("servicenow_mcp.tools.update_set_tools.requests.get") as mock_get, \
         patch("servicenow_mcp.tools.update_set_tools.requests.patch") as mock_patch:
        mock_get.return_value = _resp(200, {"result": xml_records})
        mock_patch.return_value = _resp(200, {"result": {}})

        result = move_records_to_update_set(
            config, auth,
            MoveRecordsToUpdateSetParams(
                target_update_set_sys_id="a" * 32,
                source_update_set_sys_id="b" * 32,
            ),
        )

    assert result["success"] is True
    assert result["data"]["moved"] == 1
    assert result["data"]["failed"] == 0


def test_move_records_returns_empty_when_no_records():
    config = _make_config_t6()
    auth = _make_auth_t6()

    with patch("servicenow_mcp.tools.update_set_tools.requests.get") as mock_get:
        mock_get.return_value = _resp(200, {"result": []})

        result = move_records_to_update_set(
            config, auth,
            MoveRecordsToUpdateSetParams(
                target_update_set_sys_id="a" * 32,
                source_update_set_sys_id="b" * 32,
            ),
        )

    assert result["success"] is True
    assert result["data"]["moved"] == 0


def test_inspect_update_set_not_found_returns_error():
    config = _make_config_t6()
    auth = _make_auth_t6()

    with patch("servicenow_mcp.tools.update_set_tools.requests.get") as mock_get:
        mock_get.return_value = _resp(200, {"result": []})

        result = inspect_update_set(
            config, auth,
            InspectUpdateSetParams(update_set_sys_id="z" * 32),
        )

    assert result["success"] is False
    assert "not found" in result["error"].lower()


def test_clone_update_set_source_not_found_returns_error():
    config = _make_config_t6()
    auth = _make_auth_t6()

    with patch("servicenow_mcp.tools.update_set_tools.requests.get") as mock_get:
        mock_get.return_value = _resp(200, {"result": []})

        result = clone_update_set(
            config, auth,
            CloneUpdateSetParams(source_sys_id="z" * 32, new_name="Clone"),
        )

    assert result["success"] is False
    assert "not found" in result["error"].lower()


def test_inspect_update_set_application_as_plain_string():
    config = _make_config_t6()
    auth = _make_auth_t6()

    # application returned as plain string (not object with value key)
    us_record = {"sys_id": "a" * 32, "name": "My Update Set", "state": "in progress", "application": "global"}

    with patch("servicenow_mcp.tools.update_set_tools.requests.get") as mock_get:
        mock_get.side_effect = [
            _resp(200, {"result": [us_record]}),
            _resp(200, {"result": []}),
        ]
        result = inspect_update_set(
            config, auth,
            InspectUpdateSetParams(update_set_sys_id="a" * 32),
        )

    assert result["success"] is True
    assert result["data"]["update_set"]["application"] == "global"
