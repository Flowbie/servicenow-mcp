"""
Tests for agile_constants.py — verifies state constant values and StoryIdParams model.
"""

import pytest
from pydantic import ValidationError

from servicenow_mcp.tools.agile_constants import (
    SPRINT_COMPLETED_STATE,
    STORY_BACKLOG_STATES,
    STORY_CANCELLED_STATES,
    STORY_DONE_STATES,
    STORY_IN_PROGRESS_STATES,
    STORY_TERMINAL_STATES,
    StoryIdParams,
)


# ---------------------------------------------------------------------------
# STORY_DONE_STATES
# ---------------------------------------------------------------------------


def test_story_done_states_contains_complete():
    assert "3" in STORY_DONE_STATES


def test_story_done_states_is_set():
    assert isinstance(STORY_DONE_STATES, set)


def test_story_done_states_exact():
    assert STORY_DONE_STATES == {"3"}


# ---------------------------------------------------------------------------
# STORY_CANCELLED_STATES
# ---------------------------------------------------------------------------


def test_story_cancelled_states_contains_cancelled():
    assert "4" in STORY_CANCELLED_STATES


def test_story_cancelled_states_is_set():
    assert isinstance(STORY_CANCELLED_STATES, set)


def test_story_cancelled_states_exact():
    assert STORY_CANCELLED_STATES == {"4"}


# ---------------------------------------------------------------------------
# STORY_IN_PROGRESS_STATES
# ---------------------------------------------------------------------------


def test_story_in_progress_states_contains_in_progress():
    assert "2" in STORY_IN_PROGRESS_STATES


def test_story_in_progress_states_contains_ready_for_testing():
    assert "-7" in STORY_IN_PROGRESS_STATES


def test_story_in_progress_states_contains_testing():
    assert "-8" in STORY_IN_PROGRESS_STATES


def test_story_in_progress_states_is_set():
    assert isinstance(STORY_IN_PROGRESS_STATES, set)


def test_story_in_progress_states_exact():
    assert STORY_IN_PROGRESS_STATES == {"2", "-7", "-8"}


# ---------------------------------------------------------------------------
# STORY_BACKLOG_STATES
# ---------------------------------------------------------------------------


def test_story_backlog_states_contains_draft():
    assert "-6" in STORY_BACKLOG_STATES


def test_story_backlog_states_contains_ready():
    assert "1" in STORY_BACKLOG_STATES


def test_story_backlog_states_is_set():
    assert isinstance(STORY_BACKLOG_STATES, set)


def test_story_backlog_states_exact():
    assert STORY_BACKLOG_STATES == {"-6", "1"}


# ---------------------------------------------------------------------------
# STORY_TERMINAL_STATES
# ---------------------------------------------------------------------------


def test_story_terminal_states_equals_done_union_cancelled():
    assert STORY_TERMINAL_STATES == STORY_DONE_STATES | STORY_CANCELLED_STATES


def test_story_terminal_states_contains_complete():
    assert "3" in STORY_TERMINAL_STATES


def test_story_terminal_states_contains_cancelled():
    assert "4" in STORY_TERMINAL_STATES


def test_story_terminal_states_exact():
    assert STORY_TERMINAL_STATES == {"3", "4"}


def test_story_terminal_states_is_set():
    assert isinstance(STORY_TERMINAL_STATES, set)


# ---------------------------------------------------------------------------
# SPRINT_COMPLETED_STATE
# ---------------------------------------------------------------------------


def test_sprint_completed_state_value():
    assert SPRINT_COMPLETED_STATE == "3"


def test_sprint_completed_state_is_string():
    assert isinstance(SPRINT_COMPLETED_STATE, str)


# ---------------------------------------------------------------------------
# State set disjointness
# ---------------------------------------------------------------------------


def test_done_and_cancelled_are_disjoint():
    assert STORY_DONE_STATES.isdisjoint(STORY_CANCELLED_STATES)


def test_done_and_in_progress_are_disjoint():
    assert STORY_DONE_STATES.isdisjoint(STORY_IN_PROGRESS_STATES)


def test_done_and_backlog_are_disjoint():
    assert STORY_DONE_STATES.isdisjoint(STORY_BACKLOG_STATES)


def test_cancelled_and_in_progress_are_disjoint():
    assert STORY_CANCELLED_STATES.isdisjoint(STORY_IN_PROGRESS_STATES)


def test_cancelled_and_backlog_are_disjoint():
    assert STORY_CANCELLED_STATES.isdisjoint(STORY_BACKLOG_STATES)


def test_in_progress_and_backlog_are_disjoint():
    assert STORY_IN_PROGRESS_STATES.isdisjoint(STORY_BACKLOG_STATES)


# ---------------------------------------------------------------------------
# StoryIdParams
# ---------------------------------------------------------------------------


def test_story_id_params_accepts_story_id():
    params = StoryIdParams(story_id="abc123")
    assert params.story_id == "abc123"


def test_story_id_params_requires_story_id():
    with pytest.raises(ValidationError):
        StoryIdParams()


def test_story_id_params_story_id_is_string():
    params = StoryIdParams(story_id="xyz")
    assert isinstance(params.story_id, str)


def test_story_id_params_accepts_sys_id_format():
    sys_id = "1a2b3c4d5e6f7890abcdef1234567890"
    params = StoryIdParams(story_id=sys_id)
    assert params.story_id == sys_id


def test_story_id_params_rejects_missing_field():
    with pytest.raises(ValidationError) as exc_info:
        StoryIdParams(**{})
    assert "story_id" in str(exc_info.value)
