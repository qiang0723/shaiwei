from __future__ import annotations

import csv
import io
from pathlib import Path

import yaml

from shaiwei.research_gates.gate_registry import (
    GateIdentity,
    GateRegistryService,
    GateRegistryStore,
)
from shaiwei.research_gates.gate_registry.integrity import verify_registry_integrity
from shaiwei.research_gates.gate_registry.outbox import (
    LEDGER_FIELDS,
    ledger_row,
    publish_pending,
)


ROOT = Path(__file__).parents[1]
APPROVER = "M5_LOCAL_PROTOCOL_APPROVER"


def _identity() -> GateIdentity:
    config = yaml.safe_load(
        (ROOT / "config/m5_dynamic_fundamental_cross_pool_v1.yaml").read_text(encoding="utf-8")
    )
    source = config["source_proposal"]
    return GateIdentity(
        proposal_id=source["proposal_id"],
        proposal_request_sha256=source["proposal_request_sha256"],
        canonical_proposal_sha256=source["canonical_proposal_sha256"],
        proposal_head_event_sha256=source["required_head_event_sha256"],
        proposal_export_sha256=source["proposal_export_sha256"],
        protocol_scope_sha256=(
            "ab8c33968c4ced325ec79524b774163f2991edd0c4d5d7eb7c139b27e9b17557"
        ),
        protocol_sha256="ce5cb6390df37baa553e470487c3cd319937a6d017bb43af3d874b5c41696b79",
        proposal_expires_at=source["expires_at"],
        candidate_ids=tuple(candidate["candidate_id"] for candidate in config["candidates"]),
    )


def _service(tmp_path: Path) -> GateRegistryService:
    return GateRegistryService(GateRegistryStore(tmp_path / "registry.sqlite3"))


def test_outbox_manual_publish_is_idempotent(tmp_path: Path) -> None:
    service = _service(tmp_path)
    identity = _identity()
    service.import_case(
        identity,
        actor=APPROVER,
        idempotency_key="import",
        recorded_at="2026-08-05T12:00:00+00:00",
    )
    service.advance(
        identity.case_id,
        "PROTOCOL_FROZEN",
        {
            "protocol_scope_sha256": identity.protocol_scope_sha256,
            "protocol_sha256": identity.protocol_sha256,
        },
        expected_event_seq=1,
        actor=APPROVER,
        idempotency_key="freeze",
        recorded_at="2026-08-05T12:01:00+00:00",
    )
    ledger = tmp_path / "m5_2_gate_events.csv"

    assert publish_pending(
        service.store, ledger, published_at="2026-08-05T12:10:00+00:00"
    ) == 2
    assert publish_pending(
        service.store, ledger, published_at="2026-08-05T12:11:00+00:00"
    ) == 0
    with ledger.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 2
    assert tuple(rows[0]) == LEDGER_FIELDS
    with service.store.read() as connection:
        assert connection.execute(
            "SELECT count(*) FROM outbox WHERE status='PUBLISHED'"
        ).fetchone()[0] == 2
        verify_registry_integrity(connection)


def test_outbox_adopts_exact_line_after_append_before_db_update(tmp_path: Path) -> None:
    service = _service(tmp_path)
    identity = _identity()
    service.import_case(
        identity,
        actor=APPROVER,
        idempotency_key="import",
        recorded_at="2026-08-05T12:00:00+00:00",
    )
    with service.store.read() as connection:
        expected = ledger_row(connection.execute("SELECT * FROM outbox").fetchone())
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=LEDGER_FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerow(expected)
    ledger = tmp_path / "m5_2_gate_events.csv"
    ledger.write_text(stream.getvalue(), encoding="utf-8", newline="")

    assert publish_pending(
        service.store, ledger, published_at="2026-08-05T12:10:00+00:00"
    ) == 1
    with ledger.open(encoding="utf-8", newline="") as handle:
        assert len(list(csv.DictReader(handle))) == 1
