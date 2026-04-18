import json
import os
import subprocess
import pytest
from unittest.mock import MagicMock, patch
from servicenow_mcp.tools.sdk_tools import (
    sdk_scaffold,
    sdk_explain,
    sdk_run_command,
    SdkScaffoldParams,
    SdkExplainParams,
    SdkRunCommandParams,
)


def _config():
    return MagicMock()


def _auth():
    return MagicMock()


def _proc(returncode=0, stdout="ok", stderr=""):
    p = MagicMock()
    p.returncode = returncode
    p.stdout = stdout
    p.stderr = stderr
    return p


# ── sdk_scaffold ──────────────────────────────────────────────────────────────

def test_scaffold_creates_now_config_json(tmp_path):
    params = SdkScaffoldParams(
        scope="x_myco_app",
        app_name="My App",
        project_path=str(tmp_path),
    )
    result = sdk_scaffold(_config(), _auth(), params)
    assert result["success"] is True
    config_file = tmp_path / "now.config.json"
    assert config_file.exists()
    config = json.loads(config_file.read_text())
    assert config["scope"] == "x_myco_app"


def test_scaffold_creates_package_json(tmp_path):
    params = SdkScaffoldParams(scope="x_test", app_name="Test", project_path=str(tmp_path))
    sdk_scaffold(_config(), _auth(), params)
    pkg_file = tmp_path / "package.json"
    assert pkg_file.exists()
    pkg = json.loads(pkg_file.read_text())
    assert "@servicenow/sdk" in pkg["devDependencies"]


def test_scaffold_creates_tables_template_when_requested(tmp_path):
    params = SdkScaffoldParams(
        scope="x_test", app_name="Test", project_path=str(tmp_path),
        include_tables=True,
    )
    sdk_scaffold(_config(), _auth(), params)
    tables_file = tmp_path / "src" / "fluent" / "tables.now.ts"
    assert tables_file.exists()
    content = tables_file.read_text()
    assert "Table" in content
    assert "x_test" in content


def test_scaffold_creates_flows_template_when_requested(tmp_path):
    params = SdkScaffoldParams(
        scope="x_test", app_name="Test", project_path=str(tmp_path),
        include_flows=True,
    )
    sdk_scaffold(_config(), _auth(), params)
    flows_file = tmp_path / "src" / "fluent" / "flows.now.ts"
    assert flows_file.exists()
    assert "Flow" in flows_file.read_text()


def test_scaffold_skips_flows_when_not_requested(tmp_path):
    params = SdkScaffoldParams(
        scope="x_test", app_name="Test", project_path=str(tmp_path),
        include_flows=False,
    )
    sdk_scaffold(_config(), _auth(), params)
    assert not (tmp_path / "src" / "fluent" / "flows.now.ts").exists()


def test_scaffold_reports_files_created(tmp_path):
    params = SdkScaffoldParams(
        scope="x_test", app_name="Test", project_path=str(tmp_path),
        include_tables=True, include_flows=True,
    )
    result = sdk_scaffold(_config(), _auth(), params)
    assert result["success"] is True
    assert len(result["data"]["files_created"]) >= 3  # config + package + at least 2 templates


# ── sdk_explain ───────────────────────────────────────────────────────────────

def test_sdk_explain_list_topics_uses_list_flag():
    with patch("servicenow_mcp.tools.sdk_tools.subprocess.run", return_value=_proc()) as mock_run:
        sdk_explain(_config(), _auth(), SdkExplainParams(list_topics=True))
    cmd = mock_run.call_args.args[0]
    assert "--list" in cmd


def test_sdk_explain_peek_uses_peek_flag():
    with patch("servicenow_mcp.tools.sdk_tools.subprocess.run", return_value=_proc()) as mock_run:
        sdk_explain(_config(), _auth(), SdkExplainParams(topic="Flow", peek=True))
    cmd = mock_run.call_args.args[0]
    assert "--peek" in cmd and "Flow" in cmd


def test_sdk_explain_no_peek_uses_format_raw():
    with patch("servicenow_mcp.tools.sdk_tools.subprocess.run", return_value=_proc()) as mock_run:
        sdk_explain(_config(), _auth(), SdkExplainParams(topic="Flow", peek=False))
    cmd = mock_run.call_args.args[0]
    assert "--format=raw" in cmd and "--peek" not in cmd


def test_sdk_explain_returns_output_on_success():
    with patch("servicenow_mcp.tools.sdk_tools.subprocess.run", return_value=_proc(stdout="Flow docs")):
        result = sdk_explain(_config(), _auth(), SdkExplainParams(topic="Flow"))
    assert result["success"] is True and result["data"]["output"] == "Flow docs"


def test_sdk_explain_returns_error_on_failure():
    with patch("servicenow_mcp.tools.sdk_tools.subprocess.run", return_value=_proc(returncode=1, stderr="bad topic")):
        result = sdk_explain(_config(), _auth(), SdkExplainParams(topic="Bad"))
    assert result["success"] is False and "bad topic" in result["error"]


def test_sdk_explain_npx_not_found():
    with patch("servicenow_mcp.tools.sdk_tools.subprocess.run", side_effect=FileNotFoundError):
        result = sdk_explain(_config(), _auth(), SdkExplainParams(topic="Flow"))
    assert result["success"] is False
    assert "Node.js" in result["error"] or "npx" in result["error"]


def test_sdk_explain_timeout():
    with patch("servicenow_mcp.tools.sdk_tools.subprocess.run",
               side_effect=subprocess.TimeoutExpired(cmd="npx", timeout=60)):
        result = sdk_explain(_config(), _auth(), SdkExplainParams(topic="Flow"))
    assert result["success"] is False and "timed out" in result["error"].lower()


# ── sdk_run_command ───────────────────────────────────────────────────────────

def test_sdk_run_command_dry_run_default():
    params = SdkRunCommandParams(command="build", project_path="/p")
    assert params.dry_run is True


def test_sdk_run_command_validates_now_config_exists(tmp_path):
    result = sdk_run_command(
        _config(), _auth(),
        SdkRunCommandParams(command="build", project_path=str(tmp_path), dry_run=True),
    )
    assert result["success"] is False
    assert "now.config.json" in result["error"]


def test_sdk_run_command_dry_run_passes_flag(tmp_path):
    (tmp_path / "now.config.json").write_text("{}")
    with patch("servicenow_mcp.tools.sdk_tools.subprocess.run", return_value=_proc()) as mock_run:
        sdk_run_command(_config(), _auth(),
                        SdkRunCommandParams(command="build", project_path=str(tmp_path), dry_run=True))
    assert "--dry-run" in mock_run.call_args.args[0]


def test_sdk_run_command_deploy_without_dry_run_omits_flag(tmp_path):
    (tmp_path / "now.config.json").write_text("{}")
    with patch("servicenow_mcp.tools.sdk_tools.subprocess.run", return_value=_proc()) as mock_run:
        sdk_run_command(_config(), _auth(),
                        SdkRunCommandParams(command="deploy", project_path=str(tmp_path), dry_run=False))
    assert "--dry-run" not in mock_run.call_args.args[0]


def test_sdk_run_command_deploy_without_dry_run_includes_flow_warning(tmp_path):
    (tmp_path / "now.config.json").write_text("{}")
    with patch("servicenow_mcp.tools.sdk_tools.subprocess.run", return_value=_proc()):
        result = sdk_run_command(_config(), _auth(),
                                 SdkRunCommandParams(command="deploy", project_path=str(tmp_path), dry_run=False))
    assert any("Flow Designer" in w for w in result.get("warnings", []))


def test_sdk_run_command_timeout(tmp_path):
    (tmp_path / "now.config.json").write_text("{}")
    with patch("servicenow_mcp.tools.sdk_tools.subprocess.run",
               side_effect=subprocess.TimeoutExpired(cmd="npx", timeout=120)):
        result = sdk_run_command(_config(), _auth(),
                                 SdkRunCommandParams(command="build", project_path=str(tmp_path)))
    assert result["success"] is False and "timed out" in result["error"].lower()


def test_sdk_run_command_npx_not_found(tmp_path):
    (tmp_path / "now.config.json").write_text("{}")
    with patch("servicenow_mcp.tools.sdk_tools.subprocess.run", side_effect=FileNotFoundError):
        result = sdk_run_command(_config(), _auth(),
                                 SdkRunCommandParams(command="build", project_path=str(tmp_path)))
    assert result["success"] is False and "Node.js" in result["error"]
