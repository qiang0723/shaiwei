"""M6-2 frozen Top30 execution and score-overlap diagnostics."""

from __future__ import annotations

from typing import Any, Callable

import pandas as pd
from qlib.contrib.evaluate import backtest_daily

from shaiwei.backtest.strategy import BiweeklyTopkDropoutStrategy
from shaiwei.research.model_attribution.contract import AttributionError
from shaiwei.research.model_attribution.effect_data import WindowModelOutput
from shaiwei.research.model_attribution.effect_metrics import normalize_report
from shaiwei.research.model_attribution.effect_schema import ARMS


BacktestFunction = Callable[..., tuple[pd.DataFrame, Any]]


def backtest_signal(
    signal: pd.Series,
    *,
    start: str,
    end: str,
    protocol: dict[str, Any],
    backtest_function: BacktestFunction = backtest_daily,
) -> pd.DataFrame:
    portfolio = protocol["portfolio"]
    strategy = BiweeklyTopkDropoutStrategy(
        signal=signal,
        topk=int(portfolio["topk"]),
        n_drop=int(portfolio["n_drop"]),
        rebalance_days=int(portfolio["rebalance_trade_days"]),
        only_tradable=bool(portfolio["only_tradable"]),
        forbid_all_trade_at_limit=bool(portfolio["forbid_all_trade_at_limit"]),
    )
    report, _ = backtest_function(
        start_time=start,
        end_time=end,
        strategy=strategy,
        account=float(portfolio["account_rmb"]),
        benchmark=str(portfolio["benchmark"]),
        exchange_kwargs={
            "deal_price": str(portfolio["deal_price"]),
            "limit_threshold": ("$limit_buy", "$limit_sell"),
            "open_cost": float(portfolio["open_cost"]),
            "close_cost": float(portfolio["close_cost"]),
            "min_cost": float(portfolio["minimum_cost_rmb"]),
        },
    )
    return normalize_report(report)


def execute_window(
    output: WindowModelOutput,
    window: dict[str, Any],
    protocol: dict[str, Any],
    *,
    backtest_function: BacktestFunction = backtest_daily,
) -> tuple[dict[str, pd.DataFrame], dict[str, pd.DataFrame]]:
    if tuple(output.test_predictions) != ARMS:
        raise AttributionError("M6 execution arm order differs")
    reports = {
        arm: backtest_signal(
            output.test_predictions[arm],
            start=str(window["test"][0]),
            end=str(window["test"][1]),
            protocol=protocol,
            backtest_function=backtest_function,
        )
        for arm in ARMS
    }
    stress: dict[str, pd.DataFrame] = {}
    if output.window == "W6":
        if tuple(output.stress_predictions) != ARMS:
            raise AttributionError("M6 W6 stress arm order differs")
        stress = {
            arm: backtest_signal(
                output.stress_predictions[arm],
                start="2026-01-01",
                end="2026-06-30",
                protocol=protocol,
                backtest_function=backtest_function,
            )
            for arm in ARMS
        }
    return reports, stress


def scheduled_top30(prediction: pd.Series, *, rebalance_days: int = 10) -> dict[str, list[str]]:
    dates = sorted(pd.to_datetime(prediction.index.get_level_values(0)).unique())
    output: dict[str, list[str]] = {}
    for step, date in enumerate(dates):
        if step % rebalance_days:
            continue
        cross = prediction.xs(date, level=0).rename("score").reset_index()
        cross["instrument"] = cross["instrument"].astype(str)
        cross = cross.sort_values(["score", "instrument"], ascending=[False, True])
        if len(cross) < 30:
            raise AttributionError("M6 signal Top30 cross-section is insufficient")
        output[pd.Timestamp(date).strftime("%Y-%m-%d")] = cross["instrument"].head(30).tolist()
    if not output:
        raise AttributionError("M6 signal Top30 schedule is empty")
    return output


def score_overlap_diagnostics(predictions: dict[str, pd.Series]) -> dict[str, Any]:
    if tuple(predictions) != ARMS:
        raise AttributionError("M6 score diagnostic arm order differs")
    control = predictions[ARMS[0]]
    control_top = scheduled_top30(control)
    output: dict[str, Any] = {}
    for arm in ARMS[1:]:
        alternative = predictions[arm]
        if not control.index.equals(alternative.index):
            raise AttributionError("M6 score correlation keys differ")
        correlations: list[float] = []
        for day, scores in control.groupby(level=0, sort=True):
            other = alternative.xs(day, level=0)
            scores = scores.droplevel(0)
            if not scores.index.equals(other.index):
                raise AttributionError("M6 score correlation keys differ")
            correlation = float(scores.corr(other, method="spearman"))
            if not pd.notna(correlation):
                raise AttributionError("M6 score correlation is nonfinite")
            correlations.append(correlation)
        alternative_top = scheduled_top30(alternative)
        if tuple(control_top) != tuple(alternative_top):
            raise AttributionError("M6 scheduled Top30 dates differ")
        overlaps = [len(set(control_top[day]) & set(alternative_top[day])) / 30.0 for day in control_top]
        output[arm] = {
            "mean_daily_score_spearman_vs_control": float(pd.Series(correlations).mean()),
            "mean_scheduled_signal_top30_overlap": float(pd.Series(overlaps).mean()),
            "scheduled_rebalance_count": len(overlaps),
        }
    return output
