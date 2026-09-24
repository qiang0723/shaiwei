"""Fault and concurrency checks against disposable project-local R3N fixture databases."""

import ast
from datetime import timedelta
import multiprocessing
import os
from pathlib import Path
import sqlite3

import pytest
from pydantic import ValidationError

from shaiwei.r2d_candidate_contract import CandidatePlan, StageError, ZERO_HASH
from shaiwei.r2d_candidate_store import OfflineStageStore
from test_r2d_candidate_runner import World, fixture_directory as fixture_directory
from test_r2d_post_close_contract import change, dt


def claim(world):
    return world.store.append(expected_head=ZERO_HASH, kind="CLAIM", phase=None, at=world.now)


def test_existing_journal_never_overwritten_and_missing_never_recreated(fixture_directory):
    world = World(fixture_directory)
    state = claim(world)
    with pytest.raises(StageError, match="JOURNAL_ALREADY_EXISTS"):
        world.store.create()
    assert world.store.load() == state
    world.store.path.rename(fixture_directory / "preserved.sqlite3")
    with pytest.raises(StageError, match="JOURNAL_MISSING_DO_NOT_RECREATE"):
        world.store.load()
    assert not world.store.path.exists()


def test_journal_is_bound_to_exact_offline_plan(fixture_directory):
    world = World(fixture_directory)
    changed = change(world.plan, max_readiness_checks=4)
    other = OfflineStageStore(fixture_directory, changed)
    with pytest.raises(StageError, match="JOURNAL_PLAN_DIFFERS"):
        other.load()


def test_expected_head_cas_and_duplicate_claim_are_rejected(fixture_directory):
    world = World(fixture_directory)
    state = claim(world)
    with pytest.raises(StageError, match="JOURNAL_CAS_CONFLICT"):
        claim(world)
    with pytest.raises(StageError, match="INVALID_CLAIM"):
        world.store.append(expected_head=state.head, kind="CLAIM", phase=None, at=world.now)
    assert world.store.load() == state


@pytest.mark.parametrize("kind,phase,code", [
    ("BEGIN", "DAILY", "PHASE_ORDER_DIFFERS"),
    ("END", "READINESS", "PHASE_NOT_RUNNING"),
])
def test_no_stage_can_skip_readiness_or_forge_completion(fixture_directory, kind, phase, code):
    world = World(fixture_directory)
    state = claim(world)
    with pytest.raises(StageError, match=code):
        world.store.append(expected_head=state.head, kind=kind, phase=phase, at=world.now)
    assert world.store.load() == state


@pytest.mark.parametrize("timestamp", [
    "2026-09-21T15:59:59+08:00", "2026-09-22T00:00:00+08:00",
])
def test_storage_does_not_accept_out_of_first_day_claim(fixture_directory, timestamp):
    world = World(fixture_directory)
    with pytest.raises(StageError, match="EVENT_OUTSIDE_FIRST_DAY"):
        world.store.append(expected_head=ZERO_HASH, kind="CLAIM", phase=None, at=dt(timestamp))
    assert world.store.load().sequence == 0


def test_backward_clock_blocks_append_without_altering_history(fixture_directory):
    world = World(fixture_directory)
    world.now += timedelta(minutes=1)
    state = claim(world)
    with pytest.raises(StageError, match="JOURNAL_TIME_REVERSED"):
        world.store.append(expected_head=state.head, kind="BEGIN", phase="READINESS",
                           at=world.now - timedelta(seconds=1))
    assert world.store.load() == state


@pytest.mark.parametrize("sql", [
    "UPDATE events SET sha='bad' WHERE sequence=1",
    "UPDATE events SET payload='{}' WHERE sequence=1",
    "UPDATE events SET sequence=100 WHERE sequence=1",
    "DELETE FROM events WHERE sequence=1",
])
def test_corrupt_or_gapped_history_blocks_without_business(fixture_directory, sql):
    world = World(fixture_directory)
    world.ready = False
    world.tick()
    with sqlite3.connect(world.store.path) as connection:
        connection.execute(sql)
    world.reopen()
    with pytest.raises(StageError, match="JOURNAL"):
        world.tick()
    assert world.calls == ["READINESS"]


@pytest.mark.parametrize("rows", [1, 2, 21])
def test_truncated_tail_cannot_hide_independent_completed_business(fixture_directory, rows):
    world = World(fixture_directory)
    world.tick()
    sequence = world.store.load().sequence
    with sqlite3.connect(world.store.path) as connection:
        connection.execute("DELETE FROM events WHERE sequence > ?", (sequence - rows,))
    world.reopen()
    with pytest.raises(StageError):
        world.tick()
    assert len(world.calls) == 10


def _race_claim(directory, plan_json, barrier, results, kind, head):
    plan = CandidatePlan.model_validate_json(plan_json)
    store = OfflineStageStore(Path(directory), plan)
    barrier.wait(timeout=5)
    try:
        store.append(expected_head=head, kind=kind, phase=None if kind == "CLAIM" else "READINESS",
                     at=dt("2026-09-21T16:00:00+08:00"))
        results.put("COMMITTED")
    except StageError as error:
        results.put(str(error))


@pytest.mark.parametrize("kind", ["CLAIM", "BEGIN"])
def test_two_processes_cannot_claim_or_begin_the_same_phase_twice(fixture_directory, kind):
    world = World(fixture_directory)
    head = ZERO_HASH if kind == "CLAIM" else claim(world).head
    context = multiprocessing.get_context("fork")
    barrier, results = context.Barrier(2), context.Queue()
    workers = [context.Process(
        target=_race_claim,
        args=(str(fixture_directory), world.plan.model_dump_json(), barrier, results, kind, head),
    ) for _ in range(2)]
    try:
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join(timeout=10)
            assert worker.exitcode == 0
        outcomes = [results.get(timeout=2) for _ in workers]
        assert outcomes.count("COMMITTED") == 1
        assert set(outcomes) <= {"COMMITTED", "JOURNAL_CAS_CONFLICT", "JOURNAL_IO_FAILURE"}
        assert world.store.load().sequence == (1 if kind == "CLAIM" else 2)
    finally:
        for worker in workers:
            if worker.is_alive():
                worker.terminate()
                worker.join(timeout=5)
        results.close()
        results.join_thread()


def _crash_during_begin(directory, plan_json, head, point):
    def fault(where, event):
        if where == point:
            os._exit(73)  # Terminate this fixture child only, without connection cleanup.

    store = OfflineStageStore(Path(directory), CandidatePlan.model_validate_json(plan_json), fault=fault)
    store.append(expected_head=head, kind="BEGIN", phase="READINESS",
                 at=dt("2026-09-21T16:00:00+08:00"))


@pytest.mark.parametrize("point", ["before_commit", "after_commit"])
def test_real_fixture_process_exit_preserves_transaction_boundary(fixture_directory, point):
    world = World(fixture_directory)
    head = claim(world).head
    worker = multiprocessing.get_context("fork").Process(
        target=_crash_during_begin,
        args=(str(fixture_directory), world.plan.model_dump_json(), head, point),
    )
    try:
        worker.start()
        worker.join(timeout=10)
        assert worker.exitcode == 73
        world.reopen()
        state = world.store.load()
        assert state.running == ("READINESS" if point == "after_commit" else None)
        if point == "after_commit":
            with pytest.raises(StageError, match="MAY_HAVE_WRITTEN"):
                world.tick()
            assert world.calls == []
        else:
            assert world.tick().status == "OFFLINE_FIRST_DAY_COMPLETE"
    finally:
        if worker.is_alive():
            worker.terminate()
            worker.join(timeout=5)


def test_production_directory_is_rejected_before_any_database_io(fixture_directory):
    world = World(fixture_directory)
    root = Path(__file__).resolve().parents[1]
    for directory in (root, root / ".release", root / "ledger", root / ".test-tmp"):
        with pytest.raises(StageError, match="DIRECTORY"):
            OfflineStageStore(directory, world.plan)


def test_symlink_fixture_is_rejected(fixture_directory):
    world = World(fixture_directory)
    alias = fixture_directory / "alias"
    alias.symlink_to(fixture_directory, target_is_directory=True)
    with pytest.raises(StageError, match="SYMLINK"):
        OfflineStageStore(alias, world.plan)


def test_database_hardlink_is_rejected(fixture_directory):
    world = World(fixture_directory)
    (fixture_directory / "hardlink.sqlite3").hardlink_to(world.store.path)
    with pytest.raises(StageError, match="HARDLINK"):
        world.store.load()


@pytest.mark.parametrize("field,value", [("mode", "PRODUCTION"), ("max_readiness_checks", 0),
                                         ("max_readiness_checks", True)])
def test_plan_cannot_enable_live_mode_or_coerce_budget(fixture_directory, field, value):
    world = World(fixture_directory)
    with pytest.raises(ValidationError):
        change(world.plan, **{field: value})


def test_metadata_observation_must_follow_latest_durable_stage(fixture_directory):
    world = World(fixture_directory)
    world.ready = False
    world.tick()
    world.metadata_change = lambda evidence, state: change(
        evidence, observation=change(evidence.observation, observed_at=world.now - timedelta(seconds=1)),
    )
    with pytest.raises(StageError, match="METADATA_PRECEDES_STAGE"):
        world.tick()
    assert world.calls == ["READINESS"]


def test_no_candidate_module_imports_live_runtime_or_reads_environment():
    root = Path(__file__).resolve().parents[1] / "src" / "shaiwei"
    banned = {"os", "subprocess", "socket", "shaiwei.config", "shaiwei.release", "shaiwei.pipeline"}
    for name in ("r2d_candidate_contract.py", "r2d_candidate_store.py", "r2d_candidate_runner.py"):
        tree = ast.parse((root / name).read_text())
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.add(node.module)
        assert not any(module == bad or module.startswith(bad + ".")
                       for module in imports for bad in banned)
