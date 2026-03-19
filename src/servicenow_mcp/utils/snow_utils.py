"""Shared ServiceNow utility functions."""

from typing import Any


def parse_snow_bool(value: Any) -> bool:
    """Normalize a ServiceNow boolean field to a Python bool.

    ServiceNow boolean columns can be returned as the strings "true"/"false",
    "1"/"0", or "Yes"/"No" depending on the sysparm_display_value setting, or
    as actual Python booleans when the caller has already coerced the value.

    Args:
        value: The raw field value from a ServiceNow REST response. May be a
            string, a Python bool, an integer, or None.

    Returns:
        True if the value is a truthy representation ("true", "1", "yes",
        True); False for all other values including None.
    """
    if value is None:
        return False
    return str(value).strip().lower() in ("true", "1", "yes")
