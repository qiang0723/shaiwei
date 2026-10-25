"""g1-v2 因子准入执行规格（`docs/G1_SPEC_V2.md`、`config/g1_v2_spec.yaml`）。

在 g1-v1 冻结门之上只替换 ④ 的两项与 DSR 的作用对象，并改用 PIT 支撑中性化。`research/g1.py` 一行不改：共享门原样调用
其 `_evaluate_gates`，再替换四个门。g1-v2 只有在 `g1-positive-control-v2` 标定为 G1_CALIBRATED 且用户确认启用后才可裁决真实候选；
本模块不提供任何写正式准入账本的入口。
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Literal

import pandas as pd
import yaml
from pydantic import BaseModel, ConfigDict, Field

from shaiwei.benchmark.fitness import neutralized_factor_values
from shaiwei.config import PROJECT_ROOT, Settings
from shaiwei.research.g1 import (
    FamilyTrials,
    G1Error,
    G1Evidence,
    _evaluate_gates,
    _gate,
    deflated_sharpe_probability,
    newey_west_mean_t,
    periodic_sharpe,
)

SPEC_PATH = PROJECT_ROOT / "config" / "g1_v2_spec.yaml"
V1_REPLACED = ("incremental_net_icir", "incremental_net_excess", "valid_trial_sharpes", "deflated_sharpe")
V2_ADDED = ("incremental_icir_t", "excess_noninferiority", "valid_trial_increment_irs", "deflated_increment_ir")
INCREMENT_GATES = ("incremental_icir_t", "valid_trial_increment_irs", "deflated_increment_ir")
_V1_ONLY_STATISTICS = (
    "valid_trial_sharpes", "dsr_probability", "observed_periodic_sharpe",
    "expected_maximum_periodic_sharpe", "skewness", "kurtosis", "z_score",
)


class G1V2Error(G1Error):
    pass


class _Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Thresholds(_Frozen):
    dsr_probability_threshold: float
    hac_t_threshold: float
    hac_lags: int = Field(ge=1)
    min_observations: int = Field(ge=1)
    min_valid_trial_increment_irs: int = Field(ge=2)
    max_expression_tokens: int
    max_ast_nodes: int
    min_economic_rationale_chars: int
    max_library_abs_correlation: float
    min_positive_windows: int
    min_rank_ic_retention: float
    max_stress_drawdown: float
    max_turnover_ratio: float
    factor_blend_weight: float
    slippage_stress_extra_each_side: float
    incremental_icir_t_threshold: float
    excess_noninferiority_t_threshold: float


class Discovery(_Frozen):
    start: date
    end: date


class LedgerFields(_Frozen):
    selection_metric: Literal["selection_increment_ir"]


class G1V2Spec(_Frozen):
    schema_version: Literal["g1-v2"]
    spec_version: Literal["g1-v2"]
    status: Literal["FROZEN_BEFORE_IMPLEMENTATION"]
    frozen_on: date
    document: str
    supersedes_for_new_decisions: Literal["g1-v1"]
    thresholds: Thresholds
    discovery: Discovery
    neutralization: Literal["pit_support"]
    gates: tuple[str, ...]
    ledger_fields: LedgerFields


@dataclass(frozen=True)
class SpecIdentity:
    spec: G1V2Spec
    sha256: str


def load_spec(settings: Settings, path: Path = SPEC_PATH) -> SpecIdentity:
    """共享门复用 g1-v1 计算（读 settings.g1_admission）：两边共有的阈值必须逐项相等，否则拒绝。"""
    raw = path.read_bytes()
    spec = G1V2Spec.model_validate(yaml.safe_load(raw.decode("utf-8")))
    v1 = settings.g1_admission.model_dump()
    shared = {key: value for key, value in spec.thresholds.model_dump().items() if key in v1}
    drift = sorted(key for key, value in shared.items() if v1[key] != value)
    if drift:
        raise G1V2Error(f"g1-v2 thresholds differ from the reused g1-v1 computation: {drift}")
    if (spec.discovery.start, spec.discovery.end) != (settings.g1_admission.discovery_start, settings.g1_admission.discovery_end):
        raise G1V2Error("g1-v2 discovery period differs from g1-v1")
    v1_gates = {"pit_and_shift", "complexity", "economic_rationale", "library_correlation", "rolling_window_sign",
                "rank_ic_retention", "stress_drawdown", "turnover", "cost_2x", "slippage_2x", "hac_t", *V1_REPLACED}
    if set(spec.gates) != (v1_gates - set(V1_REPLACED)) | set(V2_ADDED) or len(spec.gates) != len(set(spec.gates)):
        raise G1V2Error("g1-v2 gate list is not g1-v1 with exactly the four frozen replacements")
    return SpecIdentity(spec=spec, sha256=hashlib.sha256(raw).hexdigest())


class G1EvidenceV2(G1Evidence):
    schema_version: Literal[2]  # type: ignore[assignment]  # g1-v1 模型只接受 1，正式裁判读到 v2 证据即拒
    neutralization: Literal["pit_support"]
    candidate_score_rank_ic: dict[str, float]
    baseline_score_rank_ic: dict[str, float]
    candidate_daily_net_excess: dict[str, float]
    baseline_daily_net_excess: dict[str, float]


def neutralized_pit(observations: pd.DataFrame, *, min_cross_section: int) -> pd.Series:
    """g1-v2 中性化：同一回归，但支撑只要求当日因子、行业、市值非空；标签以常数占位，不再按未来标签裁剪支撑。"""
    return neutralized_factor_values(observations.assign(label=0.0), min_cross_section=min_cross_section)


def paired_differences(left: dict[str, float], right: dict[str, float]) -> list[float]:
    """同日配对：两侧均有有限值的日期才计入，按日期排序。"""
    days = sorted(day for day in set(left) & set(right) if math.isfinite(left[day]) and math.isfinite(right[day]))
    return [left[day] - right[day] for day in days]


def family_increment_irs(experiments_path: Path, families: tuple[str, ...]) -> tuple[float, ...]:
    values: list[float] = []
    with experiments_path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if json.loads(row["params_json"]).get("g1_research_family") in families:
                value = json.loads(row["result_json"]).get("selection_increment_ir")
                if isinstance(value, (int, float)) and math.isfinite(float(value)):
                    values.append(float(value))
    return tuple(values)


def increment_gates(
    spec: G1V2Spec, increments: list[float], *, trial_irs: tuple[float, ...], trial_count: int
) -> tuple[dict[str, dict[str, object]], dict[str, object]]:
    threshold = spec.thresholds
    t_value = newey_west_mean_t(increments, lags=threshold.hac_lags, minimum=threshold.min_observations)
    information_ratio = periodic_sharpe(increments, minimum=threshold.min_observations)
    enough = len(trial_irs) >= threshold.min_valid_trial_increment_irs
    if enough:
        dsr, details = deflated_sharpe_probability(
            increments, trial_sharpes=trial_irs, trial_count=trial_count, minimum=threshold.min_observations
        )
    else:
        dsr, details = 0.0, {"expected_maximum_periodic_sharpe": None, "skewness": None, "kurtosis": None, "z_score": None}
    gates = {
        "incremental_icir_t": _gate(
            t_value, t_value >= threshold.incremental_icir_t_threshold,
            f"NW({threshold.hac_lags}) t of paired daily RankIC difference>={threshold.incremental_icir_t_threshold}",
        ),
        "valid_trial_increment_irs": _gate(
            len(trial_irs), enough, f"valid trial increment IRs>={threshold.min_valid_trial_increment_irs}; failed attempts still count in N",
        ),
        "deflated_increment_ir": _gate(dsr, dsr >= threshold.dsr_probability_threshold, f"DSR of paired increment>={threshold.dsr_probability_threshold}"),
    }
    statistics = {
        "increment_t": t_value, "increment_ir": information_ratio, "increment_observations": len(increments),
        "increment_trial_count": trial_count, "valid_trial_increment_irs": len(trial_irs), "increment_dsr_probability": dsr,
        **{f"increment_{key}": value for key, value in details.items() if key != "observed_periodic_sharpe"},
    }
    return gates, statistics


def evaluate_gates_v2(
    settings: Settings,
    spec: G1V2Spec,
    evidence: G1EvidenceV2,
    trials: FamilyTrials,
    trial_irs: tuple[float, ...],
) -> tuple[dict[str, dict[str, object]], dict[str, object]]:
    v1_fields = set(G1Evidence.model_fields)
    v1_view = G1Evidence.model_validate({**evidence.model_dump(include=v1_fields), "schema_version": 1})
    gates, statistics = _evaluate_gates(settings, v1_view, trials)
    for name in V1_REPLACED:
        gates.pop(name)
    for name in _V1_ONLY_STATISTICS:
        statistics.pop(name, None)
    increments = paired_differences(evidence.candidate_score_rank_ic, evidence.baseline_score_rank_ic)
    excess = paired_differences(evidence.candidate_daily_net_excess, evidence.baseline_daily_net_excess)
    ledger_ir = trials.candidate_result.get("selection_increment_ir")
    if not isinstance(ledger_ir, (int, float)) or not math.isfinite(float(ledger_ir)):
        raise G1V2Error("candidate experiment lacks a finite selection_increment_ir")
    observed_ir = periodic_sharpe(increments, minimum=spec.thresholds.min_observations)
    if not math.isclose(observed_ir, float(ledger_ir), rel_tol=1e-9, abs_tol=1e-12):
        raise G1V2Error("paired increments do not reproduce ledger selection_increment_ir")
    increment, increment_statistics = increment_gates(spec, increments, trial_irs=trial_irs, trial_count=trials.trial_count)
    threshold = spec.thresholds
    excess_t = newey_west_mean_t(excess, lags=threshold.hac_lags, minimum=threshold.min_observations)
    gates.update(increment)
    gates["excess_noninferiority"] = _gate(
        excess_t, excess_t > threshold.excess_noninferiority_t_threshold,
        f"NW({threshold.hac_lags}) t of paired daily net excess difference>{threshold.excess_noninferiority_t_threshold}",
    )
    if set(gates) != set(spec.gates):
        raise G1V2Error(f"g1-v2 gate set differs from the frozen spec: {sorted(set(gates) ^ set(spec.gates))}")
    statistics.update(increment_statistics, excess_t=excess_t, excess_observations=len(excess))
    return {name: gates[name] for name in spec.gates}, statistics
