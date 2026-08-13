"""Mechanism-specific daily inputs for TS-v5-R3G-1."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Mapping

from shaiwei.research.provider_contract import D1ControlError
from shaiwei.research.trend_swing.v5_models import MechanismCandidate
from shaiwei.research.trend_swing.v5_r3g_state import DailyInput, NextOpenInput


def _decimal(value: Any, label: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (TypeError, ValueError) as exc:
        raise D1ControlError(f"TS-v5-R3G-1 {label} is invalid") from exc
    if not result.is_finite():
        raise D1ControlError(f"TS-v5-R3G-1 {label} is not finite")
    return result


def _lookback(point: Mapping[str, str], name: str) -> int:
    try:
        return int(Decimal(point[name]))
    except (KeyError, ValueError) as exc:
        raise D1ControlError(f"TS-v5-R3G-1 {name} is invalid") from exc


def _atr(row: Mapping[str, Any], days: int) -> Decimal:
    if days not in {10, 20, 30}:
        raise D1ControlError("TS-v5-R3G-1 unsupported ATR lookback")
    return _decimal(row[f"atr{days}_lagged"], "ATR")


def _moving_average(row: Mapping[str, Any], days: int) -> Decimal:
    if days not in {10, 35, 60}:
        raise D1ControlError("TS-v5-R3G-1 unsupported moving-average lookback")
    return _decimal(row[f"sma{days}_lagged"], "moving average")


def _breakout(row: Mapping[str, Any], weeks: int) -> Decimal:
    if weeks not in {4, 15, 26}:
        raise D1ControlError("TS-v5-R3G-1 unsupported breakout lookback")
    return _decimal(row[f"breakout{weeks}"], "breakout reference")


def _relative_strength(row: Mapping[str, Any], days: int) -> Decimal:
    if days not in {20, 70, 120}:
        raise D1ControlError("TS-v5-R3G-1 unsupported relative-strength lookback")
    close = _decimal(row["adj_close"], "adjusted close")
    close_lag = _decimal(row[f"close_lag{days}"], "lagged adjusted close")
    sector = _decimal(row["sector_level"], "sector level")
    sector_lag = _decimal(row[f"sector_lag{days}"], "lagged sector level")
    return (close / close_lag) / (sector / sector_lag)


def _context(candidate: MechanismCandidate, point: Mapping[str, str], row: Mapping[str, Any]) -> tuple[Decimal, Decimal, Decimal, bool, bool]:
    mechanism = candidate.primary_mechanism.value
    if mechanism == "VOLATILITY_ADAPTIVE_PULLBACK":
        return _decimal(row["week_vwap"], "week VWAP"), _atr(row, _lookback(point, "ATR_LOOKBACK_DAYS")), Decimal("0"), False, False
    if mechanism == "WEEKLY_STRUCTURE_QUANTILE":
        q = _decimal(point["WEEKLY_RANGE_QUANTILE"], "weekly range quantile")
        low, high = _decimal(row["week_low"], "week low"), _decimal(row["week_high"], "week high")
        return low + q * (high - low), Decimal("0"), Decimal("0"), False, False
    if mechanism == "BREAKOUT_RETEST":
        reference = _breakout(row, _lookback(point, "BREAKOUT_LOOKBACK_WEEKS"))
        return reference, _atr(row, 20), Decimal("0"), _decimal(row["week_close"], "week close") > reference, False
    if mechanism == "MOVING_AVERAGE_RESUMPTION":
        return _moving_average(row, _lookback(point, "MOVING_AVERAGE_LOOKBACK_DAYS")), _atr(row, 20), Decimal("0"), False, False
    if mechanism == "CONTRACTION_EXPANSION":
        weeks = _lookback(point, "CONTRACTION_LOOKBACK_WEEKS")
        quantile = _decimal(point["RANGE_CONTRACTION_QUANTILE"], "range quantile")
        if weeks not in {3, 12} or quantile not in {Decimal("0.1"), Decimal("0.5")}:
            raise D1ControlError("TS-v5-R3G-1 unsupported contraction grid point")
        threshold = _decimal(row[f"range_q{int(quantile * 100)}_lag{weeks}"], "range threshold")
        return _decimal(row["week_high"], "week high"), Decimal("0"), Decimal("0"), False, _decimal(row["week_range"], "week range") <= threshold
    if mechanism == "RELATIVE_STRENGTH_PULLBACK":
        days = _lookback(point, "RELATIVE_STRENGTH_LOOKBACK_DAYS")
        reference = _decimal(row[f"rs_peak{days}_lagged"], "relative-strength peak")
        label = point["RELATIVE_STRENGTH_DRAWDOWN_QUANTILE"].replace(".", "_")
        threshold = _decimal(row[f"rs_drawdown_q{days}_{label}"], "relative-strength threshold")
        return reference, Decimal("0"), threshold, False, False
    raise D1ControlError("TS-v5-R3G-1 mechanism is unsupported")


def daily_input(candidate: MechanismCandidate, point: Mapping[str, str], row: Mapping[str, Any]) -> DailyInput:
    reference, atr, threshold, breakout, contraction = _context(candidate, point, row)
    rs_days = _lookback(point, "RELATIVE_STRENGTH_LOOKBACK_DAYS") if "RELATIVE_STRENGTH_LOOKBACK_DAYS" in point else None
    relative_strength = _relative_strength(row, rs_days) if rs_days else Decimal("1")
    return DailyInput(
        sequence=int(row["role_sequence"]), lagged_feature_sequence=max(0, int(row["role_sequence"]) - 1),
        low=_decimal(row["adj_low"], "adjusted low"), close=_decimal(row["adj_close"], "adjusted close"),
        prior_valid_high=_decimal(row["previous_valid_high"], "previous valid high"), amount=_decimal(row["amount_rmb"], "amount"),
        prior_20d_amount_median=_decimal(row["amount_median20_lagged"], "lagged amount median"), reference=reference,
        atr=atr, threshold=threshold, relative_strength=relative_strength,
        structure_low=_decimal(row["initial_structure_stop"], "structure low"),
        base_structure_gate=bool(row["f_plan"]), market_sector_gate=bool(row["f_daily"]),
        liquidity_gate=bool(row["liquidity_gate"]), security_eligible=bool(row["security_eligible"]),
        breakout_prerequisite=breakout, contraction_prerequisite=contraction,
        first_plan_week_bar=bool(row["first_plan_week_bar"]),
    )


def next_open_input(candidate: MechanismCandidate, point: Mapping[str, str], signal: Mapping[str, Any], row: Mapping[str, Any]) -> NextOpenInput:
    adjusted_open = _decimal(row["adj_open"], "adjusted open")
    if candidate.primary_mechanism.value == "RELATIVE_STRENGTH_PULLBACK":
        days = _lookback(point, "RELATIVE_STRENGTH_LOOKBACK_DAYS")
        stock_lag = _decimal(signal[f"close_lag{days}"], "lagged adjusted close")
        sector, sector_lag = _decimal(signal["sector_level"], "sector level"), _decimal(signal[f"sector_lag{days}"], "lagged sector level")
        reference_observation = (adjusted_open / stock_lag) / (sector / sector_lag)
    else:
        reference_observation = adjusted_open
    return NextOpenInput(
        sequence=int(row["role_sequence"]), raw_open=_decimal(row["raw_open"], "raw open"),
        adjusted_equivalent_open=adjusted_open, same_adjustment_factor=bool(row["same_adjustment_factor"]),
        reference_observation=reference_observation, market_sector_gate=bool(signal["f_daily"]),
        liquidity_gate=bool(row["liquidity_gate"]), security_eligible=bool(row["security_eligible"]),
    )
