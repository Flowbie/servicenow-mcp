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
    DeleteArtifactParams,
    ExecutionLogRecordRef,
    GetAnswersParams,
    GetArtifactParams,
    ListArtifactsParams,
    LogExecutionParams,
    PresentArtifactParams,
    PresentQuestionnaireParams,
    QuestionnaireOption,
    QuestionnaireQuestion,
)


WORKBENCH_ENV = {
    "WORKBENCH_MCP_URL": "http://localhost:8001",
    "WORKBENCH_PROJECT_ID": "proj-42",
    "WORKBENCH_CHAT_ID": "chat-7",
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


def test_workbench_project_id_returns_none_for_general_chat():
    """General chats have no project; _project_id() returns None rather than raising."""
    with patch.dict(
        "os.environ",
        {"WORKBENCH_MCP_URL": "http://localhost:8001"},
        clear=True,
    ):
        assert workbench_tools._project_id() is None


def test_workbench_chat_id_required():
    with patch.dict(
        "os.environ",
        {"WORKBENCH_MCP_URL": "http://localhost:8001"},
        clear=True,
    ):
        with pytest.raises(RuntimeError, match="WORKBENCH_CHAT_ID"):
            workbench_tools._chat_id()


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
    assert kwargs["json"]["chat_id"] == "chat-7"
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
# present_artifact
# ---------------------------------------------------------------------------


def test_present_artifact_plan_posts_to_artifacts_endpoint():
    params = PresentArtifactParams(
        type="plan",
        name="PLAN.md",
        content="# Plan\n\nsteps...",
        meta={"story_number": "STRY0082341", "story_name": "Incident Auto-Assignment"},
    )
    mock_post = MagicMock(return_value=_mock_response({"artifact_id": "a-1"}))
    with patch.dict("os.environ", WORKBENCH_ENV, clear=True), \
         patch("servicenow_mcp.tools.workbench_tools.requests.post", mock_post):
        result = workbench_tools.present_artifact(None, None, params)

    assert result == {"artifact_id": "a-1"}
    assert mock_post.call_args[0][0].endswith("/api/workbench_mcp/artifacts")
    _, kwargs = mock_post.call_args
    body = kwargs["json"]
    assert body["project_id"] == "proj-42"
    assert body["chat_id"] == "chat-7"
    assert body["type"] == "plan"
    assert body["name"] == "PLAN.md"
    assert body["meta"]["story_number"] == "STRY0082341"


def test_present_artifact_requires_chat_id_env():
    params = PresentArtifactParams(type="markdown", name="x.md", content="")
    # chat_id absent: should raise before making any HTTP call.
    env_without_chat = {
        "WORKBENCH_MCP_URL": "http://localhost:8001",
        "WORKBENCH_PROJECT_ID": "proj-42",
    }
    with patch.dict("os.environ", env_without_chat, clear=True):
        with pytest.raises(RuntimeError, match="WORKBENCH_CHAT_ID"):
            workbench_tools.present_artifact(None, None, params)


def test_present_artifact_general_chat_sends_null_project():
    """General chat: WORKBENCH_PROJECT_ID unset, chat_id present. Tool succeeds
    and posts project_id=None — backend persists the row chat-scoped only."""
    params = PresentArtifactParams(type="code", name="hello.js", content="x")
    env_general = {
        "WORKBENCH_MCP_URL": "http://localhost:8001",
        "WORKBENCH_CHAT_ID": "chat-general",
    }
    mock_post = MagicMock(return_value=_mock_response({"artifact_id": "a-gen"}))
    with patch.dict("os.environ", env_general, clear=True), \
         patch("servicenow_mcp.tools.workbench_tools.requests.post", mock_post):
        result = workbench_tools.present_artifact(None, None, params)

    assert result == {"artifact_id": "a-gen"}
    body = mock_post.call_args.kwargs["json"]
    assert body["chat_id"] == "chat-general"
    assert body["project_id"] is None


def test_present_artifact_omits_meta_when_none():
    params = PresentArtifactParams(
        type="code",
        name="backfill.js",
        content="var x = 1;",
    )
    mock_post = MagicMock(return_value=_mock_response({"artifact_id": "a-2"}))
    with patch.dict("os.environ", WORKBENCH_ENV, clear=True), \
         patch("servicenow_mcp.tools.workbench_tools.requests.post", mock_post):
        workbench_tools.present_artifact(None, None, params)

    body = mock_post.call_args.kwargs["json"]
    assert "meta" not in body


def test_present_artifact_rejects_unknown_type():
    with pytest.raises(ValueError):
        PresentArtifactParams(type="pdf", name="x.pdf", content="")  # type: ignore[arg-type]


def test_present_artifact_returns_error_on_network_failure():
    params = PresentArtifactParams(type="markdown", name="notes.md", content="hi")
    mock_post = MagicMock(side_effect=requests.ConnectionError("boom"))
    with patch.dict("os.environ", WORKBENCH_ENV, clear=True), \
         patch("servicenow_mcp.tools.workbench_tools.requests.post", mock_post):
        result = workbench_tools.present_artifact(None, None, params)

    assert result["status"] == "error"
    assert "boom" in result["error"]


# ---------------------------------------------------------------------------
# get_artifact
# ---------------------------------------------------------------------------


def test_get_artifact_returns_current_content():
    params = GetArtifactParams(name="hello.js", type="code")
    payload = {
        "artifact_id": "a-42",
        "artifact_type": "code",
        "name": "hello.js",
        "content": "// latest from UI",
        "meta": None,
        "source": "user",
        "created_at": "2026-04-22T10:00:00",
        "updated_at": "2026-04-22T10:05:00",
    }
    mock_get = MagicMock(return_value=_mock_response(payload))
    with patch.dict("os.environ", WORKBENCH_ENV, clear=True), \
         patch("servicenow_mcp.tools.workbench_tools.requests.get", mock_get):
        result = workbench_tools.get_artifact(None, None, params)

    assert result["content"] == "// latest from UI"
    _, kwargs = mock_get.call_args
    assert kwargs["params"]["chat_id"] == "chat-7"
    assert kwargs["params"]["name"] == "hello.js"
    assert kwargs["params"]["type"] == "code"
    assert mock_get.call_args[0][0].endswith("/api/workbench_mcp/artifacts/by-name")


def test_get_artifact_returns_not_found_on_404():
    params = GetArtifactParams(name="nope.js", type="code")
    mock_get = MagicMock(return_value=_mock_response({}, status_code=404))
    with patch.dict("os.environ", WORKBENCH_ENV, clear=True), \
         patch("servicenow_mcp.tools.workbench_tools.requests.get", mock_get):
        result = workbench_tools.get_artifact(None, None, params)

    assert result["status"] == "not_found"
    assert result["name"] == "nope.js"


def test_get_artifact_returns_error_on_network_failure():
    params = GetArtifactParams(name="x.md", type="markdown")
    mock_get = MagicMock(side_effect=requests.ConnectionError("boom"))
    with patch.dict("os.environ", WORKBENCH_ENV, clear=True), \
         patch("servicenow_mcp.tools.workbench_tools.requests.get", mock_get):
        result = workbench_tools.get_artifact(None, None, params)

    assert result["status"] == "error"
    assert "boom" in result["error"]


# ---------------------------------------------------------------------------
# list_artifacts
# ---------------------------------------------------------------------------


def test_list_artifacts_returns_all_items():
    items = [
        {"artifact_id": "1", "artifact_type": "code", "name": "a.js"},
        {"artifact_id": "2", "artifact_type": "markdown", "name": "b.md"},
    ]
    mock_get = MagicMock(return_value=_mock_response(items))
    with patch.dict("os.environ", WORKBENCH_ENV, clear=True), \
         patch("servicenow_mcp.tools.workbench_tools.requests.get", mock_get):
        result = workbench_tools.list_artifacts(None, None, ListArtifactsParams())

    assert result["count"] == 2
    assert len(result["artifacts"]) == 2
    assert mock_get.call_args.kwargs["params"]["chat_id"] == "chat-7"


def test_list_artifacts_filters_by_type():
    items = [
        {"artifact_id": "1", "artifact_type": "code", "name": "a.js"},
        {"artifact_id": "2", "artifact_type": "markdown", "name": "b.md"},
        {"artifact_id": "3", "artifact_type": "code", "name": "c.js"},
    ]
    mock_get = MagicMock(return_value=_mock_response(items))
    with patch.dict("os.environ", WORKBENCH_ENV, clear=True), \
         patch("servicenow_mcp.tools.workbench_tools.requests.get", mock_get):
        result = workbench_tools.list_artifacts(
            None, None, ListArtifactsParams(type_filter="code")
        )

    assert result["count"] == 2
    assert {a["name"] for a in result["artifacts"]} == {"a.js", "c.js"}


def test_list_artifacts_returns_error_on_network_failure():
    mock_get = MagicMock(side_effect=requests.ConnectionError("boom"))
    with patch.dict("os.environ", WORKBENCH_ENV, clear=True), \
         patch("servicenow_mcp.tools.workbench_tools.requests.get", mock_get):
        result = workbench_tools.list_artifacts(None, None, ListArtifactsParams())

    assert result["status"] == "error"


# ---------------------------------------------------------------------------
# delete_artifact
# ---------------------------------------------------------------------------


def test_delete_artifact_resolves_then_deletes():
    params = DeleteArtifactParams(name="hello.js", type="code")
    lookup_resp = _mock_response({"artifact_id": "a-42", "name": "hello.js"})
    delete_resp = _mock_response({"artifact_id": "a-42", "name": "hello.js", "deleted": True})
    mock_get = MagicMock(return_value=lookup_resp)
    mock_delete = MagicMock(return_value=delete_resp)
    with patch.dict("os.environ", WORKBENCH_ENV, clear=True), \
         patch("servicenow_mcp.tools.workbench_tools.requests.get", mock_get), \
         patch("servicenow_mcp.tools.workbench_tools.requests.delete", mock_delete):
        result = workbench_tools.delete_artifact(None, None, params)

    assert result["deleted"] is True
    assert mock_get.call_args[0][0].endswith("/api/workbench_mcp/artifacts/by-name")
    assert mock_delete.call_args[0][0].endswith("/api/workbench_mcp/artifacts/a-42")


def test_delete_artifact_returns_not_found_when_lookup_404s():
    params = DeleteArtifactParams(name="gone.js", type="code")
    mock_get = MagicMock(return_value=_mock_response({}, status_code=404))
    mock_delete = MagicMock()
    with patch.dict("os.environ", WORKBENCH_ENV, clear=True), \
         patch("servicenow_mcp.tools.workbench_tools.requests.get", mock_get), \
         patch("servicenow_mcp.tools.workbench_tools.requests.delete", mock_delete):
        result = workbench_tools.delete_artifact(None, None, params)

    assert result["status"] == "not_found"
    mock_delete.assert_not_called()


def test_delete_artifact_returns_error_on_network_failure():
    params = DeleteArtifactParams(name="x.js", type="code")
    mock_get = MagicMock(side_effect=requests.ConnectionError("boom"))
    with patch.dict("os.environ", WORKBENCH_ENV, clear=True), \
         patch("servicenow_mcp.tools.workbench_tools.requests.get", mock_get):
        result = workbench_tools.delete_artifact(None, None, params)

    assert result["status"] == "error"


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
    assert body["chat_id"] == "chat-7"
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
