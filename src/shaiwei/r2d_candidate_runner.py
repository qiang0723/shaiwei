"""Offline candidate ingress integration over injected metadata and business ports."""

from __future__ import annotations

from datetime import datetime
from typing import Callable, Protocol

from shaiwei.r2d_candidate_contract import (
    CandidateEvidence, CandidatePlan, PhaseReceipt, StageError, StageState,
    TickResult, digest, require,
)
from shaiwei.r2d_candidate_store import OfflineStageStore
from shaiwei.r2d_parking_rehearsal import rehearse_first_day
from shaiwei.r2d_post_close_contract import AttemptCounts, SHANGHAI

INGRESSES = frozenset({"scheduler", "daily", "shadow", "paper", "verify", "acceptance"})


class MetadataPort(Protocol):
    def read(self, plan: CandidatePlan, *, now: datetime) -> CandidateEvidence: ...


class BusinessPort(Protocol):
    def execute(
        self, *, phase: str, trade_date: str, begin_sha256: str, plan_sha256: str,
    ) -> PhaseReceipt: ...


def _aware(now: datetime) -> None:
    require(now.tzinfo is not None and now.utcoffset() is not None, "NAIVE_CLOCK")


def _evidence(metadata: MetadataPort, plan: CandidatePlan, now: datetime) -> CandidateEvidence:
    _aware(now)
    try:
        value = metadata.read(plan, now=now)
    except Exception:
        raise StageError("METADATA_UNAVAILABLE_OR_INVALID") from None
    require(isinstance(value, CandidateEvidence), "METADATA_TYPE_DIFFERS")
    try:
        return CandidateEvidence.model_validate_json(value.model_dump_json())
    except (ValueError, TypeError):
        raise StageError("METADATA_UNAVAILABLE_OR_INVALID") from None


def _resume_checks(plan: CandidatePlan, state: StageState, evidence: CandidateEvidence, now: datetime):
    observation = evidence.observation
    protocol = plan.rehearsal.post_close
    first = protocol.first_candidate_trade_date
    complete = state.next_phase is None
    require(state.running is None, "MAY_HAVE_WRITTEN_RECONCILIATION_REQUIRED")
    require(state.last_at is not None and state.last_at <= now, "JOURNAL_FROM_FUTURE")
    require(0 <= (now - observation.observed_at).total_seconds() <= 3600, "STALE_METADATA")
    require(state.last_at <= observation.observed_at, "METADATA_PRECEDES_STAGE")
    require(observation.binding == protocol.binding, "RUNTIME_IDENTITY_DRIFT")
    require(
        observation.candidate_floor_fixture_sha256 == protocol.candidate_floor_fixture_sha256
        and observation.calendar_next_trade_date == first, "CAPABILITY_OR_CALENDAR_DRIFT",
    )
    require(
        observation.handoff_verified and observation.all_entrypoints_gated and observation.singleton_held
        and protocol.not_before <= observation.handoff_completed_at < protocol.expires_at
        and observation.handoff_completed_at <= observation.observed_at,
        "ISOLATION_OR_HANDOFF_UNPROVEN",
    )
    require(now >= protocol.next_dispatch_not_before, "BEFORE_FIRST_DISPATCH")
    if not complete:
        require(
            now.astimezone(SHANGHAI).strftime("%Y%m%d") == first
            and observation.eligible_trade_date == first, "FIRST_NATURAL_DAY_MISSED",
        )
    require(observation.claim_state == ("ACCEPTED" if complete else "CLAIMED"), "CLAIM_STATE_DIFFERS")
    require(observation.full_first_day_acceptance_verified == complete, "ACCEPTANCE_STATE_DIFFERS")
    require(evidence.completed_receipts == state.completed, "INDEPENDENT_PHASE_PROOF_DIFFERS")
    phases = {receipt.phase for receipt in state.completed}
    counts = AttemptCounts(
        daily=int("DAILY" in phases), shadow=int("SHADOW" in phases),
        paper=int("PAPER_BASELINE" in phases) + int("PAPER_TOP20" in phases),
    )
    require(observation.attempts == counts, "ATTEMPT_COUNTS_DIFFERS")
    require(observation.pending_trade_dates == (() if counts.daily else (first,)), "PENDING_DATES_DIFFERS")


def _call_phase(factory, plan, phase, begin_sha256) -> PhaseReceipt:
    try:
        port = factory()
        receipt = port.execute(
            phase=phase, trade_date=plan.rehearsal.post_close.first_candidate_trade_date,
            begin_sha256=begin_sha256, plan_sha256=digest(plan),
        )
    except Exception:
        raise StageError("PHASE_FAILED_MAY_HAVE_WRITTEN") from None
    require(isinstance(receipt, PhaseReceipt), "PHASE_RECEIPT_TYPE_DIFFERS")
    try:
        return PhaseReceipt.model_validate_json(receipt.model_dump_json())
    except (ValueError, TypeError):
        raise StageError("PHASE_RECEIPT_INVALID") from None


def _result(status, state, now):
    return TickResult(status=status, checked_at=now, journal_head=state.head)


def run_offline_tick(
    *, ingress: str, plan: CandidatePlan, store: OfflineStageStore, metadata: MetadataPort,
    business_factory: Callable[[], BusinessPort], clock: Callable[[], datetime],
) -> TickResult:
    """A synchronous fixture tick; never imports or invokes real business entrypoints."""
    require(ingress in INGRESSES, "UNKNOWN_INGRESS")
    require(ingress == "scheduler", "STANDALONE_BUSINESS_INGRESS_DENIED")
    plan = CandidatePlan.model_validate_json(plan.model_dump_json())
    require(digest(store.plan) == digest(plan), "STORE_PLAN_DIFFERS")
    state = store.load()
    require(state.running is None, "MAY_HAVE_WRITTEN_RECONCILIATION_REQUIRED")
    now = clock()
    evidence = _evidence(metadata, plan, now)
    if not state.claimed:
        require(not evidence.completed_receipts, "UNOWNED_PHASE_PROOFS")
        decision = rehearse_first_day(plan.rehearsal, evidence.observation, now=now)
        if decision.status == "PARKED":
            return _result("PARKED", state, now)
        require(decision.status == "WOULD_CLAIM_FIRST_DAY", "UNOWNED_ACCEPTANCE")
        state = store.append(expected_head=state.head, kind="CLAIM", phase=None, at=now)
    else:
        _resume_checks(plan, state, evidence, now)
    return _run_stages(plan, store, state, metadata, business_factory, clock)


def _run_stages(plan, store, state, metadata, factory, clock):
    while state.next_phase is not None:
        now = clock()
        _resume_checks(plan, state, _evidence(metadata, plan, now), now)
        phase = state.next_phase
        state = store.append(expected_head=state.head, kind="BEGIN", phase=phase, at=now)
        receipt = _call_phase(factory, plan, phase, state.head)
        finished = clock()
        _aware(finished)
        require(
            finished.astimezone(SHANGHAI).strftime("%Y%m%d")
            == plan.rehearsal.post_close.first_candidate_trade_date,
            "PHASE_CROSSED_FIRST_DAY_BOUNDARY",
        )
        state = store.append(
            expected_head=state.head, kind="END", phase=phase, at=finished, receipt=receipt,
        )
        if receipt.outcome == "WAITING_SOURCE":
            return _result("WAITING_SOURCE", state, finished)
    now = clock()
    _resume_checks(plan, state, _evidence(metadata, plan, now), now)
    return _result("OFFLINE_FIRST_DAY_COMPLETE", state, now)
