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

import asyncio
import logging
import os
import re
import threading
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
gs.info('MFCP | START | run_id=' + __MFCP_RUN_ID);
try {{{user_script}
}} catch (__mfcp_err) {{
  gs.error('MFCP | EXCEPTION | error=' + __mfcp_err + ' | run_id=' + __MFCP_RUN_ID);
}}
gs.info('MFCP | END | run_id=' + __MFCP_RUN_ID);
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
      3. GET /sys.scripts.do — guard-checks for login redirect, then extracts the
         page-specific CSRF token via (a) hidden input, (b) var g_ck JS variable
         (San Diego+), or (c) X-UserToken response header.

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
# Scripted REST API execution helper
# ---------------------------------------------------------------------------


def _run_via_scripted_api(
    config: ServerConfig,
    auth_manager: AuthManager,
    wrapped_script: str,
    run_id: str,
) -> tuple:
    """
    Execute a wrapped script via the custom Scripted REST API endpoint.

    Basic auth works for REST endpoints, so no UI session is required.
    The endpoint receives the script as JSON, executes it via GlideEvaluator,
    and returns success/error in the response body.

    Args:
        config: Server configuration (must have script_execution_api_resource_path set).
        auth_manager: Authentication manager.
        wrapped_script: MFCP-wrapped JavaScript to execute.
        run_id: Correlation ID for this run.

    Returns:
        (success: bool, error: str | None, http_status: int)
    """
    url = f"{config.instance_url.rstrip('/')}{config.script_execution_api_resource_path}"
    payload = {"script": wrapped_script, "run_id": run_id}

    try:
        response = requests.post(
            url,
            json=payload,
            headers=auth_manager.get_headers(),
            timeout=max(config.timeout, 120),
        )
    except requests.RequestException as e:
        _body = e.response.text[:2000] if getattr(e, "response", None) is not None else ""
        logger.error(
            f"run_background_script | scripted_api request failed | run_id={run_id} | error={e}"
            + (f" | body={_body}" if _body else "")
        )
        return False, str(e), getattr(getattr(e, "response", None), "status_code", 0) or 0

    http_status = response.status_code
    logger.info(
        f"run_background_script | scripted_api returned HTTP {http_status} | run_id={run_id}"
    )

    if not (200 <= http_status < 300):
        _body = response.text[:2000] if response.text else "(empty)"
        logger.error(
            f"run_background_script | scripted_api non-2xx | run_id={run_id}"
            f" | status={http_status} | body={_body}"
        )
        return False, f"HTTP {http_status}: {_body}", http_status

    try:
        data = response.json()
    except Exception:
        logger.warning(
            f"run_background_script | scripted_api non-JSON response | run_id={run_id}"
            f" | preview={response.text[:500]!r}"
        )
        # Treat as success if HTTP 2xx — the script ran even if the response body is malformed
        return True, None, http_status

    if not data.get("success", True):
        error_msg = data.get("error") or "scripted API reported failure"
        logger.error(
            f"run_background_script | scripted_api execution error | run_id={run_id}"
            f" | error={error_msg}"
        )
        return False, error_msg, http_status

    return True, None, http_status


# ---------------------------------------------------------------------------
# Parameter and response models
# ---------------------------------------------------------------------------


class RunBackgroundScriptParams(BaseModel):
    """Parameters for run_background_script."""

    description: str = Field(
        ...,
        description=(
            "1-3 sentence summary of what this script does, what it reads or modifies, "
            "and why it is being run. Shown in the Claude Code tool call display and "
            "prepended to the result so both the invocation and output are self-documenting. "
            "Example: 'Queries sys_hub_flow_version for flow sys_id X to inspect its trigger "
            "payload. Reads payload field only — no writes.'"
        ),
    )
    script: str = Field(
        ...,
        description=(
            "JavaScript server-side script to execute on the ServiceNow instance. "
            "Runs in admin context via sys.scripts.do (same as the Background Script "
            "module in the ServiceNow UI). "
            "OUTPUT — always use gs.info() with the __MFCP_RUN_ID tag for reliable capture: "
            "gs.info('MyModule | value=' + result + ' | run_id=' + __MFCP_RUN_ID). "
            "Tagged entries are extracted from syslog and returned in direct_output. "
            "Do NOT use gs.print() — it is only captured via the sys.scripts.do UI path "
            "and returns no output when the Scripted REST API execution path is active. "
            "The variable __MFCP_RUN_ID is injected at the top of every script automatically."
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
    # Approval gate — suspend if workbench is active
    if os.environ.get("WORKBENCH_URL"):
        _decision_holder: list = []
        _exc_holder: list = []

        def _run():
            try:
                from servicenow_mcp.utils.approval_client import request_approval, ApprovalDecision
                _decision_holder.append(asyncio.run(request_approval(
                    "run_background_script",
                    params.model_dump(),
                    os.environ.get("WORKBENCH_PROJECT_ID", ""),
                )))
            except Exception as e:
                _exc_holder.append(e)

        t = threading.Thread(target=_run, daemon=True)
        t.start()
        t.join(timeout=330)
        if t.is_alive():
            return RunBackgroundScriptResult(
                success=False,
                run_id="",
                http_status=0,
                direct_output="",
                syslog_entries=[],
                message="Approval timed out",
            )
        if _exc_holder:
            raise _exc_holder[0]
        _decision = _decision_holder[0] if _decision_holder else None
        from servicenow_mcp.utils.approval_client import ApprovalDecision
        if _decision is None or _decision != ApprovalDecision.APPROVED:
            return RunBackgroundScriptResult(
                success=False,
                run_id="",
                http_status=0,
                direct_output="",
                syslog_entries=[],
                message="Operation rejected by user",
            )

    run_id = uuid.uuid4().hex[:12]
    script_block = _format_script_code_block(params.script)

    # Indent user script and inject into wrapper
    indented = "\n".join("  " + line for line in params.script.splitlines())
    wrapped = _WRAPPER_TEMPLATE.format(run_id=run_id, user_script=indented)

    start_time = datetime.now(timezone.utc)
    logger.info(
        f"run_background_script | START | run_id={run_id} | scope={params.scope}"
        f" | path={'scripted_api' if config.script_execution_api_resource_path else 'ui_session'}"
    )

    # ------------------------------------------------------------------
    # Branch A: Scripted REST API (preferred — works with service accounts)
    # ------------------------------------------------------------------
    if config.script_execution_api_resource_path:
        success, error, http_status = _run_via_scripted_api(
            config, auth_manager, wrapped, run_id
        )
        syslog_entries = _query_syslog(config, auth_manager, start_time)
        direct_output = _extract_syslog_output(syslog_entries, run_id)

        if not success:
            return RunBackgroundScriptResult(
                success=False,
                run_id=run_id,
                http_status=http_status,
                direct_output=direct_output,
                syslog_entries=syslog_entries,
                message=(
                    f"{params.description}\n"
                    f"Scripted REST API execution failed (run_id={run_id}). "
                    f"HTTP {http_status}. Error: {error or 'none'}\n"
                    f"{script_block}"
                ),
            )

        return RunBackgroundScriptResult(
            success=True,
            run_id=run_id,
            http_status=http_status,
            direct_output=direct_output,
            syslog_entries=syslog_entries,
            message=(
                f"{params.description}\n"
                f"Script executed via Scripted REST API (run_id={run_id}). "
                f"{len(syslog_entries)} syslog entries captured. "
                f"Include '__MFCP_RUN_ID' in gs.info() calls to tag entries for this run.\n"
                f"{script_block}"
            ),
        )

    # ------------------------------------------------------------------
    # Branch B: UI session via sys.scripts.do (fallback)
    # ------------------------------------------------------------------

    # sys.scripts.do is a Jelly UI page — it silently rejects HTTP auth headers
    # (Basic, OAuth) and requires session cookies established via /login.do.
    ui_session, csrf_token, session_failure = _get_ui_session(config, auth_manager)
    logger.info(
        f"run_background_script | ui_session={'ready' if ui_session else 'unavailable'}"
        f" | csrf_token={'present' if csrf_token else 'missing'}"
        f" | run_id={run_id}"
    )

    if ui_session is None and session_failure and "session_not_authenticated" in session_failure:
        return RunBackgroundScriptResult(
            success=False,
            run_id=run_id,
            http_status=0,
            direct_output="",
            syslog_entries=[],
            message=(
                f"{params.description}\n"
                f"Cannot execute script: ServiceNow session is not authenticated. "
                f"sys.scripts.do redirected to the login page. "
                f"Check instance URL and credentials. Details: {session_failure}\n"
                f"{script_block}"
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
                f"{params.description}\n"
                f"Request to sys.scripts.do failed: {str(e)}"
                + (f" | body: {_body}" if _body else "")
                + f"\n{script_block}"
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
                f"{params.description}\n"
                f"sys.scripts.do returned HTTP {http_status} — script may not have "
                f"executed. Raw response preview: {raw_preview}\n"
                f"{script_block}"
            ),
        )

    return RunBackgroundScriptResult(
        success=True,
        run_id=run_id,
        http_status=http_status,
        direct_output=direct_output,
        syslog_entries=syslog_entries,
        message=(
            f"{params.description}\n"
            f"Script executed via sys.scripts.do (run_id={run_id}). "
            f"direct_output has gs.print() results. "
            f"{len(syslog_entries)} syslog entries captured in the execution window "
            f"(may include concurrent instance activity). "
            f"Include '__MFCP_RUN_ID' in gs.info() calls to tag entries for this run.\n"
            f"{script_block}"
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


def _format_script_code_block(script: str) -> str:
    """
    Format the user-provided script as a fenced code block for easier review.

    This is included in the RunBackgroundScriptResult.message so that callers
    can see exactly what was executed without searching logs.
    """
    # Avoid trailing blank lines inside the fence
    body = script.rstrip("\n")
    return "Script:\n```javascript\n" + body + "\n```"


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


def _extract_syslog_output(entries: List[SyslogEntry], run_id: str) -> str:
    """
    Extract user-visible output from syslog entries tagged with run_id.

    Filters entries whose message contains 'run_id=<run_id>', then strips
    MFCP infrastructure lines (START / END markers). The remainder is the
    user's gs.info/warn/error output from this specific execution.

    Args:
        entries: Syslog entries returned by _query_syslog.
        run_id: The run correlation ID injected into the wrapped script.

    Returns:
        Formatted string of user output lines, or a diagnostic message if
        no matching entries were found.
    """
    tag = f"run_id={run_id}"
    infrastructure = ("MFCP | START |", "MFCP | END |")

    tagged = [e for e in entries if tag in e.message]

    if not tagged:
        return f"(no syslog entries for run_id={run_id})"

    user_lines = [e for e in tagged if not any(e.message.startswith(m) for m in infrastructure)]

    if not user_lines:
        return "(script ran — no gs.info() output with run_id tag)"

    return "\n".join(f"[{e.level.upper()}] {e.message}" for e in user_lines)
