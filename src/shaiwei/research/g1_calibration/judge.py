"""两层判定：原样调用被测裁判（v1：`g1-v1`；v2：`g1-v2`）的门与 N/方差机械统计，只在其上划分 A 信号层 / B 传递层。

v2 另有 N3“基线复制”对照：只按三个增量门判定，三门全过即算“放行”（协议 v2 §3）。
"""

from __future__ import annotations

import hashlib
import json
import math
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from shaiwei.config import PROJECT_ROOT, Settings
from shaiwei.research.g1 import (
    G1Evidence,
    _evaluate_gates,
    _verify_integrity_binding,
    deflated_sharpe_probability,
    family_trials,
    periodic_sharpe,
)
from shaiwei.research.g1_calibration.ledger_view import IsolationError, complete_rows, prefix_snapshot
from shaiwei.research.g1_calibration.protocol import (
    ADMISSION_SCOPE,
    G1_V1_GATES,
    ProtocolError,
    ProtocolIdentity,
)

# 诊断 DSR 只替换试验数 N，试验离散度仍取本格（协议 §5 未另指定方差来源）。
DIAGNOSTIC_DSR_RULE = "trial_count replaced by the diagnostic N; trial Sharpe dispersion from the cell"
INCREMENT_SCHEMA = "g1-calibration-increment-v1"


@dataclass(frozen=True)
class CalibrationVerdict:
    layer_a: bool
    layer_b: bool
    main: bool
    failed_main: tuple[str, ...]
    gates: dict[str, dict[str, object]]
    statistics: dict[str, object]
    trial_count: int
    valid_trial_sharpes: int  # v1：有效选择期 Sharpe 数；v2：有效增量信息比数
    ledger_sha256: str
    cell_trials_sha256: str
    diagnostic_dsr: dict[str, float | None]


class IncrementEvidence(BaseModel):
    """N3 增量证据：只有两条逐日 RankIC 序列，无组合与发现期。"""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    schema_version: Literal["g1-calibration-increment-v1"]
    candidate_experiment_id: str = Field(min_length=1)
    research_family: str = Field(min_length=1)
    code_snapshot_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    data_snapshot_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    candidate_score_rank_ic: dict[str, float]
    baseline_score_rank_ic: dict[str, float]


def _document(path: Path) -> dict[str, object]:
    document = json.loads(path.read_text(encoding="utf-8"))
    if document.pop("admission_scope", None) != ADMISSION_SCOPE:
        raise IsolationError(f"calibration evidence lacks the NOT_FOR_ADMISSION marker: {path}")
    return document


def load_calibration_evidence(path: Path) -> G1Evidence:
    return G1Evidence.model_validate(_document(path))


def cell_trials_sha256(experiments_path: Path, family: str, metric: str = "selection_sharpe") -> str:
    """本格 DSR 实际用到的试验集合（ID 与选择指标）的哈希；与总账其它行的增减无关，复跑稳定。"""
    trials = sorted(
        (row["experiment_id"], json.loads(row["result_json"]).get(metric))
        for row in complete_rows(experiments_path)
        if json.loads(row["params_json"]).get("g1_research_family") == family
    )
    payload = json.dumps(trials, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def _snapshot_trials(experiments_path: Path, family: str, experiment: str, metric: str):
    """scheduler 可能同时追加总账：在完整前缀快照上统计 N 与方差，不读并发写入的半行。"""
    from shaiwei.research.g1_v2 import family_increment_irs

    with tempfile.TemporaryDirectory() as directory:
        snapshot = prefix_snapshot(experiments_path, Path(directory))
        trials = family_trials(family, experiment, experiments_path=snapshot)
        irs = family_increment_irs(snapshot, (family,)) if metric == "selection_increment_ir" else ()
        return trials, irs, cell_trials_sha256(snapshot, family, metric)


def _verdict(protocol, gates, statistics, trials, valid, cell_sha, diagnostic, *, layer_a=None) -> CalibrationVerdict:
    layers = protocol.config.layers
    main_gates = [name for name in (*layers.A_signal, *layers.B_transmission) if name in gates]
    passed_a = all(gates[name]["passed"] for name in layers.A_signal) if layer_a is None else layer_a
    passed_b = all(gates[name]["passed"] for name in layers.B_transmission if name in gates)
    return CalibrationVerdict(
        layer_a=passed_a, layer_b=passed_b, main=passed_a and passed_b,
        failed_main=tuple(name for name in main_gates if not gates[name]["passed"]),
        gates=gates, statistics=statistics, trial_count=trials.trial_count, valid_trial_sharpes=valid,
        ledger_sha256=trials.ledger_sha256, cell_trials_sha256=cell_sha, diagnostic_dsr=diagnostic,
    )


def _diagnostic_dsr(protocol, series: list[float], trial_values: tuple[float, ...], *, minimum_trials: int, minimum: int) -> dict[str, float | None]:
    diagnostic: dict[str, float | None] = {}
    for count in protocol.config.dsr.diagnostic_trial_counts:
        value = None
        if len(trial_values) >= minimum_trials:
            value, _ = deflated_sharpe_probability(series, trial_sharpes=trial_values, trial_count=count, minimum=minimum)
        diagnostic[str(count)] = value
    return diagnostic


def _judge_v1(settings: Settings, protocol: ProtocolIdentity, document: dict[str, object], experiments_path: Path) -> CalibrationVerdict:
    evidence = G1Evidence.model_validate(document)
    trials, _, cell_sha = _snapshot_trials(experiments_path, evidence.research_family, evidence.candidate_experiment_id, "selection_sharpe")
    _verify_integrity_binding(evidence, trials)
    gates, statistics = _evaluate_gates(settings, evidence, trials)
    if set(gates) != G1_V1_GATES:
        raise ProtocolError(f"g1-v1 gate set changed: {sorted(set(gates) ^ G1_V1_GATES)}")
    threshold = settings.g1_admission
    diagnostic = _diagnostic_dsr(
        protocol, evidence.portfolio.daily_net_excess_returns, trials.valid_trial_sharpes,
        minimum_trials=threshold.min_valid_trial_sharpes, minimum=threshold.min_observations,
    )
    return _verdict(protocol, gates, statistics, trials, len(trials.valid_trial_sharpes), cell_sha, diagnostic)


def _judge_v2(settings: Settings, protocol: ProtocolIdentity, document: dict[str, object], experiments_path: Path) -> CalibrationVerdict:
    from shaiwei.research.g1_v2 import G1EvidenceV2, evaluate_gates_v2, load_spec, paired_differences

    spec = load_spec(settings, PROJECT_ROOT / protocol.config.judge.spec_config).spec  # type: ignore[union-attr]
    evidence = G1EvidenceV2.model_validate(document)
    trials, irs, cell_sha = _snapshot_trials(experiments_path, evidence.research_family, evidence.candidate_experiment_id, "selection_increment_ir")
    _verify_integrity_binding(evidence, trials)
    gates, statistics = evaluate_gates_v2(settings, spec, evidence, trials, irs)
    increments = paired_differences(evidence.candidate_score_rank_ic, evidence.baseline_score_rank_ic)
    threshold = spec.thresholds
    diagnostic = _diagnostic_dsr(
        protocol, increments, irs, minimum_trials=threshold.min_valid_trial_increment_irs, minimum=threshold.min_observations,
    )
    return _verdict(protocol, gates, statistics, trials, len(irs), cell_sha, diagnostic)


def _judge_increment(settings: Settings, protocol: ProtocolIdentity, document: dict[str, object], experiments_path: Path) -> CalibrationVerdict:
    from shaiwei.research.g1_v2 import G1V2Error, increment_gates, load_spec, paired_differences

    spec = load_spec(settings, PROJECT_ROOT / protocol.config.judge.spec_config).spec  # type: ignore[union-attr]
    evidence = IncrementEvidence.model_validate(document)
    trials, irs, cell_sha = _snapshot_trials(experiments_path, evidence.research_family, evidence.candidate_experiment_id, "selection_increment_ir")
    binding = (trials.candidate["code_sha256"], trials.candidate["data_snapshot_sha256"])
    if binding != (evidence.code_snapshot_sha256, evidence.data_snapshot_sha256):
        raise IsolationError("increment evidence code/data snapshot does not match the candidate experiment")
    increments = paired_differences(evidence.candidate_score_rank_ic, evidence.baseline_score_rank_ic)
    ledger_ir = trials.candidate_result.get("selection_increment_ir")
    observed = periodic_sharpe(increments, minimum=spec.thresholds.min_observations)
    if not isinstance(ledger_ir, (int, float)) or not math.isclose(observed, float(ledger_ir), rel_tol=1e-9, abs_tol=1e-12):
        raise G1V2Error("paired increments do not reproduce ledger selection_increment_ir")
    gates, statistics = increment_gates(spec, increments, trial_irs=irs, trial_count=trials.trial_count)
    judged = tuple(protocol.config.routes["N3"].judged_gates or ())
    if tuple(gates) != judged:
        raise ProtocolError("N3 judged gates differ from the frozen protocol")
    threshold = spec.thresholds
    diagnostic = _diagnostic_dsr(
        protocol, increments, irs, minimum_trials=threshold.min_valid_trial_increment_irs, minimum=threshold.min_observations,
    )
    released = all(gate["passed"] for gate in gates.values())
    verdict = _verdict(protocol, gates, statistics, trials, len(irs), cell_sha, diagnostic, layer_a=released)
    return verdict


def judge(settings: Settings, protocol: ProtocolIdentity, evidence_path: Path, *, experiments_path: Path) -> CalibrationVerdict:
    document = _document(evidence_path)
    if not str(document.get("research_family", "")).startswith(f"{protocol.config.family}/"):
        raise IsolationError("calibration evidence must stay inside the calibration family")
    if protocol.version == "v1":
        return _judge_v1(settings, protocol, document, experiments_path)
    if document.get("schema_version") == INCREMENT_SCHEMA:
        return _judge_increment(settings, protocol, document, experiments_path)
    return _judge_v2(settings, protocol, document, experiments_path)
