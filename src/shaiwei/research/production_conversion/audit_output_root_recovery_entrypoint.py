"""One-shot Head30 audit recovery with a preverified writable output root."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any

if __package__:
    from .audit_output_root_recovery_contract import (
        OutputRootApproval,
        OutputRootProtocol,
        OutputRootScope,
        SENTINEL_PAYLOAD,
        SENTINEL_SHA256,
        mapping,
    )
    from .audit_hash_authority_contract import (
        HashAuthorityApproval,
        HashAuthorityProtocol,
        HashAuthorityScope,
    )
    from .audit_hash_authority_entrypoint import (
        full_preflight as r6_full_preflight,
        semantic_fixture,
        validate_independent_hash_authority,
    )
    from .audit_identity_recovery_entrypoint import _audit_documents
    from .audit_entrypoint_recovery_entrypoint import (
        _verify_effect_unchanged,
        _verify_sealed_tree,
    )
else:
    from audit_output_root_recovery_contract import (  # type: ignore[no-redef]
        OutputRootApproval,
        OutputRootProtocol,
        OutputRootScope,
        SENTINEL_PAYLOAD,
        SENTINEL_SHA256,
        mapping,
    )
    from audit_hash_authority_contract import (  # type: ignore[no-redef]
        HashAuthorityApproval,
        HashAuthorityProtocol,
        HashAuthorityScope,
    )
    from audit_hash_authority_entrypoint import (  # type: ignore[no-redef]
        full_preflight as r6_full_preflight,
        semantic_fixture,
        validate_independent_hash_authority,
    )
    from audit_identity_recovery_entrypoint import _audit_documents  # type: ignore[no-redef]
    from audit_entrypoint_recovery_entrypoint import (  # type: ignore[no-redef]
        _verify_effect_unchanged,
        _verify_sealed_tree,
    )

from shaiwei.research.model_attribution.contract import sha256_file
from shaiwei.research.production_conversion.contract import ProtocolError
from shaiwei.research.production_conversion.real_contract import write_once_document


def verify_output_root_roundtrip(root: Path) -> dict[str, Any]:
    if not root.is_dir():
        raise ProtocolError("Head30 output-root fixture directory is absent")
    if any(root.iterdir()):
        raise ProtocolError("Head30 output-root fixture directory is not empty before roundtrip")
    sentinel = root / ".r7-output-root-sentinel"
    descriptor = os.open(sentinel, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(SENTINEL_PAYLOAD)
            handle.flush()
            os.fsync(handle.fileno())
        observed = sentinel.read_bytes()
        digest = hashlib.sha256(observed).hexdigest()
        if observed != SENTINEL_PAYLOAD or digest != SENTINEL_SHA256:
            raise ProtocolError("Head30 output-root sentinel identity differs")
    finally:
        sentinel.unlink(missing_ok=True)
    if any(root.iterdir()):
        raise ProtocolError("Head30 output-root fixture directory is not empty after roundtrip")
    return {
        "output_root_roundtrip": "PASS", "output_root_empty_before": True,
        "output_root_empty_after": True, "sentinel_payload_sha256": SENTINEL_SHA256,
    }


def _runtime_identity(release: OutputRootScope) -> dict[str, str]:
    root = Path(__file__).parent
    observed = {
        "git_commit": os.getenv("SHAIWEI_M6_HEAD30_AUDIT_OUTPUT_ROOT_GIT_HEAD", "").strip(),
        "contract_sha256": sha256_file(root / "audit_output_root_recovery_contract.py"),
        "entrypoint_sha256": sha256_file(Path(__file__)),
        "r6_contract_sha256": sha256_file(root / "audit_hash_authority_contract.py"),
        "r6_entrypoint_sha256": sha256_file(root / "audit_hash_authority_entrypoint.py"),
    }
    expected = release.scope["implementation"]
    if observed != {key: expected[key] for key in observed}:
        raise ProtocolError("Head30 output-root runtime identity differs")
    return observed


def full_preflight(
    *, recovery_protocol_path: Path, r6_protocol_path: Path,
    r6_release_path: Path, r6_approval_path: Path, r6_compose_path: Path,
    r6_failure_evidence_path: Path, r5_protocol_path: Path, r5_release_path: Path,
    r5_approval_path: Path, r5_failure_evidence_path: Path, r4_release_path: Path,
    r3_protocol_path: Path, r3_release_path: Path, r4_failure_evidence_path: Path,
    original_release_path: Path, original_approval_path: Path,
) -> tuple[dict[str, Any], Any, Any, Any, Any]:
    protocol = OutputRootProtocol.load(recovery_protocol_path)
    r6 = protocol.document["r6_authority"]
    r6_protocol = HashAuthorityProtocol.load(r6_protocol_path)
    r6_release = HashAuthorityScope.load(r6_release_path, r6_protocol, compose_path=r6_compose_path)
    r6_approval = HashAuthorityApproval.load(r6_approval_path, r6_release)
    if (
        r6_protocol.sha256 != r6["protocol_sha256"]
        or r6_release.sha256 != r6["release_scope_sha256"]
        or sha256_file(r6_release_path) != r6["release_document_sha256"]
        or r6_approval.sha256 != r6["approval_sha256"]
    ):
        raise ProtocolError("Head30 R6 authority differs during R7 preflight")
    failure = protocol.document["r6_execution_failure"]
    if sha256_file(r6_failure_evidence_path) != failure["evidence_sha256"]:
        raise ProtocolError("Head30 R6 failure evidence identity differs")
    observed_failure = mapping(r6_failure_evidence_path)
    expected_failure = {
        "r6_scope_sha256": r6["release_scope_sha256"], "container_created": False,
        "r6_auditor_invocation_count": 0, "audit_function_entered": False,
        "effect_semantics_read": False, "independent_reconstruction_completed": False,
        "audit_output_file_count": 0, "audit_root_exists_after_failure": False,
        "runner_invocation_count": 0, "additional_portfolio_attempt_count": 0,
        "same_scope_retry_authorized": False,
    }
    if any(observed_failure.get(key) != value for key, value in expected_failure.items()):
        raise ProtocolError("Head30 R6 failure state differs during R7 preflight")
    lineage, _, original_protocol, original_release, original_approval = r6_full_preflight(
        recovery_protocol_path=r6_protocol_path, r5_protocol_path=r5_protocol_path,
        r5_release_path=r5_release_path, r5_approval_path=r5_approval_path,
        r5_failure_evidence_path=r5_failure_evidence_path, r4_release_path=r4_release_path,
        r3_protocol_path=r3_protocol_path, r3_release_path=r3_release_path,
        r4_failure_evidence_path=r4_failure_evidence_path,
        original_release_path=original_release_path, original_approval_path=original_approval_path,
    )
    evidence = {
        "r7_protocol_sha256": protocol.sha256, "r6_protocol_sha256": r6_protocol.sha256,
        "r6_release_document_sha256": sha256_file(r6_release_path),
        "r6_release_scope_sha256": r6_release.sha256,
        "r6_approval_sha256": r6_approval.sha256,
        "r6_failure_evidence_sha256": sha256_file(r6_failure_evidence_path),
        "r6_r5_r4_r3_r2_lineage_preflight_status": lineage["r5_r4_r3_r2_lineage_preflight_status"],
    }
    return evidence, r6_protocol, original_protocol, original_release, original_approval


def run(
    *, recovery_protocol_path: Path, recovery_release_path: Path,
    recovery_approval_path: Path, recovery_compose_path: Path,
    r6_protocol_path: Path, r6_release_path: Path, r6_approval_path: Path,
    r6_compose_path: Path, r6_failure_evidence_path: Path, r5_protocol_path: Path,
    r5_release_path: Path, r5_approval_path: Path, r5_failure_evidence_path: Path,
    r4_release_path: Path, r3_protocol_path: Path, r3_release_path: Path,
    r4_failure_evidence_path: Path, original_release_path: Path,
    original_approval_path: Path, effect_root: Path, audit_root: Path,
) -> dict[str, Any]:
    protocol = OutputRootProtocol.load(recovery_protocol_path)
    release = OutputRootScope.load(recovery_release_path, protocol, compose_path=recovery_compose_path)
    approval = OutputRootApproval.load(recovery_approval_path, release)
    runtime = _runtime_identity(release)
    lineage, r6_protocol, original_protocol, original_release, original_approval = full_preflight(
        recovery_protocol_path=recovery_protocol_path, r6_protocol_path=r6_protocol_path,
        r6_release_path=r6_release_path, r6_approval_path=r6_approval_path,
        r6_compose_path=r6_compose_path, r6_failure_evidence_path=r6_failure_evidence_path,
        r5_protocol_path=r5_protocol_path, r5_release_path=r5_release_path,
        r5_approval_path=r5_approval_path, r5_failure_evidence_path=r5_failure_evidence_path,
        r4_release_path=r4_release_path, r3_protocol_path=r3_protocol_path,
        r3_release_path=r3_release_path, r4_failure_evidence_path=r4_failure_evidence_path,
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
        checks, current_sha=independent_sha,
        historical_sha=r6_protocol.document["only_authority_correction"]["historical_independent_result_sha256"],
    )
    audit = {
        "schema_version": "m6-production-head30-audit-output-root-recovery-audit-v1",
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
        raise ProtocolError("Head30 output-root audit unexpectedly pre-existed")
    after = _verify_effect_unchanged(effect_root, before)
    receipt = {
        "schema_version": "m6-production-head30-audit-output-root-recovery-receipt-v1",
        "recovery_scope_sha256": release.sha256, "recovery_approval_sha256": approval.sha256,
        "audit_sha256": audit_sha, "effect_tree_before": before, "effect_tree_after": after,
        "runtime_identity": runtime, "lineage_preflight": lineage,
        "runner_invocation_count": 0, "recovery_auditor_invocation_count": 1,
        "additional_portfolio_attempt_count": 0, "family_portfolio_attempts_consumed": 2,
        "production_authorization": "none",
    }
    receipt_sha, receipt_reused = write_once_document(audit_root / "recovery-receipt.json", receipt)
    if receipt_reused:
        raise ProtocolError("Head30 output-root receipt unexpectedly pre-existed")
    return {
        "audit_sha256": audit_sha, "recovery_receipt_sha256": receipt_sha,
        "decision": rebuilt["decision"], "effect_tree_unchanged": True,
        "additional_portfolio_attempt_count": 0, "production_authorization": "none",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preflight", action="store_true")
    for name in (
        "recovery-protocol", "r6-protocol", "r6-release", "r6-approval", "r6-compose",
        "r6-failure-evidence", "r5-protocol", "r5-release", "r5-approval",
        "r5-failure-evidence", "r4-release", "r3-protocol", "r3-release",
        "r4-failure-evidence", "original-release", "original-approval",
    ):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--recovery-release", type=Path)
    parser.add_argument("--recovery-approval", type=Path)
    parser.add_argument("--recovery-compose", type=Path)
    parser.add_argument("--preflight-output", type=Path)
    parser.add_argument("--fixture-output-root", type=Path)
    parser.add_argument("--effect-root", type=Path)
    parser.add_argument("--audit-root", type=Path)
    args = parser.parse_args()
    lineage = {
        "recovery_protocol_path": args.recovery_protocol, "r6_protocol_path": args.r6_protocol,
        "r6_release_path": args.r6_release, "r6_approval_path": args.r6_approval,
        "r6_compose_path": args.r6_compose, "r6_failure_evidence_path": args.r6_failure_evidence,
        "r5_protocol_path": args.r5_protocol, "r5_release_path": args.r5_release,
        "r5_approval_path": args.r5_approval, "r5_failure_evidence_path": args.r5_failure_evidence,
        "r4_release_path": args.r4_release, "r3_protocol_path": args.r3_protocol,
        "r3_release_path": args.r3_release, "r4_failure_evidence_path": args.r4_failure_evidence,
        "original_release_path": args.original_release, "original_approval_path": args.original_approval,
    }
    if args.preflight:
        if args.preflight_output is None or args.fixture_output_root is None:
            parser.error("preflight evidence and fixture output root are required")
        evidence, *_ = full_preflight(**lineage)
        document = {
            "schema_version": "m6-production-head30-audit-output-root-daemon-fixture-v1",
            "status": "PASS", **evidence, **semantic_fixture(),
            **verify_output_root_roundtrip(args.fixture_output_root),
            "image_git_commit": os.getenv("SHAIWEI_M6_HEAD30_AUDIT_OUTPUT_ROOT_GIT_HEAD", "").strip(),
            "effect_mounted": False, "effect_semantics_read": False,
            "audit_invoked": False, "production_authorization": "none",
        }
        digest, _ = write_once_document(args.preflight_output, document)
        print(json.dumps({**document, "evidence_sha256": digest}, sort_keys=True))
        return 0
    required = (args.recovery_release, args.recovery_approval, args.recovery_compose, args.effect_root, args.audit_root)
    if any(value is None for value in required):
        parser.error("all real output-root recovery inputs are required")
    print(json.dumps(run(
        **lineage, recovery_release_path=args.recovery_release,
        recovery_approval_path=args.recovery_approval, recovery_compose_path=args.recovery_compose,
        effect_root=args.effect_root, audit_root=args.audit_root,
    ), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
