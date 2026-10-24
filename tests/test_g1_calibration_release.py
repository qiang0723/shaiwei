"""G1 正控第 4 步：精确 scope、逐字批准、一次性认领、正式执行与独立审计（合成数据，不碰真实账本）。"""

import json
from pathlib import Path

import pytest

from shaiwei.ledger import FACTOR_ADMISSIONS
from shaiwei.research.g1_calibration import audit as audit_module
from shaiwei.research.g1_calibration import execute as execute_module
from shaiwei.research.g1_calibration import runner
from shaiwei.research.g1_calibration.scope import (
    LedgerBaseline,
    ReleaseScope,
    ScopeEnvelope,
    ScopeError,
    approval_text,
    choose_noise_seeds,
    directory_fingerprint,
    ledger_baseline,
    load_approved,
    record_approval,
    scope_hash,
    verify_for_execution,
)
from tests.test_g1_calibration import _context, _reduced, _roots, baselines, protocol, research, settings  # noqa: F401

FACTS = {"code_snapshot": "c" * 64, "data_snapshot": "d" * 64, "qlib_fingerprint": "b" * 64}


def _scope(protocol, *,  # noqa: F811
            noise=2, evaluations=17, execution="g1cal-0123456789ab-20261025T000000Z", baseline=None) -> ReleaseScope:
    return ReleaseScope(
        schema_version="g1-calibration-release-scope-v1", protocol_id="g1-positive-control-v1",
        protocol_config_sha256=protocol.config_sha256, protocol_document_sha256=protocol.document_sha256,
        execution_id=execution, git_head="a" * 40, image="shaiwei:g1-calibration-cccccccccccc",
        image_id="sha256:" + "e" * 64, code_snapshot_sha256=FACTS["code_snapshot"], data_snapshot_sha256=FACTS["data_snapshot"],
        qlib_bin_sha256=FACTS["qlib_fingerprint"], noise_seeds_per_control=noise, evaluations=evaluations,
        budget_max_hours=12.0, pilot_timing_path="data/research/g1-calibration-v1/pilot/timing.json",
        pilot_timing_sha256="f" * 64, pilot_projected_hours=8.36,
        ledgers=LedgerBaseline.model_validate(baseline or {
            "experiments_rows": 0, "calibration_family_rows": 0, "calibration_runs_rows": 0,
            "factor_admissions_sha256": "0" * 64,
        }),
        prepared_at="2026-10-25T00:00:00+00:00",
    )


def _install(scope: ReleaseScope, control: Path) -> ScopeEnvelope:
    envelope = ScopeEnvelope(scope_sha256=scope_hash(scope), scope=scope)
    (control / "scopes").mkdir(parents=True, exist_ok=True)
    (control / "scopes" / f"{envelope.scope_sha256}.scope.json").write_text(envelope.model_dump_json(), encoding="utf-8")
    return envelope


def test_approval_is_only_a_verbatim_transcript(tmp_path, protocol):  # noqa: F811
    envelope = _install(_scope(protocol), tmp_path)
    text = approval_text(envelope)
    assert envelope.scope_sha256 in text and "shaiwei:g1-calibration-cccccccccccc" in text and "N1/N2 各 2 种子" in text
    with pytest.raises(ScopeError, match="verbatim"):
        record_approval(envelope.scope_sha256, text + " ", tmp_path)
    with pytest.raises(FileNotFoundError):
        load_approved(envelope.scope_sha256, tmp_path)
    assert record_approval(envelope.scope_sha256, text, tmp_path)["status"] == "APPROVAL_RECORDED"
    with pytest.raises(ScopeError, match="already recorded"):
        record_approval(envelope.scope_sha256, text, tmp_path)
    assert load_approved(envelope.scope_sha256, tmp_path) == envelope
    path = tmp_path / "scopes" / f"{envelope.scope_sha256}.scope.json"
    path.write_text(path.read_text(encoding="utf-8").replace('"noise_seeds_per_control":2', '"noise_seeds_per_control":1'), encoding="utf-8")
    with pytest.raises(ScopeError, match="hash"):
        load_approved(envelope.scope_sha256, tmp_path)


def test_noise_budget_follows_the_frozen_reduction_order(protocol):  # noqa: F811
    projections = lambda h30, h20, h10: {"30": {"projected_hours": h30}, "20": {"projected_hours": h20}, "10": {"projected_hours": h10}}  # noqa: E731
    assert choose_noise_seeds(protocol, projections(8.36, 6.6, 4.9)) == 30
    assert choose_noise_seeds(protocol, projections(13, 11, 6)) == 20
    assert choose_noise_seeds(protocol, projections(20, 15, 11.9)) == 10
    with pytest.raises(ScopeError, match="new protocol"):
        choose_noise_seeds(protocol, projections(30, 20, 13))


def test_execution_preconditions_reject_every_drift(tmp_path, protocol):  # noqa: F811
    envelope = ScopeEnvelope(scope_sha256="a" * 64, scope=_scope(protocol))
    baseline = {"experiments_rows": 5, "calibration_family_rows": 0, "calibration_runs_rows": 0, "factor_admissions_sha256": "0" * 64}
    good = dict(code_snapshot=FACTS["code_snapshot"], data_snapshot=FACTS["data_snapshot"], qlib_fingerprint=FACTS["qlib_fingerprint"])
    verify_for_execution(envelope, protocol, baseline=baseline, **good)
    for key in good:
        with pytest.raises(ScopeError, match="drifted"):
            verify_for_execution(envelope, protocol, baseline=baseline, **{**good, key: "9" * 64})
    for key, value in (("calibration_family_rows", 1), ("calibration_runs_rows", 1), ("factor_admissions_sha256", "1" * 64)):
        with pytest.raises(ScopeError, match="drifted"):
            verify_for_execution(envelope, protocol, baseline={**baseline, key: value}, **good)
    (tmp_path / "bin").mkdir()
    (tmp_path / "bin" / "a.bin").write_bytes(b"1")
    before = directory_fingerprint(tmp_path / "bin")
    (tmp_path / "bin" / "a.bin").write_bytes(b"2")
    assert directory_fingerprint(tmp_path / "bin") != before


@pytest.fixture(scope="module")
def executed(tmp_path_factory, monkeypatch_module, settings, protocol, research, baselines):  # noqa: F811
    """一次正式执行（缩小规模）+ 独立审计共用的落盘结果。"""
    tmp_path = tmp_path_factory.mktemp("g1-release")
    monkeypatch_module.setattr(runner, "_max_library_correlation", lambda *_args: 0.0)
    reduced = _reduced(protocol)
    execution = "g1cal-0123456789ab-20261025T000000Z"
    roots = _roots(settings, tmp_path, execution)
    admissions = tmp_path / "factor_admissions.csv"
    admissions.write_bytes(FACTOR_ADMISSIONS.read_bytes())
    baseline = ledger_baseline(reduced, experiments=roots.experiments, runs=roots.runs, admissions=admissions)
    control = tmp_path / "control"
    envelope = _install(_scope(reduced, baseline=baseline), control)
    record_approval(envelope.scope_sha256, approval_text(envelope), control)
    monkeypatch_module.setattr(execute_module, "load_protocol", lambda _settings: reduced)
    kwargs = dict(
        settings=settings, control_root=control, roots=roots, facts=lambda _settings: FACTS, admissions=admissions,
        context_loader=lambda s, p, timings: _context(s, p, research, baselines),
    )
    result = execute_module.execute(envelope.scope_sha256, **kwargs)
    return {"result": result, "roots": roots, "control": control, "reduced": reduced, "admissions": admissions,
            "envelope": envelope, "execution": execution, "kwargs": kwargs}


@pytest.fixture(scope="module")
def monkeypatch_module():
    patcher = pytest.MonkeyPatch()
    yield patcher
    patcher.undo()


def test_execution_runs_once_and_refuses_any_rerun(executed):
    roots = executed["roots"]
    assert executed["result"]["status"] == "COMPLETE"
    assert json.loads((roots.data / "claim.json").read_text(encoding="utf-8"))["state"] == "MAY_HAVE_WRITTEN"
    assert json.loads((roots.reports / "execution.json").read_text(encoding="utf-8"))["scope_sha256"] == executed["envelope"].scope_sha256
    with pytest.raises(ScopeError):
        execute_module.execute(executed["envelope"].scope_sha256, **executed["kwargs"])
    (roots.data / "claim.json").unlink()
    with pytest.raises(ScopeError, match="drifted"):  # 认领被删也无法重跑：标定家族行已非零
        execute_module.execute(executed["envelope"].scope_sha256, **executed["kwargs"])
    (roots.data / "claim.json").write_text(json.dumps({"scope_sha256": executed["envelope"].scope_sha256, "state": "MAY_HAVE_WRITTEN"}), encoding="utf-8")


def _audit(executed, settings, **overrides):  # noqa: F811
    roots = executed["roots"]
    kwargs = dict(
        settings=settings, protocol=executed["reduced"], data_dir=roots.data, reports_dir=roots.reports,
        control_root=executed["control"], experiments=roots.experiments, runs=roots.runs, admissions=executed["admissions"],
    )
    return audit_module.audit(executed["execution"], **{**kwargs, **overrides})


def test_independent_audit_recomputes_everything_and_catches_tampering(executed, settings, tmp_path):  # noqa: F811
    clean = _audit(executed, settings)
    assert clean["status"] == "PASS", clean["findings"]
    assert clean["units_audited"] == 17 and clean["recomputed_terminal_state"] == executed["result"]["terminal_state"]
    tampered_admissions = tmp_path / "admissions.csv"
    tampered_admissions.write_bytes(executed["admissions"].read_bytes() + b"x\n")
    assert "factor_admissions unchanged mismatch" in _audit(executed, settings, admissions=tampered_admissions)["findings"]
    report = next((executed["roots"].reports / "N1").glob("*.json"))
    original = report.read_bytes()
    try:
        report.write_bytes(original + b" ")
        findings = _audit(executed, settings)["findings"]
        assert any("report hash differs" in item for item in findings)
    finally:
        report.write_bytes(original)
    assert _audit(executed, settings)["status"] == "PASS"
