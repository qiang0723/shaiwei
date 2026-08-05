from __future__ import annotations

import json
from pathlib import Path

import pytest

from shaiwei.research_gates.m5_dynamic.auditor import audit_run, seal_audit
from shaiwei.research_gates.m5_dynamic.contract import M5DataProtocol, M5GateError
from shaiwei.research_gates.m5_dynamic.fixture import synthetic_inputs
from shaiwei.research_gates.m5_dynamic.runner import build_gate_result, seal_run


ROOT = Path(__file__).parents[1]
INPUT_SHA = "1" * 64
RELEASE_SHA = "2" * 64
CODE_SHA = "3" * 64
APPROVAL_SHA = "4" * 64


def _protocol() -> M5DataProtocol:
    return M5DataProtocol.load(
        ROOT / "config/m5_dynamic_fundamental_cross_pool_v1.yaml",
        build_path=ROOT / "config/m5_dynamic_fundamental_data_gate_build_v1.yaml",
        project_root=ROOT,
    )


def _run(tmp_path: Path):
    protocol = _protocol()
    frames, memberships = synthetic_inputs(protocol)
    panel, report = build_gate_result(
        protocol,
        frames,
        memberships,
        input_manifest_sha256=INPUT_SHA,
        release_scope_sha256=RELEASE_SHA,
        code_bundle_sha256=CODE_SHA,
        approval_event_sha256=APPROVAL_SHA,
        semantic_rows_read=False,
    )
    manifest = seal_run(tmp_path / "runs", panel, report)
    return protocol, frames, memberships, manifest, tmp_path / "runs" / manifest["run_id"]


def test_synthetic_runner_is_write_once_and_byte_deterministic(tmp_path: Path) -> None:
    protocol, frames, memberships, first, run_root = _run(tmp_path)
    panel, report = build_gate_result(
        protocol,
        frames,
        memberships,
        input_manifest_sha256=INPUT_SHA,
        release_scope_sha256=RELEASE_SHA,
        code_bundle_sha256=CODE_SHA,
        approval_event_sha256=APPROVAL_SHA,
        semantic_rows_read=False,
    )
    second = seal_run(tmp_path / "runs", panel, report)
    other = seal_run(tmp_path / "other-runs", panel, report)

    assert first == second == other
    assert first["execution_kind"] == "SYNTHETIC_FIXTURE"
    assert first["candidate_count"] == 8
    assert first["universe_count"] == 3
    assert first["evaluation_unit_count"] == 24
    assert first["runner_self_reported_only"] is True
    assert first["independent_audit_status"] == "NOT_RUN"
    assert (run_root / "feature_panel.parquet").read_bytes() == (
        tmp_path / "other-runs" / first["run_id"] / "feature_panel.parquet"
    ).read_bytes()


def test_independent_auditor_rederives_panel_matrix_and_is_idempotent(tmp_path: Path) -> None:
    protocol, frames, memberships, manifest, run_root = _run(tmp_path)
    audit = audit_run(
        protocol,
        frames,
        memberships,
        run_root=run_root,
        expected_input_manifest_sha256=INPUT_SHA,
        expected_release_scope_sha256=RELEASE_SHA,
        expected_approval_event_sha256=APPROVAL_SHA,
    )
    first = seal_audit(tmp_path / "audits", audit)
    second = seal_audit(tmp_path / "audits", audit)

    assert first == second
    assert first["status"] == "PASS"
    assert first["run_id"] == manifest["run_id"]
    assert first["feature_panel_canonical_sha256"] == first[
        "independent_recomputed_panel_sha256"
    ]
    assert len(first["candidate_matrix"]) == 24
    assert first["strategy_effective"] == "NOT_EVALUATED"
    assert first["production_authorization"] == "none"


def test_auditor_rejects_runner_report_tampering(tmp_path: Path) -> None:
    protocol, frames, memberships, _, run_root = _run(tmp_path)
    report_path = run_root / "data_gate_report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["quality"]["candidate_matrix"][0]["status"] = "FAIL"
    report_path.write_text(json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n")

    with pytest.raises(M5GateError, match="physical hash"):
        audit_run(
            protocol,
            frames,
            memberships,
            run_root=run_root,
            expected_input_manifest_sha256=INPUT_SHA,
            expected_release_scope_sha256=RELEASE_SHA,
            expected_approval_event_sha256=APPROVAL_SHA,
        )


def test_auditor_source_has_no_runner_or_primary_compute_import() -> None:
    for relative in (
        "src/shaiwei/research_gates/m5_dynamic/auditor.py",
        "src/shaiwei/research_gates/m5_dynamic/audit_recompute.py",
        "src/shaiwei/research_gates/m5_dynamic/audit_quality.py",
    ):
        source = (ROOT / relative).read_text(encoding="utf-8")
        assert "from .runner" not in source
        assert "from .statements" not in source
        assert "from .features" not in source
        assert "from .matrix" not in source
