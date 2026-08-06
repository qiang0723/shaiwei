"""Independent physical and semantic audit for sealed M5 lineage evidence."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

import yaml

from .audit_lineage import audit_lineage
from .contract import M5GateError, canonical_json, sha256_file, sha256_json
from .lineage_contract import (
    CONTROL_PATHS,
    LineageInputManifest,
    LineageProtocol,
    Observation,
    VersionEvidence,
)
from .lineage_reader import load_lineage_inputs
from .lineage_release import LineageApprovalEnvelope, LineageReleaseScope


GO_VERDICT = "GO_M5_2_SOURCE_LINEAGE_RECOVERABLE"
NO_GO_VERDICT = "NO_GO_M5_2_SOURCE_LINEAGE_PREEXECUTION"


FORBIDDEN_KEYS = {
    "ts_code",
    "f_ann_date",
    "end_date",
    "report_type",
    "update_flag",
    "raw_value",
    "normalized_value",
    "candidate_value",
    "absolute_path",
    "request_params",
}


def _canonical_file(path: Path) -> dict[str, Any]:
    serialized = path.read_text(encoding="utf-8")
    value = json.loads(serialized)
    if not isinstance(value, dict) or serialized != canonical_json(value) + "\n":
        raise M5GateError("M5 lineage evidence is not a canonical object")
    return value


def _scan_forbidden(value: Any) -> None:
    if isinstance(value, dict):
        if forbidden := set(value) & FORBIDDEN_KEYS:
            raise M5GateError(f"M5 lineage evidence contains forbidden fields: {sorted(forbidden)}")
        for child in value.values():
            _scan_forbidden(child)
    elif isinstance(value, list):
        for child in value:
            _scan_forbidden(child)


def _expected_public_report(
    analysis: dict[str, Any],
    *,
    approved_identity: dict[str, str],
    semantic_rows_read: bool,
) -> dict[str, Any]:
    authority = {
        "row_level_export": False,
        "source_selection": False,
        "data_gate_execution": False,
        "pit_compute": False,
        "candidate_compute": False,
        "label_read": False,
        "effect_read": False,
        "model_training": False,
        "backtest": False,
        "provider_call_count": 0,
        "production_authorization": "none",
    }
    return {
        "schema_version": "m5-source-lineage-report-v1",
        "outcome_kind": "SOURCE_LINEAGE_FEASIBILITY",
        "approved_identity": approved_identity,
        **analysis,
        "semantic_rows_read": semantic_rows_read,
        "authority": authority,
    }


def audit_lineage_run(
    observations: list[Observation],
    evidence: list[VersionEvidence],
    *,
    as_of: str,
    run_root: Path,
    expected_protocol_scope_sha256: str,
    expected_input_manifest_sha256: str,
    expected_release_scope_sha256: str,
    expected_approval_event_sha256: str,
) -> dict[str, Any]:
    expected_files = {
        "source_lineage_report.json",
        "lineage_gate_report.json",
        "run_manifest.json",
    }
    if not run_root.is_dir() or {path.name for path in run_root.iterdir()} != expected_files:
        raise M5GateError("M5 lineage audit artifact set differs")
    lineage_path = run_root / "source_lineage_report.json"
    gate_path = run_root / "lineage_gate_report.json"
    manifest_path = run_root / "run_manifest.json"
    lineage = _canonical_file(lineage_path)
    gate = _canonical_file(gate_path)
    manifest = _canonical_file(manifest_path)
    _scan_forbidden(lineage)
    _scan_forbidden(gate)
    identity = {
        "protocol_scope_sha256": expected_protocol_scope_sha256,
        "input_manifest_sha256": expected_input_manifest_sha256,
        "release_scope_sha256": expected_release_scope_sha256,
        "approval_event_sha256": expected_approval_event_sha256,
    }
    for key, value in identity.items():
        if gate.get(key) != value or manifest.get(key) != value:
            raise M5GateError("M5 lineage approved identity differs")
    shared = {
        key: gate[key]
        for key in (
            "protocol_scope_sha256",
            "input_manifest_sha256",
            "release_scope_sha256",
            "code_bundle_sha256",
            "approval_event_sha256",
            "outcome_kind",
        )
    }
    if manifest.get("run_id") != sha256_json(shared):
        raise M5GateError("M5 lineage run identity differs")
    artifacts = manifest.get("artifacts") or {}
    if (
        set(artifacts) != {"source_lineage_report", "lineage_gate_report"}
        or artifacts["source_lineage_report"]
        != {"file": lineage_path.name, "sha256": sha256_file(lineage_path)}
        or artifacts["lineage_gate_report"] != {"file": gate_path.name, "sha256": sha256_file(gate_path)}
        or gate.get("source_lineage_report") != artifacts["source_lineage_report"]
    ):
        raise M5GateError("M5 lineage artifact physical hash differs")
    analysis = audit_lineage(observations, evidence, as_of=as_of)
    approved = {
        key: gate[key]
        for key in (
            "protocol_scope_sha256",
            "input_manifest_sha256",
            "release_scope_sha256",
            "code_bundle_sha256",
            "approval_event_sha256",
        )
    }
    expected_lineage = _expected_public_report(
        analysis,
        approved_identity=approved,
        semantic_rows_read=gate.get("semantic_rows_read") is True,
    )
    if lineage != expected_lineage:
        raise M5GateError("M5 lineage report differs from independent recomputation")
    expected_verdict = GO_VERDICT if analysis["historical_lineage_pass"] else NO_GO_VERDICT
    if (
        gate.get("lineage") != analysis
        or gate.get("verdict") != expected_verdict
        or manifest.get("verdict") != expected_verdict
        or manifest.get("runner_self_reported_only") is not True
        or manifest.get("independent_audit_status") != "NOT_RUN"
        or gate.get("feature_panel") != {"status": "FORBIDDEN_LINEAGE_GATE"}
        or gate.get("candidate_matrix") != {"status": "FORBIDDEN_LINEAGE_GATE"}
        or gate.get("label_read") is not False
        or gate.get("effect_read") is not False
        or gate.get("model_training_run") is not False
        or gate.get("backtest_run") is not False
        or gate.get("provider_call_count") != 0
        or gate.get("production_authorization") != "none"
    ):
        raise M5GateError("M5 lineage evidence claims an unauthorized result")
    return {
        "schema_version": "m5-source-lineage-independent-audit-v1",
        "status": "PASS",
        "run_id": manifest["run_id"],
        "run_manifest_sha256": sha256_file(manifest_path),
        "lineage_gate_report_sha256": sha256_file(gate_path),
        "source_lineage_report_physical_sha256": sha256_file(lineage_path),
        "source_lineage_report_canonical_sha256": sha256_json(lineage),
        "global_lineage_commitment_sha256": analysis["global_lineage_commitment_sha256"],
        "input_manifest_sha256": expected_input_manifest_sha256,
        "release_scope_sha256": expected_release_scope_sha256,
        "approval_event_sha256": expected_approval_event_sha256,
        "conflicting_identity_group_count": analysis["conflicting_identity_group_count"],
        "disposition_counts": analysis["disposition_counts"],
        "verdict": expected_verdict,
        "strategy_effective": "NOT_EVALUATED",
        "production_authorization": "none",
    }


def seal_lineage_audit(audit_root: Path, audit: dict[str, Any]) -> dict[str, Any]:
    target = audit_root / audit["run_id"] / "lineage_audit_report.json"
    payload = (canonical_json(audit) + "\n").encode("utf-8")
    if target.exists():
        if target.read_bytes() != payload:
            raise M5GateError("existing M5 lineage audit differs")
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(f".{target.name}.{os.getpid()}.tmp")
        with temporary.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    return {**audit, "audit_report_sha256": sha256_file(target)}


def audit_approved_lineage(
    *,
    input_root: Path,
    output_root: Path,
    audit_root: Path,
) -> dict[str, Any]:
    protocol = LineageProtocol.load(
        protocol_path=input_root / CONTROL_PATHS["protocol"],
        build_path=input_root / CONTROL_PATHS["build"],
        scope_path=input_root / CONTROL_PATHS["scope"],
        project_root=input_root,
    )
    manifest = LineageInputManifest.load(input_root / CONTROL_PATHS["manifest"])
    research = yaml.safe_load((input_root / CONTROL_PATHS["research"]).read_text(encoding="utf-8"))
    release = LineageReleaseScope.load(
        input_root / CONTROL_PATHS["release"],
        protocol,
        manifest,
        source_proposal=research["source_proposal"],
    )
    approval = LineageApprovalEnvelope.load(input_root / CONTROL_PATHS["approval"], release)
    observations, evidence, _ = load_lineage_inputs(manifest, input_root=input_root)
    run_id = sha256_json(
        {
            "protocol_scope_sha256": protocol.scope_document["protocol_scope_sha256"],
            "input_manifest_sha256": manifest.sha256,
            "release_scope_sha256": release.sha256,
            "code_bundle_sha256": release.scope["implementation"]["code_bundle_sha256"],
            "approval_event_sha256": approval.document["approval_event_sha256"],
            "outcome_kind": "SOURCE_LINEAGE_FEASIBILITY",
        }
    )
    audit = audit_lineage_run(
        observations,
        evidence,
        as_of=manifest.document["created_at"],
        run_root=output_root / run_id,
        expected_protocol_scope_sha256=protocol.scope_document["protocol_scope_sha256"],
        expected_input_manifest_sha256=manifest.sha256,
        expected_release_scope_sha256=release.sha256,
        expected_approval_event_sha256=approval.document["approval_event_sha256"],
    )
    return seal_lineage_audit(audit_root, audit)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", type=Path, default=Path("/lineage-input"))
    parser.add_argument("--output-root", type=Path, default=Path("/lineage-output"))
    parser.add_argument("--audit-root", type=Path, default=Path("/lineage-audit"))
    args = parser.parse_args(argv)
    try:
        result = audit_approved_lineage(
            input_root=args.input_root,
            output_root=args.output_root,
            audit_root=args.audit_root,
        )
    except (M5GateError, OSError, TypeError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(canonical_json({"status": "FAIL", "error_class": type(error).__name__, "message": str(error)}))
        return 2
    print(
        canonical_json(
            {
                "status": result["status"],
                "run_id": result["run_id"],
                "verdict": result["verdict"],
                "audit_report_sha256": result["audit_report_sha256"],
                "strategy_effective": "NOT_EVALUATED",
                "production_authorization": "none",
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
