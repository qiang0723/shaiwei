"""One-shot result-blind recent-density profile for TS-v5-R3G-1."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

from shaiwei.config import PROJECT_ROOT
from shaiwei.research.provider_contract import D1ControlError
from shaiwei.research.trend_swing.contract import canonical_sha256, sha256_file, write_once_json
from shaiwei.research.trend_swing.r4_contract import load_r3_manifest
from shaiwei.research.trend_swing.recovery_market import prepare_market_and_sector
from shaiwei.research.trend_swing.recovery_store import configure_store, prepare_core_tables
from shaiwei.research.trend_swing.v5_r3g1_contract import (
    AUDIT_PATH,
    EVENT_PATH,
    OUTPUT_ROOT,
    PROFILE_PATH,
    R3G1Scope,
    runtime_code_identity,
    validate_bound_inputs,
)
from shaiwei.research.trend_swing.v5_r3g1_features import prepare_r3g1_features
from shaiwei.research.trend_swing.v5_r3g1_runner import load_role_rows, project_events
from shaiwei.research.trend_swing.v5_r3g1_selection import (
    density_evidence,
    discovery_pass,
    mechanism_parameter_diversity,
    parameter_hash,
    select_anchor,
    select_neighbours,
)
from shaiwei.research.trend_swing.v5_r3g_contract import R3GScope, registered_candidates


def _mechanism_profile(
    rows: tuple[dict[str, Any], ...],
    registered: Any,
    gate: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    points, events = [], []
    for point in registered.grid:
        current = project_events(rows, registered, point, "selectable_discovery")
        evidence = density_evidence(current, (2021, 2022, 2023))
        points.append({
            "point_hash": parameter_hash(point),
            "parameters": dict(sorted(point.items())),
            "discovery": evidence,
            "discovery_pass": discovery_pass(evidence, gate),
        })
        events.extend(current)
    passing = [item for item in points if item["discovery_pass"]]
    mechanism_pass = (
        len(passing) >= gate["mechanism_minimum_density_eligible_points"]
        and mechanism_parameter_diversity(registered, passing)
    )
    selected: list[dict[str, Any]] = []
    if mechanism_pass:
        anchor = select_anchor(passing)
        selected = [anchor, *select_neighbours(registered, anchor, passing)]
    return {
        "candidate_ordinal": registered.ordinal,
        "mechanism": registered.candidate.primary_mechanism.value,
        "effective_grid_point_count": len(points),
        "discovery_passing_point_count": len(passing),
        "mechanism_parameter_diversity_pass": mechanism_pass,
        "selected_points": selected,
        "point_profiles": points,
    }, events


def _later_roles(
    connection: duckdb.DuckDBPyConnection,
    candidates: tuple[Any, ...],
    profiles: list[dict[str, Any]],
    scope: R3G1Scope,
) -> list[dict[str, Any]]:
    all_events: list[dict[str, Any]] = []
    roles = {name: (start, end) for name, start, end in scope.roles}
    for role in ("frozen_stability_holdout", "current_partial_year_monitor"):
        start, end = roles[role]
        rows = load_role_rows(connection, start, end)
        years = (2024, 2025) if role == "frozen_stability_holdout" else (2026,)
        for registered, profile in zip(candidates, profiles, strict=True):
            for selected in profile["selected_points"]:
                events = project_events(rows, registered, selected["parameters"], role)
                selected[role] = density_evidence(events, years)
                if role == "frozen_stability_holdout":
                    evidence = selected[role]
                    selected["holdout_pass"] = (
                        min(evidence["legal_event_count_by_calendar_year"].values(), default=0)
                        >= scope.document["density_gate"]["holdout_selected_point_minimum_events_each_calendar_year"]
                        and evidence["distinct_signal_day_count"]
                        >= scope.document["density_gate"]["holdout_selected_point_minimum_distinct_signal_days"]
                    )
                all_events.extend(events)
    return all_events


def _write_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    schema = pa.schema([
        ("role", pa.string()), ("candidate_ordinal", pa.int64()), ("mechanism", pa.string()),
        ("point_hash", pa.string()), ("ts_code", pa.string()), ("signal_date", pa.string()),
        ("next_open_date", pa.string()), ("event_status", pa.string()),
    ])
    table = pa.Table.from_pylist(sorted(events, key=lambda x: (x["role"], x["candidate_ordinal"], x["point_hash"], x["signal_date"], x["ts_code"])), schema=schema)
    pq.write_table(table, EVENT_PATH, compression="zstd")
    return {"path": EVENT_PATH.relative_to(PROJECT_ROOT).as_posix(), "row_count": table.num_rows, "sha256": sha256_file(EVENT_PATH), "gitignored": True, "contains_post_entry_outcome": False}


def run_profile_once() -> dict[str, Any]:
    if any(path.exists() for path in (EVENT_PATH, PROFILE_PATH, AUDIT_PATH)):
        raise D1ControlError("TS-v5-R3G-1 output exists; same-scope rerun is forbidden")
    scope = R3G1Scope.load()
    validate_bound_inputs(scope)
    candidates = registered_candidates(R3GScope.load())
    manifest = load_r3_manifest(PROJECT_ROOT / scope.document["frozen_inputs"]["r3_manifest_path"])
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    connection = duckdb.connect(":memory:")
    try:
        configure_store(connection, OUTPUT_ROOT / "duckdb-tmp")
        context = scope.document["frozen_inputs"]["source_context"]
        prepare_core_tables(connection, manifest, start_date=str(context["start"]), end_date=str(context["end"]))
        prepare_market_and_sector(connection)
        prepare_r3g1_features(connection)
        discovery = scope.document["chronological_roles"]["selectable_discovery"]
        discovery_rows = load_role_rows(connection, str(discovery["start"]), str(discovery["end"]))
        profiles, discovery_events = [], []
        for registered in candidates:
            profile, events = _mechanism_profile(discovery_rows, registered, scope.document["density_gate"])
            profiles.append(profile)
            discovery_events.extend(events)
        later_events = _later_roles(connection, candidates, profiles, scope)
    finally:
        connection.close()
    events = discovery_events + later_events
    artifacts = {"event_intermediate": _write_events(events)}
    passing = [
        item["mechanism"] for item in profiles
        if len(item["selected_points"]) == 3
        and all(x.get("holdout_pass", False) for x in item["selected_points"])
    ]
    verdict = "GO_R3G_EFFECT_SCOPE_PROPOSAL_ONLY" if len(passing) == 6 else ("PARTIAL_GO_DENSE_MECHANISMS_ONLY" if passing else "STOP_NO_RECENT_DENSE_MECHANISM")
    report = {
        "schema_version": "ts-v5-r3g1-recent-density-recovery-profile-v2",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope_sha256": scope.sha256,
        "role_boundary_addendum_sha256": scope.addendum_sha256,
        "execution_clock_correction_sha256": "5aa7f0b1385a3bab64f30f63bac812c56fdc8eb2b3268065b357894f7872710b",
        "execution_projection_recovery_sha256": scope.recovery_sha256,
        "parent_invalidation": {
            "authority_status": scope.recovery["frozen_parent"]["authority_status"],
            "profile_sha256": scope.recovery["frozen_parent"]["profile_sha256"],
            "event_sha256": scope.recovery["frozen_parent"]["event_sha256"],
            "audit_sha256": scope.recovery["frozen_parent"]["audit_sha256"],
            "parent_artifacts_rewritten": False,
        },
        "release_identity": runtime_code_identity(),
        "chronological_roles": scope.document["chronological_roles"],
        "mechanism_profiles": profiles,
        "passing_mechanisms": passing,
        "machine_artifacts": artifacts,
        "authority": {"post_entry_outcome_read": False, "alpha158_value_or_rank_read": False, "benchmark_value_read": False, "external_api_calls": 0, "secret_read": False, "strategy_effect_attempt_count": 0},
        "strategy_effective": "NOT_EVALUATED", "production_authorization": "none", "verdict": verdict,
    }
    report["canonical_payload_sha256"] = canonical_sha256(report)
    write_once_json(PROFILE_PATH, report)
    return report
