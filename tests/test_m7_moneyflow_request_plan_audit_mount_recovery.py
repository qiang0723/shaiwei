from __future__ import annotations

import hashlib
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
SCOPE = ROOT / "config/m7_moneyflow_request_plan_audit_mount_recovery_scope_v1.yaml"
PLAN_ID = "406f083f09cc8e41517ff9b38a4e109606a44b3da923710e4f745e34932b0470"
SCOPE_SHA256 = "3a5d201bf3972198cd98d74e6c40cb1fb15a63180fe0e660054ca37286b9592f"


def _scope() -> dict:
    return yaml.safe_load(SCOPE.read_text(encoding="utf-8"))


def test_recovery_scope_identity_is_frozen() -> None:
    assert hashlib.sha256(SCOPE.read_bytes()).hexdigest() == SCOPE_SHA256


def test_recovery_preserves_failure_and_changes_only_plan_mount() -> None:
    scope = _scope()
    failure = scope["preserved_failure"]
    execution = scope["recovery_execution"]
    assert scope["status"] == "READY_NOT_EXECUTION_AUTHORIZED"
    assert failure["original_auditor_invocation_count"] == 1
    assert failure["original_result"] == "FAIL"
    assert failure["root_cause"] == "PLAN_MOUNT_BASENAME_IDENTITY_MISMATCH"
    assert failure["request_plan_audit_output_created"] is False
    assert execution["semantic_calculation_changed"] is False
    assert execution["source_inputs_changed"] is False
    assert execution["code_or_image_changed"] is False
    assert execution["plan_mount"]["target"] == f"/plans/{PLAN_ID}"
    command = execution["command"]
    assert command[command.index("--plan-root") + 1] == f"/plans/{PLAN_ID}"
    assert execution["auditor_invocation_count"] == 1
    assert execution["same_recovery_retry_authorized"] is False


def test_recovery_is_offline_secret_free_and_not_authorized() -> None:
    scope = _scope()
    execution = scope["recovery_execution"]
    authority = scope["authority"]
    assert execution["network_mode"] == "none"
    assert execution["read_only_root"] is True
    assert execution["run_as_non_root"] is True
    assert execution["docker_socket_mounted"] is False
    assert execution["full_project_root_mounted"] is False
    assert execution["dotenv_or_secret_mounted"] is False
    assert execution["production_data_raw_ledger_logs_mounted"] is False
    assert authority["execution_authorized"] is False
    assert authority["external_network_authorized"] is False
    assert authority["provider_call_authorized"] is False
    assert authority["secret_read_authorized"] is False
    assert authority["moneyflow_numeric_value_read_authorized"] is False
    assert authority["research_attempt_increment"] == 0
    assert authority["production_authorization"] == "none"
