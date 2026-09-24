"""Offline R3N integration: real fixture persistence, synthetic independent business ports."""

from datetime import timedelta
from pathlib import Path
import tempfile

import pytest

from shaiwei.r2d_candidate_contract import (
    PHASES, CandidateEvidence, CandidatePlan, PhaseReceipt, StageError,
)
from shaiwei.r2d_candidate_runner import INGRESSES, run_offline_tick
from shaiwei.r2d_candidate_store import OfflineStageStore
from test_r2d_parking_rehearsal import first_day
from test_r2d_post_close_contract import change, dt


@pytest.fixture
def fixture_directory():
    root = Path(__file__).resolve().parents[1] / ".test-tmp"
    root.mkdir(exist_ok=True)
    return Path(tempfile.mkdtemp(prefix="r3n-fixture.", dir=root))


class World:
    def __init__(self, directory, *, limit=3):
        rehearsal, self.base_observation, self.now = first_day()
        self.plan = CandidatePlan(
            schema_version="r2d-candidate-offline-v1", mode="OFFLINE_FIXTURE_ONLY",
            rehearsal=rehearsal, max_readiness_checks=limit,
        )
        self.store = OfflineStageStore(directory, self.plan)
        self.store.create()
        self.calls = []
        self.receipts = []  # Independent of journal END rows: records fake business side effects.
        self.factory_calls = 0
        self.metadata_calls = 0
        self.ready = True
        self.crash_phase = None
        self.receipt_change = None
        self.metadata_change = None
        self.eligible = "20260921"

    def read(self, plan, *, now):
        self.metadata_calls += 1
        state = self.store.load()
        phases = {row.phase for row in self.receipts}
        accepted = "FINAL_ACCEPTANCE" in phases
        observation = change(
            self.base_observation, observed_at=now, eligible_trade_date=self.eligible,
            claim_state="ACCEPTED" if accepted else "CLAIMED" if state.claimed else "UNCLAIMED",
            full_first_day_acceptance_verified=accepted,
            pending_trade_dates=() if "DAILY" in phases else ("20260921",),
            attempts=dict(daily=int("DAILY" in phases), shadow=int("SHADOW" in phases),
                          paper=int("PAPER_BASELINE" in phases) + int("PAPER_TOP20" in phases)),
        )
        evidence = CandidateEvidence(observation=observation, completed_receipts=tuple(self.receipts))
        return self.metadata_change(evidence, state) if self.metadata_change else evidence

    def factory(self):
        state = self.store.load()
        assert state.claimed and state.running is not None  # Durable barrier before even construction.
        self.factory_calls += 1
        return self

    def execute(self, *, phase, trade_date, begin_sha256, plan_sha256):
        state = self.store.load()
        assert state.running == phase and state.head == begin_sha256
        assert trade_date == "20260921"
        self.calls.append(phase)
        if self.crash_phase == phase:
            raise SystemExit("synthetic interrupted phase")
        receipt = PhaseReceipt(
            plan_sha256=plan_sha256, trade_date=trade_date, phase=phase,
            begin_sha256=begin_sha256, evidence_sha256="a" * 64,
            outcome=("READY" if self.ready else "WAITING_SOURCE") if phase == "READINESS" else "PASS",
        )
        if phase != "READINESS":
            self.receipts.append(receipt)
        return self.receipt_change(receipt) if self.receipt_change else receipt

    def tick(self, ingress="scheduler"):
        return run_offline_tick(
            ingress=ingress, plan=self.plan, store=self.store, metadata=self,
            business_factory=self.factory, clock=lambda: self.now,
        )

    def reopen(self):
        self.store = OfflineStageStore(self.store.directory, self.plan)


def test_full_order_and_reopened_completion_never_repeat(fixture_directory):
    world = World(fixture_directory)
    result = world.tick()
    assert result.status == "OFFLINE_FIRST_DAY_COMPLETE"
    assert result.production_authorized is False
    assert world.calls == list(PHASES)
    assert len(world.store.load().completed) == 9
    world.reopen()
    assert world.tick() == result
    assert world.calls == list(PHASES)


@pytest.mark.parametrize("now,eligible", [
    ("2026-09-18T22:00:00+08:00", "20260918"),
    ("2026-09-19T22:00:00+08:00", "20260918"),
    ("2026-09-21T15:59:59+08:00", "20260921"),
])
def test_parked_does_not_claim_construct_or_call_business(fixture_directory, now, eligible):
    world = World(fixture_directory)
    world.now, world.eligible = dt(now), eligible
    assert world.tick().status == "PARKED"
    assert not world.store.load().claimed
    assert world.store.load().sequence == 0
    assert world.factory_calls == 0 and world.calls == []


@pytest.mark.parametrize("ingress", sorted(INGRESSES - {"scheduler"}) + ["other"])
def test_all_standalone_ingresses_deny_before_metadata_or_factory(fixture_directory, ingress):
    world = World(fixture_directory)
    with pytest.raises(StageError, match="INGRESS"):
        world.tick(ingress)
    assert world.metadata_calls == world.factory_calls == 0
    assert world.store.load().sequence == 0


def test_waiting_source_resumes_same_claim_without_formal_business(fixture_directory):
    world = World(fixture_directory)
    world.ready = False
    assert world.tick().status == "WAITING_SOURCE"
    first = world.store.load()
    assert first.sequence == 3 and first.claimed and not first.completed
    assert world.calls == ["READINESS"]
    world.reopen()
    world.now += timedelta(minutes=1)
    world.ready = True
    assert world.tick().status == "OFFLINE_FIRST_DAY_COMPLETE"
    assert world.calls == ["READINESS", *PHASES]
    assert world.store.load().readiness_checks == 2


def test_waiting_budget_is_bounded_and_does_not_loop_inside_tick(fixture_directory):
    world = World(fixture_directory, limit=2)
    world.ready = False
    for expected in (1, 2):
        assert world.tick().status == "WAITING_SOURCE"
        assert len(world.calls) == expected
    with pytest.raises(StageError, match="READINESS_BUDGET_EXHAUSTED"):
        world.tick()
    assert world.calls == ["READINESS", "READINESS"]


def test_waiting_cannot_roll_forward_to_another_trade_day(fixture_directory):
    world = World(fixture_directory)
    world.ready = False
    world.tick()
    world.now = dt("2026-09-22T16:00:00+08:00")
    with pytest.raises(StageError, match="FIRST_NATURAL_DAY_MISSED"):
        world.tick()
    assert world.calls == ["READINESS"]


@pytest.mark.parametrize("phase", PHASES)
def test_crash_in_any_phase_is_durable_unknown_and_never_auto_retried(fixture_directory, phase):
    world = World(fixture_directory)
    world.crash_phase = phase
    with pytest.raises(SystemExit):
        world.tick()
    before = list(world.calls)
    assert world.store.load().running == phase
    world.reopen()
    world.crash_phase = None
    with pytest.raises(StageError, match="MAY_HAVE_WRITTEN"):
        world.tick()
    assert world.calls == before and world.calls.count(phase) == 1


@pytest.mark.parametrize("phase", PHASES)
@pytest.mark.parametrize("point", ["before_commit", "after_commit"])
def test_end_commit_failure_never_repeats_business(fixture_directory, phase, point):
    world = World(fixture_directory)

    def fault(where, event):
        if where == point and event.kind == "END" and event.phase == phase:
            raise SystemExit("synthetic commit interruption")

    world.store.fault = fault
    with pytest.raises(SystemExit):
        world.tick()
    world.reopen()
    if point == "before_commit":
        with pytest.raises(StageError, match="MAY_HAVE_WRITTEN"):
            world.tick()
    else:
        assert world.tick().status == "OFFLINE_FIRST_DAY_COMPLETE"
    assert world.calls.count(phase) == 1


@pytest.mark.parametrize("point,kind", [
    ("before_commit", "CLAIM"), ("after_commit", "CLAIM"),
    ("before_commit", "BEGIN"), ("after_commit", "BEGIN"),
])
def test_barrier_commit_interruption_happens_before_factory(fixture_directory, point, kind):
    world = World(fixture_directory)

    def fault(where, event):
        if where == point and event.kind == kind:
            raise SystemExit("synthetic boundary interruption")

    world.store.fault = fault
    with pytest.raises(SystemExit):
        world.tick()
    assert world.factory_calls == 0 and world.calls == []
    world.reopen()
    if point == "after_commit" and kind == "BEGIN":
        with pytest.raises(StageError, match="MAY_HAVE_WRITTEN"):
            world.tick()
    else:
        assert world.tick().status == "OFFLINE_FIRST_DAY_COMPLETE"


@pytest.mark.parametrize("field,value", [
    ("plan_sha256", "0" * 64), ("trade_date", "20260918"), ("phase", "DAILY"),
    ("begin_sha256", "f" * 64), ("outcome", "PASS"),
])
def test_unbound_receipt_leaves_unknown_barrier(fixture_directory, field, value):
    world = World(fixture_directory)
    world.receipt_change = lambda receipt: change(receipt, **{field: value})
    with pytest.raises(StageError, match="RECEIPT"):
        world.tick()
    assert world.store.load().running == "READINESS"
    assert world.calls == ["READINESS"]


@pytest.mark.parametrize("phase", PHASES)
def test_identity_is_rechecked_before_each_stage(fixture_directory, phase):
    world = World(fixture_directory)

    def drift(evidence, state):
        if state.claimed and state.next_phase == phase:
            binding = change(evidence.observation.binding, candidate_code_sha256="e" * 64)
            return change(evidence, observation=change(evidence.observation, binding=binding))
        return evidence

    world.metadata_change = drift
    with pytest.raises(StageError, match="RUNTIME_IDENTITY_DRIFT"):
        world.tick()
    assert phase not in world.calls


def test_independent_effect_without_matching_end_is_not_fabricated_as_pass(fixture_directory):
    world = World(fixture_directory)

    def drift(evidence, state):
        if state.next_phase == "SHADOW":
            return change(evidence, completed_receipts=())
        return evidence

    world.metadata_change = drift
    with pytest.raises(StageError, match="INDEPENDENT_PHASE_PROOF_DIFFERS"):
        world.tick()
    assert world.calls == ["READINESS", "DAILY"]


def test_unexpected_formal_attempt_blocks_waiting_resume(fixture_directory):
    world = World(fixture_directory)
    world.ready = False
    world.tick()
    world.metadata_change = lambda evidence, state: change(
        evidence, observation=change(evidence.observation, attempts=dict(daily=1, shadow=0, paper=0)),
    )
    with pytest.raises(StageError, match="ATTEMPT_COUNTS_DIFFERS"):
        world.tick()
    assert world.calls == ["READINESS"]


def test_final_acceptance_not_replaced_by_two_paper_passes(fixture_directory):
    world = World(fixture_directory)
    world.crash_phase = "FINAL_ACCEPTANCE"
    with pytest.raises(SystemExit):
        world.tick()
    assert len(world.receipts) == 8
    world.reopen()
    with pytest.raises(StageError, match="MAY_HAVE_WRITTEN"):
        world.tick()


@pytest.mark.parametrize("target", ["metadata", "business"])
@pytest.mark.parametrize("error_class", [ValueError, StageError])
def test_adapter_errors_never_echo_raw_payload(fixture_directory, target, error_class):
    world = World(fixture_directory)

    def fail(*args):
        raise error_class("synthetic raw payload must not escape")

    if target == "metadata":
        world.metadata_change = fail
    else:
        world.factory = fail
    with pytest.raises(StageError) as error:
        world.tick()
    assert "raw payload" not in str(error.value)
    assert str(error.value) == ("METADATA_UNAVAILABLE_OR_INVALID" if target == "metadata"
                                else "PHASE_FAILED_MAY_HAVE_WRITTEN")
    assert world.store.load().running == (None if target == "metadata" else "READINESS")
