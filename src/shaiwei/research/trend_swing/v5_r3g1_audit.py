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


def _event_key(event: dict[str, Any]) -> tuple[str, int, str]:
    return str(event["role"]), int(event["candidate_ordinal"]), str(event["point_hash"])


def _evidence(events: list[dict[str, Any]], years: tuple[int, ...]) -> dict[str, Any]:
    relevant = [event for event in events if int(str(event["signal_date"])[:4]) in years]
    return {
        "legal_event_count": len(relevant),
        "distinct_signal_day_count": len({str(event["signal_date"]) for event in relevant}),
        "legal_event_count_by_calendar_year": {
            str(year): sum(int(str(event["signal_date"]).startswith(str(year))) for event in relevant)
            for year in years
        },
    }


def _profile_counts_match_events(
    profiles: list[dict[str, Any]], events: list[dict[str, Any]]
) -> bool:
    grouped: dict[tuple[str, int, str], list[dict[str, Any]]] = {}
    for event in events:
        grouped.setdefault(_event_key(event), []).append(event)
    for profile in profiles:
        ordinal = int(profile["candidate_ordinal"])
        for point in profile["point_profiles"]:
            rows = grouped.get(("selectable_discovery", ordinal, point["point_hash"]), [])
            if point["discovery"] != _evidence(rows, (2021, 2022, 2023)):
                return False
        for point in profile["selected_points"]:
            for role, years in (
                ("frozen_stability_holdout", (2024, 2025)),
                ("current_partial_year_monitor", (2026,)),
            ):
                rows = grouped.get((role, ordinal, point["point_hash"]), [])
                if point[role] != _evidence(rows, years):
                    return False
    return True


def _events_obey_frozen_roles(events: list[dict[str, Any]], scope: R3G1Scope) -> bool:
    bounds = {name: (start, end) for name, start, end in scope.roles}
    return all(
        event["role"] in bounds
        and bounds[event["role"]][0] <= str(event["signal_date"]) <= bounds[event["role"]][1]
        and str(event["next_open_date"]) > str(event["signal_date"])
        and not str(event["ts_code"]).endswith(".BJ")
        for event in events
    )


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
    event_table = pq.read_table(EVENT_PATH)
    schema = set(event_table.schema.names)
    events = event_table.to_pylist()
    profiles = report["mechanism_profiles"]
    selected = [point for item in profiles for point in item["selected_points"]]
    checks = {
        "scope_identity_matches": report["scope_sha256"] == scope.sha256,
        "role_boundary_matches": report["role_boundary_addendum_sha256"] == scope.addendum_sha256,
        "recovery_identity_matches": report["execution_projection_recovery_sha256"] == scope.recovery_sha256,
        "parent_invalidation_is_explicit": report["parent_invalidation"] == {
            "authority_status": "INVALIDATED_BY_COMMON_EXECUTION_PROJECTION_DEFECT",
            "profile_sha256": scope.recovery["frozen_parent"]["profile_sha256"],
            "event_sha256": scope.recovery["frozen_parent"]["event_sha256"],
            "audit_sha256": scope.recovery["frozen_parent"]["audit_sha256"],
            "parent_artifacts_rewritten": False,
        },
        "six_mechanisms_reported": len(profiles) == 6,
        "effective_grid_total_is_431": sum(x["effective_grid_point_count"] for x in profiles) == 431,
        "at_most_eighteen_points_selected": len(selected) <= 18,
        "all_selected_points_passed_discovery": all(x["discovery_pass"] for x in selected),
        "partial_2026_never_affects_verdict": report["chronological_roles"]["current_partial_year_monitor"]["affects_verdict"] is False,
        "event_artifact_hash_matches": report["machine_artifacts"]["event_intermediate"]["sha256"] == sha256_file(EVENT_PATH),
        "event_artifact_rows_match": report["machine_artifacts"]["event_intermediate"]["row_count"] == pq.read_metadata(EVENT_PATH).num_rows,
        "event_rows_are_unique": len(events) == len({
            (
                event["role"], event["candidate_ordinal"], event["point_hash"],
                event["ts_code"], event["signal_date"], event["next_open_date"],
            )
            for event in events
        }),
        "events_obey_frozen_roles_and_exclude_bj": _events_obey_frozen_roles(events, scope),
        "profile_density_independently_matches_events": _profile_counts_match_events(profiles, events),
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
        "schema_version": "ts-v5-r3g1-recovery-independent-audit-v2",
        "profile_sha256": sha256_file(PROFILE_PATH),
        "event_sha256": sha256_file(EVENT_PATH),
        "checks": checks,
        "verdict": "PASS",
    }
    write_once_json(AUDIT_PATH, audit)
    return audit
