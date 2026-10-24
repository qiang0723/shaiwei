"""标定候选的组合证据：指标口径逐项沿用 `g1_pipeline.evaluate_candidate`（等价性测试钉住）。

另加两项协议要求、但不作门的诊断：R2 的纯因子 Top30 模式（跳过 90/10 混合），以及逐调仓日
候选/基线 Top30 Jaccard 与“因子 RankIC → 分数 RankIC → 组合净超额”的传递链（协议 §6）。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Literal

import pandas as pd

from shaiwei.backtest.strategy import is_rebalance_step
from shaiwei.config import Settings
from shaiwei.research.factor_portfolio import (
    SignalBacktest,
    augment_signal,
    backtest_signal,
    daily_rank_ic,
    icir,
)
from shaiwei.research.g1 import periodic_sharpe
from shaiwei.research.g1_pipeline import (
    BaselineWindow,
    G1PipelineError,
    _compound,
    _stress_drawdown,
    _window_values,
)

Mode = Literal["blend", "factor_only"]
Backtester = Callable[..., SignalBacktest]


@dataclass(frozen=True)
class PortfolioEvidence:
    in_sample_ic: float
    direction: float
    oos_windows: dict[str, float]
    daily_oos: list[float]
    stress: dict[str, float]
    metrics: dict[str, float]
    daily_net_excess: list[float]
    diagnostics: dict[str, object]


def _between(series: pd.Series, start: object, end: object) -> pd.Series:
    return series.loc[(series.index >= pd.Timestamp(start)) & (series.index <= pd.Timestamp(end))]


def _top30_overlap(baseline: BaselineWindow, candidate: pd.Series, *, topk: int, rebalance_days: int) -> dict[str, object]:
    dates = sorted(
        date
        for date in baseline.predictions.index.get_level_values("datetime").unique()
        if pd.Timestamp(baseline.window.test_start) <= pd.Timestamp(date) <= pd.Timestamp(baseline.window.test_end)
    )
    candidate_dates = set(candidate.index.get_level_values("datetime").unique())
    rows = []
    for step, trade_date in enumerate(dates):
        if not is_rebalance_step(step, rebalance_days) or trade_date not in candidate_dates:
            continue
        base = set(baseline.predictions.xs(trade_date, level="datetime").dropna().nlargest(topk).index)
        cand = set(candidate.xs(trade_date, level="datetime").dropna().nlargest(topk).index)
        union = base | cand
        rows.append(
            {
                "date": pd.Timestamp(trade_date).date().isoformat(),
                "jaccard": len(base & cand) / len(union) if union else 1.0,
                "replaced": topk - len(base & cand),
            }
        )
    mean = float(pd.Series([row["jaccard"] for row in rows]).mean()) if rows else None
    return {"window": baseline.window.name, "mean_jaccard": mean, "rebalances": rows}


def _ratio(numerator: float, denominator: float) -> float | None:
    return numerator / denominator if denominator else None


def build_portfolio_evidence(
    settings: Settings,
    *,
    factor: pd.Series,
    factor_daily_ic: pd.Series,
    labels: pd.Series,
    baselines: list[BaselineWindow],
    mode: Mode,
    backtest: Backtester = backtest_signal,
) -> PortfolioEvidence:
    threshold = settings.g1_admission
    direction_period = _between(factor_daily_ic, threshold.discovery_start, threshold.discovery_end)
    if len(direction_period) < threshold.min_observations:
        raise G1PipelineError("discovery period lacks the frozen minimum daily IC observations")
    in_sample_ic = float(direction_period.mean())
    if in_sample_ic == 0:
        raise G1PipelineError("candidate discovery RankIC is zero")
    direction = 1.0 if in_sample_ic > 0 else -1.0
    oriented = direction * factor

    baseline_ic, candidate_ic_parts, baseline_returns, candidate_returns = [], [], [], []
    cost_2x_returns, slippage_2x_returns, overlap = [], [], []
    baseline_turnover = candidate_turnover = 0.0
    for baseline in baselines:
        start, end = baseline.window.test_start.isoformat(), baseline.window.test_end.isoformat()
        if mode == "blend":
            candidate = augment_signal(baseline.predictions, oriented, factor_weight=threshold.factor_blend_weight)
        else:
            candidate = oriented
        candidate_ic = daily_rank_ic(candidate, baseline.labels)
        normal = backtest(settings, candidate, start_time=start, end_time=end)
        cost_2x = backtest(settings, candidate, start_time=start, end_time=end, cost_multiplier=2.0)
        slippage_2x = backtest(
            settings,
            candidate,
            start_time=start,
            end_time=end,
            extra_open_cost=threshold.slippage_stress_extra_each_side,
            extra_close_cost=threshold.slippage_stress_extra_each_side,
        )
        baseline_ic.append(baseline.daily_ic)
        candidate_ic_parts.append(candidate_ic)
        baseline_returns.append(baseline.backtest.daily_excess)
        candidate_returns.append(normal.daily_excess)
        cost_2x_returns.append(cost_2x.daily_excess)
        slippage_2x_returns.append(slippage_2x.daily_excess)
        baseline_turnover += baseline.backtest.turnover
        candidate_turnover += normal.turnover
        overlap.append(
            _top30_overlap(baseline, candidate, topk=settings.backtest.topk, rebalance_days=settings.backtest.rebalance_days)
        )

    baseline_ic_series = pd.concat(baseline_ic).sort_index()
    candidate_ic_series = pd.concat(candidate_ic_parts).sort_index()
    candidate_return_series = pd.concat(candidate_returns).sort_index()
    metrics = {
        "selection_sharpe": periodic_sharpe(candidate_return_series.tolist(), minimum=threshold.min_observations),
        "baseline_net_icir": icir(baseline_ic_series),
        "candidate_net_icir": icir(candidate_ic_series),
        "baseline_net_excess": _compound(pd.concat(baseline_returns).sort_index()),
        "candidate_net_excess": _compound(candidate_return_series),
        "cost_2x_net_excess": _compound(pd.concat(cost_2x_returns).sort_index()),
        "slippage_2x_net_excess": _compound(pd.concat(slippage_2x_returns).sort_index()),
        "baseline_turnover": baseline_turnover,
        "candidate_turnover": candidate_turnover,
    }
    stress = {
        period.name: _stress_drawdown(
            oriented,
            labels,
            start=pd.Timestamp(period.start),
            end=pd.Timestamp(period.end),
            topk=settings.backtest.topk,
            rebalance_days=settings.backtest.rebalance_days,
            roundtrip_cost=settings.backtest.open_cost + settings.backtest.close_cost,
        )
        for period in settings.evaluation.stress_periods
    }
    windows = settings.evaluation.g0_windows
    daily_oos = _between(factor_daily_ic, min(w.test_start for w in windows), max(w.test_end for w in windows))
    factor_oos_ic = direction * float(daily_oos.mean())
    score_ic_increment = float(candidate_ic_series.mean() - baseline_ic_series.mean())
    excess_increment = metrics["candidate_net_excess"] - metrics["baseline_net_excess"]
    diagnostics = {
        "mode": mode,
        "top30_overlap": overlap,
        "transmission": {
            "factor_oriented_oos_rank_ic": factor_oos_ic,
            "score_rank_ic_increment": score_ic_increment,
            "net_excess_increment": excess_increment,
            "retention_factor_to_score": _ratio(score_ic_increment, factor_oos_ic),
            "net_excess_per_unit_score_ic": _ratio(excess_increment, score_ic_increment),
        },
    }
    return PortfolioEvidence(
        in_sample_ic=in_sample_ic,
        direction=direction,
        oos_windows=_window_values(factor_daily_ic, settings),
        daily_oos=[float(value) for value in daily_oos],
        stress=stress,
        metrics=metrics,
        daily_net_excess=[float(value) for value in candidate_return_series],
        diagnostics=diagnostics,
    )
