from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
import yaml

from shaiwei.research.model_attribution.contract import canonical_sha256
from shaiwei.research.production_conversion.audit_identity_recovery_contract import (
    ACTION,
    COMPOSE_PATH,
    RecoveryApproval,
    RecoveryProtocol,
    RecoveryReleaseScope,
    effect_tree_identity,
    expected_sealed,
)
from shaiwei.research.production_conversion.audit_identity_recovery_entrypoint import (
    _audit_documents,
    _synthetic_bundle,
    self_test,
)
from shaiwei.research.production_conversion.audit_identity_recovery_release import (
    build_release_document,
)
from shaiwei.research.production_conversion.contract import ProtocolError


ROOT = Path(__file__).parents[1]


def _write(path: Path, value: dict) -> Path:
    path.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n")
    return path


def _release() -> tuple[RecoveryProtocol, dict]:
    protocol = RecoveryProtocol.load()
    original = protocol.document["original_authority"]
    document = build_release_document(
        protocol=protocol,
        created_at="2026-08-20T10:00:00+00:00",
        implementation_git_commit="a" * 40,
        origin_main_commit="a" * 40,
        image_id="sha256:" + "b" * 64,
        image_platform="linux/arm64",
        image_git_commit="a" * 40,
        base_image_id=original["base_image_id"],
        sealed_effect=expected_sealed(protocol),
    )
    return protocol, document


def _documents() -> tuple[dict, dict, dict, str]:
    first = _synthetic_bundle()
    first["result"] = copy.deepcopy(first["result"])
    first["result"]["windows"]["W1"]["cash_ratio_mean"] += 1e-15
    replay = copy.deepcopy(first)
    bundle_sha = canonical_sha256(first)
    report = {
        "decision": first["result"]["decision"],
        "first_pass_bundle_sha256": bundle_sha,
        "replay_bundle_sha256": bundle_sha,
        "result_sha256": canonical_sha256(first["result"]),
    }
    return first, replay, report, bundle_sha


def _audit(first: dict, replay: dict, report: dict, bundle_sha: str):
    return _audit_documents(
        first,
        replay,
        report,
        first_sha=bundle_sha,
        replay_sha=bundle_sha,
        converter_protocol_sha256="a" * 64,
        release_engineering_sha256="b" * 64,
    )


def test_protocol_and_release_grant_no_execution_before_approval(tmp_path: Path) -> None:
    protocol, document = _release()
    release = RecoveryReleaseScope.load(
        _write(tmp_path / "scope.json", document), protocol, compose_path=COMPOSE_PATH
    )
    assert release.sha256 == canonical_sha256(document["scope"])
    assert release.scope["execution"]["additional_portfolio_attempt_count"] == 0
    assert release.scope["authority"]["execution_authorized"] is False
    assert release.scope["authority"]["sealed_effect_read_authorized"] is False
    assert release.scope["authority"]["production_authorization"] == "none"


@pytest.mark.parametrize("mutation", ["authority", "mount", "command", "count", "image"])
def test_release_rejects_rehashed_boundary_drift(tmp_path: Path, mutation: str) -> None:
    protocol, document = _release()
    changed = copy.deepcopy(document)
    if mutation == "authority":
        changed["scope"]["authority"]["external_network_authorized"] = True
    elif mutation == "mount":
        changed["scope"]["container"]["mounts"][0]["source"] = "."
    elif mutation == "command":
        changed["scope"]["container"]["command"][-1] = "/other"
    elif mutation == "count":
        changed["scope"]["execution"]["additional_portfolio_attempt_count"] = 1
    else:
        changed["scope"]["image"]["base_image_id"] = "sha256:" + "0" * 64
    changed["recovery_scope_sha256"] = canonical_sha256(changed["scope"])
    with pytest.raises(ProtocolError):
        RecoveryReleaseScope.load(
            _write(tmp_path / f"{mutation}.json", changed),
            protocol,
            compose_path=COMPOSE_PATH,
        )


def test_approval_binds_exact_scope_and_narrow_authority(tmp_path: Path) -> None:
    protocol, document = _release()
    release = RecoveryReleaseScope.load(
        _write(tmp_path / "scope.json", document), protocol, compose_path=COMPOSE_PATH
    )
    approval = {
        "schema_version": "m6-production-head30-audit-identity-recovery-approval-v1",
        "recovery_scope_sha256": release.sha256,
        "action": ACTION,
        "approved_at": "2026-08-20T10:01:00+00:00",
        "consumed": False,
        "sealed_effect_read_authorized": True,
        "independent_audit_write_authorized": True,
        "qlib_mount_authorized": False,
        "runner_invocation_authorized": False,
        "model_fit_prediction_backtest_authorized": False,
        "experiment_ledger_write_authorized": False,
        "external_network_authorized": False,
        "env_or_secret_read_authorized": False,
        "production_authorization": "none",
    }
    RecoveryApproval.load(_write(tmp_path / "approval.json", approval), release)
    approval["runner_invocation_authorized"] = True
    with pytest.raises(ProtocolError, match="authority differs"):
        RecoveryApproval.load(_write(tmp_path / "bad.json", approval), release)


def test_independent_float_tail_is_equivalent_without_hash_equality() -> None:
    first, replay, report, bundle_sha = _documents()
    checks, _, primary_sha, independent_sha = _audit(first, replay, report, bundle_sha)
    assert all(checks.values())
    assert primary_sha != independent_sha


def test_primary_hash_drift_and_decision_drift_fail_closed() -> None:
    first, replay, report, bundle_sha = _documents()
    report["result_sha256"] = "0" * 64
    checks, *_ = _audit(first, replay, report, bundle_sha)
    assert checks["primary_result_identity"] is False
    report["result_sha256"] = canonical_sha256(first["result"])
    report["decision"] = "REJECTED_RESEARCH_SCALE"
    checks, *_ = _audit(first, replay, report, bundle_sha)
    assert checks["exact_decision_identity"] is False


def test_difference_above_frozen_tolerance_fails_closed() -> None:
    first, replay, report, bundle_sha = _documents()
    first["result"]["windows"]["W1"]["cash_ratio_mean"] += 1e-6
    replay = copy.deepcopy(first)
    bundle_sha = canonical_sha256(first)
    report["first_pass_bundle_sha256"] = bundle_sha
    report["replay_bundle_sha256"] = bundle_sha
    report["result_sha256"] = canonical_sha256(first["result"])
    checks, *_ = _audit(first, replay, report, bundle_sha)
    assert checks["independent_first_reconstruction"] is False


def test_effect_tree_detects_content_and_membership_changes(tmp_path: Path) -> None:
    root = tmp_path / "effect"
    root.mkdir()
    (root / "one").write_text("one")
    before = effect_tree_identity(root)
    assert effect_tree_identity(root) == before
    (root / "one").write_text("two")
    assert effect_tree_identity(root) != before
    (root / "extra").write_text("extra")
    assert effect_tree_identity(root)["file_count"] == 2


def test_compose_is_auditor_only_and_has_no_qlib_or_network() -> None:
    document = yaml.safe_load(
        (ROOT / "compose.m6-production-head30-audit-recovery.yaml").read_text()
    )
    service = document["services"]["m6-production-head30-audit-recovery"]
    assert service["network_mode"] == "none"
    assert service["read_only"] is True
    assert service["cap_drop"] == ["ALL"]
    sources = [mount["source"] for mount in service["volumes"]]
    assert not any("qlib" in source for source in sources)
    assert not any(source in {".", "./"} for source in sources)
    effect_mount = next(
        mount for mount in service["volumes"] if mount["target"] == "/outputs"
    )
    assert effect_mount["read_only"] is True


def test_self_test_is_synthetic_and_result_blind() -> None:
    result = self_test()
    assert result["floating_tail_semantic_equivalence"] == "PASS"
    assert result["primary_and_independent_hashes_distinct"] == "PASS"
    assert result["real_effect_read"] is False
    assert result["audit_invoked"] is False
    assert result["production_authorization"] == "none"
