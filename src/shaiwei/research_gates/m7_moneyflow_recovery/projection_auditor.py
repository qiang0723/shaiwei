"""Independent DuckDB projection audit against sealed target Parquet outputs."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd
import pyarrow.parquet as pq

from shaiwei.research_gates.m7_moneyflow.contract import canonical_json, sha256_json
from shaiwei.research_gates.m7_moneyflow_lineage.audit_compute import (
    _prepare,
    recompute_lineage_core,
)
from shaiwei.research_gates.m7_moneyflow_lineage.contract import (
    LineageInputManifest,
    LineageProtocol,
)
from shaiwei.research_gates.m7_moneyflow_lineage.reader import LineageInputs, load_lineage_inputs

from .contract import RecoveryError
from .projection_contract import TargetProjectionProtocol
from .projection_release import TargetProjectionApproval, TargetProjectionRelease
from .projection_runner import projection_run_id
from .projection_sealing import logical_target_sha256
from .sealing import claim_role_once, read_canonical, sha256_file, write_canonical_once
from .target_projection import OUTPUT_COLUMNS, TRACK_A, TRACK_B


def independent_targets(
    protocol: LineageProtocol, inputs: LineageInputs, category: str
) -> pd.DataFrame:
    connection = duckdb.connect(":memory:")
    try:
        _prepare(connection, protocol, inputs)
        frame = connection.execute(
            """
            SELECT CAST(c.trade_date AS VARCHAR) trade_date,
                   CAST(c.source_date AS VARCHAR) source_date,
                   CAST(c.universe_id AS VARCHAR) universe_id,
                   CAST(c.ts_code AS VARCHAR) ts_code,
                   CAST(m.segment AS VARCHAR) segment
            FROM classified c
            JOIN membership m
              ON CAST(c.trade_date AS VARCHAR)=CAST(m.trade_date AS VARCHAR)
             AND CAST(c.universe_id AS VARCHAR)=CAST(m.universe_id AS VARCHAR)
             AND CAST(c.ts_code AS VARCHAR)=CAST(m.ts_code AS VARCHAR)
            WHERE c.category=?
            ORDER BY 1,2,3,4,5
            """,
            [category],
        ).fetchdf()
    finally:
        connection.close()
    return frame.loc[:, OUTPUT_COLUMNS].astype("string")


def _verified_target(path: Path, item: dict[str, Any]) -> pd.DataFrame:
    metadata = pq.read_metadata(path)
    payload_sha = hashlib.sha256(path.read_bytes()).hexdigest()
    if (
        path.name != item["relative_name"]
        or path.stat().st_size != item["bytes"]
        or metadata.num_rows != item["row_count"]
        or list(metadata.schema.names) != item["schema_fields"]
        or payload_sha != item["parquet_sha256"]
    ):
        raise RecoveryError("recovery target projection physical output differs")
    frame = pq.read_table(path).to_pandas()
    if logical_target_sha256(frame) != item["logical_content_sha256"]:
        raise RecoveryError("recovery target projection logical output differs")
    return frame


def audit_projection(
    projection: TargetProjectionProtocol,
    lineage: LineageProtocol,
    manifest: LineageInputManifest,
    release: TargetProjectionRelease,
    approval: TargetProjectionApproval,
    *,
    inputs: LineageInputs,
    output_root: Path,
    synthetic_expected_lineage_core_sha256: str | None = None,
) -> dict[str, Any]:
    run_id = projection_run_id(projection, release, approval)
    run_root = output_root / run_id
    expected_core = synthetic_expected_lineage_core_sha256 or projection.expected_lineage_core_sha256
    report_path = run_root / "target_projection_report.json"
    report = read_canonical(report_path)
    run_manifest = read_canonical(run_root / "target_projection_manifest.json")
    if (
        sha256_file(report_path) != run_manifest.get("report_sha256")
        or run_manifest.get("schema_version")
        != "m7-moneyflow-recovery-target-projection-manifest-v1"
        or run_manifest.get("protocol_sha256") != projection.sha256
        or run_manifest.get("release_scope_sha256") != release.sha256
        or run_manifest.get("approval_sha256") != approval.sha256
        or run_manifest.get("lineage_core_sha256") != expected_core
        or run_manifest.get("security_codes_in_manifest") is not False
        or run_manifest.get("numeric_moneyflow_value_columns_read") != 0
        or run_manifest.get("provider_call_count") != 0
        or run_manifest.get("production_authorization") != "none"
    ):
        raise RecoveryError("recovery target projection manifest identity differs")
    core = recompute_lineage_core(lineage, inputs)
    if sha256_json(core) != expected_core:
        raise RecoveryError("recovery target projection independent lineage core differs")
    expected_a = independent_targets(lineage, inputs, TRACK_A)
    expected_b = independent_targets(lineage, inputs, TRACK_B)
    observed_a = _verified_target(run_root / "track_a_targets.parquet", run_manifest["track_a"])
    observed_b = _verified_target(run_root / "track_b_targets.parquet", run_manifest["track_b"])
    expected_hashes = {
        "track_a": logical_target_sha256(expected_a),
        "track_b": logical_target_sha256(expected_b),
    }
    observed_hashes = {
        "track_a": logical_target_sha256(observed_a),
        "track_b": logical_target_sha256(observed_b),
    }
    counts = projection.document["projection_contract"]
    if (
        expected_hashes != observed_hashes
        or report.get("logical_content_sha256") != expected_hashes
        or report.get("run_id") != run_id
        or run_manifest.get("run_id") != run_id
        or report.get("lineage_input_manifest_sha256") != manifest.sha256
        or len(expected_a) != counts["track_a"]["expected_member_rows"]
        or len(expected_b) != counts["track_b"]["expected_member_rows"]
        or expected_a.duplicated(["trade_date", "universe_id", "ts_code"]).any()
        or expected_b.duplicated(["trade_date", "universe_id", "ts_code"]).any()
        or expected_a["ts_code"].str.endswith(".BJ").any()
        or expected_b["ts_code"].str.endswith(".BJ").any()
    ):
        raise RecoveryError("recovery target projection independent target set differs")
    return {
        "schema_version": "m7-moneyflow-recovery-target-projection-audit-v1",
        "status": "PASS",
        "run_id": run_id,
        "protocol_sha256": projection.sha256,
        "release_scope_sha256": release.sha256,
        "approval_sha256": approval.sha256,
        "independent_lineage_core_sha256": expected_core,
        "independent_logical_content_sha256": expected_hashes,
        "track_a_member_rows": len(expected_a),
        "track_b_member_rows": len(expected_b),
        "main_and_independent_targets_exact_match": True,
        "moneyflow_numeric_value_columns_read": 0,
        "provider_call_count": 0,
        "network_used": False,
        "adjusted_coverage_computed": False,
        "research_attempt_increment": 0,
        "production_authorization": "none",
        "verdict": "GO_M7_RECOVERY_TARGET_PROJECTION_ONLY",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--input-root", type=Path, required=True)
    parser.add_argument("--release-scope", type=Path, required=True)
    parser.add_argument("--approval-envelope", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--audit-root", type=Path, required=True)
    parser.add_argument("--claim-root", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        project_root = args.project_root.resolve(strict=True)
        input_root = args.input_root.resolve(strict=True)
        projection = TargetProjectionProtocol.load(
            project_root / "config/m7_moneyflow_recovery_target_projection_v2.yaml",
            project_root=project_root,
        )
        lineage = LineageProtocol.load(
            input_root / "config/m7_moneyflow_gap_lineage_v1.yaml", project_root=input_root
        )
        manifest = LineageInputManifest.load(
            input_root / "config/m7_moneyflow_gap_lineage_input_v1.json", lineage
        )
        release = TargetProjectionRelease.load(args.release_scope, projection)
        approval = TargetProjectionApproval.load(args.approval_envelope, release)
        run_id = projection_run_id(projection, release, approval)
        claim_role_once(
            args.claim_root,
            role="target_auditor",
            release_scope_sha256=release.sha256,
            run_id=run_id,
        )
        inputs = load_lineage_inputs(lineage, manifest, input_root=input_root)
        audit = audit_projection(
            projection,
            lineage,
            manifest,
            release,
            approval,
            inputs=inputs,
            output_root=args.output_root,
        )
        audit_sha = write_canonical_once(args.audit_root / run_id / "target_projection_audit.json", audit)
    except (OSError, RecoveryError, TypeError, ValueError, json.JSONDecodeError) as error:
        print(canonical_json({"status": "FAIL", "error_class": type(error).__name__, "message": str(error)}))
        return 2
    print(canonical_json({**audit, "audit_sha256": audit_sha}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
