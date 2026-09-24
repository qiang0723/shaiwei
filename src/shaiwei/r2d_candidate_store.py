"""Test-directory-only SQLite adapter for the R3N stage journal, not production storage."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import sqlite3
from typing import Callable

from shaiwei.r2d_candidate_contract import (
    CandidatePlan, StageError, StageEvent, StageState, advance, canonical, digest, require,
)


class OfflineStageStore:
    """One explicitly created fixture database, never an implicit production path."""

    def __init__(self, directory: Path, plan: CandidatePlan, *, fault: Callable | None = None):
        self.directory = directory.absolute()
        self.plan = CandidatePlan.model_validate_json(plan.model_dump_json())
        self.fault = fault
        self.path = self.directory / "r3n-stages.sqlite3"
        self._confined()

    def _confined(self):
        root = Path(__file__).resolve().parents[2] / ".test-tmp"
        require(self.directory.is_relative_to(root), "OFFLINE_DIRECTORY_REQUIRED")
        require(self.directory != root, "DEDICATED_FIXTURE_DIRECTORY_REQUIRED")
        relative = self.directory.relative_to(root)
        require(".." not in relative.parts, "OFFLINE_DIRECTORY_REQUIRED")
        for path in (root, *[root.joinpath(*relative.parts[:i]) for i in range(1, len(relative.parts) + 1)]):
            require(not path.is_symlink(), "SYMLINK_FIXTURE_FORBIDDEN")
        require(self.directory.is_dir(), "FIXTURE_DIRECTORY_MISSING")
        for suffix in ("", "-journal", "-wal", "-shm"):
            require(not Path(str(self.path) + suffix).is_symlink(), "SYMLINK_FIXTURE_FORBIDDEN")
        if self.path.exists():
            require(self.path.stat().st_nlink == 1, "HARDLINK_FIXTURE_FORBIDDEN")

    @contextmanager
    def _connection(self):
        self._confined()
        require(self.path.is_file(), "JOURNAL_MISSING_DO_NOT_RECREATE")
        connection = None
        try:
            connection = sqlite3.connect(self.path.as_uri() + "?mode=rw", uri=True, timeout=0)
            connection.execute("PRAGMA synchronous=FULL")
            connection.execute("PRAGMA temp_store=MEMORY")
            connection.execute("PRAGMA trusted_schema=OFF")
            yield connection
        except sqlite3.Error:
            raise StageError("JOURNAL_IO_FAILURE") from None
        finally:
            if connection is not None:
                connection.close()

    def create(self) -> None:
        """Create once. Failed initialization leaves evidence; never overwrite or repair."""
        self._confined()
        try:
            with self.path.open("xb"):
                pass
        except FileExistsError:
            raise StageError("JOURNAL_ALREADY_EXISTS") from None
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("CREATE TABLE binding (id INTEGER PRIMARY KEY CHECK(id=1), plan TEXT NOT NULL)")
            connection.execute("CREATE TABLE events (sequence INTEGER PRIMARY KEY, payload TEXT NOT NULL, sha TEXT NOT NULL)")
            connection.execute("INSERT INTO binding VALUES (1, ?)", (canonical(self.plan),))
            connection.commit()

    def _load(self, connection) -> StageState:
        binding = connection.execute("SELECT id, plan FROM binding").fetchall()
        require(binding == [(1, canonical(self.plan))], "JOURNAL_PLAN_DIFFERS")
        state = StageState()
        for sequence, payload, checksum in connection.execute("SELECT sequence, payload, sha FROM events ORDER BY sequence"):
            try:
                event = StageEvent.model_validate_json(payload)
            except (ValueError, TypeError):
                raise StageError("JOURNAL_EVENT_INVALID") from None
            require(
                sequence == event.sequence and canonical(event) == payload and digest(event) == checksum,
                "JOURNAL_EVENT_HASH_DIFFERS",
            )
            state = advance(self.plan, state, event)
        return state

    def load(self) -> StageState:
        with self._connection() as connection:
            connection.execute("BEGIN")
            return self._load(connection)

    def append(self, *, expected_head: str, kind: str, phase, at, receipt=None) -> StageState:
        """Commit before returning. A lost response is not permission to repeat an append."""
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            state = self._load(connection)
            require(state.head == expected_head, "JOURNAL_CAS_CONFLICT")
            event = StageEvent(
                sequence=state.sequence + 1, previous_sha256=state.head,
                plan_sha256=digest(self.plan), kind=kind, phase=phase, at=at, receipt=receipt,
            )
            result = advance(self.plan, state, event)
            connection.execute("INSERT INTO events VALUES (?, ?, ?)", (event.sequence, canonical(event), result.head))
            if self.fault:
                self.fault("before_commit", event)
            connection.commit()
            if self.fault:
                self.fault("after_commit", event)
            return result
