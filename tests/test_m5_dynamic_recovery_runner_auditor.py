from __future__ import annotations

import json
from pathlib import Path

import pytest

from shaiwei.research_gates.m5_dynamic.auditor import audit_run, seal_audit
from shaiwei.research_gates.m5_dynamic.contract import (
    M5DataProtocol,
    M5GateError,
    canonical_json,
    sha256_file,
)
from shaiwei.research_gates.m5_dynamic.failure_projection import (
    build_global_failure_reports,
)
from shaiwei.research_gates.m5_dynamic.fixture import synthetic_inputs
from shaiwei.research_gates.m5_dynamic.runner import seal_global_failure
from shaiwei.research_gates.m5_dynamic.source_conflicts import (
    assess_all_statement_sources,
)


ROOT = Path(__file__).parents[1]
INPUT_SHA = "1" * 64
RELEASE_SHA = "2" * 64
CODE_SHA = "3" * 64
APPROVAL_SHA = "4" * 64


def _protocol() -> M5DataProtocol:
    return M5DataProtocol.load(
        ROOT / "config/m5_dynamic_fundamental_cross_pool_v1.yaml",
        build_path=ROOT / "config/m5_dynamic_fundamental_data_gate_build_v2.yaml",
        project_root=ROOT,
    )


def _conflicting_inputs(protocol: M5DataProtocol):
    frames, memberships = synthetic_inputs(protocol)
    vip = frames["tushare.balancesheet_vip"].copy()
    vip.loc[0, "total_assets"] = float(vip.loc[0, "total_assets"]) + 1
    frames["tushare.balancesheet_vip"] = vip
    return frames, memberships


def _run(tmp_path: Path):
    protocol = _protocol()
    frames, memberships = _conflicting_inputs(protocol)
    assessment = assess_all_statement_sources(frames)
    conflict, report = build_global_failure_reports(
        protocol,
        assessment,
        input_manifest_sha256=INPUT_SHA,
        release_scope_sha256=RELEASE_SHA,
        code_bundle_sha256=CODE_SHA,
        approval_event_sha256=APPROVAL_SHA,
        source_evidence={"sources": {}, "memberships": {}},
        semantic_rows_read=False,
    )
    manifest = seal_global_failure(tmp_path / "runs", conflict, report)
    return (
        protocol,
        frames,
        memberships,
        conflict,
        report,
        manifest,
        tmp_path / "runs" / manifest["run_id"],
    )


def _audit(protocol, frames, memberships, run_root: Path):
    return audit_run(
        protocol,
        frames,
        memberships,
        run_root=run_root,
        expected_input_manifest_sha256=INPUT_SHA,
        expected_release_scope_sha256=RELEASE_SHA,
        expected_approval_event_sha256=APPROVAL_SHA,
    )


def _write_canonical(path: Path, value: dict) -> None:
    path.write_text(canonical_json(value) + "\n", encoding="utf-8")


def test_global_failure_is_write_once_deterministic_and_independently_audited(
    tmp_path: Path,
) -> None:
    protocol, frames, memberships, conflict, report, first, run_root = _run(tmp_path)
    second = seal_global_failure(tmp_path / "runs", conflict, report)
    other = seal_global_failure(tmp_path / "other", conflict, report)
    audit = _audit(protocol, frames, memberships, run_root)
    sealed_audit = seal_audit(tmp_path / "audits", audit)

    assert first == second == other
    assert first["outcome_kind"] == "GLOBAL_DATA_FAILURE"
    assert first["verdict"] == "NO_GO_M5_2_DATA_PREEXECUTION"
    assert {path.name for path in run_root.iterdir()} == {
        "source_conflict_report.json",
        "data_gate_report.json",
        "run_manifest.json",
    }
    assert sealed_audit["status"] == "PASS"
    assert len(sealed_audit["candidate_matrix"]) == 24
    for filename in sorted(path.name for path in run_root.iterdir()):
        assert (run_root / filename).read_bytes() == (
            tmp_path / "other" / first["run_id"] / filename
        ).read_bytes()


def test_global_failure_partial_directory_fails_closed(tmp_path: Path) -> None:
    protocol = _protocol()
    frames, _ = _conflicting_inputs(protocol)
    conflict, report = build_global_failure_reports(
        protocol,
        assess_all_statement_sources(frames),
        input_manifest_sha256=INPUT_SHA,
        release_scope_sha256=RELEASE_SHA,
        code_bundle_sha256=CODE_SHA,
        approval_event_sha256=APPROVAL_SHA,
        source_evidence={},
        semantic_rows_read=False,
    )
    identity = {
        "protocol_sha256": protocol.sha256,
        "input_manifest_sha256": INPUT_SHA,
        "release_scope_sha256": RELEASE_SHA,
        "code_bundle_sha256": CODE_SHA,
        "approval_event_sha256": APPROVAL_SHA,
        "protocol_scope_sha256": protocol.protocol_scope_sha256,
        "outcome_kind": "GLOBAL_DATA_FAILURE",
    }
    from shaiwei.research_gates.m5_dynamic.contract import sha256_json

    partial = tmp_path / "runs" / sha256_json(identity)
    partial.mkdir(parents=True)
    (partial / "run_manifest.json").touch()
    with pytest.raises((M5GateError, json.JSONDecodeError)):
        seal_global_failure(tmp_path / "runs", conflict, report)


def test_global_failure_conflict_hash_tamper_is_rejected(tmp_path: Path) -> None:
    protocol, frames, memberships, _, _, _, run_root = _run(tmp_path)
    conflict_path = run_root / "source_conflict_report.json"
    conflict = json.loads(conflict_path.read_text(encoding="utf-8"))
    conflict["global_conflict_set_sha256"] = "f" * 64
    _write_canonical(conflict_path, conflict)

    with pytest.raises(M5GateError, match="physical hash"):
        _audit(protocol, frames, memberships, run_root)


def test_global_failure_forbidden_field_injection_is_rejected(tmp_path: Path) -> None:
    protocol, frames, memberships, _, _, _, run_root = _run(tmp_path)
    conflict_path = run_root / "source_conflict_report.json"
    report_path = run_root / "data_gate_report.json"
    manifest_path = run_root / "run_manifest.json"
    conflict = json.loads(conflict_path.read_text(encoding="utf-8"))
    conflict["raw_value"] = "redacted-but-still-forbidden"
    _write_canonical(conflict_path, conflict)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["source_conflict_report"]["sha256"] = sha256_file(conflict_path)
    _write_canonical(report_path, report)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["artifacts"]["source_conflict_report"]["sha256"] = sha256_file(
        conflict_path
    )
    manifest["artifacts"]["data_gate_report"]["sha256"] = sha256_file(report_path)
    _write_canonical(manifest_path, manifest)

    with pytest.raises(M5GateError, match="forbidden fields"):
        _audit(protocol, frames, memberships, run_root)


def test_global_failure_matrix_tamper_is_rejected(tmp_path: Path) -> None:
    protocol, frames, memberships, _, _, _, run_root = _run(tmp_path)
    report_path = run_root / "data_gate_report.json"
    manifest_path = run_root / "run_manifest.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["quality"]["candidate_matrix"][0]["status"] = "PASS"
    _write_canonical(report_path, report)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["artifacts"]["data_gate_report"]["sha256"] = sha256_file(report_path)
    _write_canonical(manifest_path, manifest)

    with pytest.raises(M5GateError, match="matrix differs"):
        _audit(protocol, frames, memberships, run_root)


def test_recovery_auditor_does_not_import_primary_conflict_or_projection() -> None:
    for relative in (
        "src/shaiwei/research_gates/m5_dynamic/auditor.py",
        "src/shaiwei/research_gates/m5_dynamic/audit_global_failure.py",
        "src/shaiwei/research_gates/m5_dynamic/audit_source_conflicts.py",
        "src/shaiwei/research_gates/m5_dynamic/audit_failure_projection.py",
    ):
        source = (ROOT / relative).read_text(encoding="utf-8")
        for forbidden in (
            "from .runner",
            "from .source_conflicts",
            "from .failure_projection",
            "from .statements",
            "from .features",
            "from .matrix",
        ):
            assert forbidden not in source
