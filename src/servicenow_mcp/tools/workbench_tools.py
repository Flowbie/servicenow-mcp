"""
Workbench-MCP tools.

When `WORKBENCH_MCP_URL` is set (Workbench spawns this MCP with it populated),
these tools proxy to the Workbench FastAPI backend to present questionnaires
and artifacts (plans, code, markdown, etc.), collect answers, and append
execution-log entries.

Note on env vars: the legacy `WORKBENCH_URL` (consumed by approval_client.py
for MCP-side write-tool approval) is deliberately distinct from
`WORKBENCH_MCP_URL`. Keeping them separate lets the workbench UI tool surface
work in WSL2 (where WORKBENCH_URL is stripped to avoid double approvals with
the SDK-side can_use_tool gate, but WORKBENCH_MCP_URL can be host-IP
translated and safely carried through). See ADR-0002 for detail.

When `WORKBENCH_MCP_URL` is unset (direct CLI / non-Workbench consumer) the
tools still register but every call raises a structured error so a
misconfigured session fails loud rather than corrupting state.

Tools in this module do NOT call ServiceNow. The `config` and `auth_manager`
arguments are accepted to match the uniform tool signature but are unused.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Literal, Optional

import requests
from pydantic import BaseModel, Field

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.utils.config import ServerConfig

logger = logging.getLogger(__name__)


_CONNECT_TIMEOUT = 5.0
_NETWORK_BUDGET = 30.0  # extra seconds on top of the long-poll budget


# ---------------------------------------------------------------------------
# shared models
# ---------------------------------------------------------------------------


class QuestionnaireOption(BaseModel):
    id: Optional[str] = Field(
        default=None, description="Stable option id. Auto-generated if omitted."
    )
    label: str = Field(..., description="Visible option label.")
    description: Optional[str] = Field(
        default=None, description="Optional per-option hint text."
    )


class QuestionnaireQuestion(BaseModel):
    id: Optional[str] = Field(
        default=None, description="Stable question id. Auto-generated if omitted."
    )
    prompt: str = Field(..., description="The question text shown to the user.")
    help_text: Optional[str] = Field(
        default=None, description="Optional sub-prompt / hint."
    )
    required: bool = Field(default=True, description="Whether the user must answer.")
    allow_free_text: bool = Field(
        default=False,
        description="Allow the user to type a free-text answer in addition to options.",
    )
    options: List[QuestionnaireOption] = Field(
        default_factory=list, description="Mutually-exclusive options (2–4 recommended)."
    )


class ExecutionLogRecordRef(BaseModel):
    table: Optional[str] = None
    sys_id: Optional[str] = None
    number: Optional[str] = None
    url: Optional[str] = None


# ---------------------------------------------------------------------------
# tool params
# ---------------------------------------------------------------------------


class PresentQuestionnaireParams(BaseModel):
    """Parameters for workbench_present_questionnaire."""

    id: str = Field(
        ...,
        description=(
            "External (Claude-chosen) questionnaire id, e.g. 'story-intake'. "
            "Used for display and round-tripping; not the primary key."
        ),
    )
    title: str = Field(..., description="Questionnaire title shown to the user.")
    questions: List[QuestionnaireQuestion] = Field(
        ..., description="List of questions to present."
    )
    intro: Optional[str] = Field(
        default=None, description="Optional multi-line intro shown above the questions."
    )
    submit_label: Optional[str] = Field(
        default=None, description="Optional submit button label (default: 'Submit')."
    )


class GetAnswersParams(BaseModel):
    """Parameters for workbench_get_answers."""

    questionnaire_id: str = Field(
        ..., description="The questionnaire_id returned by workbench_present_questionnaire."
    )
    timeout_seconds: int = Field(
        default=600,
        ge=1,
        le=3600,
        description="Max seconds to block waiting for the user to submit answers.",
    )


ArtifactType = Literal["plan", "mermaid", "code", "json", "markdown"]


class PresentArtifactParams(BaseModel):
    """Parameters for workbench_present_artifact."""

    type: ArtifactType = Field(
        ...,
        description=(
            "Artifact kind. Drives the right-rail icon and the renderer used in the "
            "Artifact viewer: 'plan' (PLAN.md, rendered as markdown with story header), "
            "'mermaid' (diagram source), 'code' (syntax-highlighted; pass meta.language), "
            "'json' (pretty-printed), 'markdown' (freeform docs)."
        ),
    )
    name: str = Field(
        ...,
        description=(
            "Plain filename shown to the user, e.g. 'PLAN.md', 'flow.mmd', "
            "'backfill.js'. No path separators — the backend rejects names containing "
            "'/', '\\\\', or '..'."
        ),
    )
    content: str = Field(..., description="Full artifact body as a string.")
    meta: Optional[Dict[str, Any]] = Field(
        default=None,
        description=(
            "Optional renderer hints. For type='plan': {story_number, story_name} "
            "populate the plan header. For type='code': {language} selects the "
            "syntax-highlighter grammar."
        ),
    )


class GetArtifactParams(BaseModel):
    """Parameters for workbench_get_artifact."""

    name: str = Field(
        ...,
        description=(
            "Exact artifact name as it appears in the right-rail list "
            "(e.g. 'PLAN.md', 'hello_world_dryrun.js')."
        ),
    )
    type: ArtifactType = Field(
        ...,
        description=(
            "Artifact kind. Must match the type the artifact was created with "
            "— (chat_id, type, name) is the upsert key."
        ),
    )


class ListArtifactsParams(BaseModel):
    """Parameters for workbench_list_artifacts."""

    type_filter: Optional[ArtifactType] = Field(
        default=None,
        description=(
            "Optional: restrict results to one artifact type. Omit to list "
            "every artifact in the current chat."
        ),
    )


class DeleteArtifactParams(BaseModel):
    """Parameters for workbench_delete_artifact."""

    name: str = Field(
        ...,
        description="Exact artifact name to delete.",
    )
    type: ArtifactType = Field(
        ...,
        description="Artifact kind (must match the original create call).",
    )


class LogExecutionParams(BaseModel):
    """Parameters for workbench_log_execution."""

    phase: str = Field(
        ...,
        description=(
            "Phase label, e.g. 'write', 'bulk_execution', 'validation'. "
            "Use 'bulk_execution' when `records` carries a batch."
        ),
    )
    summary: str = Field(
        ..., description="One-line human summary of what was done."
    )
    tool_name: Optional[str] = Field(
        default=None, description="Name of the ServiceNow MCP tool that performed the write."
    )
    record: Optional[ExecutionLogRecordRef] = Field(
        default=None,
        description="Single record touched. Use for single-row writes.",
    )
    records: Optional[List[ExecutionLogRecordRef]] = Field(
        default=None,
        description="Batch of records touched. Use for DRY_RUN bulk runs.",
    )
    verified: Optional[bool] = Field(
        default=None,
        description="Whether the write was verified via verify_fields / sys_mod_count.",
    )
    notes: Optional[str] = Field(
        default=None, description="Optional freeform notes (appended below the summary)."
    )


# ---------------------------------------------------------------------------
# tool implementations
# ---------------------------------------------------------------------------


def present_questionnaire(
    config: ServerConfig,  # noqa: ARG001 (uniform signature)
    auth_manager: AuthManager,  # noqa: ARG001
    params: PresentQuestionnaireParams,
) -> Dict[str, Any]:
    body = {
        "project_id": _project_id(),
        "chat_id": _chat_id(),
        "external_id": params.id,
        "title": params.title,
        "questions": [q.model_dump(exclude_none=True) for q in params.questions],
        "intro": params.intro,
        "submit_label": params.submit_label,
    }
    return _post_json("/api/workbench_mcp/questionnaires", body)


def get_answers(
    config: ServerConfig,  # noqa: ARG001
    auth_manager: AuthManager,  # noqa: ARG001
    params: GetAnswersParams,
) -> Dict[str, Any]:
    url = f"{_workbench_url()}/api/workbench_mcp/questionnaires/{params.questionnaire_id}/answers"
    try:
        resp = requests.get(
            url,
            params={"timeout_seconds": params.timeout_seconds},
            timeout=(_CONNECT_TIMEOUT, params.timeout_seconds + _NETWORK_BUDGET),
        )
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as exc:
        logger.error("workbench_get_answers failed: %s", exc)
        return {"status": "error", "answers": None, "error": str(exc)}


def present_artifact(
    config: ServerConfig,  # noqa: ARG001
    auth_manager: AuthManager,  # noqa: ARG001
    params: PresentArtifactParams,
) -> Dict[str, Any]:
    body: Dict[str, Any] = {
        "project_id": _project_id(),
        "chat_id": _chat_id(),
        "type": params.type,
        "name": params.name,
        "content": params.content,
    }
    if params.meta is not None:
        body["meta"] = params.meta
    return _post_json("/api/workbench_mcp/artifacts", body)


def get_artifact(
    config: ServerConfig,  # noqa: ARG001 (uniform signature)
    auth_manager: AuthManager,  # noqa: ARG001
    params: GetArtifactParams,
) -> Dict[str, Any]:
    """Fetch the current content of an artifact by (name, type).

    Returns the latest persisted content — useful when the user has edited
    the artifact in the Workbench UI and the agent needs the updated version
    rather than its stale in-memory copy.
    """
    url = f"{_workbench_url()}/api/workbench_mcp/artifacts/by-name"
    try:
        resp = requests.get(
            url,
            params={"chat_id": _chat_id(), "name": params.name, "type": params.type},
            timeout=(_CONNECT_TIMEOUT, 30.0),
        )
        if resp.status_code == 404:
            return {"status": "not_found", "name": params.name, "type": params.type}
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as exc:
        logger.error("workbench_get_artifact failed: %s", exc)
        return {"status": "error", "error": str(exc)}


def list_artifacts(
    config: ServerConfig,  # noqa: ARG001
    auth_manager: AuthManager,  # noqa: ARG001
    params: ListArtifactsParams,
) -> Dict[str, Any]:
    """List artifacts in the current chat, optionally filtered by type."""
    url = f"{_workbench_url()}/api/workbench_mcp/artifacts"
    try:
        resp = requests.get(
            url,
            params={"chat_id": _chat_id()},
            timeout=(_CONNECT_TIMEOUT, 30.0),
        )
        resp.raise_for_status()
        items = resp.json()
    except requests.RequestException as exc:
        logger.error("workbench_list_artifacts failed: %s", exc)
        return {"status": "error", "error": str(exc)}
    if params.type_filter is not None:
        items = [it for it in items if it.get("artifact_type") == params.type_filter]
    return {"artifacts": items, "count": len(items)}


def delete_artifact(
    config: ServerConfig,  # noqa: ARG001
    auth_manager: AuthManager,  # noqa: ARG001
    params: DeleteArtifactParams,
) -> Dict[str, Any]:
    """Delete an artifact by (name, type). Resolves the id server-side."""
    base = _workbench_url()
    chat_id = _chat_id()
    try:
        lookup = requests.get(
            f"{base}/api/workbench_mcp/artifacts/by-name",
            params={"chat_id": chat_id, "name": params.name, "type": params.type},
            timeout=(_CONNECT_TIMEOUT, 30.0),
        )
        if lookup.status_code == 404:
            return {"status": "not_found", "name": params.name, "type": params.type}
        lookup.raise_for_status()
        artifact_id = lookup.json()["artifact_id"]
        delete_resp = requests.delete(
            f"{base}/api/workbench_mcp/artifacts/{artifact_id}",
            timeout=(_CONNECT_TIMEOUT, 30.0),
        )
        delete_resp.raise_for_status()
        return delete_resp.json()
    except requests.RequestException as exc:
        logger.error("workbench_delete_artifact failed: %s", exc)
        return {"status": "error", "error": str(exc)}


def log_execution(
    config: ServerConfig,  # noqa: ARG001
    auth_manager: AuthManager,  # noqa: ARG001
    params: LogExecutionParams,
) -> Dict[str, Any]:
    body: Dict[str, Any] = {
        "project_id": _project_id(),
        "chat_id": _chat_id(),
        "phase": params.phase,
        "summary": params.summary,
    }
    if params.tool_name is not None:
        body["tool_name"] = params.tool_name
    if params.record is not None:
        body["record"] = params.record.model_dump(exclude_none=True)
    if params.records is not None:
        body["records"] = [r.model_dump(exclude_none=True) for r in params.records]
    if params.verified is not None:
        body["verified"] = params.verified
    if params.notes is not None:
        body["notes"] = params.notes
    return _post_json("/api/workbench_mcp/execution_log", body)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _workbench_url() -> str:
    url = os.environ.get("WORKBENCH_MCP_URL")
    if not url:
        raise RuntimeError(
            "WORKBENCH_MCP_URL is not set; this tool is only usable inside a "
            "Workbench session that spawns servicenow-mcp with WORKBENCH_MCP_URL "
            "pointing at the Workbench backend."
        )
    return url.rstrip("/")


def _project_id() -> Optional[str]:
    """Return the current project_id, or None for a general chat.

    General chats have no project, so `WORKBENCH_PROJECT_ID` is unset or
    empty. The workbench tool surface still works in that case — artifacts,
    questionnaires, and execution-log rows are chat-scoped — so this helper
    returns None rather than raising. `_chat_id()` is the required key.
    """
    pid = os.environ.get("WORKBENCH_PROJECT_ID")
    return pid if pid else None


def _chat_id() -> str:
    cid = os.environ.get("WORKBENCH_CHAT_ID")
    if not cid:
        raise RuntimeError(
            "WORKBENCH_CHAT_ID is not set; required for backend broadcasts to reach "
            "the subscribed WebSocket (which is keyed by chat_id, not project_id)."
        )
    return cid


def _post_json(
    path: str, body: Dict[str, Any], *, read_timeout: float = 30.0
) -> Dict[str, Any]:
    url = f"{_workbench_url()}{path}"
    try:
        resp = requests.post(url, json=body, timeout=(_CONNECT_TIMEOUT, read_timeout))
        resp.raise_for_status()
        if resp.status_code == 204 or not resp.content:
            return {"ok": True}
        return resp.json()
    except requests.RequestException as exc:
        logger.error("workbench_mcp POST %s failed: %s", path, exc)
        return {"status": "error", "error": str(exc)}
