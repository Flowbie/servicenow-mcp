"""
Workbench-MCP tools.

When `WORKBENCH_MCP_URL` is set (Workbench spawns this MCP with it populated),
these tools proxy to the Workbench FastAPI backend to present questionnaires/
plans, collect answers, request plan approval, and append execution-log entries.

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
from typing import Any, Dict, List, Optional

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


class PresentPlanParams(BaseModel):
    """Parameters for workbench_present_plan."""

    content: str = Field(..., description="Full PLAN.md markdown content.")
    story_number: str = Field(..., description="Story number, e.g. 'STRY0082341'.")
    story_name: str = Field(..., description="Short human-readable story title.")


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


def present_plan(
    config: ServerConfig,  # noqa: ARG001
    auth_manager: AuthManager,  # noqa: ARG001
    params: PresentPlanParams,
) -> Dict[str, Any]:
    body = {
        "project_id": _project_id(),
        "content": params.content,
        "story_number": params.story_number,
        "story_name": params.story_name,
    }
    return _post_json("/api/workbench_mcp/plans", body)


def log_execution(
    config: ServerConfig,  # noqa: ARG001
    auth_manager: AuthManager,  # noqa: ARG001
    params: LogExecutionParams,
) -> Dict[str, Any]:
    body: Dict[str, Any] = {
        "project_id": _project_id(),
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


def _project_id() -> str:
    pid = os.environ.get("WORKBENCH_PROJECT_ID")
    if not pid:
        raise RuntimeError(
            "WORKBENCH_PROJECT_ID is not set; the workbench tool package requires "
            "the Workbench backend to spawn this MCP with WORKBENCH_PROJECT_ID in env."
        )
    return pid


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
