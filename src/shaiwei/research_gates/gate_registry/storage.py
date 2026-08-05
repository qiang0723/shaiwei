"""SQLite v1 storage with exact schema, WAL, FULL sync, and immediate writes."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from .models import RegistryError
from .schema import SchemaFingerprintError, validate_schema_fingerprint


SCHEMA_VERSION = 1
EXPECTED_TABLES = {"gate_cases", "gate_events", "idempotency_receipts", "outbox"}

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS gate_cases (
    case_id TEXT PRIMARY KEY,
    proposal_id TEXT NOT NULL,
    proposal_request_sha256 TEXT NOT NULL,
    canonical_proposal_sha256 TEXT NOT NULL,
    proposal_head_event_sha256 TEXT NOT NULL,
    proposal_export_sha256 TEXT NOT NULL,
    protocol_scope_sha256 TEXT NOT NULL UNIQUE,
    protocol_sha256 TEXT NOT NULL,
    proposal_expires_at TEXT NOT NULL,
    candidate_ids_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    lifecycle_state TEXT NOT NULL,
    data_gate_status TEXT NOT NULL,
    engineering_gate_status TEXT NOT NULL,
    evidence_tier TEXT NOT NULL,
    authoritative_outcome TEXT NOT NULL CHECK(authoritative_outcome='NOT_EVALUATED'),
    production_authorization TEXT NOT NULL CHECK(production_authorization='none'),
    current_event_seq INTEGER NOT NULL CHECK(current_event_seq >= 1)
);
CREATE INDEX IF NOT EXISTS gate_cases_proposal_protocol
ON gate_cases(proposal_id, protocol_scope_sha256);

CREATE TABLE IF NOT EXISTS gate_events (
    event_id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL REFERENCES gate_cases(case_id),
    event_seq INTEGER NOT NULL CHECK(event_seq >= 1),
    event_type TEXT NOT NULL,
    from_state_json TEXT NOT NULL,
    to_state_json TEXT NOT NULL,
    actor_sha256 TEXT NOT NULL,
    command_sha256 TEXT NOT NULL,
    request_sha256 TEXT NOT NULL,
    payload_sha256 TEXT NOT NULL,
    prev_event_sha256 TEXT NOT NULL,
    event_sha256 TEXT NOT NULL UNIQUE,
    payload_json TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    UNIQUE(case_id, event_seq)
);
CREATE INDEX IF NOT EXISTS gate_events_case_order ON gate_events(case_id, event_seq);

CREATE TABLE IF NOT EXISTS idempotency_receipts (
    actor_sha256 TEXT NOT NULL,
    route TEXT NOT NULL,
    idempotency_key_sha256 TEXT NOT NULL,
    request_sha256 TEXT NOT NULL,
    response_status INTEGER NOT NULL,
    response_json TEXT NOT NULL,
    response_sha256 TEXT NOT NULL,
    case_id TEXT NOT NULL,
    event_seq INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY(actor_sha256, route, idempotency_key_sha256),
    UNIQUE(case_id, event_seq),
    FOREIGN KEY(case_id, event_seq) REFERENCES gate_events(case_id, event_seq)
);

CREATE TABLE IF NOT EXISTS outbox (
    outbox_id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL,
    event_seq INTEGER NOT NULL,
    ledger_payload_json TEXT NOT NULL,
    ledger_payload_sha256 TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('PENDING','PUBLISHED')),
    created_at TEXT NOT NULL,
    published_at TEXT,
    ledger_line_sha256 TEXT,
    UNIQUE(case_id, event_seq),
    FOREIGN KEY(case_id, event_seq) REFERENCES gate_events(case_id, event_seq),
    CHECK(
      (status='PENDING' AND published_at IS NULL AND ledger_line_sha256 IS NULL)
      OR (status='PUBLISHED' AND published_at IS NOT NULL AND ledger_line_sha256 IS NOT NULL)
    )
);
CREATE INDEX IF NOT EXISTS outbox_pending ON outbox(status, created_at, outbox_id);

CREATE TRIGGER IF NOT EXISTS gate_cases_immutable_columns
BEFORE UPDATE ON gate_cases
WHEN NEW.case_id != OLD.case_id
  OR NEW.proposal_id != OLD.proposal_id
  OR NEW.proposal_request_sha256 != OLD.proposal_request_sha256
  OR NEW.canonical_proposal_sha256 != OLD.canonical_proposal_sha256
  OR NEW.proposal_head_event_sha256 != OLD.proposal_head_event_sha256
  OR NEW.proposal_export_sha256 != OLD.proposal_export_sha256
  OR NEW.protocol_scope_sha256 != OLD.protocol_scope_sha256
  OR NEW.protocol_sha256 != OLD.protocol_sha256
  OR NEW.proposal_expires_at != OLD.proposal_expires_at
  OR NEW.candidate_ids_json != OLD.candidate_ids_json
  OR NEW.created_at != OLD.created_at
BEGIN SELECT RAISE(ABORT, 'immutable gate case field'); END;

CREATE TRIGGER IF NOT EXISTS gate_cases_no_delete
BEFORE DELETE ON gate_cases BEGIN SELECT RAISE(ABORT, 'gate case delete forbidden'); END;
CREATE TRIGGER IF NOT EXISTS gate_events_no_update
BEFORE UPDATE ON gate_events BEGIN SELECT RAISE(ABORT, 'gate event update forbidden'); END;
CREATE TRIGGER IF NOT EXISTS gate_events_no_delete
BEFORE DELETE ON gate_events BEGIN SELECT RAISE(ABORT, 'gate event delete forbidden'); END;
CREATE TRIGGER IF NOT EXISTS gate_receipts_no_update
BEFORE UPDATE ON idempotency_receipts BEGIN SELECT RAISE(ABORT, 'gate receipt update forbidden'); END;
CREATE TRIGGER IF NOT EXISTS gate_receipts_no_delete
BEFORE DELETE ON idempotency_receipts BEGIN SELECT RAISE(ABORT, 'gate receipt delete forbidden'); END;
CREATE TRIGGER IF NOT EXISTS gate_outbox_no_delete
BEFORE DELETE ON outbox BEGIN SELECT RAISE(ABORT, 'gate outbox delete forbidden'); END;
CREATE TRIGGER IF NOT EXISTS gate_outbox_limited_update
BEFORE UPDATE ON outbox
WHEN NEW.outbox_id != OLD.outbox_id
  OR NEW.case_id != OLD.case_id
  OR NEW.event_seq != OLD.event_seq
  OR NEW.ledger_payload_json != OLD.ledger_payload_json
  OR NEW.ledger_payload_sha256 != OLD.ledger_payload_sha256
  OR NEW.created_at != OLD.created_at
  OR OLD.status != 'PENDING'
  OR NEW.status != 'PUBLISHED'
  OR NEW.published_at IS NULL
  OR NEW.ledger_line_sha256 IS NULL
BEGIN SELECT RAISE(ABORT, 'invalid gate outbox update'); END;
"""


class GateRegistryStore:
    def __init__(self, database_path: Path, *, busy_timeout_ms: int = 2000) -> None:
        self.database_path = database_path
        self.busy_timeout_ms = busy_timeout_ms
        self._prepare_path()
        self._initialize()

    def _prepare_path(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        if self.database_path.exists() and self.database_path.is_symlink():
            raise RegistryError("registry path cannot be a symlink")

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
            raise RegistryError("cannot open M5-2 registry") from exc

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
                raise RegistryError("registry quick_check failed")
            version = int(connection.execute("PRAGMA user_version").fetchone()[0])
            tables = self._tables(connection)
            if version == 0 and not tables:
                mode = connection.execute("PRAGMA journal_mode = WAL").fetchone()[0]
                if str(mode).lower() != "wal":
                    raise RegistryError("registry WAL mode was not enabled")
                connection.executescript(SCHEMA_SQL)
                connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
                version = SCHEMA_VERSION
                tables = self._tables(connection)
            if version != SCHEMA_VERSION or tables != EXPECTED_TABLES:
                raise RegistryError("unknown or incomplete M5-2 registry schema")
            self._verify_connection(connection)
        except sqlite3.DatabaseError as exc:
            raise RegistryError("M5-2 registry is corrupt or incompatible") from exc
        finally:
            connection.close()

    def _verify_connection(self, connection: sqlite3.Connection) -> None:
        result = connection.execute("PRAGMA quick_check").fetchone()
        if result is None or result[0] != "ok":
            raise RegistryError("registry quick_check failed")
        if int(connection.execute("PRAGMA user_version").fetchone()[0]) != SCHEMA_VERSION:
            raise RegistryError("registry schema version changed")
        if self._tables(connection) != EXPECTED_TABLES:
            raise RegistryError("registry table set changed")
        if str(connection.execute("PRAGMA journal_mode").fetchone()[0]).lower() != "wal":
            raise RegistryError("registry journal mode changed")
        if int(connection.execute("PRAGMA foreign_keys").fetchone()[0]) != 1:
            raise RegistryError("registry foreign keys are disabled")
        if int(connection.execute("PRAGMA synchronous").fetchone()[0]) != 2:
            raise RegistryError("registry synchronous mode is not FULL")
        try:
            validate_schema_fingerprint(connection)
        except SchemaFingerprintError as exc:
            raise RegistryError("registry schema fingerprint changed") from exc

    @contextmanager
    def immediate(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            self._verify_connection(connection)
            yield connection
            connection.execute("COMMIT")
        except sqlite3.Error as exc:
            try:
                connection.execute("ROLLBACK")
            except sqlite3.Error:
                pass
            raise RegistryError("M5-2 registry transaction failed") from exc
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
            self._verify_connection(connection)
            yield connection
            connection.execute("COMMIT")
        except sqlite3.Error as exc:
            try:
                connection.execute("ROLLBACK")
            except sqlite3.Error:
                pass
            raise RegistryError("M5-2 registry read failed") from exc
        finally:
            connection.close()
