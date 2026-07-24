"""Run the frozen six-candidate P1 money-flow comparison and G1 judge."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import resource
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from shaiwei.config import PROJECT_ROOT, EvaluationWindow, Settings, load
from shaiwei.ledger import (
    EXPERIMENTS,
    append_experiment,
    ingest_snapshot_sha256,
    portable_artifact_path,
    sha256_file,
)
from shaiwei.provenance import code_snapshot_sha256
from shaiwei.research.factor_portfolio import (
    SignalBacktest,
    augment_signal,
    backtest_signal,
    daily_rank_ic,
    icir,
)
from shaiwei.research.g1 import AdmissionDecision, evaluate_g1, periodic_sharpe
from shaiwei.research.g1_pipeline import (
    BaselineWindow,
    _compound,
    _max_library_correlation,
    _stress_drawdown,
    load_research_data,
)
from tools.p1_moneyflow.contract import tool_snapshot_sha256, write_project_json
from tools.p1_moneyflow.feature_builder import write_content_addressed_parquet
from tools.p1_moneyflow.features import FORMAL_CANDIDATES, feature_policy_sha256


class P1ExperimentError(RuntimeError):
    pass


RESEARCH_FAMILY = "p1-moneyflow-v1"
BACKTEST_SERIALIZATION_DECIMALS = 10


@dataclass(frozen=True)
class CandidateSpec:
    name: str
    formula: str
    rationale: str
    expression_tokens: int
    ast_nodes: int


@dataclass(frozen=True)
class CandidateResult:
    spec: CandidateSpec
    experiment_id: str
    factor: pd.Series
    factor_daily_ic: pd.Series
    in_sample_ic: float
    oos_windows: dict[str, float]
    stress: dict[str, float]
    baseline_turnover: float
    candidate_turnover: float
    baseline_net_icir: float
    candidate_net_icir: float
    baseline_net_excess: float
    candidate_net_excess: float
    cost_2x_net_excess: float
    slippage_2x_net_excess: float
    selection_sharpe: float
    candidate_daily_returns: pd.Series
    warning_diagnostic: dict[str, object]
    max_library_abs_spearman: float
    return_rows: pd.DataFrame
    ic_rows: pd.DataFrame


CANDIDATE_SPECS = (
    CandidateSpec(
        "mf_net_intensity_1d",
        "net_mf_amount / (daily.amount / 10)",
        "单日官方净流入相对成交额衡量即时买卖压力，并允许发现期决定延续或反转方向。",
        5,
        7,
    ),
    CandidateSpec(
        "mf_large_intensity_1d",
        "(buy_lg_amount + buy_elg_amount - sell_lg_amount - sell_elg_amount) / "
        "(daily.amount / 10)",
        "大单与特大单的有符号失衡相对成交额衡量较大交易者的即时资金压力。",
        11,
        15,
    ),
    CandidateSpec(
        "mf_net_intensity_5d",
        "sum(net_mf_amount, 5) / sum(daily.amount / 10, 5)",
        "五个连续交易日累计净流入强度检验订单拆分造成的一周级资金压力持续性。",
        9,
        11,
    ),
    CandidateSpec(
        "mf_net_intensity_20d",
        "sum(net_mf_amount, 20) / sum(daily.amount / 10, 20)",
        "二十个连续交易日累计净流入强度检验月度资金压力是否稳定并能覆盖交易成本。",
        9,
        11,
    ),
    CandidateSpec(
        "mf_net_innovation_5_20",
        "mf_net_intensity_5d - mf_net_intensity_20d",
        "短期强度相对长期强度的变化用于识别新增资金压力，而非长期水平本身。",
        3,
        3,
    ),
    CandidateSpec(
        "mf_net_persistence_10d",
        "mean(sign(net_mf_amount), 10)",
        "十日净流入方向均值弱化金额极值，检验资金方向连续性是否具有可重复信息。",
        6,
        6,
    ),
)


COMPARISON_POLICY: dict[str, object] = {
    "schema_version": "p1-moneyflow-comparison-v1",
    "research_family": RESEARCH_FAMILY,
    "candidates": [spec.name for spec in CANDIDATE_SPECS],
    "candidate_attempt_count": 6,
    "window_count": 6,
    "scenario_count": 3,
    "evidence_cell_count": 108,
    "factor_blend": {"alpha158": 0.9, "moneyflow": 0.1},
    "scenarios": {
        "normal": {
            "cost_multiplier": 1.0,
            "extra_open_cost": 0.0,
            "extra_close_cost": 0.0,
        },
        "cost_2x": {
            "cost_multiplier": 2.0,
            "extra_open_cost": 0.0,
            "extra_close_cost": 0.0,
        },
        "slippage_2x": {
            "cost_multiplier": 1.0,
            "extra_open_cost": 0.001,
            "extra_close_cost": 0.001,
        },
    },
    "stress_panel": {
        "style_shift_2017": "core",
        "microcap_crash_2024": "w6_incremental",
        "volume_price_drawdown_2026h1": "core",
    },
    "warning_diagnostic_authority": "NOT_FOR_VERDICT",
    "backtest_serialization_decimal_places": BACKTEST_SERIALIZATION_DECIMALS,
    "selection_sharpe": "exact_from_quantized_daily_returns",
}


def comparison_policy_sha256() -> str:
    payload = json.dumps(
        COMPARISON_POLICY,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def candidate_experiment_id(
    candidate: str,
    code_hash: str,
    data_hash: str,
    policy_hash: str,
) -> str:
    payload = f"{RESEARCH_FAMILY}|{candidate}|{code_hash}|{data_hash}|{policy_hash}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]


def ts_code_to_qlib(value: str) -> str:
    code = str(value)
    if len(code) == 9 and code[6:] in {".SH", ".SZ"} and code[:6].isdigit():
        return f"{code[7:]}{code[:6]}"
    if code.endswith(".BJ"):
        raise P1ExperimentError(".BJ is forbidden in the P1 experiment")
    raise P1ExperimentError(f"unsupported A-share code: {value!r}")


def _read_json(path: Path) -> dict[str, object]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise P1ExperimentError(f"invalid JSON evidence: {path}") from error
    if not isinstance(document, dict):
        raise P1ExperimentError(f"JSON evidence must be an object: {path}")
    return document


def _artifact_path(artifact: dict[str, object]) -> Path:
    path = PROJECT_ROOT / str(artifact.get("path", ""))
    expected = str(artifact.get("sha256", ""))
    if not path.is_file() or sha256_file(path) != expected:
        raise P1ExperimentError(f"artifact is missing or hash-mismatched: {path}")
    return path


def validate_residual_report(
    path: Path,
    *,
    require_reused: bool = True,
) -> dict[str, object]:
    report = _read_json(path)
    if report.get("schema_version") != "p1-moneyflow-residual-build-v1":
        raise P1ExperimentError("residual report schema differs from the frozen version")
    if report.get("status") != "PASS":
        raise P1ExperimentError("residual report is not PASS")
    if report.get("production_code_snapshot_sha256") != code_snapshot_sha256():
        raise P1ExperimentError("production code snapshot changed after residual construction")
    if report.get("ingest_snapshot_sha256") != ingest_snapshot_sha256():
        raise P1ExperimentError("ingest snapshot changed after residual construction")
    if report.get("feature_policy_sha256") != feature_policy_sha256():
        raise P1ExperimentError("feature policy differs from residual construction")
    artifacts = report.get("artifacts")
    if not isinstance(artifacts, dict) or set(artifacts) != {
        "core",
        "formal",
        "alpha158_predictions",
    }:
        raise P1ExperimentError("residual report lacks the three frozen artifacts")
    for name, raw in artifacts.items():
        if not isinstance(raw, dict):
            raise P1ExperimentError(f"invalid residual artifact section: {name}")
        _artifact_path(raw)
        if require_reused and raw.get("reused") is not True:
            raise P1ExperimentError(f"residual artifact did not pass exact reuse: {name}")
    if report.get("formal_candidates") != list(FORMAL_CANDIDATES):
        raise P1ExperimentError("residual candidate order differs from the frozen budget")
    return report


def _factor_series(frame: pd.DataFrame, candidate: str) -> pd.Series:
    required = {"ts_code", "trade_date", candidate}
    if missing := required - set(frame.columns):
        raise P1ExperimentError(f"factor panel lacks columns: {sorted(missing)}")
    selected = frame.loc[:, ["trade_date", "ts_code", candidate]].dropna().copy()
    if selected["ts_code"].astype(str).str.endswith(".BJ").any():
        raise P1ExperimentError(".BJ returned in a formal factor panel")
    if selected.duplicated(["trade_date", "ts_code"]).any():
        raise P1ExperimentError("formal factor panel contains duplicate keys")
    selected["datetime"] = pd.to_datetime(selected["trade_date"], format="%Y%m%d")
    selected["instrument"] = selected["ts_code"].map(ts_code_to_qlib)
    value = selected.set_index(["datetime", "instrument"])[candidate]
    value.index = value.index.set_names(["datetime", "instrument"])
    return pd.to_numeric(value, errors="raise").astype(float).sort_index()


def _validate_residual_panel(frame: pd.DataFrame, *, name: str) -> None:
    required = {"ts_code", "trade_date", "source_trade_date", *FORMAL_CANDIDATES}
    if missing := required - set(frame.columns):
        raise P1ExperimentError(f"{name} residual panel lacks columns: {sorted(missing)}")
    if frame["ts_code"].astype(str).str.endswith(".BJ").any():
        raise P1ExperimentError(f".BJ returned in {name} residual panel")
    if frame.duplicated(["trade_date", "ts_code"]).any():
        raise P1ExperimentError(f"{name} residual panel contains duplicate keys")
    trade_date = pd.to_datetime(frame["trade_date"], format="%Y%m%d", errors="raise")
    source_date = pd.to_datetime(
        frame["source_trade_date"], format="%Y%m%d", errors="raise"
    )
    if source_date.ge(trade_date).any():
        raise P1ExperimentError(f"{name} residual panel violates frozen T+1 lineage")


def _prediction_series(frame: pd.DataFrame, window: EvaluationWindow) -> pd.Series:
    selected = frame.loc[frame["window"].eq(window.name)].copy()
    if selected.empty:
        raise P1ExperimentError(f"cached predictions lack {window.name}")
    if selected["ts_code"].astype(str).str.endswith(".BJ").any():
        raise P1ExperimentError(".BJ returned in cached Alpha158 predictions")
    if selected.duplicated(["trade_date", "instrument"]).any():
        raise P1ExperimentError(f"cached predictions contain duplicate keys: {window.name}")
    expected = selected["ts_code"].map(ts_code_to_qlib)
    if not expected.eq(selected["instrument"].astype(str)).all():
        raise P1ExperimentError(f"cached prediction code mapping differs: {window.name}")
    selected["datetime"] = pd.to_datetime(selected["trade_date"], format="%Y%m%d")
    value = selected.set_index(["datetime", "instrument"])["baseline_score"]
    value.index = value.index.set_names(["datetime", "instrument"])
    return pd.to_numeric(value, errors="raise").astype(float).sort_index()


def _window_values(daily_ic: pd.Series, settings: Settings) -> dict[str, float]:
    values: dict[str, float] = {}
    for window in settings.evaluation.g0_windows:
        window_values = daily_ic.loc[
            (daily_ic.index >= pd.Timestamp(window.test_start))
            & (daily_ic.index <= pd.Timestamp(window.test_end))
        ]
        if len(window_values) < 60:
            raise P1ExperimentError(f"{window.name} has fewer than 60 daily IC observations")
        values[window.name] = float(window_values.mean())
    return values


def warning_day_diagnostic(
    daily_ic: pd.Series,
    warning_feature_dates: set[pd.Timestamp],
) -> dict[str, object]:
    clean = pd.to_numeric(daily_ic, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    excluded = clean.loc[~clean.index.isin(warning_feature_dates)]
    if clean.empty or excluded.empty:
        raise P1ExperimentError("warning-day diagnostic lacks usable daily IC")
    return {
        "verdict_authority": "NOT_FOR_VERDICT",
        "definition": "exclude feature dates whose T-1 moneyflow source date carried a scale-tail warning",
        "included_observations": int(len(clean)),
        "excluded_observations": int(len(excluded)),
        "removed_observations": int(len(clean) - len(excluded)),
        "included_mean_rank_ic": float(clean.mean()),
        "excluded_mean_rank_ic": float(excluded.mean()),
        "difference_excluded_minus_included": float(excluded.mean() - clean.mean()),
    }


def _warning_feature_dates(
    formal: pd.DataFrame,
    quality_report: dict[str, object],
) -> tuple[set[pd.Timestamp], int]:
    rows = quality_report.get("per_trade_date")
    if not isinstance(rows, list):
        raise P1ExperimentError("quality report lacks per_trade_date diagnostics")
    warning_sources = {
        str(row["trade_date"])
        for row in rows
        if isinstance(row, dict)
        and "NET_FLOW_EXCEEDS_DAILY_SCALE_TAIL" in row.get("warnings", [])
    }
    mapping = formal.loc[:, ["trade_date", "source_trade_date"]].drop_duplicates()
    if mapping.duplicated("trade_date").any():
        raise P1ExperimentError("one feature date maps to multiple source dates")
    feature_dates = set(
        pd.to_datetime(
            mapping.loc[
                mapping["source_trade_date"].astype(str).isin(warning_sources),
                "trade_date",
            ],
            format="%Y%m%d",
        )
    )
    return feature_dates, len(warning_sources)


def _build_baselines(
    settings: Settings,
    labels: pd.Series,
    predictions: pd.DataFrame,
    expected_summary: object,
) -> list[BaselineWindow]:
    if set(predictions["window"].astype(str)) != {
        window.name for window in settings.evaluation.g0_windows
    }:
        raise P1ExperimentError("cached prediction windows differ from W1-W6")
    expected_rows = {
        str(row["window"]): row
        for row in expected_summary
        if isinstance(row, dict) and "window" in row
    } if isinstance(expected_summary, list) else {}
    windows = []
    for window in settings.evaluation.g0_windows:
        prediction = _prediction_series(predictions, window)
        window_labels = labels.loc[
            (labels.index.get_level_values("datetime") >= pd.Timestamp(window.test_start))
            & (labels.index.get_level_values("datetime") <= pd.Timestamp(window.test_end))
        ]
        baseline_ic = daily_rank_ic(prediction, window_labels)
        result = backtest_signal(
            settings,
            prediction,
            start_time=window.test_start.isoformat(),
            end_time=window.test_end.isoformat(),
        )
        expected = expected_rows.get(window.name)
        if not isinstance(expected, dict):
            raise P1ExperimentError(f"residual report lacks baseline summary: {window.name}")
        checks = {
            "baseline_turnover": result.turnover,
            "baseline_cumulative_excess": result.cumulative_excess,
            "baseline_max_drawdown": result.max_drawdown,
        }
        for field, actual in checks.items():
            if not math.isclose(float(expected[field]), actual, rel_tol=1e-10, abs_tol=1e-12):
                raise P1ExperimentError(
                    f"cached baseline does not reproduce residual report: {window.name}.{field}"
                )
        windows.append(
            BaselineWindow(
                window,
                prediction,
                window_labels,
                baseline_ic,
                _quantize_backtest(result),
            )
        )
    return windows


def _quantize(value: float) -> float:
    rounded = float(np.round(float(value), decimals=BACKTEST_SERIALIZATION_DECIMALS))
    return 0.0 if rounded == 0 else rounded


def _quantize_backtest(result: SignalBacktest) -> SignalBacktest:
    daily = pd.to_numeric(result.daily_excess, errors="raise").round(
        BACKTEST_SERIALIZATION_DECIMALS
    )
    daily = daily.mask(daily.eq(0), 0.0)
    nav = (1.0 + daily).cumprod()
    drawdown = nav / nav.cummax() - 1.0
    return SignalBacktest(
        daily_excess=daily,
        cumulative_excess=_quantize(float(nav.iloc[-1] - 1.0)),
        turnover=_quantize(result.turnover),
        max_drawdown=_quantize(float(-drawdown.min())),
    )


def _scenario_backtest(
    settings: Settings,
    signal: pd.Series,
    window: EvaluationWindow,
    scenario: str,
) -> SignalBacktest:
    raw = COMPARISON_POLICY["scenarios"]
    assert isinstance(raw, dict)
    parameters = raw[scenario]
    assert isinstance(parameters, dict)
    return _quantize_backtest(
        backtest_signal(
            settings,
            signal,
            start_time=window.test_start.isoformat(),
            end_time=window.test_end.isoformat(),
            cost_multiplier=float(parameters["cost_multiplier"]),
            extra_open_cost=float(parameters["extra_open_cost"]),
            extra_close_cost=float(parameters["extra_close_cost"]),
        )
    )


def _daily_rows(
    candidate: str,
    window: str,
    scenario: str,
    values: pd.Series,
) -> pd.DataFrame:
    frame = values.rename("daily_net_excess_return").reset_index()
    frame = frame.rename(columns={frame.columns[0]: "trade_date"})
    frame.insert(0, "scenario", scenario)
    frame.insert(0, "window", window)
    frame.insert(0, "candidate", candidate)
    frame["trade_date"] = pd.to_datetime(frame["trade_date"]).dt.strftime("%Y%m%d")
    return frame


def _ic_rows(
    candidate: str,
    series_type: str,
    window: str,
    values: pd.Series,
) -> pd.DataFrame:
    frame = values.rename("rank_ic").reset_index()
    frame = frame.rename(columns={frame.columns[0]: "trade_date"})
    frame.insert(0, "window", window)
    frame.insert(0, "series_type", series_type)
    frame.insert(0, "candidate", candidate)
    frame["trade_date"] = pd.to_datetime(frame["trade_date"]).dt.strftime("%Y%m%d")
    return frame


def _evaluate_candidate(
    settings: Settings,
    spec: CandidateSpec,
    *,
    code_hash: str,
    data_hash: str,
    policy_hash: str,
    core: pd.DataFrame,
    formal: pd.DataFrame,
    labels: pd.Series,
    baselines: list[BaselineWindow],
    warning_feature_dates: set[pd.Timestamp],
) -> CandidateResult:
    core_factor = _factor_series(core, spec.name)
    factor = _factor_series(formal, spec.name)
    core_daily_ic = daily_rank_ic(core_factor, labels)
    factor_daily_ic = daily_rank_ic(factor, labels)
    discovery = core_daily_ic.loc[
        (core_daily_ic.index >= pd.Timestamp(settings.g1_admission.discovery_start))
        & (core_daily_ic.index <= pd.Timestamp(settings.g1_admission.discovery_end))
    ]
    if len(discovery) < settings.g1_admission.min_observations:
        raise P1ExperimentError(f"{spec.name} discovery period lacks minimum observations")
    in_sample_ic = float(discovery.mean())
    if in_sample_ic == 0:
        raise P1ExperimentError(f"{spec.name} discovery RankIC is zero")
    direction = 1.0 if in_sample_ic > 0 else -1.0
    oriented = direction * factor

    baseline_daily_ic = []
    candidate_daily_ic = []
    baseline_returns = []
    candidate_returns = []
    cost_2x_returns = []
    slippage_2x_returns = []
    return_rows = []
    ic_rows = [_ic_rows(spec.name, "factor", "ALL", factor_daily_ic)]
    baseline_turnover = 0.0
    candidate_turnover = 0.0
    for baseline in baselines:
        augmented = augment_signal(
            baseline.predictions,
            oriented,
            factor_weight=settings.g1_admission.factor_blend_weight,
        )
        candidate_ic = daily_rank_ic(augmented, baseline.labels)
        scenario_results = {
            scenario: _scenario_backtest(settings, augmented, baseline.window, scenario)
            for scenario in ("normal", "cost_2x", "slippage_2x")
        }
        normal = scenario_results["normal"]
        baseline_daily_ic.append(baseline.daily_ic)
        candidate_daily_ic.append(candidate_ic)
        baseline_returns.append(baseline.backtest.daily_excess)
        candidate_returns.append(normal.daily_excess)
        cost_2x_returns.append(scenario_results["cost_2x"].daily_excess)
        slippage_2x_returns.append(scenario_results["slippage_2x"].daily_excess)
        baseline_turnover += baseline.backtest.turnover
        candidate_turnover += normal.turnover
        ic_rows.append(_ic_rows(spec.name, "augmented_signal", baseline.window.name, candidate_ic))
        for scenario, result in scenario_results.items():
            rows = _daily_rows(
                spec.name,
                baseline.window.name,
                scenario,
                result.daily_excess,
            )
            rows["cumulative_excess"] = result.cumulative_excess
            rows["turnover"] = result.turnover
            rows["max_drawdown"] = result.max_drawdown
            return_rows.append(rows)

    baseline_ic = pd.concat(baseline_daily_ic).sort_index()
    candidate_ic = pd.concat(candidate_daily_ic).sort_index()
    baseline_return = pd.concat(baseline_returns).sort_index()
    candidate_return = pd.concat(candidate_returns).sort_index()
    cost_2x_return = pd.concat(cost_2x_returns).sort_index()
    slippage_2x_return = pd.concat(slippage_2x_returns).sort_index()
    stress = {
        period.name: _quantize(
            _stress_drawdown(
                oriented,
                labels,
                start=pd.Timestamp(period.start),
                end=pd.Timestamp(period.end),
                topk=settings.backtest.topk,
                rebalance_days=settings.backtest.rebalance_days,
                roundtrip_cost=settings.backtest.open_cost + settings.backtest.close_cost,
            )
        )
        for period in settings.evaluation.stress_periods
    }
    return CandidateResult(
        spec=spec,
        experiment_id=candidate_experiment_id(spec.name, code_hash, data_hash, policy_hash),
        factor=factor,
        factor_daily_ic=factor_daily_ic,
        in_sample_ic=in_sample_ic,
        oos_windows=_window_values(factor_daily_ic, settings),
        stress=stress,
        baseline_turnover=_quantize(baseline_turnover),
        candidate_turnover=_quantize(candidate_turnover),
        baseline_net_icir=_quantize(icir(baseline_ic)),
        candidate_net_icir=_quantize(icir(candidate_ic)),
        baseline_net_excess=_quantize(_compound(baseline_return)),
        candidate_net_excess=_quantize(_compound(candidate_return)),
        cost_2x_net_excess=_quantize(_compound(cost_2x_return)),
        slippage_2x_net_excess=_quantize(_compound(slippage_2x_return)),
        selection_sharpe=periodic_sharpe(
            candidate_return.tolist(),
            minimum=settings.g1_admission.min_observations,
        ),
        candidate_daily_returns=candidate_return,
        warning_diagnostic=warning_day_diagnostic(factor_daily_ic, warning_feature_dates),
        max_library_abs_spearman=_max_library_correlation(
            factor,
            settings.runtime.data_root / "research" / "factor_library",
        ),
        return_rows=pd.concat(return_rows, ignore_index=True),
        ic_rows=pd.concat(ic_rows, ignore_index=True),
    )


def _canonical_json(document: dict[str, object]) -> str:
    return json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _write_json_once(path: Path, document: dict[str, object]) -> tuple[Path, bool]:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = _canonical_json(document)
    if path.is_file():
        if path.read_text(encoding="utf-8") != payload:
            raise P1ExperimentError(f"existing immutable JSON differs: {path}")
        return path, True
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_text(payload, encoding="utf-8")
        with temporary.open("rb") as handle:
            os.fsync(handle.fileno())
        os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return path, False


def _existing_experiment(experiment_id: str) -> dict[str, str] | None:
    with EXPERIMENTS.open(newline="", encoding="utf-8") as handle:
        rows = [row for row in csv.DictReader(handle) if row["experiment_id"] == experiment_id]
    if len(rows) > 1:
        raise P1ExperimentError(f"duplicate deterministic experiment ID: {experiment_id}")
    return rows[0] if rows else None


def _family_trial_count() -> int:
    with EXPERIMENTS.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    return sum(
        json.loads(row["params_json"]).get("g1_research_family") == RESEARCH_FAMILY
        for row in rows
    )


def _ensure_experiment(
    result: CandidateResult,
    *,
    code_hash: str,
    data_hash: str,
    policy_hash: str,
    evidence_path: Path,
    test_report_path: Path,
) -> bool:
    params = {
        "g1_research_family": RESEARCH_FAMILY,
        "expression_tokens": result.spec.expression_tokens,
        "ast_nodes": result.spec.ast_nodes,
        "attempt_stage": "formal_portfolio_evaluation",
        "candidate": result.spec.name,
        "factor_blend_weight": 0.1,
        "comparison_policy_sha256": policy_hash,
        "candidate_attempt_count": 6,
        "evidence_cell_count": 108,
    }
    metrics = {
        "status": "PASS",
        "selection_sharpe": result.selection_sharpe,
        "baseline_net_icir": result.baseline_net_icir,
        "candidate_net_icir": result.candidate_net_icir,
        "baseline_net_excess": result.baseline_net_excess,
        "candidate_net_excess": result.candidate_net_excess,
        "cost_2x_net_excess": result.cost_2x_net_excess,
        "slippage_2x_net_excess": result.slippage_2x_net_excess,
        "baseline_turnover": result.baseline_turnover,
        "candidate_turnover": result.candidate_turnover,
        "evidence_path": portable_artifact_path(evidence_path),
        "evidence_sha256": sha256_file(evidence_path),
        "factor_test_report_path": portable_artifact_path(test_report_path),
        "factor_test_report_sha256": sha256_file(test_report_path),
    }
    if existing := _existing_experiment(result.experiment_id):
        checks = {
            "candidate_source": "Tushare-moneyflow-P1",
            "model_or_engine": "Alpha158 + frozen moneyflow rank blend",
            "engine_version": "p1-moneyflow-comparison-v1",
            "code_sha256": code_hash,
            "data_snapshot_sha256": data_hash,
            "feature_or_formula": result.spec.formula,
            "params_json": params,
            "result_json": metrics,
        }
        for field, expected in checks.items():
            actual: object = existing[field]
            if field.endswith("_json"):
                actual = json.loads(str(actual))
            if actual != expected:
                raise P1ExperimentError(
                    f"existing deterministic candidate experiment differs: "
                    f"{result.experiment_id}.{field}"
                )
        return True
    append_experiment(
        experiment_id=result.experiment_id,
        parent_experiment_id="",
        candidate_source="Tushare-moneyflow-P1",
        model_or_engine="Alpha158 + frozen moneyflow rank blend",
        engine_version="p1-moneyflow-comparison-v1",
        seed=42,
        prompt_hash="",
        code_sha256=code_hash,
        data_snapshot_sha256=data_hash,
        feature_or_formula=result.spec.formula,
        params_json=params,
        train_period="2016-01-01~2018-12-31",
        valid_period="W1-W6 + frozen stress periods",
        result_json=metrics,
        admitted=False,
        reject_reason="G1 evidence candidate; pending frozen judge",
    )
    return False


def _build_candidate_artifacts(
    result: CandidateResult,
    *,
    code_hash: str,
    data_hash: str,
    policy_hash: str,
    formal_artifact: dict[str, object],
    feature_report_path: Path,
    feature_report_sha256: str,
    daily_returns_path: Path,
    daily_returns_sha256: str,
    daily_ic_path: Path,
    daily_ic_sha256: str,
    output_root: Path,
) -> tuple[Path, Path, bool]:
    directory = output_root / result.experiment_id
    test_report = {
        "schema_version": 1,
        "candidate_experiment_id": result.experiment_id,
        "code_snapshot_sha256": code_hash,
        "data_snapshot_sha256": data_hash,
        "candidate": result.spec.name,
        "comparison_policy_sha256": policy_hash,
        "pit_sentinel_pass": True,
        "shift_sentinel_pass": True,
        "sentinel_basis": {
            "feature_report_path": portable_artifact_path(feature_report_path),
            "feature_report_sha256": feature_report_sha256,
            "formal_residual_artifact_path": str(formal_artifact["path"]),
            "formal_residual_artifact_sha256": str(formal_artifact["sha256"]),
            "candidate_column": result.spec.name,
            "feature_available_lag_trade_days": 1,
            "lineage_violation_count": 0,
        },
        "daily_returns_path": portable_artifact_path(daily_returns_path),
        "daily_returns_sha256": daily_returns_sha256,
        "daily_ic_path": portable_artifact_path(daily_ic_path),
        "daily_ic_sha256": daily_ic_sha256,
    }
    test_path, test_reused = _write_json_once(directory / "factor_tests.json", test_report)
    evidence = {
        "schema_version": 1,
        "candidate_experiment_id": result.experiment_id,
        "research_family": RESEARCH_FAMILY,
        "code_snapshot_sha256": code_hash,
        "data_snapshot_sha256": data_hash,
        "economic_rationale": result.spec.rationale,
        "complexity": {
            "expression_tokens": result.spec.expression_tokens,
            "ast_nodes": result.spec.ast_nodes,
        },
        "integrity": {
            "pit_sentinel_pass": True,
            "shift_sentinel_pass": True,
            "test_report_path": portable_artifact_path(test_path),
            "test_report_sha256": sha256_file(test_path),
            "max_library_abs_spearman": result.max_library_abs_spearman,
        },
        "rank_ic": {
            "in_sample": result.in_sample_ic,
            "oos_windows": result.oos_windows,
            "daily_oos": [
                float(value)
                for value in result.factor_daily_ic.loc[
                    (result.factor_daily_ic.index >= pd.Timestamp("2019-01-01"))
                    & (result.factor_daily_ic.index <= pd.Timestamp("2024-12-31"))
                ]
            ],
        },
        "stress_max_drawdown": result.stress,
        "portfolio": {
            "baseline_turnover": result.baseline_turnover,
            "candidate_turnover": result.candidate_turnover,
            "baseline_net_icir": result.baseline_net_icir,
            "candidate_net_icir": result.candidate_net_icir,
            "baseline_net_excess": result.baseline_net_excess,
            "candidate_net_excess": result.candidate_net_excess,
            "cost_2x_net_excess": result.cost_2x_net_excess,
            "slippage_2x_net_excess": result.slippage_2x_net_excess,
            "daily_net_excess_returns": [
                float(value) for value in result.candidate_daily_returns
            ],
        },
    }
    evidence_path, evidence_reused = _write_json_once(directory / "g1_evidence.json", evidence)
    return test_path, evidence_path, test_reused and evidence_reused


def _peak_rss_bytes() -> int:
    # This formal runner executes in Linux Docker, where ru_maxrss is KiB.
    return int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--residual-report", type=Path, required=True)
    parser.add_argument("--quality-report", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    started = time.perf_counter()
    residual_path = (
        args.residual_report
        if args.residual_report.is_absolute()
        else PROJECT_ROOT / args.residual_report
    )
    quality_path = (
        args.quality_report
        if args.quality_report.is_absolute()
        else PROJECT_ROOT / args.quality_report
    )
    residual = validate_residual_report(residual_path)
    quality = _read_json(quality_path)
    if quality.get("ingest_snapshot_sha256") != residual.get("ingest_snapshot_sha256"):
        raise P1ExperimentError("quality and residual reports bind different ingest snapshots")
    artifacts = residual["artifacts"]
    assert isinstance(artifacts, dict)
    core_artifact = artifacts["core"]
    formal_artifact = artifacts["formal"]
    prediction_artifact = artifacts["alpha158_predictions"]
    assert isinstance(core_artifact, dict)
    assert isinstance(formal_artifact, dict)
    assert isinstance(prediction_artifact, dict)

    core = pd.read_parquet(_artifact_path(core_artifact))
    formal = pd.read_parquet(_artifact_path(formal_artifact))
    predictions = pd.read_parquet(_artifact_path(prediction_artifact))
    _validate_residual_panel(core, name="core")
    _validate_residual_panel(formal, name="formal")
    warning_feature_dates, warning_source_count = _warning_feature_dates(formal, quality)

    settings = load()
    research = load_research_data(settings)
    baselines = _build_baselines(
        settings,
        research.labels,
        predictions,
        residual.get("baseline_windows"),
    )
    code_hash = tool_snapshot_sha256()
    data_hash = str(residual["residual_data_snapshot_sha256"])
    policy_hash = comparison_policy_sha256()
    results = [
        _evaluate_candidate(
            settings,
            spec,
            code_hash=code_hash,
            data_hash=data_hash,
            policy_hash=policy_hash,
            core=core,
            formal=formal,
            labels=research.labels,
            baselines=baselines,
            warning_feature_dates=warning_feature_dates,
        )
        for spec in CANDIDATE_SPECS
    ]

    artifact_root = PROJECT_ROOT / "data" / "research" / "moneyflow" / "experiments"
    daily_returns = pd.concat([result.return_rows for result in results], ignore_index=True)
    daily_returns = daily_returns.sort_values(
        ["candidate", "window", "scenario", "trade_date"], kind="stable"
    ).reset_index(drop=True)
    daily_ic = pd.concat([result.ic_rows for result in results], ignore_index=True)
    daily_ic = daily_ic.sort_values(
        ["candidate", "series_type", "window", "trade_date"], kind="stable"
    ).reset_index(drop=True)
    returns_path, returns_hash, returns_reused = write_content_addressed_parquet(
        daily_returns,
        artifact_root,
        stem="p1-moneyflow-daily-returns-v1",
    )
    ic_path, ic_hash, ic_reused = write_content_addressed_parquet(
        daily_ic,
        artifact_root,
        stem="p1-moneyflow-daily-ic-v1",
    )

    feature_report_path = PROJECT_ROOT / str(residual["feature_report_path"])
    feature_report = _read_json(feature_report_path)
    lineage = feature_report.get("lineage")
    if not isinstance(lineage, dict) or lineage.get("status") != "PASS":
        raise P1ExperimentError("feature lineage report is not PASS")
    if lineage.get("lineage_violation_count") != 0 or lineage.get("bse_row_count") != 0:
        raise P1ExperimentError("feature lineage/BSE sentinel failed")
    feature_report_sha256 = sha256_file(feature_report_path)
    if feature_report_sha256 != residual.get("feature_report_sha256"):
        raise P1ExperimentError("feature report hash differs from residual binding")

    output_root = artifact_root / RESEARCH_FAMILY
    built = []
    immutable_reused = []
    for result in results:
        test_path, evidence_path, reused = _build_candidate_artifacts(
            result,
            code_hash=code_hash,
            data_hash=data_hash,
            policy_hash=policy_hash,
            formal_artifact=formal_artifact,
            feature_report_path=feature_report_path,
            feature_report_sha256=feature_report_sha256,
            daily_returns_path=returns_path,
            daily_returns_sha256=returns_hash,
            daily_ic_path=ic_path,
            daily_ic_sha256=ic_hash,
            output_root=output_root,
        )
        built.append((result, test_path, evidence_path))
        immutable_reused.append(reused)

    experiment_reused = [
        _ensure_experiment(
            result,
            code_hash=code_hash,
            data_hash=data_hash,
            policy_hash=policy_hash,
            evidence_path=evidence_path,
            test_report_path=test_path,
        )
        for result, test_path, evidence_path in built
    ]
    decisions: list[AdmissionDecision] = [
        evaluate_g1(
            evidence_path,
            settings=settings,
            output_dir=output_root / "g1_decisions",
        )
        for _, _, evidence_path in built
    ]

    candidates = []
    for (result, test_path, evidence_path), decision in zip(built, decisions, strict=True):
        candidates.append(
            {
                "candidate": result.spec.name,
                "experiment_id": result.experiment_id,
                "direction": 1 if result.in_sample_ic > 0 else -1,
                "in_sample_rank_ic": result.in_sample_ic,
                "oos_rank_ic": result.oos_windows,
                "warning_diagnostic": result.warning_diagnostic,
                "portfolio": {
                    "baseline_net_icir": result.baseline_net_icir,
                    "candidate_net_icir": result.candidate_net_icir,
                    "baseline_net_excess": result.baseline_net_excess,
                    "candidate_net_excess": result.candidate_net_excess,
                    "cost_2x_net_excess": result.cost_2x_net_excess,
                    "slippage_2x_net_excess": result.slippage_2x_net_excess,
                    "baseline_turnover": result.baseline_turnover,
                    "candidate_turnover": result.candidate_turnover,
                },
                "stress_max_drawdown": result.stress,
                "test_report_path": portable_artifact_path(test_path),
                "test_report_sha256": sha256_file(test_path),
                "evidence_path": portable_artifact_path(evidence_path),
                "evidence_sha256": sha256_file(evidence_path),
                "decision": "PASS" if decision.admitted else "REJECT",
                "failed_gates": list(decision.failed_gates),
                "decision_report_path": portable_artifact_path(decision.report_path),
                "decision_report_sha256": decision.report_sha256,
            }
        )
    stable_summary = {
        "schema_version": "p1-moneyflow-comparison-summary-v1",
        "status": "GO_REVIEW_ONLY"
        if any(decision.admitted for decision in decisions)
        else "REJECT",
        "research_family": RESEARCH_FAMILY,
        "production_code_snapshot_sha256": code_snapshot_sha256(),
        "p1_tool_snapshot_sha256": code_hash,
        "residual_data_snapshot_sha256": data_hash,
        "comparison_policy": COMPARISON_POLICY,
        "comparison_policy_sha256": policy_hash,
        "experiment_trial_count": _family_trial_count(),
        "current_run_candidate_count": 6,
        "evidence_cell_count": 108,
        "warning_source_date_count": warning_source_count,
        "warning_diagnostic_authority": "NOT_FOR_VERDICT",
        "artifacts": {
            "daily_returns": {
                "path": portable_artifact_path(returns_path),
                "sha256": returns_hash,
                "row_count": int(len(daily_returns)),
            },
            "daily_ic": {
                "path": portable_artifact_path(ic_path),
                "sha256": ic_hash,
                "row_count": int(len(daily_ic)),
            },
        },
        "candidates": candidates,
        "formal_library_insertions": 0,
        "production_authorization": "none",
    }
    summary_path, summary_reused = _write_json_once(
        output_root / f"summary-{policy_hash[:12]}-{code_hash[:12]}-{data_hash[:12]}.json",
        stable_summary,
    )
    run_report = {
        "schema_version": "p1-moneyflow-comparison-run-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "PASS",
        "verdict": stable_summary["status"],
        "elapsed_seconds": time.perf_counter() - started,
        "peak_rss_bytes": _peak_rss_bytes(),
        "production_code_snapshot_sha256": code_snapshot_sha256(),
        "p1_tool_snapshot_sha256": code_hash,
        "residual_data_snapshot_sha256": data_hash,
        "summary_path": portable_artifact_path(summary_path),
        "summary_sha256": sha256_file(summary_path),
        "reuse": {
            "daily_returns": returns_reused,
            "daily_ic": ic_reused,
            "candidate_immutable_artifacts": all(immutable_reused),
            "experiment_rows": all(experiment_reused),
            "g1_decisions": all(decision.reused for decision in decisions),
            "summary": summary_reused,
        },
        "candidate_decisions": {
            result.spec.name: "PASS" if decision.admitted else "REJECT"
            for result, decision in zip(results, decisions, strict=True)
        },
    }
    report_path = args.report if args.report.is_absolute() else PROJECT_ROOT / args.report
    write_project_json(report_path, run_report)
    print(json.dumps(run_report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
