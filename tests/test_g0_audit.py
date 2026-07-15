import copy

import pytest

from shaiwei.audit.g0 import (
    validate_alphagen_report,
    validate_baseline_report,
    validate_sentinel_report,
)
from shaiwei.backtest.metrics import g0_backtest_summary
from shaiwei.config import load


def _sentinel_report() -> dict:
    results = [
        {
            "sentinel": f"S{number}",
            "status": "NOT_APPLICABLE" if number == 10 else "PASS",
            "metrics": {},
            "anomalies": [],
        }
        for number in range(1, 11)
    ]
    return {"required_failures": [], "results": results}


def _baseline_report() -> dict:
    settings = load()
    scenarios = {
        f"{multiplier:g}": {
            "strategy_return": 0.1,
            "benchmark_return": 0.05,
            "cumulative_excess": 0.04,
            "reported_cost_sum": 0.01 * multiplier,
        }
        for multiplier in settings.backtest.cost_scenarios
    }
    windows = [
        {"window": window.name, "prediction_rows": 100, "cost_scenarios": copy.deepcopy(scenarios)}
        for window in settings.evaluation.g0_windows
    ]
    return {"windows": windows, "g0_backtest": g0_backtest_summary(windows)}


def _alphagen_report() -> dict:
    candidates = {
        "Add($close,$open)": {"rank_ic": 0.01, "daily_ic_count": 100, "error": ""},
        "Sub($high,$low)": {"rank_ic": -1.0, "error": "rank_ic_nan"},
    }
    return {
        "candidates": candidates,
        "summary": {
            "elapsed_seconds": 1.5,
            "setup_elapsed_seconds": 0.5,
            "evolution_elapsed_seconds": 1.0,
            "peak_memory_bytes": 1024,
            "input_label_rows": 1000,
            "input_exposure_rows": 900,
            "candidate_count": 2,
            "failed_candidate_count": 1,
            "rank_ic": {"min": -1.0, "median": -0.495, "max": 0.01},
            "decision": "stop",
        },
    }


def test_g0_sentinel_validation_recomputes_failure_detail():
    report = _sentinel_report()
    assert validate_sentinel_report(report, environment="dev")["condition_pass"]
    report["results"][0]["status"] = "FAIL"
    with pytest.raises(ValueError, match="required_failures"):
        validate_sentinel_report(report, environment="dev")


def test_g0_baseline_validation_recomputes_declared_flags():
    report = _baseline_report()
    assert validate_baseline_report(report, load())["window_condition_pass"]
    report["g0_backtest"]["window_condition_pass"] = False
    with pytest.raises(ValueError, match="recomputed"):
        validate_baseline_report(report, load())


def test_g0_baseline_validation_rejects_empty_window_predictions():
    report = _baseline_report()
    report["windows"][0]["prediction_rows"] = 0
    with pytest.raises(ValueError, match="no predictions"):
        validate_baseline_report(report, load())


def test_g0_alphagen_validation_requires_real_candidates_and_matching_summary():
    report = _alphagen_report()
    assert validate_alphagen_report(report)["candidate_count"] == 2
    report["summary"]["candidate_count"] = 0
    with pytest.raises(ValueError, match="candidate_count"):
        validate_alphagen_report(report)
    report = _alphagen_report()
    report["candidates"] = {}
    with pytest.raises(ValueError, match="at least one"):
        validate_alphagen_report(report)
