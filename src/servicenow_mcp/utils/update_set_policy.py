from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class TableGovernanceClass(str, Enum):
    REQUIRED = "required"
    EXEMPT = "exempt"
    UNKNOWN = "unknown"


CONFIGURATION_TABLES = {
    "item_option_new",
    "sc_cat_item",
    "sp_widget",
    "sys_app_module",
    "sys_auto_script",
    "sys_choice",
    "sys_data_policy2",
    "sys_db_object",
    "sys_dictionary",
    "sys_hub_action_type_definition",
    "sys_hub_flow",
    "sys_hub_flow_base",
    "sys_hub_sub_flow",
    "sys_properties",
    "sys_rest_message",
    "sys_script",
    "sys_script_client",
    "sys_script_fix",
    "sys_script_include",
    "sys_security_acl",
    "sys_security_acl_role",
    "sys_transform_entry",
    "sys_transform_map",
    "sys_ui_action",
    "sys_ui_page",
    "sys_ui_policy",
    "sys_ui_policy_action",
    "sys_ui_script",
    "sys_ui_view",
    "sys_ws_definition",
    "sys_ws_operation",
}

DATA_TABLES = {
    "change_request",
    "cmdb_ci",
    "incident",
    "kb_knowledge_base",
    "rm_scrum_task",
    "rm_story",
    "rm_sprint_2",
    "sc_request",
    "sc_req_item",
    "sc_task",
    "sys_update_set",
    "sys_user",
    "sys_user_preference",
    "task",
}

DATA_PREFIXES = ("cmdb_",)
CONFIGURATION_PREFIXES = ("sys_hub_",)


def normalize_table_name(table: str | None) -> str:
    return (table or "").strip().lower()


def classify_table(table: str | None) -> TableGovernanceClass:
    normalized = normalize_table_name(table)
    if not normalized:
        return TableGovernanceClass.UNKNOWN
    if normalized in CONFIGURATION_TABLES or normalized.startswith(CONFIGURATION_PREFIXES):
        return TableGovernanceClass.REQUIRED
    if normalized in DATA_TABLES or normalized.startswith(DATA_PREFIXES):
        return TableGovernanceClass.EXEMPT
    return TableGovernanceClass.UNKNOWN


def is_default_update_set(name: str | None) -> bool:
    normalized = (name or "").strip().lower()
    return normalized in {"default", "default [global]"} or normalized.startswith("default [")


@dataclass(frozen=True)
class UpdateSetInfo:
    name: str | None
    sys_id: str | None
    state: str | None
    is_default: bool


@dataclass(frozen=True)
class UpdateSetComplianceResult:
    allowed: bool
    classification: TableGovernanceClass
    reason: str | None = None


def requires_story_update_set(table: str | None) -> bool:
    return classify_table(table) == TableGovernanceClass.REQUIRED


def assert_update_set_compliance_for_write(
    *,
    table: str,
    current_update_set: UpdateSetInfo | None,
    expected_update_set_name: str | None = None,
) -> UpdateSetComplianceResult:
    classification = classify_table(table)
    if classification == TableGovernanceClass.EXEMPT:
        return UpdateSetComplianceResult(allowed=True, classification=classification)
    if classification == TableGovernanceClass.UNKNOWN:
        return UpdateSetComplianceResult(
            allowed=False,
            classification=classification,
            reason=(
                f"Table '{table}' is not yet classified for update-set governance. "
                "Write blocked until the table is explicitly marked as configuration-tracked "
                "or update-set-exempt."
            ),
        )
    if current_update_set is None or not current_update_set.sys_id or not current_update_set.name:
        return UpdateSetComplianceResult(
            allowed=False,
            classification=classification,
            reason=(
                f"Table '{table}' requires a non-default update set, but no active update set "
                "was detected. Call get_current_update_set or set_current_update_set first."
            ),
        )
    if current_update_set.is_default:
        return UpdateSetComplianceResult(
            allowed=False,
            classification=classification,
            reason=(
                f"Table '{table}' requires a story-scoped update set. "
                f"The active update set '{current_update_set.name}' is the default update set."
            ),
        )
    if expected_update_set_name and current_update_set.name != expected_update_set_name:
        return UpdateSetComplianceResult(
            allowed=False,
            classification=classification,
            reason=(
                f"Table '{table}' requires update set '{expected_update_set_name}', "
                f"but the active update set is '{current_update_set.name}'."
            ),
        )
    return UpdateSetComplianceResult(allowed=True, classification=classification)
