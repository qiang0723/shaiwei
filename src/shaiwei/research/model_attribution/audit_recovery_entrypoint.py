"""Thin control entrypoint for the one-shot M6 independent-audit recovery."""

from __future__ import annotations

import argparse
import inspect
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Callable

if __package__:
    from .audit_recovery_contract import (
        RecoveryApproval,
        RecoveryProtocol,
        RecoveryReleaseScope,
        effect_tree_identity,
    )
    from .contract import AttributionError, sha256_file
    from .effect_audit import audit as original_audit
    from .effect_contract import write_once_document
else:  # The formal thin image copies this file outside /workspace.
    from audit_recovery_contract import (  # type: ignore[no-redef]
        RecoveryApproval,
        RecoveryProtocol,
        RecoveryReleaseScope,
        effect_tree_identity,
    )
    from shaiwei.research.model_attribution.contract import AttributionError, sha256_file
    from shaiwei.research.model_attribution.effect_audit import audit as original_audit
    from shaiwei.research.model_attribution.effect_contract import write_once_document


AuditRunner = Callable[..., dict[str, Any]]


def _verify_runtime(
    release: RecoveryReleaseScope,
    *,
    contract_path: Path,
    entrypoint_path: Path,
) -> dict[str, str]:
    implementation = release.scope["implementation"]
    observed = {
        "git_commit": os.getenv("SHAIWEI_M6_AUDIT_RECOVERY_GIT_HEAD", "").strip(),
        "contract_sha256": sha256_file(contract_path.resolve()),
        "entrypoint_sha256": sha256_file(entrypoint_path.resolve()),
    }
    if observed != {key: implementation[key] for key in observed}:
        raise AttributionError("M6 audit recovery runtime identity differs")
    return observed


def _verify_sealed_inputs(
    *,
    protocol: RecoveryProtocol,
    release: RecoveryReleaseScope,
    original_release_path: Path,
    original_approval_path: Path,
    effect_root: Path,
    audit_root: Path,
) -> dict[str, Any]:
    original = protocol.document["original_authority"]
    if sha256_file(original_release_path) != original["release_document_sha256"]:
        raise AttributionError("M6 original release document differs during recovery")
    if sha256_file(original_approval_path) != original["approval_sha256"]:
        raise AttributionError("M6 original approval differs during recovery")
    identity = effect_tree_identity(effect_root)
    expected = release.scope["sealed_effect"]
    if identity != {
        "file_count": expected["file_count"],
        "total_bytes": expected["total_bytes"],
        "tree_sha256": expected["tree_sha256"],
    }:
        raise AttributionError("M6 sealed effect tree differs during recovery")
    if sha256_file(effect_root / "report.json") != expected["report_sha256"]:
        raise AttributionError("M6 sealed effect report differs during recovery")
    if (effect_root / "failure.json").exists():
        raise AttributionError("M6 runner failure appeared before recovery")
    if audit_root.exists() and any(audit_root.iterdir()):
        raise AttributionError("M6 recovery audit root is not empty")
    return identity


def _invoke_original_audit(
    audit_runner: AuditRunner,
    *,
    original_release_path: Path,
    original_approval_path: Path,
    effect_root: Path,
    audit_root: Path,
) -> dict[str, Any]:
    return audit_runner(
        release_path=original_release_path,
        approval_path=original_approval_path,
        effect_root=effect_root,
        audit_root=audit_root,
    )


def run(
    *,
    recovery_protocol_path: Path,
    recovery_release_path: Path,
    recovery_approval_path: Path,
    recovery_compose_path: Path,
    original_release_path: Path,
    original_approval_path: Path,
    effect_root: Path,
    audit_root: Path,
    audit_runner: AuditRunner = original_audit,
) -> dict[str, Any]:
    protocol = RecoveryProtocol.load(recovery_protocol_path)
    release = RecoveryReleaseScope.load(
        recovery_release_path,
        protocol,
        compose_path=recovery_compose_path,
    )
    approval = RecoveryApproval.load(recovery_approval_path, release)
    runtime = _verify_runtime(
        release,
        contract_path=Path(__file__).with_name("audit_recovery_contract.py"),
        entrypoint_path=Path(__file__),
    )
    before = _verify_sealed_inputs(
        protocol=protocol,
        release=release,
        original_release_path=original_release_path,
        original_approval_path=original_approval_path,
        effect_root=effect_root,
        audit_root=audit_root,
    )
    result = _invoke_original_audit(
        audit_runner,
        original_release_path=original_release_path,
        original_approval_path=original_approval_path,
        effect_root=effect_root,
        audit_root=audit_root,
    )
    if result.get("independent_audit") != "PASS":
        raise AttributionError("M6 recovered independent audit did not pass")
    after = effect_tree_identity(effect_root)
    if after != before:
        raise AttributionError("M6 sealed effect tree changed during recovered audit")
    receipt = {
        "schema_version": "m6-model-attribution-audit-recovery-receipt-v1",
        "recovery_scope_sha256": release.sha256,
        "recovery_approval_sha256": approval.sha256,
        "original_release_scope_sha256": protocol.document["original_authority"][
            "release_scope_sha256"
        ],
        "original_approval_sha256": protocol.document["original_authority"]["approval_sha256"],
        "original_report_sha256": sha256_file(effect_root / "report.json"),
        "effect_tree_before": before,
        "effect_tree_after": after,
        "recovery_runtime_identity": runtime,
        "audit_sha256": result["audit_sha256"],
        "independent_audit": "PASS",
        "additional_alternative_attempt_count": 0,
        "runner_invocation_count": 0,
        "production_authorization": "none",
    }
    receipt_sha, reused = write_once_document(audit_root / "recovery-receipt.json", receipt)
    if reused:
        raise AttributionError("M6 audit recovery receipt unexpectedly pre-existed")
    return {
        **result,
        "recovery_receipt_sha256": receipt_sha,
        "effect_tree_unchanged": True,
        "additional_alternative_attempt_count": 0,
        "production_authorization": "none",
    }


def self_test() -> dict[str, Any]:
    expected = {"release_path", "approval_path", "effect_root", "audit_root"}
    if set(inspect.signature(original_audit).parameters) != expected:
        raise AttributionError("M6 original audit signature differs")
    with tempfile.TemporaryDirectory(prefix="m6-audit-recovery-") as directory:
        root = Path(directory) / "effect"
        root.mkdir()
        (root / "one.bin").write_bytes(b"one")
        nested = root / "nested"
        nested.mkdir()
        (nested / "two.bin").write_bytes(b"two")
        before = effect_tree_identity(root)
        (nested / "two.bin").write_bytes(b"tampered")
        after = effect_tree_identity(root)
        if before == after:
            raise AttributionError("M6 recovery tree tamper self-test failed")
    return {
        "original_audit_signature": "PASS",
        "tree_tamper_detection": "PASS",
        "real_effect_read": False,
        "audit_invoked": False,
        "production_authorization": "none",
    }


def validate_release_only(
    *,
    recovery_protocol_path: Path,
    recovery_release_path: Path,
    recovery_compose_path: Path,
) -> dict[str, Any]:
    protocol = RecoveryProtocol.load(recovery_protocol_path)
    release = RecoveryReleaseScope.load(
        recovery_release_path,
        protocol,
        compose_path=recovery_compose_path,
    )
    runtime = _verify_runtime(
        release,
        contract_path=Path(__file__).with_name("audit_recovery_contract.py"),
        entrypoint_path=Path(__file__),
    )
    return {
        "recovery_scope_sha256": release.sha256,
        "runtime_identity": runtime,
        "sealed_effect_read": False,
        "audit_invoked": False,
        "production_authorization": "none",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--validate-release-only", action="store_true")
    parser.add_argument("--recovery-protocol", type=Path)
    parser.add_argument("--recovery-release", type=Path)
    parser.add_argument("--recovery-approval", type=Path)
    parser.add_argument("--recovery-compose", type=Path)
    parser.add_argument("--original-release", type=Path)
    parser.add_argument("--original-approval", type=Path)
    parser.add_argument("--effect-root", type=Path)
    parser.add_argument("--audit-root", type=Path)
    args = parser.parse_args()
    if args.self_test:
        print(json.dumps(self_test(), sort_keys=True))
        return 0
    if args.validate_release_only:
        required = (args.recovery_protocol, args.recovery_release, args.recovery_compose)
        if any(value is None for value in required):
            parser.error("release-only validation requires protocol, release, and compose")
        print(
            json.dumps(
                validate_release_only(
                    recovery_protocol_path=args.recovery_protocol,
                    recovery_release_path=args.recovery_release,
                    recovery_compose_path=args.recovery_compose,
                ),
                sort_keys=True,
            )
        )
        return 0
    required = (
        args.recovery_protocol,
        args.recovery_release,
        args.recovery_approval,
        args.recovery_compose,
        args.original_release,
        args.original_approval,
        args.effect_root,
        args.audit_root,
    )
    if any(value is None for value in required):
        parser.error("formal recovery requires every path argument")
    print(
        json.dumps(
            run(
                recovery_protocol_path=args.recovery_protocol,
                recovery_release_path=args.recovery_release,
                recovery_approval_path=args.recovery_approval,
                recovery_compose_path=args.recovery_compose,
                original_release_path=args.original_release,
                original_approval_path=args.original_approval,
                effect_root=args.effect_root,
                audit_root=args.audit_root,
            ),
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
