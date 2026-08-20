from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from shaiwei.config import PROJECT_ROOT
from shaiwei.provenance import CONTROLLED_FILES, RELEASE_MANIFEST_SCHEMA
from shaiwei.research.production_conversion.contract import ProtocolError
from shaiwei.research.production_conversion.real_contract import (
    Approval,
    ENTRYPOINT_RECOVERY_PROTOCOL,
    ReleaseProtocol,
    ReleaseScope,
)
from shaiwei.research.production_conversion.real_release import build_release_document


FAILED_SCOPE = PROJECT_ROOT / "config/m6_csi800_production_head30_release_scope_v1.json"


def _inputs() -> dict[str, object]:
    qlib = json.loads(
        (
            PROJECT_ROOT / "config/m6_csi800_model_attribution_release_scope_v1.json"
        ).read_text(encoding="utf-8")
    )["scope"]["inputs"]
    return {
        "qlib": qlib,
        "sealed_m6_effect": {
            "file_count": 1,
            "total_bytes": 1,
            "tree_sha256": "c" * 64,
            "report_sha256": "d" * 64,
            "first_pass_bundle_sha256": "e" * 64,
            "replay_bundle_sha256": "e" * 64,
        },
        "sealed_m6_audit": {
            "path": "data/example/audit.json",
            "sha256": "f" * 64,
            "independent_audit": "PASS",
        },
    }


def _release(tmp_path: Path) -> tuple[ReleaseProtocol, ReleaseScope]:
    protocol = ReleaseProtocol.load(ENTRYPOINT_RECOVERY_PROTOCOL)
    snapshot = "a" * 64
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": RELEASE_MANIFEST_SCHEMA,
                "code_snapshot_sha256": snapshot,
                "file_count": 1,
                "files": [{"path": "x", "sha256": "b" * 64}],
            }
        ),
        encoding="utf-8",
    )
    commit = "1" * 40
    document = build_release_document(
        protocol=protocol,
        created_at="2026-08-20T00:00:00+00:00",
        implementation_git_commit=commit,
        origin_main_commit=commit,
        code_snapshot=snapshot,
        image_id="sha256:" + "2" * 64,
        image_platform="linux/arm64",
        image_git_commit=commit,
        image_release_manifest_path=manifest,
        inputs=_inputs(),
    )
    path = tmp_path / "release.json"
    path.write_text(json.dumps(document, sort_keys=True), encoding="utf-8")
    return protocol, ReleaseScope.load(path, protocol)


def test_failed_scope_is_closed_before_effect_and_original_scope_still_loads() -> None:
    failure = json.loads(
        (
            PROJECT_ROOT
            / "config/m6_csi800_production_head30_entrypoint_failure_v1.json"
        ).read_text(encoding="utf-8")
    )
    assert failure["container_created"] is False
    assert failure["real_effect_read"] is False
    assert failure["portfolio_attempts_consumed"] == 0
    assert failure["same_scope_retry_authorized"] is False
    original = ReleaseScope.load(FAILED_SCOPE, ReleaseProtocol.load())
    assert original.sha256 == failure["original_release_scope_sha256"]


def test_recovery_protocol_changes_only_orchestration_and_requires_new_scope() -> None:
    protocol = ReleaseProtocol.load(ENTRYPOINT_RECOVERY_PROTOCOL)
    assert protocol.is_recovery is True
    assert protocol.document["recovery_change"]["only_changed_variable"] == (
        "docker_tmpfs_yaml_serialization"
    )
    assert protocol.document["recovery_change"]["strategy_formula_changed"] is False
    assert protocol.document["execution_counting"]["original_failed_scope_attempts_consumed"] == 0
    assert protocol.tracked_release_scope.endswith("entrypoint_recovery_scope_v1.json")


def test_recovery_compose_keeps_each_tmpfs_as_one_daemon_mount() -> None:
    name = "compose.m6-production-head30-recovery.yaml"
    assert name in CONTROLLED_FILES
    compose = yaml.safe_load((PROJECT_ROOT / name).read_text(encoding="utf-8"))
    services = compose["services"]
    assert services["m6-production-head30-recovery-runner"]["tmpfs"] == [
        "/tmp:rw,noexec,nosuid,size=4g,mode=1777"
    ]
    assert services["m6-production-head30-recovery-auditor"]["tmpfs"] == [
        "/tmp:rw,noexec,nosuid,size=1g,mode=1777"
    ]
    serialized = json.dumps(compose)
    assert ".env" not in serialized
    assert "docker.sock" not in serialized


def test_recovery_release_binds_new_image_action_and_services(tmp_path: Path) -> None:
    protocol, release = _release(tmp_path)
    scope = release.scope
    assert scope["scope_kind"] == protocol.scope_kind
    assert scope["image"]["reference"] == "shaiwei:m6-production-head30-recovery-v1"
    assert scope["execution"]["approval_action"] == protocol.approval_action
    assert scope["container"]["runner"]["service"].endswith("recovery-runner")
    assert scope["container"]["auditor"]["service"].endswith("recovery-auditor")
    assert scope["authority"]["execution_authorized"] is False


def test_recovery_approval_rejects_original_action(tmp_path: Path) -> None:
    protocol, release = _release(tmp_path)
    approval = {
        "schema_version": "m6-production-head30-approval-v1",
        "release_scope_sha256": release.sha256,
        "action": protocol.approval_action,
        "qlib_read_authorized": True,
        "sealed_m6_effect_read_authorized": True,
        "real_treatment_backtest_authorized": True,
        "sealed_control_report_read_authorized": True,
        "formal_effect_output_write_authorized": True,
        "independent_audit_authorized": True,
        "model_fit_authorized": False,
        "prediction_generation_authorized": False,
        "experiment_ledger_write_authorized": False,
        "external_network_authorized": False,
        "env_or_secret_read_authorized": False,
        "production_authorization": "none",
        "approved_at": "2026-08-20T00:01:00+00:00",
        "consumed": False,
    }
    path = tmp_path / "approval.json"
    path.write_text(json.dumps(approval), encoding="utf-8")
    Approval.load(path, release)
    approval["action"] = (
        "M6_PRODUCTION_HEAD30_G0_EFFECT_ONCE_WITH_REPLAY_AND_INDEPENDENT_AUDIT"
    )
    path.write_text(json.dumps(approval), encoding="utf-8")
    with pytest.raises(ProtocolError, match="approval authority differs"):
        Approval.load(path, release)
