"""One-shot TS-C trigger qualification profile orchestration."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from pathlib import Path
from typing import Any, Mapping

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

from shaiwei.config import PROJECT_ROOT
from shaiwei.research.trend_swing.contract import sha256_file
from shaiwei.research.trend_swing.r4_contract import load_r3_manifest
from shaiwei.research.trend_swing.v6.engine import canonical_json, canonical_sha256
from shaiwei.research.trend_swing.ts_c.contract import (
    TQCRecovery,
    active_root,
    TQCError,
    TQCScope,
    runtime_identity,
    validate_bound_inputs,
)
from shaiwei.research.trend_swing.ts_c.machine import TRIGGERS, project_events
from shaiwei.research.trend_swing.ts_c.store import load_stream, prepare_tsc_stream


def _write_json_once(path: Path, document: Mapping[str, Any]) -> str:
    if path.exists():
        raise TQCError(f"TS-C write-once output already exists: {path.name}")
    payload = canonical_json(document) + b"\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return hashlib.sha256(payload).hexdigest()


def _relative(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT).as_posix()


def real_events(scope: TQCScope, temporary: Path) -> list[dict[str, Any]]:
    manifest = load_r3_manifest(
        PROJECT_ROOT / scope.document["frozen_inputs"]["raw_market_store"][
            "r3_frozen_input_manifest"
        ]["path"]
    )
    connection = duckdb.connect(":memory:")
    try:
        prepare_tsc_stream(connection, manifest, temporary)
        rows = load_stream(connection)
    finally:
        connection.close()
    events: list[dict[str, Any]] = []
    per_security: dict[str, list[Mapping[str, Any]]] = {}
    for row in rows:
        per_security.setdefault(str(row["ts_code"]), []).append(row)
    for trigger in TRIGGERS:
        for code in sorted(per_security):
            found, _ = project_events(per_security[code], trigger)
            events.extend(found)
    return sorted(events, key=lambda row: (row["trigger_id"], row["ts_code"], row["signal_date"]))


def evaluate_density(events: list[dict[str, Any]], gate: Mapping[str, Any]) -> dict[str, Any]:
    per_trigger: dict[str, Any] = {}
    years = [str(year) for year in range(2019, 2026)]
    for trigger in TRIGGERS:
        selected = [row for row in events if row["trigger_id"] == trigger]
        yearly = {year: 0 for year in years}
        days: set[str] = set()
        for row in selected:
            yearly[row["signal_date"][:4]] += 1
            days.add(row["signal_date"])
        checks = {
            "minimum_confirmed_events": len(selected)
            >= int(gate["per_trigger_minimum_confirmed_events"]),
            "minimum_events_each_calendar_year": min(yearly.values())
            >= int(gate["per_trigger_minimum_events_each_calendar_year"]),
            "minimum_distinct_signal_days": len(days)
            >= int(gate["per_trigger_minimum_distinct_signal_days"]),
            "no_bse": not any(row["ts_code"].endswith(".BJ") for row in selected),
        }
        per_trigger[trigger] = {
            "confirmed_event_count": len(selected),
            "distinct_signal_day_count": len(days),
            "events_by_calendar_year": yearly,
            "checks": checks,
            "qualified": all(checks.values()),
        }
    survivors = [trigger for trigger in TRIGGERS if per_trigger[trigger]["qualified"]]
    return {
        "per_trigger": per_trigger,
        "surviving_triggers": survivors,
        "verdict": "GO_TS_C_TOURNAMENT_PROTOCOL_DRAFT_ONLY" if survivors
        else "STOP_TS_C_NO_DENSE_LEGAL_TRIGGER",
    }


def build_profile(scope: TQCScope, identity: Mapping[str, str], temporary: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    events = real_events(scope, temporary)
    density = evaluate_density(events, scope.document["density_gate"])
    profile = {
        "schema_version": "ts-c-trigger-qualification-profile-v1",
        "protocol_sha256": scope.sha256,
        "release_identity": dict(identity),
        "density": density,
        "authority": {
            "post_entry_outcome_read": False,
            "alpha158_value_or_rank_read": False,
            "external_api_calls": 0,
            "secret_read": False,
            "strategy_effect_attempt_increment": 0,
        },
        "strategy_effective": "NOT_EVALUATED",
        "production_authorization": "none",
        "verdict": density["verdict"],
    }
    return profile, events


def run_profile_once() -> dict[str, Any]:
    scope = TQCScope.load()
    recovery = TQCRecovery.load_if_present()
    root = active_root(recovery)
    if recovery is not None:
        recovery.validate_parent_evidence()
    marker_path = root / "semantic_read_started.json"
    events_path = root / "events.parquet"
    profile_path = root / "profile.json"
    manifest_path = root / "manifest.json"
    audit_path = root / "audit.json"
    if any(path.exists() for path in (marker_path, events_path, profile_path, manifest_path, audit_path)):
        raise TQCError("TS-C output exists; same-scope rerun is forbidden")
    validate_bound_inputs(scope)
    identity = runtime_identity()
    root.mkdir(parents=True, exist_ok=True)
    marker_sha = _write_json_once(marker_path, {
        "schema_version": "ts-c-semantic-read-marker-v1",
        "semantic_read_started": True,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "protocol_sha256": scope.sha256,
        "recovery_scope_sha256": None if recovery is None else recovery.sha256,
        "release_identity": identity,
    })
    first, events = build_profile(scope, identity, root / "duckdb-tmp")
    second, events_replay = build_profile(scope, identity, root / "duckdb-tmp-replay")
    if canonical_json(first) != canonical_json(second) or canonical_json(events) != canonical_json(events_replay):
        raise TQCError("TS-C internal deterministic replay differs")
    schema = pa.schema([
        ("trigger_id", pa.string()), ("ts_code", pa.string()), ("signal_date", pa.string()),
    ])
    table = pa.Table.from_pylist(events, schema=schema)
    pq.write_table(table, events_path, compression="zstd")
    artifacts = {
        "semantic_read_marker": {"path": _relative(marker_path), "sha256": marker_sha},
        "events": {
            "path": _relative(events_path), "row_count": table.num_rows,
            "sha256": sha256_file(events_path), "contains_post_entry_outcome": False,
        },
    }
    first["machine_artifacts"] = artifacts
    first["internal_deterministic_replay_pass"] = True
    first["canonical_payload_sha256"] = canonical_sha256(first)
    profile_sha = _write_json_once(profile_path, first)
    manifest = {
        "schema_version": "ts-c-trigger-qualification-manifest-v1",
        "protocol_sha256": scope.sha256,
        "recovery_scope_sha256": None if recovery is None else recovery.sha256,
        "release_identity": identity,
        "artifacts": {**artifacts, "profile": {"path": _relative(profile_path), "sha256": profile_sha}},
        "contains_outcome": False,
        "contains_security_identifiers": True,
        "production_authorization": "none",
    }
    _write_json_once(manifest_path, manifest)
    return first
