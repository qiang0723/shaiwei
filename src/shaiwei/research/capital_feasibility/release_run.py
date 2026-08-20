"""Approved one-shot M6-5B 500k runner with internal replay."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from shaiwei.research.model_attribution.audit_recovery_contract import effect_tree_identity
from shaiwei.research.model_attribution.contract import canonical_sha256, sha256_file
from shaiwei.research.production_conversion.contract import ProtocolError
from shaiwei.research.production_conversion.real_contract import write_once_document

from .release_contract import Approval, ReleaseProtocol, ReleaseScope
from .release_metrics import evaluate
from .sealed_inputs import load as load_sealed, verify_tree
from .simulation import run_all
from .source_reader import load_sources


def _empty(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    if any(root.iterdir()):
        raise ProtocolError("M6-5B effect root is not empty")


def execute_loaded(
    *, release: Any, approval: Any, r2_root: Path, r7_audit: Path,
    raw_manifest: Path, project_root: Path, output_root: Path,
) -> dict[str, Any]:
    """Run the frozen domain flow after a versioned adapter validates authority."""
    runtime = release.verify_runtime_identity()
    verify_tree(r2_root, release)
    expected_r7 = release.scope["inputs"]["r7_audit"]
    if sha256_file(r7_audit) != expected_r7["sha256"]:
        raise ProtocolError("M6-5B R7 audit identity differs")
    raw = release.scope["inputs"]["raw_batch_manifest"]
    if sha256_file(raw_manifest) != raw["sha256"]:
        raise ProtocolError("M6-5B raw manifest identity differs")
    _empty(output_root)
    write_once_document(output_root / "authorization.json", {
        "schema_version": "m6-head30-500k-run-authorization-v1",
        "release_scope_sha256": release.sha256, "approval_sha256": approval.sha256,
        "action": approval.document["action"], "family_attempts_before_run": 1,
        "production_authorization": "none",
    })
    started = False
    try:
        write_once_document(output_root / "effect_started.json", {
            "release_scope_sha256": release.sha256, "new_attempts_consumed": 1,
            "total_family_attempts": 2, "same_scope_retry_authorized": False,
        })
        started = True
        sealed = load_sealed(r2_root, release)
        sources = load_sources(raw_manifest, sealed, project_root=project_root)
        first = run_all(sealed, sources)
        first["result"] = evaluate(first)
        replay = run_all(sealed, sources)
        replay["result"] = evaluate(replay)
        if first != replay:
            raise ProtocolError("M6-5B internal replay differs")
        first_sha, _ = write_once_document(output_root / "first_pass/bundle.json", first)
        replay_sha, _ = write_once_document(output_root / "replay/bundle.json", replay)
        if first_sha != replay_sha:
            raise ProtocolError("M6-5B physical replay differs")
        result = first["result"]
        report = {
            "schema_version": "m6-head30-500k-effect-report-v1",
            "release_scope_sha256": release.sha256, "approval_sha256": approval.sha256,
            "runtime_identity": runtime, "sealed_r2_tree": effect_tree_identity(r2_root),
            "r7_audit_sha256": sha256_file(r7_audit), "raw_manifest_sha256": sha256_file(raw_manifest),
            "first_pass_bundle_sha256": first_sha, "replay_bundle_sha256": replay_sha,
            "first_pass_replay_equal": True, "result_sha256": canonical_sha256(result),
            "decision": result["decision"], "family_attempts_before_run": 1,
            "new_attempts_consumed": 1, "total_family_attempts": 2,
            "strategy_effective": "PENDING_INDEPENDENT_AUDIT", "production_authorization": "none",
        }
        report_sha, reused = write_once_document(output_root / "report.json", report)
        return {"report_sha256": report_sha, "reused": reused, "decision": result["decision"]}
    except Exception as error:
        write_once_document(output_root / "failure.json", {
            "schema_version": "m6-head30-500k-effect-failure-v1",
            "release_scope_sha256": release.sha256, "approval_sha256": approval.sha256,
            "effect_started": started, "new_attempts_consumed": 1 if started else 0,
            "total_family_attempts": 2 if started else 1,
            "same_scope_retry_authorized": False, "error_type": type(error).__name__,
            "error_message": str(error)[:500], "production_authorization": "none",
        })
        raise


def run(
    *, release_path: Path, approval_path: Path, r2_root: Path, r7_audit: Path,
    raw_manifest: Path, project_root: Path, output_root: Path,
) -> dict[str, Any]:
    protocol = ReleaseProtocol.load()
    release = ReleaseScope.load(release_path, protocol)
    approval = Approval.load(approval_path, release)
    return execute_loaded(
        release=release, approval=approval, r2_root=r2_root, r7_audit=r7_audit,
        raw_manifest=raw_manifest, project_root=project_root, output_root=output_root,
    )


def main(argv: list[str] | None = None, *, executor: Any = run) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--approval", type=Path, required=True)
    parser.add_argument("--r2-root", type=Path, required=True)
    parser.add_argument("--r7-audit", type=Path, required=True)
    parser.add_argument("--raw-manifest", type=Path, required=True)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args(argv)
    result = executor(
        release_path=args.release,
        approval_path=args.approval,
        r2_root=args.r2_root,
        r7_audit=args.r7_audit,
        raw_manifest=args.raw_manifest,
        project_root=args.project_root,
        output_root=args.output_root,
    )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
