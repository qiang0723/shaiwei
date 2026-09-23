"""In-memory R3M rehearsal, never an execution permit or a live adapter."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import AwareDatetime, Field, StrictBool, StrictInt, model_validator

from shaiwei.r2d_post_close_contract import (
    SHANGHAI, AttemptCounts, ContractViolation, Count, FrozenContract,
    PostCloseEvidence, PostCloseProtocol, ReleaseBinding, Sha256, TradeDate,
    assess_post_close,
)

ImageId = Annotated[str, Field(pattern=r"^sha256:[0-9a-f]{64}$")]


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise ContractViolation(code)


def _fresh(observed_at: datetime, now: datetime) -> None:
    _require(now.tzinfo is not None and now.utcoffset() is not None, "NAIVE_CLOCK")
    _require(0 <= (now - observed_at).total_seconds() <= 3600, "STALE_OR_FUTURE_WITNESS")


class RehearsalPlan(FrozenContract):
    schema_version: Literal["r2d-park-drain-rehearsal-v1"]
    post_close: PostCloseProtocol
    legacy_image_id: ImageId
    prepared_image_id: ImageId
    prepared_code_sha256: Sha256
    writer_container_ids: tuple[Sha256, ...]
    writer_inventory_sha256: Sha256
    drain_fixture_sha256: Sha256
    closed_cycle_sha256: Sha256

    @model_validator(mode="after")
    def validate_plan(self):
        images = {
            self.legacy_image_id, self.prepared_image_id,
            self.post_close.binding.candidate_image_id,
        }
        if len(images) != 3:
            raise ValueError("THREE_DISTINCT_RELEASE_IDENTITIES_REQUIRED")
        if len({
            self.prepared_code_sha256, self.post_close.binding.legacy_code_sha256,
            self.post_close.binding.candidate_code_sha256,
        }) != 3:
            raise ValueError("THREE_DISTINCT_CODE_IDENTITIES_REQUIRED")
        writers = self.writer_container_ids
        if len(writers) != len(set(writers)):
            raise ValueError("DUPLICATE_WRITER")
        if self.post_close.binding.legacy_container_id not in writers:
            raise ValueError("LEGACY_WRITER_MISSING")
        return self


class ExitWitness(FrozenContract):
    container_id: Sha256
    exited_at: AwareDatetime
    exit_code: StrictInt
    restart_count_before: Count
    restart_count_after: Count
    running: StrictBool
    remaining_children: Count


class DrainWitness(FrozenContract):
    binding: ReleaseBinding
    writer_inventory_sha256: Sha256
    drain_fixture_sha256: Sha256
    closed_cycle_sha256: Sha256
    report_sha256: Sha256
    fence_held_since: AwareDatetime
    mutation_barrier_persisted_at: AwareDatetime
    first_mutation_at: AwareDatetime
    stop_requested_at: AwareDatetime
    observed_at: AwareDatetime
    all_entrypoints_fenced: StrictBool
    fence_still_held: StrictBool
    forced_kill_used: StrictBool
    restart_suppression_verified: StrictBool
    unknown_writer_count: Count
    exits: tuple[ExitWitness, ...]


class FirstDayObservation(FrozenContract):
    binding: ReleaseBinding
    observed_at: AwareDatetime
    handoff_completed_at: AwareDatetime
    candidate_floor_fixture_sha256: Sha256
    handoff_verified: StrictBool
    all_entrypoints_gated: StrictBool
    singleton_held: StrictBool
    calendar_next_trade_date: TradeDate
    eligible_trade_date: TradeDate
    pending_trade_dates: tuple[TradeDate, ...]
    attempts: AttemptCounts
    claim_state: Literal["UNCLAIMED", "CLAIMED", "UNKNOWN", "ACCEPTED"]
    full_first_day_acceptance_verified: StrictBool

    @model_validator(mode="after")
    def validate_dates(self):
        for value in (
            self.calendar_next_trade_date, self.eligible_trade_date,
            *self.pending_trade_dates,
        ):
            datetime.strptime(value, "%Y%m%d")
        return self


class RehearsalDecision(FrozenContract):
    status: Literal[
        "WOULD_HANDOFF_PARKED", "PARKED", "WOULD_CLAIM_FIRST_DAY",
        "FIRST_DAY_ACCEPTED_NO_REPLAY",
    ]
    production_authorized: Literal[False] = False
    checked_at: AwareDatetime
    first_candidate_trade_date: TradeDate
    expected_current_image_id: ImageId
    expected_previous_image_id: ImageId
    retained_prepared_image_id: ImageId


def _decision(plan: RehearsalPlan, status, now: datetime) -> RehearsalDecision:
    return RehearsalDecision(
        status=status, checked_at=now,
        first_candidate_trade_date=plan.post_close.first_candidate_trade_date,
        expected_current_image_id=plan.post_close.binding.candidate_image_id,
        expected_previous_image_id=plan.legacy_image_id,
        retained_prepared_image_id=plan.prepared_image_id,
    )


def _check_exits(plan: RehearsalPlan, witness: DrainWitness) -> None:
    ids = tuple(row.container_id for row in witness.exits)
    _require(
        len(ids) == len(set(ids)) and set(ids) == set(plan.writer_container_ids),
        "WRITER_SET_DIFFERS",
    )
    for row in witness.exits:
        _require(
            witness.stop_requested_at <= row.exited_at <= witness.observed_at,
            "EXIT_ORDER_INVALID",
        )
        _require(not row.running and row.exit_code == 0, "WRITER_NOT_CLEANLY_EXITED")
        _require(row.remaining_children == 0, "CHILD_WRITER_REMAINS")
        _require(
            row.restart_count_before == row.restart_count_after,
            "WRITER_RESTARTED",
        )


def rehearse_handoff(
    plan: RehearsalPlan, closed: PostCloseEvidence, witness: DrainWitness, *, now: datetime,
) -> RehearsalDecision:
    """Validate staged synthetic attestations; do not stop, start, or change pointers."""
    _fresh(witness.observed_at, now)
    _require(witness.binding == plan.post_close.binding, "DRAIN_BINDING_DRIFT")
    _require(
        witness.writer_inventory_sha256 == plan.writer_inventory_sha256
        and witness.drain_fixture_sha256 == plan.drain_fixture_sha256,
        "DRAIN_CAPABILITY_DRIFT",
    )
    _require(witness.closed_cycle_sha256 == plan.closed_cycle_sha256, "CLOSED_CYCLE_DRIFT")
    _require(
        witness.report_sha256 == closed.legacy_quiescence_report_sha256,
        "DRAIN_REPORT_DIFFERS",
    )
    _require(
        witness.all_entrypoints_fenced and witness.fence_still_held
        and witness.unknown_writer_count == 0,
        "WRITER_COVERAGE_UNPROVEN",
    )
    _require(
        not witness.forced_kill_used and witness.restart_suppression_verified,
        "UNSAFE_STOP_OR_RESTART_POLICY",
    )
    _require(
        plan.post_close.not_before <= witness.mutation_barrier_persisted_at
        <= witness.first_mutation_at <= witness.fence_held_since
        <= witness.stop_requested_at <= witness.observed_at <= now,
        "MUTATION_SEQUENCE_INVALID",
    )
    _require(
        closed.health_updated_at <= witness.first_mutation_at
        and witness.observed_at <= closed.observed_at <= now,
        "ARCHIVED_HEALTH_OR_FINAL_CHECK_ORDER_INVALID",
    )
    _check_exits(plan, witness)
    assess_post_close(plan.post_close, closed, now=now)
    return _decision(plan, "WOULD_HANDOFF_PARKED", now)


def _check_first_day_identity(plan, observed, now):
    _fresh(observed.observed_at, now)
    _require(
        plan.post_close.not_before <= observed.handoff_completed_at
        < plan.post_close.expires_at
        and observed.handoff_completed_at <= observed.observed_at,
        "HANDOFF_OUTSIDE_WINDOW_OR_FUTURE",
    )
    _require(observed.binding == plan.post_close.binding, "FIRST_DAY_BINDING_DRIFT")
    _require(
        observed.candidate_floor_fixture_sha256 == plan.post_close.candidate_floor_fixture_sha256,
        "PARKING_CAPABILITY_DRIFT",
    )
    _require(
        observed.handoff_verified and observed.all_entrypoints_gated and observed.singleton_held,
        "FIRST_DAY_ISOLATION_UNPROVEN",
    )
    _require(
        observed.calendar_next_trade_date == plan.post_close.first_candidate_trade_date,
        "FIRST_DAY_CALENDAR_DRIFT",
    )


def rehearse_first_day(
    plan: RehearsalPlan, observed: FirstDayObservation, *, now: datetime,
) -> RehearsalDecision:
    """Rehearse the pre-business gate; WOULD_CLAIM never grants dispatch authority."""
    _check_first_day_identity(plan, observed, now)
    protocol = plan.post_close
    first = protocol.first_candidate_trade_date
    today = now.astimezone(SHANGHAI).strftime("%Y%m%d")
    _require(observed.claim_state not in {"CLAIMED", "UNKNOWN"}, "CLAIM_REQUIRES_RECONCILIATION")
    if observed.claim_state == "ACCEPTED":
        _require(
            observed.full_first_day_acceptance_verified
            and observed.attempts == AttemptCounts(daily=1, shadow=1, paper=2)
            and now >= protocol.next_dispatch_not_before,
            "FIRST_DAY_ACCEPTANCE_UNPROVEN",
        )
        return _decision(plan, "FIRST_DAY_ACCEPTED_NO_REPLAY", now)
    _require(not observed.full_first_day_acceptance_verified, "ACCEPTANCE_STATE_CONFLICT")
    _require(
        observed.attempts == AttemptCounts(daily=0, shadow=0, paper=0),
        "FIRST_DAY_ALREADY_ATTEMPTED",
    )
    _require(today <= first and observed.eligible_trade_date <= first, "MISSED_FIRST_NATURAL_DAY")
    _require(
        observed.pending_trade_dates in ((), (first,)), "OLD_OR_MULTIPLE_PENDING_DATES",
    )
    if now < protocol.next_dispatch_not_before or observed.eligible_trade_date < first:
        return _decision(plan, "PARKED", now)
    _require(observed.pending_trade_dates == (first,), "FIRST_DAY_PLAN_NOT_EXACT")
    return _decision(plan, "WOULD_CLAIM_FIRST_DAY", now)
