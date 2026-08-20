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
from shaiwei.research.production_conversion.audit_hash_authority_contract import (
    ACTION,
    COMPOSE_PATH,
    HashAuthorityApproval,
    HashAuthorityProtocol,
    HashAuthorityScope,
    expected_sealed,
)
from shaiwei.research.production_conversion.audit_hash_authority_entrypoint import (
    full_preflight,
    semantic_fixture,
    validate_independent_hash_authority,
)
from shaiwei.research.production_conversion.audit_hash_authority_release import (
    build_release_document,
)
from shaiwei.research.production_conversion.contract import ProtocolError


ROOT = Path(__file__).parents[1]


def _write(path: Path, value: dict) -> Path:
    path.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n")
    return path


def _release() -> tuple[HashAuthorityProtocol, dict]:
    protocol = HashAuthorityProtocol.load()
    image_id, commit = "sha256:" + "b" * 64, "a" * 40
    daemon = {
        "status": "PASS", "evidence_sha256": "c" * 64,
        "hash_mismatch_within_tolerance": "PASS",
        "above_tolerance_fail_closed": "PASS", "decision_drift_fail_closed": "PASS",
        "effect_semantics_read": False, "audit_invoked": False,
        "final_image_id": image_id, "image_git_commit": commit,
    }
    document = build_release_document(
        protocol=protocol, created_at="2026-08-20T12:00:00+00:00",
        implementation_git_commit=commit, origin_main_commit=commit,
        image_id=image_id, image_platform="linux/arm64", image_git_commit=commit,
        base_image_id=protocol.document["r5_authority"]["image_id"],
        sealed_effect=expected_sealed(protocol), daemon_fixture=daemon,
    )
    return protocol, document


def test_protocol_changes_only_historical_independent_hash_authority() -> None:
    protocol = HashAuthorityProtocol.load()
    correction = protocol.document["only_authority_correction"]
    assert correction["historical_independent_sha_equality_required"] is False
    assert correction["current_independent_sha_must_be_recorded"] is True
    assert correction["primary_result_sha_must_match_sealed_identity"] is True
    assert correction["independent_reconstruction_relative_tolerance"] == 1e-12
    assert correction["independent_reconstruction_absolute_tolerance"] == 1e-12
    assert correction["primary_and_independent_decisions_must_match_exactly"] is True


def test_hash_authority_records_distinct_current_hash_without_using_it_as_verdict() -> None:
    checks = {"primary_identity": True, "numeric_tolerance": True, "decision": True}
    authority = validate_independent_hash_authority(
        checks, current_sha="1" * 64, historical_sha="2" * 64
    )
    assert authority["historical_hash_equal"] is False
    assert authority["historical_hash_equality_required"] is False
    assert authority["current_independent_result_sha256"] == "1" * 64


def test_hash_authority_remains_fail_closed_on_substantive_check() -> None:
    with pytest.raises(ProtocolError, match="numeric_tolerance"):
        validate_independent_hash_authority(
            {"primary_identity": True, "numeric_tolerance": False, "decision": True},
            current_sha="1" * 64, historical_sha="2" * 64,
        )


def test_adversarial_semantic_fixture_passes() -> None:
    assert semantic_fixture() == {
        "hash_mismatch_within_tolerance": "PASS",
        "above_tolerance_fail_closed": "PASS",
        "decision_drift_fail_closed": "PASS",
    }


def test_thin_image_top_level_import_path_is_supported() -> None:
    module_root = ROOT / "src/shaiwei/research/production_conversion"
    completed = subprocess.run(
        [sys.executable, "-c", (
            "import sys; sys.path.insert(0, sys.argv[1]); "
            "import audit_hash_authority_contract; import audit_hash_authority_entrypoint"
        ), str(module_root)],
        cwd=ROOT, check=False, capture_output=True, text=True,
    )
    assert completed.returncode == 0, completed.stderr


def test_release_is_nonexecuting_and_binds_fixture(tmp_path: Path) -> None:
    protocol, document = _release()
    release = HashAuthorityScope.load(
        _write(tmp_path / "scope.json", document), protocol, compose_path=COMPOSE_PATH
    )
    assert release.scope["authority"]["execution_authorized"] is False
    assert release.scope["authority"]["sealed_effect_read_authorized"] is False
    assert release.scope["daemon_fixture"]["hash_mismatch_within_tolerance"] == "PASS"
    assert release.scope["execution"]["family_portfolio_attempts_consumed"] == 2


@pytest.mark.parametrize("mutation", ["mount", "command", "network", "count", "fixture"])
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
    else:
        scope["daemon_fixture"]["decision_drift_fail_closed"] = "FAIL"
    changed["recovery_scope_sha256"] = canonical_sha256(scope)
    with pytest.raises(ProtocolError):
        HashAuthorityScope.load(
            _write(tmp_path / f"{mutation}.json", changed), protocol, compose_path=COMPOSE_PATH
        )


def test_approval_binds_exact_scope_and_narrow_authority(tmp_path: Path) -> None:
    protocol, document = _release()
    release = HashAuthorityScope.load(
        _write(tmp_path / "scope.json", document), protocol, compose_path=COMPOSE_PATH
    )
    approval = {
        "schema_version": "m6-production-head30-audit-hash-authority-recovery-approval-v1",
        "recovery_scope_sha256": release.sha256, "action": ACTION,
        "approved_at": "2026-08-20T12:01:00+00:00", "consumed": False,
        "sealed_effect_read_authorized": True, "independent_audit_write_authorized": True,
        "qlib_mount_authorized": False, "runner_invocation_authorized": False,
        "model_fit_prediction_backtest_authorized": False,
        "experiment_ledger_write_authorized": False,
        "external_network_authorized": False, "env_or_secret_read_authorized": False,
        "production_authorization": "none",
    }
    HashAuthorityApproval.load(_write(tmp_path / "approval.json", approval), release)
    approval["runner_invocation_authorized"] = True
    with pytest.raises(ProtocolError, match="authority differs"):
        HashAuthorityApproval.load(_write(tmp_path / "bad.json", approval), release)


def test_full_preflight_uses_real_predecessors(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        r4_entry, "EMBEDDED_ORIGINAL_PROTOCOL",
        PROJECT_ROOT / "config/m6_csi800_production_head30_price_recovery_v1.yaml",
    )
    evidence, *_ = full_preflight(
        recovery_protocol_path=ROOT / "config/m6_csi800_production_head30_audit_hash_authority_recovery_v1.yaml",
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
    assert evidence["r5_r4_r3_r2_lineage_preflight_status"] == "PASS"


def test_compose_fixture_has_full_lineage_without_effect_mount() -> None:
    document = yaml.safe_load(
        (ROOT / "compose.m6-production-head30-audit-hash-authority-recovery.yaml").read_text()
    )
    fixture = document["services"]["m6-production-head30-audit-hash-authority-recovery-fixture"]
    real = document["services"]["m6-production-head30-audit-hash-authority-recovery"]
    for service in (fixture, real):
        assert service["network_mode"] == "none"
        assert service["read_only"] is True
        assert service["cap_drop"] == ["ALL"]
    fixture_targets = {mount["target"] for mount in fixture["volumes"]}
    real_targets = {mount["target"] for mount in real["volumes"]}
    lineage = {
        "/inputs/recovery-protocol.yaml", "/inputs/r5-protocol.yaml",
        "/inputs/r5-release.json", "/inputs/r5-approval.json",
        "/inputs/r5-execution-failure.json", "/inputs/r4-release.json",
        "/inputs/r3-protocol.yaml", "/inputs/r3-release.json",
        "/inputs/r4-execution-failure.json", "/inputs/original-release.json",
        "/inputs/original-approval.json",
    }
    assert lineage <= fixture_targets
    assert lineage <= real_targets
    assert "/outputs" not in fixture_targets and "/audit" not in fixture_targets
    assert "/outputs" in real_targets and "/audit" in real_targets
