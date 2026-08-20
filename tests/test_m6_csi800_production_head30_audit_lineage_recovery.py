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
from shaiwei.research.production_conversion.audit_lineage_recovery_contract import (
    ACTION,
    COMPOSE_PATH,
    R3_PROTOCOL_TARGET,
    LineageApproval,
    LineageProtocol,
    LineageScope,
    expected_sealed,
)
from shaiwei.research.production_conversion.audit_lineage_recovery_entrypoint import (
    lineage_preflight,
)
from shaiwei.research.production_conversion.audit_lineage_recovery_release import (
    build_release_document,
)
from shaiwei.research.production_conversion.contract import ProtocolError


ROOT = Path(__file__).parents[1]


def _write(path: Path, value: dict) -> Path:
    path.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n")
    return path


def _release() -> tuple[LineageProtocol, dict]:
    protocol = LineageProtocol.load()
    image_id, commit = "sha256:" + "b" * 64, "a" * 40
    daemon = {
        "status": "PASS", "evidence_sha256": "c" * 64,
        "r3_protocol_path": R3_PROTOCOL_TARGET,
        "r3_protocol_sha256": protocol.document["root_cause_and_only_change"]["r3_protocol_sha256"],
        "r3_release_scope_sha256": "b38628defcfee83087f0c0d982d0c1145b3f6d642c28508055cba2bddb9614d3",
        "original_release_scope_sha256": "9b78ef69ec11c180bbc1adc46b95c3f8023bf729480d4fd647e2eab1085f9b4a",
        "effect_semantics_read": False, "audit_invoked": False,
        "final_image_id": image_id, "image_git_commit": commit,
    }
    document = build_release_document(
        protocol=protocol, created_at="2026-08-20T11:00:00+00:00",
        implementation_git_commit=commit, origin_main_commit=commit,
        image_id=image_id, image_platform="linux/arm64", image_git_commit=commit,
        base_image_id=protocol.document["r4_authority"]["image_id"],
        sealed_effect=expected_sealed(protocol), daemon_preflight=daemon,
    )
    return protocol, document


def test_protocol_freezes_only_explicit_r3_protocol_delivery() -> None:
    protocol = LineageProtocol.load()
    change = protocol.document["root_cause_and_only_change"]
    assert change["r3_protocol_container_path"] == R3_PROTOCOL_TARGET
    assert change["r3_protocol_read_only_mount_is_the_only_runtime_input_change"] is True
    assert protocol.document["objective"]["audit_semantics_change"] is False
    assert protocol.document["daemon_preflight_requirements"]["effect_mount_forbidden"] is True


def test_thin_image_top_level_import_path_is_supported() -> None:
    module_root = ROOT / "src/shaiwei/research/production_conversion"
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; sys.path.insert(0, sys.argv[1]); import audit_lineage_recovery_contract; import audit_lineage_recovery_entrypoint",
            str(module_root),
        ],
        cwd=ROOT, check=False, capture_output=True, text=True,
    )
    assert completed.returncode == 0, completed.stderr


def test_release_is_nonexecuting_and_binds_final_preflight(tmp_path: Path) -> None:
    protocol, document = _release()
    release = LineageScope.load(
        _write(tmp_path / "scope.json", document), protocol, compose_path=COMPOSE_PATH
    )
    assert release.scope["authority"]["execution_authorized"] is False
    assert release.scope["authority"]["sealed_effect_read_authorized"] is False
    assert release.scope["daemon_preflight"]["status"] == "PASS"
    assert release.scope["daemon_preflight"]["effect_semantics_read"] is False
    assert release.scope["execution"]["family_portfolio_attempts_consumed"] == 2


@pytest.mark.parametrize(
    "mutation", ["mount", "command", "network", "count", "preflight_path", "preflight_image"]
)
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
    elif mutation == "preflight_path":
        scope["daemon_preflight"]["r3_protocol_path"] = "/workspace/missing.yaml"
    else:
        scope["daemon_preflight"]["final_image_id"] = "sha256:" + "0" * 64
    changed["recovery_scope_sha256"] = canonical_sha256(scope)
    with pytest.raises(ProtocolError):
        LineageScope.load(
            _write(tmp_path / f"{mutation}.json", changed),
            protocol, compose_path=COMPOSE_PATH,
        )


def test_approval_binds_exact_scope_and_narrow_authority(tmp_path: Path) -> None:
    protocol, document = _release()
    release = LineageScope.load(
        _write(tmp_path / "scope.json", document), protocol, compose_path=COMPOSE_PATH
    )
    approval = {
        "schema_version": "m6-production-head30-audit-lineage-entry-recovery-approval-v1",
        "recovery_scope_sha256": release.sha256, "action": ACTION,
        "approved_at": "2026-08-20T11:01:00+00:00", "consumed": False,
        "sealed_effect_read_authorized": True, "independent_audit_write_authorized": True,
        "qlib_mount_authorized": False, "runner_invocation_authorized": False,
        "model_fit_prediction_backtest_authorized": False,
        "experiment_ledger_write_authorized": False,
        "external_network_authorized": False, "env_or_secret_read_authorized": False,
        "production_authorization": "none",
    }
    LineageApproval.load(_write(tmp_path / "approval.json", approval), release)
    approval["runner_invocation_authorized"] = True
    with pytest.raises(ProtocolError, match="authority differs"):
        LineageApproval.load(_write(tmp_path / "bad.json", approval), release)


def test_full_lineage_preflight_uses_real_predecessors(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        r4_entry, "EMBEDDED_ORIGINAL_PROTOCOL",
        PROJECT_ROOT / "config/m6_csi800_production_head30_price_recovery_v1.yaml",
    )
    evidence, *_ = lineage_preflight(
        recovery_protocol_path=ROOT / "config/m6_csi800_production_head30_audit_lineage_entry_recovery_v1.yaml",
        r4_release_path=ROOT / "config/m6_csi800_production_head30_audit_entrypoint_recovery_scope_v1.json",
        r3_protocol_path=ROOT / "config/m6_csi800_production_head30_audit_identity_recovery_v1.yaml",
        r3_release_path=ROOT / "config/m6_csi800_production_head30_audit_identity_recovery_scope_v1.json",
        r4_failure_evidence_path=ROOT / "config/m6_csi800_production_head30_audit_entrypoint_recovery_execution_failure_v1.json",
        original_release_path=ROOT / "config/m6_csi800_production_head30_price_recovery_scope_v1.json",
        original_approval_path=ROOT / "data/control/m6_csi800_production_head30_v1/approval-r2.json",
    )
    assert evidence["status"] == "PASS"
    assert evidence["r3_protocol_sha256"] == "60e36c6ebedcf9051561f6fc823866787a982dac79651e24c40bfb39c2f8d2e2"
    assert evidence["effect_mounted"] is False
    assert evidence["effect_semantics_read"] is False
    assert evidence["audit_invoked"] is False


def test_lineage_preflight_rejects_r4_failure_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        r4_entry, "EMBEDDED_ORIGINAL_PROTOCOL",
        PROJECT_ROOT / "config/m6_csi800_production_head30_price_recovery_v1.yaml",
    )
    failure = json.loads(
        (ROOT / "config/m6_csi800_production_head30_audit_entrypoint_recovery_execution_failure_v1.json").read_text()
    )
    failure["effect_semantics_read"] = True
    with pytest.raises(ProtocolError, match="evidence identity differs"):
        lineage_preflight(
            recovery_protocol_path=ROOT / "config/m6_csi800_production_head30_audit_lineage_entry_recovery_v1.yaml",
            r4_release_path=ROOT / "config/m6_csi800_production_head30_audit_entrypoint_recovery_scope_v1.json",
            r3_protocol_path=ROOT / "config/m6_csi800_production_head30_audit_identity_recovery_v1.yaml",
            r3_release_path=ROOT / "config/m6_csi800_production_head30_audit_identity_recovery_scope_v1.json",
            r4_failure_evidence_path=_write(tmp_path / "failure.json", failure),
            original_release_path=ROOT / "config/m6_csi800_production_head30_price_recovery_scope_v1.json",
            original_approval_path=ROOT / "data/control/m6_csi800_production_head30_v1/approval-r2.json",
        )


def test_compose_fixture_matches_real_lineage_without_effect_mount() -> None:
    document = yaml.safe_load(
        (ROOT / "compose.m6-production-head30-audit-lineage-recovery.yaml").read_text()
    )
    fixture = document["services"]["m6-production-head30-audit-lineage-recovery-fixture"]
    real = document["services"]["m6-production-head30-audit-lineage-recovery"]
    for service in (fixture, real):
        assert service["network_mode"] == "none"
        assert service["read_only"] is True
        assert service["cap_drop"] == ["ALL"]
    fixture_targets = {mount["target"] for mount in fixture["volumes"]}
    real_targets = {mount["target"] for mount in real["volumes"]}
    lineage = {
        "/inputs/recovery-protocol.yaml", "/inputs/r4-release.json",
        "/inputs/r3-protocol.yaml", "/inputs/r3-release.json",
        "/inputs/r4-execution-failure.json", "/inputs/original-release.json",
        "/inputs/original-approval.json",
    }
    assert lineage <= fixture_targets
    assert lineage <= real_targets
    assert "/outputs" not in fixture_targets and "/audit" not in fixture_targets
    assert "/outputs" in real_targets and "/audit" in real_targets
    assert fixture["command"][1] == "/opt/shaiwei/m6-head30-audit-lineage-recovery/entrypoint.py"
    assert "--preflight" in fixture["command"]
