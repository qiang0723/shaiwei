"""g1-positive-control-v1 编排：按“路线×强度”格子执行 对照构造 → 组合证据 → 实验总账 → 两层判定 → 汇总。

每格先完成全部种子的证据与记账，再逐个判定：DSR 的 N 与试验方差由 `g1-v1` 从总账机械统计，
失败尝试同样计入 N。数据与六窗基线由调用方只载入/训练一次（见 `pilot.load_context`）。
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from shaiwei.research.factor_portfolio import FactorPortfolioError
from shaiwei.research.g1 import G1Error, _spec_sha256, periodic_sharpe
from shaiwei.research.g1_calibration import controls
from shaiwei.research.g1_calibration.evidence import build_increment_series, build_portfolio_evidence
from shaiwei.research.g1_calibration.judge import DIAGNOSTIC_DSR_RULE, INCREMENT_SCHEMA, judge
from shaiwei.research.g1_calibration.protocol import ADMISSION_SCOPE, cell_family
from shaiwei.research.g1_calibration.signals import RATIONALE, RunContext, Unit, build_signal, plan_cells
from shaiwei.research.g1_calibration.summary import UnitOutcome, summarize
from shaiwei.research.g1_calibration.writer import (
    OutputRoots,
    artifact,
    experiment_id,
    record_experiment,
    record_verdict,
    write_factor_panel,
    write_json_once,
)
from shaiwei.research.g1_pipeline import BaselineWindow, G1PipelineError, _max_library_correlation

EVIDENCE_ERRORS = (controls.CalibrationError, G1PipelineError, FactorPortfolioError, G1Error)


def _slug(ctx: RunContext, family: str) -> str:
    return family.removeprefix(f"{ctx.protocol.config.family}/")


def _judge_spec_sha(ctx: RunContext) -> str:
    if ctx.protocol.version == "v2":
        return ctx.protocol.config.judge.spec_config_sha256  # type: ignore[union-attr]
    return _spec_sha256(ctx.settings)


def _dated(series: pd.Series) -> dict[str, float]:
    return {pd.Timestamp(day).date().isoformat(): float(value) for day, value in series.items()}


def _increment_ir(ctx: RunContext, candidate: dict[str, float], baseline: dict[str, float]) -> float:
    from shaiwei.research.g1_v2 import paired_differences

    return periodic_sharpe(paired_differences(candidate, baseline), minimum=ctx.settings.g1_admission.min_observations)


def evaluate_increment_unit(ctx: RunContext, roots: OutputRoots, unit: Unit) -> tuple[str, Path | None, dict[str, object], str]:
    """N3：只算混合分数与基线分数的逐日 RankIC，按三个增量门判定；不回测、不写面板。"""
    config = ctx.protocol.config
    family = cell_family(config, unit.route, unit.strength)
    experiment = experiment_id(ctx.protocol, family, unit.seed, ctx.code_hash, ctx.data_hash)
    route = config.routes[unit.route]
    params: dict[str, object] = {
        "g1_research_family": family, "protocol_id": config.protocol_id, "route": unit.route,
        "construction": route.construction, "strength": None, "mode": "increment_only", "direction": route.direction,
        "judged_gates": list(route.judged_gates or ()),
    }
    discovery = f"{config.calibration.discovery_start}~{config.calibration.discovery_end}"
    try:
        signal = build_signal(ctx, unit)
        candidate_ic, baseline_ic = build_increment_series(
            ctx.settings, factor=signal.residual, baselines=ctx.baselines, direction=float(route.direction or 1)
        )
        candidate, baseline = _dated(candidate_ic), _dated(baseline_ic)
        increment_ir = _increment_ir(ctx, candidate, baseline)
    except EVIDENCE_ERRORS as error:
        record_experiment(
            roots, experiment=experiment, seed=unit.seed, code_hash=ctx.code_hash, data_hash=ctx.data_hash,
            formula=f"{unit.route} evidence error", params=params,
            result={"error_type": type(error).__name__, "error": str(error)[:300]}, discovery=discovery,
        )
        return experiment, None, {}, type(error).__name__
    params.update(construction_detail=signal.construction)
    evidence = {
        "admission_scope": ADMISSION_SCOPE, "schema_version": INCREMENT_SCHEMA, "candidate_experiment_id": experiment,
        "research_family": family, "code_snapshot_sha256": ctx.code_hash, "data_snapshot_sha256": ctx.data_hash,
        "candidate_score_rank_ic": candidate, "baseline_score_rank_ic": baseline,
    }
    evidence_path = write_json_once(roots.data / _slug(ctx, family) / experiment / "increment_evidence.json", evidence, root=roots.data, roots=roots)
    record_experiment(
        roots, experiment=experiment, seed=unit.seed, code_hash=ctx.code_hash, data_hash=ctx.data_hash,
        formula=signal.formula, params=params, result={"selection_increment_ir": increment_ir}, discovery=discovery,
    )
    return experiment, evidence_path, {}, ""


def evaluate_unit(ctx: RunContext, roots: OutputRoots, unit: Unit) -> tuple[str, Path | None, dict[str, object], str]:
    """返回 (实验 ID, 证据路径或 None, 诊断, 错误类型)；任何已知证据错误都如实记账并计入 N。"""
    if unit.route == "N3":
        return evaluate_increment_unit(ctx, roots, unit)
    config, settings = ctx.protocol.config, ctx.settings
    family = cell_family(config, unit.route, unit.strength)
    experiment = experiment_id(ctx.protocol, family, unit.seed, ctx.code_hash, ctx.data_hash)
    mode = "factor_only" if unit.route == "R2" else "blend"
    route = config.routes[unit.route]
    params: dict[str, object] = {
        "g1_research_family": family, "protocol_id": config.protocol_id, "route": unit.route,
        "construction": route.construction, "strength": unit.strength, "mode": mode,
        "pit_and_shift_exempt": route.pit_and_shift_exempt or unit.route == "R2",
    }
    discovery = f"{config.calibration.discovery_start}~{config.calibration.discovery_end}"
    try:
        signal = build_signal(ctx, unit)
        portfolio = build_portfolio_evidence(
            settings, factor=signal.residual, factor_daily_ic=signal.daily_ic, labels=ctx.research.labels,
            baselines=ctx.baselines, mode=mode, backtest=ctx.backtest,
        )
        paired: dict[str, object] = {}
        if ctx.protocol.version == "v2":  # g1-v2 证据 schema 2：逐日配对序列；不足 252 个配对日即证据错误
            paired = {
                "neutralization": "pit_support",
                "candidate_score_rank_ic": _dated(portfolio.candidate_score_ic),
                "baseline_score_rank_ic": _dated(portfolio.baseline_score_ic),
                "candidate_daily_net_excess": _dated(portfolio.candidate_daily_excess),
                "baseline_daily_net_excess": _dated(portfolio.baseline_daily_excess),
            }
            increment_ir = _increment_ir(ctx, paired["candidate_score_rank_ic"], paired["baseline_score_rank_ic"])  # type: ignore[arg-type]
    except EVIDENCE_ERRORS as error:
        record_experiment(
            roots, experiment=experiment, seed=unit.seed, code_hash=ctx.code_hash, data_hash=ctx.data_hash,
            formula=f"{unit.route} evidence error", params=params,
            result={"error_type": type(error).__name__, "error": str(error)[:300]}, discovery=discovery,
        )
        return experiment, None, {}, type(error).__name__
    params.update(expression_tokens=signal.tokens, ast_nodes=signal.nodes, construction_detail=signal.construction)
    if mode == "blend":
        params["factor_blend_weight"] = settings.g1_admission.factor_blend_weight
    directory = roots.data / _slug(ctx, family) / experiment
    panel_path = write_factor_panel(directory / "factor_panel.parquet", signal.residual, ctx.research.labels, roots=roots)
    panel_ref, panel_sha = artifact(panel_path)
    test_report = {
        "schema_version": 1, "admission_scope": ADMISSION_SCOPE, "candidate_experiment_id": experiment,
        "code_snapshot_sha256": ctx.code_hash, "data_snapshot_sha256": ctx.data_hash, "expression": signal.formula,
        "pit_sentinel_pass": signal.pit, "shift_sentinel_pass": signal.shift,
        "pit_and_shift_exempt": params["pit_and_shift_exempt"],
        "factor_panel_path": panel_ref, "factor_panel_sha256": panel_sha, "factor_panel_rows": int(len(signal.residual)),
    }
    test_path = write_json_once(directory / "factor_tests.json", test_report, root=roots.data, roots=roots)
    test_ref, test_sha = artifact(test_path)
    metrics = portfolio.metrics
    evidence = {
        "admission_scope": ADMISSION_SCOPE, "schema_version": 2 if paired else 1, "candidate_experiment_id": experiment,
        "research_family": family, "code_snapshot_sha256": ctx.code_hash, "data_snapshot_sha256": ctx.data_hash,
        "economic_rationale": RATIONALE[unit.route],
        "complexity": {"expression_tokens": signal.tokens, "ast_nodes": signal.nodes},
        "integrity": {
            "pit_sentinel_pass": signal.pit, "shift_sentinel_pass": signal.shift,
            "test_report_path": test_ref, "test_report_sha256": test_sha,
            "max_library_abs_spearman": _max_library_correlation(
                signal.residual, settings.runtime.data_root / "research" / "factor_library"
            ),
        },
        "rank_ic": {"in_sample": portfolio.in_sample_ic, "oos_windows": portfolio.oos_windows, "daily_oos": portfolio.daily_oos},
        "stress_max_drawdown": portfolio.stress,
        "portfolio": {
            **{key: value for key, value in metrics.items() if key != "selection_sharpe"},
            "daily_net_excess_returns": portfolio.daily_net_excess,
        },
        **paired,
    }
    evidence_path = write_json_once(directory / "g1_evidence.json", evidence, root=roots.data, roots=roots)
    result = {**metrics, "factor_test_report_path": test_ref, "factor_test_report_sha256": test_sha}
    if paired:
        result["selection_increment_ir"] = increment_ir
    record_experiment(
        roots, experiment=experiment, seed=unit.seed, code_hash=ctx.code_hash, data_hash=ctx.data_hash,
        formula=signal.formula, params=params, result=result, discovery=discovery,
    )
    return experiment, evidence_path, portfolio.diagnostics, ""


def judge_cell(ctx: RunContext, roots: OutputRoots, unit: Unit, experiment: str, evidence_path: Path, diagnostics: dict[str, object]) -> UnitOutcome:
    config = ctx.protocol.config
    family = cell_family(config, unit.route, unit.strength)
    verdict = judge(ctx.settings, ctx.protocol, evidence_path, experiments_path=roots.experiments)
    evidence_ref, evidence_sha = artifact(evidence_path)
    spec_sha = _judge_spec_sha(ctx)
    report = {
        "schema_version": 1, "admission_scope": ADMISSION_SCOPE, "protocol_id": config.protocol_id,
        "protocol_config_sha256": ctx.protocol.config_sha256, "protocol_document_sha256": ctx.protocol.document_sha256,
        "unit": {"route": unit.route, "strength": unit.strength, "seed": unit.seed, "cell_family": family},
        "bindings": {
            "experiment_id": experiment, "evidence_path": evidence_ref, "evidence_sha256": evidence_sha,
            "spec_sha256": spec_sha, "cell_trials_sha256": verdict.cell_trials_sha256,
            "code_snapshot_sha256": ctx.code_hash, "data_snapshot_sha256": ctx.data_hash,
        },
        "layers": {"A_signal": verdict.layer_a, "B_transmission": verdict.layer_b, "main": verdict.main},
        "failed_main_gates": list(verdict.failed_main),
        "pit_and_shift_exempt": unit.route in {"R1", "R2"},
        "judged_gates": list(config.routes[unit.route].judged_gates or verdict.gates),
        "gates": verdict.gates, "statistics": verdict.statistics,
        "diagnostic_dsr": {"rule": DIAGNOSTIC_DSR_RULE, "values": verdict.diagnostic_dsr},
        "diagnostics": diagnostics,
    }
    report_path = write_json_once(
        roots.reports / _slug(ctx, family) / f"{experiment}-{verdict.cell_trials_sha256[:12]}.json", report,
        root=roots.reports, roots=roots,
    )
    report_ref, report_sha = artifact(report_path)
    run_id = hashlib.sha256(f"{experiment}{evidence_sha}{spec_sha}{verdict.cell_trials_sha256}".encode()).hexdigest()[:16]
    record_verdict(roots, {
        "run_id": run_id, "evaluated_at": datetime.now(timezone.utc).isoformat(), "protocol_id": config.protocol_id,
        "protocol_config_sha256": ctx.protocol.config_sha256, "admission_scope": ADMISSION_SCOPE,
        "execution_id": roots.data.name, "route": unit.route, "strength": "" if unit.strength is None else unit.strength,
        "seed": "" if unit.seed is None else unit.seed, "cell_family": family, "experiment_id": experiment,
        "code_snapshot_sha256": ctx.code_hash, "data_snapshot_sha256": ctx.data_hash, "evidence_sha256": evidence_sha,
        "experiment_ledger_sha256": verdict.ledger_sha256, "trial_count": verdict.trial_count,
        "valid_trial_sharpes": verdict.valid_trial_sharpes, "layer_a_pass": str(verdict.layer_a).lower(),
        "layer_b_pass": str(verdict.layer_b).lower(), "main_pass": str(verdict.main).lower(),
        "failed_main_gates": "|".join(verdict.failed_main), "report_path": report_ref, "report_sha256": report_sha,
    })
    overlap = [w["mean_jaccard"] for w in diagnostics.get("top30_overlap", []) if w["mean_jaccard"] is not None]  # type: ignore[union-attr]
    return UnitOutcome(
        route=unit.route, strength=unit.strength, seed=unit.seed, cell_family=family, experiment_id=experiment,
        status="JUDGED", main=verdict.main, layer_a=verdict.layer_a, layer_b=verdict.layer_b,
        failed_main=verdict.failed_main, report_path=report_ref,
        diagnostics={"mean_top30_jaccard": sum(overlap) / len(overlap) if overlap else None,
                     "transmission": diagnostics.get("transmission")},
    )


def run_calibration(ctx: RunContext, roots: OutputRoots, *, noise_seeds: int) -> dict[str, object]:
    outcomes: list[UnitOutcome] = []
    timings: dict[str, float] = {}
    for cell in plan_cells(ctx.protocol, noise_seeds):
        started = time.monotonic()
        evaluated = [(unit, *evaluate_unit(ctx, roots, unit)) for unit in cell]
        for unit, experiment, evidence_path, diagnostics, error_type in evaluated:
            if evidence_path is None:
                family = cell_family(ctx.protocol.config, unit.route, unit.strength)
                outcomes.append(UnitOutcome(unit.route, unit.strength, unit.seed, family, experiment, "EVIDENCE_ERROR", error_type=error_type))
            else:
                outcomes.append(judge_cell(ctx, roots, unit, experiment, evidence_path, diagnostics))
        timings[cell_family(ctx.protocol.config, cell[0].route, cell[0].strength)] = round(time.monotonic() - started, 3)
        # 用完即释放：R1/R2 同强度格子共用的面板、R4/R5 面板；R3 留给 N2 打乱。
        finished = ("signal:blend:",) if cell[0].route == "R2" else (f"signal:{cell[0].route}",) if cell[0].route in {"R4", "R5"} else ()
        for key in [key for key in ctx.cache if key.startswith(finished)] if finished else []:
            del ctx.cache[key]
    summary = summarize(ctx.protocol, outcomes, planned_noise_seeds=noise_seeds)
    document = {
        "schema_version": 1, "admission_scope": ADMISSION_SCOPE, "protocol_id": ctx.protocol.config.protocol_id,
        "protocol_config_sha256": ctx.protocol.config_sha256, "protocol_document_sha256": ctx.protocol.document_sha256,
        "execution_id": roots.data.name, "code_snapshot_sha256": ctx.code_hash, "data_snapshot_sha256": ctx.data_hash,
        "baseline_fingerprint": baseline_fingerprint(ctx.baselines),
        "summary": summary, "units": [asdict(outcome) for outcome in outcomes],
    }
    # 汇总只含确定性内容，同绑定复跑逐字节一致；耗时每次执行单独落一份。
    write_json_once(roots.reports / "summary.json", document, root=roots.reports, roots=roots)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    write_json_once(roots.reports / f"timings-{stamp}.json", {"cell_seconds": timings}, root=roots.reports, roots=roots)
    return document


def baseline_fingerprint(baselines: list[BaselineWindow]) -> dict[str, str]:
    """六窗基线只训一次：以预测值逐位哈希绑定到每份汇总，复核时可证明全部评估共用同一基线。"""
    result = {}
    for baseline in baselines:
        frame = baseline.predictions.sort_index().reset_index()
        payload = pd.util.hash_pandas_object(frame, index=False).to_numpy().tobytes()
        result[baseline.window.name] = hashlib.sha256(payload).hexdigest()
    return result


