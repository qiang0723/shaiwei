"""两层判定：原样调用 `g1-v1` 的门与 N/方差机械统计，只在其上划分 A 信号层 / B 传递层（协议 §2）。"""

from __future__ import annotations

import hashlib
import json
import tempfile
from dataclasses import dataclass
from pathlib import Path

from shaiwei.config import Settings
from shaiwei.research.g1 import (
    G1Evidence,
    _evaluate_gates,
    _verify_integrity_binding,
    deflated_sharpe_probability,
    family_trials,
)
from shaiwei.research.g1_calibration.ledger_view import IsolationError, complete_rows, prefix_snapshot
from shaiwei.research.g1_calibration.protocol import (
    ADMISSION_SCOPE,
    G1_V1_GATES,
    ProtocolError,
    ProtocolIdentity,
)

# 诊断 DSR 只替换试验数 N，试验 Sharpe 离散度仍取本格（协议 §5 未另指定方差来源）。
DIAGNOSTIC_DSR_RULE = "trial_count replaced by the diagnostic N; trial Sharpe dispersion from the cell"


@dataclass(frozen=True)
class CalibrationVerdict:
    layer_a: bool
    layer_b: bool
    main: bool
    failed_main: tuple[str, ...]
    gates: dict[str, dict[str, object]]
    statistics: dict[str, object]
    trial_count: int
    valid_trial_sharpes: int
    ledger_sha256: str
    cell_trials_sha256: str
    diagnostic_dsr: dict[str, float | None]


def load_calibration_evidence(path: Path) -> G1Evidence:
    document = json.loads(path.read_text(encoding="utf-8"))
    if document.pop("admission_scope", None) != ADMISSION_SCOPE:
        raise IsolationError(f"calibration evidence lacks the NOT_FOR_ADMISSION marker: {path}")
    return G1Evidence.model_validate(document)


def cell_trials_sha256(experiments_path: Path, family: str) -> str:
    """本格 DSR 实际用到的试验集合（ID 与选择期 Sharpe）的哈希；与总账其它行的增减无关，复跑稳定。"""
    trials = sorted(
        (row["experiment_id"], json.loads(row["result_json"]).get("selection_sharpe"))
        for row in complete_rows(experiments_path)
        if json.loads(row["params_json"]).get("g1_research_family") == family
    )
    payload = json.dumps(trials, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def judge(settings: Settings, protocol: ProtocolIdentity, evidence_path: Path, *, experiments_path: Path) -> CalibrationVerdict:
    evidence = load_calibration_evidence(evidence_path)
    if not evidence.research_family.startswith(f"{protocol.config.family}/"):
        raise IsolationError("calibration evidence must stay inside the calibration family")
    # scheduler 可能同时追加总账：在完整前缀快照上统计 N 与方差，不读并发写入的半行。
    with tempfile.TemporaryDirectory() as directory:
        snapshot = prefix_snapshot(experiments_path, Path(directory))
        trials = family_trials(evidence.research_family, evidence.candidate_experiment_id, experiments_path=snapshot)
        cell_sha = cell_trials_sha256(snapshot, evidence.research_family)
    _verify_integrity_binding(evidence, trials)
    gates, statistics = _evaluate_gates(settings, evidence, trials)
    if set(gates) != G1_V1_GATES:
        raise ProtocolError(f"g1-v1 gate set changed: {sorted(set(gates) ^ G1_V1_GATES)}")
    layers = protocol.config.layers
    main_gates = (*layers.A_signal, *layers.B_transmission)
    threshold = settings.g1_admission
    diagnostic: dict[str, float | None] = {}
    for count in protocol.config.dsr.diagnostic_trial_counts:
        value = None
        if len(trials.valid_trial_sharpes) >= threshold.min_valid_trial_sharpes:
            value, _ = deflated_sharpe_probability(
                evidence.portfolio.daily_net_excess_returns,
                trial_sharpes=trials.valid_trial_sharpes,
                trial_count=count,
                minimum=threshold.min_observations,
            )
        diagnostic[str(count)] = value
    layer_a = all(gates[name]["passed"] for name in layers.A_signal)
    layer_b = all(gates[name]["passed"] for name in layers.B_transmission)
    return CalibrationVerdict(
        layer_a=layer_a,
        layer_b=layer_b,
        main=layer_a and layer_b,
        failed_main=tuple(name for name in main_gates if not gates[name]["passed"]),
        gates=gates,
        statistics=statistics,
        trial_count=trials.trial_count,
        valid_trial_sharpes=len(trials.valid_trial_sharpes),
        ledger_sha256=trials.ledger_sha256,
        cell_trials_sha256=cell_sha,
        diagnostic_dsr=diagnostic,
    )
