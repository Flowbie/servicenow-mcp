"""
Tests for run_background_script CSRF fix.

Covers four behaviors:
  SCRP-02 — g_ck regex extraction from sys.scripts.do response body
  SCRP-04 — redirect guard (session_not_authenticated)
  SCRP-01 — X-UserToken header placement (sysparm_ck absent from form_data)
  SCRP-03 — non-empty direct_output when session is authenticated and script executes
"""

import unittest
from unittest.mock import MagicMock, patch, call

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.script_tools import (
    RunBackgroundScriptParams,
    _get_ui_session,
    run_background_script,
)
from servicenow_mcp.utils.config import (
    AuthConfig,
    AuthType,
    BasicAuthConfig,
    ServerConfig,
)


def _make_config():
    return ServerConfig(
        instance_url="https://test.service-now.com",
        auth=AuthConfig(
            type=AuthType.BASIC,
            basic=BasicAuthConfig(username="admin", password="pass"),
        ),
        timeout=30,
    )


def _make_auth_manager():
    am = MagicMock(spec=AuthManager)
    am.config = AuthConfig(
        type=AuthType.BASIC,
        basic=BasicAuthConfig(username="admin", password="pass"),
    )
    am.get_headers.return_value = {"Authorization": "Basic dGVzdA=="}
    return am


# ---------------------------------------------------------------------------
# SCRP-02 — g_ck JS variable regex extraction
# ---------------------------------------------------------------------------


class TestGetUiSessionCsrfExtraction(unittest.TestCase):
    """SCRP-02: _get_ui_session must extract the CSRF token from var g_ck = '...'."""

    def _make_session_mock(self, scripts_body, scripts_url="https://test.service-now.com/sys.scripts.do"):
        """Return a mock requests.Session that simulates the three-step login flow."""
        # GET /login.do response
        login_get = MagicMock()
        login_get.status_code = 200
        login_get.text = "<html><input type='hidden' name='sysparm_ck' value='login_ck_token' /></html>"

        # POST /login.do response — marks user as logged in
        login_post = MagicMock()
        login_post.status_code = 200
        login_post.headers = {"X-Is-Logged-In": "true"}

        # GET /sys.scripts.do response
        scripts_get = MagicMock()
        scripts_get.status_code = 200
        scripts_get.text = scripts_body
        scripts_get.url = scripts_url
        scripts_get.headers = {}

        mock_session = MagicMock()
        mock_session.get.side_effect = [login_get, scripts_get]
        mock_session.post.return_value = login_post
        return mock_session

    @patch("servicenow_mcp.tools.script_tools.requests.Session")
    def test_extracts_csrf_token_from_g_ck_js_variable(self, mock_session_cls):
        """Token is extracted from var g_ck = '...' when no hidden input is present."""
        body = (
            "<html><head>"
            "<script>var g_ck = 'abc123';</script>"
            "</head><body><div>sysparm_script</div></body></html>"
        )
        mock_session_cls.return_value = self._make_session_mock(body)
        config = _make_config()
        auth_manager = _make_auth_manager()

        session, csrf_token, failure = _get_ui_session(config, auth_manager)

        self.assertIsNotNone(session, "session should not be None for authenticated request")
        self.assertEqual(csrf_token, "abc123", "CSRF token should be extracted from g_ck JS variable")
        self.assertIsNone(failure, "failure_reason should be None on success")

    @patch("servicenow_mcp.tools.script_tools.requests.Session")
    def test_returns_none_token_when_g_ck_absent(self, mock_session_cls):
        """csrf_token is None (warning logged) when no hidden input, no g_ck, no X-UserToken."""
        # Body has sysparm_script but no token anywhere
        body = "<html><body><div>sysparm_script present here</div></body></html>"

        # Build mocks individually so we can set headers on the scripts_get mock
        login_get = MagicMock()
        login_get.status_code = 200
        login_get.text = "<html><input type='hidden' name='sysparm_ck' value='login_ck_token' /></html>"

        login_post = MagicMock()
        login_post.status_code = 200
        login_post.headers = {"X-Is-Logged-In": "true"}

        scripts_get = MagicMock()
        scripts_get.status_code = 200
        scripts_get.text = body
        scripts_get.url = "https://test.service-now.com/sys.scripts.do"
        scripts_get.headers = {}  # No X-UserToken header

        mock_session = MagicMock()
        mock_session.get.side_effect = [login_get, scripts_get]
        mock_session.post.return_value = login_post
        mock_session_cls.return_value = mock_session

        config = _make_config()
        auth_manager = _make_auth_manager()

        session, csrf_token, failure = _get_ui_session(config, auth_manager)

        self.assertIsNotNone(session, "session should be returned even when token missing")
        self.assertIsNone(csrf_token, "csrf_token should be None when no token found anywhere")
        self.assertIsNone(failure, "failure_reason should still be None — session itself is valid")


# ---------------------------------------------------------------------------
# SCRP-04 — redirect guard
# ---------------------------------------------------------------------------


class TestRunBackgroundScriptAuthGuard(unittest.TestCase):
    """SCRP-04: _get_ui_session must detect redirect to login.do and return failure."""

    def _make_session_mock_redirected_to_login(self):
        """Simulate sys.scripts.do redirecting to login.do."""
        login_get = MagicMock()
        login_get.status_code = 200
        login_get.text = "<html><input type='hidden' name='sysparm_ck' value='ck' /></html>"

        login_post = MagicMock()
        login_post.status_code = 200
        login_post.headers = {"X-Is-Logged-In": "true"}

        # The redirect: final URL is login.do, body is the login page (not sys.scripts.do)
        scripts_get = MagicMock()
        scripts_get.status_code = 200
        scripts_get.url = "https://test.service-now.com/login.do?sysparm_stack=sys.scripts.do"
        scripts_get.text = "<html><body>Please log in</body></html>"
        scripts_get.headers = {}

        mock_session = MagicMock()
        mock_session.get.side_effect = [login_get, scripts_get]
        mock_session.post.return_value = login_post
        return mock_session

    def _make_session_mock_missing_sysparm_script(self):
        """Simulate sys.scripts.do returning a page without sysparm_script content."""
        login_get = MagicMock()
        login_get.status_code = 200
        login_get.text = "<html><input type='hidden' name='sysparm_ck' value='ck' /></html>"

        login_post = MagicMock()
        login_post.status_code = 200
        login_post.headers = {"X-Is-Logged-In": "true"}

        scripts_get = MagicMock()
        scripts_get.status_code = 200
        scripts_get.url = "https://test.service-now.com/sys.scripts.do"
        scripts_get.text = "<html><body>Some other page without the expected marker</body></html>"
        scripts_get.headers = {}

        mock_session = MagicMock()
        mock_session.get.side_effect = [login_get, scripts_get]
        mock_session.post.return_value = login_post
        return mock_session

    @patch("servicenow_mcp.tools.script_tools.requests.Session")
    def test_returns_none_when_redirected_to_login_do(self, mock_session_cls):
        """session_failure starts with 'session_not_authenticated' when URL contains login.do."""
        mock_session_cls.return_value = self._make_session_mock_redirected_to_login()
        config = _make_config()
        auth_manager = _make_auth_manager()

        session, csrf_token, failure = _get_ui_session(config, auth_manager)

        self.assertIsNone(session, "session should be None when redirected to login.do")
        self.assertIsNone(csrf_token, "csrf_token should be None when redirected to login.do")
        self.assertIsNotNone(failure, "failure_reason must be set")
        self.assertTrue(
            failure.startswith("session_not_authenticated"),
            f"failure_reason should start with 'session_not_authenticated', got: {failure!r}",
        )

    @patch("servicenow_mcp.tools.script_tools.requests.Session")
    def test_returns_none_when_sysparm_script_absent(self, mock_session_cls):
        """session_failure starts with 'session_not_authenticated' when body lacks sysparm_script."""
        mock_session_cls.return_value = self._make_session_mock_missing_sysparm_script()
        config = _make_config()
        auth_manager = _make_auth_manager()

        session, csrf_token, failure = _get_ui_session(config, auth_manager)

        self.assertIsNone(session, "session should be None when sysparm_script not in body")
        self.assertIsNone(csrf_token, "csrf_token should be None")
        self.assertIsNotNone(failure, "failure_reason must be set")
        self.assertTrue(
            failure.startswith("session_not_authenticated"),
            f"failure_reason should start with 'session_not_authenticated', got: {failure!r}",
        )

    @patch("servicenow_mcp.tools.script_tools._get_ui_session")
    def test_run_background_script_returns_failure_when_not_authenticated(self, mock_get_session):
        """run_background_script returns success=False with descriptive message on auth failure."""
        mock_get_session.return_value = (
            None,
            None,
            "session_not_authenticated: sys.scripts.do redirected to login",
        )
        config = _make_config()
        auth_manager = _make_auth_manager()
        params = RunBackgroundScriptParams(script="gs.print('hello');")

        # After the fix, run_background_script must return early with success=False
        # without making any network calls when session_failure contains "session_not_authenticated"
        result = run_background_script(config, auth_manager, params)

        self.assertFalse(result.success, "success should be False when not authenticated")
        self.assertEqual(result.http_status, 0, "http_status should be 0 on early auth failure return")
        self.assertIn(
            "session",
            result.message.lower(),
            "message should mention session/authentication",
        )


# ---------------------------------------------------------------------------
# SCRP-01 — X-UserToken header placement, sysparm_ck absent from form_data
# ---------------------------------------------------------------------------


class TestRunBackgroundScriptTokenPlacement(unittest.TestCase):
    """SCRP-01: CSRF token sent as X-UserToken header, NOT as sysparm_ck in form_data."""

    @patch("servicenow_mcp.tools.script_tools._query_syslog")
    @patch("servicenow_mcp.tools.script_tools._get_ui_session")
    def test_csrf_token_sent_as_x_user_token_header(self, mock_get_session, mock_query_syslog):
        """When csrf_token is present, it is passed as X-UserToken in the POST headers."""
        mock_query_syslog.return_value = []

        # Build a realistic sys.scripts.do POST response with MFCP markers
        run_id_holder = {}

        mock_ui_session = MagicMock()

        def capture_post(*args, **kwargs):
            # Capture call args for assertion
            capture_post.call_args_captured = (args, kwargs)
            # Build a response body matching what the code expects
            # We need the actual run_id used — it's embedded in the wrapped script
            form_data = kwargs.get("data", {})
            script_body = form_data.get("sysparm_script", "")
            # Extract run_id from MFCP_START marker in the wrapped script
            import re as _re
            match = _re.search(r"\[run_id=([a-f0-9]+)\]", script_body)
            run_id_holder["id"] = match.group(1) if match else "unknown"
            rid = run_id_holder["id"]
            html = (
                f"<pre>=== MFCP_START [run_id={rid}] ===\n"
                f"hello world\n"
                f"=== MFCP_END [run_id={rid}] ===\n</pre>"
            )
            resp = MagicMock()
            resp.status_code = 200
            resp.text = html
            resp.headers = {}
            return resp

        capture_post.call_args_captured = None
        mock_ui_session.post.side_effect = capture_post
        mock_get_session.return_value = (mock_ui_session, "tok123", None)

        config = _make_config()
        auth_manager = _make_auth_manager()
        params = RunBackgroundScriptParams(script="gs.print('hello world');")

        result = run_background_script(config, auth_manager, params)

        self.assertIsNotNone(
            capture_post.call_args_captured,
            "ui_session.post should have been called",
        )
        _args, _kwargs = capture_post.call_args_captured

        # Assert X-UserToken header present with correct value
        post_headers = _kwargs.get("headers", {})
        self.assertIn(
            "X-UserToken",
            post_headers,
            "X-UserToken must be present in POST headers",
        )
        self.assertEqual(
            post_headers["X-UserToken"],
            "tok123",
            "X-UserToken header must equal the csrf_token",
        )

        # Assert sysparm_ck is NOT in form_data
        form_data = _kwargs.get("data", {})
        self.assertNotIn(
            "sysparm_ck",
            form_data,
            "sysparm_ck must NOT appear in POST form_data (token goes in X-UserToken header)",
        )

    @patch("servicenow_mcp.tools.script_tools._query_syslog")
    @patch("servicenow_mcp.tools.script_tools._get_ui_session")
    def test_no_x_user_token_header_when_csrf_token_missing(self, mock_get_session, mock_query_syslog):
        """When csrf_token is None, headers dict should not contain X-UserToken."""
        mock_query_syslog.return_value = []

        mock_ui_session = MagicMock()

        def capture_post_no_token(*args, **kwargs):
            capture_post_no_token.call_args_captured = (args, kwargs)
            rid_match = __import__("re").search(
                r"\[run_id=([a-f0-9]+)\]", kwargs.get("data", {}).get("sysparm_script", "")
            )
            rid = rid_match.group(1) if rid_match else "unknown"
            html = (
                f"<pre>=== MFCP_START [run_id={rid}] ===\n"
                f"output\n"
                f"=== MFCP_END [run_id={rid}] ===\n</pre>"
            )
            resp = MagicMock()
            resp.status_code = 200
            resp.text = html
            resp.headers = {}
            return resp

        capture_post_no_token.call_args_captured = None
        mock_ui_session.post.side_effect = capture_post_no_token
        mock_get_session.return_value = (mock_ui_session, None, None)

        config = _make_config()
        auth_manager = _make_auth_manager()
        params = RunBackgroundScriptParams(script="gs.print('output');")

        run_background_script(config, auth_manager, params)

        _args, _kwargs = capture_post_no_token.call_args_captured
        post_headers = _kwargs.get("headers", {})
        self.assertNotIn(
            "X-UserToken",
            post_headers,
            "X-UserToken must NOT be present when csrf_token is None",
        )


# ---------------------------------------------------------------------------
# SCRP-03 — non-empty direct_output (integration)
# ---------------------------------------------------------------------------


class TestRunBackgroundScriptDirectOutput(unittest.TestCase):
    """SCRP-03: direct_output must contain actual gs.print() output when session is authenticated."""

    @patch("servicenow_mcp.tools.script_tools._query_syslog")
    @patch("servicenow_mcp.tools.script_tools._get_ui_session")
    def test_direct_output_contains_gs_print_output(self, mock_get_session, mock_query_syslog):
        """direct_output is non-empty and contains the actual gs.print() output."""
        mock_query_syslog.return_value = []

        mock_ui_session = MagicMock()

        def make_response(*args, **kwargs):
            form_data = kwargs.get("data", {})
            script_body = form_data.get("sysparm_script", "")
            import re as _re
            match = _re.search(r"\[run_id=([a-f0-9]+)\]", script_body)
            rid = match.group(1) if match else "unknown"
            html = (
                f"<pre>=== MFCP_START [run_id={rid}] ===\n"
                f"hello from gs.print\n"
                f"=== MFCP_END [run_id={rid}] ===\n</pre>"
            )
            resp = MagicMock()
            resp.status_code = 200
            resp.text = html
            resp.headers = {}
            return resp

        mock_ui_session.post.side_effect = make_response
        mock_get_session.return_value = (mock_ui_session, "some_token", None)

        config = _make_config()
        auth_manager = _make_auth_manager()
        params = RunBackgroundScriptParams(script="gs.print('hello from gs.print');")

        result = run_background_script(config, auth_manager, params)

        self.assertTrue(result.success, f"success should be True, got message: {result.message}")
        self.assertNotEqual(result.direct_output, "", "direct_output must not be empty")
        self.assertNotEqual(
            result.direct_output,
            "(no gs.print() output)",
            "direct_output should contain actual output, not the empty-output placeholder",
        )
        self.assertIn(
            "hello from gs.print",
            result.direct_output,
            "direct_output should contain the actual gs.print() text",
        )


if __name__ == "__main__":
    unittest.main()
