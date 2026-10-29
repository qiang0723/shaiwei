"""TP-F-1 stage E: offline g1-v2 evidence for retained candidates, mechanical discovery selection, judgement.

Every completed response gets exactly one experiment row in the TP-F-1 family, so g1-v2 counts N as frozen
(all completed responses, failures and vetoes included). Retained candidates carry full evidence and a finite
`selection_increment_ir` (the DSR trial variance); only Top1/Top2 by discovery |RankIC| are judged.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, Mapping

import pandas as pd

from shaiwei.config import Settings
from shaiwei.ledger import append_llm_factor_experiment, portable_artifact_path, sha256_file
from shaiwei.research.factor_portfolio import FactorPortfolioError, backtest_signal
from shaiwei.research.g1 import G1Error, periodic_sharpe
from shaiwei.research.g1_calibration import controls
from shaiwei.research.g1_calibration.evidence import build_portfolio_evidence
from shaiwei.research.g1_pipeline import BaselineWindow, G1PipelineError, ResearchData, _max_library_correlation
from shaiwei.research.g1_v2 import G1V2Spec, paired_differences
from shaiwei.research.g1_v2_rejudge.judge import RejudgeRoots, judge_unit, write_json_once
from shaiwei.research.tp_f_1.contract import FAMILY, TPF1Error, TPF1Scope

EVIDENCE_ERRORS = (G1PipelineError, FactorPortfolioError, G1Error, controls.CalibrationError)


@dataclass
class EvaluationContext:
    settings: Settings
    scope: TPF1Scope
    spec: G1V2Spec
    spec_sha256: str
    research: ResearchData
    baselines: list[BaselineWindow]
    code_hash: str
    data_hash: str
    scope_sha256: str
    backtest: Callable[..., object] = backtest_signal
    expression_values: Callable[[str, object], pd.Series] = controls.raw_expression_values
    residuals: dict[str, pd.Series] = field(default_factory=dict)

    @property
    def judge_view(self) -> SimpleNamespace:
        """The attributes `judge_unit` reads: a single-family multiple-testing declaration for TP-F-1."""
        config = SimpleNamespace(multiple_testing_families={FAMILY: (FAMILY,)}, protocol_id=self.scope.document["protocol_id"])
        return SimpleNamespace(settings=self.settings, spec=self.spec, identity=SimpleNamespace(config=config, spec_sha256=self.spec_sha256))


def experiment_id(ctx: EvaluationContext, attempt_id: str) -> str:
    return hashlib.sha256(f"{ctx.scope.document['protocol_id']}|{ctx.scope_sha256}|{attempt_id}".encode()).hexdigest()[:12]


def _dated(series: pd.Series) -> dict[str, float]:
    return {pd.Timestamp(day).date().isoformat(): float(value) for day, value in series.items()}


def _record(ctx: EvaluationContext, roots: RejudgeRoots, attempt: Mapping[str, str], experiment: str, *,
            formula: str, params: dict[str, Any], result: dict[str, Any], reason: str) -> None:
    append_llm_factor_experiment(
        path=roots.experiments, experiment_id=experiment, parent_experiment_id="", ts=datetime.now(timezone.utc).isoformat(),
        candidate_source="tp-f-1-llm", model_or_engine="Alpha158 + rank blend (g1-v2)", engine_version=ctx.scope.document["protocol_id"],
        seed="", prompt_hash=attempt["prompt_sha256"], code_sha256=ctx.code_hash, data_snapshot_sha256=ctx.data_hash,
        feature_or_formula=formula, params_json={"g1_research_family": FAMILY, "attempt_id": attempt["attempt_id"],
                                                 "attempt_ordinal": int(attempt["ordinal"]), **params},
        train_period=f"{ctx.spec.discovery.start}~{ctx.spec.discovery.end}", valid_period="W1-W6 + frozen stress periods",
        result_json=result, admitted=False, reject_reason=reason,
    )


def record_non_evaluated(ctx: EvaluationContext, roots: RejudgeRoots, attempt: Mapping[str, str], status: str) -> str:
    """Failed, duplicate or vetoed responses still enter the family (N counts every completed response)."""
    experiment = experiment_id(ctx, attempt["attempt_id"])
    _record(ctx, roots, attempt, experiment, formula=attempt["canonical_expression"], params={"attempt_stage": "tp_f_1_generation"},
            result={"status": status}, reason=status)
    return experiment


def evaluate_candidate(ctx: EvaluationContext, roots: RejudgeRoots, attempt: Mapping[str, str], candidate: Mapping[str, Any],
                       audit: Mapping[str, Any]) -> dict[str, Any]:
    """Full g1-v2 evidence for one retained candidate; returns its discovery selection statistic."""
    experiment = experiment_id(ctx, attempt["attempt_id"])
    formula = str(candidate["normalized_expression"])
    # 复杂度只进证据（complexity 门读证据）；总账写入口拒绝含 "token" 的键名
    params = {"attempt_stage": "tp_f_1_evaluation", "candidate_id": candidate["candidate_id"], "neutralization": "pit_support",
              "factor_blend_weight": ctx.spec.thresholds.factor_blend_weight}
    try:
        raw = ctx.expression_values(formula, ctx.research.stock_data)
        if raw is None or raw.dropna().empty:
            raise controls.CalibrationError("candidate raw factor has no finite values")
        residual, daily_ic = controls.neutralize_pit(raw, ctx.research, min_cross_section=ctx.settings.alphagen_benchmark.min_cross_section)
        portfolio = build_portfolio_evidence(ctx.settings, factor=residual, factor_daily_ic=daily_ic, labels=ctx.research.labels,
                                             baselines=ctx.baselines, mode="blend", backtest=ctx.backtest)  # type: ignore[arg-type]
        paired = {"candidate_score_rank_ic": _dated(portfolio.candidate_score_ic), "baseline_score_rank_ic": _dated(portfolio.baseline_score_ic),
                  "candidate_daily_net_excess": _dated(portfolio.candidate_daily_excess),
                  "baseline_daily_net_excess": _dated(portfolio.baseline_daily_excess)}
        increment_ir = periodic_sharpe(paired_differences(paired["candidate_score_rank_ic"], paired["baseline_score_rank_ic"]),
                                       minimum=ctx.spec.thresholds.min_observations)
    except EVIDENCE_ERRORS as error:
        _record(ctx, roots, attempt, experiment, formula=formula, params=params,
                result={"status": "EVIDENCE_ERROR", "error_type": type(error).__name__, "error": str(error)[:300]}, reason="EVIDENCE_ERROR")
        return {"experiment_id": experiment, "candidate_id": candidate["candidate_id"], "status": "EVIDENCE_ERROR", "error_type": type(error).__name__}
    ctx.residuals[experiment] = residual
    directory = roots.data / experiment
    panel = directory / "factor_panel.parquet"
    panel.parent.mkdir(parents=True, exist_ok=True)
    residual.rename("factor").reset_index().to_parquet(panel, index=False)
    tests = {"schema_version": 2, "candidate_experiment_id": experiment, "code_snapshot_sha256": ctx.code_hash,
             "data_snapshot_sha256": ctx.data_hash, "expression": formula, "pit_sentinel_pass": bool(audit["pit_sentinel_pass"]),
             "shift_sentinel_pass": bool(audit["shift_sentinel_pass"]), "factor_panel_path": portable_artifact_path(panel),
             "factor_panel_sha256": sha256_file(panel)}
    test_path = write_json_once(directory / "factor_tests.json", tests)
    evidence = {
        "schema_version": 2, "candidate_experiment_id": experiment, "research_family": FAMILY, "multiple_testing_families": [],
        "code_snapshot_sha256": ctx.code_hash, "data_snapshot_sha256": ctx.data_hash,
        "economic_rationale": str(candidate["economic_rationale"]),
        "complexity": {"expression_tokens": audit["expression_tokens"], "ast_nodes": audit["ast_nodes"]},
        "integrity": {"pit_sentinel_pass": bool(audit["pit_sentinel_pass"]), "shift_sentinel_pass": bool(audit["shift_sentinel_pass"]),
                      "test_report_path": portable_artifact_path(test_path), "test_report_sha256": sha256_file(test_path),
                      "max_library_abs_spearman": _max_library_correlation(residual, ctx.settings.runtime.data_root / "research" / "factor_library")},
        "rank_ic": {"in_sample": portfolio.in_sample_ic, "oos_windows": portfolio.oos_windows, "daily_oos": portfolio.daily_oos},
        "stress_max_drawdown": portfolio.stress,
        "portfolio": {**{k: v for k, v in portfolio.metrics.items() if k != "selection_sharpe"},
                      "daily_net_excess_returns": portfolio.daily_net_excess},
        "neutralization": "pit_support", **paired,
    }
    evidence_path = write_json_once(directory / "g1_evidence.json", evidence)
    result = {**portfolio.metrics, "status": "EVALUATED", "selection_increment_ir": increment_ir,
              "discovery_mean_daily_rank_ic": portfolio.in_sample_ic, "factor_test_report_path": portable_artifact_path(test_path),
              "factor_test_report_sha256": sha256_file(test_path)}
    _record(ctx, roots, attempt, experiment, formula=formula, params=params, result=result, reason="pending g1-v2 judge")
    return {"experiment_id": experiment, "candidate_id": candidate["candidate_id"], "status": "EVALUATED",
            "evidence_path": evidence_path, "discovery_abs_rank_ic": abs(float(portfolio.in_sample_ic)),
            "canonical_sha256": candidate["canonical_sha256"]}


def select_top_two(evaluated: list[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    """Addendum A1: |discovery mean daily RankIC| descending; ties by lower canonical sha; in-sample only."""
    ranked = sorted((item for item in evaluated if item["status"] == "EVALUATED"),
                    key=lambda item: (-float(item["discovery_abs_rank_ic"]), str(item["canonical_sha256"])))
    return ranked[:2]


def run_evaluation(ctx: EvaluationContext, roots: RejudgeRoots, *, attempts: list[Mapping[str, str]],
                   candidates: Mapping[str, Mapping[str, Any]], audits: Mapping[str, Mapping[str, Any]],
                   decisions: Mapping[str, str]) -> dict[str, Any]:
    """`attempts`: every completed response row; `decisions`: the recorded blind-review ruling per candidate id."""
    if {cid for cid in candidates} != set(decisions):
        raise TPF1Error("TP-F-1 blind-review decisions do not cover exactly the qualified candidates")
    evaluated: list[dict[str, Any]] = []
    for attempt in sorted(attempts, key=lambda row: int(row["ordinal"])):
        cid = attempt["candidate_id"]
        if attempt["status"] != "QUALIFIED":
            record_non_evaluated(ctx, roots, attempt, attempt["status"])
        elif decisions[cid] != "RETAIN":
            record_non_evaluated(ctx, roots, attempt, f"VETOED_{decisions[cid]}")
        else:
            evaluated.append(evaluate_candidate(ctx, roots, attempt, candidates[cid], audits[cid]))
    selected = select_top_two(evaluated)
    judged = []
    for rank, item in enumerate(selected, start=1):
        decision = judge_unit(ctx.judge_view, roots, FAMILY, str(item["experiment_id"]), Path(item["evidence_path"]))
        judged.append({"rank": rank, "candidate_id": item["candidate_id"], "experiment_id": item["experiment_id"],
                       "status": decision["status"], "failed_gates": decision["failed_gates"], "decision_id": decision["decision_id"],
                       "report_path": decision["report_path"]})
    if any(item["status"] == "PASS" for item in judged):
        verdict = "GO_SEPARATE_ADMISSION_OR_PAPER_PROTOCOL_PROPOSAL_ONLY"
    else:
        verdict = "REJECT_TP_F_AND_CLOSE"
    summary = {
        "schema_version": "tp-f-1-evaluation-summary-v1", "scope_sha256": ctx.scope_sha256, "protocol_sha256": ctx.scope.sha256,
        "addendum_sha256": ctx.scope.addendum_sha256, "code_snapshot_sha256": ctx.code_hash, "data_snapshot_sha256": ctx.data_hash,
        "family": FAMILY, "completed_responses": len(attempts),
        "evaluated": [{key: value for key, value in item.items() if key != "evidence_path"} for item in evaluated],
        "selected": [item["candidate_id"] for item in selected], "judged": judged, "verdict": verdict,
        "strategy_effective": "NOT_EVALUATED_BEYOND_G1_V2", "production_authorization": "none",
    }
    write_json_once(roots.reports / "evaluation_summary.json", summary)
    return summary
