"""One-shot result-blind TS-v6 entry-quality profile."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

from shaiwei.config import PROJECT_ROOT
from shaiwei.research.provider_contract import D1ControlError
from shaiwei.research.trend_swing.contract import sha256_file
from shaiwei.research.trend_swing.r4_contract import load_r3_manifest
from shaiwei.research.trend_swing.recovery_market import prepare_market_and_sector
from shaiwei.research.trend_swing.recovery_store import configure_store, prepare_core_tables
from shaiwei.research.trend_swing.v6.contract import (
    ADDENDUM_SHA256,
    AUDIT_PATH,
    CANDIDATE_EVENT_PATH,
    MANIFEST_PATH,
    MARKER_PATH,
    OBSERVATION_PATH,
    OUTPUT_ROOT,
    PROFILE_PATH,
    PROTOCOL_SHA256,
    V6Scope,
    runtime_identity,
    validate_bound_inputs,
)
from shaiwei.research.trend_swing.v6.engine import (
    AXES,
    canonical_json,
    canonical_sha256,
    density,
    derive_levels,
    design_points,
    development_eligible,
    filter_events,
    native,
    select_point,
)
from shaiwei.research.trend_swing.v6.observations import (
    frozen_parent_keys,
    load_role_rows,
    parent_candidate,
    prepare_v6_stream,
    project_parent_observations,
    reconcile_parent_keys,
)


def _write_json_once(path: Path, document: Mapping[str, Any]) -> str:
    if path.exists():
        raise D1ControlError(f"TS-v6 write-once output already exists: {path.name}")
    payload = canonical_json(document) + b"\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return hashlib.sha256(payload).hexdigest()


def _pre_marker_receipts() -> list[dict[str, Any]]:
    receipts = []
    for path in sorted(OUTPUT_ROOT.glob("pre_marker_failure_*.json")):
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise D1ControlError("TS-v6 pre-marker failure receipt is invalid") from exc
        if (
            not isinstance(document, dict)
            or document.get("real_feature_read") is not False
            or document.get("semantic_read_marker_exists") is not False
            or document.get("strategy_or_density_attempt_increment") != 0
        ):
            raise D1ControlError("TS-v6 pre-marker failure receipt authority differs")
        receipts.append({
            "path": path.relative_to(PROJECT_ROOT).as_posix(),
            "sha256": sha256_file(path),
            "failure_class": document.get("failure_class"),
        })
    if len(receipts) > 2:
        raise D1ControlError("TS-v6 pre-marker technical repair budget exceeded")
    return receipts


def _write_observations(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if OBSERVATION_PATH.exists():
        raise D1ControlError("TS-v6 observation output already exists")
    schema = pa.schema([
        ("role", pa.string()), ("point_hash", pa.string()), ("ts_code", pa.string()),
        ("signal_date", pa.string()), ("next_open_date", pa.string()),
        ("pullback_amount_ratio", pa.float64()), ("recovery_close_location", pa.float64()),
        ("pre_entry_10d_return_percentile", pa.float64()),
    ])
    ordered = sorted(rows, key=lambda row: (
        str(row["role"]), str(row["ts_code"]), str(row["signal_date"]), str(row["next_open_date"])
    ))
    table = pa.Table.from_pylist(ordered, schema=schema)
    pq.write_table(table, OBSERVATION_PATH, compression="zstd")
    return {
        "path": OBSERVATION_PATH.relative_to(PROJECT_ROOT).as_posix(),
        "row_count": table.num_rows,
        "sha256": sha256_file(OBSERVATION_PATH),
        "gitignored": True,
        "contains_post_entry_outcome": False,
    }


def _write_candidate_events(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if CANDIDATE_EVENT_PATH.exists():
        raise D1ControlError("TS-v6 candidate-event output already exists")
    schema = pa.schema([
        ("role", pa.string()), ("point_hash", pa.string()), ("ts_code", pa.string()),
        ("signal_date", pa.string()), ("next_open_date", pa.string()),
    ])
    ordered = sorted(rows, key=lambda row: (
        str(row["role"]), str(row["point_hash"]), str(row["signal_date"]), str(row["ts_code"])
    ))
    table = pa.Table.from_pylist(ordered, schema=schema)
    pq.write_table(table, CANDIDATE_EVENT_PATH, compression="zstd")
    return {
        "path": CANDIDATE_EVENT_PATH.relative_to(PROJECT_ROOT).as_posix(),
        "row_count": table.num_rows,
        "sha256": sha256_file(CANDIDATE_EVENT_PATH),
        "gitignored": True,
        "contains_post_entry_outcome": False,
    }


def build_profile(
    observations: Sequence[Mapping[str, Any]], scope: V6Scope, identity: Mapping[str, str]
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    development = [row for row in observations if row["role"] == "selectable_discovery"]
    holdout = [row for row in observations if row["role"] == "frozen_stability_holdout"]
    if not development or not holdout:
        raise D1ControlError("TS-v6 parent observations are missing a frozen role")
    levels = derive_levels(development)
    gate_source = scope.document["density_and_distinctness_gate"]
    development_gate = dict(gate_source["development"])
    development_gate.update(
        retention_minimum=gate_source["parent_event_retention_ratio"]["minimum"],
        retention_maximum=gate_source["parent_event_retention_ratio"]["maximum"],
    )
    profiles, candidate_events = [], []
    for point in design_points(levels):
        accepted, reasons, axis_rejected = filter_events(development, point["parameters"])
        evidence = density(accepted, (2021, 2022, 2023))
        eligible, retention = development_eligible(
            evidence, len(development), axis_rejected, development_gate
        )
        profile = {
            **point,
            "development": evidence,
            "development_pass": eligible,
            "parent_event_retention_ratio": round(retention, 12),
            "first_rejection_reason_counts": reasons,
            "per_axis_rejected_parent_event_counts": axis_rejected,
        }
        profiles.append(profile)
        candidate_events.extend({
            "role": "selectable_discovery",
            "point_hash": point["point_hash"],
            "ts_code": row["ts_code"],
            "signal_date": row["signal_date"],
            "next_open_date": row["next_open_date"],
        } for row in accepted)
    selected = select_point(profiles)
    holdout_evidence = None
    holdout_pass = False
    if selected is not None:
        accepted, _, _ = filter_events(holdout, selected["parameters"])
        holdout_evidence = density(accepted, (2024, 2025))
        gate = gate_source["conditional_density_only_holdout"]
        holdout_pass = (
            holdout_evidence["distinct_signal_day_count"] >= gate["minimum_distinct_signal_days"]
            and min(holdout_evidence["legal_event_count_by_calendar_year"].values(), default=0)
            >= gate["minimum_events_each_calendar_year"]
        )
        candidate_events.extend({
            "role": "frozen_stability_holdout",
            "point_hash": selected["point_hash"],
            "ts_code": row["ts_code"],
            "signal_date": row["signal_date"],
            "next_open_date": row["next_open_date"],
        } for row in accepted)
    verdict = (
        "GO_TS_V6_ENTRY_QUALITY_EFFECT_SCOPE_PROPOSAL_ONLY"
        if selected is not None and holdout_pass
        else "STOP_TS_V6_ENTRY_QUALITY_NO_DENSE_NONDUPLICATE_POINT"
    )
    report = {
        "schema_version": "ts-v6-entry-quality-preflight-profile-v1",
        "protocol_sha256": PROTOCOL_SHA256,
        "operationalization_addendum_sha256": ADDENDUM_SHA256,
        "release_identity": dict(identity),
        "parent_primary_point_hash": scope.document["result_informed_parent"][
            "parent_primary_point_hash"
        ],
        "parent_effect_verdict_retained": scope.document["result_informed_parent"][
            "parent_effect_verdict"
        ],
        "derived_parameter_levels": {
            axis: [format(value, "f") for value in levels[axis]] for axis in AXES
        },
        "parent_observation_counts": {
            "selectable_discovery": len(development),
            "frozen_stability_holdout": len(holdout),
        },
        "point_profiles": profiles,
        "selected_point": None if selected is None else {
            "point_hash": selected["point_hash"],
            "level_indices": selected["level_indices"],
            "parameters": selected["parameters"],
        },
        "conditional_density_only_holdout": holdout_evidence,
        "conditional_density_only_holdout_pass": holdout_pass,
        "authority": {
            "post_entry_outcome_read": False,
            "holdout_outcome_read": False,
            "current_partial_year_read": False,
            "alpha158_value_or_rank_read": False,
            "benchmark_value_read": False,
            "external_api_calls": 0,
            "secret_read": False,
            "strategy_effect_attempt_increment": 0,
        },
        "strategy_effective": "NOT_EVALUATED",
        "production_authorization": "none",
        "verdict": verdict,
    }
    report["canonical_payload_sha256"] = canonical_sha256(report)
    return native(report), candidate_events


def _real_observations(scope: V6Scope) -> list[dict[str, Any]]:
    manifest_path = PROJECT_ROOT / scope.document["frozen_inputs"]["r3_manifest_path"]
    manifest = load_r3_manifest(manifest_path)
    registered = parent_candidate()
    connection = duckdb.connect(":memory:")
    try:
        configure_store(connection, OUTPUT_ROOT / "duckdb-tmp")
        context = scope.document["frozen_inputs"]["source_context"]
        holdout_end = scope.document["chronological_roles"][
            "conditional_density_only_holdout"
        ]["end"]
        prepare_core_tables(
            connection, manifest, start_date=str(context["start"]), end_date=str(holdout_end)
        )
        prepare_market_and_sector(connection)
        prepare_v6_stream(connection)
        observations = []
        for role, start, end in scope.roles:
            observations.extend(
                project_parent_observations(load_role_rows(connection, start, end), registered, role)
            )
    finally:
        connection.close()
    reconcile_parent_keys(observations, frozen_parent_keys(scope))
    if any(str(row["signal_date"]) >= "20260101" for row in observations):
        raise D1ControlError("TS-v6 current partial-year data entered the preflight")
    return observations


def run_profile_once() -> dict[str, Any]:
    outputs = (MARKER_PATH, OBSERVATION_PATH, CANDIDATE_EVENT_PATH, PROFILE_PATH, MANIFEST_PATH, AUDIT_PATH)
    if any(path.exists() for path in outputs):
        raise D1ControlError("TS-v6 output exists; same-scope rerun is forbidden")
    scope = V6Scope.load()
    validate_bound_inputs(scope)
    identity = runtime_identity()
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    receipts = _pre_marker_receipts()
    marker = {
        "schema_version": "ts-v6-semantic-read-marker-v1",
        "semantic_read_started": True,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "protocol_sha256": scope.sha256,
        "operationalization_addendum_sha256": scope.addendum_sha256,
        "release_identity": identity,
        "pre_marker_technical_failure_receipts": receipts,
    }
    marker_sha = _write_json_once(MARKER_PATH, marker)
    observations = _real_observations(scope)
    first, candidate_events = build_profile(observations, scope, identity)
    second, replay_events = build_profile(observations, scope, identity)
    if canonical_json(first) != canonical_json(second) or canonical_json(candidate_events) != canonical_json(replay_events):
        raise D1ControlError("TS-v6 internal deterministic replay differs")
    artifacts = {
        "semantic_read_marker": {
            "path": MARKER_PATH.relative_to(PROJECT_ROOT).as_posix(), "sha256": marker_sha
        },
        "parent_observations": _write_observations(observations),
        "candidate_events": _write_candidate_events(candidate_events),
        "pre_marker_failure_receipts": receipts,
    }
    first["machine_artifacts"] = artifacts
    first["internal_deterministic_replay_pass"] = True
    first["pre_marker_technical_failure_count"] = len(receipts)
    first["canonical_payload_sha256"] = canonical_sha256({
        key: value for key, value in first.items() if key != "canonical_payload_sha256"
    })
    profile_sha = _write_json_once(PROFILE_PATH, first)
    manifest = {
        "schema_version": "ts-v6-entry-quality-preflight-manifest-v1",
        "protocol_sha256": scope.sha256,
        "operationalization_addendum_sha256": scope.addendum_sha256,
        "release_identity": identity,
        "artifacts": {**artifacts, "profile": {
            "path": PROFILE_PATH.relative_to(PROJECT_ROOT).as_posix(), "sha256": profile_sha
        }},
        "contains_post_entry_outcome": False,
        "contains_security_identifiers": True,
        "production_authorization": "none",
    }
    _write_json_once(MANIFEST_PATH, manifest)
    return first


def fixture() -> dict[str, Any]:
    observations = []
    for amount in range(1, 7):
        for close in range(1, 7):
            for momentum in range(1, 7):
                index = len(observations)
                observations.append({
                    "role": "selectable_discovery",
                    "ts_code": f"fixture-{index:03d}",
                    "signal_date": f"{2021 + index % 3}0101",
                    "next_open_date": f"{2021 + index % 3}0102",
                    "pullback_amount_ratio": amount / 10,
                    "recovery_close_location": close / 6,
                    "pre_entry_10d_return_percentile": momentum / 6,
                })
    levels = derive_levels(observations)
    points = design_points(levels)
    if len(points) != 9 or len({row["point_hash"] for row in points}) != 9:
        raise D1ControlError("TS-v6 fixture L9 design differs")
    accepted, _, axis_rejected = filter_events(observations, points[0]["parameters"])
    if not accepted or not all(value > 0 for value in axis_rejected.values()):
        raise D1ControlError("TS-v6 fixture filtering differs")
    return {"fixture_pass": True, "design_point_count": 9, "library_scalar_normalization": True}
