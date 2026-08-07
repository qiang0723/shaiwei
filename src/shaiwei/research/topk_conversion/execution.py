"""Portfolio-only TopK schedule and injectable Qlib backtest adapter."""

from __future__ import annotations

from typing import Any, Callable

import numpy as np
import pandas as pd
from qlib.contrib.evaluate import backtest_daily

from shaiwei.backtest.strategy import BiweeklyTopkDropoutStrategy
from shaiwei.research.topk_conversion.contract import ConversionError


BacktestFunction = Callable[..., tuple[pd.DataFrame, Any]]
NORMALIZED_COLUMNS = ["gross_return", "benchmark_return", "recorded_cost", "turnover"]


def normalize_report(report: pd.DataFrame) -> pd.DataFrame:
    if list(report.columns) == NORMALIZED_COLUMNS:
        frame = report.copy()
    else:
        missing = {"return", "bench", "cost"} - set(report.columns)
        turnover = "turnover" if "turnover" in report.columns else "total_turnover"
        if missing or turnover not in report.columns:
            raise ConversionError("M6-3 backtest report columns differ")
        frame = report[["return", "bench", "cost", turnover]].copy()
        frame.columns = NORMALIZED_COLUMNS
    frame.index = pd.to_datetime(frame.index)
    frame = frame.sort_index()
    for column in NORMALIZED_COLUMNS:
        frame[column] = pd.to_numeric(frame[column], errors="raise").astype(float)
    if frame.empty or frame.index.has_duplicates or not np.isfinite(frame.to_numpy()).all():
        raise ConversionError("M6-3 backtest report is empty, duplicated, or nonfinite")
    if (frame[["gross_return", "benchmark_return"]] <= -1).any().any():
        raise ConversionError("M6-3 backtest report is not compoundable")
    return frame


def backtest_signal(
    signal: pd.Series,
    *,
    start: str,
    end: str,
    protocol: dict[str, Any],
    topk: int,
    backtest_function: BacktestFunction = backtest_daily,
) -> pd.DataFrame:
    variable = protocol["single_variable_contract"]
    if topk not in (int(variable["control_value"]), int(variable["treatment_value"])):
        raise ConversionError("M6-3 unregistered TopK")
    portfolio = protocol["portfolio_constants"]
    strategy = BiweeklyTopkDropoutStrategy(
        signal=signal,
        topk=topk,
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


def scheduled_topk(
    prediction: pd.Series,
    *,
    topk: int,
    rebalance_days: int,
) -> dict[str, list[str]]:
    if not isinstance(prediction, pd.Series) or not isinstance(prediction.index, pd.MultiIndex):
        raise ConversionError("M6-3 prediction is not a member-day Series")
    if prediction.index.has_duplicates or topk < 1 or rebalance_days < 1:
        raise ConversionError("M6-3 prediction keys or schedule parameters differ")
    values = pd.to_numeric(prediction, errors="raise").astype(float).sort_index()
    if values.empty or not np.isfinite(values.to_numpy()).all():
        raise ConversionError("M6-3 prediction is empty or nonfinite")
    dates = sorted(pd.to_datetime(values.index.get_level_values(0)).unique())
    output: dict[str, list[str]] = {}
    for step, day in enumerate(dates):
        if step % rebalance_days:
            continue
        cross = values.xs(day, level=0).rename("score").reset_index()
        cross["instrument"] = cross["instrument"].astype(str)
        if cross["instrument"].str.endswith(".BJ").any():
            raise ConversionError("M6-3 scheduled set contains .BJ")
        cross = cross.sort_values(["score", "instrument"], ascending=[False, True])
        if len(cross) < topk:
            raise ConversionError("M6-3 scheduled cross-section is insufficient")
        output[pd.Timestamp(day).strftime("%Y-%m-%d")] = cross["instrument"].head(topk).tolist()
    if not output:
        raise ConversionError("M6-3 scheduled set is empty")
    return output


def assert_top30_compatible(
    reference: dict[str, dict[str, list[dict[str, Any]]]],
    replay: dict[str, dict[str, list[dict[str, Any]]]],
) -> None:
    if reference != replay:
        raise ConversionError("M6-3 Top30 replay differs from predecessor")
