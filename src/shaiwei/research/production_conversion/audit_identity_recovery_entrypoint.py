"""One-shot, artifact-only Head30 audit identity recovery."""

from __future__ import annotations

import argparse
import copy
import json
import math
import os
from pathlib import Path
import tempfile
from typing import Any

if __package__:
    from .audit_identity_recovery_contract import (
        RecoveryApproval,
        RecoveryProtocol,
        RecoveryReleaseScope,
        effect_tree_identity,
        mapping,
    )
else:
    from audit_identity_recovery_contract import (  # type: ignore[no-redef]
        RecoveryApproval,
        RecoveryProtocol,
        RecoveryReleaseScope,
        effect_tree_identity,
        mapping,
    )

from shaiwei.research.model_attribution.contract import canonical_sha256, sha256_file
from shaiwei.research.production_conversion.audit_statistics import independently_evaluate
from shaiwei.research.production_conversion.contract import ProtocolError
from shaiwei.research.production_conversion.real_contract import (
    Approval,
    ReleaseProtocol,
    ReleaseScope,
    write_once_document,
)


EXPECTED_EFFECT_FILES = {
    "authorization.json",
    "treatment_effect_started.json",
    "first_pass/bundle.json",
    "replay/bundle.json",
    "report.json",
}


def _equivalent(left: Any, right: Any) -> bool:
    if isinstance(left, bool) or isinstance(right, bool):
        return left is right
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return math.isclose(float(left), float(right), rel_tol=1e-12, abs_tol=1e-12)
    if isinstance(left, dict) and isinstance(right, dict):
        return set(left) == set(right) and all(_equivalent(left[key], right[key]) for key in left)
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(
            _equivalent(a, b) for a, b in zip(left, right, strict=True)
        )
    return left == right


def _audit_documents(
    first: dict[str, Any],
    replay: dict[str, Any],
    report: dict[str, Any],
    *,
    first_sha: str,
    replay_sha: str,
    converter_protocol_sha256: str,
    release_engineering_sha256: str,
) -> tuple[dict[str, bool], dict[str, Any], str, str]:
    rebuilt_first = independently_evaluate(first)
    rebuilt_replay = independently_evaluate(replay)
    primary = first.get("result")
    primary_sha = canonical_sha256(primary)
    independent_sha = canonical_sha256(rebuilt_first)
    decisions = (
        report.get("decision"),
        primary.get("decision") if isinstance(primary, dict) else None,
        rebuilt_first.get("decision"),
    )
    checks = {
        "bundle_schema": first.get("schema_version") == replay.get("schema_version") == "m6-production-head30-pass-bundle-v1",
        "protocol_identity": first.get("converter_protocol_sha256") == replay.get("converter_protocol_sha256") == converter_protocol_sha256 and first.get("release_engineering_sha256") == replay.get("release_engineering_sha256") == release_engineering_sha256,
        "first_pass_replay_physical_identity": first_sha == replay_sha,
        "first_pass_replay_semantic_identity": first == replay,
        "reported_bundle_identity": report.get("first_pass_bundle_sha256") == first_sha and report.get("replay_bundle_sha256") == replay_sha,
        "primary_result_identity": report.get("result_sha256") == primary_sha,
        "independent_first_reconstruction": _equivalent(rebuilt_first, primary),
        "independent_replay_reconstruction": _equivalent(rebuilt_replay, rebuilt_first),
        "exact_decision_identity": decisions[0] == decisions[1] == decisions[2],
        "non_production_result": primary.get("production_authorization") == rebuilt_first.get("production_authorization") == "none" if isinstance(primary, dict) else False,
    }
    return checks, rebuilt_first, primary_sha, independent_sha


def _verify_runtime(release: RecoveryReleaseScope) -> dict[str, str]:
    expected = release.scope["implementation"]
    observed = {
        "git_commit": os.getenv("SHAIWEI_M6_HEAD30_AUDIT_RECOVERY_GIT_HEAD", "").strip(),
        "contract_sha256": sha256_file(Path(__file__).with_name("audit_identity_recovery_contract.py")),
        "entrypoint_sha256": sha256_file(Path(__file__)),
    }
    if observed != {key: expected[key] for key in observed}:
        raise ProtocolError("Head30 audit-recovery runtime identity differs")
    return observed


def _verify_original_authority(
    *,
    protocol: RecoveryProtocol,
    original_protocol_path: Path,
    original_release_path: Path,
    original_approval_path: Path,
    failure_evidence_path: Path,
) -> tuple[ReleaseProtocol, ReleaseScope, Approval]:
    original = protocol.document["original_authority"]
    original_protocol = ReleaseProtocol.load(original_protocol_path)
    release = ReleaseScope.load(original_release_path, original_protocol)
    approval = Approval.load(original_approval_path, release)
    if (
        release.sha256 != original["release_scope_sha256"]
        or sha256_file(original_release_path) != original["release_document_sha256"]
        or approval.sha256 != original["approval_sha256"]
    ):
        raise ProtocolError("Head30 original R2 authority differs during recovery")
    failed = protocol.document["failed_r2_auditor"]
    if sha256_file(failure_evidence_path) != failed["tracked_failure_evidence_sha256"]:
        raise ProtocolError("Head30 audit failure evidence differs during recovery")
    evidence = mapping(failure_evidence_path)
    if evidence.get("audit_failure_check") != "reported_result_identity":
        raise ProtocolError("Head30 audit failure classification differs")
    return original_protocol, release, approval


def _verify_sealed_tree(
    *, effect_root: Path, audit_root: Path, release: RecoveryReleaseScope
) -> dict[str, Any]:
    actual_files = {
        path.relative_to(effect_root).as_posix()
        for path in effect_root.rglob("*")
        if path.is_file()
    }
    if actual_files != EXPECTED_EFFECT_FILES:
        raise ProtocolError("Head30 recovered effect file set differs")
    observed = effect_tree_identity(effect_root)
    sealed = release.scope["sealed_effect"]
    if observed != {key: sealed[key] for key in ("file_count", "total_bytes", "tree_sha256")}:
        raise ProtocolError("Head30 recovered effect tree identity differs")
    if audit_root.exists() and any(audit_root.iterdir()):
        raise ProtocolError("Head30 recovery audit root is not empty")
    return observed


def run(
    *,
    recovery_protocol_path: Path,
    recovery_release_path: Path,
    recovery_approval_path: Path,
    recovery_compose_path: Path,
    original_protocol_path: Path,
    original_release_path: Path,
    original_approval_path: Path,
    failure_evidence_path: Path,
    effect_root: Path,
    audit_root: Path,
) -> dict[str, Any]:
    protocol = RecoveryProtocol.load(recovery_protocol_path)
    release = RecoveryReleaseScope.load(
        recovery_release_path, protocol, compose_path=recovery_compose_path
    )
    approval = RecoveryApproval.load(recovery_approval_path, release)
    runtime = _verify_runtime(release)
    original_protocol, original_release, original_approval = _verify_original_authority(
        protocol=protocol,
        original_protocol_path=original_protocol_path,
        original_release_path=original_release_path,
        original_approval_path=original_approval_path,
        failure_evidence_path=failure_evidence_path,
    )
    before = _verify_sealed_tree(effect_root=effect_root, audit_root=audit_root, release=release)
    first_path = effect_root / "first_pass/bundle.json"
    replay_path = effect_root / "replay/bundle.json"
    first, replay, report = mapping(first_path), mapping(replay_path), mapping(effect_root / "report.json")
    checks, rebuilt, primary_sha, independent_sha = _audit_documents(
        first,
        replay,
        report,
        first_sha=sha256_file(first_path),
        replay_sha=sha256_file(replay_path),
        converter_protocol_sha256=original_protocol.base.sha256,
        release_engineering_sha256=original_protocol.sha256,
    )
    sealed = release.scope["sealed_effect"]
    checks.update(
        {
            "release_and_approval_identity": report.get("release_scope_sha256") == original_release.sha256 and report.get("approval_sha256") == original_approval.sha256,
            "sealed_report_identity": sha256_file(effect_root / "report.json") == sealed["report_sha256"],
            "sealed_primary_result_identity": primary_sha == sealed["primary_result_sha256"],
            "sealed_decision_identity": report.get("decision") == sealed["primary_decision"],
            "independent_result_lineage": independent_sha == protocol.document["root_cause"]["independent_result_sha256"],
            "attempt_count": report.get("portfolio_attempts_consumed") == 1 and report.get("model_attempt_increment") == 0,
            "pending_audit_state": report.get("strategy_effective") == "PENDING_INDEPENDENT_AUDIT" and report.get("production_authorization") == "none",
            "no_failure_artifact": not (effect_root / "failure.json").exists(),
        }
    )
    if not all(checks.values()):
        raise ProtocolError(
            f"Head30 audit identity recovery failed: {[name for name, passed in checks.items() if not passed]}"
        )
    audit_root.mkdir(parents=True, exist_ok=True)
    audit_document = {
        "schema_version": "m6-production-head30-audit-identity-recovery-audit-v1",
        "recovery_scope_sha256": release.sha256,
        "recovery_approval_sha256": approval.sha256,
        "original_release_scope_sha256": original_release.sha256,
        "original_approval_sha256": original_approval.sha256,
        "report_sha256": sealed["report_sha256"],
        "bundle_sha256": sealed["first_pass_bundle_sha256"],
        "primary_result_sha256": primary_sha,
        "independent_result_sha256": independent_sha,
        "independent_hash_equality_with_primary_required": False,
        "checks": checks,
        "decision": rebuilt["decision"],
        "independent_audit": "PASS",
        "strategy_effective": rebuilt["decision"],
        "additional_portfolio_attempt_count": 0,
        "production_authorization": "none",
    }
    audit_sha, reused = write_once_document(audit_root / "audit.json", audit_document)
    if reused:
        raise ProtocolError("Head30 recovered audit unexpectedly pre-existed")
    after = effect_tree_identity(effect_root)
    if after != before:
        raise ProtocolError("Head30 sealed effect changed during recovered audit")
    receipt = {
        "schema_version": "m6-production-head30-audit-identity-recovery-receipt-v1",
        "recovery_scope_sha256": release.sha256,
        "recovery_approval_sha256": approval.sha256,
        "audit_sha256": audit_sha,
        "effect_tree_before": before,
        "effect_tree_after": after,
        "runtime_identity": runtime,
        "runner_invocation_count": 0,
        "recovery_auditor_invocation_count": 1,
        "additional_portfolio_attempt_count": 0,
        "family_portfolio_attempts_consumed": 2,
        "production_authorization": "none",
    }
    receipt_sha, receipt_reused = write_once_document(
        audit_root / "recovery-receipt.json", receipt
    )
    if receipt_reused:
        raise ProtocolError("Head30 recovery receipt unexpectedly pre-existed")
    return {
        "audit_sha256": audit_sha,
        "recovery_receipt_sha256": receipt_sha,
        "decision": rebuilt["decision"],
        "effect_tree_unchanged": True,
        "additional_portfolio_attempt_count": 0,
        "production_authorization": "none",
    }


def _synthetic_bundle() -> dict[str, Any]:
    treatments = {}
    controls = {}
    for window in ("W1", "W2", "W3", "W4", "W5", "W6"):
        treatments[window] = {
            "daily": [{"gross_return": 0.01, "recorded_cost": 0.0, "benchmark_return": 0.0, "turnover": 0.0}],
            "rebalances": [],
            "positions": [{"position_count": 30, "cash_ratio": 0.0}],
        }
        controls[window] = [0.0]
    bundle = {
        "schema_version": "m6-production-head30-pass-bundle-v1",
        "converter_protocol_sha256": "a" * 64,
        "release_engineering_sha256": "b" * 64,
        "treatments": treatments,
        "control_base_daily_active_return": controls,
    }
    bundle["result"] = independently_evaluate(bundle)
    return bundle


def self_test() -> dict[str, Any]:
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
    checks, _, primary_sha, independent_sha = _audit_documents(
        first,
        replay,
        report,
        first_sha=bundle_sha,
        replay_sha=bundle_sha,
        converter_protocol_sha256="a" * 64,
        release_engineering_sha256="b" * 64,
    )
    if not all(checks.values()) or primary_sha == independent_sha:
        raise ProtocolError("Head30 audit-recovery floating-tail self-test failed")
    bad = copy.deepcopy(report)
    bad["decision"] = "REJECTED_RESEARCH_SCALE"
    bad_checks, *_ = _audit_documents(
        first,
        replay,
        bad,
        first_sha=bundle_sha,
        replay_sha=bundle_sha,
        converter_protocol_sha256="a" * 64,
        release_engineering_sha256="b" * 64,
    )
    if bad_checks["exact_decision_identity"]:
        raise ProtocolError("Head30 audit-recovery decision-drift self-test failed")
    with tempfile.TemporaryDirectory(prefix="m6-head30-audit-recovery-") as directory:
        root = Path(directory)
        (root / "one").write_text("one")
        before = effect_tree_identity(root)
        (root / "one").write_text("two")
        if effect_tree_identity(root) == before:
            raise ProtocolError("Head30 audit-recovery tree-tamper self-test failed")
    return {
        "floating_tail_semantic_equivalence": "PASS",
        "primary_and_independent_hashes_distinct": "PASS",
        "decision_drift_fail_closed": "PASS",
        "tree_tamper_detection": "PASS",
        "real_effect_read": False,
        "audit_invoked": False,
        "production_authorization": "none",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--recovery-protocol", type=Path)
    parser.add_argument("--recovery-release", type=Path)
    parser.add_argument("--recovery-approval", type=Path)
    parser.add_argument("--recovery-compose", type=Path)
    parser.add_argument("--original-protocol", type=Path)
    parser.add_argument("--original-release", type=Path)
    parser.add_argument("--original-approval", type=Path)
    parser.add_argument("--failure-evidence", type=Path)
    parser.add_argument("--effect-root", type=Path)
    parser.add_argument("--audit-root", type=Path)
    args = parser.parse_args()
    if args.self_test:
        print(json.dumps(self_test(), sort_keys=True))
        return 0
    required = {key: value for key, value in vars(args).items() if key != "self_test"}
    if any(value is None for value in required.values()):
        parser.error("all recovery inputs are required")
    print(
        json.dumps(
            run(
                recovery_protocol_path=args.recovery_protocol,
                recovery_release_path=args.recovery_release,
                recovery_approval_path=args.recovery_approval,
                recovery_compose_path=args.recovery_compose,
                original_protocol_path=args.original_protocol,
                original_release_path=args.original_release,
                original_approval_path=args.original_approval,
                failure_evidence_path=args.failure_evidence,
                effect_root=args.effect_root,
                audit_root=args.audit_root,
            ),
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
