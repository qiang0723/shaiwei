"""Offline evaluator with an internal exact replay and aggregate-only output."""

from __future__ import annotations

import re
from typing import Any

from shaiwei.research_gates.m7_moneyflow.contract import canonical_json, sha256_json

from .compute import compute_recovery_core
from .contract import RecoveryError, RecoveryProtocol
from .inputs import RecoveryInputs


CODE_RE = re.compile(r"[0-9]{6}\.(?:SH|SZ|BJ)")


def evaluation_run_id(
    protocol: RecoveryProtocol,
    *,
    release_scope_sha256: str,
    target_plan_manifest_sha256: str,
    batch_manifest_sha256: str,
) -> str:
    return sha256_json(
        {
            "protocol_sha256": protocol.sha256,
            "release_scope_sha256": release_scope_sha256,
            "target_plan_manifest_sha256": target_plan_manifest_sha256,
            "batch_manifest_sha256": batch_manifest_sha256,
        }
    )


def evaluate_recovery(
    protocol: RecoveryProtocol,
    inputs: RecoveryInputs,
    *,
    release_scope_sha256: str,
    target_plan_manifest_sha256: str,
    batch_manifest_sha256: str,
) -> dict[str, Any]:
    first = compute_recovery_core(protocol, inputs)
    replay = compute_recovery_core(protocol, inputs)
    if first != replay:
        raise RecoveryError("recovery evaluator internal replay differs")
    core_sha = sha256_json(first)
    identity = {
        "protocol_sha256": protocol.sha256,
        "release_scope_sha256": release_scope_sha256,
        "target_plan_manifest_sha256": target_plan_manifest_sha256,
        "batch_manifest_sha256": batch_manifest_sha256,
    }
    report = {
        "schema_version": "m7-moneyflow-recovery-evaluation-v1",
        "run_id": evaluation_run_id(
            protocol,
            release_scope_sha256=release_scope_sha256,
            target_plan_manifest_sha256=target_plan_manifest_sha256,
            batch_manifest_sha256=batch_manifest_sha256,
        ),
        **identity,
        "core_sha256": core_sha,
        "execution_kind": "OFFLINE_RECOVERY_EVALUATOR",
        "internal_replay": {
            "status": "PASS",
            "first_pass_core_sha256": core_sha,
            "replay_core_sha256": core_sha,
        },
        **first,
        "provider_call_count": 0,
        "candidate_or_effect_read": False,
        "production_authorization": "none",
    }
    if CODE_RE.search(canonical_json(report)):
        raise RecoveryError("recovery evaluator report leaks a security code")
    return report
