"""Create an M7 lineage approval from exact scope and live proposal proof."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from shaiwei.research_control.authority import AuthorityError, load_authority
from shaiwei.research_control.service import ControlError, ProposalService
from shaiwei.research_control.storage import SQLiteStore, StorageError
from shaiwei.research_gates.m7_moneyflow.contract import canonical_json, sha256_file, sha256_json
from shaiwei.research_gates.m7_moneyflow_lineage.contract import (
    ACTION,
    LineageError,
    LineageInputManifest,
    LineageProtocol,
)
from shaiwei.research_gates.m7_moneyflow_lineage.release import (
    APPROVER_SHA256,
    LineageRelease,
)


def _project_file(root: Path, relative: str) -> Path:
    path = root / relative
    if path.is_symlink():
        raise LineageError("lineage proposal database cannot be a symlink")
    try:
        resolved = path.resolve(strict=True)
        resolved.relative_to(root.resolve(strict=True))
    except (FileNotFoundError, ValueError) as exc:
        raise LineageError("lineage proposal database is outside the project") from exc
    if not resolved.is_file():
        raise LineageError("lineage proposal database is not a regular file")
    return resolved


def _live_proposal(
    root: Path,
    protocol: LineageProtocol,
    release: LineageRelease,
) -> dict[str, Any]:
    proposal = release.scope["source_proposal"]
    relative = str(proposal["proposal_database_relative_path"])
    database = _project_file(root, relative)
    export = protocol.proposal_export
    actor_sha256 = str(export["canonical_proposal"]["created_by_actor_sha256"])
    service = ProposalService(load_authority(root), SQLiteStore(database))
    live = service.get(str(proposal["proposal_id"]), actor_sha256)
    events = live.get("events") or []
    if not events:
        raise LineageError("lineage live proposal lacks event proof")
    head = events[-1]
    if (
        live.get("current_state") != proposal["required_state_at_approval"]
        or live.get("current_event_seq") != proposal["required_event_seq_at_approval"]
        or live.get("proposal_request_sha256") != proposal["proposal_request_sha256"]
        or sha256_json(live.get("canonical_proposal")) != proposal["canonical_proposal_sha256"]
        or head.get("event_seq") != proposal["required_event_seq_at_approval"]
        or head.get("event_sha256") != proposal["proposal_head_event_sha256"]
    ):
        raise LineageError("lineage live proposal state, sequence, or head differs")
    return {
        "proposal_state": live["current_state"],
        "proposal_event_seq": live["current_event_seq"],
        "proposal_head_event_sha256": head["event_sha256"],
        "proposal_database_relative_path": relative,
    }


def build_approval_document(
    release: LineageRelease,
    live: dict[str, Any],
    *,
    approved_at: str,
    observed_now: datetime,
) -> dict[str, Any]:
    proposal = release.scope["source_proposal"]
    approved = datetime.fromisoformat(approved_at)
    expires = datetime.fromisoformat(str(proposal["expires_at"]))
    now = observed_now.astimezone(timezone.utc)
    if approved.tzinfo is None or abs((approved.astimezone(timezone.utc) - now).total_seconds()) > 300:
        raise LineageError("lineage approval timestamp is not current")
    if approved >= expires or now >= expires:
        raise LineageError("lineage proposal expired before approval")
    return {
        "schema_version": "m7-moneyflow-gap-lineage-approval-v1",
        "action": ACTION,
        "release_scope_sha256": release.sha256,
        "proposal_id": proposal["proposal_id"],
        **live,
        "proposal_integrity_verified": True,
        "approved_at": approved_at,
        "approval_actor_sha256": APPROVER_SHA256,
        "execution_authorized": True,
    }


def _write_once(path: Path, document: dict[str, Any]) -> str:
    payload = (canonical_json(document) + "\n").encode()
    if path.exists():
        if path.read_bytes() != payload:
            raise LineageError("existing lineage approval differs")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        with temporary.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    return sha256_file(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--input-manifest", type=Path, required=True)
    parser.add_argument("--release-scope", type=Path, required=True)
    parser.add_argument("--action", required=True)
    parser.add_argument("--release-scope-sha256", required=True)
    parser.add_argument("--approved-at", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        root = args.project_root.resolve(strict=True)
        protocol = LineageProtocol.load(args.protocol, project_root=root)
        manifest = LineageInputManifest.load(args.input_manifest, protocol)
        release = LineageRelease.load(args.release_scope, protocol, manifest)
        if args.action != ACTION or args.release_scope_sha256 != release.sha256:
            raise LineageError("lineage user approval does not bind exact action and scope")
        if sha256_file(Path(__file__)) != release.scope["implementation"]["approval_builder_sha256"]:
            raise LineageError("lineage approval builder differs from release")
        document = build_approval_document(
            release,
            _live_proposal(root, protocol, release),
            approved_at=args.approved_at,
            observed_now=datetime.now(timezone.utc),
        )
        physical = _write_once(args.output, document)
    except (
        AuthorityError,
        ControlError,
        StorageError,
        LineageError,
        OSError,
        TypeError,
        ValueError,
        json.JSONDecodeError,
    ) as error:
        print(canonical_json({"status": "FAIL", "error_class": type(error).__name__, "message": str(error)}))
        return 2
    print(
        canonical_json(
            {
                "status": "PASS",
                "approval_sha256": sha256_json(document),
                "approval_physical_sha256": physical,
                "proposal_integrity_verified": True,
                "release_scope_sha256": release.sha256,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
