"""Unit tests for workbench_tools.

The tools proxy to WORKBENCH_URL; tests mock `requests` to verify correct
payload construction, env-var gating, and error handling.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests

from servicenow_mcp.tools import workbench_tools
from servicenow_mcp.tools.workbench_tools import (
    ExecutionLogRecordRef,
    GetAnswersParams,
    LogExecutionParams,
    PresentPlanParams,
    PresentQuestionnaireParams,
    QuestionnaireOption,
    QuestionnaireQuestion,
    RequestApprovalParams,
)


WORKBENCH_ENV = {
    "WORKBENCH_MCP_URL": "http://localhost:8001",
    "WORKBENCH_PROJECT_ID": "proj-42",
}


def _mock_response(payload: dict, status_code: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.content = b"x" if payload else b""
    resp.json = MagicMock(return_value=payload)
    resp.raise_for_status = MagicMock()
    return resp


# ---------------------------------------------------------------------------
# env gating
# ---------------------------------------------------------------------------


def test_workbench_url_required():
    with patch.dict("os.environ", {"WORKBENCH_PROJECT_ID": "p"}, clear=True):
        with pytest.raises(RuntimeError, match="WORKBENCH_MCP_URL"):
            workbench_tools._workbench_url()


def test_workbench_project_id_required():
    with patch.dict(
        "os.environ",
        {"WORKBENCH_MCP_URL": "http://localhost:8001"},
        clear=True,
    ):
        with pytest.raises(RuntimeError, match="WORKBENCH_PROJECT_ID"):
            workbench_tools._project_id()


# ---------------------------------------------------------------------------
# present_questionnaire
# ---------------------------------------------------------------------------


def test_present_questionnaire_posts_correctly():
    params = PresentQuestionnaireParams(
        id="story-intake",
        title="Story Intake",
        intro="answer these",
        submit_label="Submit",
        questions=[
            QuestionnaireQuestion(
                id="task_type",
                prompt="What kind of work is this?",
                options=[
                    QuestionnaireOption(id="a", label="Scripting"),
                    QuestionnaireOption(id="b", label="Config"),
                ],
            )
        ],
    )
    mock_post = MagicMock(return_value=_mock_response({"questionnaire_id": "q-1", "warnings": []}))
    with patch.dict("os.environ", WORKBENCH_ENV, clear=True), \
         patch("servicenow_mcp.tools.workbench_tools.requests.post", mock_post):
        result = workbench_tools.present_questionnaire(None, None, params)

    assert result == {"questionnaire_id": "q-1", "warnings": []}
    assert mock_post.call_count == 1
    _, kwargs = mock_post.call_args
    assert kwargs["json"]["project_id"] == "proj-42"
    assert kwargs["json"]["external_id"] == "story-intake"
    assert kwargs["json"]["questions"][0]["prompt"] == "What kind of work is this?"
    assert kwargs["json"]["questions"][0]["options"][0]["label"] == "Scripting"


def test_present_questionnaire_returns_error_on_network_failure():
    params = PresentQuestionnaireParams(
        id="q1", title="Q", questions=[QuestionnaireQuestion(prompt="?")]
    )
    mock_post = MagicMock(side_effect=requests.ConnectionError("boom"))
    with patch.dict("os.environ", WORKBENCH_ENV, clear=True), \
         patch("servicenow_mcp.tools.workbench_tools.requests.post", mock_post):
        result = workbench_tools.present_questionnaire(None, None, params)

    assert result["status"] == "error"
    assert "boom" in result["error"]


# ---------------------------------------------------------------------------
# get_answers (long-poll)
# ---------------------------------------------------------------------------


def test_get_answers_returns_submitted():
    mock_get = MagicMock(
        return_value=_mock_response(
            {
                "status": "submitted",
                "answers": {"task_type": {"option_id": "a"}},
                "compiled_answer": "user picked scripting",
            }
        )
    )
    with patch.dict("os.environ", WORKBENCH_ENV, clear=True), \
         patch("servicenow_mcp.tools.workbench_tools.requests.get", mock_get):
        result = workbench_tools.get_answers(
            None, None, GetAnswersParams(questionnaire_id="q-1", timeout_seconds=5)
        )

    assert result["status"] == "submitted"
    assert result["answers"] == {"task_type": {"option_id": "a"}}
    _, kwargs = mock_get.call_args
    assert kwargs["params"]["timeout_seconds"] == 5
    assert mock_get.call_args[0][0].endswith(
        "/api/workbench_mcp/questionnaires/q-1/answers"
    )


def test_get_answers_returns_timeout_on_http_error():
    mock_get = MagicMock(side_effect=requests.Timeout("read timeout"))
    with patch.dict("os.environ", WORKBENCH_ENV, clear=True), \
         patch("servicenow_mcp.tools.workbench_tools.requests.get", mock_get):
        result = workbench_tools.get_answers(
            None, None, GetAnswersParams(questionnaire_id="q-1", timeout_seconds=1)
        )

    assert result["status"] == "error"
    assert result["answers"] is None


# ---------------------------------------------------------------------------
# present_plan
# ---------------------------------------------------------------------------


def test_present_plan_posts_story_fields():
    params = PresentPlanParams(
        content="# Plan\n\nsteps...",
        story_number="STRY0082341",
        story_name="Incident Auto-Assignment",
    )
    mock_post = MagicMock(return_value=_mock_response({"plan_id": "p-1"}))
    with patch.dict("os.environ", WORKBENCH_ENV, clear=True), \
         patch("servicenow_mcp.tools.workbench_tools.requests.post", mock_post):
        result = workbench_tools.present_plan(None, None, params)

    assert result == {"plan_id": "p-1"}
    _, kwargs = mock_post.call_args
    assert kwargs["json"]["story_number"] == "STRY0082341"
    assert kwargs["json"]["project_id"] == "proj-42"


# ---------------------------------------------------------------------------
# request_approval
# ---------------------------------------------------------------------------


def test_request_approval_approved_status():
    params = RequestApprovalParams(plan_id="p-1", scope="session", timeout_seconds=3)
    mock_post = MagicMock(
        return_value=_mock_response({"status": "approved", "decided_at": "2026-04-18T00:00:00Z"})
    )
    with patch.dict("os.environ", WORKBENCH_ENV, clear=True), \
         patch("servicenow_mcp.tools.workbench_tools.requests.post", mock_post):
        result = workbench_tools.request_approval(None, None, params)

    assert result["status"] == "approved"
    _, kwargs = mock_post.call_args
    assert kwargs["json"]["scope"] == "session"
    assert kwargs["timeout"][1] >= 3  # read timeout >= requested


def test_request_approval_rejected_status():
    params = RequestApprovalParams(plan_id="p-1", timeout_seconds=2)
    mock_post = MagicMock(return_value=_mock_response({"status": "rejected", "decided_at": None}))
    with patch.dict("os.environ", WORKBENCH_ENV, clear=True), \
         patch("servicenow_mcp.tools.workbench_tools.requests.post", mock_post):
        result = workbench_tools.request_approval(None, None, params)

    assert result["status"] == "rejected"


# ---------------------------------------------------------------------------
# log_execution
# ---------------------------------------------------------------------------


def test_log_execution_single_record_normalises_to_records_none():
    params = LogExecutionParams(
        phase="write",
        summary="updated incident priority",
        tool_name="update_record",
        record=ExecutionLogRecordRef(
            table="incident", number="INC0007001", sys_id="abc", url="https://x/incident/abc"
        ),
        verified=True,
    )
    mock_post = MagicMock(return_value=_mock_response({"entry_id": "e-1", "logged_at": "x"}))
    with patch.dict("os.environ", WORKBENCH_ENV, clear=True), \
         patch("servicenow_mcp.tools.workbench_tools.requests.post", mock_post):
        result = workbench_tools.log_execution(None, None, params)

    assert result["entry_id"] == "e-1"
    _, kwargs = mock_post.call_args
    body = kwargs["json"]
    assert body["phase"] == "write"
    assert body["verified"] is True
    assert body["record"]["number"] == "INC0007001"
    assert "records" not in body


def test_log_execution_batch_records():
    params = LogExecutionParams(
        phase="bulk_execution",
        summary="DRY_RUN backfill",
        records=[
            ExecutionLogRecordRef(table="incident", number="INC0007001"),
            ExecutionLogRecordRef(table="incident", number="INC0007002"),
        ],
    )
    mock_post = MagicMock(return_value=_mock_response({"entry_id": "e-2", "logged_at": "y"}))
    with patch.dict("os.environ", WORKBENCH_ENV, clear=True), \
         patch("servicenow_mcp.tools.workbench_tools.requests.post", mock_post):
        result = workbench_tools.log_execution(None, None, params)

    assert result["entry_id"] == "e-2"
    _, kwargs = mock_post.call_args
    body = kwargs["json"]
    assert len(body["records"]) == 2
    assert "record" not in body
