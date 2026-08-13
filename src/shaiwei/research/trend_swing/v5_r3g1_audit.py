"""Independent artifact and result-firewall audit for TS-v5-R3G-1."""

from __future__ import annotations

import json
from typing import Any

import pyarrow.parquet as pq

from shaiwei.research.provider_contract import D1ControlError
from shaiwei.research.trend_swing.contract import sha256_file, write_once_json
from shaiwei.research.trend_swing.v5_r3g1_contract import (
    AUDIT_PATH,
    EVENT_PATH,
    PROFILE_PATH,
    R3G1Scope,
    validate_bound_inputs,
)


FORBIDDEN = {
    "return_after_entry", "pnl", "win_rate", "excess_return", "mae", "mfe",
    "sharpe", "drawdown", "alpha158_value", "alpha158_rank", "benchmark_value",
}


def _keys(value: Any) -> set[str]:
    result: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            result.add(str(key).lower())
            result.update(_keys(child))
    elif isinstance(value, list):
        for child in value:
            result.update(_keys(child))
    return result


def audit_once() -> dict[str, Any]:
    if AUDIT_PATH.exists():
        raise D1ControlError("TS-v5-R3G-1 audit already exists; rerun is forbidden")
    scope = R3G1Scope.load()
    validate_bound_inputs(scope)
    report = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    schema = set(pq.read_schema(EVENT_PATH).names)
    profiles = report["mechanism_profiles"]
    selected = [point for item in profiles for point in item["selected_points"]]
    checks = {
        "scope_identity_matches": report["scope_sha256"] == scope.sha256,
        "role_boundary_matches": report["role_boundary_addendum_sha256"] == scope.addendum_sha256,
        "six_mechanisms_reported": len(profiles) == 6,
        "effective_grid_total_is_431": sum(x["effective_grid_point_count"] for x in profiles) == 431,
        "at_most_eighteen_points_selected": len(selected) <= 18,
        "all_selected_points_passed_discovery": all(x["discovery_pass"] for x in selected),
        "partial_2026_never_affects_verdict": report["chronological_roles"]["current_partial_year_monitor"]["affects_verdict"] is False,
        "event_artifact_hash_matches": report["machine_artifacts"]["event_intermediate"]["sha256"] == sha256_file(EVENT_PATH),
        "event_artifact_rows_match": report["machine_artifacts"]["event_intermediate"]["row_count"] == pq.read_metadata(EVENT_PATH).num_rows,
        "event_schema_has_no_effect_fields": not (schema & FORBIDDEN),
        "report_has_no_effect_fields": not (_keys(report) & FORBIDDEN),
        "strategy_effect_not_evaluated": report["strategy_effective"] == "NOT_EVALUATED",
        "zero_effect_attempts": report["authority"]["strategy_effect_attempt_count"] == 0,
        "zero_external_calls_and_secret_reads": report["authority"]["external_api_calls"] == 0 and report["authority"]["secret_read"] is False,
        "production_authorization_none": report["production_authorization"] == "none",
    }
    if not all(checks.values()):
        raise D1ControlError(f"TS-v5-R3G-1 independent audit failed: {checks}")
    audit = {
        "schema_version": "ts-v5-r3g1-independent-audit-v1",
        "profile_sha256": sha256_file(PROFILE_PATH),
        "event_sha256": sha256_file(EVENT_PATH),
        "checks": checks,
        "verdict": "PASS",
    }
    write_once_json(AUDIT_PATH, audit)
    return audit
