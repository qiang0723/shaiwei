"""Atomic pre-read consumption for future one-shot M7 roles."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable, TypeVar

from .contract import M7GateError, canonical_json, require_sha256, sha256_json


T = TypeVar("T")
ROLES = frozenset({"runner", "auditor"})
IDENTITY_FIELDS = {
    "protocol_sha256",
    "release_scope_sha256",
    "approval_sha256",
    "role",
    "run_id",
}


def _claim_document(identity: dict[str, Any]) -> dict[str, Any]:
    if set(identity) != IDENTITY_FIELDS:
        raise M7GateError("M7 pre-read consumption identity fields differ")
    role = str(identity["role"])
    if role not in ROLES:
        raise M7GateError("M7 pre-read consumption role differs")
    document = {
        "schema_version": "m7-pre-read-consumption-v1",
        "protocol_sha256": require_sha256(identity["protocol_sha256"], "protocol SHA"),
        "release_scope_sha256": require_sha256(
            identity["release_scope_sha256"], "release scope SHA"
        ),
        "approval_sha256": require_sha256(identity["approval_sha256"], "approval SHA"),
        "role": role,
        "run_id": require_sha256(identity["run_id"], "run ID"),
        "same_identity_retry_authorized": False,
        "semantic_input_read_authorized_after_claim": True,
        "production_authorization": "none",
    }
    return {**document, "claim_sha256": sha256_json(document)}


def claim_before_semantic_read(
    claim_root: Path,
    identity: dict[str, Any],
) -> dict[str, Any]:
    """Consume one role identity atomically before a caller invokes its loader."""

    document = _claim_document(identity)
    claim_root.mkdir(parents=True, exist_ok=True)
    target = claim_root / f"{document['run_id']}.{document['role']}.json"
    payload = (canonical_json(document) + "\n").encode("utf-8")
    try:
        with target.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as error:
        raise M7GateError(
            "M7 role identity was already consumed before semantic input read"
        ) from error
    directory_fd = os.open(claim_root, os.O_RDONLY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)
    return document


def execute_after_pre_read_claim(
    claim_root: Path,
    identity: dict[str, Any],
    semantic_loader: Callable[[], T],
) -> tuple[dict[str, Any], T]:
    """Claim first, then invoke exactly one semantic loader."""

    claim = claim_before_semantic_read(claim_root, identity)
    return claim, semantic_loader()
