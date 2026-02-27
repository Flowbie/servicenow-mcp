"""
Background script execution tool for the ServiceNow MCP server.

Executes arbitrary JavaScript server-side scripts on the ServiceNow instance
via the sys.scripts.do endpoint (the same mechanism used by the Background
Script module in the ServiceNow UI).

Output capture:
  - Direct (gs.print): extracted from HTML <pre> tags in the HTTP response,
    delimited by injected MFCP_START / MFCP_END markers.
  - System log (gs.info/warn/error): queried from the syslog table using a
    timestamp window that starts just before execution. May include entries
    from concurrent operations on a shared instance.

The variable __MFCP_RUN_ID is injected at the top of every script and can be
included in user log calls to tag entries for this specific run.
"""

import logging
import re
import uuid
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import List, Optional

import requests
from pydantic import BaseModel, Field

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.utils.config import AuthType, ServerConfig

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Script wrapper template
#
# Literal JavaScript braces are escaped as {{ / }} per str.format() rules.
# Format fields: {run_id}, {user_script}
# ---------------------------------------------------------------------------

_WRAPPER_TEMPLATE = """\
var __MFCP_RUN_ID = '{run_id}';
gs.print('=== MFCP_START [run_id=' + __MFCP_RUN_ID + '] ===');
try {{{user_script}
}} catch (__mfcp_err) {{
  gs.print('MFCP_EXCEPTION: ' + __mfcp_err);
}}
gs.print('=== MFCP_END [run_id=' + __MFCP_RUN_ID + '] ===');
gs.info('MFCP | script_complete | run_id=' + __MFCP_RUN_ID);
"""


# ---------------------------------------------------------------------------
# HTML parser — extract <pre> tag contents from sys.scripts.do response
# ---------------------------------------------------------------------------


class _PreTagParser(HTMLParser):
    """Collect text content from every <pre> element in an HTML document."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._in_pre = False
        self._segments: list = []
        self._buf: list = []

    def handle_starttag(self, tag, attrs):
        if tag == "pre":
            self._in_pre = True
            self._buf = []

    def handle_endtag(self, tag):
        if tag == "pre":
            self._in_pre = False
            self._segments.append("".join(self._buf))

    def handle_data(self, data):
        if self._in_pre:
            self._buf.append(data)

    def pre_contents(self) -> list:
        return self._segments


class _HiddenInputParser(HTMLParser):
    """Extract hidden <input> field values from an HTML form."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._inputs: dict = {}

    def handle_starttag(self, tag, attrs):
        if tag == "input":
            attrs_dict = dict(attrs)
            name = attrs_dict.get("name")
            value = attrs_dict.get("value", "")
            if name:
                self._inputs[name] = value

    def get(self, name: str) -> Optional[str]:
        return self._inputs.get(name)


# ---------------------------------------------------------------------------
# UI session helper
# ---------------------------------------------------------------------------


def _get_ui_session(
    config: ServerConfig,
    auth_manager: AuthManager,
) -> tuple:
    """
    Establish an authenticated browser session for UI endpoint access.

    ServiceNow UI pages (sys.scripts.do) silently reject HTTP auth headers
    and return HTTP 200 with empty body. They require session cookies
    established via /login.do.

    Three-step login flow:
      1. GET /login.do — creates base session, returns initial CSRF token in form.
      2. POST /login.do — submits credentials, receives auth cookies.
      3. GET /sys.scripts.do — retrieves the page-specific sysparm_ck for the POST.

    Returns:
        (session, csrf_token, failure_reason): session is a requests.Session with
        auth cookies, csrf_token is the sysparm_ck for the sys.scripts.do POST.
        On failure, returns (None, None, reason_string).
    """
    if auth_manager.config.type != AuthType.BASIC or not auth_manager.config.basic:
        reason = (
            f"auth_type={auth_manager.config.type!r} "
            f"basic={'set' if auth_manager.config.basic else 'None'}"
        )
        logger.warning(
            "run_background_script | UI session login requires basic auth config"
            f" | {reason}"
        )
        return None, None, f"wrong_auth_type: {reason}"

    username = auth_manager.config.basic.username
    password = auth_manager.config.basic.password
    base = config.instance_url.rstrip("/")
    session = requests.Session()

    try:
        # Step 1: GET /login.do — establishes base session + gets initial CSRF token
        get_resp = session.get(f"{base}/login.do", timeout=config.timeout)
        csrf_parser = _HiddenInputParser()
        csrf_parser.feed(get_resp.text)
        initial_ck = csrf_parser.get("sysparm_ck") or ""
        logger.info(
            f"run_background_script | login.do GET | status={get_resp.status_code}"
            f" | initial_ck={'present' if initial_ck else 'missing'}"
        )

        # Step 2: POST /login.do — submit credentials to establish auth session
        login_resp = session.post(
            f"{base}/login.do",
            data={
                "user_name": username,
                "user_password": password,
                "sys_action": "sysverify",
                "sysparm_ck": initial_ck,
            },
            timeout=config.timeout,
        )
        logged_in = login_resp.headers.get("X-Is-Logged-In", "").lower()
        logger.info(
            f"run_background_script | login.do POST | status={login_resp.status_code}"
            f" | X-Is-Logged-In={logged_in}"
        )
        if logged_in == "false":
            logger.warning(
                "run_background_script | session login failed — check credentials"
            )
            return None, None, "login_failed: X-Is-Logged-In=false after POST"

        # Step 3: GET /sys.scripts.do — extract the page-specific CSRF token
        scripts_resp = session.get(f"{base}/sys.scripts.do", timeout=config.timeout)

        # Guard: detect redirect to login page — MUST be first, before any extraction
        if "login.do" in scripts_resp.url or "sysparm_script" not in scripts_resp.text:
            logger.warning(
                "run_background_script | sys.scripts.do returned login page"
                " — session not authenticated"
            )
            return None, None, "session_not_authenticated: sys.scripts.do redirected to login"

        # Attempt 1: legacy hidden input (Jelly-only SN releases — harmless no-op on modern SN)
        scripts_parser = _HiddenInputParser()
        scripts_parser.feed(scripts_resp.text)
        scripts_ck = scripts_parser.get("sysparm_ck")

        # Attempt 2: JS variable extraction (primary fix — San Diego+ SPA delivery)
        if not scripts_ck:
            _ck_match = re.search(r"var\s+g_ck\s*=\s*'([^']+)'", scripts_resp.text)
            if _ck_match:
                scripts_ck = _ck_match.group(1)
                logger.info("run_background_script | sysparm_ck extracted via g_ck JS regex")

        # Attempt 3: X-UserToken response header (last resort — dead on UI pages, costs nothing)
        if not scripts_ck:
            scripts_ck = scripts_resp.headers.get("X-UserToken")

        if scripts_ck:
            logger.info(
                f"run_background_script | UI session ready"
                f" | sysparm_ck_len={len(scripts_ck)}"
            )
        else:
            logger.warning(
                "run_background_script | session established but sysparm_ck not found"
                f" | sys.scripts.do status={scripts_resp.status_code}"
            )
        return session, scripts_ck, None

    except Exception as e:
        logger.warning(f"run_background_script | UI session setup failed | error={e}")
        return None, None, f"exception: {e}"


# ---------------------------------------------------------------------------
# Parameter and response models
# ---------------------------------------------------------------------------


class RunBackgroundScriptParams(BaseModel):
    """Parameters for run_background_script."""

    script: str = Field(
        ...,
        description=(
            "JavaScript server-side script to execute on the ServiceNow instance. "
            "Runs in admin context via sys.scripts.do (same as the Background Script "
            "module in the ServiceNow UI). "
            "Use gs.print() for direct output — it appears in the direct_output field. "
            "Use gs.info()/gs.warn()/gs.error() for structured log output — these are "
            "captured in syslog_entries via a timestamp-window query after execution. "
            "The variable __MFCP_RUN_ID is injected at the top of your script. Include "
            "it in your log calls to tag entries for this run: "
            "gs.info('MyModule | value=' + result + ' | run_id=' + __MFCP_RUN_ID)."
        ),
    )
    scope: str = Field(
        "global",
        description="Transaction scope for script execution. Default: 'global'.",
    )


class SyslogEntry(BaseModel):
    """One syslog record captured after script execution."""

    level: str
    source: Optional[str] = None
    message: str
    created_on: str


class RunBackgroundScriptResult(BaseModel):
    """Result from run_background_script."""

    success: bool
    run_id: str
    http_status: int
    direct_output: str
    syslog_entries: List[SyslogEntry]
    message: str


# ---------------------------------------------------------------------------
# Implementation
# ---------------------------------------------------------------------------


def run_background_script(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: RunBackgroundScriptParams,
) -> RunBackgroundScriptResult:
    """
    Execute a JavaScript background script on the ServiceNow instance.

    Uses sys.scripts.do with a form-encoded body. Returns both direct
    gs.print() output (from HTML response parsing) and system log output
    (from syslog table query).

    Args:
        config: Server configuration.
        auth_manager: Authentication manager.
        params: Script content and scope.

    Returns:
        RunBackgroundScriptResult with direct output and syslog entries.
    """
    run_id = uuid.uuid4().hex[:12]

    # Indent user script and inject into wrapper
    indented = "\n".join("  " + line for line in params.script.splitlines())
    wrapped = _WRAPPER_TEMPLATE.format(run_id=run_id, user_script=indented)

    # Establish an authenticated session for UI endpoint access.
    # sys.scripts.do is a Jelly UI page — it silently rejects HTTP auth headers
    # (Basic, OAuth) and requires session cookies established via /login.do.
    ui_session, csrf_token, session_failure = _get_ui_session(config, auth_manager)

    start_time = datetime.now(timezone.utc)
    logger.info(
        f"run_background_script | START | run_id={run_id} | scope={params.scope}"
        f" | session={'ready' if ui_session else 'unavailable'}"
        f" | csrf_token={'present' if csrf_token else 'missing'}"
    )

    if ui_session is None and session_failure and "session_not_authenticated" in session_failure:
        return RunBackgroundScriptResult(
            success=False,
            run_id=run_id,
            http_status=0,
            direct_output="",
            syslog_entries=[],
            message=(
                f"Cannot execute script: ServiceNow session is not authenticated. "
                f"sys.scripts.do redirected to the login page. "
                f"Check instance URL and credentials. Details: {session_failure}"
            ),
        )

    form_data: dict = {
        "sysparm_track_flag": "true",
        "sysparm_script": wrapped,
        "sysparm_transaction_scope": params.scope,
        # sysparm_ck intentionally absent — token sent as X-UserToken header below
    }

    post_headers: dict = {}
    if csrf_token:
        post_headers["X-UserToken"] = csrf_token

    try:
        if ui_session is not None:
            # Session carries auth cookies — no Authorization header needed.
            # requests sets Content-Type: application/x-www-form-urlencoded automatically.
            response = ui_session.post(
                f"{config.instance_url.rstrip('/')}/sys.scripts.do",
                data=form_data,
                headers=post_headers,
                timeout=max(config.timeout, 120),
            )
        else:
            # Fallback: attempt without session (will likely return empty body for UI endpoints)
            auth_headers = auth_manager.get_headers()
            fallback_headers = {}
            if "Authorization" in auth_headers:
                fallback_headers["Authorization"] = auth_headers["Authorization"]
            fallback_headers.update(post_headers)
            response = requests.post(
                f"{config.instance_url.rstrip('/')}/sys.scripts.do",
                data=form_data,
                headers=fallback_headers,
                timeout=max(config.timeout, 120),
            )
    except requests.RequestException as e:
        _body = e.response.text[:2000] if getattr(e, "response", None) is not None else ""
        logger.error(
            f"run_background_script | request failed | run_id={run_id} | error={e}"
            + (f" | body={_body}" if _body else "")
        )
        return RunBackgroundScriptResult(
            success=False,
            run_id=run_id,
            http_status=getattr(getattr(e, "response", None), "status_code", 0) or 0,
            direct_output="",
            syslog_entries=[],
            message=(
                f"Request to sys.scripts.do failed: {str(e)}"
                + (f" | body: {_body}" if _body else "")
            ),
        )

    http_status = response.status_code
    logger.info(
        f"run_background_script | sys.scripts.do returned HTTP {http_status} "
        f"| run_id={run_id}"
    )

    direct_output = _extract_direct_output(response.text, run_id)
    # When body is empty, surface CSRF status and response headers so the cause
    # is visible in the tool result without needing server-side logs.
    if not response.text:
        resp_headers_preview = dict(list(response.headers.items())[:12])
        csrf_status = (
            f"present (len={len(csrf_token)})" if csrf_token else "missing"
        )
        direct_output += (
            f"\n[debug | csrf={csrf_status}"
            f" | session_failure={session_failure!r}"
            f" | response_headers={resp_headers_preview}]"
        )
    syslog_entries = _query_syslog(config, auth_manager, start_time)

    if not (200 <= http_status < 300):
        raw_preview = response.text[:1000] if response.text else "(empty response)"
        return RunBackgroundScriptResult(
            success=False,
            run_id=run_id,
            http_status=http_status,
            direct_output=direct_output,
            syslog_entries=syslog_entries,
            message=(
                f"sys.scripts.do returned HTTP {http_status} — script may not have "
                f"executed. Raw response preview: {raw_preview}"
            ),
        )

    return RunBackgroundScriptResult(
        success=True,
        run_id=run_id,
        http_status=http_status,
        direct_output=direct_output,
        syslog_entries=syslog_entries,
        message=(
            f"Script executed (run_id={run_id}). "
            f"direct_output has gs.print() results. "
            f"{len(syslog_entries)} syslog entries captured in the execution window "
            f"(may include concurrent instance activity). "
            f"Include '__MFCP_RUN_ID' in gs.info() calls to tag entries for this run."
        ),
    )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _extract_direct_output(html: str, run_id: str) -> str:
    """
    Parse HTML from sys.scripts.do and extract content between MFCP markers.

    Falls back to returning all <pre> tag content if markers are not found
    (e.g. when sys.scripts.do returns an error page rather than script output).
    """
    parser = _PreTagParser()
    parser.feed(html)
    full_text = "\n".join(parser.pre_contents())

    start_marker = f"=== MFCP_START [run_id={run_id}] ==="
    end_marker = f"=== MFCP_END [run_id={run_id}] ==="

    start_idx = full_text.find(start_marker)
    end_idx = full_text.find(end_marker)

    if start_idx != -1 and end_idx != -1:
        between = full_text[start_idx + len(start_marker) : end_idx].strip()
        return between if between else "(no gs.print() output)"

    # Markers not found — log HTML preview for diagnosis and surface in return value
    logger.warning(
        f"run_background_script | MFCP markers not found | run_id={run_id}"
        f" | html_preview={html[:500]!r}"
    )
    stripped = full_text.strip()
    if stripped:
        return f"(MFCP markers missing — raw <pre> content follows)\n{stripped}"
    return f"(no output in HTML — markers missing | html_preview={html[:300]!r})"


def _query_syslog(
    config: ServerConfig,
    auth_manager: AuthManager,
    start_time: datetime,
) -> List[SyslogEntry]:
    """
    Query the syslog table for entries written at or after start_time.

    Background scripts execute synchronously within the HTTP transaction, so
    all gs.info/warn/error calls are committed by the time this query runs.
    The timestamp window may include entries from concurrent instance activity.
    """
    ts = start_time.strftime("%Y-%m-%d %H:%M:%S")
    try:
        response = requests.get(
            f"{config.api_url}/table/syslog",
            params={
                "sysparm_query": f"sys_created_on>={ts}",
                "sysparm_fields": "level,source,message,sys_created_on",
                "sysparm_limit": 200,
                "sysparm_orderby": "sys_created_on",
            },
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()
        records = response.json().get("result", [])
        return [
            SyslogEntry(
                level=r.get("level", ""),
                source=r.get("source"),
                message=r.get("message", ""),
                created_on=r.get("sys_created_on", ""),
            )
            for r in records
        ]
    except Exception as e:
        _resp_preview = ""
        if hasattr(e, "response") and e.response is not None:
            _resp_preview = e.response.text[:500]
        logger.warning(
            f"run_background_script | syslog query failed | error={e}"
            + (f" | body={_resp_preview}" if _resp_preview else "")
        )
        return []
