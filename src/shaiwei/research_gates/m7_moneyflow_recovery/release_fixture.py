"""Offline synthetic acceptance for the non-executable recovery release chain."""

from __future__ import annotations

import argparse
import tempfile
from pathlib import Path

from shaiwei.research_gates.m7_moneyflow.contract import canonical_json, sha256_json

from .auditor import audit_evaluation
from .batch_reader import assemble_inputs
from .batch_store import BatchIdentity, write_batch
from .contract import RecoveryError, RecoveryProtocol
from .evaluator import evaluate_recovery, evaluation_run_id
from .fixture import synthetic_inputs
from .release import (
    NonExecutableRecoveryRelease,
    RecoveryReleaseBuild,
    build_synthetic_release,
)
from .sealing import claim_role_once, write_canonical_once


def _receipt_path(root: Path, receipt: dict[str, object]) -> Path:
    return root / Path(str(receipt["batch_relative_path"])).with_name("receipt.json")


def verify_release_fixture(project_root: Path) -> dict[str, object]:
    protocol = RecoveryProtocol.load(
        project_root / "config/m7_moneyflow_evidence_recovery_v1.yaml",
        engineering_path=project_root / "config/m7_moneyflow_evidence_recovery_engineering_v1.yaml",
        project_root=project_root,
    )
    build = RecoveryReleaseBuild.load(
        project_root / "config/m7_moneyflow_recovery_release_build_v1.yaml",
        project_root=project_root,
    )
    clean = synthetic_inputs(protocol)
    target_manifest_sha = sha256_json(
        {
            "synthetic": True,
            "track_a_member_rows": len(clean.track_a_targets),
            "track_b_member_rows": len(clean.track_b_targets),
        }
    )
    request_bundles = {
        "status": {"request_count": 1, "identity_bundle_sha256": "a" * 64},
        "full_market": {"request_count": 1, "identity_bundle_sha256": "b" * 64},
        "targeted": {"request_count": 1, "identity_bundle_sha256": "c" * 64},
    }
    document = build_synthetic_release(
        build,
        implementation_commit="d" * 40,
        code_bundle_sha256="e" * 64,
        image_id="sha256:" + "f" * 64,
        target_plan_manifest_sha256=target_manifest_sha,
        request_bundles=request_bundles,
    )
    release = NonExecutableRecoveryRelease.parse(canonical_json(document) + "\n", build)
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        status_root = root / "status"
        moneyflow_root = root / "moneyflow"
        status_receipt = write_batch(
            status_root,
            BatchIdentity(release.sha256, "1" * 64, "baostock.history_k_data_plus", "exact_status_window"),
            clean.independent_status,
        )
        full_receipt = write_batch(
            moneyflow_root,
            BatchIdentity(release.sha256, "2" * 64, "tushare.moneyflow", "full_market_by_trade_date"),
            clean.full_market_target_rows,
        )
        targeted_receipt = write_batch(
            moneyflow_root,
            BatchIdentity(release.sha256, "3" * 64, "tushare.moneyflow", "one_security_one_date"),
            clean.targeted_rows,
        )
        receipts = [status_receipt, full_receipt, targeted_receipt]
        inputs = assemble_inputs(
            protocol,
            release_scope_sha256=release.sha256,
            status_root=status_root,
            moneyflow_root=moneyflow_root,
            track_a=clean.track_a_targets,
            track_b=clean.track_b_targets,
            daily_keys=clean.daily_keys,
            official_dates=clean.official_dates,
            status_receipts=[_receipt_path(status_root, status_receipt)],
            full_market_receipts=[_receipt_path(moneyflow_root, full_receipt)],
            targeted_receipts=[_receipt_path(moneyflow_root, targeted_receipt)],
            status_request_sha256s=frozenset({"1" * 64}),
            full_market_request_sha256s=frozenset({"2" * 64}),
            targeted_request_sha256s=frozenset({"3" * 64}),
        )
        batch_manifest_sha = sha256_json(receipts)
        run_id = evaluation_run_id(
            protocol,
            release_scope_sha256=release.sha256,
            target_plan_manifest_sha256=target_manifest_sha,
            batch_manifest_sha256=batch_manifest_sha,
        )
        claim_role_once(
            root / "evaluator-claims",
            role="evaluator",
            release_scope_sha256=release.sha256,
            run_id=run_id,
        )
        report = evaluate_recovery(
            protocol,
            inputs,
            release_scope_sha256=release.sha256,
            target_plan_manifest_sha256=target_manifest_sha,
            batch_manifest_sha256=batch_manifest_sha,
        )
        report_sha = write_canonical_once(root / "run" / "report.json", report)
        claim_role_once(
            root / "auditor-claims",
            role="auditor",
            release_scope_sha256=release.sha256,
            run_id=str(report["run_id"]),
        )
        audit = audit_evaluation(protocol, inputs, report)
        audit_sha = write_canonical_once(root / "audit" / "report.json", audit)
        try:
            write_batch(
                status_root,
                BatchIdentity(
                    release.sha256,
                    "1" * 64,
                    "baostock.history_k_data_plus",
                    "exact_status_window",
                ),
                clean.independent_status,
            )
        except RecoveryError:
            duplicate_stopped = True
        else:
            duplicate_stopped = False
    if not duplicate_stopped:
        raise RecoveryError("recovery release fixture did not stop duplicate batch")
    return {
        "status": "PASS",
        "verdict": "GO_M7_RECOVERY_RELEASE_ENGINEERING_ONLY",
        "release_scope_sha256": release.sha256,
        "report_sha256": report_sha,
        "audit_sha256": audit_sha,
        "batch_count": 3,
        "collector_writable_roots_separate": True,
        "evaluator_internal_replay": True,
        "independent_audit_exact_match": True,
        "duplicate_batch_stopped": True,
        "actual_provider_call_count": 0,
        "real_target_projection_run": False,
        "real_scope_generated": False,
        "production_authorization": "none",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = verify_release_fixture(args.project_root.resolve(strict=True))
    except (OSError, RecoveryError, TypeError, ValueError) as error:
        print(canonical_json({"status": "FAIL", "error_class": type(error).__name__, "message": str(error)}))
        return 2
    print(canonical_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
