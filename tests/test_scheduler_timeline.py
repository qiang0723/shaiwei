import json
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import yaml

import shaiwei.pipeline.scheduler_timeline as timeline_module
import shaiwei.storage.interprocess_lock as lock_module
from shaiwei.pipeline.scheduler_timeline import (
    SchedulerTimeline,
    TimelineError,
    load_timeline_contract,
    verify_timeline,
)
from shaiwei.storage.interprocess_lock import active_process_lock_count, logical_lock
from shaiwei.storage.lock_resources import DAILY_CYCLE


class Clock:
    def __init__(self) -> None:
        self.current = datetime(2026, 8, 24, 15, 59, tzinfo=timezone.utc)
        self.elapsed = 0.0

    def now(self) -> datetime:
        return self.current

    def monotonic(self) -> float:
        return self.elapsed

    def advance(self, seconds: float) -> None:
        self.current += timedelta(seconds=seconds)
        self.elapsed += seconds


@dataclass(frozen=True)
class Notice:
    status: str
    error_type: str = ""


def _timeline(tmp_path: Path, clock: Clock | None = None, cycle_id: str = "a" * 24):
    clock = clock or Clock()
    timeline = SchedulerTimeline(
        load_timeline_contract(),
        root=tmp_path,
        now=clock.now,
        monotonic=clock.monotonic,
        cycle_id_factory=lambda: cycle_id,
    )
    return timeline, clock


def test_frozen_contract_loads_strictly(tmp_path: Path):
    contract = load_timeline_contract()
    assert set(contract.phases) == {
        "CYCLE",
        "DAILY",
        "READINESS_PROBE",
        "DAILY_COLLECTION",
        "SHADOW",
        "PAPER",
        "PAPER_EXECUTE",
        "PAPER_VERIFY",
        "PAPER_ACCEPTANCE",
    }

    document = yaml.safe_load(
        Path("config/r2_1r0_scheduler_timeline_v1.yaml").read_text(encoding="utf-8")
    )
    document["storage"]["fsync_each_event"] = False
    path = tmp_path / "invalid.yaml"
    path.write_text(yaml.safe_dump(document), encoding="utf-8")
    with pytest.raises(TimelineError, match="invariant disabled"):
        load_timeline_contract(path)

    document = yaml.safe_load(
        Path("config/r2_1r0_scheduler_timeline_v1.yaml").read_text(encoding="utf-8")
    )
    document["phases"]["SHADOW"]["warn_after_seconds"] = 3601
    path.write_text(yaml.safe_dump(document), encoding="utf-8")
    with pytest.raises(TimelineError, match="budgets or account rules"):
        load_timeline_contract(path)


def test_hash_chain_and_cross_midnight_cycle_stay_in_start_file(tmp_path: Path):
    timeline, clock = _timeline(tmp_path)
    cycle = timeline.start_cycle()
    clock.advance(120)
    with cycle.phase("SHADOW", target_trade_date="20260824") as phase:
        phase.outcome = "PASS"
        clock.advance(10)
    cycle.finish("PASS", target_trade_date="20260824")

    path = tmp_path / "logs/scheduler/timeline_20260824.jsonl"
    events = verify_timeline(path, timeline.contract)
    assert [(row["phase"], row["status"]) for row in events] == [
        ("CYCLE", "STARTED"),
        ("SHADOW", "STARTED"),
        ("SHADOW", "COMPLETED"),
        ("CYCLE", "COMPLETED"),
    ]
    assert not (tmp_path / "logs/scheduler/timeline_20260825.jsonl").exists()


def test_slow_phase_persists_warn_before_notification_result(tmp_path: Path):
    calls = []
    timeline, clock = _timeline(tmp_path)

    def notify(phase: str, account: str, elapsed: float, budget: float) -> Notice:
        calls.append((phase, account, elapsed, budget))
        return Notice("PASS")

    cycle = timeline.start_cycle(warning_sink=notify)
    with cycle.phase("PAPER_EXECUTE", account_id="model_baseline") as phase:
        phase.outcome = "PASS"
        clock.advance(301)
    cycle.finish("PASS")

    events = verify_timeline(cycle.path, timeline.contract)
    assert events[2]["status"] == "COMPLETED_WITH_WARN"
    assert events[3]["event_kind"] == "DURATION_WARNING_NOTIFICATION"
    assert events[3]["status"] == "PASS"
    assert calls == [("PAPER_EXECUTE", "model_baseline", 301.0, 300.0)]


@pytest.mark.parametrize("with_sink", [False, True])
def test_warning_notification_failure_does_not_reclassify_core(
    tmp_path: Path, with_sink: bool
):
    timeline, clock = _timeline(tmp_path)

    def broken(*_args):
        raise ConnectionError("not persisted")

    cycle = timeline.start_cycle(warning_sink=broken if with_sink else None)
    with cycle.phase("PAPER_VERIFY", account_id="model_top20") as phase:
        phase.outcome = "PASS"
        clock.advance(301)
    cycle.finish("PASS")
    events = verify_timeline(cycle.path, timeline.contract)
    assert events[2]["status"] == "COMPLETED_WITH_WARN"
    assert events[3]["status"] == ("FAIL" if with_sink else "DISABLED")
    assert events[-1]["outcome"] == "PASS"


def test_tamper_and_truncated_tail_fail_closed(tmp_path: Path):
    timeline, _clock = _timeline(tmp_path)
    cycle = timeline.start_cycle()
    event = json.loads(cycle.path.read_text(encoding="utf-8"))
    event["recorded_at"] = "2026-08-24T00:00:00+00:00"
    cycle.path.write_text(json.dumps(event) + "\n", encoding="utf-8")
    with pytest.raises(TimelineError, match="SHA-256"):
        verify_timeline(cycle.path, timeline.contract)
    with pytest.raises(TimelineError, match="SHA-256"):
        with cycle.phase("DAILY"):
            pytest.fail("tampered history must be rejected before the body")

    other, _ = _timeline(tmp_path / "tail", cycle_id="b" * 24)
    other_cycle = other.start_cycle()
    with other_cycle.path.open("a", encoding="utf-8") as handle:
        handle.write("{")
    with pytest.raises(TimelineError, match="truncated tail"):
        verify_timeline(other_cycle.path, other.contract)


def test_unknown_phase_and_account_are_rejected_before_body(tmp_path: Path):
    timeline, _clock = _timeline(tmp_path)
    cycle = timeline.start_cycle()
    entered = False
    with pytest.raises(TimelineError, match="unknown scheduler phase"):
        with cycle.phase("UNKNOWN"):
            entered = True
    assert not entered
    with pytest.raises(TimelineError, match="frozen account"):
        with cycle.phase("PAPER_EXECUTE", account_id="other"):
            entered = True
    assert not entered


def test_append_failure_prevents_phase_body(tmp_path: Path, monkeypatch):
    timeline, _clock = _timeline(tmp_path)
    cycle = timeline.start_cycle()
    entered = False

    def fail(_event):
        raise TimelineError("disk failure")

    monkeypatch.setattr(cycle, "_append", fail)
    with pytest.raises(TimelineError, match="disk failure"):
        with cycle.phase("DAILY"):
            entered = True
    assert not entered


def test_unwritable_output_shape_fails_before_cycle_starts(tmp_path: Path):
    (tmp_path / "logs").write_text("not a directory", encoding="utf-8")
    timeline, _clock = _timeline(tmp_path)
    with pytest.raises(TimelineError, match="could not be persisted"):
        timeline.start_cycle()


def test_phase_exception_is_recorded_without_message(tmp_path: Path):
    timeline, _clock = _timeline(tmp_path)
    cycle = timeline.start_cycle()
    with pytest.raises(ValueError, match="sensitive detail"):
        with cycle.phase("SHADOW"):
            raise ValueError("sensitive detail")
    cycle.finish("FAILED", error_type="ValueError")
    events = verify_timeline(cycle.path, timeline.contract)
    assert events[2]["status"] == "FAILED"
    assert events[2]["error_type"] == "ValueError"
    assert "sensitive detail" not in cycle.path.read_text(encoding="utf-8")
    assert events[-1]["status"] == "FAILED"


def test_two_writers_produce_one_valid_chain(tmp_path: Path):
    contract = load_timeline_contract()

    def write_cycle(index: int) -> None:
        timeline = SchedulerTimeline(
            contract,
            root=tmp_path,
            cycle_id_factory=lambda: f"{index:024x}",
        )
        cycle = timeline.start_cycle()
        with cycle.phase("DAILY") as phase:
            phase.outcome = "NOOP"
        cycle.finish("NOOP")

    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(write_cycle, range(1, 9)))

    path = next((tmp_path / "logs/scheduler").glob("timeline_*.jsonl"))
    events = verify_timeline(path, contract)
    assert len(events) == 32
    by_cycle: dict[str, list[int]] = {}
    for event in events:
        by_cycle.setdefault(str(event["cycle_id"]), []).append(int(event["sequence"]))
    assert all(sequence == [1, 2, 3, 4] for sequence in by_cycle.values())


def test_process_mutex_serializes_threads_and_releases_registry(tmp_path: Path):
    barrier = threading.Barrier(8)
    state_mutex = threading.Lock()
    active = 0
    maximum_active = 0

    def enter() -> None:
        nonlocal active, maximum_active
        barrier.wait()
        with logical_lock(DAILY_CYCLE, lock_root=tmp_path):
            with state_mutex:
                active += 1
                maximum_active = max(maximum_active, active)
            time.sleep(0.005)
            with state_mutex:
                active -= 1

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda _index: enter(), range(8)))

    assert maximum_active == 1
    assert active_process_lock_count() == 0


def test_thread_chain_stays_valid_when_flock_is_ineffective(
    tmp_path: Path, monkeypatch
):
    original_read = timeline_module.read_and_verify

    def slow_read(handle, contract):
        result = original_read(handle, contract)
        time.sleep(0.005)
        return result

    monkeypatch.setattr(lock_module.fcntl, "flock", lambda *_args: None)
    monkeypatch.setattr(timeline_module, "read_and_verify", slow_read)
    contract = load_timeline_contract()
    barrier = threading.Barrier(8)

    def write_cycle(index: int) -> None:
        timeline = SchedulerTimeline(
            contract,
            root=tmp_path,
            cycle_id_factory=lambda: f"{index:024x}",
        )
        barrier.wait()
        cycle = timeline.start_cycle()
        with cycle.phase("DAILY") as phase:
            phase.outcome = "NOOP"
        cycle.finish("NOOP")

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(write_cycle, range(1, 9)))

    path = next((tmp_path / "logs/scheduler").glob("timeline_*.jsonl"))
    assert len(verify_timeline(path, contract)) == 32
    assert active_process_lock_count() == 0


def test_independent_processes_produce_one_valid_chain(tmp_path: Path):
    worker = """
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from shaiwei.pipeline.scheduler_timeline import SchedulerTimeline, load_timeline_contract

root = Path(sys.argv[1])
index = int(sys.argv[2])
ready = Path(sys.argv[3])
gate = Path(sys.argv[4])
ready.write_text("ready", encoding="utf-8")
deadline = time.monotonic() + 15
while not gate.exists():
    if time.monotonic() > deadline:
        raise RuntimeError("process concurrency gate timed out")
    time.sleep(0.001)
fixed_now = lambda: datetime(2026, 8, 24, 15, 59, tzinfo=timezone.utc)
timeline = SchedulerTimeline(
    load_timeline_contract(),
    root=root,
    now=fixed_now,
    cycle_id_factory=lambda: f"{index:024x}",
)
cycle = timeline.start_cycle()
with cycle.phase("DAILY") as phase:
    phase.outcome = "NOOP"
cycle.finish("NOOP")
"""
    gate = tmp_path / "start"
    processes = []
    for index in range(1, 5):
        ready = tmp_path / f"ready-{index}"
        processes.append(
            subprocess.Popen(
                [sys.executable, "-c", worker, str(tmp_path), str(index), str(ready), str(gate)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        )

    failures = []
    try:
        deadline = time.monotonic() + 15
        ready_paths = [tmp_path / f"ready-{index}" for index in range(1, 5)]
        while not all(path.exists() for path in ready_paths):
            if time.monotonic() > deadline:
                pytest.fail("independent process workers did not become ready")
            time.sleep(0.005)
        gate.write_text("start", encoding="utf-8")

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

    contract = load_timeline_contract()
    path = next((tmp_path / "logs/scheduler").glob("timeline_*.jsonl"))
    events = verify_timeline(path, contract)
    assert len(events) == 16
    by_cycle: dict[str, list[int]] = {}
    for event in events:
        by_cycle.setdefault(str(event["cycle_id"]), []).append(int(event["sequence"]))
    assert all(sequence == [1, 2, 3, 4] for sequence in by_cycle.values())


def test_invalid_outcome_fails_closed(tmp_path: Path):
    timeline, _clock = _timeline(tmp_path)
    cycle = timeline.start_cycle()
    with pytest.raises(TimelineError, match="invalid phase outcome"):
        with cycle.phase("DAILY") as phase:
            phase.outcome = "FREE_TEXT"
