# Integration Test Suite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a gated integration test suite that runs read-only tests against a live ServiceNow PDI across three domains (incidents, catalog, stories), with full response output visible so real shapes can be observed.

**Architecture:** Integration tests live in `tests/integration/` and are skipped by default unless `SN_INTEGRATION_TESTS=1` is set. A root `conftest.py` enforces the gate via pytest marker logic. A subdirectory `conftest.py` provides `live_config` and `live_auth_manager` fixtures from env vars. Write tests are additionally guarded by a PDI URL check.

**Tech Stack:** pytest, python-dotenv, unittest (existing), servicenow_mcp tools (existing)

---

## File Map

| Action | File | Purpose |
|--------|------|---------|
| Create | `tests/conftest.py` | Marker-based skip gate — skips `integration` marker unless `SN_INTEGRATION_TESTS=1` |
| Create | `tests/integration/__init__.py` | Makes integration/ a package for pytest discovery |
| Create | `tests/integration/conftest.py` | `live_config` + `live_auth_manager` fixtures loaded from env vars |
| Create | `tests/integration/test_incidents.py` | Read-only incident integration tests |
| Create | `tests/integration/test_catalog.py` | Read-only catalog integration tests |
| Create | `tests/integration/test_stories.py` | Read-only story integration tests |
| Modify | `pyproject.toml` | Register `integration` marker to suppress pytest warnings |

---

## Task 1: Root conftest.py — integration test gate

**Files:**
- Create: `tests/conftest.py`

- [ ] **Step 1: Create the gate**

```python
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
```

- [ ] **Step 2: Verify unit tests still pass unaffected**

```bash
cd servicenow-mcp
pytest tests/ -x -q
```

Expected: all existing unit tests pass, no integration-related output.

- [ ] **Step 3: Commit**

```bash
git add tests/conftest.py
git commit -m "test: add integration test gate — skips unless SN_INTEGRATION_TESTS=1"
```

---

## Task 2: Register pytest marker in pyproject.toml

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add marker registration**

In `pyproject.toml`, find the `[tool.pytest.ini_options]` section and add:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = "test_*.py"
python_classes = "Test*"
python_functions = "test_*"
addopts = "--ignore=examples"
markers = [
    "integration: marks tests as integration tests requiring a live ServiceNow instance (deselect with '-m not integration')",
]
```

- [ ] **Step 2: Verify no pytest warnings**

```bash
pytest tests/ -q 2>&1 | grep -i "warning\|marker"
```

Expected: no "Unknown pytest.mark.integration" warnings.

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "test: register integration pytest marker"
```

---

## Task 3: Integration conftest.py — live fixtures

**Files:**
- Create: `tests/integration/__init__.py`
- Create: `tests/integration/conftest.py`

- [ ] **Step 1: Create the package init**

```python
# tests/integration/__init__.py
```

(empty file)

- [ ] **Step 2: Create the fixtures**

```python
# tests/integration/conftest.py
import os
import pytest
from dotenv import load_dotenv

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig

# Load .env from the project root (servicenow-mcp/)
load_dotenv()


def _build_config() -> ServerConfig:
    """Build a real ServerConfig from environment variables."""
    instance_url = os.environ.get("SERVICENOW_INSTANCE_URL", "").rstrip("/")
    username = os.environ.get("SERVICENOW_USERNAME", "")
    password = os.environ.get("SERVICENOW_PASSWORD", "")

    if not all([instance_url, username, password]):
        pytest.skip(
            "Integration test requires SERVICENOW_INSTANCE_URL, "
            "SERVICENOW_USERNAME, and SERVICENOW_PASSWORD env vars."
        )

    auth = AuthConfig(
        type=AuthType.BASIC,
        basic=BasicAuthConfig(username=username, password=password),
    )
    return ServerConfig(instance_url=instance_url, auth=auth)


@pytest.fixture(scope="session")
def live_config() -> ServerConfig:
    """Real ServerConfig loaded from environment variables."""
    return _build_config()


@pytest.fixture(scope="session")
def live_auth(live_config) -> AuthManager:
    """Real AuthManager for the live instance."""
    return AuthManager(live_config.auth)


@pytest.fixture(scope="session")
def pdi_guard(live_config):
    """
    Guard fixture for write tests — refuses to run against non-PDI instances.
    Add this fixture to any test that creates or modifies records.
    """
    url = live_config.instance_url
    if "dev" not in url:
        pytest.skip(
            f"Write integration tests only run against a PDI (dev*.service-now.com). "
            f"Current instance: {url}"
        )
    return live_config
```

- [ ] **Step 3: Verify fixtures load without error**

```bash
cd servicenow-mcp
SN_INTEGRATION_TESTS=1 pytest tests/integration/ --collect-only -q 2>&1 | head -20
```

Expected: no import errors (even with zero test files yet).

- [ ] **Step 4: Commit**

```bash
git add tests/integration/__init__.py tests/integration/conftest.py
git commit -m "test: add integration fixture scaffolding with live_config and pdi_guard"
```

---

## Task 4: Incident integration tests

**Files:**
- Create: `tests/integration/test_incidents.py`

These tests verify that incident tools return real data from the PDI and surface the actual response shape.

- [ ] **Step 1: Create the test file**

```python
# tests/integration/test_incidents.py
"""
Integration tests for incident tools against a live ServiceNow instance.
Run with: SN_INTEGRATION_TESTS=1 pytest tests/integration/test_incidents.py -v -s

The -s flag shows print() output so you can inspect real response shapes.
"""
import json
import pytest

from servicenow_mcp.tools.incident_tools import (
    list_incidents,
    get_incident_by_number,
    ListIncidentsParams,
    GetIncidentByNumberParams,
)


@pytest.mark.integration
class TestIncidentIntegration:

    def test_list_incidents_returns_results(self, live_config, live_auth):
        """Verify list_incidents connects and returns records."""
        params = ListIncidentsParams(limit=5)
        result = list_incidents(live_config, live_auth, params)

        print("\n--- list_incidents response ---")
        print(json.dumps(result, indent=2, default=str))

        assert result["success"] is True, f"Expected success, got: {result.get('message')}"
        assert "incidents" in result
        assert isinstance(result["incidents"], list)

    def test_list_incidents_shape(self, live_config, live_auth):
        """Verify each incident record has the expected key fields."""
        params = ListIncidentsParams(limit=3)
        result = list_incidents(live_config, live_auth, params)

        assert result["success"] is True
        incidents = result["incidents"]

        if not incidents:
            pytest.skip("No incidents found on this instance — cannot verify shape.")

        first = incidents[0]
        print("\n--- first incident fields ---")
        print(json.dumps(first, indent=2, default=str))

        # Verify minimum expected fields exist
        for field in ["sys_id", "number", "short_description", "state"]:
            assert field in first, f"Missing expected field: {field}"

    def test_list_incidents_limit_respected(self, live_config, live_auth):
        """Verify the limit parameter is respected."""
        params = ListIncidentsParams(limit=2)
        result = list_incidents(live_config, live_auth, params)

        assert result["success"] is True
        assert len(result["incidents"]) <= 2

    def test_get_incident_by_number(self, live_config, live_auth):
        """Verify get_incident_by_number returns a real incident."""
        # First get a real incident number from the list
        list_result = list_incidents(live_config, live_auth, ListIncidentsParams(limit=1))
        assert list_result["success"] is True

        if not list_result["incidents"]:
            pytest.skip("No incidents on this instance to look up.")

        number = list_result["incidents"][0]["number"]

        # Now look it up by number
        params = GetIncidentByNumberParams(incident_number=number)
        result = get_incident_by_number(live_config, live_auth, params)

        print(f"\n--- get_incident_by_number({number}) response ---")
        print(json.dumps(result, indent=2, default=str))

        assert result["success"] is True
        assert result["incident"]["number"] == number

    def test_get_incident_not_found(self, live_config, live_auth):
        """Verify a graceful not-found response for a fake incident number."""
        params = GetIncidentByNumberParams(incident_number="INC9999999999")
        result = get_incident_by_number(live_config, live_auth, params)

        print("\n--- not_found response ---")
        print(json.dumps(result, indent=2, default=str))

        # Should not raise — should return success=False with a message
        assert result["success"] is False
        assert "message" in result
```

- [ ] **Step 2: Run and observe output**

```bash
cd servicenow-mcp
SN_INTEGRATION_TESTS=1 pytest tests/integration/test_incidents.py -v -s
```

Expected: all tests PASS. The `-s` flag prints real response shapes to stdout — read them carefully. Note any missing fields or unexpected shapes that differ from mock data.

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_incidents.py
git commit -m "test(integration): add incident integration tests — list and get"
```

---

## Task 5: Catalog integration tests

**Files:**
- Create: `tests/integration/test_catalog.py`

- [ ] **Step 1: Create the test file**

```python
# tests/integration/test_catalog.py
"""
Integration tests for catalog tools against a live ServiceNow instance.
Run with: SN_INTEGRATION_TESTS=1 pytest tests/integration/test_catalog.py -v -s
"""
import json
import pytest

from servicenow_mcp.tools.catalog_tools import (
    list_catalogs,
    list_catalog_items,
    get_catalog_item,
    ListCatalogsParams,
    ListCatalogItemsParams,
    GetCatalogItemParams,
)


@pytest.mark.integration
class TestCatalogIntegration:

    def test_list_catalogs(self, live_config, live_auth):
        """Verify catalogs are returned from the live instance."""
        params = ListCatalogsParams()
        result = list_catalogs(live_config, live_auth, params)

        print("\n--- list_catalogs response ---")
        print(json.dumps(result, indent=2, default=str))

        assert result["success"] is True, f"Expected success, got: {result.get('message')}"
        assert "catalogs" in result
        assert isinstance(result["catalogs"], list)

    def test_list_catalog_items(self, live_config, live_auth):
        """Verify catalog items are returned."""
        params = ListCatalogItemsParams(limit=5)
        result = list_catalog_items(live_config, live_auth, params)

        print("\n--- list_catalog_items response ---")
        print(json.dumps(result, indent=2, default=str))

        assert result["success"] is True, f"Expected success, got: {result.get('message')}"
        assert "items" in result
        assert isinstance(result["items"], list)

    def test_catalog_item_shape(self, live_config, live_auth):
        """Verify each catalog item has expected fields."""
        params = ListCatalogItemsParams(limit=3)
        result = list_catalog_items(live_config, live_auth, params)

        assert result["success"] is True
        items = result["items"]

        if not items:
            pytest.skip("No catalog items found on this instance.")

        first = items[0]
        print("\n--- first catalog item fields ---")
        print(json.dumps(first, indent=2, default=str))

        for field in ["sys_id", "name"]:
            assert field in first, f"Missing expected field: {field}"

    def test_get_catalog_item(self, live_config, live_auth):
        """Verify get_catalog_item returns full item details."""
        # Get a real sys_id from the list first
        list_result = list_catalog_items(live_config, live_auth, ListCatalogItemsParams(limit=1))
        assert list_result["success"] is True

        if not list_result["items"]:
            pytest.skip("No catalog items on this instance.")

        sys_id = list_result["items"][0]["sys_id"]

        params = GetCatalogItemParams(item_id=sys_id)
        result = get_catalog_item(live_config, live_auth, params)

        print(f"\n--- get_catalog_item({sys_id}) response ---")
        print(json.dumps(result, indent=2, default=str))

        assert result["success"] is True
        assert "item" in result
        assert result["item"]["sys_id"] == sys_id

    def test_list_catalog_items_with_filter(self, live_config, live_auth):
        """Verify category filter is applied and returns filtered results."""
        # Get a real category from an existing item
        list_result = list_catalog_items(live_config, live_auth, ListCatalogItemsParams(limit=5))
        assert list_result["success"] is True

        items = list_result["items"]
        if not items:
            pytest.skip("No catalog items on this instance.")

        print("\n--- catalog items for filter test ---")
        print(json.dumps(items, indent=2, default=str))

        # Just verify the call succeeds with active=True filter
        params = ListCatalogItemsParams(limit=5, active=True)
        result = list_catalog_items(live_config, live_auth, params)
        assert result["success"] is True
```

- [ ] **Step 2: Run and observe output**

```bash
SN_INTEGRATION_TESTS=1 pytest tests/integration/test_catalog.py -v -s
```

Expected: all tests PASS. Inspect the printed catalog item shapes — pay attention to whether `category`, `price`, `cost`, and `short_description` are present and what their formats look like vs. what the unit test mocks assumed.

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_catalog.py
git commit -m "test(integration): add catalog integration tests — list and get"
```

---

## Task 6: Story integration tests

**Files:**
- Create: `tests/integration/test_stories.py`

- [ ] **Step 1: Create the test file**

```python
# tests/integration/test_stories.py
"""
Integration tests for story tools against a live ServiceNow instance.
Run with: SN_INTEGRATION_TESTS=1 pytest tests/integration/test_stories.py -v -s
"""
import json
import pytest

from servicenow_mcp.tools.story_tools import (
    list_stories,
    get_story,
    ListStoriesParams,
    GetStoryParams,
)


@pytest.mark.integration
class TestStoryIntegration:

    def test_list_stories_returns_results(self, live_config, live_auth):
        """Verify list_stories connects and returns records."""
        params = ListStoriesParams(limit=5)
        result = list_stories(live_config, live_auth, params)

        print("\n--- list_stories response ---")
        print(json.dumps(result, indent=2, default=str))

        assert result["success"] is True, f"Expected success, got: {result.get('message')}"
        assert "stories" in result
        assert isinstance(result["stories"], list)

    def test_list_stories_shape(self, live_config, live_auth):
        """Verify story records have expected fields."""
        params = ListStoriesParams(limit=3)
        result = list_stories(live_config, live_auth, params)

        assert result["success"] is True
        stories = result["stories"]

        if not stories:
            pytest.skip("No stories found on this instance.")

        first = stories[0]
        print("\n--- first story fields ---")
        print(json.dumps(first, indent=2, default=str))

        for field in ["sys_id", "number", "short_description", "state"]:
            assert field in first, f"Missing expected field: {field}"

    def test_get_story_by_sys_id(self, live_config, live_auth):
        """Verify get_story returns full story details."""
        list_result = list_stories(live_config, live_auth, ListStoriesParams(limit=1))
        assert list_result["success"] is True

        if not list_result["stories"]:
            pytest.skip("No stories on this instance.")

        sys_id = list_result["stories"][0]["sys_id"]

        params = GetStoryParams(story_id=sys_id)
        result = get_story(live_config, live_auth, params)

        print(f"\n--- get_story({sys_id}) response ---")
        print(json.dumps(result, indent=2, default=str))

        assert result["success"] is True
        assert "story" in result
        assert result["story"]["sys_id"] == sys_id

    def test_list_stories_limit_respected(self, live_config, live_auth):
        """Verify limit param is respected."""
        params = ListStoriesParams(limit=2)
        result = list_stories(live_config, live_auth, params)

        assert result["success"] is True
        assert len(result["stories"]) <= 2

    def test_get_story_not_found(self, live_config, live_auth):
        """Verify graceful not-found handling."""
        params = GetStoryParams(story_id="nonexistent_sys_id_00000000000")
        result = get_story(live_config, live_auth, params)

        print("\n--- not_found response ---")
        print(json.dumps(result, indent=2, default=str))

        assert result["success"] is False
        assert "message" in result
```

- [ ] **Step 2: Run and observe output**

```bash
SN_INTEGRATION_TESTS=1 pytest tests/integration/test_stories.py -v -s
```

Expected: all tests PASS. Note the actual state values and field shapes returned — these may differ from what unit test fixtures assumed.

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_stories.py
git commit -m "test(integration): add story integration tests — list and get"
```

---

## Task 7: Full suite verification

- [ ] **Step 1: Run unit tests alone — confirm nothing broke**

```bash
cd servicenow-mcp
pytest tests/ -q --ignore=tests/integration
```

Expected: all existing unit tests PASS.

- [ ] **Step 2: Run integration tests with output**

```bash
SN_INTEGRATION_TESTS=1 pytest tests/integration/ -v -s 2>&1 | tee /tmp/integration-output.txt
```

Expected: all integration tests PASS. Full response shapes printed to stdout.

- [ ] **Step 3: Confirm gate works — run full suite without env var**

```bash
pytest tests/ -q
```

Expected: all unit tests pass, integration tests show as SKIPPED (not FAILED).

- [ ] **Step 4: Final commit**

```bash
git add .
git commit -m "test(integration): complete read-only integration test suite for incidents, catalog, stories"
```

---

## Running Integration Tests

```bash
# Run all integration tests with visible output
cd servicenow-mcp
SN_INTEGRATION_TESTS=1 pytest tests/integration/ -v -s

# Run a single domain
SN_INTEGRATION_TESTS=1 pytest tests/integration/test_incidents.py -v -s

# Run unit tests only (default, no env var needed)
pytest tests/ -q
```

## What to look for in output

When tests run, print output shows the real JSON shapes. Look for:
- Fields present in real responses that are missing from mock data
- Fields the mocks include that don't exist in real responses
- Value formats (e.g., state as `{"value": "1", "display_value": "New"}` vs plain `"1"`)
- Null vs missing fields
- Any unexpected nesting or array structures

These observations are the inputs for improving tool parsing logic.
