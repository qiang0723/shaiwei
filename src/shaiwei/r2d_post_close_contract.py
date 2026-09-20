"""Pure post-close contract checks; deliberately not a production start adapter."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from pydantic import (
    AwareDatetime, BaseModel, ConfigDict, Field, StrictBool, field_validator,
    model_validator,
)

Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
GitHead = Annotated[str, Field(pattern=r"^[0-9a-f]{40}$")]
TradeDate = Annotated[str, Field(pattern=r"^[0-9]{8}$")]
Count = Annotated[int, Field(strict=True, ge=0)]
SHANGHAI = ZoneInfo("Asia/Shanghai")


class ContractViolation(ValueError):
    """A safe, stable reason code; no embedded evidence or command output."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise ContractViolation(code)


class FrozenContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class ReleaseBinding(FrozenContract):
    candidate_image_id: Annotated[str, Field(pattern=r"^sha256:[0-9a-f]{64}$")]
    candidate_code_sha256: Sha256
    legacy_code_sha256: Sha256
    legacy_container_id: Sha256
    state_sha256: Sha256
    audit_sha256: Sha256
    calendar_sha256: Sha256
    controller_sha256: Sha256
    git_head: GitHead
    origin_main: GitHead

    @model_validator(mode="after")
    def validate_binding(self):
        if self.git_head != self.origin_main:
            raise ValueError("UNPUSHED_CONTROLLER")
        if self.candidate_code_sha256 == self.legacy_code_sha256:
            raise ValueError("NOT_CROSS_RELEASE")
        return self


class ForwardAnchor(FrozenContract):
    account_id: Literal["model_baseline", "model_top20"]
    execution_trade_date: TradeDate
    code_snapshot_sha256: Sha256
    artifact_sha256: Sha256
    finished_at: AwareDatetime
    status: Literal["PASS"]
    freshness_status: Literal["PASS"]
    mode: Literal["FORWARD"]
    operator: Literal["docker-scheduler"]
    hash_and_identity_verified: StrictBool

    @field_validator("execution_trade_date")
    @classmethod
    def valid_date(cls, value):
        datetime.strptime(value, "%Y%m%d")
        return value


class AttemptCounts(FrozenContract):
    daily: Count
    shadow: Count
    paper: Count


class PostCloseProtocol(FrozenContract):
    schema_version: Literal["r2d-post-close-contract-v1"]
    mode: Literal["POST_CLOSE_PARKED"]
    closed_trade_date: TradeDate
    first_candidate_trade_date: TradeDate
    not_before: AwareDatetime
    expires_at: AwareDatetime
    next_dispatch_not_before: AwareDatetime
    binding: ReleaseBinding
    baseline_artifact_sha256: Sha256
    top20_artifact_sha256: Sha256
    candidate_floor_fixture_sha256: Sha256
    health_max_age_seconds: Literal[3600] = 3600
    rollback_policy: Literal["FORBID_AFTER_DISPATCH"] = "FORBID_AFTER_DISPATCH"

    @field_validator("closed_trade_date", "first_candidate_trade_date")
    @classmethod
    def valid_date(cls, value):
        datetime.strptime(value, "%Y%m%d")
        return value

    @model_validator(mode="after")
    def validate_window(self):
        if self.first_candidate_trade_date <= self.closed_trade_date:
            raise ValueError("FIRST_DATE_NOT_NEW")
        duration = self.expires_at - self.not_before
        if not timedelta(0) < duration <= timedelta(hours=24):
            raise ValueError("WINDOW_MUST_BE_POSITIVE_AND_AT_MOST_24H")
        if self.expires_at > self.next_dispatch_not_before:
            raise ValueError("WINDOW_OVERLAPS_FIRST_DISPATCH")
        dispatch_date = self.next_dispatch_not_before.astimezone(SHANGHAI).strftime("%Y%m%d")
        if dispatch_date != self.first_candidate_trade_date:
            raise ValueError("DISPATCH_DATE_DIFFERS")
        if self.not_before.astimezone(SHANGHAI).strftime("%Y%m%d") < self.closed_trade_date:
            raise ValueError("WINDOW_BEFORE_CLOSED_DATE")
        return self


class PostCloseEvidence(FrozenContract):
    binding: ReleaseBinding
    daily_trade_date: TradeDate
    shadow_trade_date: TradeDate
    daily_status: Literal["PASS"]
    shadow_status: Literal["PASS"]
    shadow_code_sha256: Sha256
    calendar_next_trade_date: TradeDate
    observed_at: AwareDatetime
    cycle_finished_at: AwareDatetime
    health_updated_at: AwareDatetime
    health_status: Literal["noop"]
    health_detail: TradeDate
    completed_attempts: AttemptCounts
    first_day_attempts: AttemptCounts
    pending_trade_dates: tuple[TradeDate, ...]
    latest_forwards: tuple[ForwardAnchor, ...]
    independent_replay_pass: StrictBool
    notifications_pass: StrictBool
    legacy_quiescence_method: Literal["ALL_WRITERS_FENCED_AND_DRAINED"]
    legacy_quiescence_report_sha256: Sha256
    fence_held: StrictBool
    legacy_writers_inflight: Count
    candidate_mode: Literal["PARKED_UNTIL_FIRST_ELIGIBLE_DATE"]
    candidate_floor_fixture_sha256: Sha256


class ContractDecision(FrozenContract):
    status: Literal["CONTRACT_VALID_NOT_FOR_EXECUTION"] = "CONTRACT_VALID_NOT_FOR_EXECUTION"
    production_authorized: Literal[False] = False
    closed_trade_date: TradeDate
    first_candidate_trade_date: TradeDate
    checked_at: AwareDatetime
    expires_at: AwareDatetime


def _check_observation(protocol, evidence, now):
    _require(now.tzinfo is not None and now.utcoffset() is not None, "NAIVE_CLOCK")
    _require(protocol.not_before <= now < protocol.expires_at, "OUTSIDE_WINDOW")
    for timestamp in (evidence.observed_at, evidence.health_updated_at):
        age = (now - timestamp).total_seconds()
        _require(0 <= age <= protocol.health_max_age_seconds, "STALE_OR_FUTURE_EVIDENCE")
    _require(
        evidence.cycle_finished_at <= evidence.health_updated_at <= evidence.observed_at,
        "INCONSISTENT_EVIDENCE_ORDER",
    )
    _require(
        evidence.cycle_finished_at.astimezone(SHANGHAI).strftime("%Y%m%d")
        >= protocol.closed_trade_date,
        "CYCLE_BEFORE_CLOSED_DATE",
    )


def _check_forwards(protocol, evidence):
    rows = evidence.latest_forwards
    _require(len(rows) == 2, "FORWARD_ACCOUNT_COUNT")
    _require(
        {row.account_id for row in rows} == {"model_baseline", "model_top20"},
        "FORWARD_ACCOUNT_SET",
    )
    hashes = {
        "model_baseline": protocol.baseline_artifact_sha256,
        "model_top20": protocol.top20_artifact_sha256,
    }
    for row in rows:
        _require(row.execution_trade_date == protocol.closed_trade_date, "FORWARD_DATE_DIFFERS")
        _require(
            row.code_snapshot_sha256 == protocol.binding.legacy_code_sha256,
            "FORWARD_CODE_DIFFERS",
        )
        _require(row.artifact_sha256 == hashes[row.account_id], "FORWARD_HASH_DIFFERS")
        _require(row.hash_and_identity_verified, "FORWARD_UNVERIFIED")
        _require(row.finished_at <= evidence.cycle_finished_at, "FORWARD_FINISH_AFTER_CYCLE")
        _require(
            row.finished_at.astimezone(SHANGHAI).strftime("%Y%m%d")
            >= protocol.closed_trade_date,
            "FORWARD_FINISH_BEFORE_EXECUTION_DATE",
        )


def assess_post_close(
    protocol: PostCloseProtocol, evidence: PostCloseEvidence, *, now: datetime,
) -> ContractDecision:
    """Check already-verified metadata in memory; never grants execution authority."""
    _check_observation(protocol, evidence, now)
    _require(evidence.binding == protocol.binding, "RELEASE_BINDING_DRIFT")
    _require(
        evidence.daily_trade_date == evidence.shadow_trade_date == protocol.closed_trade_date,
        "CLOSED_DATE_DIFFERS",
    )
    _require(evidence.shadow_code_sha256 == protocol.binding.legacy_code_sha256, "SHADOW_CODE_DIFFERS")
    _require(evidence.health_detail == protocol.closed_trade_date, "HEALTH_DETAIL_DIFFERS")
    _require(
        evidence.calendar_next_trade_date == protocol.first_candidate_trade_date,
        "NOT_FIRST_CALENDAR_TRADE_DATE",
    )
    _require(
        evidence.completed_attempts == AttemptCounts(daily=1, shadow=1, paper=2),
        "CLOSED_ATTEMPTS_NOT_UNAMBIGUOUS",
    )
    _require(
        evidence.first_day_attempts == AttemptCounts(daily=0, shadow=0, paper=0),
        "FIRST_DAY_ALREADY_ATTEMPTED",
    )
    _require(not evidence.pending_trade_dates, "PENDING_WORK")
    _require(evidence.independent_replay_pass, "REPLAY_NOT_VERIFIED")
    _require(evidence.notifications_pass, "NOTIFICATIONS_NOT_VERIFIED")
    _require(evidence.fence_held and evidence.legacy_writers_inflight == 0, "NOT_QUIESCENT")
    _require(
        evidence.candidate_floor_fixture_sha256 == protocol.candidate_floor_fixture_sha256,
        "CANDIDATE_FLOOR_FIXTURE_DIFFERS",
    )
    _check_forwards(protocol, evidence)
    return ContractDecision(
        closed_trade_date=protocol.closed_trade_date,
        first_candidate_trade_date=protocol.first_candidate_trade_date,
        checked_at=now, expires_at=protocol.expires_at,
    )
