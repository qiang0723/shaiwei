from __future__ import annotations

import ast
import csv
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

import shaiwei.storage.interprocess_lock as lock_module
from shaiwei import ledger
from shaiwei.storage.interprocess_lock import (
    DOCKER_AUTHORITY,
    LockBusy,
    LockConfigurationError,
    LockMode,
    LockOrderError,
    active_process_lock_count,
    logical_lock,
)
from shaiwei.storage.lock_resources import (
    DAILY_CYCLE,
    PAPER_CYCLE,
    SHADOW_CYCLE,
    LockResourceError,
    cycle_resource,
    ledger_resource,
    resource_spec,
    timeline_resource,
)


ROOT = Path(__file__).parents[1]


def test_resource_registry_is_stable_portable_and_fail_closed(tmp_path: Path):
    assert resource_spec(DAILY_CYCLE).rank == 10
    assert resource_spec("runtime:scheduler-timeline:20260825").rank == 20
    assert resource_spec("ledger:paper_runs.csv").rank == 30
    assert timeline_resource(tmp_path / "timeline_20260825.jsonl") == (
        "runtime:scheduler-timeline:20260825"
    )
    assert cycle_resource("paper") == PAPER_CYCLE
    local = ledger_resource(tmp_path / "paper_runs.csv")
    assert local.startswith("local:ledger:") and resource_spec(local).local_only
    with pytest.raises(LockResourceError, match="unregistered"):
        resource_spec("runtime:free-text")
    with pytest.raises(LockResourceError, match="filename"):
        timeline_resource(tmp_path / "timeline_latest.jsonl")


def test_thread_layer_serializes_even_when_flock_is_ineffective(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(lock_module.fcntl, "flock", lambda *_args: None)
    barrier = threading.Barrier(8)
    guard = threading.Lock()
    active = 0
    maximum = 0

    def enter() -> None:
        nonlocal active, maximum
        barrier.wait()
        with logical_lock(DAILY_CYCLE, lock_root=tmp_path):
            with guard:
                active += 1
                maximum = max(maximum, active)
            time.sleep(0.003)
            with guard:
                active -= 1

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda _index: enter(), range(8)))
    assert maximum == 1
    assert active_process_lock_count() == 0


def test_nonblocking_contention_reentrancy_and_order_fail_closed(tmp_path: Path):
    entered = threading.Event()
    release = threading.Event()

    def holder() -> None:
        with logical_lock(DAILY_CYCLE, lock_root=tmp_path):
            entered.set()
            release.wait(timeout=5)

    thread = threading.Thread(target=holder)
    thread.start()
    assert entered.wait(timeout=5)
    with pytest.raises(LockBusy):
        with logical_lock(DAILY_CYCLE, blocking=False, lock_root=tmp_path):
            pytest.fail("busy lock body must not execute")
    release.set()
    thread.join(timeout=5)
    assert not thread.is_alive()

    with logical_lock(DAILY_CYCLE, lock_root=tmp_path):
        with logical_lock("ledger:daily_runs.csv", lock_root=tmp_path):
            pass
        with pytest.raises(LockOrderError, match="reentrant"):
            with logical_lock(DAILY_CYCLE, lock_root=tmp_path):
                pass
        with pytest.raises(LockOrderError, match="order"):
            with logical_lock(SHADOW_CYCLE, lock_root=tmp_path):
                pass


def test_shared_mode_and_identity_are_recorded(tmp_path: Path, monkeypatch):
    calls: list[int] = []
    real_flock = lock_module.fcntl.flock

    def observed(fd: int, operation: int) -> None:
        calls.append(operation)
        real_flock(fd, operation)

    monkeypatch.setattr(lock_module.fcntl, "flock", observed)
    resource = "runtime:scheduler-timeline:20260825"
    with logical_lock(resource, mode=LockMode.SHARED, lock_root=tmp_path):
        pass
    files = list(tmp_path.glob("*.lock"))
    assert len(files) == 1 and files[0].read_text(encoding="utf-8") == resource + "\n"
    assert lock_module.fcntl.LOCK_EX in calls
    assert lock_module.fcntl.LOCK_SH in calls
    assert calls[-1] == lock_module.fcntl.LOCK_UN


def test_production_authority_requires_exact_mounted_root(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(lock_module, "DOCKER_LOCK_ROOT", tmp_path / "locks")
    monkeypatch.setenv(lock_module.LOCK_AUTHORITY_ENV, DOCKER_AUTHORITY)
    monkeypatch.setenv(lock_module.LOCK_ROOT_ENV, str(tmp_path / "wrong"))
    with pytest.raises(LockConfigurationError, match="invalid root"):
        with logical_lock(DAILY_CYCLE):
            pass

    root = tmp_path / "locks"
    root.mkdir()
    monkeypatch.setenv(lock_module.LOCK_ROOT_ENV, str(root))
    monkeypatch.setattr(lock_module.os.path, "ismount", lambda path: Path(path) == root)
    with logical_lock(DAILY_CYCLE):
        pass
    with pytest.raises(LockConfigurationError, match="local-only"):
        with logical_lock(ledger_resource(tmp_path / "outside.csv")):
            pass

    blocked = lock_module._lock_path(root, SHADOW_CYCLE)
    blocked.mkdir()
    with pytest.raises(LockConfigurationError, match="not writable"):
        with logical_lock(SHADOW_CYCLE):
            pass


def test_unknown_authority_mode_and_identity_collision_fail_closed(tmp_path: Path, monkeypatch):
    monkeypatch.setenv(lock_module.LOCK_AUTHORITY_ENV, "unregistered")
    with pytest.raises(LockConfigurationError, match="unknown lock authority"):
        with logical_lock(DAILY_CYCLE):
            pass
    monkeypatch.delenv(lock_module.LOCK_AUTHORITY_ENV)
    with pytest.raises(LockConfigurationError, match="unknown lock mode"):
        with logical_lock(DAILY_CYCLE, mode="exclusive", lock_root=tmp_path):  # type: ignore[arg-type]
            pass
    path = lock_module._lock_path(tmp_path, DAILY_CYCLE)
    path.write_text(SHADOW_CYCLE + "\n", encoding="utf-8")
    with pytest.raises(LockConfigurationError, match="identity collision"):
        with logical_lock(DAILY_CYCLE, lock_root=tmp_path):
            pass


def test_released_runtime_without_authority_fails_before_creating_lock(
    tmp_path: Path, monkeypatch
):
    monkeypatch.delenv(lock_module.LOCK_AUTHORITY_ENV, raising=False)
    monkeypatch.setenv("SHAIWEI_RELEASE_MANIFEST", "/opt/shaiwei/release-manifest.json")
    with pytest.raises(LockConfigurationError, match="lacks Docker lock authority"):
        with logical_lock(DAILY_CYCLE, lock_root=tmp_path):
            pass
    assert list(tmp_path.iterdir()) == []


def test_independent_processes_append_every_ledger_row_once(tmp_path: Path):
    path = tmp_path / "concurrent.csv"
    path.write_text("id,value\n", encoding="utf-8")
    lock_root = tmp_path / "locks"
    gate = tmp_path / "gate"
    worker = """
import os
import sys
import time
from pathlib import Path
from shaiwei import ledger

path, gate, index = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
deadline = time.monotonic() + 15
while not gate.exists():
    if time.monotonic() > deadline:
        raise RuntimeError("gate timeout")
    time.sleep(0.001)
ledger._append(path, {"id": index, "value": f"v{index}"})
"""
    environment = {**os.environ, lock_module.LOCK_ROOT_ENV: str(lock_root)}
    processes = [
        subprocess.Popen(
            [sys.executable, "-c", worker, str(path), str(gate), str(index)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=environment,
        )
        for index in range(8)
    ]
    failures = []
    try:
        gate.write_text("go", encoding="utf-8")
        for process in processes:
            stdout, stderr = process.communicate(timeout=20)
            if process.returncode:
                failures.append((process.returncode, stdout, stderr))
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
        for process in processes:
            if process.poll() is None:
                process.wait(timeout=5)
    assert failures == []
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 8
    assert {row["id"] for row in rows} == {str(index) for index in range(8)}


def test_idempotent_ledger_collision_remains_fail_closed(tmp_path: Path):
    path = tmp_path / "idempotent.csv"
    path.write_text("id,value\n", encoding="utf-8")
    assert ledger._append_idempotent(path, {"id": "one", "value": "a"}, key="id")
    assert not ledger._append_idempotent(path, {"id": "one", "value": "a"}, key="id")
    with pytest.raises(ValueError, match="key collision"):
        ledger._append_idempotent(path, {"id": "one", "value": "b"}, key="id")


def _direct_flock_files() -> set[str]:
    found = set()
    for path in (ROOT / "src/shaiwei").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "fcntl"
                and node.func.attr == "flock"
            ):
                found.add(path.relative_to(ROOT).as_posix())
    return found


def test_direct_flock_inventory_is_self_discovering_and_migrations_are_complete():
    assert _direct_flock_files() == {
        "src/shaiwei/storage/interprocess_lock.py",
        "src/shaiwei/research/g1.py",
        "src/shaiwei/research/star50_residual_effect/evidence.py",
        "src/shaiwei/research_gates/gate_registry/outbox.py",
    }
    assert not (ROOT / "src/shaiwei/pipeline/scheduler_timeline_lock.py").exists()
