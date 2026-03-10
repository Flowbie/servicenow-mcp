"""
Tests for agile_sprint_planning_tools.py — recommend_sprint_stories.
"""

from unittest.mock import MagicMock, patch

import pytest

from servicenow_mcp.tools.agile_sprint_planning_tools import (
    RecommendSprintStoriesParams,
    recommend_sprint_stories,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def config():
    cfg = MagicMock()
    cfg.instance_url = "https://test.service-now.com"
    cfg.timeout = 30
    return cfg


@pytest.fixture
def auth_manager():
    am = MagicMock()
    am.get_headers.return_value = {"Authorization": "Basic dGVzdA=="}
    return am


def _sprint_response(capacity=20, state="2", name="Sprint 1"):
    return MagicMock(
        status_code=200,
        json=lambda: {
            "result": {
                "sys_id": "sprint-1",
                "name": name,
                "state": state,
                "capacity": str(capacity),
            }
        },
    )


def _stories_response(stories):
    return MagicMock(
        status_code=200,
        json=lambda: {"result": stories},
    )


def _deps_response(deps):
    return MagicMock(
        status_code=200,
        json=lambda: {"result": deps},
    )


def _make_story(sys_id, number, points=5, priority="2", title="Story"):
    return {
        "sys_id": sys_id,
        "number": number,
        "short_description": title,
        "state": "1",
        "story_points": str(points),
        "priority": priority,
        "epic": "",
        "epic.short_description": "",
        "project": "",
        "project.name": "",
        "assigned_to": "",
        "assigned_to.name": "",
    }


# ---------------------------------------------------------------------------
# TestRecommendSprintStories
# ---------------------------------------------------------------------------


class TestRecommendSprintStories:
    """Tests for recommend_sprint_stories."""

    def test_happy_path_all_recommended(self, config, auth_manager):
        """Stories with clear deps and within capacity are all recommended."""
        params = RecommendSprintStoriesParams(sprint_id="sprint-1")

        stories = [
            _make_story("s1", "STRY0001", points=5, priority="1"),
            _make_story("s2", "STRY0002", points=3, priority="2"),
        ]

        with patch("requests.get") as mock_get:
            mock_get.side_effect = [
                _sprint_response(capacity=20),
                _stories_response(stories),
                _deps_response([]),  # no deps
            ]
            result = recommend_sprint_stories(config, auth_manager, params)

        assert result["success"] is True
        assert len(result["recommended"]) == 2
        assert len(result["blocked"]) == 0
        assert len(result["over_capacity"]) == 0
        assert result["points_allocated"] == 8

    def test_empty_backlog(self, config, auth_manager):
        """Empty backlog returns success with empty lists."""
        params = RecommendSprintStoriesParams(sprint_id="sprint-1")

        with patch("requests.get") as mock_get:
            mock_get.side_effect = [
                _sprint_response(capacity=20),
                _stories_response([]),
            ]
            result = recommend_sprint_stories(config, auth_manager, params)

        assert result["success"] is True
        assert result["recommended"] == []
        assert result["blocked"] == []
        assert result["over_capacity"] == []
        assert result["summary"]["total_evaluated"] == 0

    def test_blocked_story_separated(self, config, auth_manager):
        """Stories with open prerequisites end up in blocked list."""
        params = RecommendSprintStoriesParams(sprint_id="sprint-1")

        stories = [
            _make_story("s1", "STRY0001", points=5, priority="2"),
            _make_story("s2", "STRY0002", points=3, priority="2"),
        ]
        # s2 has an open prereq (state "2" = In Progress, not terminal)
        deps = [
            {
                "dependent_story": "s2",
                "prerequisite_story": "s99",
                "prerequisite_story.state": "2",
                "prerequisite_story.number": "STRY0099",
                "prerequisite_story.short_description": "Prereq story",
            }
        ]

        with patch("requests.get") as mock_get:
            mock_get.side_effect = [
                _sprint_response(capacity=20),
                _stories_response(stories),
                _deps_response(deps),
            ]
            result = recommend_sprint_stories(config, auth_manager, params)

        assert result["success"] is True
        assert len(result["recommended"]) == 1
        assert len(result["blocked"]) == 1
        assert result["blocked"][0]["number"] == "STRY0002"
        assert len(result["blocked"][0]["open_blockers"]) == 1

    def test_terminal_dep_not_blocked(self, config, auth_manager):
        """Prerequisites in Complete or Cancelled state do not block a story."""
        params = RecommendSprintStoriesParams(sprint_id="sprint-1")

        stories = [_make_story("s1", "STRY0001", points=5, priority="2")]
        deps = [
            {
                "dependent_story": "s1",
                "prerequisite_story": "s99",
                "prerequisite_story.state": "3",  # Complete — terminal
                "prerequisite_story.number": "STRY0099",
                "prerequisite_story.short_description": "Done prereq",
            }
        ]

        with patch("requests.get") as mock_get:
            mock_get.side_effect = [
                _sprint_response(capacity=20),
                _stories_response(stories),
                _deps_response(deps),
            ]
            result = recommend_sprint_stories(config, auth_manager, params)

        assert result["success"] is True
        assert len(result["recommended"]) == 1
        assert len(result["blocked"]) == 0

    def test_over_capacity_story_separated(self, config, auth_manager):
        """Stories that would exceed capacity land in over_capacity list."""
        params = RecommendSprintStoriesParams(sprint_id="sprint-1")

        stories = [
            _make_story("s1", "STRY0001", points=8, priority="2"),
            _make_story("s2", "STRY0002", points=8, priority="2"),  # won't fit after s1
        ]

        with patch("requests.get") as mock_get:
            mock_get.side_effect = [
                _sprint_response(capacity=10),
                _stories_response(stories),
                _deps_response([]),
            ]
            result = recommend_sprint_stories(config, auth_manager, params)

        assert result["success"] is True
        assert len(result["recommended"]) == 1
        assert len(result["over_capacity"]) == 1
        assert result["points_allocated"] == 8

    def test_capacity_zero_no_cap(self, config, auth_manager):
        """When capacity is 0, all stories without dep issues are recommended."""
        params = RecommendSprintStoriesParams(sprint_id="sprint-1")

        stories = [
            _make_story("s1", "STRY0001", points=50, priority="2"),
            _make_story("s2", "STRY0002", points=50, priority="2"),
        ]

        with patch("requests.get") as mock_get:
            mock_get.side_effect = [
                _sprint_response(capacity=0),
                _stories_response(stories),
                _deps_response([]),
            ]
            result = recommend_sprint_stories(config, auth_manager, params)

        assert result["success"] is True
        assert len(result["recommended"]) == 2
        assert len(result["over_capacity"]) == 0
        assert result["remaining_capacity"] is None

    def test_capacity_override(self, config, auth_manager):
        """capacity_override takes precedence over sprint.capacity."""
        params = RecommendSprintStoriesParams(
            sprint_id="sprint-1", capacity_override=5
        )

        stories = [
            _make_story("s1", "STRY0001", points=3, priority="2"),
            _make_story("s2", "STRY0002", points=4, priority="2"),
        ]

        with patch("requests.get") as mock_get:
            mock_get.side_effect = [
                _sprint_response(capacity=100),  # sprint says 100 but override is 5
                _stories_response(stories),
                _deps_response([]),
            ]
            result = recommend_sprint_stories(config, auth_manager, params)

        assert result["capacity"] == 5
        assert len(result["recommended"]) == 1
        assert len(result["over_capacity"]) == 1

    def test_priority_ordering(self, config, auth_manager):
        """Critical priority stories rank above High which rank above Moderate."""
        params = RecommendSprintStoriesParams(sprint_id="sprint-1")

        stories = [
            _make_story("s3", "STRY0003", points=2, priority="3"),  # Moderate
            _make_story("s1", "STRY0001", points=2, priority="1"),  # Critical
            _make_story("s2", "STRY0002", points=2, priority="2"),  # High
        ]

        with patch("requests.get") as mock_get:
            mock_get.side_effect = [
                _sprint_response(capacity=100),
                _stories_response(stories),
                _deps_response([]),
            ]
            result = recommend_sprint_stories(config, auth_manager, params)

        numbers = [s["number"] for s in result["recommended"]]
        assert numbers.index("STRY0001") < numbers.index("STRY0002")
        assert numbers.index("STRY0002") < numbers.index("STRY0003")

    def test_objective_keyword_bonus(self, config, auth_manager):
        """Stories matching objective keywords rank higher than priority-equal peers."""
        params = RecommendSprintStoriesParams(
            sprint_id="sprint-1", objectives="login authentication"
        )

        stories = [
            _make_story(
                "s1", "STRY0001", points=2, priority="2", title="Refactor database layer"
            ),
            _make_story(
                "s2", "STRY0002", points=2, priority="2", title="Fix login authentication bug"
            ),
        ]

        with patch("requests.get") as mock_get:
            mock_get.side_effect = [
                _sprint_response(capacity=100),
                _stories_response(stories),
                _deps_response([]),
            ]
            result = recommend_sprint_stories(config, auth_manager, params)

        numbers = [s["number"] for s in result["recommended"]]
        # s2 matches 2 keywords so should rank first despite equal base priority
        assert numbers[0] == "STRY0002"

    def test_sprint_fetch_failure(self, config, auth_manager):
        """Returns failure when sprint fetch fails."""
        import requests as req

        params = RecommendSprintStoriesParams(sprint_id="bad-id")

        with patch("requests.get") as mock_get:
            mock_get.side_effect = req.RequestException("Connection error")
            result = recommend_sprint_stories(config, auth_manager, params)

        assert result["success"] is False
        assert "Failed to fetch sprint" in result["message"]

    def test_backlog_fetch_failure(self, config, auth_manager):
        """Returns failure when backlog story fetch fails."""
        import requests as req

        params = RecommendSprintStoriesParams(sprint_id="sprint-1")

        with patch("requests.get") as mock_get:
            mock_get.side_effect = [
                _sprint_response(),
                MagicMock(
                    raise_for_status=MagicMock(
                        side_effect=req.RequestException("Timeout")
                    )
                ),
            ]
            result = recommend_sprint_stories(config, auth_manager, params)

        assert result["success"] is False
        assert "Failed to fetch backlog" in result["message"]

    def test_dep_fetch_failure_non_fatal(self, config, auth_manager):
        """Dependency fetch failure is non-fatal; stories still recommended."""
        import requests as req

        params = RecommendSprintStoriesParams(sprint_id="sprint-1")

        stories = [_make_story("s1", "STRY0001", points=3, priority="2")]

        dep_mock = MagicMock()
        dep_mock.raise_for_status.side_effect = req.RequestException("Dep error")

        with patch("requests.get") as mock_get:
            mock_get.side_effect = [
                _sprint_response(capacity=20),
                _stories_response(stories),
                dep_mock,
            ]
            result = recommend_sprint_stories(config, auth_manager, params)

        # Should still succeed — deps are treated as clear when data is unavailable
        assert result["success"] is True
        assert len(result["recommended"]) == 1

    def test_summary_counts_correct(self, config, auth_manager):
        """summary block accurately counts each partition."""
        params = RecommendSprintStoriesParams(sprint_id="sprint-1")

        stories = [
            _make_story("s1", "STRY0001", points=5, priority="1"),   # recommended
            _make_story("s2", "STRY0002", points=5, priority="2"),   # blocked
            _make_story("s3", "STRY0003", points=15, priority="2"),  # over capacity
        ]
        deps = [
            {
                "dependent_story": "s2",
                "prerequisite_story": "s99",
                "prerequisite_story.state": "1",  # not terminal
                "prerequisite_story.number": "STRY0099",
                "prerequisite_story.short_description": "Prereq",
            }
        ]

        with patch("requests.get") as mock_get:
            mock_get.side_effect = [
                _sprint_response(capacity=10),
                _stories_response(stories),
                _deps_response(deps),
            ]
            result = recommend_sprint_stories(config, auth_manager, params)

        assert result["summary"]["recommended_count"] == 1
        assert result["summary"]["blocked_count"] == 1
        assert result["summary"]["over_capacity_count"] == 1
        assert result["summary"]["total_evaluated"] == 3
