"""Short-lived CLI for the M5-2 registry; no daemon, HTTP server, queue, or retry loop."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .integrity import verify_registry_integrity
from .models import GateIdentity, RegistryError, canonical_json
from .outbox import publish_pending
from .service import GateRegistryService
from .storage import GateRegistryStore


def _json_file(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RegistryError("command file must contain one JSON object")
    return value


def _identity(value: dict[str, Any]) -> GateIdentity:
    fields = set(GateIdentity.__dataclass_fields__)
    if set(value) != fields:
        raise RegistryError("identity fields differ from registry v1")
    return GateIdentity(
        **{
            **value,
            "candidate_ids": tuple(value["candidate_ids"]),
        }
    )


def _execute(service: GateRegistryService, command: dict[str, Any]) -> dict[str, Any]:
    operation = command.get("operation")
    common = {
        "actor": command.get("actor"),
        "idempotency_key": command.get("idempotency_key"),
        "recorded_at": command.get("recorded_at"),
    }
    if operation == "IMPORT":
        if set(command) != {"operation", "identity", *common}:
            raise RegistryError("IMPORT command fields differ")
        return service.import_case(_identity(command["identity"]), **common)
    if operation == "ADVANCE":
        if set(command) != {
            "operation",
            "case_id",
            "event_type",
            "payload",
            "expected_event_seq",
            *common,
        }:
            raise RegistryError("ADVANCE command fields differ")
        return service.advance(
            command["case_id"],
            command["event_type"],
            command["payload"],
            expected_event_seq=int(command["expected_event_seq"]),
            **common,
        )
    raise RegistryError("command operation must be IMPORT or ADVANCE")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    subparsers = parser.add_subparsers(dest="action", required=True)
    execute = subparsers.add_parser("execute")
    execute.add_argument("--command", type=Path, required=True)
    subparsers.add_parser("verify")
    publish = subparsers.add_parser("publish-outbox")
    publish.add_argument("--ledger", type=Path, required=True)
    publish.add_argument("--published-at", required=True)
    args = parser.parse_args(argv)
    try:
        store = GateRegistryStore(args.database)
        if args.action == "execute":
            result = _execute(GateRegistryService(store), _json_file(args.command))
        elif args.action == "verify":
            with store.read() as connection:
                verify_registry_integrity(connection)
                result = {"status": "PASS", "case_count": connection.execute(
                    "SELECT count(*) FROM gate_cases"
                ).fetchone()[0]}
        else:
            result = {
                "status": "PASS",
                "published_count": publish_pending(
                    store, args.ledger, published_at=args.published_at
                ),
            }
    except (OSError, RegistryError, TypeError, ValueError, json.JSONDecodeError) as error:
        print(canonical_json({"status": "FAIL", "error_class": type(error).__name__, "message": str(error)}))
        return 2
    print(canonical_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
