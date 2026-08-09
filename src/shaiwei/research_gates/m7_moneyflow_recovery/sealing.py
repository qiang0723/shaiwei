"""Canonical write-once sealing for recovery evaluator and auditor evidence."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from shaiwei.research_gates.m7_moneyflow.contract import canonical_json

from .contract import RecoveryError


ROLE_NAMES = frozenset({"evaluator", "auditor", "target_projector", "target_auditor"})


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def write_canonical_once(path: Path, document: dict[str, Any]) -> str:
    payload = (canonical_json(document) + "\n").encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as error:
        raise RecoveryError("recovery evidence path was already consumed") from error
    return sha256_file(path)


def read_canonical(path: Path) -> dict[str, Any]:
    serialized = path.read_text(encoding="utf-8")
    document = json.loads(serialized)
    if not isinstance(document, dict) or serialized != canonical_json(document) + "\n":
        raise RecoveryError("recovery evidence is not a canonical object")
    return document


def claim_role_once(root: Path, *, role: str, release_scope_sha256: str, run_id: str) -> str:
    if role not in ROLE_NAMES:
        raise RecoveryError("recovery evidence role differs")
    document = {
        "schema_version": "m7-moneyflow-recovery-role-claim-v1",
        "role": role,
        "release_scope_sha256": release_scope_sha256,
        "run_id": run_id,
        "same_role_retry_authorized": False,
        "production_authorization": "none",
    }
    return write_canonical_once(root / f"{run_id}.{role}.json", document)
