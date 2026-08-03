"""Immutable F1-1 evidence and append-only experiment-ledger bindings."""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from shaiwei.ledger import EXPERIMENTS, append_experiment, portable_artifact_path, sha256_file
from shaiwei.research.fundamental_effect.contract import (
    CandidateSpec,
    FundamentalEffectError,
    FundamentalEffectProtocol,
)
from shaiwei.research.fundamental_effect.io import write_json_once
from shaiwei.research.fundamental_effect.metrics import CandidateResult, DiscoveryResult
from shaiwei.research.fundamental_effect.runtime import EffectRuntime


def candidate_experiment_id(
    candidate: str,
    code_hash: str,
    data_hash: str,
    policy_hash: str,
    runtime: EffectRuntime,
) -> str:
    payload = f"{runtime.research_family}|{candidate}|{code_hash}|{data_hash}|{policy_hash}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]


def _existing_experiment(experiment_id: str) -> dict[str, str] | None:
    with EXPERIMENTS.open(newline="", encoding="utf-8") as handle:
        rows = [row for row in csv.DictReader(handle) if row["experiment_id"] == experiment_id]
    if len(rows) > 1:
        raise FundamentalEffectError(f"duplicate F1-1 experiment ID: {experiment_id}")
    return rows[0] if rows else None


def _json_equal(value: str, expected: object) -> bool:
    try:
        return json.loads(value) == expected
    except json.JSONDecodeError:
        return False


def ensure_experiment(
    *,
    experiment_id: str,
    spec: CandidateSpec,
    code_hash: str,
    data_hash: str,
    policy_hash: str,
    result: dict[str, object],
    reject_reason: str,
    runtime: EffectRuntime,
) -> bool:
    params = {
        "g1_research_family": runtime.research_family,
        "expression_tokens": spec.expression_tokens,
        "ast_nodes": spec.ast_nodes,
        "attempt_stage": "formal_fundamental_effect",
        "candidate": spec.name,
        "pre_registered_direction": spec.direction,
        "factor_blend_weight": 0.1,
        "comparison_policy_sha256": policy_hash,
        "candidate_attempt_count": runtime.candidate_attempt_count,
    }
    expected = {
        "candidate_source": runtime.candidate_source,
        "model_or_engine": runtime.model_or_engine,
        "engine_version": runtime.engine_version,
        "seed": "42",
        "prompt_hash": "",
        "code_sha256": code_hash,
        "data_snapshot_sha256": data_hash,
        "feature_or_formula": spec.formula,
        "params_json": params,
        "train_period": runtime.train_period,
        "valid_period": runtime.valid_period,
        "result_json": result,
        "admitted": "false",
        "reject_reason": reject_reason,
    }
    if existing := _existing_experiment(experiment_id):
        for field, value in expected.items():
            actual: object = existing[field]
            if field in {"params_json", "result_json"}:
                if not _json_equal(str(actual), value):
                    raise FundamentalEffectError(
                        f"existing F1-1 experiment differs: {experiment_id}.{field}"
                    )
            elif actual != value:
                raise FundamentalEffectError(
                    f"existing F1-1 experiment differs: {experiment_id}.{field}"
                )
        return True
    append_experiment(
        experiment_id=experiment_id,
        parent_experiment_id="",
        candidate_source=expected["candidate_source"],
        model_or_engine=expected["model_or_engine"],
        engine_version=expected["engine_version"],
        seed=42,
        prompt_hash="",
        code_sha256=code_hash,
        data_snapshot_sha256=data_hash,
        feature_or_formula=spec.formula,
        params_json=params,
        train_period=expected["train_period"],
        valid_period=expected["valid_period"],
        result_json=result,
        admitted=False,
        reject_reason=reject_reason,
    )
    return False


def build_candidate_artifacts(
    result: CandidateResult,
    *,
    code_hash: str,
    data_hash: str,
    policy_hash: str,
    panel_report_path: Path,
    panel_report_sha256: str,
    daily_returns_path: Path,
    daily_returns_sha256: str,
    daily_ic_path: Path,
    daily_ic_sha256: str,
    output_root: Path,
    runtime: EffectRuntime,
) -> tuple[Path, Path, bool]:
    directory = output_root / result.experiment_id
    test_report: dict[str, object] = {
        "schema_version": runtime.factor_test_schema,
        "candidate_experiment_id": result.experiment_id,
        "code_snapshot_sha256": code_hash,
        "data_snapshot_sha256": data_hash,
        "candidate": result.discovery.spec.name,
        "pre_registered_direction": result.discovery.spec.direction,
        "comparison_policy_sha256": policy_hash,
        "pit_sentinel_pass": True,
        "shift_sentinel_pass": True,
        "sentinel_basis": {
            "panel_report_path": portable_artifact_path(panel_report_path),
            "panel_report_sha256": panel_report_sha256,
            "future_formation_rows": 0,
            "bse_rows": 0,
            "effective_on_formation_close_for_next_open": True,
        },
        "daily_returns_path": portable_artifact_path(daily_returns_path),
        "daily_returns_sha256": daily_returns_sha256,
        "daily_ic_path": portable_artifact_path(daily_ic_path),
        "daily_ic_sha256": daily_ic_sha256,
    }
    test_path, test_sha, test_reused = write_json_once(
        directory / "factor_tests.json", test_report
    )
    daily_oos = result.factor_daily_ic.loc[
        (result.factor_daily_ic.index >= pd.Timestamp("2019-01-01"))
        & (result.factor_daily_ic.index <= pd.Timestamp("2024-12-31"))
    ]
    evidence: dict[str, object] = {
        "schema_version": 1,
        "candidate_experiment_id": result.experiment_id,
        "research_family": runtime.research_family,
        "multiple_testing_families": list(runtime.multiple_testing_families),
        "code_snapshot_sha256": code_hash,
        "data_snapshot_sha256": data_hash,
        "economic_rationale": result.discovery.spec.rationale,
        "complexity": {
            "expression_tokens": result.discovery.spec.expression_tokens,
            "ast_nodes": result.discovery.spec.ast_nodes,
        },
        "integrity": {
            "pit_sentinel_pass": True,
            "shift_sentinel_pass": True,
            "test_report_path": portable_artifact_path(test_path),
            "test_report_sha256": test_sha,
            "max_library_abs_spearman": result.max_library_abs_spearman,
        },
        "rank_ic": {
            "in_sample": result.discovery.mean_rank_ic,
            "oos_windows": result.oos_windows,
            "daily_oos": [float(value) for value in daily_oos],
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
    evidence_path, _, evidence_reused = write_json_once(directory / "g1_evidence.json", evidence)
    return test_path, evidence_path, test_reused and evidence_reused


def experiment_result(
    result: CandidateResult,
    *,
    test_path: Path,
    evidence_path: Path,
) -> dict[str, object]:
    return {
        "status": "PASS_DIRECTION",
        "pre_registered_direction": result.discovery.spec.direction,
        "discovery_mean_rank_ic": result.discovery.mean_rank_ic,
        "discovery_observations": result.discovery.observation_count,
        "selection_sharpe": result.selection_sharpe,
        "baseline_net_icir": result.baseline_net_icir,
        "candidate_net_icir": result.candidate_net_icir,
        "baseline_net_excess": result.baseline_net_excess,
        "candidate_net_excess": result.candidate_net_excess,
        "cost_2x_net_excess": result.cost_2x_net_excess,
        "slippage_2x_net_excess": result.slippage_2x_net_excess,
        "baseline_turnover": result.baseline_turnover,
        "candidate_turnover": result.candidate_turnover,
        "factor_test_report_path": portable_artifact_path(test_path),
        "factor_test_report_sha256": sha256_file(test_path),
        "evidence_path": portable_artifact_path(evidence_path),
        "evidence_sha256": sha256_file(evidence_path),
    }


def direction_reject_result(discovery: DiscoveryResult) -> dict[str, object]:
    return {
        "status": "REJECT_DIRECTION",
        "pre_registered_direction": discovery.spec.direction,
        "discovery_mean_rank_ic": discovery.mean_rank_ic,
        "discovery_observations": discovery.observation_count,
        "oos_effect_read": False,
        "g1_run": False,
    }


def family_trial_count(runtime: EffectRuntime) -> int:
    with EXPERIMENTS.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    count = 0
    for row in rows:
        try:
            params = json.loads(row["params_json"])
        except json.JSONDecodeError as error:
            raise FundamentalEffectError("experiment ledger contains invalid params JSON") from error
        count += params.get("g1_research_family") in runtime.multiple_testing_families
    return count


def record_execution_failure(
    protocol: FundamentalEffectProtocol,
    *,
    code_hash: str,
    data_hash: str,
    error_type: str,
    runtime: EffectRuntime,
) -> None:
    experiment_id = hashlib.sha256(
        (
            f"{runtime.research_family}|implementation|{code_hash}|{data_hash}|"
            f"{protocol.policy_sha256}"
        ).encode()
    ).hexdigest()[:12]
    if _existing_experiment(experiment_id):
        return
    append_experiment(
        experiment_id=experiment_id,
        parent_experiment_id="",
        ts=datetime.now(timezone.utc).isoformat(),
        candidate_source=runtime.implementation_source,
        model_or_engine=runtime.implementation_engine,
        engine_version=runtime.engine_version,
        seed=42,
        prompt_hash="",
        code_sha256=code_hash,
        data_snapshot_sha256=data_hash,
        feature_or_formula="IMPLEMENTATION_ATTEMPT",
        params_json={
            "g1_research_family": runtime.research_family,
            "attempt_stage": "effect_execution_after_label_read",
            "comparison_policy_sha256": protocol.policy_sha256,
        },
        train_period=runtime.train_period,
        valid_period=runtime.valid_period,
        result_json={"status": "FAILED", "error_type": error_type},
        admitted=False,
        reject_reason=f"{runtime.research_family} implementation failure: {error_type}",
    )


def stable_decision_summary(result: CandidateResult) -> dict[str, object]:
    return {
        "candidate": result.discovery.spec.name,
        "experiment_id": result.experiment_id,
        "pre_registered_direction": result.discovery.spec.direction,
        "discovery_mean_rank_ic": result.discovery.mean_rank_ic,
        "oos_rank_ic": result.oos_windows,
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
    }
