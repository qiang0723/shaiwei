"""SQLite schema-v1 storage for the proposal-only control plane."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from .schema import SchemaFingerprintError, validate_schema_fingerprint

SCHEMA_VERSION = 1
EXPECTED_TABLES = {"proposals", "proposal_events", "idempotency_receipts"}

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS proposals (
    proposal_id TEXT PRIMARY KEY,
    actor_sha256 TEXT NOT NULL,
    proposal_request_sha256 TEXT NOT NULL,
    canonical_proposal_json TEXT NOT NULL,
    config_sha256 TEXT NOT NULL,
    authority_bundle_sha256 TEXT NOT NULL,
    source_snapshot_id TEXT NOT NULL,
    source_snapshot_sha256 TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    current_state TEXT NOT NULL CHECK(current_state IN ('DRAFT','REVIEW_REQUIRED','CANCELLED')),
    current_event_seq INTEGER NOT NULL CHECK(current_event_seq >= 1)
);
CREATE INDEX IF NOT EXISTS proposals_actor_created
ON proposals(actor_sha256, created_at DESC, proposal_id DESC);

CREATE TABLE IF NOT EXISTS proposal_events (
    event_id TEXT PRIMARY KEY,
    proposal_id TEXT NOT NULL REFERENCES proposals(proposal_id),
    event_seq INTEGER NOT NULL CHECK(event_seq >= 1),
    event_type TEXT NOT NULL CHECK(event_type IN
        ('PROPOSAL_CREATED','SUBMITTED_FOR_REVIEW','CANCELLED_BY_PROPOSER')),
    from_state TEXT NOT NULL CHECK(from_state IN ('NONE','DRAFT','REVIEW_REQUIRED')),
    to_state TEXT NOT NULL CHECK(to_state IN ('DRAFT','REVIEW_REQUIRED','CANCELLED')),
    actor_sha256 TEXT NOT NULL,
    command_sha256 TEXT NOT NULL,
    request_sha256 TEXT NOT NULL,
    payload_sha256 TEXT NOT NULL,
    prev_event_sha256 TEXT NOT NULL,
    event_sha256 TEXT NOT NULL UNIQUE,
    payload_json TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    UNIQUE(proposal_id, event_seq)
);

CREATE TABLE IF NOT EXISTS idempotency_receipts (
    actor_sha256 TEXT NOT NULL,
    route TEXT NOT NULL,
    idempotency_key_sha256 TEXT NOT NULL,
    request_sha256 TEXT NOT NULL,
    response_status INTEGER NOT NULL,
    response_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY(actor_sha256, route, idempotency_key_sha256)
);

CREATE TRIGGER IF NOT EXISTS proposals_immutable_columns
BEFORE UPDATE ON proposals
WHEN NEW.proposal_id != OLD.proposal_id
  OR NEW.actor_sha256 != OLD.actor_sha256
  OR NEW.proposal_request_sha256 != OLD.proposal_request_sha256
  OR NEW.canonical_proposal_json != OLD.canonical_proposal_json
  OR NEW.config_sha256 != OLD.config_sha256
  OR NEW.authority_bundle_sha256 != OLD.authority_bundle_sha256
  OR NEW.source_snapshot_id != OLD.source_snapshot_id
  OR NEW.source_snapshot_sha256 != OLD.source_snapshot_sha256
  OR NEW.created_at != OLD.created_at
  OR NEW.expires_at != OLD.expires_at
BEGIN SELECT RAISE(ABORT, 'immutable proposal field'); END;

CREATE TRIGGER IF NOT EXISTS proposals_no_delete
BEFORE DELETE ON proposals BEGIN SELECT RAISE(ABORT, 'proposal delete forbidden'); END;
CREATE TRIGGER IF NOT EXISTS events_no_update
BEFORE UPDATE ON proposal_events BEGIN SELECT RAISE(ABORT, 'event update forbidden'); END;
CREATE TRIGGER IF NOT EXISTS events_no_delete
BEFORE DELETE ON proposal_events BEGIN SELECT RAISE(ABORT, 'event delete forbidden'); END;
CREATE TRIGGER IF NOT EXISTS receipts_no_update
BEFORE UPDATE ON idempotency_receipts BEGIN SELECT RAISE(ABORT, 'receipt update forbidden'); END;
CREATE TRIGGER IF NOT EXISTS receipts_no_delete
BEFORE DELETE ON idempotency_receipts BEGIN SELECT RAISE(ABORT, 'receipt delete forbidden'); END;
"""


class StorageError(RuntimeError):
    """Storage is busy, corrupt, or has an unknown schema."""


class SQLiteStore:
    def __init__(self, database_path: Path, *, busy_timeout_ms: int = 2000) -> None:
        self.database_path = database_path
        self.busy_timeout_ms = busy_timeout_ms
        self._prepare_path()
        self._initialize()

    def _prepare_path(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        if self.database_path.exists() and self.database_path.is_symlink():
            raise StorageError("database path cannot be a symlink")

    def _connect(self) -> sqlite3.Connection:
        try:
            connection = sqlite3.connect(
                self.database_path,
                timeout=self.busy_timeout_ms / 1000,
                isolation_level=None,
            )
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute(f"PRAGMA busy_timeout = {int(self.busy_timeout_ms)}")
            connection.execute("PRAGMA synchronous = FULL")
            return connection
        except sqlite3.Error as exc:
            raise StorageError("cannot open control database") from exc

    @staticmethod
    def _tables(connection: sqlite3.Connection) -> set[str]:
        rows = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
        return {str(row[0]) for row in rows}

    def _initialize(self) -> None:
        connection = self._connect()
        try:
            result = connection.execute("PRAGMA quick_check").fetchone()
            if result is None or result[0] != "ok":
                raise StorageError("database quick_check failed")
            version = int(connection.execute("PRAGMA user_version").fetchone()[0])
            tables = self._tables(connection)
            if version == 0 and not tables:
                mode = connection.execute("PRAGMA journal_mode = WAL").fetchone()[0]
                if str(mode).lower() != "wal":
                    raise StorageError("WAL mode was not enabled")
                connection.execute("PRAGMA synchronous = FULL")
                connection.executescript(SCHEMA_SQL)
                connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
                version = SCHEMA_VERSION
                tables = self._tables(connection)
            if version != SCHEMA_VERSION or tables != EXPECTED_TABLES:
                raise StorageError("unknown or incomplete control database schema")
            try:
                validate_schema_fingerprint(connection)
            except SchemaFingerprintError as exc:
                raise StorageError("control database schema fingerprint mismatch") from exc
            mode = str(connection.execute("PRAGMA journal_mode").fetchone()[0]).lower()
            if mode != "wal" or int(connection.execute("PRAGMA foreign_keys").fetchone()[0]) != 1:
                raise StorageError("required SQLite safety pragmas are not active")
        except sqlite3.DatabaseError as exc:
            raise StorageError("control database is corrupt or incompatible") from exc
        finally:
            connection.close()

    @contextmanager
    def immediate(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            self._verify_ready(connection)
            yield connection
            connection.execute("COMMIT")
        except sqlite3.Error as exc:
            try:
                connection.execute("ROLLBACK")
            except sqlite3.Error:
                pass
            raise StorageError("control transaction failed") from exc
        except Exception:
            try:
                connection.execute("ROLLBACK")
            except sqlite3.Error:
                pass
            raise
        finally:
            connection.close()

    @contextmanager
    def read(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            connection.execute("BEGIN")
            self._verify_ready(connection)
            yield connection
            connection.execute("COMMIT")
        except sqlite3.DatabaseError as exc:
            try:
                connection.execute("ROLLBACK")
            except sqlite3.Error:
                pass
            raise StorageError("control read failed") from exc
        except Exception:
            try:
                connection.execute("ROLLBACK")
            except sqlite3.Error:
                pass
            raise
        finally:
            connection.close()

    def _verify_ready(self, connection: sqlite3.Connection) -> None:
        result = connection.execute("PRAGMA quick_check").fetchone()
        if result is None or result[0] != "ok":
            raise StorageError("database quick_check failed")
        if int(connection.execute("PRAGMA user_version").fetchone()[0]) != SCHEMA_VERSION:
            raise StorageError("database schema changed after startup")
        if self._tables(connection) != EXPECTED_TABLES:
            raise StorageError("database table set changed after startup")
        if str(connection.execute("PRAGMA journal_mode").fetchone()[0]).lower() != "wal":
            raise StorageError("database journal mode changed after startup")
        if int(connection.execute("PRAGMA foreign_keys").fetchone()[0]) != 1:
            raise StorageError("database foreign-key enforcement is disabled")
        if int(connection.execute("PRAGMA synchronous").fetchone()[0]) != 2:
            raise StorageError("database synchronous mode is not FULL")
        try:
            validate_schema_fingerprint(connection)
        except SchemaFingerprintError as exc:
            raise StorageError("database schema fingerprint changed after startup") from exc
