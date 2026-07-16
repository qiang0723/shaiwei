"""Canonical same-budget signal comparison used by G1 evidence production."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from qlib.contrib.evaluate import backtest_daily

from shaiwei.backtest.strategy import BiweeklyTopkDropoutStrategy
from shaiwei.config import Settings


class FactorPortfolioError(RuntimeError):
    pass


@dataclass(frozen=True)
class SignalBacktest:
    daily_excess: pd.Series
    cumulative_excess: float
    turnover: float
    max_drawdown: float


def _rank_signal(signal: pd.Series) -> pd.Series:
    if not isinstance(signal.index, pd.MultiIndex) or signal.index.nlevels != 2:
        raise FactorPortfolioError("signal must have a two-level datetime/instrument index")
    ranked = signal.groupby(level=0).rank(pct=True)
    return ranked.replace([np.inf, -np.inf], np.nan).dropna()


def augment_signal(baseline: pd.Series, factor: pd.Series, *, factor_weight: float) -> pd.Series:
    if not 0 < factor_weight < 1:
        raise ValueError("factor_weight must be between zero and one")
    joined = pd.concat(
        [_rank_signal(baseline).rename("baseline"), _rank_signal(factor).rename("factor")],
        axis=1,
        join="inner",
    ).dropna()
    if joined.empty:
        raise FactorPortfolioError("baseline and factor signals have no common observations")
    return (1.0 - factor_weight) * joined["baseline"] + factor_weight * joined["factor"]


def daily_rank_ic(signal: pd.Series, labels: pd.Series) -> pd.Series:
    joined = pd.concat([signal.rename("signal"), labels.rename("label")], axis=1, join="inner").dropna()
    values: dict[pd.Timestamp, float] = {}
    for trade_date, group in joined.groupby(level=0, sort=True):
        if len(group) < 30 or group["signal"].nunique() < 2 or group["label"].nunique() < 2:
            continue
        values[pd.Timestamp(trade_date)] = float(
            group["signal"].rank(pct=True).corr(group["label"].rank(pct=True))
        )
    return pd.Series(values, dtype=float).dropna()


def icir(daily_ic: pd.Series) -> float:
    clean = pd.to_numeric(daily_ic, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    if len(clean) < 2 or clean.std(ddof=1) <= 0:
        raise FactorPortfolioError("ICIR requires at least two non-constant daily IC observations")
    return float(clean.mean() / clean.std(ddof=1))


def summarize_report(report: pd.DataFrame) -> SignalBacktest:
    required = {"return", "bench", "cost"}
    if missing := required - set(report.columns):
        raise FactorPortfolioError(f"qlib report missing columns: {sorted(missing)}")
    strategy = pd.to_numeric(report["return"], errors="coerce").fillna(0.0) - pd.to_numeric(
        report["cost"], errors="coerce"
    ).fillna(0.0)
    benchmark = pd.to_numeric(report["bench"], errors="coerce").fillna(0.0)
    if (benchmark <= -1).any() or (strategy <= -1).any():
        raise FactorPortfolioError("daily strategy/benchmark returns must exceed -100%")
    daily_excess = (1.0 + strategy) / (1.0 + benchmark) - 1.0
    nav = (1.0 + daily_excess).cumprod()
    drawdown = nav / nav.cummax() - 1.0
    turnover_column = "turnover" if "turnover" in report.columns else "total_turnover"
    if turnover_column not in report.columns:
        raise FactorPortfolioError("qlib report is missing turnover evidence")
    return SignalBacktest(
        daily_excess=daily_excess,
        cumulative_excess=float(nav.iloc[-1] - 1.0),
        turnover=float(pd.to_numeric(report[turnover_column], errors="coerce").fillna(0.0).sum()),
        max_drawdown=float(-drawdown.min()),
    )


def backtest_signal(
    settings: Settings,
    signal: pd.Series,
    *,
    start_time: str,
    end_time: str,
    cost_multiplier: float = 1.0,
    extra_open_cost: float = 0.0,
    extra_close_cost: float = 0.0,
) -> SignalBacktest:
    if cost_multiplier <= 0 or extra_open_cost < 0 or extra_close_cost < 0:
        raise ValueError("cost inputs must be non-negative and multiplier positive")
    strategy = BiweeklyTopkDropoutStrategy(
        signal=signal,
        topk=settings.backtest.topk,
        n_drop=settings.backtest.n_drop,
        rebalance_days=settings.backtest.rebalance_days,
        only_tradable=True,
        forbid_all_trade_at_limit=False,
    )
    report, _ = backtest_daily(
        start_time=start_time,
        end_time=end_time,
        strategy=strategy,
        account=settings.baseline.account,
        benchmark=settings.backtest.benchmark,
        exchange_kwargs={
            "deal_price": settings.backtest.deal_price,
            "limit_threshold": ("$limit_buy", "$limit_sell"),
            "open_cost": settings.backtest.open_cost * cost_multiplier + extra_open_cost,
            "close_cost": settings.backtest.close_cost * cost_multiplier + extra_close_cost,
            "min_cost": settings.backtest.min_cost,
        },
    )
    return summarize_report(report)
