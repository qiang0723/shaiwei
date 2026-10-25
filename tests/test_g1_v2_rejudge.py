"""g1-v2-rejudge-v2 工程的合成测试：不读真实研究数据、不写真实账本（协议 v2 §5 第 2 步）。"""

import csv
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml
from pydantic import ValidationError

from shaiwei.config import PROJECT_ROOT
from shaiwei.ledger import EXPERIMENTS, FACTOR_ADMISSIONS, append_experiment
from shaiwei.research.g1_calibration import controls
from shaiwei.research.g1_v2_rejudge import audit as audit_module
from shaiwei.research.g1_v2_rejudge import evaluate, release
from shaiwei.research.g1_v2_rejudge.judge import RejudgeIsolationError, rejudge_roots
from shaiwei.research.g1_v2_rejudge.protocol import CONFIG_PATH, FACTOR_ADMISSIONS_V2, FAMILIES, RejudgeProtocolError, Target, load_rejudge_protocol
from shaiwei.research.g1_v2_rejudge.sources import Reconstruction, compare_series, rebuild_gp
from tests.test_g1_calibration import _fake_backtest, _series, baselines, research, settings  # noqa: F401

GP, P1, F1, F2 = FAMILIES
FACTS = {"code_snapshot": "c" * 64, "data_snapshot": "d" * 64, "qlib_fingerprint": "b" * 64}
EXECUTION = "g1rj-0123456789ab-20261025T120000Z"
V1_ROWS = {GP: 3, P1: 2, F1: 2, F2: 1}  # 合成的历史家族尝试数：判定时 N = 历史 + 本次写入


@pytest.fixture(scope="module")
def identity(settings):  # noqa: F811
    return load_rejudge_protocol(settings, verify_artifacts=False)


def _tampered(tmp_path: Path, settings, change):  # noqa: F811
    document = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    change(document)
    path = tmp_path / "rejudge.yaml"
    path.write_text(yaml.safe_dump(document, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return load_rejudge_protocol(settings, path, verify_artifacts=False)


def test_protocol_binds_the_frozen_21_units_and_refuses_drift(settings, identity, tmp_path):  # noqa: F811
    config = identity.config
    assert config.family_order == FAMILIES and len(config.candidates()) == 21
    assert {family: len(config.families[family]) for family in FAMILIES} == {GP: 4, P1: 6, F1: 6, F2: 5}
    assert set(config.multiple_testing_families[F2]) == {F1, F2}
    assert all(config.multiple_testing_families[family] == (family,) for family in (GP, P1, F1))
    assert sum(len(c.supersedes) for _, c in config.candidates()) == 8
    gp_rationale = [c.rationale_chars for c in config.families[GP]]
    assert all(chars < 20 for chars in gp_rationale)  # 占位理由：第②项必然 REJECT（协议 D2）

    def repeat_formula(document):
        document["families"][F1][1]["formula"] = document["families"][F1][0]["formula"]

    def drop_unit(document):
        document["families"][P1].pop()

    def supersede_a_unit(document):
        units = document["families"][GP]
        holder = next(unit for unit in units if unit.get("supersedes"))
        holder["supersedes"][0]["candidate_experiment_id"] = units[0]["candidate_experiment_id"]

    def spec_drift(document):
        document["judge"]["spec_config_sha256"] = "0" * 64

    for change, message in ((repeat_formula, "repeats"), (drop_unit, "unit counts"), (supersede_a_unit, "superseded"), (spec_drift, "spec sha256")):
        with pytest.raises(RejudgeProtocolError, match=message):
            _tampered(tmp_path, settings, change)
    with pytest.raises(ValidationError):
        _tampered(tmp_path, settings, lambda document: document.update(extra_field=1))
    with pytest.raises(ValidationError):
        _tampered(tmp_path, settings, lambda document: document["reproduction_gate"].update(max_abs_daily_difference=1e-4))


def test_reproduction_gate_needs_identical_keys_within_tolerance():
    index = pd.date_range("2020-01-01", periods=5)
    stored = pd.Series([0.1, 0.2, 0.3, 0.4, 0.5], index=index)
    assert compare_series(stored + 5e-7, stored, tolerance=1e-6)["status"] == "PASS"
    assert compare_series(stored + 2e-6, stored, tolerance=1e-6)["status"] == "FAIL"
    missing = compare_series(stored.iloc[1:], stored, tolerance=1e-6)
    assert missing["status"] == "FAIL" and missing["missing_keys"] == 1
    extra = compare_series(pd.concat([stored, pd.Series([0.6], index=[pd.Timestamp("2020-02-01")])]), stored, tolerance=1e-6)
    assert extra["status"] == "FAIL" and extra["extra_keys"] == 1


def _v1_files(tmp_path: Path, rationale: str = "x" * 15) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    tests = tmp_path / "v1_tests.json"
    tests.write_text(json.dumps({"pit_sentinel_pass": True, "shift_sentinel_pass": True}), encoding="utf-8")
    evidence = tmp_path / "v1_evidence.json"
    evidence.write_text(json.dumps({
        "economic_rationale": rationale, "complexity": {"expression_tokens": 11, "ast_nodes": 9},
        "integrity": {"test_report_path": str(tests)}, "rank_ic": {"in_sample": 0.01}, "multiple_testing_families": [],
    }), encoding="utf-8")
    return evidence


def test_gp_rebuild_must_reproduce_the_v1_residual_panel(identity, research, tmp_path):  # noqa: F811
    raw = _series(31)
    residual, _ = controls.neutralize(raw, research, min_cross_section=30)
    panel = tmp_path / "factor_panel.parquet"
    residual.rename("factor").reset_index().to_parquet(panel, index=False)
    candidate = identity.config.families[GP][0].model_copy(update={
        "v1_evidence_path": str(_v1_files(tmp_path)), "reproduction_target": Target(kind="factor_panel", path=str(panel), sha256="0" * 64),
    })
    expression = lambda text, _stock_data: raw.copy() if text == candidate.formula else None  # noqa: E731
    item = rebuild_gp(candidate, research, min_cross_section=30, tolerance=1e-6, expression_values=expression)
    assert item.reproduced and item.reproduction["max_abs_difference"] <= 1e-6 and item.raw.equals(raw)
    assert item.v1["economic_rationale"] == "x" * 15 and item.v1["pit_sentinel_pass"] is True
    (residual + 1e-5).rename("factor").reset_index().to_parquet(panel, index=False)
    assert not rebuild_gp(candidate, research, min_cross_section=30, tolerance=1e-6, expression_values=expression).reproduced


def test_outputs_refuse_the_v1_admission_ledger_and_logs_g1(settings, tmp_path):  # noqa: F811
    with pytest.raises(RejudgeIsolationError):
        rejudge_roots(settings, EXECUTION, admissions=FACTOR_ADMISSIONS, data_root=tmp_path, reports_root=tmp_path)
    with pytest.raises(RejudgeIsolationError):
        rejudge_roots(settings, EXECUTION, admissions=tmp_path / "a.csv", data_root=tmp_path, reports_root=PROJECT_ROOT / "logs" / "g1")
    roots = rejudge_roots(settings, EXECUTION, admissions=tmp_path / "a.csv", data_root=tmp_path, reports_root=PROJECT_ROOT / "logs" / "g1-v2")
    assert roots.reports.name == EXECUTION and roots.admissions == tmp_path / "a.csv"


def _ledgers(tmp_path: Path) -> tuple[Path, Path]:
    experiments = tmp_path / "experiments.csv"
    experiments.write_text(EXPERIMENTS.read_text(encoding="utf-8").splitlines()[0] + "\n", encoding="utf-8")
    for family, count in V1_ROWS.items():
        for position in range(count):
            append_experiment(
                path=experiments, experiment_id=f"v1-{family}-{position}", parent_experiment_id="", ts="2026-08-01T00:00:00+00:00",
                candidate_source="synthetic-v1", model_or_engine="synthetic", engine_version="v1", seed="", prompt_hash="",
                code_sha256="1" * 64, data_snapshot_sha256="2" * 64, feature_or_formula=f"v1 {family} {position}",
                params_json={"g1_research_family": family}, train_period="", valid_period="",
                result_json={"selection_sharpe": 0.1 * (position + 1)}, admitted=False, reject_reason="synthetic v1 attempt",
            )
    admissions = tmp_path / "factor_admissions_v2.csv"
    admissions.write_text(FACTOR_ADMISSIONS_V2.read_text(encoding="utf-8").splitlines()[0] + "\n", encoding="utf-8")  # 只取表头：真实 v2 账本已有正式行
    return experiments, admissions


def _reconstructions(identity, tmp_path: Path) -> dict[str, list[Reconstruction]]:
    """每家族取前两个冻结定义；P1 有一个复现不过 → 整家族 NOT_REEVALUATED。"""
    short, full = _v1_files(tmp_path / "gp", "x" * 15), _v1_files(tmp_path / "f", "因子刻画了可解释的基本面风险补偿与市场定价偏差，" * 2)
    from shaiwei.research.g1_v2_rejudge.sources import v1_metadata

    result = {}
    for offset, family in enumerate(FAMILIES):
        items = []
        for position, candidate in enumerate(identity.config.families[family][:2]):
            metadata = v1_metadata(candidate.model_copy(update={"v1_evidence_path": str(short if family == GP else full)}))
            failed = family == P1 and position == 1
            reproduction = {"status": "FAIL" if failed else "PASS", "max_abs_difference": 1.0 if failed else 0.0}
            items.append(Reconstruction(family, candidate, _series(200 + 10 * offset + position), reproduction, metadata))
        result[family] = items
    return result


def _scope(identity, ledgers: dict[str, object]) -> release.Envelope:
    scope = release.RejudgeScope(
        schema_version="g1-v2-rejudge-scope-v1", protocol_id="g1-v2-rejudge-v2", protocol_config_sha256=identity.config_sha256,
        protocol_document_sha256=identity.document_sha256, spec_sha256=identity.spec_sha256, execution_id=EXECUTION, git_head="a" * 40,
        image="shaiwei:g1-calibration-cccccccccccc", image_id="sha256:" + "e" * 64, code_snapshot_sha256=FACTS["code_snapshot"],
        data_snapshot_sha256=FACTS["data_snapshot"], qlib_bin_sha256=FACTS["qlib_fingerprint"], units=21,
        precheck_report_path="logs/g1-v2/precheck/reproduction-20261025T110000Z.json", precheck_report_sha256="f" * 64,
        ledgers=release.Ledgers.model_validate(ledgers), prepared_at="2026-10-25T12:00:00+00:00",
    )
    return release.Envelope(scope_sha256=release.scope_hash(scope), scope=scope)


def _install(envelope: release.Envelope, control: Path) -> None:
    (control / "scopes").mkdir(parents=True, exist_ok=True)
    (control / "scopes" / f"{envelope.scope_sha256}.scope.json").write_text(envelope.model_dump_json(), encoding="utf-8")


def test_approval_is_only_a_verbatim_transcript_and_preconditions_reject_drift(identity, tmp_path):
    ledgers = {"experiments_rows": 8, "rejudge_rows": 0, "admissions_v2_rows": 0, "factor_admissions_v1_sha256": "0" * 64}
    envelope = _scope(identity, ledgers)
    _install(envelope, tmp_path)
    text = release.approval_text(envelope)
    assert envelope.scope_sha256 in text and "全部 21 个因子定义" in text and "不写 v1 准入账本" in text
    with pytest.raises(release.RejudgeScopeError, match="verbatim"):
        release.record_approval(envelope.scope_sha256, text.replace("仅执行一次", "执行"), tmp_path)
    with pytest.raises(FileNotFoundError):
        release.load_approved(envelope.scope_sha256, tmp_path)
    assert release.record_approval(envelope.scope_sha256, text, tmp_path)["status"] == "APPROVAL_RECORDED"
    with pytest.raises(release.RejudgeScopeError, match="already recorded"):
        release.record_approval(envelope.scope_sha256, text, tmp_path)
    assert release.load_approved(envelope.scope_sha256, tmp_path) == envelope
    good = dict(code=FACTS["code_snapshot"], data=FACTS["data_snapshot"], qlib=FACTS["qlib_fingerprint"])
    release.verify(envelope, identity, ledgers=ledgers, **good)
    for key in good:
        with pytest.raises(release.RejudgeScopeError, match="drifted"):
            release.verify(envelope, identity, ledgers=ledgers, **{**good, key: "9" * 64})
    for key, value in (("rejudge_rows", 1), ("admissions_v2_rows", 1), ("factor_admissions_v1_sha256", "1" * 64)):
        with pytest.raises(release.RejudgeScopeError, match="drifted"):
            release.verify(envelope, identity, ledgers={**ledgers, key: value}, **good)
    path = tmp_path / "scopes" / f"{envelope.scope_sha256}.scope.json"
    path.write_text(path.read_text(encoding="utf-8").replace('"experiments_rows":8', '"experiments_rows":9'), encoding="utf-8")
    with pytest.raises(release.RejudgeScopeError, match="hash"):
        release.load_approved(envelope.scope_sha256, tmp_path)
    with pytest.raises(ValidationError):
        _scope(identity, {**ledgers, "rejudge_rows": 3})


@pytest.fixture(scope="module")
def executed(tmp_path_factory, settings, identity, research, baselines):  # noqa: F811
    patcher = pytest.MonkeyPatch()
    patcher.setattr(evaluate, "_max_library_correlation", lambda *_args: 0.0)
    patcher.setattr(release, "load_rejudge_protocol", lambda *_args, **_kwargs: identity)
    tmp_path = tmp_path_factory.mktemp("g1-v2-rejudge")
    formal = {path: path.read_bytes() for path in (EXPERIMENTS, FACTOR_ADMISSIONS, FACTOR_ADMISSIONS_V2)}
    experiments, admissions = _ledgers(tmp_path)
    roots = rejudge_roots(settings, EXECUTION, experiments=experiments, admissions=admissions,
                          data_root=tmp_path / "data", reports_root=tmp_path / "logs")
    envelope = _scope(identity, release.ledger_state(experiments=experiments, admissions_v2=admissions))
    control = tmp_path / "control"
    _install(envelope, control)
    release.record_approval(envelope.scope_sha256, release.approval_text(envelope), control)
    reconstructions = _reconstructions(identity, tmp_path)
    parts = {"research": research, "baselines": baselines, "backtest": _fake_backtest(research.labels)}
    kwargs = dict(settings=settings, control=control, roots=roots, facts=lambda _settings: FACTS,
                  loader=lambda _settings, _identity: (parts, reconstructions))
    result = release.execute(envelope.scope_sha256, **kwargs)
    yield {"result": result, "roots": roots, "control": control, "envelope": envelope, "kwargs": kwargs, "formal": formal}
    patcher.undo()


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_execution_writes_real_family_rows_and_only_isolated_outputs(executed):
    roots = executed["roots"]
    summary = json.loads((roots.reports / "summary.json").read_text(encoding="utf-8"))
    assert summary["execution_id"] == EXECUTION and executed["result"]["counts"] == summary["counts"]
    statuses = {(u["family"], u["status"]) for u in summary["units"]}
    assert {status for family, status in statuses if family == P1} == {"NOT_REEVALUATED"}
    assert all(status in {"PASS", "REJECT"} for family, status in statuses if family != P1)
    rejudged = [row for row in _rows(roots.experiments) if json.loads(row["params_json"]).get("attempt_stage") == "g1_v2_rejudge"]
    assert len(rejudged) == 6  # P1 整家族未评估：不记账
    parents = {row["parent_experiment_id"]: json.loads(row["params_json"]) for row in rejudged}
    for family in (GP, F1, F2):
        for item in executed["kwargs"]["loader"](None, None)[1][family]:
            params = parents[item.candidate.candidate_experiment_id]
            assert params["g1_research_family"] == family and params["neutralization"] == "pit_support"
    assert all(json.loads(row["result_json"])["selection_increment_ir"] is not None for row in rejudged)
    reproduction = json.loads((roots.reports / "reproduction.json").read_text(encoding="utf-8"))
    assert reproduction["scope"] == "reproduction only; no g1-v2 statistic computed" and len(reproduction["candidates"]) == 8
    assert {path: path.read_bytes() for path in executed["formal"]} == executed["formal"]  # 真实账本一字未动


def test_family_n_follows_the_declared_multiple_testing_families(executed, settings):  # noqa: F811
    from shaiwei.research.g1_v2 import load_spec

    decisions = _rows(executed["roots"].admissions)
    by_family: dict[str, set[tuple[str, str]]] = {}
    for row in decisions:
        by_family.setdefault(row["research_family"], set()).add((row["trial_count"], row["valid_trial_sharpes"]))
    assert by_family == {
        GP: {(str(V1_ROWS[GP] + 2), "2")},
        F1: {(str(V1_ROWS[F1] + 2), "2")},
        F2: {(str(V1_ROWS[F1] + 2 + V1_ROWS[F2] + 2), "4")},  # F2 = F1+F2：历史与本次写入都计入，方差取两家族的增量 IR
    }
    for row in decisions:
        report = json.loads(Path(row["report_path"]).read_text(encoding="utf-8"))
        assert set(report["candidate"]["multiple_testing_families"]) == ({F1, F2} if row["research_family"] == F2 else {row["research_family"]})
        assert set(report["gates"]) == set(load_spec(settings).spec.gates)
        if row["research_family"] == GP:
            assert "economic_rationale" in report["failed_gates"] and report["status"] == "REJECT"


def test_execution_runs_once_and_refuses_any_rerun(executed):
    with pytest.raises(release.RejudgeScopeError):
        release.execute(executed["envelope"].scope_sha256, **executed["kwargs"])
    claim = json.loads((executed["roots"].data / "claim.json").read_text(encoding="utf-8"))
    assert claim["scope_sha256"] == executed["envelope"].scope_sha256 and claim["state"] == "MAY_HAVE_WRITTEN"


def _audit(executed, settings, identity, **overrides):  # noqa: F811
    roots = executed["roots"]
    kwargs = dict(settings=settings, data_dir=roots.data, reports_dir=roots.reports, control_root=executed["control"],
                  experiments=roots.experiments, admissions_v2=roots.admissions, admissions_v1=FACTOR_ADMISSIONS, identity=identity)
    return audit_module.audit(EXECUTION, **{**kwargs, **overrides})


def test_independent_audit_rejudges_everything_and_catches_tampering(executed, settings, identity, tmp_path):  # noqa: F811
    result = _audit(executed, settings, identity)
    assert result["status"] == "PASS", result["findings"]
    assert result["recomputed_counts"] == json.loads((executed["roots"].reports / "summary.json").read_text(encoding="utf-8"))["counts"]
    v1 = tmp_path / "factor_admissions.csv"
    v1.write_bytes(FACTOR_ADMISSIONS.read_bytes() + b"\n")
    assert any("g1-v1" in finding for finding in _audit(executed, settings, identity, admissions_v1=v1)["findings"])
    admissions = tmp_path / "factor_admissions_v2.csv"
    text = executed["roots"].admissions.read_text(encoding="utf-8")
    flipped = re.sub(r",(true|false),", lambda m: ",false," if m.group(1) == "true" else ",true,", text, count=1)
    admissions.write_text(flipped, encoding="utf-8")
    tampered = _audit(executed, settings, identity, admissions_v2=admissions)
    assert tampered["status"] == "FAIL" and any("admission row" in finding for finding in tampered["findings"])


def test_rejudge_context_rejects_evidence_that_cannot_be_neutralized(settings, identity, research, baselines, tmp_path):  # noqa: F811
    experiments, admissions = _ledgers(tmp_path)
    roots = rejudge_roots(settings, EXECUTION, experiments=experiments, admissions=admissions, data_root=tmp_path / "d", reports_root=tmp_path / "l")
    from shaiwei.research.g1_v2 import load_spec

    ctx = evaluate.RejudgeContext(settings=settings, identity=identity, spec=load_spec(settings).spec, research=research, baselines=baselines,
                                  code_hash=FACTS["code_snapshot"], data_hash=FACTS["data_snapshot"], backtest=_fake_backtest(research.labels))
    item = _reconstructions(identity, tmp_path)[F1][0]
    empty = Reconstruction(F1, item.candidate, pd.Series(np.nan, index=item.raw.index), item.reproduction, item.v1)
    experiment, evidence, error = evaluate.evaluate_unit(ctx, roots, empty)
    assert evidence is None and error
    row = next(row for row in _rows(experiments) if row["experiment_id"] == experiment)
    assert json.loads(row["result_json"])["error_type"] == error and row["admitted"] == "false"
