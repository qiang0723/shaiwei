"""Qlib adapter and canonical evidence for the frozen production Head30 treatment."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import numpy as np
import pandas as pd
from qlib.contrib.evaluate import backtest_daily

from shaiwei.backtest.full_target import BiweeklyRankHeadEqualWeightStrategy
from shaiwei.research.model_attribution.effect_metrics import normalize_report
from shaiwei.research.production_conversion.contract import Protocol, ProtocolError


BacktestFunction = Callable[..., tuple[pd.DataFrame, Any]]


def _position_rows(positions: Any) -> list[dict[str, float | int | str]]:
    if not isinstance(positions, dict) or not positions:
        raise ProtocolError("production-converter Qlib positions are absent")
    rows: list[dict[str, float | int | str]] = []
    for day, position in sorted(positions.items(), key=lambda item: pd.Timestamp(item[0])):
        try:
            codes = tuple(str(code) for code in position.get_stock_list())
            cash = float(position.get_cash())
            stock_value = sum(
                float(position.get_stock_amount(code)) * float(position.get_stock_price(code))
                for code in codes
            )
        except (AttributeError, TypeError, ValueError) as error:
            raise ProtocolError("production-converter Qlib position schema differs") from error
        nav = cash + stock_value
        if nav <= 0 or not np.isfinite([cash, stock_value, nav]).all():
            raise ProtocolError("production-converter realized position value is invalid")
        rows.append(
            {
                "date": pd.Timestamp(day).strftime("%Y-%m-%d"),
                "position_count": len(codes),
                "cash_ratio": float(cash / nav),
            }
        )
    return rows


def report_rows(report: pd.DataFrame) -> list[dict[str, float | str]]:
    frame = normalize_report(report)
    return [
        {
            "date": pd.Timestamp(day).strftime("%Y-%m-%d"),
            "gross_return": float(row["gross_return"]),
            "benchmark_return": float(row["benchmark_return"]),
            "recorded_cost": float(row["recorded_cost"]),
            "turnover": float(row["turnover"]),
        }
        for day, row in frame.iterrows()
    ]


def backtest_treatment(
    signal: pd.Series,
    *,
    start: str,
    end: str,
    protocol: Protocol,
    backtest_function: BacktestFunction = backtest_daily,
) -> dict[str, Any]:
    constants = protocol.document["constants"]
    strategy = BiweeklyRankHeadEqualWeightStrategy(
        signal=signal,
        topk=int(constants["topk"]),
        rebalance_days=int(constants["rebalance_trade_days"]),
        risk_degree=protocol.target_investment_ratio,
        forbid_all_trade_at_limit=bool(constants["forbid_all_trade_at_limit"]),
    )
    report, positions = backtest_function(
        start_time=start,
        end_time=end,
        strategy=strategy,
        account=float(constants["account_rmb"]),
        benchmark=str(constants["benchmark"]),
        exchange_kwargs={
            "deal_price": str(constants["deal_price"]),
            "limit_threshold": ("$limit_buy", "$limit_sell"),
            "open_cost": float(constants["open_cost"]),
            "close_cost": float(constants["close_cost"]),
            "min_cost": float(constants["minimum_cost_rmb"]),
        },
    )
    rows = report_rows(report)
    if not strategy.rebalance_evidence:
        raise ProtocolError("production-converter treatment produced no rebalance evidence")
    return {
        "daily": rows,
        "rebalances": strategy.rebalance_evidence,
        "positions": _position_rows(positions),
    }


__all__ = ["backtest_treatment", "report_rows"]
