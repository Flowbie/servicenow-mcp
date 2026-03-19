"""
Shared Pydantic models and state constants for agile tool files.

These values are used across agile_planning_tools, agile_governance_tools,
agile_reporting_tools, sprint_tools, and release_tools. Centralising them
here eliminates duplication and provides a single source of truth.

State references (rm_story.state):
  -6  Draft
   1  Ready
   2  In Progress
  -7  Ready for Testing
  -8  Testing
   3  Complete
   4  Cancelled

State references (rm_sprint_2.state):
   1  Planning
   2  Active
   3  Completed
   4  Cancelled
"""

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Shared Pydantic model
# ---------------------------------------------------------------------------


class StoryIdParams(BaseModel):
    """Parameters for operations requiring a story ID."""

    story_id: str = Field(
        ...,
        description="sys_id of the rm_story record.",
    )


# ---------------------------------------------------------------------------
# rm_story state constants
# ---------------------------------------------------------------------------

STORY_DONE_STATES = {"3"}           # Complete
STORY_CANCELLED_STATES = {"4"}      # Cancelled
STORY_IN_PROGRESS_STATES = {"2", "-7", "-8"}  # In Progress, Ready for Testing, Testing
STORY_BACKLOG_STATES = {"-6", "1"}  # Draft, Ready

# Union of done + cancelled — "terminal" means no further state transitions expected
STORY_TERMINAL_STATES = STORY_DONE_STATES | STORY_CANCELLED_STATES  # {"3", "4"}

# ---------------------------------------------------------------------------
# rm_sprint_2 state constants
# ---------------------------------------------------------------------------

SPRINT_COMPLETED_STATE = "3"        # Completed
