"""Manual, crash-recoverable publication of committed gate events to a narrow ledger."""

from __future__ import annotations

import csv
import fcntl
import hashlib
import io
import os
from pathlib import Path
from typing import Any

from .integrity import verify_registry_integrity
from .models import RegistryError, canonical_json, require_utc_iso
from .storage import GateRegistryStore


LEDGER_FIELDS = (
    "schema_version",
    "outbox_id",
    "case_id",
    "event_seq",
    "event_id",
    "event_type",
    "event_sha256",
    "ledger_payload_sha256",
    "lifecycle_state",
    "data_gate_status",
    "engineering_gate_status",
    "evidence_tier",
    "release_scope_sha256",
    "evidence_manifest_sha256",
    "audit_manifest_sha256",
    "verdict",
    "recorded_at",
)


def _csv_line(row: dict[str, str], *, include_header: bool = False) -> str:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=LEDGER_FIELDS, lineterminator="\n")
    if include_header:
        writer.writeheader()
    writer.writerow(row)
    return stream.getvalue()


def ledger_row(outbox: Any) -> dict[str, str]:
    import json

    payload = json.loads(outbox["ledger_payload_json"])
    return {
        "schema_version": payload["schema_version"],
        "outbox_id": outbox["outbox_id"],
        "case_id": payload["case_id"],
        "event_seq": str(payload["event_seq"]),
        "event_id": payload["event_id"],
        "event_type": payload["event_type"],
        "event_sha256": payload["event_sha256"],
        "ledger_payload_sha256": outbox["ledger_payload_sha256"],
        "lifecycle_state": payload["lifecycle_state"],
        "data_gate_status": payload["data_gate_status"],
        "engineering_gate_status": payload["engineering_gate_status"],
        "evidence_tier": payload["evidence_tier"],
        "release_scope_sha256": payload["release_scope_sha256"],
        "evidence_manifest_sha256": payload["evidence_manifest_sha256"],
        "audit_manifest_sha256": payload["audit_manifest_sha256"],
        "verdict": payload["verdict"],
        "recorded_at": payload["recorded_at"],
    }


def _read_existing(handle: Any) -> dict[str, dict[str, str]]:
    handle.seek(0)
    content = handle.read()
    if not content:
        return {}
    reader = csv.DictReader(io.StringIO(content))
    if tuple(reader.fieldnames or ()) != LEDGER_FIELDS:
        raise RegistryError("M5-2 gate ledger header differs")
    rows: dict[str, dict[str, str]] = {}
    for row in reader:
        outbox_id = row["outbox_id"]
        if not outbox_id or outbox_id in rows:
            raise RegistryError("M5-2 gate ledger contains duplicate or empty outbox ID")
        rows[outbox_id] = dict(row)
    return rows


def publish_pending(store: GateRegistryStore, ledger_path: Path, *, published_at: str) -> int:
    """Publish each pending row once; a prior append is adopted after an interrupted DB update."""
    recorded = require_utc_iso(published_at, "published_at")
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    if ledger_path.exists() and ledger_path.is_symlink():
        raise RegistryError("gate ledger path cannot be a symlink")
    with store.read() as connection:
        verify_registry_integrity(connection)
        pending = connection.execute(
            "SELECT * FROM outbox WHERE status='PENDING' ORDER BY created_at,outbox_id"
        ).fetchall()
    if not pending:
        return 0
    mode = os.O_RDWR | os.O_CREAT
    descriptor = os.open(ledger_path, mode, 0o600)
    line_hashes: dict[str, str] = {}
    try:
        with os.fdopen(descriptor, "r+", encoding="utf-8", newline="") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            existing = _read_existing(handle)
            handle.seek(0, os.SEEK_END)
            for outbox in pending:
                row = ledger_row(outbox)
                old = existing.get(outbox["outbox_id"])
                if old is not None and canonical_json(old) != canonical_json(row):
                    raise RegistryError("existing gate ledger row differs from committed outbox")
                line = _csv_line(row)
                line_hashes[outbox["outbox_id"]] = hashlib.sha256(line.encode("utf-8")).hexdigest()
                if old is None:
                    if handle.tell() == 0:
                        header = io.StringIO(newline="")
                        csv.DictWriter(
                            header, fieldnames=LEDGER_FIELDS, lineterminator="\n"
                        ).writeheader()
                        handle.write(header.getvalue())
                    handle.write(line)
                    existing[outbox["outbox_id"]] = row
            handle.flush()
            os.fsync(handle.fileno())
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    except Exception:
        try:
            os.close(descriptor)
        except OSError:
            pass
        raise
    with store.immediate() as connection:
        verify_registry_integrity(connection)
        for outbox in pending:
            row = connection.execute(
                "SELECT status FROM outbox WHERE outbox_id=?", (outbox["outbox_id"],)
            ).fetchone()
            if row is None or row["status"] != "PENDING":
                raise RegistryError("outbox changed during manual publication")
            connection.execute(
                "UPDATE outbox SET status='PUBLISHED',published_at=?,ledger_line_sha256=? "
                "WHERE outbox_id=?",
                (recorded, line_hashes[outbox["outbox_id"]], outbox["outbox_id"]),
            )
        verify_registry_integrity(connection)
    return len(pending)
