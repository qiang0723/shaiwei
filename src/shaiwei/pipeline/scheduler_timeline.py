"""Append-only writer and phase contexts for scheduler timing evidence."""

from __future__ import annotations

import fcntl
import json
import os
import re
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterator, Protocol
from zoneinfo import ZoneInfo

from shaiwei.config import PROJECT_ROOT
from shaiwei.pipeline.scheduler_timeline_contract import (
    TimelineContract,
    TimelineError,
    load_timeline_contract,
)
from shaiwei.pipeline.scheduler_timeline_events import (
    event_hash,
    read_and_verify,
    safe_error_type,
    validate_event,
    verify_timeline,
)

__all__ = [
    "CycleTimeline",
    "PhaseObservation",
    "SchedulerTimeline",
    "TimelineContract",
    "TimelineError",
    "load_timeline_contract",
    "observe_phase",
    "verify_timeline",
]


@dataclass
class PhaseObservation:
    outcome: str = ""
    target_trade_date: str = ""


class WarningResult(Protocol):
    status: str
    error_type: str


WarningSink = Callable[[str, str, float, float], WarningResult]


class SchedulerTimeline:
    def __init__(
        self,
        contract: TimelineContract,
        *,
        root: Path = PROJECT_ROOT,
        now: Callable[[], datetime] | None = None,
        monotonic: Callable[[], float] = time.monotonic,
        cycle_id_factory: Callable[[], str] | None = None,
    ) -> None:
        self.contract = contract
        self.root = root
        self.now = now or (lambda: datetime.now(timezone.utc))
        self.monotonic = monotonic
        self.cycle_id_factory = cycle_id_factory or (lambda: uuid.uuid4().hex[:24])

    def start_cycle(self, *, warning_sink: WarningSink | None = None) -> CycleTimeline:
        started_at = self.now()
        if started_at.tzinfo is None:
            raise TimelineError("cycle clock must return a timezone-aware datetime")
        local_date = started_at.astimezone(ZoneInfo(self.contract.timezone)).strftime("%Y%m%d")
        cycle_id = self.cycle_id_factory()
        if not re.fullmatch(r"[0-9a-f]{24}", cycle_id):
            raise TimelineError("cycle_id factory returned an invalid identifier")
        path = self.root / self.contract.directory / self.contract.filename_pattern.format(
            cycle_started_local_date=local_date
        )
        cycle = CycleTimeline(
            contract=self.contract,
            path=path,
            cycle_id=cycle_id,
            local_date=local_date,
            now=self.now,
            monotonic=self.monotonic,
            warning_sink=warning_sink,
        )
        cycle.start()
        return cycle


class CycleTimeline:
    def __init__(
        self,
        *,
        contract: TimelineContract,
        path: Path,
        cycle_id: str,
        local_date: str,
        now: Callable[[], datetime],
        monotonic: Callable[[], float],
        warning_sink: WarningSink | None,
    ) -> None:
        self.contract = contract
        self.path = path
        self.cycle_id = cycle_id
        self.local_date = local_date
        self.now = now
        self.monotonic = monotonic
        self.warning_sink = warning_sink
        self.sequence = 0
        self.cycle_started = 0.0
        self.closed = False

    def start(self) -> None:
        if self.sequence or self.cycle_started:
            raise TimelineError("cycle is already started")
        self.cycle_started = self.monotonic()
        self._append_phase("CYCLE", "STARTED", elapsed=0.0)

    def _append(self, event: dict[str, object]) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a+", encoding="utf-8") as handle:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
                previous_hash, sequences = read_and_verify(handle, self.contract)
                expected = sequences.get(self.cycle_id, 0) + 1
                if expected != self.sequence + 1:
                    raise TimelineError("in-memory cycle sequence differs from persisted timeline")
                event["previous_event_sha256"] = previous_hash
                event["event_sha256"] = event_hash(event)
                validate_event(
                    event,
                    self.contract,
                    previous_hash=previous_hash,
                    expected_sequence=expected,
                )
                handle.seek(0, os.SEEK_END)
                handle.write(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
                self.sequence = expected
        except TimelineError:
            raise
        except OSError as error:
            raise TimelineError("timeline event could not be persisted") from error

    def _event(
        self,
        *,
        kind: str,
        phase: str,
        status: str,
        account_id: str,
        target_trade_date: str,
        elapsed: float,
        error_type: str,
        outcome: str,
    ) -> dict[str, object]:
        if phase not in self.contract.phases:
            raise TimelineError("unknown scheduler phase")
        return {
            "schema_version": self.contract.event_schema_version,
            "event_kind": kind,
            "cycle_id": self.cycle_id,
            "sequence": self.sequence + 1,
            "recorded_at": self.now().astimezone(timezone.utc).isoformat(),
            "cycle_started_local_date": self.local_date,
            "phase": phase,
            "status": status,
            "target_trade_date": target_trade_date,
            "account_id": account_id,
            "elapsed_seconds": round(max(0.0, elapsed), 6),
            "budget_seconds": self.contract.phases[phase].warn_after_seconds,
            "error_type": error_type,
            "outcome": outcome,
            "previous_event_sha256": "",
            "event_sha256": "",
        }

    def _append_phase(
        self,
        phase: str,
        status: str,
        *,
        account_id: str = "",
        target_trade_date: str = "",
        elapsed: float,
        error_type: BaseException | str | None = None,
        outcome: str = "",
    ) -> None:
        self._append(
            self._event(
                kind="PHASE",
                phase=phase,
                status=status,
                account_id=account_id,
                target_trade_date=target_trade_date,
                elapsed=elapsed,
                error_type=safe_error_type(error_type),
                outcome=outcome,
            )
        )

    def _notify_warning(
        self,
        phase: str,
        *,
        account_id: str,
        target_trade_date: str,
        elapsed: float,
    ) -> None:
        status, error_type = "DISABLED", ""
        if self.warning_sink is not None:
            try:
                result = self.warning_sink(
                    phase,
                    account_id,
                    elapsed,
                    self.contract.phases[phase].warn_after_seconds,
                )
                status, error_type = result.status, safe_error_type(result.error_type)
                if status not in self.contract.notification_statuses:
                    status, error_type = "FAIL", "InvalidWarningResult"
                elif status == "FAIL" and not error_type:
                    error_type = "NotificationFailure"
                elif status != "FAIL":
                    error_type = ""
            except Exception as error:
                status, error_type = "FAIL", safe_error_type(error)
        self._append(
            self._event(
                kind="DURATION_WARNING_NOTIFICATION",
                phase=phase,
                status=status,
                account_id=account_id,
                target_trade_date=target_trade_date,
                elapsed=elapsed,
                error_type=error_type,
                outcome="",
            )
        )

    def _complete(
        self,
        phase: str,
        *,
        started: float,
        observation: PhaseObservation,
        account_id: str = "",
    ) -> None:
        elapsed = self.monotonic() - started
        warned = elapsed > self.contract.phases[phase].warn_after_seconds
        self._append_phase(
            phase,
            "COMPLETED_WITH_WARN" if warned else "COMPLETED",
            account_id=account_id,
            target_trade_date=observation.target_trade_date,
            elapsed=elapsed,
            outcome=observation.outcome,
        )
        if warned:
            self._notify_warning(
                phase,
                account_id=account_id,
                target_trade_date=observation.target_trade_date,
                elapsed=elapsed,
            )

    @contextmanager
    def phase(
        self,
        phase: str,
        *,
        account_id: str = "",
        target_trade_date: str = "",
    ) -> Iterator[PhaseObservation]:
        if self.closed:
            raise TimelineError("cannot append a phase to a closed cycle")
        observation = PhaseObservation(target_trade_date=target_trade_date)
        started = self.monotonic()
        self._append_phase(
            phase,
            "STARTED",
            account_id=account_id,
            target_trade_date=target_trade_date,
            elapsed=0.0,
        )
        try:
            yield observation
        except Exception as error:
            self._append_phase(
                phase,
                "FAILED",
                account_id=account_id,
                target_trade_date=observation.target_trade_date,
                elapsed=self.monotonic() - started,
                error_type=error,
                outcome=observation.outcome,
            )
            raise
        self._complete(phase, started=started, observation=observation, account_id=account_id)

    def finish(
        self,
        outcome: str,
        *,
        target_trade_date: str = "",
        error_type: BaseException | str | None = None,
    ) -> None:
        if self.closed:
            raise TimelineError("cycle is already closed")
        if outcome == "FAILED":
            self._append_phase(
                "CYCLE",
                "FAILED",
                target_trade_date=target_trade_date,
                elapsed=self.monotonic() - self.cycle_started,
                error_type=error_type or "SchedulerCycleFailure",
                outcome=outcome,
            )
        else:
            self._complete(
                "CYCLE",
                started=self.cycle_started,
                observation=PhaseObservation(outcome, target_trade_date),
            )
        self.closed = True


@contextmanager
def observe_phase(
    timeline: CycleTimeline | None,
    phase: str,
    *,
    account_id: str = "",
    target_trade_date: str = "",
) -> Iterator[PhaseObservation]:
    """Use a real timeline when supplied and a no-op observation otherwise."""
    if timeline is None:
        yield PhaseObservation(target_trade_date=target_trade_date)
        return
    with timeline.phase(
        phase,
        account_id=account_id,
        target_trade_date=target_trade_date,
    ) as observation:
        yield observation
