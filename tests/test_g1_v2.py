"""g1-v2 裁判（docs/G1_SPEC_V2.md）的合成测试：不读真实数据，g1-v1 原样复用。"""

import csv
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml
from pydantic import ValidationError

from shaiwei.benchmark.fitness import neutralized_factor_values
from shaiwei.config import load
from shaiwei.ledger import EXPERIMENTS
from shaiwei.research.g1 import G1Evidence, family_trials, periodic_sharpe
from shaiwei.research.g1_v2 import (
    SPEC_PATH,
    G1EvidenceV2,
    G1V2Error,
    evaluate_gates_v2,
    family_increment_irs,
    increment_gates,
    load_spec,
    neutralized_pit,
    paired_differences,
)

FAMILY = "synthetic-v2"


@pytest.fixture(scope="module")
def settings():
    return load()


@pytest.fixture(scope="module")
def spec(settings):
    return load_spec(settings).spec


def test_spec_is_bound_to_the_frozen_hash_and_refuses_drift(settings, tmp_path):
    identity = load_spec(settings)
    protocol = yaml.safe_load(Path("config/g1_positive_control_v2.yaml").read_text(encoding="utf-8"))
    assert identity.sha256 == protocol["judge"]["spec_config_sha256"]
    text = SPEC_PATH.read_text(encoding="utf-8")
    for old, new in (("hac_t_threshold: 3.0", "hac_t_threshold: 2.5"), ("  - deflated_increment_ir\n", "  - deflated_sharpe\n")):
        drifted = tmp_path / "spec.yaml"
        drifted.write_text(text.replace(old, new, 1), encoding="utf-8")
        with pytest.raises(G1V2Error):
            load_spec(settings, drifted)


def test_pit_neutralization_no_longer_trims_support_by_future_labels():
    rng = np.random.default_rng(1)
    rows = [(pd.Timestamp("2020-01-02"), f"S{i:02d}", rng.normal(), f"I{i % 3}", float(np.exp(rng.normal(10, 1)))) for i in range(40)]
    frame = pd.DataFrame(rows, columns=["trade_date", "instrument", "factor", "industry", "market_cap"])
    frame["label"] = [np.nan if i < 5 else rng.normal() for i in range(40)]
    v1 = neutralized_factor_values(frame, min_cross_section=30)
    v2 = neutralized_pit(frame.drop(columns=["label"]), min_cross_section=30)
    assert len(v1) == 35 and len(v2) == 40
    assert set(v1.index) < set(v2.index)


def test_paired_differences_align_on_common_finite_days():
    left = {"2020-01-02": 0.03, "2020-01-03": 0.05, "2020-01-06": float("nan"), "2020-01-07": 0.01}
    right = {"2020-01-02": 0.01, "2020-01-06": 0.02, "2020-01-07": 0.02}
    assert paired_differences(left, right) == pytest.approx([0.02, -0.01])


def test_increment_gates_detect_a_real_increment_and_reject_noise(spec):
    rng = np.random.default_rng(7)
    trial_irs = (0.05, 0.10, 0.02, 0.08, 0.04)
    strong = list(0.004 + 0.005 * rng.standard_normal(1200))
    gates, stats = increment_gates(spec, strong, trial_irs=trial_irs, trial_count=5)
    assert gates["incremental_icir_t"]["passed"] and gates["valid_trial_increment_irs"]["passed"]
    assert gates["deflated_increment_ir"]["passed"] and stats["increment_observations"] == 1200
    noise = list(0.005 * rng.standard_normal(1200))
    gates, _ = increment_gates(spec, noise, trial_irs=trial_irs, trial_count=5)
    assert not gates["incremental_icir_t"]["passed"] and not gates["deflated_increment_ir"]["passed"]
    gates, _ = increment_gates(spec, strong, trial_irs=(0.1,), trial_count=5)
    assert not gates["valid_trial_increment_irs"]["passed"] and gates["deflated_increment_ir"]["actual"] == 0.0


def _days(count: int) -> list[str]:
    return [day.date().isoformat() for day in pd.bdate_range("2019-01-02", periods=count)]


def _evidence(settings, *, increment: float, excess_shift: float, experiment: str) -> dict:
    rng = np.random.default_rng(11)
    days = _days(600)
    baseline_ic = {day: float(0.05 + 0.03 * rng.standard_normal()) for day in days}
    candidate_ic = {day: value + increment + 0.004 * float(rng.standard_normal()) for day, value in baseline_ic.items()}
    baseline_excess = {day: float(0.0005 + 0.01 * rng.standard_normal()) for day in days}
    candidate_excess = {day: value + excess_shift + 0.003 * float(rng.standard_normal()) for day, value in baseline_excess.items()}
    windows = {window.name: 0.03 for window in settings.evaluation.g0_windows}
    return {
        "schema_version": 2, "candidate_experiment_id": experiment, "research_family": FAMILY,
        "code_snapshot_sha256": "c" * 64, "data_snapshot_sha256": "d" * 64,
        "economic_rationale": "合成测试候选，经济含义陈述满二十个字符以上。",
        "complexity": {"expression_tokens": 3, "ast_nodes": 3},
        "integrity": {"pit_sentinel_pass": True, "shift_sentinel_pass": True, "test_report_path": "x", "test_report_sha256": "e" * 64,
                      "max_library_abs_spearman": 0.1},
        "rank_ic": {"in_sample": 0.04, "oos_windows": windows, "daily_oos": [float(0.03 + 0.05 * rng.standard_normal()) for _ in days]},
        "stress_max_drawdown": {period.name: 0.1 for period in settings.evaluation.stress_periods},
        "portfolio": {
            "baseline_turnover": 10.0, "candidate_turnover": 10.5, "baseline_net_icir": 1.0, "candidate_net_icir": 1.1,
            "baseline_net_excess": 0.2, "candidate_net_excess": 0.1, "cost_2x_net_excess": 0.05, "slippage_2x_net_excess": 0.04,
            "daily_net_excess_returns": list(candidate_excess.values()),
        },
        "neutralization": "pit_support",
        "candidate_score_rank_ic": candidate_ic, "baseline_score_rank_ic": baseline_ic,
        "candidate_daily_net_excess": candidate_excess, "baseline_daily_net_excess": baseline_excess,
    }


def _ledger(tmp_path: Path, settings, documents: list[dict]) -> Path:
    path = tmp_path / "experiments.csv"
    header = EXPERIMENTS.read_text(encoding="utf-8").splitlines()[0].split(",")
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=header, lineterminator="\n")
        writer.writeheader()
        for document in documents:
            increments = paired_differences(document["candidate_score_rank_ic"], document["baseline_score_rank_ic"])
            result = {
                "selection_sharpe": periodic_sharpe(document["portfolio"]["daily_net_excess_returns"], minimum=252),
                "selection_increment_ir": periodic_sharpe(increments, minimum=252),
            }
            writer.writerow({
                **{key: "" for key in header}, "experiment_id": document["candidate_experiment_id"],
                "code_sha256": "c" * 64, "data_snapshot_sha256": "d" * 64, "feature_or_formula": "x",
                "params_json": json.dumps({"g1_research_family": FAMILY, "expression_tokens": 3, "ast_nodes": 3}),
                "result_json": json.dumps(result), "admitted": "false",
            })
    return path


def test_evaluate_gates_v2_replaces_exactly_four_gates_and_binds_the_ledger(settings, spec, tmp_path):
    documents = [
        _evidence(settings, increment=0.004, excess_shift=-0.0001, experiment="cand"),
        _evidence(settings, increment=0.001, excess_shift=0.0, experiment="peer1"),
        _evidence(settings, increment=0.0, excess_shift=0.0, experiment="peer2"),
    ]
    ledger = _ledger(tmp_path, settings, documents)
    evidence = G1EvidenceV2.model_validate(documents[0])
    trials = family_trials(FAMILY, "cand", experiments_path=ledger)
    gates, stats = evaluate_gates_v2(settings, spec, evidence, trials, family_increment_irs(ledger, (FAMILY,)))
    assert tuple(gates) == spec.gates
    assert gates["incremental_icir_t"]["passed"] and gates["excess_noninferiority"]["passed"]
    assert not gates["valid_trial_increment_irs"]["passed"] or stats["valid_trial_increment_irs"] == 3
    assert "dsr_probability" not in stats and stats["increment_trial_count"] == 3
    shifted = {day: value * 1.5 for day, value in evidence.candidate_score_rank_ic.items()}
    with pytest.raises(G1V2Error, match="reproduce"):
        evaluate_gates_v2(settings, spec, evidence.model_copy(update={"candidate_score_rank_ic": shifted}), trials, ())
    worse = _evidence(settings, increment=0.004, excess_shift=-0.003, experiment="cand")
    ledger = _ledger(tmp_path, settings, [worse, *documents[1:]])
    trials = family_trials(FAMILY, "cand", experiments_path=ledger)
    gates, _ = evaluate_gates_v2(settings, spec, G1EvidenceV2.model_validate(worse), trials, family_increment_irs(ledger, (FAMILY,)))
    assert not gates["excess_noninferiority"]["passed"]


def test_formal_g1_v1_judge_rejects_v2_evidence(settings):
    document = _evidence(settings, increment=0.004, excess_shift=0.0, experiment="cand")
    with pytest.raises(ValidationError):
        G1Evidence.model_validate(document)
    with pytest.raises(ValidationError):
        G1EvidenceV2.model_validate({**document, "schema_version": 1})
