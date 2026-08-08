"""Create an M7 approval only from an exact user-authorized scope and live proposal proof."""

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
from shaiwei.research_gates.m7_moneyflow.contract import (
    InputManifest,
    M7GateError,
    M7Protocol,
    canonical_json,
    sha256_file,
    sha256_json,
)
from shaiwei.research_gates.m7_moneyflow.release import ACTION, APPROVER_SHA256, DataReleaseScope


def _project_file(project_root: Path, relative: str) -> Path:
    path = project_root / relative
    if path.is_symlink():
        raise M7GateError("M7 proposal database cannot be a symlink")
    try:
        resolved = path.resolve(strict=True)
        resolved.relative_to(project_root.resolve(strict=True))
    except (FileNotFoundError, ValueError) as exc:
        raise M7GateError("M7 proposal database is missing or outside the project") from exc
    if not resolved.is_file():
        raise M7GateError("M7 proposal database is not a regular file")
    return resolved


def _live_proposal(
    project_root: Path,
    protocol: M7Protocol,
    release: DataReleaseScope,
) -> dict[str, Any]:
    proposal = release.scope["source_proposal"]
    relative = str(proposal["proposal_database_relative_path"])
    database = _project_file(project_root, relative)
    export = json.loads(
        (project_root / protocol.proposal["proposal_export_path"]).read_text(encoding="utf-8")
    )
    actor_sha256 = str(export["canonical_proposal"]["created_by_actor_sha256"])
    authority = load_authority(project_root)
    service = ProposalService(authority, SQLiteStore(database))
    live = service.get(str(proposal["proposal_id"]), actor_sha256)
    events = live.get("events") or []
    if not events:
        raise M7GateError("M7 live proposal has no event proof")
    head = events[-1]
    if (
        live.get("current_state") != proposal["required_state_at_approval"]
        or live.get("current_event_seq") != proposal["required_event_seq_at_approval"]
        or live.get("proposal_request_sha256") != proposal["proposal_request_sha256"]
        or sha256_json(live.get("canonical_proposal")) != proposal["canonical_proposal_sha256"]
        or head.get("event_seq") != proposal["required_event_seq_at_approval"]
        or head.get("event_sha256") != proposal["proposal_head_event_sha256"]
    ):
        raise M7GateError("M7 live proposal state, sequence, or head differs")
    return {
        "proposal_state": live["current_state"],
        "proposal_event_seq": live["current_event_seq"],
        "proposal_head_event_sha256": head["event_sha256"],
        "proposal_database_relative_path": relative,
    }


def build_approval_document(
    release: DataReleaseScope,
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
        raise M7GateError("M7 approval timestamp is not current")
    if approved >= expires or now >= expires:
        raise M7GateError("M7 proposal expired before approval")
    return {
        "schema_version": "m7-moneyflow-data-gate-approval-v1",
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
    payload = (canonical_json(document) + "\n").encode("utf-8")
    if path.exists():
        if path.read_bytes() != payload:
            raise M7GateError("existing M7 approval differs")
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
    parser.add_argument("--build-contract", type=Path, required=True)
    parser.add_argument("--input-manifest", type=Path, required=True)
    parser.add_argument("--release-scope", type=Path, required=True)
    parser.add_argument("--action", required=True)
    parser.add_argument("--release-scope-sha256", required=True)
    parser.add_argument("--approved-at", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        root = args.project_root.resolve(strict=True)
        protocol = M7Protocol.load(args.protocol, build_path=args.build_contract, project_root=root)
        manifest = InputManifest.load(args.input_manifest, protocol)
        release = DataReleaseScope.load(args.release_scope, protocol, manifest)
        if args.action != ACTION or args.release_scope_sha256 != release.sha256:
            raise M7GateError("M7 user approval does not bind the exact action and scope")
        expected_builder = release.scope["implementation"]["approval_builder_sha256"]
        if sha256_file(Path(__file__)) != expected_builder:
            raise M7GateError("M7 approval builder differs from the release")
        live = _live_proposal(root, protocol, release)
        document = build_approval_document(
            release,
            live,
            approved_at=args.approved_at,
            observed_now=datetime.now(timezone.utc),
        )
        physical_sha = _write_once(args.output, document)
    except (
        AuthorityError,
        ControlError,
        StorageError,
        M7GateError,
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
                "approval_physical_sha256": physical_sha,
                "proposal_integrity_verified": True,
                "release_scope_sha256": release.sha256,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
