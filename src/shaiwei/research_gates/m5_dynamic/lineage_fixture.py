"""Offline adversarial fixture for the M5 source-lineage recovery gate."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import yaml

from shaiwei.research_gates.gate_registry import GateIdentity, GateRegistryService, GateRegistryStore
from shaiwei.research_gates.gate_registry.integrity import verify_registry_integrity

from .contract import M5GateError, canonical_json, sha256_json
from .lineage import assess_lineage
from .lineage_auditor import audit_lineage_run, seal_lineage_audit
from .lineage_commitment import value_version_sha256
from .lineage_contract import CASE_ID, PROTOCOL_SCOPE_SHA256, Observation, VersionEvidence
from .lineage_projection import build_lineage_reports
from .lineage_sealing import seal_lineage_run


AS_OF = "2026-08-06T04:00:00+00:00"
INPUT_SHA, RELEASE_SHA, CODE_SHA, APPROVAL_SHA = (char * 64 for char in "1234")


def _identity_fields() -> dict[str, str]:
    return {
        "ts_code": "990001.SH",
        "f_ann_date": "20260131",
        "end_date": "20251231",
        "report_type": "1",
        "update_flag": "1",
    }


def _observation(value: int, *, batch: str, observed_at: str, vip: bool = False) -> Observation:
    return Observation.from_mapping(
        {
            "table": "balancesheet",
            "source_kind": "VIP" if vip else "STANDARD",
            "source_api": "tushare.balancesheet_vip" if vip else "tushare.balancesheet",
            "statement_identity": _identity_fields(),
            "business_values": {
                "accounts_receiv": 1,
                "inventories": 2,
                "total_assets": value,
                "total_liab": 4,
                "total_cur_assets": 5,
                "total_cur_liab": 3,
            },
            "request_params_sha256": "a" * 64,
            "batch_id": batch,
            "content_sha256": sha256_json(batch),
            "local_observed_at": observed_at,
        }
    )


def _evidence(
    item: Observation,
    *,
    version: str,
    effective_at: str,
    predecessor: str | None,
) -> VersionEvidence:
    return VersionEvidence.from_mapping(
        {
            "table": item.table,
            "statement_identity": _identity_fields(),
            "provider_version_id_sha256": sha256_json(version),
            "value_version_sha256": value_version_sha256(item),
            "predecessor_provider_version_id_sha256": (
                None if predecessor is None else sha256_json(predecessor)
            ),
            "evidence_tier": "E2_PROVIDER_DECLARED_VERSION",
            "provider_revision_effective_at": effective_at,
            "evidence_content_sha256": sha256_json(f"content:{version}"),
            "evidence_locator_sha256": sha256_json(f"locator:{version}"),
        }
    )


def _versions() -> tuple[Observation, Observation]:
    return (
        _observation(100, batch="old", observed_at="2026-02-01T01:00:00+00:00"),
        _observation(101, batch="new", observed_at="2026-03-01T01:00:00+00:00", vip=True),
    )


def _resolved() -> tuple[list[Observation], list[VersionEvidence]]:
    old, new = _versions()
    return [old, new], [
        _evidence(old, version="v1", effective_at="2026-01-31T08:00:00+00:00", predecessor=None),
        _evidence(new, version="v2", effective_at="2026-02-28T08:00:00+00:00", predecessor="v1"),
    ]


def _seal_and_audit(
    root: Path,
    observations: list[Observation],
    evidence: list[VersionEvidence],
) -> tuple[dict[str, object], Path]:
    assessment = assess_lineage(observations, evidence, as_of=AS_OF)
    lineage, gate = build_lineage_reports(
        assessment,
        protocol_scope_sha256=PROTOCOL_SCOPE_SHA256,
        input_manifest_sha256=INPUT_SHA,
        release_scope_sha256=RELEASE_SHA,
        code_bundle_sha256=CODE_SHA,
        approval_event_sha256=APPROVAL_SHA,
        semantic_rows_read=False,
    )
    first = seal_lineage_run(root / "runs", lineage, gate)
    second = seal_lineage_run(root / "runs", lineage, gate)
    if first != second:
        raise M5GateError("M5 lineage fixture is not byte deterministic")
    run_root = root / "runs" / str(first["run_id"])
    audit = audit_lineage_run(
        observations,
        evidence,
        as_of=AS_OF,
        run_root=run_root,
        expected_protocol_scope_sha256=PROTOCOL_SCOPE_SHA256,
        expected_input_manifest_sha256=INPUT_SHA,
        expected_release_scope_sha256=RELEASE_SHA,
        expected_approval_event_sha256=APPROVAL_SHA,
    )
    seal_lineage_audit(root / "audits", audit)
    return first, run_root


def _identity(project_root: Path) -> GateIdentity:
    research = yaml.safe_load(
        (project_root / "config/m5_dynamic_fundamental_cross_pool_v1.yaml").read_text(encoding="utf-8")
    )
    proposal = research["source_proposal"]
    identity = GateIdentity(
        proposal_id=proposal["proposal_id"],
        proposal_request_sha256=proposal["proposal_request_sha256"],
        canonical_proposal_sha256=proposal["canonical_proposal_sha256"],
        proposal_head_event_sha256=proposal["required_head_event_sha256"],
        proposal_export_sha256=proposal["proposal_export_sha256"],
        protocol_scope_sha256=PROTOCOL_SCOPE_SHA256,
        protocol_sha256=("badfac341ae1ecd65536a809789c1e1f7f4ad7c0e1b42d6faa6f60dc0adb6673"),
        proposal_expires_at=proposal["expires_at"],
        candidate_ids=tuple(item["candidate_id"] for item in research["candidates"]),
    )
    if identity.case_id != CASE_ID:
        raise M5GateError("M5 lineage fixture case identity differs")
    return identity


def _registry(root: Path, project_root: Path, manifest: dict[str, object]) -> None:
    identity = _identity(project_root)
    service = GateRegistryService(GateRegistryStore(root / "registry.sqlite3"))
    actor = "M5_LOCAL_PROTOCOL_APPROVER"
    service.import_case(
        identity,
        actor=actor,
        idempotency_key="lineage-import",
        recorded_at="2026-08-06T03:00:00+00:00",
    )
    events = [
        (
            "PROTOCOL_FROZEN",
            {"protocol_scope_sha256": PROTOCOL_SCOPE_SHA256, "protocol_sha256": identity.protocol_sha256},
        ),
        ("LINEAGE_GATE_RELEASE_READY", {"release_scope_sha256": RELEASE_SHA}),
        (
            "LINEAGE_GATE_APPROVED",
            {
                "release_scope_sha256": RELEASE_SHA,
                "decision": "APPROVE",
                "proposal_state": "REVIEW_REQUIRED",
                "proposal_event_seq": 2,
                "proposal_head_event_sha256": identity.proposal_head_event_sha256,
            },
        ),
        ("LINEAGE_GATE_STARTED", {"release_scope_sha256": RELEASE_SHA}),
        (
            "LINEAGE_GATE_RECORDED",
            {
                "verdict": manifest["verdict"],
                "identity_group_count": 1,
                "conflicting_identity_group_count": 1,
                "resolved_conflicting_group_count": 1,
                "blocked_conflicting_group_count": 0,
                "disposition_counts": {
                    "LOSSLESS_EXACT_DUPLICATE": 0,
                    "PIT_VERSION_CHAIN_RESOLVED": 1,
                    "FORWARD_ONLY_OBSERVED_VERSION": 0,
                    "UNRESOLVED_MISSING_EFFECTIVE_TIME": 0,
                    "UNRESOLVED_AMBIGUOUS_ORDER": 0,
                    "UNRESOLVED_INCOMPLETE_CHAIN": 0,
                },
                "evidence_manifest_sha256": sha256_json(manifest),
                "audit_manifest_sha256": "9" * 64,
                "audit_status": "PASS",
            },
        ),
    ]
    for seq, (event, payload) in enumerate(events, start=1):
        service.advance(
            identity.case_id,
            event,
            payload,
            expected_event_seq=seq,
            actor=actor,
            idempotency_key=f"lineage-{seq}",
            recorded_at=f"2026-08-06T03:0{seq}:00+00:00",
        )
    with service.store.read() as connection:
        verify_registry_integrity(connection)


def run_fixture(project_root: Path) -> dict[str, object]:
    old, new = _versions()
    rollback = _observation(
        100,
        batch="rollback",
        observed_at="2026-03-02T01:00:00+00:00",
        vip=True,
    )
    resolved_observations, resolved_evidence = _resolved()
    cases = {
        "exact_duplicate": assess_lineage(
            [old, _observation(100, batch="copy", observed_at="2026-02-02T01:00:00+00:00")],
            [],
            as_of=AS_OF,
        )
        .groups[0]
        .disposition,
        "local_observation_only": assess_lineage([old, new], [], as_of=AS_OF).groups[0].disposition,
        "same_update_flag_different_values": assess_lineage([old, new], [], as_of=AS_OF)
        .groups[0]
        .disposition,
        "unique_authoritative_times": assess_lineage(resolved_observations, resolved_evidence, as_of=AS_OF)
        .groups[0]
        .disposition,
        "simultaneous_versions": assess_lineage(
            [old, new],
            [
                resolved_evidence[0],
                _evidence(new, version="v2", effective_at="2026-01-31T08:00:00+00:00", predecessor="v1"),
            ],
            as_of=AS_OF,
        )
        .groups[0]
        .disposition,
        "missing_middle": assess_lineage(
            [old, new],
            [
                resolved_evidence[0],
                _evidence(new, version="v3", effective_at="2026-02-28T08:00:00+00:00", predecessor="v2"),
            ],
            as_of=AS_OF,
        )
        .groups[0]
        .disposition,
        "future_version": assess_lineage(
            [old, new],
            [
                resolved_evidence[0],
                _evidence(new, version="v2", effective_at="2026-09-01T08:00:00+00:00", predecessor="v1"),
            ],
            as_of=AS_OF,
        )
        .groups[0]
        .disposition,
        "unexplained_rollback": assess_lineage([old, new, rollback], resolved_evidence, as_of=AS_OF)
        .groups[0]
        .disposition,
    }
    expected = {
        "exact_duplicate": "LOSSLESS_EXACT_DUPLICATE",
        "local_observation_only": "FORWARD_ONLY_OBSERVED_VERSION",
        "same_update_flag_different_values": "FORWARD_ONLY_OBSERVED_VERSION",
        "unique_authoritative_times": "PIT_VERSION_CHAIN_RESOLVED",
        "simultaneous_versions": "UNRESOLVED_AMBIGUOUS_ORDER",
        "missing_middle": "UNRESOLVED_INCOMPLETE_CHAIN",
        "future_version": "UNRESOLVED_MISSING_EFFECTIVE_TIME",
        "unexplained_rollback": "UNRESOLVED_INCOMPLETE_CHAIN",
    }
    if cases != expected:
        raise M5GateError("M5 lineage fixture disposition matrix differs")
    with tempfile.TemporaryDirectory(prefix="m5-lineage-fixture-") as temporary:
        root = Path(temporary)
        manifest, run_root = _seal_and_audit(root, resolved_observations, resolved_evidence)
        _registry(root, project_root, manifest)
        tampered = json.loads((run_root / "source_lineage_report.json").read_text(encoding="utf-8"))
        tampered["ts_code"] = "forbidden"
        (run_root / "source_lineage_report.json").write_text(
            canonical_json(tampered) + "\n", encoding="utf-8"
        )
        try:
            audit_lineage_run(
                resolved_observations,
                resolved_evidence,
                as_of=AS_OF,
                run_root=run_root,
                expected_protocol_scope_sha256=PROTOCOL_SCOPE_SHA256,
                expected_input_manifest_sha256=INPUT_SHA,
                expected_release_scope_sha256=RELEASE_SHA,
                expected_approval_event_sha256=APPROVAL_SHA,
            )
        except M5GateError:
            tamper_rejected = True
        else:
            tamper_rejected = False
    if not tamper_rejected:
        raise M5GateError("M5 lineage fixture accepted forbidden report tampering")
    return {
        "schema_version": "m5-source-lineage-fixture-v1",
        "status": "PASS",
        "case_count": len(cases),
        "cases": cases,
        "deterministic_double_run": True,
        "independent_audit_pass": True,
        "forbidden_field_tamper_rejected": True,
        "registry_replay_pass": True,
        "semantic_rows_read": False,
        "external_call_count": 0,
        "strategy_effective": "NOT_EVALUATED",
        "production_authorization": "none",
    }


def main() -> int:
    try:
        result = run_fixture(Path.cwd())
    except (M5GateError, OSError, TypeError, ValueError, KeyError) as error:
        print(canonical_json({"status": "FAIL", "error_class": type(error).__name__, "message": str(error)}))
        return 2
    print(canonical_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
