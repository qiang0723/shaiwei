"""Independent DuckDB-backed audit of an offline recovery evaluation."""

from __future__ import annotations

from typing import Any

from shaiwei.research_gates.m7_moneyflow.contract import sha256_json

from .audit_compute import recompute_audit_vector
from .contract import RecoveryError, RecoveryProtocol
from .inputs import RecoveryInputs


def audit_evaluation(
    protocol: RecoveryProtocol,
    inputs: RecoveryInputs,
    report: dict[str, Any],
) -> dict[str, Any]:
    vector = recompute_audit_vector(protocol, inputs)
    if report.get("audit_vector") != vector:
        raise RecoveryError("recovery independent audit vector differs")
    if report.get("core_sha256") != sha256_json(
        {
            key: report[key]
            for key in (
                "dataset_and_grain",
                "request_plan",
                "track_a",
                "track_b",
                "segments",
                "audit_vector",
                "gates",
                "authority",
                "verdict",
            )
        }
    ):
        raise RecoveryError("recovery independent audit core identity differs")
    return {
        "schema_version": "m7-moneyflow-recovery-audit-v1",
        "status": "PASS",
        "run_id": report["run_id"],
        "release_scope_sha256": report["release_scope_sha256"],
        "reported_core_sha256": report["core_sha256"],
        "independent_audit_vector_sha256": sha256_json(vector),
        "checked_gate_count": len(report["gates"]),
        "verdict": report["verdict"],
        "provider_call_count": 0,
        "effect_test_count": 0,
        "strategy_effective": "NOT_EVALUATED",
        "production_authorization": "none",
    }
