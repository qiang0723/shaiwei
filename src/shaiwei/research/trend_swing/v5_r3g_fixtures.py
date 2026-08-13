"""Synthetic and adversarial fixtures for TS-v5-R3G executable semantics."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Callable

from shaiwei.research.provider_contract import D1ControlError
from shaiwei.research.trend_swing.v5_r3g_contract import RegisteredCandidate
from shaiwei.research.trend_swing.v5_r3g_state import (
    DailyInput,
    Episode,
    EpisodeStatus,
    NextOpenInput,
    advance_without_security_bar,
    execute_next_open,
    transition,
)


def _daily(**overrides: Any) -> DailyInput:
    values: dict[str, Any] = {
        "sequence": 1,
        "lagged_feature_sequence": 0,
        "low": Decimal("99"),
        "close": Decimal("101"),
        "prior_valid_high": Decimal("100"),
        "amount": Decimal("120"),
        "prior_20d_amount_median": Decimal("100"),
        "reference": Decimal("100"),
        "atr": Decimal("10"),
        "threshold": Decimal("0.10"),
        "relative_strength": Decimal("1.05"),
        "structure_low": Decimal("80"),
        "base_structure_gate": True,
        "market_sector_gate": True,
        "liquidity_gate": True,
        "security_eligible": True,
        "breakout_prerequisite": True,
        "contraction_prerequisite": True,
        "first_plan_week_bar": True,
    }
    values.update(overrides)
    return DailyInput.from_mapping(values)


def _open(signal_sequence: int, *, relative_strength: bool = False, **overrides: Any) -> NextOpenInput:
    values: dict[str, Any] = {
        "sequence": signal_sequence + 1,
        "raw_open": Decimal("99"),
        "adjusted_equivalent_open": Decimal("99"),
        "same_adjustment_factor": True,
        "reference_observation": Decimal("1.10") if relative_strength else Decimal("99"),
        "market_sector_gate": True,
        "liquidity_gate": True,
        "security_eligible": True,
    }
    values.update(overrides)
    return NextOpenInput.from_mapping(values)


def successful_episode(item: RegisteredCandidate) -> Episode:
    point = item.grid[0]
    if item.candidate.primary_mechanism.value == "RELATIVE_STRENGTH_PULLBACK":
        episode = transition(
            item.candidate,
            point,
            Episode(),
            _daily(reference=Decimal("1.20"), relative_strength=Decimal("1.05"), close=Decimal("99")),
        )
        episode = transition(
            item.candidate,
            point,
            episode,
            _daily(
                sequence=2,
                lagged_feature_sequence=1,
                reference=Decimal("1.25"),
                relative_strength=Decimal("1.10"),
            ),
        )
        return execute_next_open(item.candidate, episode, _open(2, relative_strength=True))
    episode = transition(item.candidate, point, Episode(), _daily())
    return execute_next_open(item.candidate, episode, _open(episode.signal_sequence))


def normal_path_evidence(candidates: tuple[RegisteredCandidate, ...]) -> list[dict[str, Any]]:
    evidence = []
    for item in candidates:
        episode = successful_episode(item)
        evidence.append({
            "candidate_id": f"ts-v5-r3g-c{item.ordinal:02d}",
            "mechanism": item.candidate.primary_mechanism.value,
            "terminal_status": episode.status.value,
            "terminal_reason": episode.terminal_reason,
        })
    return evidence


def _fails(action: Callable[[], object]) -> bool:
    try:
        action()
    except D1ControlError:
        return True
    return False


def _armed(item: RegisteredCandidate) -> Episode:
    return transition(
        item.candidate,
        item.grid[0],
        Episode(),
        _daily(close=Decimal("99")),
    )


def _streak_fixture(item: RegisteredCandidate) -> bool:
    point = next(
        row for row in item.grid
        if row["RECOVERY_CONFIRMATION_DAYS"] == "2" and row["MAXIMUM_WAIT_DAYS"] == "10"
    )
    episode = transition(item.candidate, point, Episode(), _daily())
    episode = transition(
        item.candidate, point, episode,
        _daily(sequence=2, lagged_feature_sequence=1, close=Decimal("99")),
    )
    episode = transition(
        item.candidate, point, episode,
        _daily(sequence=3, lagged_feature_sequence=2),
    )
    episode = transition(
        item.candidate, point, episode,
        _daily(sequence=4, lagged_feature_sequence=3),
    )
    return episode.status == EpisodeStatus.CONFIRMED and episode.confirmation_streak == 2


def adversarial_evidence(candidates: tuple[RegisteredCandidate, ...]) -> dict[str, bool]:
    first, _, third, _, _, relative = candidates
    point = first.grid[0]
    armed = _armed(first)
    precedence = transition(
        first.candidate,
        point,
        armed,
        _daily(
            sequence=2,
            lagged_feature_sequence=1,
            market_sector_gate=False,
        ),
    )
    timeout = armed
    for sequence, close in ((2, "99"), (3, "99"), (4, "101")):
        timeout = transition(
            first.candidate,
            point,
            timeout,
            _daily(
                sequence=sequence,
                lagged_feature_sequence=sequence - 1,
                close=Decimal(close),
            ),
        )
    confirmed = transition(first.candidate, point, Episode(), _daily())
    third_armed = _armed(third)
    liquidity = transition(
        third.candidate,
        third.grid[0],
        third_armed,
        _daily(sequence=2, lagged_feature_sequence=1, liquidity_gate=False),
    )
    relative_confirmed = transition(
        relative.candidate,
        relative.grid[0],
        Episode(),
        _daily(reference=Decimal("1.20"), relative_strength=Decimal("1.05"), close=Decimal("99")),
    )
    relative_confirmed = transition(
        relative.candidate,
        relative.grid[0],
        relative_confirmed,
        _daily(
            sequence=2,
            lagged_feature_sequence=1,
            reference=Decimal("1.25"),
            relative_strength=Decimal("1.10"),
        ),
    )
    future = {field: getattr(_daily(), field) for field in _daily().__dataclass_fields__}
    future["return_after_entry"] = Decimal("0.5")
    missing = dict(future)
    missing.pop("return_after_entry")
    missing.pop("atr")
    extra_point = {**point, "FUTURE_PROFIT_THRESHOLD": "1"}
    no_bar = advance_without_security_bar(
        first.candidate,
        point,
        armed,
        sequence=2,
        market_sector_gate=True,
    )
    return {
        "future_result_field_rejected": _fails(lambda: DailyInput.from_mapping(future)),
        "missing_feature_rejected": _fails(lambda: DailyInput.from_mapping(missing)),
        "current_bar_reference_rejected": _fails(lambda: transition(
            first.candidate, point, Episode(), _daily(lagged_feature_sequence=1)
        )),
        "extra_parameter_rejected": _fails(lambda: transition(
            first.candidate, extra_point, Episode(), _daily()
        )),
        "cancellation_precedes_confirmation": precedence.status == EpisodeStatus.CANCELLED
        and precedence.terminal_reason == "MARKET_OR_SECTOR_GATE_LOST",
        "maximum_wait_precedes_late_confirmation": timeout.status == EpisodeStatus.CANCELLED
        and timeout.terminal_reason == "MAX_WAIT_EXPIRED",
        "liquidity_cancellation_is_candidate_specific": liquidity.status == EpisodeStatus.CANCELLED
        and liquidity.terminal_reason == "LIQUIDITY_GATE_LOST",
        "terminal_episode_rejects_duplicate": _fails(lambda: transition(
            first.candidate, point, confirmed, _daily(sequence=2, lagged_feature_sequence=1)
        )),
        "confirmation_streak_resets": _streak_fixture(first),
        "next_open_above_reference_cancels": execute_next_open(
            first.candidate,
            confirmed,
            _open(confirmed.signal_sequence, adjusted_equivalent_open=Decimal("101"),
                  reference_observation=Decimal("101")),
        ).terminal_reason == "NEXT_OPEN_ABOVE_REFERENCE",
        "next_open_equal_reference_allowed": execute_next_open(
            first.candidate,
            confirmed,
            _open(confirmed.signal_sequence, adjusted_equivalent_open=Decimal("100"),
                  reference_observation=Decimal("100")),
        ).status == EpisodeStatus.EXECUTED,
        "price_reference_dimension_mismatch_rejected": _fails(lambda: execute_next_open(
            first.candidate, confirmed,
            _open(confirmed.signal_sequence, adjusted_equivalent_open=Decimal("99"),
                  reference_observation=Decimal("1.1")),
        )),
        "relative_strength_uses_relative_open_observation": execute_next_open(
            relative.candidate,
            relative_confirmed,
            _open(2, relative_strength=True, adjusted_equivalent_open=Decimal("110")),
        ).status == EpisodeStatus.EXECUTED,
        "relative_strength_unavailable_fails_closed": execute_next_open(
            relative.candidate,
            relative_confirmed,
            _open(2, relative_strength=True, reference_observation=Decimal("NaN")),
        ).terminal_reason == "CANCELLED_EXECUTION_REFERENCE_UNAVAILABLE",
        "suspended_market_day_advances_wait_age": no_bar.status == EpisodeStatus.ARMED
        and no_bar.wait_age == 1
        and no_bar.confirmation_streak == 0,
    }
