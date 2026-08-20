"""One-shot Head30 audit recovery with corrected independent-hash authority."""

from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
from typing import Any

if __package__:
    from .audit_hash_authority_contract import (
        HashAuthorityApproval,
        HashAuthorityProtocol,
        HashAuthorityScope,
        mapping,
    )
    from .audit_identity_recovery_entrypoint import _audit_documents, _synthetic_bundle
    from .audit_entrypoint_recovery_entrypoint import (
        _verify_effect_unchanged,
        _verify_sealed_tree,
    )
    from .audit_lineage_recovery_entrypoint import lineage_preflight as r5_lineage_preflight
else:
    from audit_hash_authority_contract import (  # type: ignore[no-redef]
        HashAuthorityApproval,
        HashAuthorityProtocol,
        HashAuthorityScope,
        mapping,
    )
    from audit_identity_recovery_entrypoint import (  # type: ignore[no-redef]
        _audit_documents,
        _synthetic_bundle,
    )
    from audit_entrypoint_recovery_entrypoint import (  # type: ignore[no-redef]
        _verify_effect_unchanged,
        _verify_sealed_tree,
    )
    from audit_lineage_recovery_entrypoint import (  # type: ignore[no-redef]
        lineage_preflight as r5_lineage_preflight,
    )

from shaiwei.research.model_attribution.contract import canonical_sha256, sha256_file
from shaiwei.research.production_conversion.contract import ProtocolError
from shaiwei.research.production_conversion.real_contract import write_once_document


def _sha(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(char in "0123456789abcdef" for char in value)


def validate_independent_hash_authority(
    checks: dict[str, bool], *, current_sha: str, historical_sha: str
) -> dict[str, Any]:
    if not all(checks.values()):
        raise ProtocolError(
            f"Head30 hash-authority substantive audit failed: {[key for key, value in checks.items() if not value]}"
        )
    if not _sha(current_sha) or not _sha(historical_sha):
        raise ProtocolError("Head30 hash-authority diagnostic SHA is invalid")
    return {
        "current_independent_result_sha256": current_sha,
        "historical_independent_result_sha256": historical_sha,
        "historical_hash_equal": current_sha == historical_sha,
        "historical_hash_equality_required": False,
        "current_independent_sha_recorded": True,
        "substantive_checks_passed": True,
    }


def _runtime_identity(release: HashAuthorityScope) -> dict[str, str]:
    root = Path(__file__).parent
    observed = {
        "git_commit": os.getenv("SHAIWEI_M6_HEAD30_AUDIT_HASH_AUTHORITY_GIT_HEAD", "").strip(),
        "contract_sha256": sha256_file(root / "audit_hash_authority_contract.py"),
        "entrypoint_sha256": sha256_file(Path(__file__)),
        "r5_contract_sha256": sha256_file(root / "audit_lineage_recovery_contract.py"),
        "r5_entrypoint_sha256": sha256_file(root / "audit_lineage_recovery_entrypoint.py"),
        "r4_contract_sha256": sha256_file(root / "audit_entrypoint_recovery_contract.py"),
        "r4_entrypoint_sha256": sha256_file(root / "audit_entrypoint_recovery_entrypoint.py"),
        "r3_contract_sha256": sha256_file(root / "audit_identity_recovery_contract.py"),
        "r3_entrypoint_sha256": sha256_file(root / "audit_identity_recovery_entrypoint.py"),
    }
    expected = release.scope["implementation"]
    if observed != {key: expected[key] for key in observed}:
        raise ProtocolError("Head30 hash-authority runtime identity differs")
    return observed


def full_preflight(
    *, recovery_protocol_path: Path, r5_protocol_path: Path,
    r5_release_path: Path, r5_approval_path: Path, r5_failure_evidence_path: Path,
    r4_release_path: Path, r3_protocol_path: Path, r3_release_path: Path,
    r4_failure_evidence_path: Path, original_release_path: Path,
    original_approval_path: Path,
) -> tuple[dict[str, Any], Any, Any, Any, Any]:
    protocol = HashAuthorityProtocol.load(recovery_protocol_path)
    r5 = protocol.document["r5_authority"]
    r5_release = mapping(r5_release_path)
    if (
        sha256_file(r5_protocol_path) != r5["protocol_sha256"]
        or sha256_file(r5_release_path) != r5["release_document_sha256"]
        or r5_release.get("recovery_scope_sha256") != r5["release_scope_sha256"]
        or sha256_file(r5_approval_path) != r5["approval_sha256"]
    ):
        raise ProtocolError("Head30 R5 authority differs during R6 preflight")
    failure = protocol.document["r5_execution_failure"]
    if sha256_file(r5_failure_evidence_path) != failure["evidence_sha256"]:
        raise ProtocolError("Head30 R5 failure evidence identity differs")
    observed_failure = mapping(r5_failure_evidence_path)
    expected_failure = {
        "r5_scope_sha256": r5["release_scope_sha256"],
        "effect_semantics_read": True, "independent_reconstruction_completed": True,
        "independent_tolerance_equivalence_passed": True, "decision_identity_passed": True,
        "all_other_audit_checks_passed": True, "audit_output_file_count": 0,
        "runner_invocation_count": 0, "additional_portfolio_attempt_count": 0,
        "same_scope_retry_authorized": False, "failed_check": "independent_result_lineage",
    }
    if any(observed_failure.get(key) != value for key, value in expected_failure.items()):
        raise ProtocolError("Head30 R5 failure state differs during R6 preflight")
    lineage, r3_protocol, original_protocol, original_release, original_approval = r5_lineage_preflight(
        recovery_protocol_path=r5_protocol_path, r4_release_path=r4_release_path,
        r3_protocol_path=r3_protocol_path, r3_release_path=r3_release_path,
        r4_failure_evidence_path=r4_failure_evidence_path,
        original_release_path=original_release_path, original_approval_path=original_approval_path,
    )
    evidence = {
        "r6_protocol_sha256": protocol.sha256,
        "r5_protocol_sha256": sha256_file(r5_protocol_path),
        "r5_release_document_sha256": sha256_file(r5_release_path),
        "r5_release_scope_sha256": r5["release_scope_sha256"],
        "r5_approval_sha256": sha256_file(r5_approval_path),
        "r5_failure_evidence_sha256": sha256_file(r5_failure_evidence_path),
        "r5_r4_r3_r2_lineage_preflight_status": lineage["status"],
    }
    return evidence, r3_protocol, original_protocol, original_release, original_approval


def semantic_fixture() -> dict[str, str]:
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
    checks, _, _, independent_sha = _audit_documents(
        first, replay, report, first_sha=bundle_sha, replay_sha=bundle_sha,
        converter_protocol_sha256=first["converter_protocol_sha256"],
        release_engineering_sha256=first["release_engineering_sha256"],
    )
    authority = validate_independent_hash_authority(
        checks, current_sha=independent_sha, historical_sha="0" * 64
    )
    if authority["historical_hash_equal"]:
        raise ProtocolError("Head30 hash-authority mismatch fixture is not distinct")
    above = copy.deepcopy(first)
    above["result"]["windows"]["W1"]["cash_ratio_mean"] += 1e-6
    above_sha = canonical_sha256(above)
    above_report = {
        **report, "first_pass_bundle_sha256": above_sha,
        "replay_bundle_sha256": above_sha,
        "result_sha256": canonical_sha256(above["result"]),
    }
    above_checks, _, _, above_independent = _audit_documents(
        above, copy.deepcopy(above), above_report,
        first_sha=above_sha, replay_sha=above_sha,
        converter_protocol_sha256=above["converter_protocol_sha256"],
        release_engineering_sha256=above["release_engineering_sha256"],
    )
    try:
        validate_independent_hash_authority(
            above_checks, current_sha=above_independent, historical_sha="0" * 64
        )
    except ProtocolError:
        pass
    else:
        raise ProtocolError("Head30 hash-authority above-tolerance fixture did not fail")
    bad_report = dict(report)
    bad_report["decision"] = "REJECTED_RESEARCH_SCALE"
    bad_checks, _, _, bad_independent = _audit_documents(
        first, replay, bad_report, first_sha=bundle_sha, replay_sha=bundle_sha,
        converter_protocol_sha256=first["converter_protocol_sha256"],
        release_engineering_sha256=first["release_engineering_sha256"],
    )
    try:
        validate_independent_hash_authority(
            bad_checks, current_sha=bad_independent, historical_sha="0" * 64
        )
    except ProtocolError:
        pass
    else:
        raise ProtocolError("Head30 hash-authority decision-drift fixture did not fail")
    return {
        "hash_mismatch_within_tolerance": "PASS",
        "above_tolerance_fail_closed": "PASS",
        "decision_drift_fail_closed": "PASS",
    }


def run(
    *, recovery_protocol_path: Path, recovery_release_path: Path,
    recovery_approval_path: Path, recovery_compose_path: Path,
    r5_protocol_path: Path, r5_release_path: Path, r5_approval_path: Path,
    r5_failure_evidence_path: Path, r4_release_path: Path, r3_protocol_path: Path,
    r3_release_path: Path, r4_failure_evidence_path: Path,
    original_release_path: Path, original_approval_path: Path,
    effect_root: Path, audit_root: Path,
) -> dict[str, Any]:
    protocol = HashAuthorityProtocol.load(recovery_protocol_path)
    release = HashAuthorityScope.load(recovery_release_path, protocol, compose_path=recovery_compose_path)
    approval = HashAuthorityApproval.load(recovery_approval_path, release)
    runtime = _runtime_identity(release)
    lineage, _, original_protocol, original_release, original_approval = full_preflight(
        recovery_protocol_path=recovery_protocol_path, r5_protocol_path=r5_protocol_path,
        r5_release_path=r5_release_path, r5_approval_path=r5_approval_path,
        r5_failure_evidence_path=r5_failure_evidence_path, r4_release_path=r4_release_path,
        r3_protocol_path=r3_protocol_path, r3_release_path=r3_release_path,
        r4_failure_evidence_path=r4_failure_evidence_path,
        original_release_path=original_release_path, original_approval_path=original_approval_path,
    )
    before = _verify_sealed_tree(effect_root=effect_root, audit_root=audit_root, release=release)
    first_path, replay_path = effect_root / "first_pass/bundle.json", effect_root / "replay/bundle.json"
    first, replay, report = mapping(first_path), mapping(replay_path), mapping(effect_root / "report.json")
    checks, rebuilt, primary_sha, independent_sha = _audit_documents(
        first, replay, report, first_sha=sha256_file(first_path), replay_sha=sha256_file(replay_path),
        converter_protocol_sha256=original_protocol.base.sha256,
        release_engineering_sha256=original_protocol.sha256,
    )
    sealed = release.scope["sealed_effect"]
    checks.update({
        "release_and_approval_identity": report.get("release_scope_sha256") == original_release.sha256 and report.get("approval_sha256") == original_approval.sha256,
        "sealed_report_identity": sha256_file(effect_root / "report.json") == sealed["report_sha256"],
        "sealed_primary_result_identity": primary_sha == sealed["primary_result_sha256"],
        "sealed_decision_identity": report.get("decision") == sealed["primary_decision"],
        "attempt_count": report.get("portfolio_attempts_consumed") == 1 and report.get("model_attempt_increment") == 0,
        "pending_audit_state": report.get("strategy_effective") == "PENDING_INDEPENDENT_AUDIT" and report.get("production_authorization") == "none",
        "no_failure_artifact": not (effect_root / "failure.json").exists(),
    })
    authority = validate_independent_hash_authority(
        checks,
        current_sha=independent_sha,
        historical_sha=protocol.document["only_authority_correction"]["historical_independent_result_sha256"],
    )
    audit_root.mkdir(parents=True, exist_ok=True)
    audit = {
        "schema_version": "m6-production-head30-audit-hash-authority-recovery-audit-v1",
        "recovery_scope_sha256": release.sha256, "recovery_approval_sha256": approval.sha256,
        "original_release_scope_sha256": original_release.sha256,
        "original_approval_sha256": original_approval.sha256,
        "report_sha256": sealed["report_sha256"], "bundle_sha256": sealed["first_pass_bundle_sha256"],
        "primary_result_sha256": primary_sha, "independent_hash_authority": authority,
        "checks": checks, "decision": rebuilt["decision"], "independent_audit": "PASS",
        "strategy_effective": rebuilt["decision"], "additional_portfolio_attempt_count": 0,
        "production_authorization": "none",
    }
    audit_sha, reused = write_once_document(audit_root / "audit.json", audit)
    if reused:
        raise ProtocolError("Head30 hash-authority output unexpectedly pre-existed")
    after = _verify_effect_unchanged(effect_root, before)
    receipt = {
        "schema_version": "m6-production-head30-audit-hash-authority-recovery-receipt-v1",
        "recovery_scope_sha256": release.sha256, "recovery_approval_sha256": approval.sha256,
        "audit_sha256": audit_sha, "effect_tree_before": before, "effect_tree_after": after,
        "runtime_identity": runtime, "lineage_preflight": lineage,
        "runner_invocation_count": 0, "recovery_auditor_invocation_count": 1,
        "additional_portfolio_attempt_count": 0, "family_portfolio_attempts_consumed": 2,
        "production_authorization": "none",
    }
    receipt_sha, receipt_reused = write_once_document(audit_root / "recovery-receipt.json", receipt)
    if receipt_reused:
        raise ProtocolError("Head30 hash-authority receipt unexpectedly pre-existed")
    return {
        "audit_sha256": audit_sha, "recovery_receipt_sha256": receipt_sha,
        "decision": rebuilt["decision"], "effect_tree_unchanged": True,
        "additional_portfolio_attempt_count": 0, "production_authorization": "none",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preflight", action="store_true")
    for name in (
        "recovery-protocol", "r5-protocol", "r5-release", "r5-approval",
        "r5-failure-evidence", "r4-release", "r3-protocol", "r3-release",
        "r4-failure-evidence", "original-release", "original-approval",
    ):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--recovery-release", type=Path)
    parser.add_argument("--recovery-approval", type=Path)
    parser.add_argument("--recovery-compose", type=Path)
    parser.add_argument("--preflight-output", type=Path)
    parser.add_argument("--effect-root", type=Path)
    parser.add_argument("--audit-root", type=Path)
    args = parser.parse_args()
    lineage = {
        "recovery_protocol_path": args.recovery_protocol,
        "r5_protocol_path": args.r5_protocol, "r5_release_path": args.r5_release,
        "r5_approval_path": args.r5_approval,
        "r5_failure_evidence_path": args.r5_failure_evidence,
        "r4_release_path": args.r4_release, "r3_protocol_path": args.r3_protocol,
        "r3_release_path": args.r3_release,
        "r4_failure_evidence_path": args.r4_failure_evidence,
        "original_release_path": args.original_release,
        "original_approval_path": args.original_approval,
    }
    if args.preflight:
        if args.preflight_output is None:
            parser.error("preflight output is required")
        evidence, *_ = full_preflight(**lineage)
        document = {
            "schema_version": "m6-production-head30-audit-hash-authority-daemon-fixture-v1",
            "status": "PASS", **evidence, **semantic_fixture(),
            "image_git_commit": os.getenv("SHAIWEI_M6_HEAD30_AUDIT_HASH_AUTHORITY_GIT_HEAD", "").strip(),
            "effect_mounted": False, "effect_semantics_read": False,
            "audit_invoked": False, "production_authorization": "none",
        }
        digest, _ = write_once_document(args.preflight_output, document)
        print(json.dumps({**document, "evidence_sha256": digest}, sort_keys=True))
        return 0
    required = (args.recovery_release, args.recovery_approval, args.recovery_compose, args.effect_root, args.audit_root)
    if any(value is None for value in required):
        parser.error("all real hash-authority recovery inputs are required")
    print(json.dumps(run(
        **lineage, recovery_release_path=args.recovery_release,
        recovery_approval_path=args.recovery_approval,
        recovery_compose_path=args.recovery_compose,
        effect_root=args.effect_root, audit_root=args.audit_root,
    ), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
