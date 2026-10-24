"""g1-positive-control-v1 工程的合成测试：不读真实数据、不写真实账本（协议 §10 第 2 步）。"""

import csv
import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import pytest
from pydantic import ValidationError

from shaiwei.config import load
from shaiwei.ledger import EXPERIMENTS, FACTOR_ADMISSIONS
from shaiwei.research import g1_pipeline
from shaiwei.research.factor_portfolio import SignalBacktest, daily_rank_ic
from shaiwei.research.g1 import G1Evidence
from shaiwei.research.g1_calibration import controls, pilot, runner, signals
from shaiwei.research.g1_calibration.evidence import build_portfolio_evidence
from shaiwei.research.g1_calibration.judge import load_calibration_evidence
from shaiwei.research.g1_calibration.protocol import ProtocolError, load_protocol
from shaiwei.research.g1_calibration.summary import UnitOutcome, clopper_pearson_upper, summarize
from shaiwei.research.g1_calibration.writer import (
    IsolationError,
    output_roots,
    record_experiment,
    write_factor_panel,
)
from shaiwei.research.g1_pipeline import BaselineWindow, ResearchData

INSTRUMENTS = [f"SH6000{index:02d}" for index in range(36)]


def _calendar() -> pd.DatetimeIndex:
    parts = [pd.bdate_range("2016-06-01", "2018-12-31"), pd.bdate_range("2026-01-01", "2026-03-31")]
    parts += [pd.bdate_range(f"{year}-01-01", f"{year}-12-31")[:70] for year in range(2019, 2025)]
    return pd.DatetimeIndex(sorted(set().union(*parts)))


def _index(dates) -> pd.MultiIndex:
    return pd.MultiIndex.from_product([dates, INSTRUMENTS], names=["datetime", "instrument"])


def _series(seed: int, dates=None, scale: float = 1.0) -> pd.Series:
    index = _index(_calendar() if dates is None else dates)
    return pd.Series(np.random.default_rng(seed).standard_normal(len(index)) * scale, index=index)


@pytest.fixture(scope="module")
def settings():
    return load()


@pytest.fixture(scope="module")
def protocol(settings):
    return load_protocol(settings)


@pytest.fixture(scope="module")
def research() -> ResearchData:
    dates = _calendar()
    labels = _series(1, dates, 0.03).rename("label")
    rng = np.random.default_rng(2)
    caps = dict(zip(INSTRUMENTS, np.exp(rng.normal(10, 1, len(INSTRUMENTS))), strict=True))
    exposures = pd.DataFrame(
        [(date, code, f"I{index % 3}", caps[code] * (1 + 0.001 * position)) for position, date in enumerate(dates)
         for index, code in enumerate(INSTRUMENTS)],
        columns=["trade_date", "instrument", "industry", "market_cap"],
    )
    return ResearchData(stock_data=SimpleNamespace(name="synthetic"), labels=labels, exposures=exposures)


def _fake_backtest(labels: pd.Series):
    def backtest(settings, signal, *, start_time, end_time, cost_multiplier=1.0, extra_open_cost=0.0, extra_close_cost=0.0):
        joined = pd.concat([signal.rename("signal"), labels.rename("label")], axis=1, join="inner").dropna()
        dates = joined.index.get_level_values("datetime")
        joined = joined.loc[(dates >= pd.Timestamp(start_time)) & (dates <= pd.Timestamp(end_time))]
        cost = (settings.backtest.open_cost + settings.backtest.close_cost) * cost_multiplier + extra_open_cost + extra_close_cost
        daily = joined.groupby(level="datetime").apply(lambda g: g.nlargest(settings.backtest.topk, "signal")["label"].mean()) / 10
        daily = daily - cost / 10
        return SignalBacktest(daily_excess=daily, cumulative_excess=float((1 + daily).prod() - 1), turnover=float(len(daily)) * 0.1, max_drawdown=0.0)

    return backtest


@pytest.fixture(scope="module")
def baselines(settings, research) -> list[BaselineWindow]:
    backtest = _fake_backtest(research.labels)
    windows = []
    for position, window in enumerate(settings.evaluation.g0_windows):
        dates = research.labels.index.get_level_values("datetime")
        mask = (dates >= pd.Timestamp(window.test_start)) & (dates <= pd.Timestamp(window.test_end))
        window_labels = research.labels.loc[mask]
        predictions = (0.3 * window_labels + _series(100 + position, scale=0.03).reindex(window_labels.index)).rename("score")
        result = backtest(settings, predictions, start_time=window.test_start.isoformat(), end_time=window.test_end.isoformat())
        windows.append(BaselineWindow(window, predictions, window_labels, daily_rank_ic(predictions, window_labels), result))
    return windows


def _expressions(research):
    support = research.labels.index
    values = {
        controls.PIT_SUPPORT_EXPRESSION: pd.Series(1.0, index=support),
        controls.ROUTE_EXPRESSIONS["R3"]: _series(7),
        controls.ROUTE_EXPRESSIONS["R4"]: _series(8),
        controls.ROUTE_EXPRESSIONS["R5"]: _series(9),
    }
    return lambda text, _stock_data: values[text].copy()


def _audit(_expression):
    return SimpleNamespace(expression_tokens=11, ast_nodes=9, pit_sentinel_pass=True, shift_sentinel_pass=True)


def _context(settings, protocol, research, baselines, **overrides):
    return signals.RunContext(
        settings=settings, protocol=protocol, research=research, r5_stock_data=SimpleNamespace(name="r5"),
        baselines=baselines, code_hash="c" * 64, data_hash="d" * 64, backtest=_fake_backtest(research.labels),
        expression_values=_expressions(research), audit=_audit, **overrides,
    )


def _roots(settings, tmp_path: Path, execution="exec-test"):
    experiments = tmp_path / "experiments.csv"
    experiments.write_text(EXPERIMENTS.read_text(encoding="utf-8").splitlines()[0] + "\n", encoding="utf-8")
    runs = tmp_path / "g1_calibration_runs.csv"
    runs.write_text(Path("ledger/g1_calibration_runs.csv").read_text(encoding="utf-8").splitlines()[0] + "\n", encoding="utf-8")
    return output_roots(
        settings, execution, experiments=experiments, runs=runs,
        data_root=tmp_path / "data" / "g1-calibration-v1", reports_root=tmp_path / "logs" / "g1-calibration",
    )


def _reduced(protocol, *, noise_seeds=2):
    """端到端只缩小规模（单强度、每对照 2 种子），路线、门、判读规则全部原样。"""
    config = protocol.config
    routes = dict(config.routes)
    for route in ("N1", "N2"):
        start = config.routes[route].seed_values()[0]
        routes[route] = config.routes[route].model_copy(update={"seeds": tuple(range(start, start + noise_seeds))})
    reduced = config.model_copy(update={
        "routes": routes,
        "calibration": config.calibration.model_copy(update={"target_mean_rank_ic": (0.04,)}),
    })
    return replace(protocol, config=reduced)


# ---- 协议身份 ---------------------------------------------------------------------------


def test_protocol_binds_to_live_g1_v1_spec_and_refuses_drift(settings, tmp_path):
    identity = load_protocol(settings)
    assert identity.config.status == "FROZEN_BEFORE_RESULTS"
    assert len(runner.plan_cells(identity, 30)) == 11
    assert [sum(len(c) for c in runner.plan_cells(identity, n)) for n in (30, 20, 10)] == [93, 73, 53]
    with pytest.raises(ProtocolError):
        runner.plan_cells(identity, 25)
    text = identity.config_path.read_text(encoding="utf-8")
    drifted = tmp_path / "drifted.yaml"
    drifted.write_text(text.replace(identity.config.judge.spec_sha256, "0" * 64), encoding="utf-8")
    with pytest.raises(ProtocolError, match="spec sha256"):
        load_protocol(settings, drifted)
    moved = tmp_path / "moved.yaml"
    moved.write_text(text.replace('"rank_ic_retention", ', ""), encoding="utf-8")
    with pytest.raises(ProtocolError, match="partition"):
        load_protocol(settings, moved)
    controls.verify_route_expressions(identity.config)


# ---- 对照构造与 a 标定 --------------------------------------------------------------------------


def test_seeded_noise_and_shuffle_are_deterministic_and_structure_preserving():
    index = _index(pd.bdate_range("2020-01-01", periods=5))
    first = controls.seeded_normal(index[::-1], 101)
    assert first.equals(controls.seeded_normal(index, 101))
    assert not first.equals(controls.seeded_normal(index, 102))
    values = _series(3, pd.bdate_range("2020-01-01", periods=5))
    shuffled = controls.shuffle_within_dates(values, 3001)
    assert not shuffled.equals(values.sort_index())
    for date in values.index.get_level_values(0).unique():
        assert sorted(shuffled.xs(date)) == sorted(values.xs(date))
    z = controls.cross_section_z(values)
    assert np.allclose(z.groupby(level=0).mean(), 0) and np.allclose(z.groupby(level=0).std(ddof=0), 1)


def test_neutralize_matches_the_real_pipeline_path(monkeypatch, settings, research):
    raw = _series(7).rename("factor")
    frame = raw.to_frame("factor")
    monkeypatch.setattr(g1_pipeline, "parse_safe_expression", lambda _text: SimpleNamespace(evaluate=lambda _data: "tensor"))
    stock = SimpleNamespace(make_dataframe=lambda _tensor, columns: frame.rename(columns={"factor": columns[0]}))
    real_residual, real_ic = g1_pipeline.evaluate_factor_panel("R3", replace(research, stock_data=stock), min_cross_section=30)
    residual, ic = controls.neutralize(raw, research, min_cross_section=30)
    pd.testing.assert_series_equal(residual, real_residual)
    pd.testing.assert_series_equal(ic, real_ic)


def test_blend_calibration_hits_target_on_the_real_neutralization_path(protocol, research):
    tolerance = protocol.config.calibration.tolerance
    discovery = (protocol.config.calibration.discovery_start, protocol.config.calibration.discovery_end)
    z_label = controls.cross_section_z(research.labels)
    label_residual, _ = controls.neutralize(z_label, research, min_cross_section=30)
    z_noise = controls.cross_section_z(controls.seeded_normal(z_label.index, 101))
    noise_residual, _ = controls.neutralize(z_noise, research, min_cross_section=30)
    calibration = controls.calibrate_blend(
        target=0.04, tolerance=tolerance, label_residual=label_residual, noise_residual=noise_residual,
        labels=research.labels, discovery=discovery,
    )
    residual, daily_ic = controls.neutralize(controls.blend(z_label, z_noise, calibration.a), research, min_cross_section=30)
    achieved = controls.verify_blend(
        calibration=calibration, residual=residual, daily_ic=daily_ic, label_residual=label_residual,
        noise_residual=noise_residual, discovery=discovery, tolerance=tolerance,
    )
    assert abs(achieved - 0.04) <= tolerance
    with pytest.raises(controls.CalibrationError, match="not linear"):
        controls.verify_blend(
            calibration=calibration, residual=residual + 1e-3, daily_ic=daily_ic, label_residual=label_residual,
            noise_residual=noise_residual, discovery=discovery, tolerance=tolerance,
        )
    with pytest.raises(controls.CalibrationError, match="misses target"):
        controls.verify_blend(
            calibration=replace(calibration, target=0.06), residual=residual, daily_ic=daily_ic,
            label_residual=label_residual, noise_residual=noise_residual, discovery=discovery, tolerance=tolerance,
        )


# ---- 证据口径与诊断 ------------------------------------------------------------------------------


def test_blend_evidence_equals_real_evaluate_candidate(monkeypatch, tmp_path, settings, research, baselines):
    factor, daily_ic = controls.neutralize(_series(11).rename("factor"), research, min_cross_section=30)
    backtest = _fake_backtest(research.labels)
    captured = {}
    monkeypatch.setattr(g1_pipeline, "backtest_signal", backtest)
    monkeypatch.setattr(g1_pipeline, "code_snapshot_sha256", lambda: "c" * 64)
    monkeypatch.setattr(g1_pipeline, "ingest_snapshot_sha256", lambda: "d" * 64)
    monkeypatch.setattr(g1_pipeline, "_existing_experiment", lambda _id: None)
    monkeypatch.setattr(g1_pipeline, "_max_library_correlation", lambda *_args: 0.0)
    monkeypatch.setattr(g1_pipeline, "append_experiment", lambda **kw: captured.update(kw))
    report = tmp_path / "benchmark.json"
    report.write_text("{}", encoding="utf-8")
    audit = SimpleNamespace(normalized_expression="x", expression_tokens=3, ast_nodes=3, pit_sentinel_pass=True,
                            shift_sentinel_pass=True, max_lookback_days=1, required_backtrack_days=0, compared_values=1)
    artifacts = g1_pipeline.evaluate_candidate(
        settings, expression="x", family="synthetic", benchmark_report=report, audit=audit, research=research,
        factor=factor, factor_daily_ic=daily_ic, baselines=baselines, output_root=tmp_path / "out", rationale="r" * 20,
    )
    real = json.loads(artifacts.evidence_path.read_text(encoding="utf-8"))
    ours = build_portfolio_evidence(
        settings, factor=factor, factor_daily_ic=daily_ic, labels=research.labels, baselines=baselines, mode="blend", backtest=backtest,
    )
    assert real["rank_ic"] == {"in_sample": ours.in_sample_ic, "oos_windows": ours.oos_windows, "daily_oos": ours.daily_oos}
    assert real["stress_max_drawdown"] == ours.stress
    assert real["portfolio"]["daily_net_excess_returns"] == ours.daily_net_excess
    for key, value in ours.metrics.items():
        if key != "selection_sharpe":
            assert real["portfolio"][key] == value
    assert captured["result_json"]["selection_sharpe"] == ours.metrics["selection_sharpe"]


def test_factor_only_mode_trades_the_oriented_factor_and_reports_overlap(settings, research, baselines):
    factor, daily_ic = controls.neutralize(_series(12).rename("factor"), research, min_cross_section=30)
    seen = []
    backtest = _fake_backtest(research.labels)

    def spy(settings_, signal, **kwargs):
        seen.append(signal)
        return backtest(settings_, signal, **kwargs)

    evidence = build_portfolio_evidence(
        settings, factor=factor, factor_daily_ic=daily_ic, labels=research.labels, baselines=baselines, mode="factor_only", backtest=spy,
    )
    pd.testing.assert_series_equal(seen[0], evidence.direction * factor)
    overlap = evidence.diagnostics["top30_overlap"]
    assert [w["window"] for w in overlap] == ["W1", "W2", "W3", "W4", "W5", "W6"]
    first = overlap[0]["rebalances"]
    assert len(first) == 7 and all(0 <= row["jaccard"] <= 1 and 0 <= row["replaced"] <= 30 for row in first)
    assert set(evidence.diagnostics["transmission"]) == {
        "factor_oriented_oos_rank_ic", "score_rank_ic_increment", "net_excess_increment",
        "retention_factor_to_score", "net_excess_per_unit_score_ic",
    }


# ---- 隔离 -------------------------------------------------------------------------------------------


def test_isolation_refuses_formal_paths_and_marks_every_artifact(settings, tmp_path, research):
    with pytest.raises(IsolationError):
        output_roots(settings, "x", runs=FACTOR_ADMISSIONS)
    with pytest.raises(IsolationError):
        output_roots(settings, "x", data_root=settings.runtime.data_root / "research" / "factor_library")
    with pytest.raises(IsolationError):
        output_roots(settings, "x", reports_root=Path("logs/g1"))
    roots = _roots(settings, tmp_path)
    with pytest.raises(IsolationError, match="escapes"):
        write_factor_panel(tmp_path / "elsewhere.parquet", _series(1), research.labels, roots=roots)
    path = write_factor_panel(roots.data / "R1" / "p.parquet", _series(1), research.labels, roots=roots)
    assert pq.read_schema(path).metadata[b"admission_scope"] == b"NOT_FOR_ADMISSION"
    params = {"route": "N1", "construction": "iid", "g1_research_family": "g1-calibration-v1/N1"}
    kwargs = dict(experiment="e1", seed=2001, code_hash="c" * 64, data_hash="d" * 64, formula="Normal(seed)",
                  params=params, result={"selection_sharpe": 0.1}, discovery="d")
    record_experiment(roots, **kwargs)
    record_experiment(roots, **kwargs)
    assert len(list(csv.DictReader(roots.experiments.open(encoding="utf-8")))) == 1
    with pytest.raises(IsolationError, match="differs"):
        record_experiment(roots, **{**kwargs, "result": {"selection_sharpe": 0.2}})


def test_formal_judge_schema_rejects_calibration_evidence(tmp_path):
    document = {"admission_scope": "NOT_FOR_ADMISSION", "candidate_experiment_id": "x"}
    with pytest.raises(ValidationError, match="admission_scope"):
        G1Evidence.model_validate(document)
    unmarked = tmp_path / "unmarked.json"
    unmarked.write_text(json.dumps({"candidate_experiment_id": "x"}), encoding="utf-8")
    with pytest.raises(IsolationError, match="NOT_FOR_ADMISSION"):
        load_calibration_evidence(unmarked)


# ---- 汇总与终态 ----------------------------------------------------------------------------------


def _outcomes(protocol, *, r1_passes, negative_passes=0, noise=30, error=False):
    outcomes = []
    for strength in protocol.config.calibration.target_mean_rank_ic:
        for position, seed in enumerate(protocol.config.routes["R1"].seed_values()):
            passed = position < r1_passes.get(strength, 0)
            outcomes.append(UnitOutcome("R1", strength, seed, f"g1-calibration-v1/R1/{strength:.2f}", f"r{seed}",
                                        "EVIDENCE_ERROR" if error and position == 0 else "JUDGED", main=passed))
    for route in ("N1", "N2"):
        for position, seed in enumerate(protocol.config.routes[route].seed_values()[:noise]):
            passed = route == "N1" and position < negative_passes
            outcomes.append(UnitOutcome(route, None, seed, f"g1-calibration-v1/{route}", f"{route}{seed}", "JUDGED", main=passed))
    return outcomes


def test_clopper_pearson_and_preregistered_terminal_states(protocol):
    assert clopper_pearson_upper(0, 60, 0.95) == pytest.approx(0.0487, abs=5e-4)
    assert clopper_pearson_upper(60, 60, 0.95) == 1.0
    state = lambda **kw: summarize(protocol, _outcomes(protocol, **kw), planned_noise_seeds=kw.get("noise", 30))["terminal_state"]  # noqa: E731
    assert state(r1_passes={0.04: 4}) == "G1_CALIBRATED"
    assert state(r1_passes={0.02: 5}) == "G1_CALIBRATED"
    assert state(r1_passes={0.04: 3, 0.06: 4}) == "G1_BORDERLINE"
    assert state(r1_passes={0.06: 3}) == "G1_UNDERPOWERED"
    assert state(r1_passes={0.04: 5}, negative_passes=1) == "G1_PERMISSIVE"
    reduced = summarize(protocol, _outcomes(protocol, r1_passes={0.04: 5}, noise=10), planned_noise_seeds=10)
    assert reduced["negative_controls"]["false_pass_upper_bound"] == pytest.approx(1 - 0.05 ** (1 / 20))
    incomplete = summarize(protocol, _outcomes(protocol, r1_passes={0.04: 5}, error=True), planned_noise_seeds=30)
    assert incomplete["status"] == "INCOMPLETE" and incomplete["terminal_state"] is None


# ---- 端到端（缩小规模） ---------------------------------------------------------------------------


def test_end_to_end_run_writes_only_isolated_outputs(monkeypatch, settings, protocol, research, baselines, tmp_path):
    monkeypatch.setattr(runner, "_max_library_correlation", lambda *_args: 0.0)
    reduced = _reduced(protocol)
    roots = _roots(settings, tmp_path)
    formal = {path: path.read_bytes() for path in (EXPERIMENTS, FACTOR_ADMISSIONS, Path("ledger/g1_calibration_runs.csv"))}
    document = runner.run_calibration(_context(settings, reduced, research, baselines), roots, noise_seeds=2)
    assert {path: path.read_bytes() for path in formal} == formal
    rows = list(csv.DictReader(roots.experiments.open(encoding="utf-8")))
    families = pd.Series([json.loads(row["params_json"])["g1_research_family"] for row in rows]).value_counts().to_dict()
    assert families == {
        "g1-calibration-v1/R1/0.04": 5, "g1-calibration-v1/R2/0.04": 5, "g1-calibration-v1/R3": 1,
        "g1-calibration-v1/R4": 1, "g1-calibration-v1/R5": 1, "g1-calibration-v1/N1": 2, "g1-calibration-v1/N2": 2,
    }
    assert all(json.loads(row["params_json"])["admission_scope"] == "NOT_FOR_ADMISSION" for row in rows)
    runs = list(csv.DictReader(roots.runs.open(encoding="utf-8")))
    assert len(runs) == 17 and {row["admission_scope"] for row in runs} == {"NOT_FOR_ADMISSION"}
    r1 = [row for row in runs if row["route"] == "R1"]
    assert {row["trial_count"] for row in r1} == {"5"}
    report = json.loads((roots.reports / "summary.json").read_text(encoding="utf-8"))
    assert report == json.loads(json.dumps(document))
    assert report["summary"]["status"] == "COMPLETE"
    assert report["summary"]["terminal_state"] in protocol.config.interpretation.terminal_states
    assert set(report["baseline_fingerprint"]) == {"W1", "W2", "W3", "W4", "W5", "W6"}
    detail = json.loads((Path(roots.reports) / "R1" / "0.04").glob("*.json").__next__().read_text(encoding="utf-8"))
    assert detail["pit_and_shift_exempt"] is True and set(detail["layers"]) == {"A_signal", "B_transmission", "main"}
    assert set(detail["diagnostic_dsr"]["values"]) == {"166", "196"}
    for row in rows[:5]:
        construction = json.loads(row["params_json"])["construction_detail"]
        assert abs(construction["achieved_discovery_rank_ic"] - 0.04) <= protocol.config.calibration.tolerance
    again = runner.run_calibration(_context(settings, reduced, research, baselines), roots, noise_seeds=2)
    assert again == document  # 同绑定复跑：证据、报告、汇总逐字节复用，不追加任何账本行
    assert len(list(csv.DictReader(roots.experiments.open(encoding="utf-8")))) == 17
    assert len(list(csv.DictReader(roots.runs.open(encoding="utf-8")))) == 17


def test_pilot_records_timings_only(settings, protocol, research, baselines):
    report = pilot.pilot(_context(settings, protocol, research, baselines), {"build_baseline_windows": 1.0})
    text = json.dumps(report)
    assert set(report["projections"]) == {"30", "20", "10"}
    assert report["projections"]["30"]["evaluations"] == 93
    for forbidden in ("selection_sharpe", "rank_ic", "net_excess", "passed", "a\""):
        assert forbidden not in text
    assert {unit["seed"] for unit in report["pilot_units"]} == {0}
