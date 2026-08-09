"""Role claims layered over the frozen recovery evidence sealing primitives."""

from __future__ import annotations

from pathlib import Path

from shaiwei.research_gates.m7_moneyflow_recovery.contract import RecoveryError
from shaiwei.research_gates.m7_moneyflow_recovery.sealing import (
    read_canonical,
    sha256_file,
    write_canonical_once,
)


ROLE_NAMES = frozenset(
    {"status_collector", "moneyflow_collector", "evaluator", "auditor"}
)


def claim_role_once(
    root: Path,
    *,
    role: str,
    release_scope_sha256: str,
    run_id: str,
) -> str:
    if role not in ROLE_NAMES:
        raise RecoveryError("recovery network role differs")
    document = {
        "schema_version": "m7-moneyflow-network-recovery-role-claim-v1",
        "role": role,
        "release_scope_sha256": release_scope_sha256,
        "run_id": run_id,
        "same_role_retry_authorized": False,
        "production_authorization": "none",
    }
    return write_canonical_once(root / f"{run_id}.{role}.json", document)


__all__ = ["claim_role_once", "read_canonical", "sha256_file", "write_canonical_once"]
