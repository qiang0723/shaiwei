from datetime import date

import pandas as pd

from shaiwei.backtest.baseline import cost_scenario_metrics, g0_backtest_summary, window_segments
from shaiwei.backtest.strategy import is_rebalance_step
from shaiwei.config import EvaluationWindow


def test_biweekly_rebalance_is_every_tenth_trading_step():
    assert [step for step in range(22) if is_rebalance_step(step, 10)] == [0, 10, 20]


def test_validation_split_is_inside_training_and_before_test():
    window = EvaluationWindow(
        name="W",
        train_start=date(2016, 1, 1),
        train_end=date(2018, 12, 31),
        test_start=date(2019, 1, 1),
        test_end=date(2019, 12, 31),
    )
    segments = window_segments(window, 6)
    assert segments.train == ("2016-01-01", "2018-06-30")
    assert segments.valid == ("2018-07-01", "2018-12-31")
    assert segments.test == ("2019-01-01", "2019-12-31")


def test_cost_scenarios_reprice_reported_cost_and_g0_counts_windows():
    report = pd.DataFrame({"return": [0.02], "bench": [0.01], "cost": [0.001]})
    metrics = cost_scenario_metrics(report, [1.0, 1.5])
    assert metrics["1"]["cumulative_excess"] > metrics["1.5"]["cumulative_excess"]
    windows = [{"cost_scenarios": metrics} for _ in range(6)]
    summary = g0_backtest_summary(windows)
    assert summary["positive_excess_windows"] == 6
    assert summary["window_condition_pass"]
    assert summary["cost_1_5_condition_pass"]
