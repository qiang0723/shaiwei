"""Independent M7 auditor: re-read keys, recompute all gates, and verify sealing."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .audit_compute import recompute_quality_core
from .contract import (
    InputManifest,
    M7GateError,
    M7Protocol,
    canonical_json,
    sha256_file,
    sha256_json,
)
from .reader import load_key_inputs
from .release import ApprovalEnvelope, DataReleaseScope
from .sealing import canonical_object, seal_audit


CORE_KEYS = (
    "dataset_and_grain",
    "pit_mapping",
    "completeness",
    "uniqueness",
    "validity",
    "integrity",
    "gates",
    "authority",
    "verdict",
)


def audit_run(
    protocol: M7Protocol,
    manifest: InputManifest,
    release: DataReleaseScope,
    approval: ApprovalEnvelope,
    *,
    input_root: Path,
    run_root: Path,
) -> dict[str, Any]:
    manifest_path = run_root / "run_manifest.json"
    report_path = run_root / "data_gate_report.json"
    if not manifest_path.is_file() or not report_path.is_file():
        raise M7GateError("M7 run root is incomplete")
    run_manifest = canonical_object(manifest_path)
    report = canonical_object(report_path)
    identities = {
        "protocol_sha256": protocol.sha256,
        "input_manifest_sha256": manifest.sha256,
        "release_scope_sha256": release.sha256,
        "approval_sha256": approval.sha256,
        "code_bundle_sha256": release.scope["implementation"]["code_bundle_sha256"],
    }
    if any(report.get(key) != value or run_manifest.get(key) != value for key, value in identities.items()):
        raise M7GateError("M7 sealed run identity differs from approved release")
    if (
        report.get("schema_version") != "m7-moneyflow-data-compatibility-report-v1"
        or report.get("protocol_scope_sha256") != protocol.build_document["protocol_scope_sha256"]
        or report.get("build_contract_sha256") != protocol.build_sha256
        or report.get("input_manifest_physical_sha256") != manifest.physical_sha256
        or report.get("semantic_rows_read") is not True
        or report.get("label_or_return_read") is not False
        or report.get("effect_read") is not False
        or report.get("model_training_run") is not False
        or report.get("backtest_run") is not False
        or report.get("provider_call_count") != 0
        or report.get("provider_cost_usd") != "0.00"
        or report.get("authority", {}).get("production_authorization") != "none"
    ):
        raise M7GateError("M7 runner report shape or authority differs")
    if run_manifest.get("report_sha256") != sha256_file(report_path):
        raise M7GateError("M7 sealed report physical hash differs")
    expected_run_id = sha256_json(identities)
    if report.get("run_id") != expected_run_id or run_manifest.get("run_id") != expected_run_id:
        raise M7GateError("M7 run ID differs")
    inputs = load_key_inputs(protocol, manifest, input_root=input_root)
    recomputed = recompute_quality_core(protocol, inputs)
    reported = {key: report[key] for key in CORE_KEYS}
    recomputed_sha = sha256_json(recomputed)
    if reported != recomputed or report.get("core_sha256") != recomputed_sha:
        raise M7GateError("M7 reported quality core differs from independent recomputation")
    replay = report.get("internal_replay") or {}
    if replay != {
        "status": "PASS",
        "first_pass_core_sha256": recomputed_sha,
        "replay_core_sha256": recomputed_sha,
    }:
        raise M7GateError("M7 runner internal replay evidence differs")
    if run_manifest.get("verdict") != recomputed["verdict"]:
        raise M7GateError("M7 run manifest verdict differs")
    return {
        "schema_version": "m7-moneyflow-data-compatibility-audit-v1",
        "status": "PASS",
        "run_id": expected_run_id,
        "protocol_sha256": protocol.sha256,
        "input_manifest_sha256": manifest.sha256,
        "release_scope_sha256": release.sha256,
        "approval_sha256": approval.sha256,
        "run_manifest_sha256": sha256_file(manifest_path),
        "report_sha256": sha256_file(report_path),
        "reported_core_sha256": recomputed_sha,
        "independent_recomputed_core_sha256": recomputed_sha,
        "checked_gate_count": len(recomputed["gates"]),
        "verdict": recomputed["verdict"],
        "semantic_rows_read": True,
        "numeric_moneyflow_value_columns_read": 0,
        "effect_test_count": 0,
        "generation_attempt_increment": 0,
        "strategy_effective": "NOT_EVALUATED",
        "production_authorization": "none",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--build-contract", type=Path, required=True)
    parser.add_argument("--input-manifest", type=Path, required=True)
    parser.add_argument("--release-scope", type=Path, required=True)
    parser.add_argument("--approval-envelope", type=Path, required=True)
    parser.add_argument("--input-root", type=Path, required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--audit-root", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        protocol = M7Protocol.load(args.protocol, build_path=args.build_contract, project_root=args.input_root)
        manifest = InputManifest.load(args.input_manifest, protocol)
        release = DataReleaseScope.load(args.release_scope, protocol, manifest)
        approval = ApprovalEnvelope.load(args.approval_envelope, release)
        result = seal_audit(
            args.audit_root,
            audit_run(
                protocol,
                manifest,
                release,
                approval,
                input_root=args.input_root,
                run_root=args.run_root,
            ),
        )
    except (M7GateError, OSError, TypeError, ValueError, json.JSONDecodeError) as error:
        print(canonical_json({"status": "FAIL", "error_class": type(error).__name__, "message": str(error)}))
        return 2
    print(canonical_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
