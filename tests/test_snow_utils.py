"""Tests for servicenow_mcp.utils.snow_utils."""

import pytest

from servicenow_mcp.utils.snow_utils import parse_snow_bool
from servicenow_mcp.utils import parse_snow_bool as parse_snow_bool_from_pkg  # noqa: F401


class TestParseSnowBool:
    """Tests for parse_snow_bool."""

    # --- truthy string values ---

    def test_string_true_lowercase(self):
        assert parse_snow_bool("true") is True

    def test_string_one(self):
        assert parse_snow_bool("1") is True

    def test_string_yes_lowercase(self):
        assert parse_snow_bool("yes") is True

    # --- falsy string values ---

    def test_string_false_lowercase(self):
        assert parse_snow_bool("false") is False

    def test_string_zero(self):
        assert parse_snow_bool("0") is False

    def test_string_no_lowercase(self):
        assert parse_snow_bool("no") is False

    def test_empty_string(self):
        assert parse_snow_bool("") is False

    # --- Python bool pass-through ---

    def test_python_true(self):
        assert parse_snow_bool(True) is True

    def test_python_false(self):
        assert parse_snow_bool(False) is False

    # --- None ---

    def test_none_returns_false(self):
        assert parse_snow_bool(None) is False

    # --- case insensitivity ---

    def test_string_true_uppercase(self):
        # The implementation lowercases before comparing, so "TRUE" → True.
        assert parse_snow_bool("TRUE") is True

    def test_string_true_mixed_case(self):
        assert parse_snow_bool("True") is True

    def test_string_yes_uppercase(self):
        assert parse_snow_bool("YES") is True

    # --- whitespace stripping ---

    def test_string_true_with_whitespace(self):
        assert parse_snow_bool("  true  ") is True

    def test_string_false_with_whitespace(self):
        assert parse_snow_bool("  false  ") is False

    # --- non-string, non-bool, non-None values ---

    def test_integer_1(self):
        # int 1 → str "1" → True
        assert parse_snow_bool(1) is True

    def test_integer_0(self):
        # int 0 → str "0" → "0" is NOT in ("true", "1", "yes") → False
        assert parse_snow_bool(0) is False

    def test_arbitrary_string(self):
        assert parse_snow_bool("maybe") is False
