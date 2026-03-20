# tests/conftest.py
import os
import pytest


def pytest_collection_modifyitems(config, items):
    """Skip all integration tests unless SN_INTEGRATION_TESTS=1 is set."""
    if os.getenv("SN_INTEGRATION_TESTS") == "1":
        return  # env var set — let them run

    skip_marker = pytest.mark.skip(
        reason="Integration tests disabled. Set SN_INTEGRATION_TESTS=1 to enable."
    )
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_marker)
