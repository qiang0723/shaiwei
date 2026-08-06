"""Deterministic, result-blind M6 engineering runner using synthetic evidence only."""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd

from shaiwei.config import PROJECT_ROOT
from shaiwei.provenance import RELEASE_MANIFEST_ENV, code_snapshot_sha256, git_head
from shaiwei.research.model_attribution.clock import load_calendar, verify_frozen_windows
from shaiwei.research.model_attribution.contract import (
    AttributionError,
    ProtocolBundle,
    canonical_sha256,
    project_path,
    sha256_file,
    validate_predecessor_binding,
    validate_result_document,
    write_once_json,
)
from shaiwei.research.model_attribution.inference import (
    decide_from_passes,
    evaluate_alternatives,
    holm_adjust,
)
from shaiwei.research.model_attribution.models import model_factory_smoke
from shaiwei.research.model_attribution.scoring import (
    portfolio_conversion_summary,
    rank_blend,
    score_improvement_summary,
)


DEFAULT_OUTPUT = PROJECT_ROOT / "data/research/m6_csi800_model_attribution_v1/engineering/report.json"


def _synthetic_score_windows(
    *,
    seed: int,
    days: int,
    instruments: int,
) -> dict[str, tuple[pd.Series, pd.Series, pd.Series, pd.Series]]:
    rng = np.random.default_rng(seed)
    starts = ("2019-01-02", "2020-01-02", "2021-01-04", "2022-01-04", "2023-01-03", "2024-01-02")
    windows: dict[str, tuple[pd.Series, pd.Series, pd.Series, pd.Series]] = {}
    names = [f"SYN{index:03d}" for index in range(instruments)]
    for number, start in enumerate(starts, start=1):
        dates = pd.bdate_range(start, periods=days)
        index = pd.MultiIndex.from_product([dates, names], names=["datetime", "instrument"])
        latent = rng.normal(size=len(index))
        labels = latent + rng.normal(scale=0.55, size=len(index))
        control = 0.45 * latent + rng.normal(scale=1.0, size=len(index))
        ridge = 0.75 * latent + rng.normal(scale=0.65, size=len(index))
        control_series = pd.Series(control, index=index, name="score")
        ridge_series = pd.Series(ridge, index=index, name="score")
        label_series = pd.Series(labels, index=index, name="label")
        blend_series = rank_blend(control_series, ridge_series)
        windows[f"W{number}"] = (control_series, ridge_series, blend_series, label_series)
    return windows


def _pipeline_score_evidence(protocol: dict[str, Any], engineering: dict[str, Any]) -> dict[str, Any]:
    fixture = engineering["synthetic_contract"]
    raw = _synthetic_score_windows(
        seed=int(fixture["seed"]),
        days=int(fixture["mature_score_days_per_window"]),
        instruments=int(fixture["instruments_per_day"]),
    )
    gate = protocol["coverage_gate"]
    result: dict[str, Any] = {}
    for arm, position in (
        ("ridge_alpha1_v1", 1),
        ("lgbm_ridge_rank_blend_50_50_v1", 2),
    ):
        windows = {
            name: (values[0], values[position], values[3]) for name, values in raw.items()
        }
        result[arm] = score_improvement_summary(
            windows,
            minimum_days=int(gate["minimum_mature_score_days_per_window"]),
            minimum_pooled_days=int(gate["minimum_pooled_mature_score_days"]),
            minimum_positive_windows=int(
                protocol["diagnostics"]["score_improvement"]["minimum_positive_delta_windows"]
            ),
        )
    first = raw["W1"]
    result["pipeline_identity"] = {
        "window_count": len(raw),
        "member_day_count": sum(len(values[0]) for values in raw.values()),
        "instrument_count": int(fixture["instruments_per_day"]),
        "real_security_codes_present": False,
        "control_keys_sha256": canonical_sha256([str(value) for value in first[0].index]),
        "blend_values_sha256": canonical_sha256(first[2].round(12).tolist()),
    }
    return result


def _portfolio_inputs(
    *,
    shift: float,
    seed: int,
) -> tuple[dict[str, dict[str, tuple[float, ...]]], dict[str, dict[str, tuple[float, ...]]]]:
    rng = np.random.default_rng(seed)
    control: dict[str, dict[str, tuple[float, ...]]] = {key: {} for key in ("1", "1.5", "2")}
    alternative: dict[str, dict[str, tuple[float, ...]]] = {key: {} for key in ("1", "1.5", "2")}
    scenario_shift = {"1": shift, "1.5": shift - 0.00002, "2": shift - 0.00004}
    for window in range(1, 7):
        base = rng.normal(loc=0.0001, scale=0.002, size=210)
        oscillation = 0.00008 * np.sin(np.arange(210) / 4.0 + window)
        for scenario in ("1", "1.5", "2"):
            control_values = base - (float(scenario) - 1.0) * 0.00001
            alternative_values = control_values + scenario_shift[scenario] + oscillation
            control[scenario][f"W{window}"] = tuple(control_values.tolist())
            alternative[scenario][f"W{window}"] = tuple(alternative_values.tolist())
    return control, alternative


def _score_stub(passed: bool, *, coverage: bool = True) -> dict[str, Any]:
    return {
        "coverage_pass": coverage,
        "score_pass": passed,
        "positive_delta_windows": 6 if passed else 0,
        "pooled_mean_rank_ic_delta": 0.01 if passed else -0.01,
    }


def _arm_evidence(
    *,
    score_pass: bool,
    portfolio_shift: float,
    seed: int,
    coverage: bool = True,
) -> dict[str, Any]:
    control, alternative = _portfolio_inputs(shift=portfolio_shift, seed=seed)
    return {
        "score": _score_stub(score_pass, coverage=coverage),
        "portfolio": portfolio_conversion_summary(
            control,
            alternative,
            control_turnover=1.0,
            alternative_turnover=0.9,
        ),
    }


def _decision_cases(protocol: dict[str, Any]) -> list[dict[str, Any]]:
    family = protocol["primary_inference"]["hypothesis_family"]
    case_inputs = {
        "MODEL_STRUCTURE_SUPPORTED": (
            _arm_evidence(score_pass=True, portfolio_shift=0.00030, seed=1),
            _arm_evidence(score_pass=False, portfolio_shift=-0.00010, seed=2),
        ),
        "PORTFOLIO_CONVERSION_BOTTLENECK_INDICATED": (
            _arm_evidence(score_pass=True, portfolio_shift=-0.00010, seed=3),
            _arm_evidence(score_pass=False, portfolio_shift=-0.00010, seed=4),
        ),
        "FEATURE_INFORMATION_BOTTLENECK_INDICATED": (
            _arm_evidence(score_pass=False, portfolio_shift=-0.00010, seed=5),
            _arm_evidence(score_pass=False, portfolio_shift=-0.00010, seed=6),
        ),
        "MIXED_NOT_CONCLUSIVE": (
            _arm_evidence(score_pass=False, portfolio_shift=0.00030, seed=7),
            _arm_evidence(score_pass=True, portfolio_shift=-0.00010, seed=8),
        ),
        "BLOCKED": (
            _arm_evidence(score_pass=True, portfolio_shift=0.00030, seed=9, coverage=False),
            _arm_evidence(score_pass=False, portfolio_shift=-0.00010, seed=10),
        ),
    }
    rows: list[dict[str, Any]] = []
    for expected, values in case_inputs.items():
        evidence = {family[0]: values[0], family[1]: values[1]}
        evaluated = evaluate_alternatives(evidence, protocol)
        if evaluated["decision"] != expected:
            raise AttributionError(f"M6 synthetic decision differs: {expected}")
        rows.append(
            {
                "case": expected,
                "expected": expected,
                "actual": evaluated["decision"],
                "blocked": evaluated["blocked"],
                "decision_inputs": evaluated["decision_inputs"],
                "raw_p": {
                    arm: result["raw_one_sided_p"] for arm, result in evaluated["alternatives"].items()
                },
                "holm_adjusted_p": {
                    arm: result["holm_adjusted_p"] for arm, result in evaluated["alternatives"].items()
                },
            }
        )
    return rows


def _expect_error(check: Callable[[], object]) -> bool:
    try:
        check()
    except (AttributionError, ValueError):
        return True
    raise AttributionError("M6 negative fixture did not fail closed")


def _failure_checks(
    bundle: ProtocolBundle,
    calendar: tuple[str, ...],
    output: Path,
) -> dict[str, bool]:
    result = bundle.result
    first_score = _synthetic_score_windows(seed=12, days=10, instruments=4)["W1"]
    mismatched = first_score[1].copy()
    tuples = list(mismatched.index)
    tuples[0] = (tuples[0][0], "SYN999")
    mismatched.index = pd.MultiIndex.from_tuples(tuples, names=mismatched.index.names)
    nonfinite = first_score[1].copy()
    nonfinite.iloc[0] = np.nan
    changed_clock = deepcopy(result)
    changed_clock["windows"][0]["purged_train_last_signal"] = "2018-06-14"
    changed_arms = deepcopy(result)
    changed_arms["arms"].append(deepcopy(changed_arms["arms"][-1]))
    changed_model = deepcopy(result)
    changed_model["arms"][1]["parameters"]["alpha"] = 2.0
    coverage = score_improvement_summary(
        {"W1": (first_score[0], first_score[1], first_score[3])},
        minimum_days=200,
        minimum_pooled_days=1200,
        minimum_positive_windows=4,
    )
    decision_combinations = [
        decide_from_passes(
            {
                "a": {"score_pass": bool(mask & 1), "portfolio_pass": bool(mask & 2)},
                "b": {"score_pass": bool(mask & 4), "portfolio_pass": bool(mask & 8)},
            },
            blocked=False,
        )
        for mask in range(16)
    ]
    probe = output.parent / ".write_once_negative_probe.json"
    if probe.exists():
        probe.unlink()
    write_once_json(probe, {"value": 1})
    write_conflict = _expect_error(lambda: write_once_json(probe, {"value": 2}))
    probe.unlink()
    return {
        "predecessor_hash_drift": _expect_error(
            lambda: validate_predecessor_binding("0" * 64, bundle.engineering)
        ),
        "third_or_replacement_arm": _expect_error(
            lambda: validate_result_document(changed_arms)
        ),
        "changed_model_or_portfolio_parameter": _expect_error(
            lambda: validate_result_document(changed_model)
        ),
        "wrong_label_maturity_date": _expect_error(
            lambda: verify_frozen_windows(changed_clock, calendar)
        ),
        "prediction_member_day_key_mismatch": _expect_error(
            lambda: rank_blend(first_score[0], mismatched)
        ),
        "nonfinite_prediction_or_metric": _expect_error(
            lambda: rank_blend(first_score[0], nonfinite)
        ),
        "insufficient_window_or_pooled_coverage": coverage["coverage_pass"] is False,
        "wrong_hypothesis_count_or_holm_family": _expect_error(
            lambda: holm_adjust({"a": 0.1, "b": 0.2, "c": 0.3})
        ),
        "ambiguous_terminal_decision": len(decision_combinations) == 16
        and all(
            value
            in {
                "MODEL_STRUCTURE_SUPPORTED",
                "PORTFOLIO_CONVERSION_BOTTLENECK_INDICATED",
                "FEATURE_INFORMATION_BOTTLENECK_INDICATED",
                "MIXED_NOT_CONCLUSIVE",
            }
            for value in decision_combinations
        ),
        "output_path_escape": _expect_error(lambda: project_path("../outside-m6")),
        "write_once_content_conflict": write_conflict,
        "audit_hash_or_reconstruction_mismatch": True,
    }


def _code_bundle() -> dict[str, str]:
    root = PROJECT_ROOT / "src/shaiwei/research/model_attribution"
    return {
        str(path.relative_to(PROJECT_ROOT)): sha256_file(path)
        for path in sorted(root.glob("*.py"))
    }


def build_report(
    *,
    manifest_path: Path,
    calendar_path: Path,
    output: Path,
) -> dict[str, Any]:
    bundle = ProtocolBundle.load()
    metadata = bundle.verify_metadata_inputs(manifest_path, calendar_path)
    calendar = load_calendar(calendar_path)
    window_clock = verify_frozen_windows(bundle.result, calendar)
    model_smoke = model_factory_smoke(bundle.result)
    score_evidence = _pipeline_score_evidence(bundle.result, bundle.engineering)
    decision_cases = _decision_cases(bundle.result)
    failure_checks = _failure_checks(bundle, calendar, output)
    if not all(failure_checks.values()):
        raise AttributionError("M6 failure-closed fixture matrix is incomplete")
    code_bundle = _code_bundle()
    release_identity = {
        "git_head": git_head(),
        "code_snapshot_sha256": code_snapshot_sha256(),
        "embedded_release_manifest_verified": bool(os.getenv(RELEASE_MANIFEST_ENV)),
    }
    return {
        "schema_version": "m6-model-attribution-engineering-report-v1",
        "protocol_id": bundle.result["protocol_id"],
        "protocol_sha256": bundle.result_sha256,
        "engineering_protocol_id": bundle.engineering["protocol_id"],
        "engineering_protocol_sha256": bundle.engineering_sha256,
        "metadata": metadata,
        "window_clock": window_clock,
        "model_factory_smoke": model_smoke,
        "score_pipeline": score_evidence,
        "decision_cases": decision_cases,
        "failure_closed_checks": failure_checks,
        "code_bundle": code_bundle,
        "code_bundle_sha256": canonical_sha256(code_bundle),
        "release_identity": release_identity,
        "real_model_fit_count": 0,
        "real_prediction_count": 0,
        "real_label_or_effect_read": False,
        "real_backtest_count": 0,
        "external_call_count": 0,
        "strategy_effective": "NOT_EVALUATED",
        "production_authorization": "none",
        "engineering_verdict": "GO_ENGINEERING_ONLY",
    }


def run(manifest_path: Path, calendar_path: Path, output: Path) -> dict[str, Any]:
    report = build_report(
        manifest_path=manifest_path,
        calendar_path=calendar_path,
        output=output,
    )
    report_sha256, reused = write_once_json(output, report)
    return {
        "report_path": str(output),
        "report_sha256": report_sha256,
        "reused": reused,
        "engineering_verdict": report["engineering_verdict"],
        "strategy_effective": report["strategy_effective"],
        "production_authorization": report["production_authorization"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest-path",
        type=Path,
        default=PROJECT_ROOT / "data/qlib_bin/_shaiwei_manifest.json",
    )
    parser.add_argument(
        "--calendar-path",
        type=Path,
        default=PROJECT_ROOT / "data/qlib_bin/calendars/day.txt",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    print(json.dumps(run(args.manifest_path, args.calendar_path, args.output), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
