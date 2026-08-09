"""Independent offline auditor for one sealed M7 network-recovery evaluation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from shaiwei.research_gates.m7_moneyflow.contract import canonical_json

from shaiwei.research_gates.m7_moneyflow_recovery.auditor import audit_evaluation
from shaiwei.research_gates.m7_moneyflow_recovery.contract import RecoveryError
from shaiwei.research_gates.m7_moneyflow_recovery.evaluator import evaluation_run_id

from .network_runtime import (
    assemble_runtime_inputs,
    load_runtime_authority,
    role_activation_id,
)
from .sealing import claim_role_once, read_canonical, sha256_file, write_canonical_once


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--plan-root", type=Path, required=True)
    parser.add_argument("--release-scope", type=Path, required=True)
    parser.add_argument("--approval-envelope", type=Path, required=True)
    parser.add_argument("--target-root", type=Path, required=True)
    parser.add_argument("--status-root", type=Path, required=True)
    parser.add_argument("--moneyflow-root", type=Path, required=True)
    parser.add_argument("--evaluation-root", type=Path, required=True)
    parser.add_argument("--audit-root", type=Path, required=True)
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
            role="auditor",
            release_scope_sha256=authority.release.sha256,
            run_id=role_activation_id(authority, "auditor"),
        )
        sealed = assemble_runtime_inputs(
            authority,
            target_root=args.target_root.resolve(strict=True),
            status_root=args.status_root.resolve(strict=True),
            moneyflow_root=args.moneyflow_root.resolve(strict=True),
        )
        run_id = evaluation_run_id(
            authority.recovery,
            release_scope_sha256=authority.release.sha256,
            target_plan_manifest_sha256=authority.plan_manifest_sha256,
            batch_manifest_sha256=sealed.batch_manifest_sha256,
        )
        run_root = args.evaluation_root.resolve(strict=True) / run_id
        report = read_canonical(run_root / "report.json")
        manifest = read_canonical(run_root / "evaluation_manifest.json")
        if (
            manifest.get("run_id") != run_id
            or manifest.get("report_sha256") != sha256_file(run_root / "report.json")
            or manifest.get("batch_manifest_sha256") != sealed.batch_manifest_sha256
            or int(manifest.get("sealed_receipt_count", -1)) != sealed.receipt_count
        ):
            raise RecoveryError("recovery network evaluation manifest differs")
        audit = audit_evaluation(authority.recovery, sealed.inputs, report)
        audit["provider_call_count"] = sealed.receipt_count
        audit["network_collection"] = {
            "batch_manifest_sha256": sealed.batch_manifest_sha256,
            "sealed_receipt_count": sealed.receipt_count,
        }
        audit_sha = write_canonical_once(args.audit_root / run_id / "audit.json", audit)
    except (OSError, RecoveryError, TypeError, ValueError, json.JSONDecodeError) as error:
        print(canonical_json({"status": "FAIL", "error_class": type(error).__name__}))
        return 2
    print(
        canonical_json(
            {
                "status": "PASS",
                "role": "auditor",
                "run_id": run_id,
                "audit_sha256": audit_sha,
                "verdict": audit["verdict"],
                "production_authorization": "none",
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
