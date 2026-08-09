"""Real-scale synthetic, offline acceptance for target projection and audit."""

from __future__ import annotations

import argparse
import tempfile
from pathlib import Path

import pandas as pd

from shaiwei.research_gates.m7_moneyflow.contract import canonical_json, sha256_json
from shaiwei.research_gates.m7_moneyflow_lineage.compute import compute_lineage_core
from shaiwei.research_gates.m7_moneyflow_lineage.contract import (
    UNIVERSE_IDS,
    LineageInputManifest,
    LineageProtocol,
)
from shaiwei.research_gates.m7_moneyflow_lineage.reader import LineageInputs

from .contract import RecoveryError, RecoveryProtocol
from .projection_auditor import audit_projection
from .projection_contract import ACTION, TargetProjectionProtocol
from .projection_release import (
    APPROVER_SHA256,
    TargetProjectionApproval,
    TargetProjectionRelease,
    build_release_document,
)
from .projection_runner import build_projection, projection_run_id
from .sealing import claim_role_once, write_canonical_once


def synthetic_lineage_inputs() -> LineageInputs:
    records = [
        {
            "trade_date": "20210104",
            "formation_date": "20201231",
            "universe_id": UNIVERSE_IDS[index % len(UNIVERSE_IDS)],
            "ts_code": f"{688000 + index:06d}.SH",
            "segment": "2021H1",
        }
        for index in range(1449)
    ]
    membership = pd.DataFrame(records)
    suspension = pd.DataFrame(
        {
            "ts_code": membership.iloc[:908]["ts_code"],
            "trade_date": "20201231",
            "primary_full_day": 1,
            "primary_intraday": 0,
        }
    )
    daily = pd.DataFrame(
        {"ts_code": membership.iloc[908:]["ts_code"], "trade_date": "20201231"}
    )
    return LineageInputs(
        membership=membership,
        moneyflow_keys=pd.DataFrame(columns=("ts_code", "trade_date", "request_trade_date")),
        daily_keys=daily,
        suspension=suspension,
        independent_status=pd.DataFrame(
            columns=(
                "ts_code",
                "trade_date",
                "independent_nontrading",
                "independent_trading",
                "invalid_status_rows",
            )
        ),
        official_dates=("20201231", "20210104"),
        quarantined_source_dates=frozenset(),
        evidence={"numeric_moneyflow_value_columns_read": 0},
    )


def _runtime(project_root: Path, root: Path) -> tuple[object, ...]:
    projection = TargetProjectionProtocol.load(
        project_root / "config/m7_moneyflow_recovery_target_projection_v2.yaml",
        project_root=project_root,
    )
    recovery = RecoveryProtocol.load(
        project_root / "config/m7_moneyflow_evidence_recovery_v1.yaml",
        engineering_path=project_root / "config/m7_moneyflow_evidence_recovery_engineering_v1.yaml",
        project_root=project_root,
    )
    lineage = LineageProtocol.load(
        project_root / "config/m7_moneyflow_gap_lineage_v1.yaml", project_root=project_root
    )
    lineage_manifest = LineageInputManifest({}, "a" * 64, "b" * 64)
    release_document = build_release_document(
        projection,
        created_at="2026-08-09T14:12:07+08:00",
        git_commit="c" * 40,
        code_bundle_sha256="d" * 64,
        image_id="sha256:" + "e" * 64,
        platform="linux/arm64",
    )
    release_path = root / "release.json"
    release_path.write_text(canonical_json(release_document) + "\n", encoding="utf-8")
    release = TargetProjectionRelease.load(release_path, projection)
    approval_document = {
        "schema_version": "m7-moneyflow-recovery-target-approval-v1",
        "action": ACTION,
        "release_scope_sha256": release.sha256,
        "approved_at": "2026-08-09T14:12:08+08:00",
        "approval_actor_sha256": APPROVER_SHA256,
        "execution_authorized": True,
    }
    approval_path = root / "approval.json"
    approval_path.write_text(canonical_json(approval_document) + "\n", encoding="utf-8")
    approval = TargetProjectionApproval.load(approval_path, release)
    return projection, recovery, lineage, lineage_manifest, release, approval


def verify_projection_fixture(project_root: Path) -> dict[str, object]:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        projection, recovery, lineage, manifest, release, approval = _runtime(project_root, root)
        inputs = synthetic_lineage_inputs()
        expected_core = sha256_json(compute_lineage_core(lineage, inputs))
        loader_calls = 0

        def loader() -> LineageInputs:
            nonlocal loader_calls
            loader_calls += 1
            return inputs

        run_manifest = build_projection(
            projection,
            recovery,
            lineage,
            manifest,
            release,
            approval,
            input_loader=loader,
            output_root=root / "outputs",
            claim_root=root / "claims",
            synthetic_expected_lineage_core_sha256=expected_core,
        )
        run_id = projection_run_id(projection, release, approval)
        claim_role_once(
            root / "claims",
            role="target_auditor",
            release_scope_sha256=release.sha256,
            run_id=run_id,
        )
        audit = audit_projection(
            projection,
            lineage,
            manifest,
            release,
            approval,
            inputs=inputs,
            output_root=root / "outputs",
            synthetic_expected_lineage_core_sha256=expected_core,
        )
        audit_sha = write_canonical_once(root / "audits" / run_id / "audit.json", audit)
        try:
            build_projection(
                projection,
                recovery,
                lineage,
                manifest,
                release,
                approval,
                input_loader=loader,
                output_root=root / "outputs",
                claim_root=root / "claims",
                synthetic_expected_lineage_core_sha256=expected_core,
            )
        except RecoveryError:
            duplicate_stopped = True
        else:
            duplicate_stopped = False
    if not duplicate_stopped or loader_calls != 1:
        raise RecoveryError("recovery target fixture duplicate did not stop before loader")
    return {
        "status": "PASS",
        "verdict": "GO_M7_RECOVERY_TARGET_PROJECTION_ENGINEERING_ONLY",
        "track_a_member_rows": run_manifest["track_a"]["row_count"],
        "track_b_member_rows": run_manifest["track_b"]["row_count"],
        "main_and_independent_targets_exact_match": audit[
            "main_and_independent_targets_exact_match"
        ],
        "second_invocation_stopped_before_semantic_read": True,
        "audit_sha256": audit_sha,
        "real_security_key_read": False,
        "moneyflow_numeric_value_columns_read": 0,
        "provider_call_count": 0,
        "network_used": False,
        "production_authorization": "none",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = verify_projection_fixture(args.project_root.resolve(strict=True))
    except (OSError, RecoveryError, TypeError, ValueError) as error:
        print(canonical_json({"status": "FAIL", "error_class": type(error).__name__, "message": str(error)}))
        return 2
    print(canonical_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
