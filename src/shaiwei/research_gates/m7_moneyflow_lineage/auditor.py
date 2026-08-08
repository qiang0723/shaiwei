"""Independent one-shot auditor for a sealed M7 lineage run."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from shaiwei.research_gates.m7_moneyflow.consumption import execute_after_pre_read_claim
from shaiwei.research_gates.m7_moneyflow.contract import M7GateError, canonical_json, sha256_file, sha256_json

from .audit_compute import recompute_lineage_core
from .contract import LineageError, LineageInputManifest, LineageProtocol
from .reader import load_lineage_inputs
from .release import LineageApproval, LineageRelease
from .runner import run_identity
from .sealing import canonical_object, seal_audit


CORE_KEYS = ("dataset_and_grain", "lineage_partition", "validity", "gates", "authority", "verdict")


def audit_run(
    protocol: LineageProtocol,
    manifest: LineageInputManifest,
    release: LineageRelease,
    approval: LineageApproval,
    *,
    input_root: Path,
    run_root: Path,
    claim_root: Path,
) -> dict[str, Any]:
    report_path = run_root / "lineage_report.json"
    manifest_path = run_root / "run_manifest.json"
    report = canonical_object(report_path)
    run_manifest = canonical_object(manifest_path)
    identity = run_identity(protocol, manifest, release, approval)
    run_id = sha256_json(identity)
    if any(report.get(key) != value or run_manifest.get(key) != value for key, value in identity.items()):
        raise LineageError("lineage sealed identity differs")
    if report.get("run_id") != run_id or run_manifest.get("run_id") != run_id:
        raise LineageError("lineage sealed run ID differs")
    if run_manifest.get("report_sha256") != sha256_file(report_path):
        raise LineageError("lineage report physical hash differs")
    claim, inputs = execute_after_pre_read_claim(
        claim_root,
        {
            "protocol_sha256": protocol.sha256,
            "release_scope_sha256": release.sha256,
            "approval_sha256": approval.sha256,
            "role": "auditor",
            "run_id": run_id,
        },
        lambda: load_lineage_inputs(protocol, manifest, input_root=input_root),
    )
    recomputed = recompute_lineage_core(protocol, inputs)
    reported = {key: report[key] for key in CORE_KEYS}
    core_sha = sha256_json(recomputed)
    if reported != recomputed or report.get("core_sha256") != core_sha:
        raise LineageError("lineage report differs from independent recomputation")
    if report.get("internal_replay") != {
        "status": "PASS",
        "first_pass_core_sha256": core_sha,
        "replay_core_sha256": core_sha,
    }:
        raise LineageError("lineage internal replay evidence differs")
    return {
        "schema_version": "m7-moneyflow-gap-lineage-audit-v1",
        "status": "PASS",
        "run_id": run_id,
        **identity,
        "run_manifest_sha256": sha256_file(manifest_path),
        "report_sha256": sha256_file(report_path),
        "reported_core_sha256": core_sha,
        "independent_recomputed_core_sha256": core_sha,
        "checked_gate_count": len(recomputed["gates"]),
        "verdict": recomputed["verdict"],
        "pre_read_consumption": claim,
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
    parser.add_argument("--input-manifest", type=Path, required=True)
    parser.add_argument("--release-scope", type=Path, required=True)
    parser.add_argument("--approval-envelope", type=Path, required=True)
    parser.add_argument("--input-root", type=Path, required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--audit-root", type=Path, required=True)
    parser.add_argument("--claim-root", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        protocol = LineageProtocol.load(args.protocol, project_root=args.input_root)
        manifest = LineageInputManifest.load(args.input_manifest, protocol)
        release = LineageRelease.load(args.release_scope, protocol, manifest)
        approval = LineageApproval.load(args.approval_envelope, release)
        result = seal_audit(
            args.audit_root,
            audit_run(
                protocol,
                manifest,
                release,
                approval,
                input_root=args.input_root,
                run_root=args.run_root,
                claim_root=args.claim_root,
            ),
        )
    except (LineageError, M7GateError, OSError, TypeError, ValueError, json.JSONDecodeError) as error:
        print(canonical_json({"status": "FAIL", "error_class": type(error).__name__, "message": str(error)}))
        return 2
    print(canonical_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
