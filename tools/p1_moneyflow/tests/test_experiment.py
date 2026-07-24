import pandas as pd
import pytest

from tools.p1_moneyflow.experiment import (
    CANDIDATE_SPECS,
    COMPARISON_POLICY,
    P1ExperimentError,
    _factor_series,
    _quantize_backtest,
    _validate_residual_panel,
    candidate_experiment_id,
    comparison_policy_sha256,
    ts_code_to_qlib,
    warning_day_diagnostic,
)
from tools.p1_moneyflow.features import FORMAL_CANDIDATES
from shaiwei.research.factor_portfolio import SignalBacktest


def test_frozen_budget_has_six_attempts_and_108_evidence_cells():
    assert tuple(spec.name for spec in CANDIDATE_SPECS) == FORMAL_CANDIDATES
    assert COMPARISON_POLICY["candidate_attempt_count"] == 6
    assert COMPARISON_POLICY["window_count"] == 6
    assert COMPARISON_POLICY["scenario_count"] == 3
    assert COMPARISON_POLICY["evidence_cell_count"] == 108


def test_candidate_id_is_bound_to_code_data_and_policy():
    policy = comparison_policy_sha256()
    first = candidate_experiment_id("mf_net_intensity_1d", "c" * 64, "d" * 64, policy)
    assert first == candidate_experiment_id(
        "mf_net_intensity_1d", "c" * 64, "d" * 64, policy
    )
    assert first != candidate_experiment_id(
        "mf_net_intensity_1d", "e" * 64, "d" * 64, policy
    )
    assert first != candidate_experiment_id(
        "mf_net_intensity_1d", "c" * 64, "d" * 64, "f" * 64
    )


def test_factor_series_maps_only_shenzhen_and_shanghai():
    frame = pd.DataFrame(
        {
            "trade_date": ["20260105", "20260105"],
            "ts_code": ["000001.SZ", "600000.SH"],
            "factor": [1.0, 2.0],
        }
    )
    result = _factor_series(frame, "factor")
    assert result.index.get_level_values("instrument").tolist() == ["SH600000", "SZ000001"]
    assert ts_code_to_qlib("688001.SH") == "SH688001"
    with pytest.raises(P1ExperimentError, match="\\.BJ"):
        ts_code_to_qlib("920001.BJ")


def test_factor_series_fails_closed_on_duplicate_keys():
    frame = pd.DataFrame(
        {
            "trade_date": ["20260105", "20260105"],
            "ts_code": ["000001.SZ", "000001.SZ"],
            "factor": [1.0, 2.0],
        }
    )
    with pytest.raises(P1ExperimentError, match="duplicate"):
        _factor_series(frame, "factor")


def test_residual_panel_requires_strict_t_plus_one_lineage():
    row = {
        "trade_date": "20260106",
        "source_trade_date": "20260105",
        "ts_code": "000001.SZ",
        **{candidate: 1.0 for candidate in FORMAL_CANDIDATES},
    }
    _validate_residual_panel(pd.DataFrame([row]), name="formal")
    row["source_trade_date"] = row["trade_date"]
    with pytest.raises(P1ExperimentError, match="T\\+1"):
        _validate_residual_panel(pd.DataFrame([row]), name="formal")


def test_warning_day_diagnostic_is_not_for_verdict():
    dates = pd.date_range("2026-01-01", periods=4)
    daily_ic = pd.Series([0.01, 0.02, -0.01, 0.03], index=dates)
    result = warning_day_diagnostic(daily_ic, {dates[1]})
    assert result["verdict_authority"] == "NOT_FOR_VERDICT"
    assert result["included_observations"] == 4
    assert result["excluded_observations"] == 3
    assert result["removed_observations"] == 1


def test_backtest_quantization_removes_last_bit_runtime_noise():
    index = pd.date_range("2026-01-01", periods=3)
    first = SignalBacktest(
        daily_excess=pd.Series([0.01, -0.02, 0.03], index=index),
        cumulative_excess=0.0,
        turnover=1.234567890123,
        max_drawdown=0.0,
    )
    second = SignalBacktest(
        daily_excess=pd.Series(
            [0.01 + 1e-15, -0.02 - 1e-15, 0.03 + 1e-15], index=index
        ),
        cumulative_excess=0.0,
        turnover=1.234567890123 + 1e-15,
        max_drawdown=0.0,
    )
    first_quantized = _quantize_backtest(first)
    second_quantized = _quantize_backtest(second)
    pd.testing.assert_series_equal(
        first_quantized.daily_excess, second_quantized.daily_excess
    )
    assert first_quantized.cumulative_excess == second_quantized.cumulative_excess
    assert first_quantized.turnover == second_quantized.turnover
    assert first_quantized.max_drawdown == second_quantized.max_drawdown
