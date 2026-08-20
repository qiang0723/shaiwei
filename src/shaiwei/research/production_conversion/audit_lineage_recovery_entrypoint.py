"""One-shot Head30 audit recovery with complete lineage preflight."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

if __package__:
    from .audit_lineage_recovery_contract import (
        LineageApproval,
        LineageProtocol,
        LineageScope,
        mapping,
    )
    from .audit_identity_recovery_contract import RecoveryProtocol as R3Protocol
    from .audit_entrypoint_recovery_entrypoint import (
        _audit_documents,
        _verify_effect_unchanged,
        _verify_original_authority,
        _verify_sealed_tree,
    )
else:
    from audit_lineage_recovery_contract import (  # type: ignore[no-redef]
        LineageApproval,
        LineageProtocol,
        LineageScope,
        mapping,
    )
    from audit_identity_recovery_contract import RecoveryProtocol as R3Protocol  # type: ignore[no-redef]
    from audit_entrypoint_recovery_entrypoint import (  # type: ignore[no-redef]
        _audit_documents,
        _verify_effect_unchanged,
        _verify_original_authority,
        _verify_sealed_tree,
    )

from shaiwei.research.model_attribution.contract import sha256_file
from shaiwei.research.production_conversion.contract import ProtocolError
from shaiwei.research.production_conversion.real_contract import write_once_document


def _runtime_identity(release: LineageScope) -> dict[str, str]:
    root = Path(__file__).parent
    observed = {
        "git_commit": os.getenv("SHAIWEI_M6_HEAD30_AUDIT_LINEAGE_RECOVERY_GIT_HEAD", "").strip(),
        "contract_sha256": sha256_file(root / "audit_lineage_recovery_contract.py"),
        "entrypoint_sha256": sha256_file(Path(__file__)),
        "r4_contract_sha256": sha256_file(root / "audit_entrypoint_recovery_contract.py"),
        "r4_entrypoint_sha256": sha256_file(root / "audit_entrypoint_recovery_entrypoint.py"),
        "r3_contract_sha256": sha256_file(root / "audit_identity_recovery_contract.py"),
        "r3_entrypoint_sha256": sha256_file(root / "audit_identity_recovery_entrypoint.py"),
    }
    expected = release.scope["implementation"]
    if observed != {key: expected[key] for key in observed}:
        raise ProtocolError("Head30 audit-lineage runtime identity differs")
    return observed


def lineage_preflight(
    *, recovery_protocol_path: Path, r4_release_path: Path,
    r3_protocol_path: Path, r3_release_path: Path,
    r4_failure_evidence_path: Path, original_release_path: Path,
    original_approval_path: Path,
) -> tuple[dict[str, Any], R3Protocol, Any, Any, Any]:
    protocol = LineageProtocol.load(recovery_protocol_path)
    r4 = protocol.document["r4_authority"]
    r4_release = mapping(r4_release_path)
    if (
        sha256_file(r4_release_path) != r4["release_document_sha256"]
        or r4_release.get("recovery_scope_sha256") != r4["release_scope_sha256"]
    ):
        raise ProtocolError("Head30 R4 release identity differs during R5 preflight")
    r4_scope = r4_release.get("scope")
    if not isinstance(r4_scope, dict) or r4_scope.get("protocol_sha256") != r4["protocol_sha256"]:
        raise ProtocolError("Head30 R4 release lineage differs during R5 preflight")
    expected_r3 = r4_scope.get("r3_authority", {})
    change = protocol.document["root_cause_and_only_change"]
    if sha256_file(r3_protocol_path) != change["r3_protocol_sha256"]:
        raise ProtocolError("Head30 explicit R3 protocol identity differs")
    r3_protocol = R3Protocol.load(r3_protocol_path)
    if r3_protocol.sha256 != expected_r3.get("protocol_sha256"):
        raise ProtocolError("Head30 R3 protocol is not the R4-bound predecessor")
    r3_release = mapping(r3_release_path)
    if (
        sha256_file(r3_release_path) != expected_r3.get("release_document_sha256")
        or r3_release.get("recovery_scope_sha256") != expected_r3.get("release_scope_sha256")
    ):
        raise ProtocolError("Head30 R3 release identity differs during R5 preflight")
    failure = protocol.document["r4_execution_failure"]
    if sha256_file(r4_failure_evidence_path) != failure["evidence_sha256"]:
        raise ProtocolError("Head30 R4 failure evidence identity differs")
    observed_failure = mapping(r4_failure_evidence_path)
    expected_failure = {
        "r4_scope_sha256": r4["release_scope_sha256"],
        "effect_semantics_read": False, "audit_output_file_count": 0,
        "runner_invocation_count": 0, "additional_portfolio_attempt_count": 0,
        "same_scope_retry_authorized": False,
    }
    if any(observed_failure.get(key) != value for key, value in expected_failure.items()):
        raise ProtocolError("Head30 R4 failure state differs during R5 preflight")
    original_protocol, original_release, original_approval = _verify_original_authority(
        r3_protocol=r3_protocol, original_release_path=original_release_path,
        original_approval_path=original_approval_path,
    )
    evidence = {
        "schema_version": "m6-production-head30-audit-lineage-daemon-preflight-v1",
        "status": "PASS", "r5_protocol_sha256": protocol.sha256,
        "r4_release_document_sha256": sha256_file(r4_release_path),
        "r4_release_scope_sha256": r4["release_scope_sha256"],
        "r3_protocol_path": str(r3_protocol_path), "r3_protocol_sha256": r3_protocol.sha256,
        "r3_release_document_sha256": sha256_file(r3_release_path),
        "r3_release_scope_sha256": r3_release["recovery_scope_sha256"],
        "r4_failure_evidence_sha256": sha256_file(r4_failure_evidence_path),
        "original_release_scope_sha256": original_release.sha256,
        "original_approval_sha256": original_approval.sha256,
        "original_protocol_sha256": original_protocol.sha256,
        "image_git_commit": os.getenv("SHAIWEI_M6_HEAD30_AUDIT_LINEAGE_RECOVERY_GIT_HEAD", "").strip(),
        "same_preflight_function_as_real_entrypoint": True,
        "effect_mounted": False, "effect_semantics_read": False,
        "audit_invoked": False, "production_authorization": "none",
    }
    return evidence, r3_protocol, original_protocol, original_release, original_approval


def run(
    *, recovery_protocol_path: Path, recovery_release_path: Path,
    recovery_approval_path: Path, recovery_compose_path: Path,
    r4_release_path: Path, r3_protocol_path: Path, r3_release_path: Path,
    r4_failure_evidence_path: Path, original_release_path: Path,
    original_approval_path: Path, effect_root: Path, audit_root: Path,
) -> dict[str, Any]:
    protocol = LineageProtocol.load(recovery_protocol_path)
    release = LineageScope.load(recovery_release_path, protocol, compose_path=recovery_compose_path)
    approval = LineageApproval.load(recovery_approval_path, release)
    runtime = _runtime_identity(release)
    preflight, r3_protocol, original_protocol, original_release, original_approval = lineage_preflight(
        recovery_protocol_path=recovery_protocol_path, r4_release_path=r4_release_path,
        r3_protocol_path=r3_protocol_path, r3_release_path=r3_release_path,
        r4_failure_evidence_path=r4_failure_evidence_path,
        original_release_path=original_release_path, original_approval_path=original_approval_path,
    )
    before = _verify_sealed_tree(effect_root=effect_root, audit_root=audit_root, release=release)
    first_path = effect_root / "first_pass/bundle.json"
    replay_path = effect_root / "replay/bundle.json"
    first, replay = mapping(first_path), mapping(replay_path)
    report = mapping(effect_root / "report.json")
    checks, rebuilt, primary_sha, independent_sha = _audit_documents(
        first, replay, report, first_sha=sha256_file(first_path),
        replay_sha=sha256_file(replay_path),
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
            f"Head30 audit-lineage recovery failed: {[name for name, passed in checks.items() if not passed]}"
        )
    audit_root.mkdir(parents=True, exist_ok=True)
    audit = {
        "schema_version": "m6-production-head30-audit-lineage-entry-recovery-audit-v1",
        "recovery_scope_sha256": release.sha256, "recovery_approval_sha256": approval.sha256,
        "original_release_scope_sha256": original_release.sha256,
        "original_approval_sha256": original_approval.sha256,
        "report_sha256": sealed["report_sha256"], "bundle_sha256": sealed["first_pass_bundle_sha256"],
        "primary_result_sha256": primary_sha, "independent_result_sha256": independent_sha,
        "independent_hash_equality_with_primary_required": False,
        "checks": checks, "decision": rebuilt["decision"], "independent_audit": "PASS",
        "strategy_effective": rebuilt["decision"], "additional_portfolio_attempt_count": 0,
        "production_authorization": "none",
    }
    audit_sha, reused = write_once_document(audit_root / "audit.json", audit)
    if reused:
        raise ProtocolError("Head30 audit-lineage output unexpectedly pre-existed")
    after = _verify_effect_unchanged(effect_root, before)
    receipt = {
        "schema_version": "m6-production-head30-audit-lineage-entry-recovery-receipt-v1",
        "recovery_scope_sha256": release.sha256, "recovery_approval_sha256": approval.sha256,
        "audit_sha256": audit_sha, "effect_tree_before": before, "effect_tree_after": after,
        "runtime_identity": runtime, "lineage_preflight": preflight,
        "runner_invocation_count": 0, "recovery_auditor_invocation_count": 1,
        "additional_portfolio_attempt_count": 0, "family_portfolio_attempts_consumed": 2,
        "production_authorization": "none",
    }
    receipt_sha, receipt_reused = write_once_document(audit_root / "recovery-receipt.json", receipt)
    if receipt_reused:
        raise ProtocolError("Head30 audit-lineage receipt unexpectedly pre-existed")
    return {
        "audit_sha256": audit_sha, "recovery_receipt_sha256": receipt_sha,
        "decision": rebuilt["decision"], "effect_tree_unchanged": True,
        "additional_portfolio_attempt_count": 0, "production_authorization": "none",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--recovery-protocol", type=Path, required=True)
    parser.add_argument("--recovery-release", type=Path)
    parser.add_argument("--recovery-approval", type=Path)
    parser.add_argument("--recovery-compose", type=Path)
    parser.add_argument("--r4-release", type=Path, required=True)
    parser.add_argument("--r3-protocol", type=Path, required=True)
    parser.add_argument("--r3-release", type=Path, required=True)
    parser.add_argument("--r4-failure-evidence", type=Path, required=True)
    parser.add_argument("--original-release", type=Path, required=True)
    parser.add_argument("--original-approval", type=Path, required=True)
    parser.add_argument("--preflight-output", type=Path)
    parser.add_argument("--effect-root", type=Path)
    parser.add_argument("--audit-root", type=Path)
    args = parser.parse_args()
    lineage = {
        "recovery_protocol_path": args.recovery_protocol,
        "r4_release_path": args.r4_release, "r3_protocol_path": args.r3_protocol,
        "r3_release_path": args.r3_release,
        "r4_failure_evidence_path": args.r4_failure_evidence,
        "original_release_path": args.original_release,
        "original_approval_path": args.original_approval,
    }
    if args.preflight:
        if args.preflight_output is None:
            parser.error("preflight output is required")
        evidence, *_ = lineage_preflight(**lineage)
        digest, _ = write_once_document(args.preflight_output, evidence)
        print(json.dumps({**evidence, "evidence_sha256": digest}, sort_keys=True))
        return 0
    required = (args.recovery_release, args.recovery_approval, args.recovery_compose, args.effect_root, args.audit_root)
    if any(value is None for value in required):
        parser.error("all real audit-lineage recovery inputs are required")
    print(json.dumps(run(
        **lineage, recovery_release_path=args.recovery_release,
        recovery_approval_path=args.recovery_approval,
        recovery_compose_path=args.recovery_compose,
        effect_root=args.effect_root, audit_root=args.audit_root,
    ), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
