"""Versioned domain contracts for offline, resumable candidate-stage fixtures."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
import hashlib
import json
from typing import Annotated, Literal

from pydantic import AwareDatetime, Field

from shaiwei.r2d_parking_rehearsal import FirstDayObservation, RehearsalPlan
from shaiwei.r2d_post_close_contract import FrozenContract, SHANGHAI, Sha256, TradeDate

Phase = Literal[
    "READINESS", "DAILY", "SHADOW", "PAPER_BASELINE", "VERIFY_BASELINE",
    "ACCEPT_BASELINE", "PAPER_TOP20", "VERIFY_TOP20", "ACCEPT_TOP20", "FINAL_ACCEPTANCE",
]
PHASES = (
    "READINESS", "DAILY", "SHADOW", "PAPER_BASELINE", "VERIFY_BASELINE",
    "ACCEPT_BASELINE", "PAPER_TOP20", "VERIFY_TOP20", "ACCEPT_TOP20", "FINAL_ACCEPTANCE",
)
ZERO_HASH = "0" * 64


class StageError(ValueError):
    """Stable result-blind failure code, never raw adapter output."""


def require(condition: bool, code: str) -> None:
    if not condition:
        raise StageError(code)


def canonical(model: FrozenContract) -> str:
    return json.dumps(model.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))


def digest(model: FrozenContract) -> str:
    return hashlib.sha256(canonical(model).encode("utf-8")).hexdigest()


class CandidatePlan(FrozenContract):
    schema_version: Literal["r2d-candidate-offline-v1"]
    mode: Literal["OFFLINE_FIXTURE_ONLY"]
    rehearsal: RehearsalPlan
    max_readiness_checks: Annotated[int, Field(strict=True, ge=1)]


class PhaseReceipt(FrozenContract):
    plan_sha256: Sha256
    trade_date: TradeDate
    phase: Phase
    begin_sha256: Sha256
    outcome: Literal["READY", "WAITING_SOURCE", "PASS"]
    evidence_sha256: Sha256


class StageEvent(FrozenContract):
    schema_version: Literal["r2d-offline-stage-event-v1"] = "r2d-offline-stage-event-v1"
    sequence: Annotated[int, Field(strict=True, ge=1)]
    previous_sha256: Sha256
    plan_sha256: Sha256
    kind: Literal["CLAIM", "BEGIN", "END"]
    phase: Phase | None
    at: AwareDatetime
    receipt: PhaseReceipt | None = None


class CandidateEvidence(FrozenContract):
    observation: FirstDayObservation
    completed_receipts: tuple[PhaseReceipt, ...]


class TickResult(FrozenContract):
    status: Literal["PARKED", "WAITING_SOURCE", "OFFLINE_FIRST_DAY_COMPLETE"]
    production_authorized: Literal[False] = False
    checked_at: AwareDatetime
    journal_head: Sha256


@dataclass(frozen=True)
class StageState:
    sequence: int = 0
    head: str = ZERO_HASH
    last_at: datetime | None = None
    claimed: bool = False
    running: str | None = None
    readiness_checks: int = 0
    ready: bool = False
    completed: tuple[PhaseReceipt, ...] = ()

    @property
    def next_phase(self) -> str | None:
        if not self.ready:
            return "READINESS"
        index = len(self.completed) + 1
        return PHASES[index] if index < len(PHASES) else None


def _receipt(plan: CandidatePlan, state: StageState, event: StageEvent) -> PhaseReceipt:
    receipt = event.receipt
    require(receipt is not None, "MISSING_PHASE_RECEIPT")
    require(
        receipt.plan_sha256 == digest(plan)
        and receipt.trade_date == plan.rehearsal.post_close.first_candidate_trade_date
        and receipt.phase == event.phase and receipt.begin_sha256 == state.head,
        "RECEIPT_BINDING_DIFFERS",
    )
    expected = {"READY", "WAITING_SOURCE"} if event.phase == "READINESS" else {"PASS"}
    require(receipt.outcome in expected, "RECEIPT_OUTCOME_DIFFERS")
    return receipt


def advance(plan: CandidatePlan, state: StageState, event: StageEvent) -> StageState:
    """Validate and fold exactly one append; no I/O and no retry decisions."""
    require(event.plan_sha256 == digest(plan), "JOURNAL_PLAN_DIFFERS")
    protocol = plan.rehearsal.post_close
    require(
        event.at >= protocol.next_dispatch_not_before
        and event.at.astimezone(SHANGHAI).strftime("%Y%m%d") == protocol.first_candidate_trade_date,
        "EVENT_OUTSIDE_FIRST_DAY",
    )
    require(
        event.sequence == state.sequence + 1 and event.previous_sha256 == state.head,
        "JOURNAL_CHAIN_DIFFERS",
    )
    require(state.last_at is None or event.at >= state.last_at, "JOURNAL_TIME_REVERSED")
    result = replace(state, sequence=event.sequence, head=digest(event), last_at=event.at)
    if event.kind == "CLAIM":
        require(not state.claimed and event.phase is None and event.receipt is None, "INVALID_CLAIM")
        return replace(result, claimed=True)
    require(state.claimed, "CLAIM_REQUIRED")
    if event.kind == "BEGIN":
        require(state.running is None and state.next_phase is not None, "PHASE_NOT_AVAILABLE")
        require(event.phase == state.next_phase and event.receipt is None, "PHASE_ORDER_DIFFERS")
        checks = state.readiness_checks + (event.phase == "READINESS")
        require(checks <= plan.max_readiness_checks, "READINESS_BUDGET_EXHAUSTED")
        return replace(result, running=event.phase, readiness_checks=checks)
    require(state.running is not None and event.phase == state.running, "PHASE_NOT_RUNNING")
    receipt = _receipt(plan, state, event)
    if event.phase == "READINESS":
        return replace(result, running=None, ready=receipt.outcome == "READY")
    return replace(result, running=None, completed=(*state.completed, receipt))
