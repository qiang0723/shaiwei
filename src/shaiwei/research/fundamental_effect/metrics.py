"""Frozen F1-1 discovery, portfolio, stress, and evidence metrics."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from qlib.data import D

from shaiwei.backtest.qlib_runtime import initialize_qlib
from shaiwei.config import EvaluationWindow, Settings
from shaiwei.research.factor_portfolio import (
    SignalBacktest,
    augment_signal,
    backtest_signal,
    daily_rank_ic,
    icir,
)
from shaiwei.research.fundamental_effect.contract import CandidateSpec, FundamentalEffectError
from shaiwei.research.fundamental_effect.panel import ts_code_to_qlib
from shaiwei.research.g1 import periodic_sharpe
from shaiwei.research.g1_pipeline import BaselineWindow, _compound, _stress_drawdown


BACKTEST_DECIMALS = 10
LABEL_FIELD = "Ref($open,-11)/Ref($open,-1)-1"


@dataclass(frozen=True)
class DiscoveryResult:
    spec: CandidateSpec
    factor: pd.Series
    daily_ic: pd.Series
    mean_rank_ic: float
    observation_count: int
    direction_pass: bool


@dataclass(frozen=True)
class CandidateResult:
    discovery: DiscoveryResult
    experiment_id: str
    factor: pd.Series
    factor_daily_ic: pd.Series
    oos_windows: dict[str, float]
    stress: dict[str, float]
    baseline_turnover: float
    candidate_turnover: float
    baseline_net_icir: float
    candidate_net_icir: float
    baseline_net_excess: float
    candidate_net_excess: float
    cost_2x_net_excess: float
    slippage_2x_net_excess: float
    selection_sharpe: float
    candidate_daily_returns: pd.Series
    max_library_abs_spearman: float
    return_rows: pd.DataFrame
    ic_rows: pd.DataFrame


def factor_series(frame: pd.DataFrame, candidate: str) -> pd.Series:
    required = {"ts_code", "trade_date", candidate}
    if missing := required - set(frame.columns):
        raise FundamentalEffectError(f"F1-1 residual panel lacks {sorted(missing)}")
    selected = frame.loc[:, ["trade_date", "ts_code", candidate]].dropna().copy()
    if selected["ts_code"].astype(str).str.endswith(".BJ").any():
        raise FundamentalEffectError(".BJ returned in an F1-1 residual panel")
    if selected.duplicated(["trade_date", "ts_code"]).any():
        raise FundamentalEffectError("F1-1 residual panel contains duplicate keys")
    selected["datetime"] = pd.to_datetime(selected["trade_date"], format="%Y%m%d")
    selected["instrument"] = selected["ts_code"].map(ts_code_to_qlib)
    result = selected.set_index(["datetime", "instrument"])[candidate]
    result.index = result.index.set_names(["datetime", "instrument"])
    return pd.to_numeric(result, errors="raise").astype(float).sort_index()


def load_labels(settings: Settings) -> pd.Series:
    initialize_qlib(settings)
    frame = D.features(
        D.instruments(settings.baseline.instrument),
        [LABEL_FIELD],
        start_time="2016-07-01",
        end_time="2026-07-31",
        freq="day",
    )
    if frame.empty or LABEL_FIELD not in frame.columns:
        raise FundamentalEffectError("F1-1 qlib label query is empty")
    labels = frame[LABEL_FIELD].rename("label")
    if not isinstance(labels.index, pd.MultiIndex) or labels.index.nlevels != 2:
        raise FundamentalEffectError("F1-1 labels lack a qlib MultiIndex")
    names = list(labels.index.names)
    if names == ["instrument", "datetime"]:
        labels = labels.swaplevel()
    elif names != ["datetime", "instrument"]:
        index_frame = labels.index.to_frame(index=False)
        instrument_column = next(
            (column for column in index_frame if index_frame[column].astype(str).str.match(r"^(SH|SZ)\d{6}$").all()),
            None,
        )
        if instrument_column is None:
            raise FundamentalEffectError("F1-1 could not resolve qlib label index levels")
        datetime_column = next(column for column in index_frame if column != instrument_column)
        labels.index = pd.MultiIndex.from_arrays(
            [
                pd.to_datetime(index_frame[datetime_column]),
                index_frame[instrument_column].astype(str),
            ],
            names=["datetime", "instrument"],
        )
    labels.index = labels.index.set_names(["datetime", "instrument"])
    return pd.to_numeric(labels, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna().sort_index()


def prediction_series(predictions: pd.DataFrame, window: EvaluationWindow) -> pd.Series:
    selected = predictions.loc[predictions["window"].eq(window.name)].copy()
    if selected.empty:
        raise FundamentalEffectError(f"cached Alpha158 predictions lack {window.name}")
    if selected.duplicated(["trade_date", "instrument"]).any():
        raise FundamentalEffectError(f"Alpha158 predictions duplicate {window.name} keys")
    selected["datetime"] = pd.to_datetime(selected["trade_date"], format="%Y%m%d")
    result = selected.set_index(["datetime", "instrument"])["baseline_score"]
    result.index = result.index.set_names(["datetime", "instrument"])
    return pd.to_numeric(result, errors="raise").astype(float).sort_index()


def quantize(value: float) -> float:
    result = float(np.round(float(value), decimals=BACKTEST_DECIMALS))
    return 0.0 if result == 0 else result


def quantize_backtest(result: SignalBacktest) -> SignalBacktest:
    daily = pd.to_numeric(result.daily_excess, errors="raise").round(BACKTEST_DECIMALS)
    daily = daily.mask(daily.eq(0), 0.0)
    nav = (1.0 + daily).cumprod()
    drawdown = nav / nav.cummax() - 1.0
    return SignalBacktest(
        daily_excess=daily,
        cumulative_excess=quantize(float(nav.iloc[-1] - 1.0)),
        turnover=quantize(result.turnover),
        max_drawdown=quantize(float(-drawdown.min())),
    )


def build_baselines(
    settings: Settings,
    labels: pd.Series,
    predictions: pd.DataFrame,
) -> list[BaselineWindow]:
    expected = {window.name for window in settings.evaluation.g0_windows}
    if set(predictions["window"].astype(str)) != expected:
        raise FundamentalEffectError("cached Alpha158 windows differ from W1-W6")
    baselines = []
    for window in settings.evaluation.g0_windows:
        signal = prediction_series(predictions, window)
        dates = labels.index.get_level_values("datetime")
        window_labels = labels.loc[
            (dates >= pd.Timestamp(window.test_start)) & (dates <= pd.Timestamp(window.test_end))
        ]
        daily_ic = daily_rank_ic(signal, window_labels)
        backtest = quantize_backtest(
            backtest_signal(
                settings,
                signal,
                start_time=window.test_start.isoformat(),
                end_time=window.test_end.isoformat(),
            )
        )
        baselines.append(BaselineWindow(window, signal, window_labels, daily_ic, backtest))
    return baselines


def evaluate_discovery(
    spec: CandidateSpec,
    core: pd.DataFrame,
    labels: pd.Series,
    *,
    start: str,
    end: str,
    minimum: int,
) -> DiscoveryResult:
    factor = factor_series(core, spec.name)
    daily_ic = daily_rank_ic(factor, labels)
    discovery = daily_ic.loc[(daily_ic.index >= pd.Timestamp(start)) & (daily_ic.index <= pd.Timestamp(end))]
    if len(discovery) < minimum:
        raise FundamentalEffectError(
            f"{spec.name} discovery has {len(discovery)} observations; need {minimum}"
        )
    mean_rank_ic = float(discovery.mean())
    if not math.isfinite(mean_rank_ic) or mean_rank_ic == 0:
        direction_pass = False
    else:
        direction_pass = spec.direction * mean_rank_ic > 0
    return DiscoveryResult(
        spec=spec,
        factor=factor,
        daily_ic=daily_ic,
        mean_rank_ic=mean_rank_ic,
        observation_count=int(len(discovery)),
        direction_pass=direction_pass,
    )


def _scenario_backtest(
    settings: Settings,
    signal: pd.Series,
    window: EvaluationWindow,
    scenario: str,
) -> SignalBacktest:
    parameters = {
        "normal": (1.0, 0.0),
        "cost_2x": (2.0, 0.0),
        "extra_10bp_each_side": (1.0, 0.001),
    }[scenario]
    return quantize_backtest(
        backtest_signal(
            settings,
            signal,
            start_time=window.test_start.isoformat(),
            end_time=window.test_end.isoformat(),
            cost_multiplier=parameters[0],
            extra_open_cost=parameters[1],
            extra_close_cost=parameters[1],
        )
    )


def _daily_rows(candidate: str, window: str, scenario: str, values: pd.Series) -> pd.DataFrame:
    frame = values.rename("daily_net_excess_return").reset_index()
    frame = frame.rename(columns={frame.columns[0]: "trade_date"})
    frame.insert(0, "scenario", scenario)
    frame.insert(0, "window", window)
    frame.insert(0, "candidate", candidate)
    frame["trade_date"] = pd.to_datetime(frame["trade_date"]).dt.strftime("%Y%m%d")
    return frame


def _ic_rows(candidate: str, series_type: str, window: str, values: pd.Series) -> pd.DataFrame:
    frame = values.rename("rank_ic").reset_index()
    frame = frame.rename(columns={frame.columns[0]: "trade_date"})
    frame.insert(0, "window", window)
    frame.insert(0, "series_type", series_type)
    frame.insert(0, "candidate", candidate)
    frame["trade_date"] = pd.to_datetime(frame["trade_date"]).dt.strftime("%Y%m%d")
    return frame


def _window_values(daily_ic: pd.Series, settings: Settings) -> dict[str, float]:
    result = {}
    for window in settings.evaluation.g0_windows:
        values = daily_ic.loc[
            (daily_ic.index >= pd.Timestamp(window.test_start))
            & (daily_ic.index <= pd.Timestamp(window.test_end))
        ]
        if len(values) < 60:
            raise FundamentalEffectError(f"{window.name} has fewer than 60 F1-1 IC observations")
        result[window.name] = float(values.mean())
    return result


def evaluate_candidate(
    settings: Settings,
    discovery: DiscoveryResult,
    experiment_id: str,
    formal: pd.DataFrame,
    labels: pd.Series,
    baselines: list[BaselineWindow],
    *,
    factor_library_root: Path,
) -> CandidateResult:
    if not discovery.direction_pass:
        raise FundamentalEffectError("direction-failed candidate cannot enter F1-1 OOS evaluation")
    factor = factor_series(formal, discovery.spec.name)
    factor_daily_ic = daily_rank_ic(factor, labels)
    oriented = float(discovery.spec.direction) * factor
    baseline_daily_ic: list[pd.Series] = []
    candidate_daily_ic: list[pd.Series] = []
    baseline_returns: list[pd.Series] = []
    candidate_returns: list[pd.Series] = []
    cost_2x_returns: list[pd.Series] = []
    slippage_returns: list[pd.Series] = []
    return_rows: list[pd.DataFrame] = []
    ic_rows = [_ic_rows(discovery.spec.name, "factor", "ALL", factor_daily_ic)]
    baseline_turnover = 0.0
    candidate_turnover = 0.0
    for baseline in baselines:
        augmented = augment_signal(
            baseline.predictions,
            oriented,
            factor_weight=settings.g1_admission.factor_blend_weight,
        )
        candidate_ic = daily_rank_ic(augmented, baseline.labels)
        scenarios = {
            name: _scenario_backtest(settings, augmented, baseline.window, name)
            for name in ("normal", "cost_2x", "extra_10bp_each_side")
        }
        normal = scenarios["normal"]
        baseline_daily_ic.append(baseline.daily_ic)
        candidate_daily_ic.append(candidate_ic)
        baseline_returns.append(baseline.backtest.daily_excess)
        candidate_returns.append(normal.daily_excess)
        cost_2x_returns.append(scenarios["cost_2x"].daily_excess)
        slippage_returns.append(scenarios["extra_10bp_each_side"].daily_excess)
        baseline_turnover += baseline.backtest.turnover
        candidate_turnover += normal.turnover
        ic_rows.append(
            _ic_rows(discovery.spec.name, "augmented_signal", baseline.window.name, candidate_ic)
        )
        for scenario, result in scenarios.items():
            rows = _daily_rows(discovery.spec.name, baseline.window.name, scenario, result.daily_excess)
            rows["cumulative_excess"] = result.cumulative_excess
            rows["turnover"] = result.turnover
            rows["max_drawdown"] = result.max_drawdown
            return_rows.append(rows)
    baseline_ic = pd.concat(baseline_daily_ic).sort_index()
    candidate_ic = pd.concat(candidate_daily_ic).sort_index()
    baseline_return = pd.concat(baseline_returns).sort_index()
    candidate_return = pd.concat(candidate_returns).sort_index()
    cost_2x_return = pd.concat(cost_2x_returns).sort_index()
    slippage_return = pd.concat(slippage_returns).sort_index()
    stress = {
        period.name: quantize(
            _stress_drawdown(
                oriented,
                labels,
                start=pd.Timestamp(period.start),
                end=pd.Timestamp(period.end),
                topk=settings.backtest.topk,
                rebalance_days=settings.backtest.rebalance_days,
                roundtrip_cost=settings.backtest.open_cost + settings.backtest.close_cost,
            )
        )
        for period in settings.evaluation.stress_periods
    }
    from shaiwei.research.g1_pipeline import _max_library_correlation

    library_root = factor_library_root
    return CandidateResult(
        discovery=discovery,
        experiment_id=experiment_id,
        factor=factor,
        factor_daily_ic=factor_daily_ic,
        oos_windows=_window_values(factor_daily_ic, settings),
        stress=stress,
        baseline_turnover=quantize(baseline_turnover),
        candidate_turnover=quantize(candidate_turnover),
        baseline_net_icir=quantize(icir(baseline_ic)),
        candidate_net_icir=quantize(icir(candidate_ic)),
        baseline_net_excess=quantize(_compound(baseline_return)),
        candidate_net_excess=quantize(_compound(candidate_return)),
        cost_2x_net_excess=quantize(_compound(cost_2x_return)),
        slippage_2x_net_excess=quantize(_compound(slippage_return)),
        selection_sharpe=periodic_sharpe(
            candidate_return.tolist(), minimum=settings.g1_admission.min_observations
        ),
        candidate_daily_returns=candidate_return,
        max_library_abs_spearman=_max_library_correlation(factor, library_root),
        return_rows=pd.concat(return_rows, ignore_index=True),
        ic_rows=pd.concat(ic_rows, ignore_index=True),
    )
