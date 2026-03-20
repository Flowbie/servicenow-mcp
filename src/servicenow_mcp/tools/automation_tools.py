"""
Automation platform tools for the ServiceNow MCP server.

Covers scheduled jobs (sys_trigger), scheduled import sets
(scheduled_import_set), and scheduled data exports (scheduled_data_export).

Key platform notes:
- disable_scheduled_job sets trigger_type=2 ("Once"), NOT active=false.
  Setting active=false is unreliable on some SN versions.
- delete_scheduled_job refuses to delete parent cluster jobs whose
  system_id is 'ALL NODES', 'ACTIVE NODES', or 'PRIMARY NODES'.
- create_scheduled_script requires time_zone; run_start must be before
  run_end when both are supplied.
"""

import logging
from typing import Any, Dict, List, Optional

import requests
from pydantic import BaseModel, Field, model_validator

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.utils.config import ServerConfig

logger = logging.getLogger(__name__)

# sys_id values that identify cluster-wide parent jobs — never delete these
_PROTECTED_SYSTEM_IDS = {"ALL NODES", "ACTIVE NODES", "PRIMARY NODES"}


# ---------------------------------------------------------------------------
# Parameter models
# ---------------------------------------------------------------------------


class ListScheduledJobsParams(BaseModel):
    """Parameters for listing scheduled jobs."""

    limit: int = Field(10, description="Maximum number of records to return")
    offset: int = Field(0, description="Pagination offset")
    trigger_type: Optional[str] = Field(
        None,
        description=(
            "Filter by trigger_type value: 0=Daily, 1=Weekly, 2=Once, "
            "3=Periodically, 4=Monthly"
        ),
    )
    active: Optional[bool] = Field(None, description="Filter by active flag")
    name_filter: Optional[str] = Field(None, description="Filter by name (LIKE match)")


class GetScheduledJobParams(BaseModel):
    """Parameters for getting a single scheduled job.

    At least one of job_name or job_sys_id must be provided.
    """

    job_name: Optional[str] = Field(None, description="Name of the scheduled job")
    job_sys_id: Optional[str] = Field(None, description="sys_id of the scheduled job")

    @model_validator(mode="after")
    def require_at_least_one(self) -> "GetScheduledJobParams":
        if not self.job_name and not self.job_sys_id:
            raise ValueError("At least one of job_name or job_sys_id must be provided")
        return self


class EnableScheduledJobParams(BaseModel):
    """Parameters for enabling a scheduled job."""

    job_sys_id: str = Field(..., description="sys_id of the scheduled job to enable")


class DisableScheduledJobParams(BaseModel):
    """Parameters for disabling a scheduled job.

    Sets trigger_type=2 (Once) rather than active=false, which is unreliable.
    """

    job_sys_id: str = Field(..., description="sys_id of the scheduled job to disable")


class CreateScheduledScriptParams(BaseModel):
    """Parameters for creating a scheduled script execution job.

    time_zone is mandatory. When both run_start and run_end are provided,
    run_start must be before run_end (validated here).
    """

    name: str = Field(..., description="Display name for the scheduled job")
    script: str = Field(..., description="JavaScript to execute")
    time_zone: str = Field(..., description="Time zone for the schedule (e.g. 'US/Eastern')")
    trigger_type: int = Field(
        3,
        description=(
            "Trigger type: 0=Daily, 1=Weekly, 2=Once, 3=Periodically, 4=Monthly"
        ),
    )
    run_period: Optional[str] = Field(
        None,
        description="Run period for Periodically type (e.g. '00:01:00' for every minute)",
    )
    run_start: Optional[str] = Field(
        None, description="Schedule start date/time (YYYY-MM-DD HH:MM:SS)"
    )
    run_end: Optional[str] = Field(
        None, description="Schedule end date/time (YYYY-MM-DD HH:MM:SS)"
    )

    @model_validator(mode="after")
    def validate_run_dates(self) -> "CreateScheduledScriptParams":
        if self.run_start and self.run_end and self.run_start >= self.run_end:
            raise ValueError("run_start must be before run_end")
        return self


class DeleteScheduledJobParams(BaseModel):
    """Parameters for deleting a scheduled job.

    Delete is refused when system_id identifies a cluster-wide parent job
    ('ALL NODES', 'ACTIVE NODES', 'PRIMARY NODES').
    """

    job_sys_id: str = Field(..., description="sys_id of the scheduled job to delete")


class ListScheduledImportsParams(BaseModel):
    """Parameters for listing scheduled import sets."""

    limit: int = Field(10, description="Maximum number of records to return")
    offset: int = Field(0, description="Pagination offset")
    active: Optional[bool] = Field(None, description="Filter by active flag")


class ListScheduledExportsParams(BaseModel):
    """Parameters for listing scheduled data exports."""

    limit: int = Field(10, description="Maximum number of records to return")
    offset: int = Field(0, description="Pagination offset")
    active: Optional[bool] = Field(None, description="Filter by active flag")


# ---------------------------------------------------------------------------
# Tool functions
# ---------------------------------------------------------------------------


def list_scheduled_jobs(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: ListScheduledJobsParams,
) -> Dict[str, Any]:
    """List scheduled jobs from sys_trigger, with optional type/active filters."""
    try:
        url = f"{config.instance_url}/api/now/table/sys_trigger"
        headers = auth_manager.get_headers()

        query_parts: List[str] = []
        if params.trigger_type is not None:
            query_parts.append(f"trigger_type={params.trigger_type}")
        if params.active is not None:
            query_parts.append(f"active={str(params.active).lower()}")
        if params.name_filter:
            query_parts.append(f"nameLIKE{params.name_filter}")

        query_params: Dict[str, Any] = {
            "sysparm_limit": params.limit,
            "sysparm_offset": params.offset,
            "sysparm_display_value": "true",
        }
        if query_parts:
            query_params["sysparm_query"] = "^".join(query_parts)

        response = requests.get(url, headers=headers, params=query_params)
        response.raise_for_status()
        jobs = response.json().get("result", [])
        return {
            "success": True,
            "scheduled_jobs": jobs,
            "count": len(jobs),
        }
    except requests.HTTPError as e:
        logger.error(f"HTTP error listing scheduled jobs: {e}")
        return {"success": False, "message": f"HTTP error: {e}"}
    except Exception as e:
        logger.error(f"Error listing scheduled jobs: {e}")
        return {"success": False, "message": f"Error: {e}"}


def get_scheduled_job(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: GetScheduledJobParams,
) -> Dict[str, Any]:
    """Get a single scheduled job by sys_id or name."""
    try:
        headers = auth_manager.get_headers()

        if params.job_sys_id:
            url = f"{config.instance_url}/api/now/table/sys_trigger/{params.job_sys_id}"
            response = requests.get(url, headers=headers, params={"sysparm_display_value": "true"})
            response.raise_for_status()
            return {
                "success": True,
                "scheduled_job": response.json().get("result", {}),
            }

        # Look up by name
        url = f"{config.instance_url}/api/now/table/sys_trigger"
        response = requests.get(
            url,
            headers=headers,
            params={
                "sysparm_query": f"name={params.job_name}",
                "sysparm_limit": 1,
                "sysparm_display_value": "true",
            },
        )
        response.raise_for_status()
        results = response.json().get("result", [])
        if not results:
            return {"success": False, "message": f"No scheduled job found with name '{params.job_name}'"}
        return {
            "success": True,
            "scheduled_job": results[0],
        }
    except requests.HTTPError as e:
        logger.error(f"HTTP error getting scheduled job: {e}")
        return {"success": False, "message": f"HTTP error: {e}"}
    except Exception as e:
        logger.error(f"Error getting scheduled job: {e}")
        return {"success": False, "message": f"Error: {e}"}


def enable_scheduled_job(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: EnableScheduledJobParams,
) -> Dict[str, Any]:
    """Enable a scheduled job by setting active=true."""
    try:
        url = f"{config.instance_url}/api/now/table/sys_trigger/{params.job_sys_id}"
        headers = auth_manager.get_headers()
        headers["Content-Type"] = "application/json"
        response = requests.patch(url, json={"active": "true"}, headers=headers)
        response.raise_for_status()
        return {
            "success": True,
            "message": "Scheduled job enabled successfully",
            "scheduled_job": response.json().get("result", {}),
        }
    except requests.HTTPError as e:
        logger.error(f"HTTP error enabling scheduled job: {e}")
        return {"success": False, "message": f"HTTP error: {e}"}
    except Exception as e:
        logger.error(f"Error enabling scheduled job: {e}")
        return {"success": False, "message": f"Error: {e}"}


def disable_scheduled_job(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: DisableScheduledJobParams,
) -> Dict[str, Any]:
    """Disable a scheduled job by setting trigger_type=2 (Once).

    Does NOT set active=false — that is unreliable on some ServiceNow versions.
    Setting trigger_type=2 (Once) with no future run date effectively prevents
    the job from running again.
    """
    try:
        url = f"{config.instance_url}/api/now/table/sys_trigger/{params.job_sys_id}"
        headers = auth_manager.get_headers()
        headers["Content-Type"] = "application/json"
        response = requests.patch(url, json={"trigger_type": "2"}, headers=headers)
        response.raise_for_status()
        return {
            "success": True,
            "message": "Scheduled job disabled (trigger_type set to Once)",
            "scheduled_job": response.json().get("result", {}),
        }
    except requests.HTTPError as e:
        logger.error(f"HTTP error disabling scheduled job: {e}")
        return {"success": False, "message": f"HTTP error: {e}"}
    except Exception as e:
        logger.error(f"Error disabling scheduled job: {e}")
        return {"success": False, "message": f"Error: {e}"}


def create_scheduled_script(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: CreateScheduledScriptParams,
) -> Dict[str, Any]:
    """Create a scheduled script execution job in sys_trigger.

    time_zone is mandatory. run_start must be before run_end when both provided.
    """
    try:
        url = f"{config.instance_url}/api/now/table/sys_trigger"
        headers = auth_manager.get_headers()
        headers["Content-Type"] = "application/json"

        data: Dict[str, Any] = {
            "name": params.name,
            "script": params.script,
            "time_zone": params.time_zone,
            "trigger_type": str(params.trigger_type),
        }
        if params.run_period is not None:
            data["run_period"] = params.run_period
        if params.run_start is not None:
            data["run_start"] = params.run_start
        if params.run_end is not None:
            data["run_end"] = params.run_end

        response = requests.post(url, json=data, headers=headers)
        response.raise_for_status()
        return {
            "success": True,
            "message": "Scheduled script created successfully",
            "scheduled_job": response.json().get("result", {}),
        }
    except requests.HTTPError as e:
        logger.error(f"HTTP error creating scheduled script: {e}")
        return {"success": False, "message": f"HTTP error: {e}"}
    except Exception as e:
        logger.error(f"Error creating scheduled script: {e}")
        return {"success": False, "message": f"Error: {e}"}


def delete_scheduled_job(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: DeleteScheduledJobParams,
) -> Dict[str, Any]:
    """Delete a scheduled job.

    Refuses to delete cluster-wide parent jobs whose system_id is
    'ALL NODES', 'ACTIVE NODES', or 'PRIMARY NODES'.
    """
    try:
        headers = auth_manager.get_headers()

        # Fetch the record first to check system_id
        get_url = f"{config.instance_url}/api/now/table/sys_trigger/{params.job_sys_id}"
        get_response = requests.get(get_url, headers=headers, params={"sysparm_fields": "sys_id,name,system_id"})
        get_response.raise_for_status()
        record = get_response.json().get("result", {})

        system_id = record.get("system_id", "")
        if isinstance(system_id, dict):
            system_id = system_id.get("value", "")

        if system_id in _PROTECTED_SYSTEM_IDS:
            return {
                "success": False,
                "message": (
                    f"Refusing to delete cluster-wide parent job "
                    f"(system_id='{system_id}'). These jobs are managed by "
                    "the ServiceNow platform and must not be deleted."
                ),
            }

        delete_url = f"{config.instance_url}/api/now/table/sys_trigger/{params.job_sys_id}"
        delete_response = requests.delete(delete_url, headers=headers)
        delete_response.raise_for_status()
        return {
            "success": True,
            "message": f"Scheduled job '{record.get('name', params.job_sys_id)}' deleted successfully",
        }
    except requests.HTTPError as e:
        logger.error(f"HTTP error deleting scheduled job: {e}")
        return {"success": False, "message": f"HTTP error: {e}"}
    except Exception as e:
        logger.error(f"Error deleting scheduled job: {e}")
        return {"success": False, "message": f"Error: {e}"}


def list_scheduled_imports(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: ListScheduledImportsParams,
) -> Dict[str, Any]:
    """List scheduled import sets from scheduled_import_set."""
    try:
        url = f"{config.instance_url}/api/now/table/scheduled_import_set"
        headers = auth_manager.get_headers()

        query_parts: List[str] = []
        if params.active is not None:
            query_parts.append(f"active={str(params.active).lower()}")

        query_params: Dict[str, Any] = {
            "sysparm_limit": params.limit,
            "sysparm_offset": params.offset,
            "sysparm_display_value": "true",
        }
        if query_parts:
            query_params["sysparm_query"] = "^".join(query_parts)

        response = requests.get(url, headers=headers, params=query_params)
        response.raise_for_status()
        imports = response.json().get("result", [])
        return {
            "success": True,
            "scheduled_imports": imports,
            "count": len(imports),
        }
    except requests.HTTPError as e:
        logger.error(f"HTTP error listing scheduled imports: {e}")
        return {"success": False, "message": f"HTTP error: {e}"}
    except Exception as e:
        logger.error(f"Error listing scheduled imports: {e}")
        return {"success": False, "message": f"Error: {e}"}


def list_scheduled_exports(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: ListScheduledExportsParams,
) -> Dict[str, Any]:
    """List scheduled data exports from scheduled_data_export."""
    try:
        url = f"{config.instance_url}/api/now/table/scheduled_data_export"
        headers = auth_manager.get_headers()

        query_parts: List[str] = []
        if params.active is not None:
            query_parts.append(f"active={str(params.active).lower()}")

        query_params: Dict[str, Any] = {
            "sysparm_limit": params.limit,
            "sysparm_offset": params.offset,
            "sysparm_display_value": "true",
        }
        if query_parts:
            query_params["sysparm_query"] = "^".join(query_parts)

        response = requests.get(url, headers=headers, params=query_params)
        response.raise_for_status()
        exports = response.json().get("result", [])
        return {
            "success": True,
            "scheduled_exports": exports,
            "count": len(exports),
        }
    except requests.HTTPError as e:
        logger.error(f"HTTP error listing scheduled exports: {e}")
        return {"success": False, "message": f"HTTP error: {e}"}
    except Exception as e:
        logger.error(f"Error listing scheduled exports: {e}")
        return {"success": False, "message": f"Error: {e}"}


# ---------------------------------------------------------------------------
# update_scheduled_job — Story 12.1
# ---------------------------------------------------------------------------


class UpdateScheduledJobParams(BaseModel):
    """Parameters for updating a scheduled job.

    Only fields provided (non-None) are included in the PATCH payload.
    """

    job_sys_id: str = Field(..., description="sys_id of the scheduled job to update")
    name: Optional[str] = Field(None, description="New name for the job")
    script: Optional[str] = Field(None, description="New server-side script body")
    run_start: Optional[str] = Field(None, description="New start time (ISO 8601 or SN datetime)")
    time_zone: Optional[str] = Field(None, description="Time zone (e.g. 'US/Eastern')")


def update_scheduled_job(
    config: ServerConfig, auth_manager: AuthManager, params: UpdateScheduledJobParams
) -> Dict[str, Any]:
    """Update a scheduled job record (sys_trigger) via PATCH.

    Only the fields explicitly provided (non-None) are sent in the payload.
    """
    url = f"{config.instance_url}/api/now/table/sys_trigger/{params.job_sys_id}"
    headers = auth_manager.get_headers()
    payload: Dict[str, Any] = {}
    if params.name is not None:
        payload["name"] = params.name
    if params.script is not None:
        payload["script"] = params.script
    if params.run_start is not None:
        payload["run_start"] = params.run_start
    if params.time_zone is not None:
        payload["time_zone"] = params.time_zone

    try:
        response = requests.patch(url, headers=headers, json=payload)
        response.raise_for_status()
        return {"success": True, "scheduled_job": response.json().get("result", {})}
    except requests.HTTPError as e:
        logger.error(f"HTTP error updating scheduled job {params.job_sys_id}: {e}")
        return {"success": False, "message": f"HTTP error: {e}"}
    except Exception as e:
        logger.error(f"Error updating scheduled job {params.job_sys_id}: {e}")
        return {"success": False, "message": f"Error: {e}"}


# ---------------------------------------------------------------------------
# run_scheduled_job_now — Story 12.1
# ---------------------------------------------------------------------------


class RunScheduledJobNowParams(BaseModel):
    """Parameters for triggering a scheduled job to run immediately."""

    job_sys_id: str = Field(..., description="sys_id of the scheduled job to run now")


def run_scheduled_job_now(
    config: ServerConfig, auth_manager: AuthManager, params: RunScheduledJobNowParams
) -> Dict[str, Any]:
    """Trigger a scheduled job to run immediately.

    Sets trigger=true on the sys_trigger record, which causes the scheduler
    to execute the job on its next poll cycle (typically within ~1 minute).
    """
    url = f"{config.instance_url}/api/now/table/sys_trigger/{params.job_sys_id}"
    headers = auth_manager.get_headers()
    try:
        response = requests.patch(url, headers=headers, json={"trigger": "true"})
        response.raise_for_status()
        return {
            "success": True,
            "scheduled_job": response.json().get("result", {}),
            "message": "Job queued for immediate execution (runs on next scheduler poll)",
        }
    except requests.HTTPError as e:
        logger.error(f"HTTP error triggering scheduled job {params.job_sys_id}: {e}")
        return {"success": False, "message": f"HTTP error: {e}"}
    except Exception as e:
        logger.error(f"Error triggering scheduled job {params.job_sys_id}: {e}")
        return {"success": False, "message": f"Error: {e}"}
