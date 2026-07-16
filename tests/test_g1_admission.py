import csv
import json
import math
from pathlib import Path

import numpy as np
import pytest

from shaiwei.config import load
from shaiwei.ledger import sha256_file
from shaiwei.research.g1 import (
    G1Error,
    deflated_sharpe_probability,
    evaluate_g1,
    expected_maximum_sharpe,
    family_trials,
    newey_west_mean_t,
    periodic_sharpe,
)


EXPERIMENT_HEADER = [
    "experiment_id",
    "parent_experiment_id",
    "ts",
    "candidate_source",
    "model_or_engine",
    "engine_version",
    "seed",
    "prompt_hash",
    "code_sha256",
    "data_snapshot_sha256",
    "feature_or_formula",
    "params_json",
    "train_period",
    "valid_period",
    "result_json",
    "admitted",
    "reject_reason",
]
ADMISSION_HEADER = [
    "decision_id",
    "evaluated_at",
    "candidate_experiment_id",
    "research_family",
    "evidence_sha256",
    "spec_sha256",
    "experiment_ledger_sha256",
    "trial_count",
    "valid_trial_sharpes",
    "report_path",
    "report_sha256",
    "admitted",
    "failed_gates",
]


def _returns() -> list[float]:
    x = np.arange(300, dtype=float)
    return (0.002 + 0.01 * np.sin(x / 3.0)).tolist()


def _daily_ic() -> list[float]:
    x = np.arange(300, dtype=float)
    return (0.03 + 0.02 * np.sin(x / 4.0)).tolist()


def _write_experiments(path: Path, candidate_sharpe: float, *, include_failed: bool = False) -> None:
    rows = [
        {
            "experiment_id": "trial-1",
            "parent_experiment_id": "",
            "ts": "2026-07-16T00:00:00+00:00",
            "candidate_source": "AlphaGen-GP",
            "model_or_engine": "GP",
            "engine_version": "1",
            "seed": "1",
            "prompt_hash": "",
            "code_sha256": "c" * 64,
            "data_snapshot_sha256": "d" * 64,
            "feature_or_formula": "Mean($close, 5) / $close - 1",
            "params_json": json.dumps(
                {"g1_research_family": "stage1-gp-v1", "expression_tokens": 8, "ast_nodes": 12}
            ),
            "train_period": "2016~2023",
            "valid_period": "2019~2024",
            "result_json": json.dumps({"selection_sharpe": candidate_sharpe * 0.97}),
            "admitted": "false",
            "reject_reason": "candidate attempt",
        },
        {
            "experiment_id": "candidate-2",
            "parent_experiment_id": "",
            "ts": "2026-07-16T00:01:00+00:00",
            "candidate_source": "AlphaGen-GP",
            "model_or_engine": "GP",
            "engine_version": "1",
            "seed": "2",
            "prompt_hash": "",
            "code_sha256": "c" * 64,
            "data_snapshot_sha256": "d" * 64,
            "feature_or_formula": "Std($volume, 10) / Mean($volume, 10)",
            "params_json": json.dumps(
                {"g1_research_family": "stage1-gp-v1", "expression_tokens": 9, "ast_nodes": 14}
            ),
            "train_period": "2016~2023",
            "valid_period": "2019~2024",
            "result_json": json.dumps({"selection_sharpe": candidate_sharpe}),
            "admitted": "false",
            "reject_reason": "candidate attempt",
        },
        {
            "experiment_id": "other-family",
            "parent_experiment_id": "",
            "ts": "2026-07-16T00:02:00+00:00",
            "candidate_source": "CogAlpha-lite",
            "model_or_engine": "LLM-code",
            "engine_version": "1",
            "seed": "3",
            "prompt_hash": "p",
            "code_sha256": "c" * 64,
            "data_snapshot_sha256": "d" * 64,
            "feature_or_formula": "other",
            "params_json": json.dumps(
                {"g1_research_family": "stage1-cog-v1", "expression_tokens": 4, "ast_nodes": 7}
            ),
            "train_period": "2016~2023",
            "valid_period": "2019~2024",
            "result_json": json.dumps({"selection_sharpe": 99.0}),
            "admitted": "false",
            "reject_reason": "candidate attempt",
        },
    ]
    if include_failed:
        rows.insert(
            1,
            {
                **rows[0],
                "experiment_id": "failed-code",
                "ts": "2026-07-16T00:00:30+00:00",
                "result_json": json.dumps({"status": "failed"}),
            },
        )
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=EXPERIMENT_HEADER, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _write_admissions(path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        csv.DictWriter(handle, fieldnames=ADMISSION_HEADER, lineterminator="\n").writeheader()


def _factor_test_report(path: Path) -> Path:
    path.write_text(
        json.dumps(
            {
                "candidate_experiment_id": "candidate-2",
                "code_snapshot_sha256": "c" * 64,
                "data_snapshot_sha256": "d" * 64,
                "pit_sentinel_pass": True,
                "shift_sentinel_pass": True,
            }
        ),
        encoding="utf-8",
    )
    return path


def _evidence(candidate_sharpe: float, factor_test_report: Path) -> dict[str, object]:
    assert candidate_sharpe == pytest.approx(periodic_sharpe(_returns(), minimum=252))
    return {
        "schema_version": 1,
        "candidate_experiment_id": "candidate-2",
        "research_family": "stage1-gp-v1",
        "code_snapshot_sha256": "c" * 64,
        "data_snapshot_sha256": "d" * 64,
        "economic_rationale": "成交量离散度刻画交易拥挤和流动性脆弱性，预期补充现有量价因子。",
        "complexity": {"expression_tokens": 9, "ast_nodes": 14},
        "integrity": {
            "pit_sentinel_pass": True,
            "shift_sentinel_pass": True,
            "test_report_path": str(factor_test_report),
            "test_report_sha256": sha256_file(factor_test_report),
            "max_library_abs_spearman": 0.3,
        },
        "rank_ic": {
            "in_sample": 0.05,
            "oos_windows": {f"W{index}": 0.031 for index in range(1, 7)},
            "daily_oos": _daily_ic(),
        },
        "stress_max_drawdown": {
            "style_shift_2017": 0.12,
            "microcap_crash_2024": 0.18,
            "volume_price_drawdown_2026h1": 0.15,
        },
        "portfolio": {
            "baseline_turnover": 0.3,
            "candidate_turnover": 0.31,
            "baseline_net_icir": 0.4,
            "candidate_net_icir": 0.5,
            "baseline_net_excess": 0.04,
            "candidate_net_excess": 0.06,
            "cost_2x_net_excess": 0.01,
            "slippage_2x_net_excess": 0.008,
            "daily_net_excess_returns": _returns(),
        },
    }


def test_expected_maximum_sharpe_rises_with_trial_count():
    trial_sharpes = (0.01, 0.02, 0.03)
    assert expected_maximum_sharpe(trial_sharpes, 100) > expected_maximum_sharpe(
        trial_sharpes, 2
    )


def test_dsr_falls_as_total_trial_count_rises():
    trial_sharpes = (0.26, 0.27, 0.28)
    small, _ = deflated_sharpe_probability(
        _returns(), trial_sharpes=trial_sharpes, trial_count=3, minimum=252
    )
    large, _ = deflated_sharpe_probability(
        _returns(), trial_sharpes=trial_sharpes, trial_count=1000, minimum=252
    )
    assert 0 <= large < small <= 1


def test_newey_west_t_is_finite_and_directional():
    positive = newey_west_mean_t(_daily_ic(), lags=10, minimum=252)
    negative = newey_west_mean_t([-value for value in _daily_ic()], lags=10, minimum=252)
    assert math.isfinite(positive)
    assert positive > 3
    assert negative == pytest.approx(-positive)


def test_family_trial_n_counts_failed_attempt_but_not_other_family(tmp_path: Path):
    experiments = tmp_path / "experiments.csv"
    _write_experiments(experiments, periodic_sharpe(_returns(), minimum=252), include_failed=True)
    trials = family_trials("stage1-gp-v1", "candidate-2", experiments_path=experiments)
    assert trials.trial_count == 3
    assert len(trials.valid_trial_sharpes) == 2


def test_g1_pass_is_immutable_and_idempotent(tmp_path: Path):
    candidate_sharpe = periodic_sharpe(_returns(), minimum=252)
    experiments = tmp_path / "experiments.csv"
    admissions = tmp_path / "factor_admissions.csv"
    evidence_path = tmp_path / "evidence.json"
    output = tmp_path / "reports"
    factor_test_report = _factor_test_report(tmp_path / "factor_test_report.json")
    _write_experiments(experiments, candidate_sharpe)
    _write_admissions(admissions)
    evidence_path.write_text(
        json.dumps(_evidence(candidate_sharpe, factor_test_report)), encoding="utf-8"
    )

    first = evaluate_g1(
        evidence_path,
        settings=load(),
        experiments_path=experiments,
        admissions_path=admissions,
        output_dir=output,
    )
    second = evaluate_g1(
        evidence_path,
        settings=load(),
        experiments_path=experiments,
        admissions_path=admissions,
        output_dir=output,
    )

    assert first.admitted and not first.reused
    assert second.admitted and second.reused
    assert second.decision_id == first.decision_id
    assert admissions.read_text(encoding="utf-8").count("\n") == 2
    report = json.loads(first.report_path.read_text(encoding="utf-8"))
    assert report["status"] == "PASS"
    assert report["statistics"]["trial_count"] == 2
    assert report["gates"]["deflated_sharpe"]["passed"]


def test_g1_rejects_correlation_at_frozen_boundary(tmp_path: Path):
    candidate_sharpe = periodic_sharpe(_returns(), minimum=252)
    experiments = tmp_path / "experiments.csv"
    admissions = tmp_path / "factor_admissions.csv"
    evidence_path = tmp_path / "evidence.json"
    factor_test_report = _factor_test_report(tmp_path / "factor_test_report.json")
    _write_experiments(experiments, candidate_sharpe)
    _write_admissions(admissions)
    evidence = _evidence(candidate_sharpe, factor_test_report)
    evidence["integrity"]["max_library_abs_spearman"] = 0.5
    evidence_path.write_text(json.dumps(evidence), encoding="utf-8")

    decision = evaluate_g1(
        evidence_path,
        settings=load(),
        experiments_path=experiments,
        admissions_path=admissions,
        output_dir=tmp_path / "reports",
    )
    assert not decision.admitted
    assert "library_correlation" in decision.failed_gates


def test_g1_rejects_returns_not_bound_to_candidate_ledger(tmp_path: Path):
    experiments = tmp_path / "experiments.csv"
    admissions = tmp_path / "factor_admissions.csv"
    evidence_path = tmp_path / "evidence.json"
    factor_test_report = _factor_test_report(tmp_path / "factor_test_report.json")
    actual = periodic_sharpe(_returns(), minimum=252)
    _write_experiments(experiments, actual + 0.01)
    _write_admissions(admissions)
    evidence_path.write_text(
        json.dumps(_evidence(actual, factor_test_report)), encoding="utf-8"
    )
    with pytest.raises(G1Error, match="do not reproduce"):
        evaluate_g1(
            evidence_path,
            settings=load(),
            experiments_path=experiments,
            admissions_path=admissions,
            output_dir=tmp_path / "reports",
        )


def test_g1_insufficient_trial_sharpes_is_a_reject_not_a_system_error(tmp_path: Path):
    candidate_sharpe = periodic_sharpe(_returns(), minimum=252)
    experiments = tmp_path / "experiments.csv"
    admissions = tmp_path / "factor_admissions.csv"
    evidence_path = tmp_path / "evidence.json"
    factor_test_report = _factor_test_report(tmp_path / "factor_test_report.json")
    _write_experiments(experiments, candidate_sharpe)
    with experiments.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    rows[0]["result_json"] = json.dumps({"status": "failed"})
    with experiments.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=EXPERIMENT_HEADER, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    _write_admissions(admissions)
    evidence_path.write_text(
        json.dumps(_evidence(candidate_sharpe, factor_test_report)), encoding="utf-8"
    )

    decision = evaluate_g1(
        evidence_path,
        settings=load(),
        experiments_path=experiments,
        admissions_path=admissions,
        output_dir=tmp_path / "reports",
    )
    assert not decision.admitted
    assert "valid_trial_sharpes" in decision.failed_gates
    assert "deflated_sharpe" in decision.failed_gates


def test_g1_fails_closed_when_factor_test_report_is_tampered(tmp_path: Path):
    candidate_sharpe = periodic_sharpe(_returns(), minimum=252)
    experiments = tmp_path / "experiments.csv"
    admissions = tmp_path / "factor_admissions.csv"
    evidence_path = tmp_path / "evidence.json"
    factor_test_report = _factor_test_report(tmp_path / "factor_test_report.json")
    _write_experiments(experiments, candidate_sharpe)
    _write_admissions(admissions)
    evidence_path.write_text(
        json.dumps(_evidence(candidate_sharpe, factor_test_report)), encoding="utf-8"
    )
    factor_test_report.write_text("{}", encoding="utf-8")

    with pytest.raises(G1Error, match="hash mismatch"):
        evaluate_g1(
            evidence_path,
            settings=load(),
            experiments_path=experiments,
            admissions_path=admissions,
            output_dir=tmp_path / "reports",
        )
