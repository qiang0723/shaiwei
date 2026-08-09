"""Offline evaluator for the sealed M7 network-recovery batches."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from shaiwei.research_gates.m7_moneyflow.contract import canonical_json

from shaiwei.research_gates.m7_moneyflow_recovery.contract import RecoveryError
from shaiwei.research_gates.m7_moneyflow_recovery.evaluator import evaluate_recovery

from .network_runtime import (
    assemble_runtime_inputs,
    load_runtime_authority,
    role_activation_id,
)
from .sealing import claim_role_once, write_canonical_once


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--plan-root", type=Path, required=True)
    parser.add_argument("--release-scope", type=Path, required=True)
    parser.add_argument("--approval-envelope", type=Path, required=True)
    parser.add_argument("--target-root", type=Path, required=True)
    parser.add_argument("--status-root", type=Path, required=True)
    parser.add_argument("--moneyflow-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--claim-root", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        authority = load_runtime_authority(
            args.project_root.resolve(strict=True),
            plan_root=args.plan_root.resolve(strict=True),
            release_scope=args.release_scope.resolve(strict=True),
            approval_envelope=args.approval_envelope.resolve(strict=True),
        )
        claim_role_once(
            args.claim_root,
            role="evaluator",
            release_scope_sha256=authority.release.sha256,
            run_id=role_activation_id(authority, "evaluator"),
        )
        sealed = assemble_runtime_inputs(
            authority,
            target_root=args.target_root.resolve(strict=True),
            status_root=args.status_root.resolve(strict=True),
            moneyflow_root=args.moneyflow_root.resolve(strict=True),
        )
        report = evaluate_recovery(
            authority.recovery,
            sealed.inputs,
            release_scope_sha256=authority.release.sha256,
            target_plan_manifest_sha256=authority.plan_manifest_sha256,
            batch_manifest_sha256=sealed.batch_manifest_sha256,
        )
        report["execution_kind"] = "OFFLINE_EVALUATOR_AFTER_SEALED_NETWORK_COLLECTION"
        report["provider_call_count"] = sealed.receipt_count
        report["network_collection"] = {
            "sealed_receipt_count": sealed.receipt_count,
            "batch_manifest_sha256": sealed.batch_manifest_sha256,
            "collection_manifest_sha256": {
                name: value["manifest_sha256"]
                for name, value in sealed.collection_manifests.items()
            },
        }
        run_root = args.output_root / str(report["run_id"])
        report_sha = write_canonical_once(run_root / "report.json", report)
        manifest = {
            "schema_version": "m7-moneyflow-recovery-network-evaluation-manifest-v1",
            "run_id": report["run_id"],
            "release_scope_sha256": authority.release.sha256,
            "approval_sha256": authority.approval.sha256,
            "request_plan_manifest_sha256": authority.plan_manifest_sha256,
            "batch_manifest_sha256": sealed.batch_manifest_sha256,
            "sealed_receipt_count": sealed.receipt_count,
            "report_sha256": report_sha,
            "verdict": report["verdict"],
            "production_authorization": "none",
        }
        manifest_sha = write_canonical_once(run_root / "evaluation_manifest.json", manifest)
    except (OSError, RecoveryError, TypeError, ValueError, json.JSONDecodeError) as error:
        print(canonical_json({"status": "FAIL", "error_class": type(error).__name__}))
        return 2
    print(
        canonical_json(
            {
                "status": "PASS",
                "role": "evaluator",
                "run_id": report["run_id"],
                "manifest_sha256": manifest_sha,
                "verdict": report["verdict"],
                "production_authorization": "none",
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
