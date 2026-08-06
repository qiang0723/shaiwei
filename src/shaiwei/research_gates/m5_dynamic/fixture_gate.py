"""Offline container smoke gate using only fabricated M5 inputs and a temporary registry."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pandas as pd

from shaiwei.research_gates.gate_registry.integrity import verify_registry_integrity
from shaiwei.research_gates.gate_registry.models import GateIdentity, canonical_json
from shaiwei.research_gates.gate_registry.service import GateRegistryService
from shaiwei.research_gates.gate_registry.storage import GateRegistryStore

from .auditor import audit_run, seal_audit
from .contract import PROTOCOL_SCOPE_SHA256, M5DataProtocol, sha256_file
from .failure_projection import build_global_failure_reports
from .fixture import synthetic_inputs
from .runner import build_gate_result, seal_global_failure, seal_run
from .source_conflicts import assess_all_statement_sources


def _conflicting_inputs(protocol: M5DataProtocol, mode: str):
    frames, memberships = synthetic_inputs(protocol)
    source = {
        "WITHIN_STANDARD": "tushare.balancesheet",
        "WITHIN_VIP": "tushare.balancesheet_vip",
        "STANDARD_VIP": "tushare.balancesheet_vip",
    }[mode]
    frame = frames[source].copy(deep=True)
    if mode == "STANDARD_VIP":
        frame.loc[0, "total_assets"] = float(frame.loc[0, "total_assets"]) + 1
    else:
        extra = frame.iloc[[0]].copy(deep=True)
        extra.loc[extra.index[0], "total_assets"] = (
            float(extra.loc[extra.index[0], "total_assets"]) + 1
        )
        frame = pd.concat([frame, extra], ignore_index=True)
    frames[source] = frame
    return frames, memberships


def _classification_fixture(protocol: M5DataProtocol) -> bool:
    frames, _ = synthetic_inputs(protocol)
    baseline = assess_all_statement_sources(frames)
    if baseline.has_conflicts:
        return False
    ordinary = frames["tushare.income"].copy(deep=True)
    vip = frames["tushare.income_vip"].copy(deep=True)
    frames["tushare.income"] = pd.concat(
        [ordinary, ordinary.iloc[[0]].copy(deep=True)], ignore_index=True
    )
    frames["tushare.income_vip"] = vip.iloc[1:].copy(deep=True)
    standard = assess_all_statement_sources(frames)
    standard_count = standard.report["tables"][0]["category_counts"][
        "EXACT_DUPLICATE_WITHIN_STANDARD"
    ]

    frames, _ = synthetic_inputs(protocol)
    ordinary = frames["tushare.income"].copy(deep=True)
    vip = frames["tushare.income_vip"].copy(deep=True)
    frames["tushare.income"] = ordinary.iloc[1:].copy(deep=True)
    frames["tushare.income_vip"] = pd.concat(
        [vip, vip.iloc[[0]].copy(deep=True)], ignore_index=True
    )
    vip_result = assess_all_statement_sources(frames)
    vip_count = vip_result.report["tables"][0]["category_counts"][
        "EXACT_DUPLICATE_WITHIN_VIP"
    ]

    frames, _ = synthetic_inputs(protocol)
    frames["tushare.income"].loc[0, "rd_exp"] = None
    frames["tushare.income_vip"].loc[0, "rd_exp"] = None
    null_result = assess_all_statement_sources(frames)
    return bool(
        standard_count == 1
        and vip_count == 1
        and not standard.has_conflicts
        and not vip_result.has_conflicts
        and not null_result.has_conflicts
    )


def _identity(protocol: M5DataProtocol) -> GateIdentity:
    proposal = protocol.document["source_proposal"]
    return GateIdentity(
        proposal_id=proposal["proposal_id"],
        proposal_request_sha256=proposal["proposal_request_sha256"],
        canonical_proposal_sha256=proposal["canonical_proposal_sha256"],
        proposal_head_event_sha256=proposal["required_head_event_sha256"],
        proposal_export_sha256=proposal["proposal_export_sha256"],
        protocol_scope_sha256=protocol.protocol_scope_sha256,
        protocol_sha256=protocol.sha256,
        proposal_expires_at=proposal["expires_at"],
        candidate_ids=protocol.candidate_ids,
    )


def run_fixture(project_root: Path) -> dict[str, object]:
    protocol = M5DataProtocol.load(
        project_root / "config/m5_dynamic_fundamental_cross_pool_v1.yaml",
        build_path=project_root / "config/m5_dynamic_fundamental_data_gate_build_v2.yaml",
        project_root=project_root,
    )
    frames, memberships = synthetic_inputs(protocol)
    input_sha, release_sha, code_sha, approval_sha = (character * 64 for character in "1234")
    panel, report = build_gate_result(
        protocol,
        frames,
        memberships,
        input_manifest_sha256=input_sha,
        release_scope_sha256=release_sha,
        code_bundle_sha256=code_sha,
        approval_event_sha256=approval_sha,
        semantic_rows_read=False,
    )
    with tempfile.TemporaryDirectory(prefix="m5-fixture-") as temporary:
        root = Path(temporary)
        normal_manifest = seal_run(root / "normal-runs", panel, report)
        normal_root = root / "normal-runs" / normal_manifest["run_id"]
        normal_audit = audit_run(
            protocol,
            frames,
            memberships,
            run_root=normal_root,
            expected_input_manifest_sha256=input_sha,
            expected_release_scope_sha256=release_sha,
            expected_approval_event_sha256=approval_sha,
        )
        seal_audit(root / "normal-audits", normal_audit)

        failure_results = {}
        for index, mode in enumerate(
            ("WITHIN_STANDARD", "WITHIN_VIP", "STANDARD_VIP"), start=5
        ):
            conflict_frames, conflict_memberships = _conflicting_inputs(protocol, mode)
            variant_input_sha = str(index) * 64
            assessment = assess_all_statement_sources(conflict_frames)
            conflict_report, failure_report = build_global_failure_reports(
                protocol,
                assessment,
                input_manifest_sha256=variant_input_sha,
                release_scope_sha256=release_sha,
                code_bundle_sha256=code_sha,
                approval_event_sha256=approval_sha,
                source_evidence={"sources": {}, "memberships": {}},
                semantic_rows_read=False,
            )
            manifest = seal_global_failure(
                root / "failure-runs", conflict_report, failure_report
            )
            replayed_manifest = seal_global_failure(
                root / "failure-runs", conflict_report, failure_report
            )
            run_root = root / "failure-runs" / manifest["run_id"]
            audit = audit_run(
                protocol,
                conflict_frames,
                conflict_memberships,
                run_root=run_root,
                expected_input_manifest_sha256=variant_input_sha,
                expected_release_scope_sha256=release_sha,
                expected_approval_event_sha256=approval_sha,
            )
            sealed_audit = seal_audit(root / "failure-audits", audit)
            replayed_audit = seal_audit(root / "failure-audits", audit)
            failure_results[mode] = (
                manifest,
                replayed_manifest,
                run_root,
                sealed_audit,
                replayed_audit,
            )
        manifest, replayed_manifest, run_root, sealed_audit, replayed_audit = (
            failure_results["STANDARD_VIP"]
        )
        store = GateRegistryStore(root / "registry.sqlite3")
        service = GateRegistryService(store)

        prior = _identity(protocol)
        prior = GateIdentity(
            **{
                **prior.as_dict(),
                "protocol_scope_sha256": PROTOCOL_SCOPE_SHA256,
                "candidate_ids": prior.candidate_ids,
            }
        )
        service.import_case(
            prior,
            actor="M5_FIXTURE_BUILDER",
            idempotency_key="prior-import",
            recorded_at="2026-08-06T00:00:00+00:00",
        )
        service.advance(
            prior.case_id,
            "STOPPED",
            {"reason": "synthetic replay of prior immutable STOPPED case"},
            expected_event_seq=1,
            actor="M5_FIXTURE_BUILDER",
            idempotency_key="prior-stop",
            recorded_at="2026-08-06T00:00:01+00:00",
        )
        identity = _identity(protocol)
        service.import_case(
            identity,
            actor="M5_FIXTURE_BUILDER",
            idempotency_key="fixture-import",
            recorded_at="2026-08-06T00:01:00+00:00",
        )
        service.advance(
            identity.case_id,
            "PROTOCOL_FROZEN",
            {
                "protocol_scope_sha256": identity.protocol_scope_sha256,
                "protocol_sha256": identity.protocol_sha256,
            },
            expected_event_seq=1,
            actor="M5_FIXTURE_BUILDER",
            idempotency_key="fixture-protocol",
            recorded_at="2026-08-06T00:02:00+00:00",
        )
        service.advance(
            identity.case_id,
            "DATA_GATE_RELEASE_READY",
            {"release_scope_sha256": release_sha},
            expected_event_seq=2,
            actor="M5_FIXTURE_BUILDER",
            idempotency_key="fixture-release",
            recorded_at="2026-08-06T00:03:00+00:00",
        )
        service.advance(
            identity.case_id,
            "DATA_GATE_APPROVED",
            {
                "release_scope_sha256": release_sha,
                "decision": "APPROVE",
                "proposal_state": "REVIEW_REQUIRED",
                "proposal_event_seq": 2,
                "proposal_head_event_sha256": identity.proposal_head_event_sha256,
            },
            expected_event_seq=3,
            actor="M5_LOCAL_PROTOCOL_APPROVER",
            idempotency_key="fixture-approval",
            recorded_at="2026-08-06T00:04:00+00:00",
        )
        service.advance(
            identity.case_id,
            "DATA_GATE_STARTED",
            {"release_scope_sha256": release_sha},
            expected_event_seq=4,
            actor="M5_FIXTURE_RUNNER",
            idempotency_key="fixture-start",
            recorded_at="2026-08-06T00:05:00+00:00",
        )
        record_payload = {
            "verdict": manifest["verdict"],
            "eligible_candidate_ids": sealed_audit["eligible_candidate_ids"],
            "rejected_candidate_ids": sealed_audit["rejected_candidate_ids"],
            "candidate_matrix": sealed_audit["candidate_matrix"],
            "evidence_manifest_sha256": sha256_file(
                run_root / "run_manifest.json"
            ),
            "audit_manifest_sha256": sealed_audit["audit_report_sha256"],
            "audit_status": "PASS",
        }
        recorded = service.advance(
            identity.case_id,
            "DATA_GATE_RECORDED",
            record_payload,
            expected_event_seq=5,
            actor="M5_FIXTURE_REGISTRAR",
            idempotency_key="fixture-record",
            recorded_at="2026-08-06T00:06:00+00:00",
        )
        replayed_record = service.advance(
            identity.case_id,
            "DATA_GATE_RECORDED",
            record_payload,
            expected_event_seq=5,
            actor="M5_FIXTURE_REGISTRAR",
            idempotency_key="fixture-record",
            recorded_at="2026-08-06T00:06:00+00:00",
        )
        with store.read() as connection:
            verify_registry_integrity(connection)
            table_count = connection.execute(
                "SELECT count(*) FROM sqlite_schema WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            ).fetchone()[0]
            event_count = connection.execute("SELECT count(*) FROM gate_events").fetchone()[0]
        prior_state = service.get_case(prior.case_id)
        current_state = service.get_case(identity.case_id)
        return {
            "status": "PASS",
            "execution_kind": manifest["execution_kind"],
            "data_gate_verdict": manifest["verdict"],
            "independent_audit_status": sealed_audit["status"],
            "candidate_count": manifest["candidate_count"],
            "universe_count": manifest["universe_count"],
            "evaluation_unit_count": manifest["evaluation_unit_count"],
            "registry_table_count": table_count,
            "registry_event_count": event_count,
            "registry_state": current_state["lifecycle_state"],
            "prior_registry_state": prior_state["lifecycle_state"],
            "runner_idempotent": manifest == replayed_manifest,
            "auditor_idempotent": sealed_audit == replayed_audit,
            "registry_idempotent": recorded == replayed_record,
            "normal_fixture_verdict": normal_manifest["verdict"],
            "classification_fixture_pass": _classification_fixture(protocol),
            "sealed_conflict_mode_count": len(failure_results),
            "formal_registry_initialized": False,
            "real_financial_rows_read": False,
            "effect_test_count": 0,
            "production_authorization": "none",
        }


def main() -> int:
    result = run_fixture(Path.cwd())
    print(canonical_json(result))
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
