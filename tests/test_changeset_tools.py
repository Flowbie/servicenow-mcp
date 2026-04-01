"""
Tests for the changeset tools.

Only compound tool tests are retained here.
CRUD operations (list, create, update, commit, publish, add_file) have been
removed — those are handled by table_tools + sys_update_set architecture blueprint.
"""

import unittest
from unittest.mock import MagicMock, patch

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.changeset_tools import (
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

    @patch("servicenow_mcp.tools.changeset_tools.requests.get")
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

    @patch("servicenow_mcp.tools.changeset_tools.requests.get")
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
