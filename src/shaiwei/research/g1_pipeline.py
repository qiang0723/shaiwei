"""Promote bounded GP candidates, build real G1 evidence, and invoke the frozen judge."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import torch

from shaiwei.backtest.baseline import train_window_predictions
from shaiwei.backtest.qlib_runtime import initialize_qlib
from shaiwei.benchmark.alphagen_cpu import _load_exposures, stock_data_effective_start
from shaiwei.benchmark.fitness import neutralized_factor_values
from shaiwei.config import PROJECT_ROOT, EvaluationWindow, Settings, load
from shaiwei.ledger import (
    EXPERIMENTS,
    append_experiment,
    ingest_snapshot_sha256,
    portable_artifact_path,
    sha256_file,
)
from shaiwei.provenance import code_snapshot_sha256
from shaiwei.research.alphagen_expression import ExpressionAudit, audit_expression, parse_safe_expression
from shaiwei.research.factor_portfolio import (
    SignalBacktest,
    augment_signal,
    backtest_signal,
    daily_rank_ic,
    icir,
)
from shaiwei.research.g1 import AdmissionDecision, evaluate_g1, periodic_sharpe


class G1PipelineError(RuntimeError):
    pass


@dataclass(frozen=True)
class ResearchData:
    stock_data: object
    labels: pd.Series
    exposures: pd.DataFrame


@dataclass(frozen=True)
class BaselineWindow:
    window: EvaluationWindow
    predictions: pd.Series
    labels: pd.Series
    daily_ic: pd.Series
    backtest: SignalBacktest


@dataclass(frozen=True)
class CandidateArtifacts:
    experiment_id: str
    expression: str
    evidence_path: Path
    test_report_path: Path
    factor_panel_path: Path


def _canonical_json(document: dict[str, object]) -> str:
    return json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _write_json_once(path: Path, document: dict[str, object]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = _canonical_json(document)
    if path.is_file():
        if path.read_text(encoding="utf-8") != payload:
            raise G1PipelineError(f"existing immutable JSON differs: {path}")
        return path
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_text(payload, encoding="utf-8")
        with temporary.open("rb") as handle:
            os.fsync(handle.fileno())
        os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return path


def _write_factor_panel(path: Path, factor: pd.Series, labels: pd.Series) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    panel = pd.concat([factor.rename("factor"), labels.rename("label")], axis=1, join="inner").reset_index()
    if panel.empty:
        raise G1PipelineError("factor panel is empty")
    if path.is_file():
        existing = pd.read_parquet(path)
        if not existing.equals(panel):
            raise G1PipelineError(f"existing immutable factor panel differs: {path}")
        return path
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        panel.to_parquet(temporary, index=False)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return path


def _series(frame: pd.DataFrame, column: str) -> pd.Series:
    value = frame[column]
    if not isinstance(value.index, pd.MultiIndex):
        raise G1PipelineError(f"{column} must use a qlib MultiIndex")
    value.index = value.index.set_names(["datetime", "instrument"])
    return value.sort_index()


def load_research_data(settings: Settings) -> ResearchData:
    initialize_qlib(settings)
    vendor = PROJECT_ROOT / "vendor" / "alphagen"
    if str(vendor) not in sys.path:
        sys.path.insert(0, str(vendor))
    from alphagen.data.expression import Ref
    from alphagen_generic.features import open_
    from alphagen_qlib import stock_data as alphagen_stock_data
    from alphagen_qlib.stock_data import StockData

    alphagen_stock_data._QLIB_INITIALIZED = True
    start = min(
        settings.g1_admission.discovery_start,
        *(period.start for period in settings.evaluation.stress_periods),
    )
    end = max(
        *(window.test_end for window in settings.evaluation.g0_windows),
        *(period.end for period in settings.evaluation.stress_periods),
    )
    max_backtrack_days = 100
    effective_start = stock_data_effective_start(start, max_backtrack_days)
    data = StockData(
        settings.baseline.instrument,
        effective_start.isoformat(),
        end.isoformat(),
        max_backtrack_days=max_backtrack_days,
        max_future_days=settings.backtest.rebalance_days + 1,
        device=torch.device("cpu"),
    )
    target = Ref(open_, -(settings.backtest.rebalance_days + 1)) / Ref(open_, -1) - 1
    label_frame = data.make_dataframe(target.evaluate(data), columns=["label"])
    labels = _series(label_frame, "label")
    instruments = set(labels.index.get_level_values("instrument").dropna().astype(str))
    exposures = _load_exposures(instruments, effective_start, end)
    return ResearchData(stock_data=data, labels=labels, exposures=exposures)


def evaluate_factor_panel(
    expression_text: str,
    research: ResearchData,
    *,
    min_cross_section: int,
) -> tuple[pd.Series, pd.Series]:
    expression = parse_safe_expression(expression_text)
    frame = research.stock_data.make_dataframe(expression.evaluate(research.stock_data), columns=["factor"])
    factor = _series(frame, "factor")
    observations = (
        factor.rename("factor")
        .reset_index()
        .merge(research.labels.rename("label").reset_index(), on=["datetime", "instrument"])
        .rename(columns={"datetime": "trade_date"})
        .merge(research.exposures, on=["trade_date", "instrument"])
    )
    residual = neutralized_factor_values(observations, min_cross_section=min_cross_section)
    residual.index = residual.index.set_names(["datetime", "instrument"])
    daily_ic = daily_rank_ic(residual, research.labels)
    if daily_ic.empty:
        raise G1PipelineError("candidate has no valid neutralized daily RankIC")
    return residual.sort_index(), daily_ic.sort_index()


def build_baseline_windows(settings: Settings, labels: pd.Series) -> list[BaselineWindow]:
    windows = []
    for window in settings.evaluation.g0_windows:
        predictions, _ = train_window_predictions(settings, window)
        if not isinstance(predictions, pd.Series):
            raise G1PipelineError("baseline prediction must be a Series")
        predictions.index = predictions.index.set_names(["datetime", "instrument"])
        window_labels = labels.loc[
            (labels.index.get_level_values("datetime") >= pd.Timestamp(window.test_start))
            & (labels.index.get_level_values("datetime") <= pd.Timestamp(window.test_end))
        ]
        window_ic = daily_rank_ic(predictions, window_labels)
        result = backtest_signal(
            settings,
            predictions,
            start_time=window.test_start.isoformat(),
            end_time=window.test_end.isoformat(),
        )
        windows.append(BaselineWindow(window, predictions, window_labels, window_ic, result))
    return windows


def _compound(series: pd.Series) -> float:
    values = pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    if values.empty or (values <= -1).any():
        raise G1PipelineError("cannot compound empty or <=-100% excess returns")
    return float((1.0 + values).prod() - 1.0)


def _stress_drawdown(
    factor: pd.Series,
    labels: pd.Series,
    *,
    start: pd.Timestamp,
    end: pd.Timestamp,
    topk: int,
    rebalance_days: int,
    roundtrip_cost: float,
) -> float:
    joined = pd.concat([factor.rename("factor"), labels.rename("label")], axis=1, join="inner").dropna()
    dates = sorted(
        date
        for date in joined.index.get_level_values("datetime").unique()
        if start <= pd.Timestamp(date) <= end
    )
    interval_returns = []
    for trade_date in dates[::rebalance_days]:
        cross_section = joined.xs(trade_date, level="datetime").dropna()
        if len(cross_section) < topk:
            continue
        selected = cross_section.nlargest(topk, "factor")
        interval_returns.append(float(selected["label"].mean() - roundtrip_cost))
    if len(interval_returns) < 2 or any(value <= -1 for value in interval_returns):
        raise G1PipelineError(f"stress period {start.date()}..{end.date()} lacks usable returns")
    nav = pd.Series(1.0 + np.asarray(interval_returns)).cumprod()
    return float(-(nav / nav.cummax() - 1.0).min())


def _max_library_correlation(factor: pd.Series, library_root: Path) -> float:
    correlations = []
    if not library_root.is_dir():
        return 0.0
    for path in sorted(library_root.glob("*.parquet")):
        frame = pd.read_parquet(path)
        required = {"datetime", "instrument", "factor"}
        if missing := required - set(frame.columns):
            raise G1PipelineError(f"factor library artifact {path} missing {sorted(missing)}")
        library = frame.set_index(["datetime", "instrument"])["factor"]
        joined = pd.concat([factor.rename("candidate"), library.rename("library")], axis=1).dropna()
        if len(joined) >= 252:
            correlation = joined["candidate"].corr(joined["library"], method="spearman")
            if math.isfinite(float(correlation)):
                correlations.append(abs(float(correlation)))
    return max(correlations, default=0.0)


def _existing_experiment(experiment_id: str) -> dict[str, str] | None:
    with EXPERIMENTS.open(newline="", encoding="utf-8") as handle:
        rows = [row for row in csv.DictReader(handle) if row["experiment_id"] == experiment_id]
    if len(rows) > 1:
        raise G1PipelineError(f"duplicate deterministic experiment ID: {experiment_id}")
    return rows[0] if rows else None


def _candidate_experiment_id(
    family: str,
    expression: str,
    code_hash: str,
    data_hash: str,
) -> str:
    return hashlib.sha256(f"{family}|{expression}|{code_hash}|{data_hash}|portfolio-v1".encode()).hexdigest()[:12]


def _window_values(daily_ic: pd.Series, settings: Settings) -> dict[str, float]:
    result = {}
    for window in settings.evaluation.g0_windows:
        values = daily_ic.loc[
            (daily_ic.index >= pd.Timestamp(window.test_start))
            & (daily_ic.index <= pd.Timestamp(window.test_end))
        ]
        if len(values) < 60:
            raise G1PipelineError(f"{window.name} has fewer than 60 daily IC observations")
        result[window.name] = float(values.mean())
    return result


def evaluate_candidate(
    settings: Settings,
    *,
    expression: str,
    family: str,
    benchmark_report: Path,
    audit: ExpressionAudit,
    research: ResearchData,
    factor: pd.Series,
    factor_daily_ic: pd.Series,
    baselines: list[BaselineWindow],
    output_root: Path,
    rationale: str,
) -> CandidateArtifacts:
    code_hash = code_snapshot_sha256()
    data_hash = ingest_snapshot_sha256()
    experiment_id = _candidate_experiment_id(family, expression, code_hash, data_hash)
    direction_period = factor_daily_ic.loc[
        (factor_daily_ic.index >= pd.Timestamp(settings.g1_admission.discovery_start))
        & (factor_daily_ic.index <= pd.Timestamp(settings.g1_admission.discovery_end))
    ]
    if len(direction_period) < settings.g1_admission.min_observations:
        raise G1PipelineError("discovery period lacks the frozen minimum daily IC observations")
    in_sample_ic = float(direction_period.mean())
    if in_sample_ic == 0:
        raise G1PipelineError("candidate discovery RankIC is zero")
    direction = 1.0 if in_sample_ic > 0 else -1.0
    oriented_factor = direction * factor

    baseline_daily_ic = []
    candidate_daily_ic = []
    baseline_returns = []
    candidate_returns = []
    cost_2x_returns = []
    slippage_2x_returns = []
    baseline_turnover = 0.0
    candidate_turnover = 0.0
    for baseline in baselines:
        augmented = augment_signal(
            baseline.predictions,
            oriented_factor,
            factor_weight=settings.g1_admission.factor_blend_weight,
        )
        candidate_ic = daily_rank_ic(augmented, baseline.labels)
        normal = backtest_signal(
            settings,
            augmented,
            start_time=baseline.window.test_start.isoformat(),
            end_time=baseline.window.test_end.isoformat(),
        )
        cost_2x = backtest_signal(
            settings,
            augmented,
            start_time=baseline.window.test_start.isoformat(),
            end_time=baseline.window.test_end.isoformat(),
            cost_multiplier=2.0,
        )
        slippage_2x = backtest_signal(
            settings,
            augmented,
            start_time=baseline.window.test_start.isoformat(),
            end_time=baseline.window.test_end.isoformat(),
            extra_open_cost=settings.g1_admission.slippage_stress_extra_each_side,
            extra_close_cost=settings.g1_admission.slippage_stress_extra_each_side,
        )
        baseline_daily_ic.append(baseline.daily_ic)
        candidate_daily_ic.append(candidate_ic)
        baseline_returns.append(baseline.backtest.daily_excess)
        candidate_returns.append(normal.daily_excess)
        cost_2x_returns.append(cost_2x.daily_excess)
        slippage_2x_returns.append(slippage_2x.daily_excess)
        baseline_turnover += baseline.backtest.turnover
        candidate_turnover += normal.turnover

    baseline_ic_series = pd.concat(baseline_daily_ic).sort_index()
    candidate_ic_series = pd.concat(candidate_daily_ic).sort_index()
    baseline_return_series = pd.concat(baseline_returns).sort_index()
    candidate_return_series = pd.concat(candidate_returns).sort_index()
    cost_2x_series = pd.concat(cost_2x_returns).sort_index()
    slippage_2x_series = pd.concat(slippage_2x_returns).sort_index()
    selection_sharpe = periodic_sharpe(
        candidate_return_series.tolist(),
        minimum=settings.g1_admission.min_observations,
    )
    stress = {
        period.name: _stress_drawdown(
            oriented_factor,
            research.labels,
            start=pd.Timestamp(period.start),
            end=pd.Timestamp(period.end),
            topk=settings.backtest.topk,
            rebalance_days=settings.backtest.rebalance_days,
            roundtrip_cost=settings.backtest.open_cost + settings.backtest.close_cost,
        )
        for period in settings.evaluation.stress_periods
    }

    directory = output_root / family / experiment_id
    factor_panel_path = _write_factor_panel(
        directory / "factor_panel.parquet",
        factor,
        research.labels,
    )
    test_report = {
        "schema_version": 1,
        "candidate_experiment_id": experiment_id,
        "code_snapshot_sha256": code_hash,
        "data_snapshot_sha256": data_hash,
        "expression": expression,
        "normalized_expression": audit.normalized_expression,
        "pit_sentinel_pass": audit.pit_sentinel_pass,
        "shift_sentinel_pass": audit.shift_sentinel_pass,
        "max_lookback_days": audit.max_lookback_days,
        "required_backtrack_days": audit.required_backtrack_days,
        "shift_compared_values": audit.compared_values,
        "factor_panel_path": portable_artifact_path(factor_panel_path),
        "factor_panel_sha256": sha256_file(factor_panel_path),
        "factor_panel_rows": int(pq.read_metadata(factor_panel_path).num_rows),
    }
    test_report_path = _write_json_once(directory / "factor_tests.json", test_report)
    metrics = {
        "selection_sharpe": selection_sharpe,
        "baseline_net_icir": icir(baseline_ic_series),
        "candidate_net_icir": icir(candidate_ic_series),
        "baseline_net_excess": _compound(baseline_return_series),
        "candidate_net_excess": _compound(candidate_return_series),
        "cost_2x_net_excess": _compound(cost_2x_series),
        "slippage_2x_net_excess": _compound(slippage_2x_series),
        "baseline_turnover": baseline_turnover,
        "candidate_turnover": candidate_turnover,
    }
    params = {
        "g1_research_family": family,
        "expression_tokens": audit.expression_tokens,
        "ast_nodes": audit.ast_nodes,
        "attempt_stage": "portfolio_evaluation",
        "factor_blend_weight": settings.g1_admission.factor_blend_weight,
        "benchmark_report_sha256": sha256_file(benchmark_report),
    }
    if existing := _existing_experiment(experiment_id):
        if (
            existing["feature_or_formula"] != expression
            or existing["code_sha256"] != code_hash
            or existing["data_snapshot_sha256"] != data_hash
            or json.loads(existing["params_json"]) != params
            or not math.isclose(
                float(json.loads(existing["result_json"])["selection_sharpe"]),
                selection_sharpe,
                rel_tol=1e-12,
                abs_tol=1e-15,
            )
        ):
            raise G1PipelineError("existing deterministic candidate experiment differs")
    else:
        append_experiment(
            experiment_id=experiment_id,
            parent_experiment_id="",
            candidate_source="AlphaGen-GP-G1",
            model_or_engine="AlphaGen GP + Alpha158 rank blend",
            engine_version="g1-evidence-v1",
            seed=settings.alphagen_benchmark.seed,
            prompt_hash="",
            code_sha256=code_hash,
            data_snapshot_sha256=data_hash,
            feature_or_formula=expression,
            params_json=params,
            train_period=(
                f"{settings.g1_admission.discovery_start}~{settings.g1_admission.discovery_end}"
            ),
            valid_period="W1-W6 + frozen stress periods",
            result_json={
                **metrics,
                "factor_test_report_path": portable_artifact_path(test_report_path),
                "factor_test_report_sha256": sha256_file(test_report_path),
            },
            admitted=False,
            reject_reason="G1 evidence candidate; pending frozen judge",
        )

    daily_oos = factor_daily_ic.loc[
        (factor_daily_ic.index >= pd.Timestamp(min(w.test_start for w in settings.evaluation.g0_windows)))
        & (factor_daily_ic.index <= pd.Timestamp(max(w.test_end for w in settings.evaluation.g0_windows)))
    ]
    evidence = {
        "schema_version": 1,
        "candidate_experiment_id": experiment_id,
        "research_family": family,
        "code_snapshot_sha256": code_hash,
        "data_snapshot_sha256": data_hash,
        "economic_rationale": rationale,
        "complexity": {
            "expression_tokens": audit.expression_tokens,
            "ast_nodes": audit.ast_nodes,
        },
        "integrity": {
            "pit_sentinel_pass": audit.pit_sentinel_pass,
            "shift_sentinel_pass": audit.shift_sentinel_pass,
            "test_report_path": portable_artifact_path(test_report_path),
            "test_report_sha256": sha256_file(test_report_path),
            "max_library_abs_spearman": _max_library_correlation(
                factor,
                settings.runtime.data_root / "research" / "factor_library",
            ),
        },
        "rank_ic": {
            "in_sample": in_sample_ic,
            "oos_windows": _window_values(factor_daily_ic, settings),
            "daily_oos": [float(value) for value in daily_oos],
        },
        "stress_max_drawdown": stress,
        "portfolio": {
            "baseline_turnover": baseline_turnover,
            "candidate_turnover": candidate_turnover,
            "baseline_net_icir": metrics["baseline_net_icir"],
            "candidate_net_icir": metrics["candidate_net_icir"],
            "baseline_net_excess": metrics["baseline_net_excess"],
            "candidate_net_excess": metrics["candidate_net_excess"],
            "cost_2x_net_excess": metrics["cost_2x_net_excess"],
            "slippage_2x_net_excess": metrics["slippage_2x_net_excess"],
            "daily_net_excess_returns": [float(value) for value in candidate_return_series],
        },
    }
    evidence_path = _write_json_once(directory / "g1_evidence.json", evidence)
    return CandidateArtifacts(
        experiment_id=experiment_id,
        expression=expression,
        evidence_path=evidence_path,
        test_report_path=test_report_path,
        factor_panel_path=factor_panel_path,
    )


def _selected_candidates(report: dict[str, object], count: int) -> list[str]:
    candidates = report.get("candidates")
    if not isinstance(candidates, dict):
        raise G1PipelineError("benchmark report candidates must be an object")
    valid = [
        (expression, result)
        for expression, result in candidates.items()
        if isinstance(result, dict) and not result.get("error") and math.isfinite(float(result["rank_ic"]))
    ]
    valid.sort(key=lambda item: abs(float(item[1]["rank_ic"])), reverse=True)
    if len(valid) < count:
        raise G1PipelineError(f"benchmark has only {len(valid)} promotable candidates; need {count}")
    return [str(expression) for expression, _ in valid[:count]]


def run_pipeline(
    benchmark_report: Path,
    *,
    settings: Settings | None = None,
    output_root: Path | None = None,
    rationale: str = "预演候选，待人工确认经济含义。",
) -> dict[str, object]:
    settings = settings or load()
    output_root = output_root or settings.runtime.data_root / "research" / "g1"
    report = json.loads(benchmark_report.read_text(encoding="utf-8"))
    family = str(report.get("research_family", ""))
    if not family:
        raise G1PipelineError("benchmark report is not bound to a G1 research family")
    code_hash = code_snapshot_sha256()
    data_hash = ingest_snapshot_sha256()
    if report.get("code_snapshot_sha256") != code_hash or report.get("data_snapshot_sha256") != data_hash:
        raise G1PipelineError("benchmark report does not match the current code/data snapshots")
    expressions = _selected_candidates(report, settings.g1_admission.promoted_candidates)
    research = load_research_data(settings)
    baselines = build_baseline_windows(settings, research.labels)
    artifacts = []
    for expression in expressions:
        audit = audit_expression(expression)
        factor, daily_ic = evaluate_factor_panel(
            expression,
            research,
            min_cross_section=settings.alphagen_benchmark.min_cross_section,
        )
        artifacts.append(
            evaluate_candidate(
                settings,
                expression=expression,
                family=family,
                benchmark_report=benchmark_report,
                audit=audit,
                research=research,
                factor=factor,
                factor_daily_ic=daily_ic,
                baselines=baselines,
                output_root=output_root,
                rationale=rationale,
            )
        )
    decisions: list[AdmissionDecision] = [evaluate_g1(item.evidence_path) for item in artifacts]
    benchmark_report_sha256 = sha256_file(benchmark_report)
    summary = {
        "research_family": family,
        "benchmark_report_path": portable_artifact_path(benchmark_report),
        "benchmark_report_sha256": benchmark_report_sha256,
        "code_snapshot_sha256": code_hash,
        "data_snapshot_sha256": data_hash,
        "candidates": [
            {
                "experiment_id": artifact.experiment_id,
                "expression": artifact.expression,
                "evidence_path": portable_artifact_path(artifact.evidence_path),
                "decision": "PASS" if decision.admitted else "REJECT",
                "failed_gates": decision.failed_gates,
                "decision_report_path": portable_artifact_path(decision.report_path),
                "decision_report_sha256": decision.report_sha256,
            }
            for artifact, decision in zip(artifacts, decisions, strict=True)
        ],
        "formal_library_insertions": 0,
    }
    summary_path = (
        output_root
        / family
        / f"pipeline_summary-{benchmark_report_sha256[:12]}.json"
    )
    _write_json_once(summary_path, summary)
    return {**summary, "summary_path": str(summary_path)}


def latest_family_report(family: str) -> Path:
    matches = []
    for path in (PROJECT_ROOT / "logs" / "benchmark").glob("alphagen_cpu_*.json"):
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if report.get("research_family") == family:
            matches.append(path)
    if not matches:
        raise G1PipelineError(f"no AlphaGen benchmark report for research family: {family}")
    return max(matches, key=lambda path: path.stat().st_mtime_ns)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--benchmark-report", type=Path)
    source.add_argument("--research-family")
    parser.add_argument("--rationale", default="预演候选，待人工确认经济含义。")
    args = parser.parse_args(argv)
    benchmark_report = (
        args.benchmark_report
        if args.benchmark_report is not None
        else latest_family_report(args.research_family)
    )
    result = run_pipeline(benchmark_report, rationale=args.rationale)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
