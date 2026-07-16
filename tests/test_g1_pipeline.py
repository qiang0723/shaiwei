import pandas as pd
import pytest

from shaiwei.research.g1_pipeline import (
    G1PipelineError,
    _candidate_experiment_id,
    _selected_candidates,
    _stress_drawdown,
)


def test_candidate_selection_ignores_short_sample_false_winner():
    report = {
        "candidates": {
            "one-day": {"rank_ic": -1.0, "daily_ic_count": 1, "error": "insufficient_daily_ic:1"},
            "valid-a": {"rank_ic": 0.02, "daily_ic_count": 252, "error": ""},
            "valid-b": {"rank_ic": 0.03, "daily_ic_count": 300, "error": ""},
        }
    }
    assert _selected_candidates(report, 2) == ["valid-b", "valid-a"]


def test_candidate_selection_ranks_direction_free_discovery_strength():
    report = {
        "candidates": {
            "weak-negative": {"rank_ic": -0.01, "daily_ic_count": 252, "error": ""},
            "strong-negative": {"rank_ic": -0.04, "daily_ic_count": 252, "error": ""},
            "positive": {"rank_ic": 0.03, "daily_ic_count": 252, "error": ""},
        }
    }
    assert _selected_candidates(report, 2) == ["strong-negative", "positive"]


def test_candidate_selection_fails_closed_when_tiny_batch_has_too_few_valid_results():
    report = {"candidates": {"bad": {"rank_ic": -1.0, "error": "rank_ic_nan"}}}
    with pytest.raises(G1PipelineError, match="promotable"):
        _selected_candidates(report, 2)


def test_stress_drawdown_uses_non_overlapping_ten_day_holdings():
    dates = pd.date_range("2020-01-01", periods=30, freq="D")
    instruments = [f"S{index:02d}" for index in range(35)]
    index = pd.MultiIndex.from_product([dates, instruments], names=["datetime", "instrument"])
    factor = pd.Series(list(range(35)) * len(dates), index=index, dtype=float)
    labels = pd.Series(0.01, index=index)
    drawdown = _stress_drawdown(
        factor,
        labels,
        start=dates[0],
        end=dates[-1],
        topk=30,
        rebalance_days=10,
        roundtrip_cost=0.002,
    )
    assert drawdown == 0.0


def test_promoted_experiment_id_is_deterministic_and_snapshot_bound():
    first = _candidate_experiment_id("family", "Mean(close,10)", "c" * 64, "d" * 64)
    assert first == _candidate_experiment_id("family", "Mean(close,10)", "c" * 64, "d" * 64)
    assert first != _candidate_experiment_id("family", "Mean(close,20)", "c" * 64, "d" * 64)
