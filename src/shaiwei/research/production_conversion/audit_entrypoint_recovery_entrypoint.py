"""One-shot Head30 audit recovery with the corrected embedded protocol path."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

if __package__:
    from .audit_entrypoint_recovery_contract import (
        EMBEDDED_ORIGINAL_PROTOCOL,
        EntryRecoveryApproval,
        EntryRecoveryProtocol,
        EntryRecoveryScope,
        mapping,
    )
    from .audit_identity_recovery_contract import (
        RecoveryProtocol as R3Protocol,
        effect_tree_identity,
    )
    from .audit_identity_recovery_entrypoint import (
        _audit_documents,
        _synthetic_bundle,
        _verify_sealed_tree,
    )
else:
    from audit_entrypoint_recovery_contract import (  # type: ignore[no-redef]
        EMBEDDED_ORIGINAL_PROTOCOL,
        EntryRecoveryApproval,
        EntryRecoveryProtocol,
        EntryRecoveryScope,
        mapping,
    )
    from audit_identity_recovery_contract import (  # type: ignore[no-redef]
        RecoveryProtocol as R3Protocol,
        effect_tree_identity,
    )
    from audit_identity_recovery_entrypoint import (  # type: ignore[no-redef]
        _audit_documents,
        _synthetic_bundle,
        _verify_sealed_tree,
    )

from shaiwei.research.model_attribution.contract import canonical_sha256, sha256_file
from shaiwei.research.production_conversion.contract import ProtocolError
from shaiwei.research.production_conversion.real_contract import (
    Approval,
    ReleaseProtocol,
    ReleaseScope,
    write_once_document,
)


EMBEDDED_R3_PROTOCOL = Path(
    "/workspace/config/m6_csi800_production_head30_audit_identity_recovery_v1.yaml"
)


def _runtime_identity(release: EntryRecoveryScope) -> dict[str, str]:
    root = Path(__file__).parent
    observed = {
        "git_commit": os.getenv("SHAIWEI_M6_HEAD30_AUDIT_ENTRY_RECOVERY_GIT_HEAD", "").strip(),
        "contract_sha256": sha256_file(root / "audit_entrypoint_recovery_contract.py"),
        "entrypoint_sha256": sha256_file(Path(__file__)),
        "r3_contract_sha256": sha256_file(root / "audit_identity_recovery_contract.py"),
        "r3_entrypoint_sha256": sha256_file(root / "audit_identity_recovery_entrypoint.py"),
    }
    expected = release.scope["implementation"]
    if observed != {key: expected[key] for key in observed}:
        raise ProtocolError("Head30 audit-entry recovery runtime identity differs")
    return observed


def _verify_r3_lineage(
    *, protocol: EntryRecoveryProtocol, r3_release_path: Path, r3_failure_path: Path
) -> R3Protocol:
    r3 = protocol.document["r3_authority"]
    if sha256_file(EMBEDDED_R3_PROTOCOL) != r3["protocol_sha256"]:
        raise ProtocolError("Head30 embedded R3 protocol identity differs")
    r3_protocol = R3Protocol.load(EMBEDDED_R3_PROTOCOL)
    r3_release = mapping(r3_release_path)
    if (
        sha256_file(r3_release_path) != r3["release_document_sha256"]
        or r3_release.get("recovery_scope_sha256") != r3["release_scope_sha256"]
    ):
        raise ProtocolError("Head30 R3 release identity differs")
    failure = protocol.document["r3_execution_failure"]
    if sha256_file(r3_failure_path) != failure["evidence_sha256"]:
        raise ProtocolError("Head30 R3 execution failure identity differs")
    observed_failure = mapping(r3_failure_path)
    expected = {
        "recovery_scope_sha256": r3["release_scope_sha256"],
        "effect_semantics_read": False,
        "audit_output_file_count": 0,
        "runner_invocation_count": 0,
        "additional_portfolio_attempt_count": 0,
        "same_scope_retry_authorized": False,
    }
    if any(observed_failure.get(key) != value for key, value in expected.items()):
        raise ProtocolError("Head30 R3 failure state differs")
    return r3_protocol


def _verify_original_authority(
    *, r3_protocol: R3Protocol, original_release_path: Path, original_approval_path: Path
) -> tuple[ReleaseProtocol, ReleaseScope, Approval]:
    original = r3_protocol.document["original_authority"]
    protocol = ReleaseProtocol.load(EMBEDDED_ORIGINAL_PROTOCOL)
    release = ReleaseScope.load(original_release_path, protocol)
    approval = Approval.load(original_approval_path, release)
    if sha256_file(EMBEDDED_ORIGINAL_PROTOCOL) != (
        "6e4fc89c5c02db862681866e96d1e8063e6b6bc2a6bb58c3cfc08819ba327a6e"
    ):
        raise ProtocolError("Head30 embedded original protocol identity differs")
    if (
        release.sha256 != original["release_scope_sha256"]
        or sha256_file(original_release_path) != original["release_document_sha256"]
        or approval.sha256 != original["approval_sha256"]
    ):
        raise ProtocolError("Head30 original R2 authority differs")
    return protocol, release, approval


def run(
    *, recovery_protocol_path: Path, recovery_release_path: Path,
    recovery_approval_path: Path, recovery_compose_path: Path,
    r3_release_path: Path, r3_failure_evidence_path: Path,
    original_release_path: Path, original_approval_path: Path,
    effect_root: Path, audit_root: Path,
) -> dict[str, Any]:
    protocol = EntryRecoveryProtocol.load(recovery_protocol_path)
    release = EntryRecoveryScope.load(
        recovery_release_path, protocol, compose_path=recovery_compose_path
    )
    approval = EntryRecoveryApproval.load(recovery_approval_path, release)
    runtime = _runtime_identity(release)
    r3_protocol = _verify_r3_lineage(
        protocol=protocol, r3_release_path=r3_release_path,
        r3_failure_path=r3_failure_evidence_path,
    )
    original_protocol, original_release, original_approval = _verify_original_authority(
        r3_protocol=r3_protocol, original_release_path=original_release_path,
        original_approval_path=original_approval_path,
    )
    before = _verify_sealed_tree(effect_root=effect_root, audit_root=audit_root, release=release)
    first_path = effect_root / "first_pass/bundle.json"
    replay_path = effect_root / "replay/bundle.json"
    first = mapping(first_path)
    replay = mapping(replay_path)
    report = mapping(effect_root / "report.json")
    checks, rebuilt, primary_sha, independent_sha = _audit_documents(
        first, replay, report,
        first_sha=sha256_file(first_path), replay_sha=sha256_file(replay_path),
        converter_protocol_sha256=original_protocol.base.sha256,
        release_engineering_sha256=original_protocol.sha256,
    )
    sealed = release.scope["sealed_effect"]
    checks.update({
        "release_and_approval_identity": report.get("release_scope_sha256") == original_release.sha256 and report.get("approval_sha256") == original_approval.sha256,
        "sealed_report_identity": sha256_file(effect_root / "report.json") == sealed["report_sha256"],
        "sealed_primary_result_identity": primary_sha == sealed["primary_result_sha256"],
        "sealed_decision_identity": report.get("decision") == sealed["primary_decision"],
        "independent_result_lineage": independent_sha == r3_protocol.document["root_cause"]["independent_result_sha256"],
        "attempt_count": report.get("portfolio_attempts_consumed") == 1 and report.get("model_attempt_increment") == 0,
        "pending_audit_state": report.get("strategy_effective") == "PENDING_INDEPENDENT_AUDIT" and report.get("production_authorization") == "none",
        "no_failure_artifact": not (effect_root / "failure.json").exists(),
    })
    if not all(checks.values()):
        raise ProtocolError(
            f"Head30 audit-entry recovery failed: {[name for name, passed in checks.items() if not passed]}"
        )
    audit_root.mkdir(parents=True, exist_ok=True)
    audit = {
        "schema_version": "m6-production-head30-audit-entrypoint-recovery-audit-v1",
        "recovery_scope_sha256": release.sha256,
        "recovery_approval_sha256": approval.sha256,
        "original_release_scope_sha256": original_release.sha256,
        "original_approval_sha256": original_approval.sha256,
        "report_sha256": sealed["report_sha256"],
        "bundle_sha256": sealed["first_pass_bundle_sha256"],
        "primary_result_sha256": primary_sha,
        "independent_result_sha256": independent_sha,
        "independent_hash_equality_with_primary_required": False,
        "checks": checks, "decision": rebuilt["decision"],
        "independent_audit": "PASS", "strategy_effective": rebuilt["decision"],
        "additional_portfolio_attempt_count": 0, "production_authorization": "none",
    }
    audit_sha, reused = write_once_document(audit_root / "audit.json", audit)
    if reused:
        raise ProtocolError("Head30 audit-entry recovery output unexpectedly pre-existed")
    after = _verify_effect_unchanged(effect_root, before)
    receipt = {
        "schema_version": "m6-production-head30-audit-entrypoint-recovery-receipt-v1",
        "recovery_scope_sha256": release.sha256,
        "recovery_approval_sha256": approval.sha256, "audit_sha256": audit_sha,
        "effect_tree_before": before, "effect_tree_after": after,
        "runtime_identity": runtime, "embedded_original_protocol_path": str(EMBEDDED_ORIGINAL_PROTOCOL),
        "runner_invocation_count": 0, "recovery_auditor_invocation_count": 1,
        "additional_portfolio_attempt_count": 0, "family_portfolio_attempts_consumed": 2,
        "production_authorization": "none",
    }
    receipt_sha, receipt_reused = write_once_document(audit_root / "recovery-receipt.json", receipt)
    if receipt_reused:
        raise ProtocolError("Head30 audit-entry recovery receipt unexpectedly pre-existed")
    return {
        "audit_sha256": audit_sha, "recovery_receipt_sha256": receipt_sha,
        "decision": rebuilt["decision"], "effect_tree_unchanged": True,
        "additional_portfolio_attempt_count": 0, "production_authorization": "none",
    }


def _verify_effect_unchanged(effect_root: Path, before: dict[str, Any]) -> dict[str, Any]:
    after = effect_tree_identity(effect_root)
    if after != before:
        raise ProtocolError("Head30 sealed effect changed during audit-entry recovery")
    return after


def self_test() -> dict[str, Any]:
    loaded = ReleaseProtocol.load(EMBEDDED_ORIGINAL_PROTOCOL)
    expected_sha = "6e4fc89c5c02db862681866e96d1e8063e6b6bc2a6bb58c3cfc08819ba327a6e"
    if sha256_file(EMBEDDED_ORIGINAL_PROTOCOL) != expected_sha:
        raise ProtocolError("Head30 daemon fixture embedded protocol hash differs")
    bundle = _synthetic_bundle()
    bundle_sha = canonical_sha256(bundle)
    report = {
        "decision": bundle["result"]["decision"],
        "first_pass_bundle_sha256": bundle_sha,
        "replay_bundle_sha256": bundle_sha,
        "result_sha256": canonical_sha256(bundle["result"]),
    }
    checks, *_ = _audit_documents(
        bundle, bundle, report, first_sha=bundle_sha, replay_sha=bundle_sha,
        converter_protocol_sha256=bundle["converter_protocol_sha256"],
        release_engineering_sha256=bundle["release_engineering_sha256"],
    )
    if not all(checks.values()):
        raise ProtocolError("Head30 audit-entry recovery inherited audit self-test failed")
    return {
        "status": "PASS", "loaded_path": str(EMBEDDED_ORIGINAL_PROTOCOL),
        "protocol_sha256": expected_sha, "release_protocol_sha256": loaded.sha256,
        "inherited_audit_semantics": "PASS", "real_effect_read": False,
        "audit_invoked": False, "production_authorization": "none",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--recovery-protocol", type=Path)
    parser.add_argument("--recovery-release", type=Path)
    parser.add_argument("--recovery-approval", type=Path)
    parser.add_argument("--recovery-compose", type=Path)
    parser.add_argument("--r3-release", type=Path)
    parser.add_argument("--r3-failure-evidence", type=Path)
    parser.add_argument("--original-release", type=Path)
    parser.add_argument("--original-approval", type=Path)
    parser.add_argument("--effect-root", type=Path)
    parser.add_argument("--audit-root", type=Path)
    args = parser.parse_args()
    if args.self_test:
        print(json.dumps(self_test(), sort_keys=True))
        return 0
    required = {key: value for key, value in vars(args).items() if key != "self_test"}
    if any(value is None for value in required.values()):
        parser.error("all audit-entry recovery inputs are required")
    print(json.dumps(run(**{f"{key}_path" if key not in {"effect_root", "audit_root"} else key: value for key, value in required.items()}), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
