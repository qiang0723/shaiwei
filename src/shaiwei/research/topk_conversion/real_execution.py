"""Portfolio-only Top30 compatibility replay and Top20 case construction."""

from __future__ import annotations

from typing import Any, Callable

import pandas as pd

from shaiwei.research.model_attribution.contract import ProtocolBundle as M6ProtocolBundle
from shaiwei.research.topk_conversion.contract import ConversionError
from shaiwei.research.topk_conversion.execution import backtest_signal, scheduled_topk
from shaiwei.research.topk_conversion.real_contract import RealProtocol
from shaiwei.research.topk_conversion.schema import ARMS, STRESS_PERIODS, TOPK_KEYS, WINDOWS


Backtester = Callable[..., pd.DataFrame]
Top20Start = Callable[[], None]


def _assert_frame_equal(actual: pd.DataFrame, expected: pd.DataFrame, name: str) -> None:
    if not actual.equals(expected):
        raise ConversionError(f"M6-3C Top30 canonical report differs: {name}")


def _rows(frame: pd.DataFrame) -> list[dict[str, float | str]]:
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


def _prediction_keys(sealed: dict[str, Any]) -> None:
    for window in WINDOWS:
        values = sealed["predictions"][window]
        if tuple(values) != ARMS:
            raise ConversionError("M6-3C sealed prediction arm order differs")
        reference = values[ARMS[0]].index
        if any(not reference.equals(values[arm].index) for arm in ARMS[1:]):
            raise ConversionError("M6-3C prediction member-day keys differ")
    stress = sealed["stress_predictions"]
    reference = stress[ARMS[0]].index
    if tuple(stress) != ARMS or any(not reference.equals(stress[arm].index) for arm in ARMS[1:]):
        raise ConversionError("M6-3C stress prediction member-day keys differ")


def _windows() -> dict[str, dict[str, Any]]:
    rows = M6ProtocolBundle.load().result["windows"]
    windows = {str(row["name"]): row for row in rows}
    if tuple(windows) != WINDOWS:
        raise ConversionError("M6-3C predecessor window set differs")
    return windows


def _top30_compatibility(
    sealed: dict[str, Any],
    protocol: RealProtocol,
    *,
    backtester: Backtester,
) -> tuple[dict[str, dict[str, pd.DataFrame]], dict[str, pd.DataFrame]]:
    reports: dict[str, dict[str, pd.DataFrame]] = {}
    windows = _windows()
    cadence = int(protocol.result["portfolio_constants"]["rebalance_trade_days"])
    for window in WINDOWS:
        reports[window] = {}
        for arm in ARMS:
            prediction = sealed["predictions"][window][arm]
            schedule = scheduled_topk(prediction, topk=30, rebalance_days=cadence)
            if schedule != sealed["top30"][window][arm]:
                raise ConversionError(f"M6-3C Top30 schedule differs: {window}/{arm}")
            report = backtester(
                prediction,
                start=str(windows[window]["test"][0]),
                end=str(windows[window]["test"][1]),
                protocol=protocol.result,
                topk=30,
            )
            _assert_frame_equal(report, sealed["reports"][window][arm], f"{window}/{arm}")
            reports[window][arm] = report
    stress: dict[str, pd.DataFrame] = {}
    for arm in ARMS:
        report = backtester(
            sealed["stress_predictions"][arm],
            start="2026-01-01",
            end="2026-06-30",
            protocol=protocol.result,
            topk=30,
        )
        _assert_frame_equal(report, sealed["stress_reports"][arm], f"stress/{arm}")
        stress[arm] = report
    return reports, stress


def build_real_case(
    sealed: dict[str, Any],
    protocol: RealProtocol,
    *,
    backtester: Backtester = backtest_signal,
    on_top20_start: Top20Start = lambda: None,
) -> dict[str, Any]:
    _prediction_keys(sealed)
    top30_reports, top30_volume_stress = _top30_compatibility(
        sealed, protocol, backtester=backtester
    )
    on_top20_start()
    windows = _windows()
    cadence = int(protocol.result["portfolio_constants"]["rebalance_trade_days"])
    frame_reports: dict[str, dict[str, dict[str, pd.DataFrame]]] = {"30": top30_reports, "20": {}}
    scheduled: dict[str, dict[str, dict[str, dict[str, list[str]]]]] = {
        topk: {window: {} for window in WINDOWS} for topk in TOPK_KEYS
    }
    for window in WINDOWS:
        frame_reports["20"][window] = {}
        for arm in ARMS:
            prediction = sealed["predictions"][window][arm]
            scheduled["30"][window][arm] = scheduled_topk(
                prediction, topk=30, rebalance_days=cadence
            )
            scheduled["20"][window][arm] = scheduled_topk(
                prediction, topk=20, rebalance_days=cadence
            )
            frame_reports["20"][window][arm] = backtester(
                prediction,
                start=str(windows[window]["test"][0]),
                end=str(windows[window]["test"][1]),
                protocol=protocol.result,
                topk=20,
            )
    volume_stress: dict[str, dict[str, pd.DataFrame]] = {"30": top30_volume_stress, "20": {}}
    for arm in ARMS:
        volume_stress["20"][arm] = backtester(
            sealed["stress_predictions"][arm],
            start="2026-01-01",
            end="2026-06-30",
            protocol=protocol.result,
            topk=20,
        )
    reports = {
        topk: {
            window: {arm: _rows(frame_reports[topk][window][arm]) for arm in ARMS}
            for window in WINDOWS
        }
        for topk in TOPK_KEYS
    }
    stress_reports: dict[str, dict[str, dict[str, list[dict[str, float | str]]]]] = {}
    for topk in TOPK_KEYS:
        stress_reports[topk] = {period: {} for period in STRESS_PERIODS}
        for arm in ARMS:
            w6 = frame_reports[topk]["W6"][arm].loc["2024-01-01":"2024-02-29"]
            if w6.empty:
                raise ConversionError("M6-3C microcap stress slice is empty")
            stress_reports[topk]["microcap_crash_2024"][arm] = _rows(w6)
            stress_reports[topk]["volume_price_drawdown_2026h1"][arm] = _rows(
                volume_stress[topk][arm]
            )
    return {
        "preflight_blocked_reasons": [],
        "top30_reference": reports["30"],
        "reports": reports,
        "stress_reports": stress_reports,
        "scheduled_names": scheduled,
    }


__all__ = ["build_real_case"]
