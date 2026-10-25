"""重判单位的 g1-v2 证据、记账与判定（协议 v2 §3）。

复现通过的原始因子 → PIT 中性化 → 与标定相同的组合证据与逐日配对序列 → 实验总账（真实家族，计入 N）→ 本家族全部记账后逐个按 g1-v2 判定
→ `ledger/factor_admissions_v2.csv` 与 `logs/g1-v2/`。v1 账本与 `logs/g1/` 一律拒写。
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import pandas as pd

from shaiwei.config import Settings
from shaiwei.ledger import FACTOR_ADMISSIONS, append_experiment, portable_artifact_path, sha256_file
from shaiwei.research.factor_portfolio import FactorPortfolioError, backtest_signal
from shaiwei.research.g1 import G1Error, periodic_sharpe
from shaiwei.research.g1_calibration import controls
from shaiwei.research.g1_calibration.evidence import build_portfolio_evidence
from shaiwei.research.g1_pipeline import BaselineWindow, G1PipelineError, ResearchData, _max_library_correlation, _write_json_once
from shaiwei.research.g1_v2 import G1V2Spec, paired_differences
from shaiwei.research.g1_v2_rejudge.judge import RejudgeIsolationError, RejudgeRoots, _existing, judge_unit
from shaiwei.research.g1_v2_rejudge.protocol import RejudgeIdentity
from shaiwei.research.g1_v2_rejudge.sources import Reconstruction

EVIDENCE_ERRORS = (G1PipelineError, FactorPortfolioError, G1Error, controls.CalibrationError)


@dataclass
class RejudgeContext:
    settings: Settings
    identity: RejudgeIdentity
    spec: G1V2Spec
    research: ResearchData
    baselines: list[BaselineWindow]
    code_hash: str
    data_hash: str
    backtest: Callable[..., object] = backtest_signal
    residuals: dict[str, pd.Series] = field(default_factory=dict)

    @property
    def min_cross_section(self) -> int:
        return self.settings.alphagen_benchmark.min_cross_section


def _dated(series: pd.Series) -> dict[str, float]:
    return {pd.Timestamp(day).date().isoformat(): float(value) for day, value in series.items()}


def experiment_id(ctx: RejudgeContext, family: str, v1_candidate: str) -> str:
    key = f"{ctx.identity.config.protocol_id}|{family}|{v1_candidate}|{ctx.code_hash}|{ctx.data_hash}"
    return hashlib.sha256(key.encode()).hexdigest()[:12]


def _record_experiment(ctx: RejudgeContext, roots: RejudgeRoots, item: Reconstruction, experiment: str, params: dict[str, object], result: dict[str, object]) -> None:
    """同绑定复跑只复用，不追加第二行；内容不同即失败关闭。"""
    if existing := _existing(roots.experiments, "experiment_id", experiment):
        if json.loads(existing["params_json"]) != params or existing["feature_or_formula"] != item.candidate.formula:
            raise RejudgeIsolationError(f"existing re-judge experiment differs: {experiment}")
        return
    append_experiment(
        path=roots.experiments, experiment_id=experiment, parent_experiment_id=item.candidate.candidate_experiment_id,
        ts=datetime.now(timezone.utc).isoformat(), candidate_source="g1-v2-rejudge", model_or_engine="Alpha158 + rank blend (g1-v2 re-judge)",
        engine_version=ctx.identity.config.protocol_id, seed="", prompt_hash="", code_sha256=ctx.code_hash,
        data_snapshot_sha256=ctx.data_hash, feature_or_formula=item.candidate.formula, params_json=params,
        train_period=f"{ctx.spec.discovery.start}~{ctx.spec.discovery.end}", valid_period="W1-W6 + frozen stress periods",
        result_json=result, admitted=False, reject_reason="g1-v2 re-judge evidence; pending g1-v2 judge",
    )


def evaluate_unit(ctx: RejudgeContext, roots: RejudgeRoots, item: Reconstruction) -> tuple[str, Path | None, str]:
    family, candidate, v1 = item.family, item.candidate, item.v1
    experiment = experiment_id(ctx, family, candidate.candidate_experiment_id)
    params: dict[str, object] = {
        "g1_research_family": family, "attempt_stage": "g1_v2_rejudge", "rejudge_protocol_id": ctx.identity.config.protocol_id,
        "rejudge_of": candidate.candidate_experiment_id, "supersedes": [s.candidate_experiment_id for s in candidate.supersedes],
        "expression_tokens": v1["complexity"]["expression_tokens"], "ast_nodes": v1["complexity"]["ast_nodes"],  # type: ignore[index]
        "factor_blend_weight": ctx.spec.thresholds.factor_blend_weight, "neutralization": "pit_support",
    }
    try:
        if item.raw is None or item.raw.dropna().empty:  # 空因子在共用中性化里会抛裸 ValueError，单次正式执行中须记为证据错误
            raise controls.CalibrationError("reconstructed raw factor has no finite values")
        residual, daily_ic = controls.neutralize_pit(item.raw, ctx.research, min_cross_section=ctx.min_cross_section)
        portfolio = build_portfolio_evidence(
            ctx.settings, factor=residual, factor_daily_ic=daily_ic, labels=ctx.research.labels, baselines=ctx.baselines,
            mode="blend", backtest=ctx.backtest,  # type: ignore[arg-type]
        )
        paired = {
            "candidate_score_rank_ic": _dated(portfolio.candidate_score_ic), "baseline_score_rank_ic": _dated(portfolio.baseline_score_ic),
            "candidate_daily_net_excess": _dated(portfolio.candidate_daily_excess), "baseline_daily_net_excess": _dated(portfolio.baseline_daily_excess),
        }
        increment_ir = periodic_sharpe(
            paired_differences(paired["candidate_score_rank_ic"], paired["baseline_score_rank_ic"]), minimum=ctx.spec.thresholds.min_observations
        )
    except EVIDENCE_ERRORS as error:
        _record_experiment(ctx, roots, item, experiment, params, {"error_type": type(error).__name__, "error": str(error)[:300]})
        return experiment, None, type(error).__name__
    ctx.residuals[experiment] = residual
    directory = roots.data / family / experiment
    panel = directory / "factor_panel.parquet"
    if not panel.is_file():
        panel.parent.mkdir(parents=True, exist_ok=True)
        residual.rename("factor").reset_index().to_parquet(panel, index=False)
    tests = {
        "schema_version": 2, "candidate_experiment_id": experiment, "code_snapshot_sha256": ctx.code_hash,
        "data_snapshot_sha256": ctx.data_hash, "expression": candidate.formula, "pit_sentinel_pass": v1["pit_sentinel_pass"],
        "shift_sentinel_pass": v1["shift_sentinel_pass"], "sentinel_basis": "v1 frozen definition (unchanged); see rejudge_of",
        "rejudge_of": candidate.candidate_experiment_id, "v1_evidence_sha256": candidate.v1_evidence_sha256,
        "reproduction": item.reproduction, "factor_panel_path": portable_artifact_path(panel), "factor_panel_sha256": sha256_file(panel),
    }
    test_path = _write_json_once(directory / "factor_tests.json", tests)
    related = tuple(f for f in ctx.identity.config.multiple_testing_families[family] if f != family)
    metrics = portfolio.metrics
    evidence = {
        "schema_version": 2, "candidate_experiment_id": experiment, "research_family": family,
        "multiple_testing_families": [family, *related] if related else [],
        "code_snapshot_sha256": ctx.code_hash, "data_snapshot_sha256": ctx.data_hash, "economic_rationale": v1["economic_rationale"],
        "complexity": v1["complexity"],
        "integrity": {
            "pit_sentinel_pass": v1["pit_sentinel_pass"], "shift_sentinel_pass": v1["shift_sentinel_pass"],
            "test_report_path": portable_artifact_path(test_path), "test_report_sha256": sha256_file(test_path),
            "max_library_abs_spearman": _max_library_correlation(residual, ctx.settings.runtime.data_root / "research" / "factor_library"),
        },
        "rank_ic": {"in_sample": portfolio.in_sample_ic, "oos_windows": portfolio.oos_windows, "daily_oos": portfolio.daily_oos},
        "stress_max_drawdown": portfolio.stress,
        "portfolio": {**{k: v for k, v in metrics.items() if k != "selection_sharpe"}, "daily_net_excess_returns": portfolio.daily_net_excess},
        "neutralization": "pit_support", **paired,
    }
    evidence_path = _write_json_once(directory / "g1_evidence.json", evidence)
    result = {**metrics, "selection_increment_ir": increment_ir, "factor_test_report_path": portable_artifact_path(test_path),
              "factor_test_report_sha256": sha256_file(test_path)}
    _record_experiment(ctx, roots, item, experiment, params, result)
    return experiment, evidence_path, ""


def pass_correlations(ctx: RejudgeContext, passed: list[str]) -> dict[str, float]:
    """PASS 定义两两 Spearman（共同键上合并计算），只报告，供后续入库去冗余。"""
    result = {}
    for i, left in enumerate(passed):
        for right in passed[i + 1:]:
            joined = pd.concat([ctx.residuals[left].rename("a"), ctx.residuals[right].rename("b")], axis=1, join="inner").dropna()
            value = float(joined["a"].corr(joined["b"], method="spearman")) if len(joined) > 2 else float("nan")
            result[f"{left}|{right}"] = value if math.isfinite(value) else None  # type: ignore[assignment]
    return result


def run_rejudge(ctx: RejudgeContext, roots: RejudgeRoots, reconstructions: dict[str, list[Reconstruction]]) -> dict[str, object]:
    units: list[dict[str, object]] = []
    for family in ctx.identity.config.family_order:
        items = reconstructions[family]
        if not all(item.reproduced for item in items):  # 复现门：整家族不过即 NOT_REEVALUATED，不评估、不记账
            units += [{"family": family, "v1_candidate": i.candidate.candidate_experiment_id, "status": "NOT_REEVALUATED",
                       "reproduction": i.reproduction} for i in items]
            continue
        evaluated = [(item, *evaluate_unit(ctx, roots, item)) for item in items]
        for item, experiment, evidence_path, error_type in evaluated:
            entry: dict[str, object] = {"family": family, "v1_candidate": item.candidate.candidate_experiment_id, "experiment_id": experiment,
                                        "supersedes": [s.candidate_experiment_id for s in item.candidate.supersedes]}
            if evidence_path is None:
                units.append({**entry, "status": "EVIDENCE_ERROR", "error_type": error_type})
                continue
            decision = judge_unit(ctx, roots, family, experiment, evidence_path)
            units.append({**entry, "status": decision["status"], "failed_gates": decision["failed_gates"],
                          "decision_id": decision["decision_id"], "report_path": decision["report_path"]})
    passed = [str(u["experiment_id"]) for u in units if u["status"] == "PASS"]
    summary = {
        "schema_version": 1, "protocol_id": ctx.identity.config.protocol_id, "execution_id": roots.data.name,
        "protocol_config_sha256": ctx.identity.config_sha256, "spec_sha256": ctx.identity.spec_sha256,
        "code_snapshot_sha256": ctx.code_hash, "data_snapshot_sha256": ctx.data_hash,
        "counts": {status: sum(u["status"] == status for u in units) for status in ("PASS", "REJECT", "NOT_REEVALUATED", "EVIDENCE_ERROR")},
        "units": units, "pass_correlations": pass_correlations(ctx, passed),
    }
    _write_json_once(roots.reports / "summary.json", summary)
    return summary


def admissions_header() -> str:
    with FACTOR_ADMISSIONS.open(newline="", encoding="utf-8") as handle:
        return ",".join(next(csv.reader(handle))) + "\n"
