"""Pure, result-blind TS-v5-R3G entry state machine."""

from __future__ import annotations

from dataclasses import dataclass, fields, replace
from decimal import Decimal
from enum import StrEnum
from typing import Any, Mapping

from shaiwei.research.provider_contract import D1ControlError
from shaiwei.research.trend_swing.v5_models import CancellationRule, MechanismCandidate


class EpisodeStatus(StrEnum):
    IDLE = "IDLE"
    ARMED = "ARMED"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"
    EXECUTED = "EXECUTED"


@dataclass(frozen=True)
class DailyInput:
    sequence: int
    lagged_feature_sequence: int
    low: Decimal
    close: Decimal
    prior_valid_high: Decimal
    amount: Decimal
    prior_20d_amount_median: Decimal
    reference: Decimal
    atr: Decimal
    threshold: Decimal
    relative_strength: Decimal
    structure_low: Decimal
    base_structure_gate: bool
    market_sector_gate: bool
    liquidity_gate: bool
    security_eligible: bool
    breakout_prerequisite: bool
    contraction_prerequisite: bool
    first_plan_week_bar: bool

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "DailyInput":
        return _strict_dataclass(cls, value)


@dataclass(frozen=True)
class NextOpenInput:
    sequence: int
    raw_open: Decimal
    adjusted_equivalent_open: Decimal
    same_adjustment_factor: bool
    reference_observation: Decimal
    market_sector_gate: bool
    liquidity_gate: bool
    security_eligible: bool

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "NextOpenInput":
        return _strict_dataclass(cls, value)


@dataclass(frozen=True)
class Episode:
    status: EpisodeStatus = EpisodeStatus.IDLE
    mechanism: str = ""
    armed_sequence: int = 0
    signal_sequence: int = 0
    wait_age: int = 0
    confirmation_streak: int = 0
    reference: Decimal = Decimal("0")
    threshold: Decimal = Decimal("0")
    structure_low: Decimal = Decimal("0")
    terminal_reason: str = ""
def _strict_dataclass(cls: type[Any], value: Mapping[str, Any]) -> Any:
    expected = {field.name for field in fields(cls)}
    if set(value) != expected:
        raise D1ControlError("TS-v5-R3G input schema contains missing or future/result fields")
    try:
        return cls(**value)
    except (TypeError, ValueError) as exc:
        raise D1ControlError("TS-v5-R3G input field type is invalid") from exc


def _parameter_values(candidate: MechanismCandidate, values: Mapping[str, str]) -> dict[str, Decimal]:
    required = {slot.parameter_id.value for slot in candidate.parameter_slots}
    if set(values) != required:
        raise D1ControlError("TS-v5-R3G parameter point differs from candidate slots")
    try:
        return {key: Decimal(value) for key, value in values.items()}
    except (ValueError, TypeError) as exc:
        raise D1ControlError("TS-v5-R3G parameter point is invalid") from exc


def _validate_daily(row: DailyInput) -> None:
    decimals = (row.low, row.close, row.prior_valid_high, row.amount,
                row.prior_20d_amount_median, row.reference, row.atr, row.threshold,
                row.relative_strength, row.structure_low)
    if (
        row.sequence < 1
        or row.lagged_feature_sequence >= row.sequence
        or any(not value.is_finite() for value in decimals)
        or any(value <= 0 for value in (row.low, row.close, row.prior_valid_high,
                                        row.reference, row.relative_strength, row.structure_low))
        or any(value < 0 for value in (row.atr, row.amount, row.prior_20d_amount_median, row.threshold))
    ):
        raise D1ControlError("TS-v5-R3G daily input violates PIT or numeric invariants")


def _base_eligible(row: DailyInput) -> bool:
    return all((
        row.base_structure_gate,
        row.market_sector_gate,
        row.liquidity_gate,
        row.security_eligible,
    ))


def _arms(mechanism: str, row: DailyInput, point: Mapping[str, Decimal]) -> bool:
    if mechanism == "VOLATILITY_ADAPTIVE_PULLBACK":
        lower = row.reference - point["PULLBACK_ATR_MULTIPLE"] * row.atr
        return lower <= row.low <= row.reference
    if mechanism == "WEEKLY_STRUCTURE_QUANTILE":
        return row.low <= row.reference
    if mechanism == "BREAKOUT_RETEST":
        tolerance = point["RETEST_TOLERANCE_ATR"] * row.atr
        return (
            row.breakout_prerequisite
            and row.low <= row.reference + tolerance
            and row.close >= row.reference - tolerance
        )
    if mechanism == "MOVING_AVERAGE_RESUMPTION":
        tolerance = point["MOVING_AVERAGE_TOLERANCE_ATR"] * row.atr
        return row.low <= row.reference + tolerance and row.close >= row.reference - tolerance
    if mechanism == "CONTRACTION_EXPANSION":
        return row.contraction_prerequisite and row.first_plan_week_bar
    if mechanism == "RELATIVE_STRENGTH_PULLBACK":
        drawdown = (row.reference - row.relative_strength) / row.reference
        return drawdown >= row.threshold
    raise D1ControlError("TS-v5-R3G mechanism is not executable")


def _confirms(
    mechanism: str,
    row: DailyInput,
    point: Mapping[str, Decimal],
    episode: Episode,
) -> bool:
    if mechanism in {
        "VOLATILITY_ADAPTIVE_PULLBACK",
        "WEEKLY_STRUCTURE_QUANTILE",
        "BREAKOUT_RETEST",
    }:
        return row.close >= episode.reference
    if mechanism == "MOVING_AVERAGE_RESUMPTION":
        return (
            row.close > episode.reference
            and row.close > row.prior_valid_high
            and row.amount > row.prior_20d_amount_median
        )
    if mechanism == "CONTRACTION_EXPANSION":
        return (
            row.close > episode.reference
            and row.amount
            >= point["VOLUME_EXPANSION_RATIO"] * row.prior_20d_amount_median
        )
    if mechanism == "RELATIVE_STRENGTH_PULLBACK":
        recovery_line = episode.reference * (Decimal("1") - episode.threshold)
        return row.relative_strength >= recovery_line
    raise D1ControlError("TS-v5-R3G confirmation mechanism is not executable")


def _cancellation_reason(
    candidate: MechanismCandidate,
    row: DailyInput,
    episode: Episode,
    point: Mapping[str, Decimal],
) -> str:
    rules = set(candidate.entry_design.cancellation_rules)
    if row.close <= episode.structure_low:
        return "STRUCTURE_LOW_BROKEN"
    if not row.market_sector_gate:
        return "MARKET_OR_SECTOR_GATE_LOST"
    if CancellationRule.LIQUIDITY_GATE_LOST in rules and not row.liquidity_gate:
        return "LIQUIDITY_GATE_LOST"
    if (
        CancellationRule.MAX_WAIT_EXPIRED in rules
        and episode.wait_age > int(point["MAXIMUM_WAIT_DAYS"])
    ):
        return "MAX_WAIT_EXPIRED"
    return ""


def transition(
    candidate: MechanismCandidate,
    parameter_point: Mapping[str, str],
    episode: Episode,
    row: DailyInput,
) -> Episode:
    _validate_daily(row)
    if episode.status in {EpisodeStatus.CONFIRMED, EpisodeStatus.CANCELLED, EpisodeStatus.EXECUTED}:
        raise D1ControlError("TS-v5-R3G terminal episode cannot receive another daily bar")
    point = _parameter_values(candidate, parameter_point)
    mechanism = candidate.primary_mechanism.value
    current = episode
    if current.status == EpisodeStatus.IDLE:
        if not _base_eligible(row) or not _arms(mechanism, row, point):
            return current
        current = Episode(
            status=EpisodeStatus.ARMED,
            mechanism=mechanism,
            armed_sequence=row.sequence,
            wait_age=0,
            reference=row.reference,
            threshold=row.threshold,
            structure_low=row.structure_low,
        )
    else:
        if row.sequence != current.armed_sequence + current.wait_age + 1:
            raise D1ControlError("TS-v5-R3G daily sequence is duplicated or out of order")
        current = replace(current, wait_age=current.wait_age + 1)
    cancellation = _cancellation_reason(candidate, row, current, point)
    if cancellation:
        return replace(current, status=EpisodeStatus.CANCELLED, terminal_reason=cancellation)
    confirmation = _confirms(mechanism, row, point, current) if _base_eligible(row) else False
    streak = current.confirmation_streak + 1 if confirmation else 0
    if streak >= int(point["RECOVERY_CONFIRMATION_DAYS"]):
        return replace(
            current,
            status=EpisodeStatus.CONFIRMED,
            signal_sequence=row.sequence,
            confirmation_streak=streak,
        )
    return replace(current, confirmation_streak=streak)


def advance_without_security_bar(
    candidate: MechanismCandidate,
    parameter_point: Mapping[str, str],
    episode: Episode,
    *,
    sequence: int,
    market_sector_gate: bool,
) -> Episode:
    """Advance one official market day when the security has no legal bar."""
    if episode.status != EpisodeStatus.ARMED or sequence != episode.armed_sequence + episode.wait_age + 1:
        raise D1ControlError("TS-v5-R3G no-bar day is out of order or has no active episode")
    point = _parameter_values(candidate, parameter_point)
    current = replace(episode, wait_age=episode.wait_age + 1, confirmation_streak=0)
    if not market_sector_gate:
        return replace(current, status=EpisodeStatus.CANCELLED, terminal_reason="MARKET_OR_SECTOR_GATE_LOST")
    rules = set(candidate.entry_design.cancellation_rules)
    if CancellationRule.LIQUIDITY_GATE_LOST in rules:
        return replace(current, status=EpisodeStatus.CANCELLED, terminal_reason="LIQUIDITY_GATE_LOST")
    if (
        CancellationRule.MAX_WAIT_EXPIRED in rules
        and current.wait_age > int(point["MAXIMUM_WAIT_DAYS"])
    ):
        return replace(current, status=EpisodeStatus.CANCELLED, terminal_reason="MAX_WAIT_EXPIRED")
    return current


def execute_next_open(candidate: MechanismCandidate, episode: Episode, row: NextOpenInput) -> Episode:
    if episode.status != EpisodeStatus.CONFIRMED or row.sequence != episode.signal_sequence + 1:
        raise D1ControlError("TS-v5-R3G execution is not the immediate next official security bar")
    numeric = (row.raw_open, row.adjusted_equivalent_open, row.reference_observation)
    relative_strength = candidate.primary_mechanism.value == "RELATIVE_STRENGTH_PULLBACK"
    if relative_strength and (
        not row.reference_observation.is_finite() or row.reference_observation <= 0
    ):
        return replace(
            episode,
            status=EpisodeStatus.CANCELLED,
            terminal_reason="CANCELLED_EXECUTION_REFERENCE_UNAVAILABLE",
        )
    if any(not value.is_finite() or value <= 0 for value in numeric):
        return replace(episode, status=EpisodeStatus.CANCELLED, terminal_reason="OPEN_INVALID")
    if not relative_strength and row.reference_observation != row.adjusted_equivalent_open:
        raise D1ControlError("TS-v5-R3G price reference observation differs from adjusted open")
    if (
        not row.same_adjustment_factor
        or row.adjusted_equivalent_open <= episode.structure_low
        or not all((row.market_sector_gate, row.liquidity_gate, row.security_eligible))
    ):
        return replace(episode, status=EpisodeStatus.CANCELLED, terminal_reason="EXECUTION_GATE_LOST")
    rules = set(candidate.entry_design.cancellation_rules)
    if (
        CancellationRule.NEXT_OPEN_ABOVE_REFERENCE in rules
        and row.reference_observation > episode.reference
    ):
        return replace(
            episode,
            status=EpisodeStatus.CANCELLED,
            terminal_reason="NEXT_OPEN_ABOVE_REFERENCE",
        )
    return replace(episode, status=EpisodeStatus.EXECUTED, terminal_reason="")
