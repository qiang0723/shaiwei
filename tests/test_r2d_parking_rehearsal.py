"""Synthetic design rehearsals; never load runtime settings or production evidence."""

import ast
from datetime import timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from shaiwei.r2d_parking_rehearsal import (
    DrainWitness, FirstDayObservation, RehearsalPlan, rehearse_first_day,
    rehearse_handoff,
)
from shaiwei.r2d_post_close_contract import ContractViolation
from test_r2d_post_close_contract import bundle, change, dt


def scenario():
    protocol, closed, now = bundle()
    plan = RehearsalPlan(
        schema_version="r2d-park-drain-rehearsal-v1", post_close=protocol,
        legacy_image_id="sha256:" + "8" * 64, prepared_image_id="sha256:" + "9" * 64,
        prepared_code_sha256="8" * 64,
        writer_container_ids=("d" * 64, "0" * 64), writer_inventory_sha256="a" * 64,
        drain_fixture_sha256="b" * 64, closed_cycle_sha256="c" * 64,
    )
    closed = change(closed, observed_at=now)
    witness = DrainWitness(
        binding=protocol.binding, writer_inventory_sha256="a" * 64,
        drain_fixture_sha256="b" * 64, closed_cycle_sha256="c" * 64,
        report_sha256="7" * 64,
        mutation_barrier_persisted_at=now - timedelta(minutes=4),
        first_mutation_at=now - timedelta(minutes=3),
        fence_held_since=now - timedelta(minutes=2),
        stop_requested_at=now - timedelta(minutes=2),
        observed_at=now - timedelta(seconds=30),
        all_entrypoints_fenced=True, fence_still_held=True, forced_kill_used=False,
        restart_suppression_verified=True, unknown_writer_count=0,
        exits=tuple(dict(
            container_id=container, exited_at=now - timedelta(minutes=1), exit_code=0,
            restart_count_before=0, restart_count_after=0, running=False, remaining_children=0,
        ) for container in plan.writer_container_ids),
    )
    return plan, closed, witness, now


def first_day(now=None):
    plan, _, _, _ = scenario()
    now = now or dt("2026-09-21T16:00:00+08:00")
    observation = FirstDayObservation(
        binding=plan.post_close.binding, observed_at=now,
        handoff_completed_at=dt("2026-09-18T22:00:00+08:00"),
        candidate_floor_fixture_sha256="6" * 64, handoff_verified=True,
        all_entrypoints_gated=True, singleton_held=True,
        calendar_next_trade_date="20260921", eligible_trade_date="20260921",
        pending_trade_dates=("20260921",), attempts=dict(daily=0, shadow=0, paper=0),
        claim_state="UNCLAIMED", full_first_day_acceptance_verified=False,
    )
    return plan, observation, now


def test_handoff_is_inert_deterministic_and_preserves_actual_legacy_previous():
    plan, closed, witness, now = scenario()
    decision = rehearse_handoff(plan, closed, witness, now=now)
    assert decision == rehearse_handoff(plan, closed, witness, now=now)
    assert decision.status == "WOULD_HANDOFF_PARKED"
    assert decision.production_authorized is False
    assert decision.expected_current_image_id == plan.post_close.binding.candidate_image_id
    assert decision.expected_previous_image_id == plan.legacy_image_id
    assert decision.expected_previous_image_id != plan.prepared_image_id
    assert decision.retained_prepared_image_id == plan.prepared_image_id


@pytest.mark.parametrize("field,value,code", [
    ("writer_inventory_sha256", "f" * 64, "DRAIN_CAPABILITY_DRIFT"),
    ("drain_fixture_sha256", "f" * 64, "DRAIN_CAPABILITY_DRIFT"),
    ("closed_cycle_sha256", "f" * 64, "CLOSED_CYCLE_DRIFT"),
    ("report_sha256", "f" * 64, "DRAIN_REPORT_DIFFERS"),
    ("all_entrypoints_fenced", False, "WRITER_COVERAGE_UNPROVEN"),
    ("fence_still_held", False, "WRITER_COVERAGE_UNPROVEN"),
    ("unknown_writer_count", 1, "WRITER_COVERAGE_UNPROVEN"),
    ("forced_kill_used", True, "UNSAFE_STOP_OR_RESTART_POLICY"),
    ("restart_suppression_verified", False, "UNSAFE_STOP_OR_RESTART_POLICY"),
])
def test_drain_attestation_failure(field, value, code):
    plan, closed, witness, now = scenario()
    with pytest.raises(ContractViolation, match=code):
        rehearse_handoff(plan, closed, change(witness, **{field: value}), now=now)


@pytest.mark.parametrize("field,value,code", [
    ("running", True, "WRITER_NOT_CLEANLY_EXITED"),
    ("exit_code", 1, "WRITER_NOT_CLEANLY_EXITED"),
    ("exit_code", 137, "WRITER_NOT_CLEANLY_EXITED"),
    ("remaining_children", 1, "CHILD_WRITER_REMAINS"),
    ("restart_count_after", 1, "WRITER_RESTARTED"),
    ("container_id", "f" * 64, "WRITER_SET_DIFFERS"),
    ("exited_at", dt("2026-09-18T21:00:00+08:00"), "EXIT_ORDER_INVALID"),
    ("exited_at", dt("2026-09-18T22:01:00+08:00"), "EXIT_ORDER_INVALID"),
])
def test_each_writer_requires_complete_exit_proof(field, value, code):
    plan, closed, witness, now = scenario()
    for index in range(2):
        rows = list(witness.exits)
        rows[index] = change(rows[index], **{field: value})
        with pytest.raises(ContractViolation, match=code):
            rehearse_handoff(plan, closed, change(witness, exits=tuple(rows)), now=now)


@pytest.mark.parametrize("rows", [(), (0,), (1,), (0, 0), (0, 1, 1)])
def test_missing_or_duplicate_writers_block(rows):
    plan, closed, witness, now = scenario()
    bad = change(witness, exits=tuple(witness.exits[index] for index in rows))
    with pytest.raises(ContractViolation, match="WRITER_SET_DIFFERS"):
        rehearse_handoff(plan, closed, bad, now=now)


@pytest.mark.parametrize("field,offset", [
    ("mutation_barrier_persisted_at", -170),
    ("first_mutation_at", -250),
    ("fence_held_since", -190),
    ("stop_requested_at", -130),
    ("observed_at", -150),
])
def test_no_mutation_can_precede_barrier_or_skip_fence(field, offset):
    plan, closed, witness, now = scenario()
    bad = change(witness, **{field: now + timedelta(seconds=offset)})
    with pytest.raises(ContractViolation, match="MUTATION_SEQUENCE_INVALID"):
        rehearse_handoff(plan, closed, bad, now=now)


@pytest.mark.parametrize("seconds", [-3601, 1])
def test_stale_or_future_exit_snapshot_blocks(seconds):
    plan, closed, witness, now = scenario()
    bad = change(witness, observed_at=now + timedelta(seconds=seconds))
    with pytest.raises(ContractViolation, match="STALE_OR_FUTURE_WITNESS"):
        rehearse_handoff(plan, closed, bad, now=now)


def test_archived_noop_must_not_be_fabricated_after_stop():
    plan, closed, witness, now = scenario()
    bad = change(closed, health_updated_at=now - timedelta(seconds=10))
    with pytest.raises(ContractViolation, match="ARCHIVED_HEALTH"):
        rehearse_handoff(plan, bad, witness, now=now)


def test_final_closure_must_be_rechecked_after_exit_observation():
    plan, closed, witness, now = scenario()
    with pytest.raises(ContractViolation, match="FINAL_CHECK_ORDER"):
        rehearse_handoff(plan, change(closed, observed_at=now - timedelta(minutes=2)), witness, now=now)


@pytest.mark.parametrize("field", ["state_sha256", "audit_sha256", "candidate_image_id"])
def test_binding_drift_blocks_both_stages(field):
    plan, closed, witness, now = scenario()
    value = ("sha256:" if field.endswith("image_id") else "") + "0" * 64
    drift = change(witness.binding, **{field: value})
    with pytest.raises(ContractViolation, match="DRAIN_BINDING_DRIFT"):
        rehearse_handoff(plan, closed, change(witness, binding=drift), now=now)
    plan, observed, now = first_day()
    with pytest.raises(ContractViolation, match="FIRST_DAY_BINDING_DRIFT"):
        rehearse_first_day(plan, change(observed, binding=drift), now=now)


def test_r3l_full_closure_and_window_gates_are_still_required():
    plan, closed, witness, now = scenario()
    with pytest.raises(ContractViolation, match="REPLAY_NOT_VERIFIED"):
        rehearse_handoff(plan, change(closed, independent_replay_pass=False), witness, now=now)
    with pytest.raises(ContractViolation, match="OUTSIDE_WINDOW"):
        rehearse_handoff(
            change(plan, post_close=change(plan.post_close, expires_at=now)), closed, witness, now=now,
        )


@pytest.mark.parametrize("timestamp,eligible,status", [
    ("2026-09-18T22:00:00+08:00", "20260918", "PARKED"),
    ("2026-09-19T22:00:00+08:00", "20260918", "PARKED"),
    ("2026-09-21T15:59:59+08:00", "20260921", "PARKED"),
    ("2026-09-21T16:00:00+08:00", "20260918", "PARKED"),
    ("2026-09-21T16:00:00+08:00", "20260921", "WOULD_CLAIM_FIRST_DAY"),
    ("2026-09-21T08:00:00+00:00", "20260921", "WOULD_CLAIM_FIRST_DAY"),
])
def test_parked_route_selects_no_claim_and_never_an_old_date(timestamp, eligible, status):
    plan, observed, now = first_day(dt(timestamp))
    observed = change(observed, eligible_trade_date=eligible)
    decision = rehearse_first_day(plan, observed, now=now)
    # A fake claim route only, not evidence of an integrated scheduler's behavior.
    claim_routes = []
    if decision.status == "WOULD_CLAIM_FIRST_DAY":
        claim_routes.append(decision.first_candidate_trade_date)
    assert decision.status == status
    assert decision.production_authorized is False
    assert claim_routes == (["20260921"] if status == "WOULD_CLAIM_FIRST_DAY" else [])


@pytest.mark.parametrize("field,value,code", [
    ("handoff_verified", False, "FIRST_DAY_ISOLATION_UNPROVEN"),
    ("all_entrypoints_gated", False, "FIRST_DAY_ISOLATION_UNPROVEN"),
    ("singleton_held", False, "FIRST_DAY_ISOLATION_UNPROVEN"),
    ("calendar_next_trade_date", "20260922", "FIRST_DAY_CALENDAR_DRIFT"),
    ("candidate_floor_fixture_sha256", "a" * 64, "PARKING_CAPABILITY_DRIFT"),
    ("claim_state", "CLAIMED", "CLAIM_REQUIRES_RECONCILIATION"),
    ("claim_state", "UNKNOWN", "CLAIM_REQUIRES_RECONCILIATION"),
    ("claim_state", "ACCEPTED", "FIRST_DAY_ACCEPTANCE_UNPROVEN"),
    ("full_first_day_acceptance_verified", True, "ACCEPTANCE_STATE_CONFLICT"),
    ("eligible_trade_date", "20260922", "MISSED_FIRST_NATURAL_DAY"),
    ("pending_trade_dates", ("20260918",), "OLD_OR_MULTIPLE_PENDING_DATES"),
    ("pending_trade_dates", ("20260918", "20260921"), "OLD_OR_MULTIPLE_PENDING_DATES"),
    ("pending_trade_dates", ("20260921", "20260921"), "OLD_OR_MULTIPLE_PENDING_DATES"),
    ("pending_trade_dates", (), "FIRST_DAY_PLAN_NOT_EXACT"),
])
def test_first_day_fail_closed(field, value, code):
    plan, observed, now = first_day()
    with pytest.raises(ContractViolation, match=code):
        rehearse_first_day(plan, change(observed, **{field: value}), now=now)


@pytest.mark.parametrize("phase", ["daily", "shadow", "paper"])
def test_any_first_day_attempt_blocks_blind_replay(phase):
    plan, observed, now = first_day()
    counts = dict(daily=0, shadow=0, paper=0)
    counts[phase] = 1
    with pytest.raises(ContractViolation, match="FIRST_DAY_ALREADY_ATTEMPTED"):
        rehearse_first_day(plan, change(observed, attempts=counts), now=now)


def test_missed_first_day_cannot_be_rolled_forward():
    plan, observed, now = first_day(dt("2026-09-22T08:00:00+08:00"))
    with pytest.raises(ContractViolation, match="MISSED_FIRST_NATURAL_DAY"):
        rehearse_first_day(plan, observed, now=now)


@pytest.mark.parametrize("seconds,valid", [(-3601, False), (-3600, True), (0, True), (1, False)])
def test_first_day_freshness_boundary(seconds, valid):
    plan, observed, now = first_day()
    changed = change(observed, observed_at=now + timedelta(seconds=seconds))
    if valid:
        assert rehearse_first_day(plan, changed, now=now).status == "WOULD_CLAIM_FIRST_DAY"
    else:
        with pytest.raises(ContractViolation, match="STALE_OR_FUTURE_WITNESS"):
            rehearse_first_day(plan, changed, now=now)


@pytest.mark.parametrize("timestamp", [
    "2026-09-18T19:59:59+08:00", "2026-09-19T20:00:00+08:00",
    "2026-09-21T16:01:00+08:00",
])
def test_first_day_cannot_launder_an_out_of_window_handoff(timestamp):
    plan, observed, now = first_day()
    bad = change(observed, handoff_completed_at=dt(timestamp))
    with pytest.raises(ContractViolation, match="HANDOFF_OUTSIDE_WINDOW_OR_FUTURE"):
        rehearse_first_day(plan, bad, now=now)


@pytest.mark.parametrize("stage", ["handoff", "first_day"])
def test_naive_clock_is_rejected(stage):
    plan, closed, witness, now = scenario()
    with pytest.raises(ContractViolation, match="NAIVE_CLOCK"):
        if stage == "handoff":
            rehearse_handoff(plan, closed, witness, now=now.replace(tzinfo=None))
        else:
            plan, observed, now = first_day()
            rehearse_first_day(plan, observed, now=now.replace(tzinfo=None))


@pytest.mark.parametrize("field,value", [
    ("exit_code", False), ("restart_count_before", True), ("running", 0),
    ("remaining_children", -1),
])
def test_exit_schema_rejects_weak_proofs(field, value):
    _, _, witness, _ = scenario()
    with pytest.raises(ValidationError):
        change(witness.exits[0], **{field: value})


def test_first_day_can_follow_expired_cutover_window_but_never_replay_acceptance():
    plan, observed, now = first_day()
    assert now > plan.post_close.expires_at
    assert rehearse_first_day(plan, observed, now=now).status == "WOULD_CLAIM_FIRST_DAY"
    accepted = change(observed, claim_state="ACCEPTED", full_first_day_acceptance_verified=True,
                      attempts=dict(daily=1, shadow=1, paper=2))
    assert rehearse_first_day(plan, accepted, now=now).status == "FIRST_DAY_ACCEPTED_NO_REPLAY"


@pytest.mark.parametrize("field,value", [
    ("handoff_verified", "true"), ("singleton_held", 1),
    ("eligible_trade_date", "20260230"), ("pending_trade_dates", ("20260230",)),
    ("attempts", dict(daily=True, shadow=0, paper=0)), ("production_authorized", True),
])
def test_strict_schema_rejects_coercion_and_extra_authority(field, value):
    _, observed, _ = first_day()
    with pytest.raises(ValidationError):
        change(observed, **{field: value})


@pytest.mark.parametrize("which", ["legacy", "prepared", "duplicate", "missing", "old_code", "new_code"])
def test_three_party_plan_identity_is_required(which):
    plan, _, _, _ = scenario()
    updates = {
        "legacy": dict(legacy_image_id=plan.post_close.binding.candidate_image_id),
        "prepared": dict(prepared_image_id=plan.legacy_image_id),
        "duplicate": dict(writer_container_ids=("d" * 64, "d" * 64)),
        "missing": dict(writer_container_ids=("0" * 64,)),
        "old_code": dict(prepared_code_sha256=plan.post_close.binding.legacy_code_sha256),
        "new_code": dict(prepared_code_sha256=plan.post_close.binding.candidate_code_sha256),
    }
    with pytest.raises(ValidationError):
        change(plan, **updates[which])


def test_reference_module_has_no_io_or_live_runtime_dependencies():
    import shaiwei.r2d_parking_rehearsal as module

    tree = ast.parse(Path(module.__file__).read_text())
    imports = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert imports <= {
        "__future__", "datetime", "typing", "pydantic", "shaiwei.r2d_post_close_contract",
    }
    assert not any(isinstance(node, ast.Import) for node in ast.walk(tree))
    calls = {node.func.id for node in ast.walk(tree)
             if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
    assert not calls & {"open", "eval", "exec", "__import__"}
