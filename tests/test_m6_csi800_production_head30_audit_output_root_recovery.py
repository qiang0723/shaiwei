from __future__ import annotations

import copy
import json
from pathlib import Path
import subprocess
import sys

import pytest
import yaml

from shaiwei.config import PROJECT_ROOT
from shaiwei.research.model_attribution.contract import canonical_sha256
from shaiwei.research.production_conversion import audit_entrypoint_recovery_entrypoint as r4_entry
from shaiwei.research.production_conversion.audit_output_root_recovery_contract import (
    ACTION,
    AUDIT_HOST_ROOT,
    COMPOSE_PATH,
    SENTINEL_SHA256,
    OutputRootApproval,
    OutputRootProtocol,
    OutputRootScope,
    expected_sealed,
)
from shaiwei.research.production_conversion.audit_output_root_recovery_entrypoint import (
    full_preflight,
    verify_output_root_roundtrip,
)
from shaiwei.research.production_conversion.audit_output_root_recovery_release import (
    build_release_document,
)
from shaiwei.research.production_conversion.contract import ProtocolError


ROOT = Path(__file__).parents[1]


def _write(path: Path, value: dict) -> Path:
    path.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n")
    return path


def _release() -> tuple[OutputRootProtocol, dict]:
    protocol = OutputRootProtocol.load()
    image_id, commit = "sha256:" + "b" * 64, "a" * 40
    daemon = {
        "status": "PASS", "evidence_sha256": "c" * 64,
        "output_root_roundtrip": "PASS", "output_root_empty_before": True,
        "output_root_empty_after": True, "sentinel_payload_sha256": SENTINEL_SHA256,
        "host_audit_root": AUDIT_HOST_ROOT.relative_to(PROJECT_ROOT).as_posix(),
        "same_host_root_as_real_mount": True, "effect_semantics_read": False,
        "audit_invoked": False, "final_image_id": image_id, "image_git_commit": commit,
    }
    document = build_release_document(
        protocol=protocol, created_at="2026-08-20T12:30:00+00:00",
        implementation_git_commit=commit, origin_main_commit=commit,
        image_id=image_id, image_platform="linux/arm64", image_git_commit=commit,
        base_image_id=protocol.document["r6_authority"]["image_id"],
        sealed_effect=expected_sealed(protocol), daemon_fixture=daemon,
    )
    return protocol, document


def test_protocol_changes_only_output_root_preparation() -> None:
    protocol = OutputRootProtocol.load()
    change = protocol.document["only_output_root_correction"]
    inherited = protocol.document["inherited_hash_authority"]
    assert change["create_host_path_must_remain_false"] is True
    assert change["fixture_and_real_service_must_bind_the_exact_same_host_root"] is True
    assert change["fixture_write_read_hash_delete_roundtrip_required"] is True
    assert inherited["historical_independent_sha_equality_required"] is False
    assert inherited["current_independent_sha_must_be_recorded"] is True
    assert inherited["independent_reconstruction_relative_tolerance"] == 1e-12
    assert inherited["primary_and_independent_decisions_must_match_exactly"] is True


def test_output_root_roundtrip_restores_empty_directory(tmp_path: Path) -> None:
    result = verify_output_root_roundtrip(tmp_path)
    assert result["output_root_roundtrip"] == "PASS"
    assert result["sentinel_payload_sha256"] == SENTINEL_SHA256
    assert list(tmp_path.iterdir()) == []


def test_output_root_roundtrip_rejects_nonempty_directory(tmp_path: Path) -> None:
    (tmp_path / "existing").write_text("x")
    with pytest.raises(ProtocolError, match="not empty before"):
        verify_output_root_roundtrip(tmp_path)


def test_thin_image_top_level_import_path_is_supported() -> None:
    module_root = ROOT / "src/shaiwei/research/production_conversion"
    completed = subprocess.run(
        [sys.executable, "-c", (
            "import sys; sys.path.insert(0, sys.argv[1]); "
            "import audit_output_root_recovery_contract; "
            "import audit_output_root_recovery_entrypoint"
        ), str(module_root)], cwd=ROOT, check=False, capture_output=True, text=True,
    )
    assert completed.returncode == 0, completed.stderr


def test_release_is_nonexecuting_and_binds_same_root_fixture(tmp_path: Path) -> None:
    protocol, document = _release()
    release = OutputRootScope.load(
        _write(tmp_path / "scope.json", document), protocol, compose_path=COMPOSE_PATH
    )
    assert release.scope["authority"]["execution_authorized"] is False
    assert release.scope["authority"]["sealed_effect_read_authorized"] is False
    assert release.scope["daemon_fixture"]["same_host_root_as_real_mount"] is True
    assert release.scope["execution"]["family_portfolio_attempts_consumed"] == 2


@pytest.mark.parametrize("mutation", ["mount", "command", "network", "count", "root", "fixture"])
def test_release_rejects_rehashed_boundary_drift(tmp_path: Path, mutation: str) -> None:
    protocol, document = _release()
    changed = copy.deepcopy(document)
    scope = changed["scope"]
    if mutation == "mount":
        scope["container"]["mounts"].append({"source": ".", "target": "/workspace", "mode": "ro"})
    elif mutation == "command":
        scope["container"]["command"][-1] = "/other"
    elif mutation == "network":
        scope["container"]["network_mode"] = "bridge"
    elif mutation == "count":
        scope["execution"]["additional_portfolio_attempt_count"] = 1
    elif mutation == "root":
        scope["daemon_fixture"]["host_audit_root"] = "data/other"
    else:
        scope["daemon_fixture"]["output_root_roundtrip"] = "FAIL"
    changed["recovery_scope_sha256"] = canonical_sha256(scope)
    with pytest.raises(ProtocolError):
        OutputRootScope.load(
            _write(tmp_path / f"{mutation}.json", changed), protocol, compose_path=COMPOSE_PATH
        )


def test_approval_binds_exact_scope_and_narrow_authority(tmp_path: Path) -> None:
    protocol, document = _release()
    release = OutputRootScope.load(
        _write(tmp_path / "scope.json", document), protocol, compose_path=COMPOSE_PATH
    )
    approval = {
        "schema_version": "m6-production-head30-audit-output-root-recovery-approval-v1",
        "recovery_scope_sha256": release.sha256, "action": ACTION,
        "approved_at": "2026-08-20T12:31:00+00:00", "consumed": False,
        "sealed_effect_read_authorized": True, "independent_audit_write_authorized": True,
        "qlib_mount_authorized": False, "runner_invocation_authorized": False,
        "model_fit_prediction_backtest_authorized": False,
        "experiment_ledger_write_authorized": False,
        "external_network_authorized": False, "env_or_secret_read_authorized": False,
        "production_authorization": "none",
    }
    OutputRootApproval.load(_write(tmp_path / "approval.json", approval), release)
    approval["runner_invocation_authorized"] = True
    with pytest.raises(ProtocolError, match="authority differs"):
        OutputRootApproval.load(_write(tmp_path / "bad.json", approval), release)


def test_full_preflight_uses_real_predecessors(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        r4_entry, "EMBEDDED_ORIGINAL_PROTOCOL",
        PROJECT_ROOT / "config/m6_csi800_production_head30_price_recovery_v1.yaml",
    )
    evidence, *_ = full_preflight(
        recovery_protocol_path=ROOT / "config/m6_csi800_production_head30_audit_output_root_recovery_v1.yaml",
        r6_protocol_path=ROOT / "config/m6_csi800_production_head30_audit_hash_authority_recovery_v1.yaml",
        r6_release_path=ROOT / "config/m6_csi800_production_head30_audit_hash_authority_recovery_scope_v1.json",
        r6_approval_path=ROOT / "data/control/m6_csi800_production_head30_v1/audit-hash-authority-recovery-approval.json",
        r6_compose_path=ROOT / "compose.m6-production-head30-audit-hash-authority-recovery.yaml",
        r6_failure_evidence_path=ROOT / "config/m6_csi800_production_head30_audit_hash_authority_recovery_execution_failure_v1.json",
        r5_protocol_path=ROOT / "config/m6_csi800_production_head30_audit_lineage_entry_recovery_v1.yaml",
        r5_release_path=ROOT / "config/m6_csi800_production_head30_audit_lineage_entry_recovery_scope_v1.json",
        r5_approval_path=ROOT / "data/control/m6_csi800_production_head30_v1/audit-lineage-entry-recovery-approval.json",
        r5_failure_evidence_path=ROOT / "config/m6_csi800_production_head30_audit_lineage_entry_recovery_execution_failure_v1.json",
        r4_release_path=ROOT / "config/m6_csi800_production_head30_audit_entrypoint_recovery_scope_v1.json",
        r3_protocol_path=ROOT / "config/m6_csi800_production_head30_audit_identity_recovery_v1.yaml",
        r3_release_path=ROOT / "config/m6_csi800_production_head30_audit_identity_recovery_scope_v1.json",
        r4_failure_evidence_path=ROOT / "config/m6_csi800_production_head30_audit_entrypoint_recovery_execution_failure_v1.json",
        original_release_path=ROOT / "config/m6_csi800_production_head30_price_recovery_scope_v1.json",
        original_approval_path=ROOT / "data/control/m6_csi800_production_head30_v1/approval-r2.json",
    )
    assert evidence["r6_r5_r4_r3_r2_lineage_preflight_status"] == "PASS"


def test_compose_fixture_uses_real_root_without_effect_mount() -> None:
    document = yaml.safe_load(
        (ROOT / "compose.m6-production-head30-audit-output-root-recovery.yaml").read_text()
    )
    fixture = document["services"]["m6-production-head30-audit-output-root-recovery-fixture"]
    real = document["services"]["m6-production-head30-audit-output-root-recovery"]
    for service in (fixture, real):
        assert service["network_mode"] == "none"
        assert service["read_only"] is True
        assert service["cap_drop"] == ["ALL"]
    fixture_by_target = {mount["target"]: mount for mount in fixture["volumes"]}
    real_by_target = {mount["target"]: mount for mount in real["volumes"]}
    assert "/outputs" not in fixture_by_target and "/audit" not in fixture_by_target
    assert "/outputs" in real_by_target and "/audit" in real_by_target
    assert fixture_by_target["/fixture-output"]["source"] == real_by_target["/audit"]["source"]
    assert fixture_by_target["/fixture-output"]["bind"]["create_host_path"] is False
    assert real_by_target["/audit"]["bind"]["create_host_path"] is False
