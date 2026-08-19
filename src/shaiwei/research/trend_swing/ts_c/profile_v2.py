"""TS-C v2 profile: density evaluated per permission-ON calendar year."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
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
    TQCError,
    TQC2Scope,
    V2_OUTPUT_ROOT,
    runtime_identity,
    validate_v2_bound_inputs,
)
from shaiwei.research.trend_swing.ts_c.machine import TRIGGERS, project_events
from shaiwei.research.trend_swing.ts_c.store import load_stream, prepare_tsc_stream


def _write_json_once(path: Path, document: Mapping[str, Any]) -> str:
    if path.exists():
        raise TQCError(f"TS-C v2 write-once output already exists: {path.name}")
    payload = canonical_json(document) + b"\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return hashlib.sha256(payload).hexdigest()


def _relative(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT).as_posix()


def permission_on_years(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    """Permission-ON year = index double permission on >=50% of the year's open days."""
    per_year: dict[str, dict[str, int]] = {}
    seen: set[tuple[str, str]] = set()
    for row in rows:
        day = str(row["trade_date"])
        if day in seen:
            continue
        seen.add(day)
        year = day[:4]
        bucket = per_year.setdefault(year, {"open_days": 0, "permission_on_days": 0})
        bucket["open_days"] += 1
        if (
            row.get("index_prev_month_close") is not None
            and row.get("index_prev_sma6") is not None
            and row.get("index_prev2_sma6") is not None
            and float(row["index_prev_month_close"]) > float(row["index_prev_sma6"])
            and float(row["index_prev_sma6"]) > float(row["index_prev2_sma6"])
        ):
            bucket["permission_on_days"] += 1
    on_years = sorted(
        year for year, bucket in per_year.items()
        if bucket["open_days"] > 0 and bucket["permission_on_days"] / bucket["open_days"] >= 0.5
    )
    return {"per_year": per_year, "permission_on_years": on_years}


def evaluate_density_v2(
    events: list[dict[str, Any]], on_years: list[str], gate: Mapping[str, Any]
) -> dict[str, Any]:
    if len(on_years) < 4:
        raise TQCError("TS-C v2 permission-ON years collapsed below four")
    per_trigger: dict[str, Any] = {}
    years = [str(year) for year in range(2019, 2026)]
    for trigger in TRIGGERS:
        selected = [row for row in events if row["trigger_id"] == trigger]
        yearly = {year: 0 for year in years}
        days: set[str] = set()
        for row in selected:
            yearly[row["signal_date"][:4]] += 1
            days.add(row["signal_date"])
        on_yearly = [yearly[year] for year in on_years]
        checks = {
            "minimum_confirmed_events": len(selected)
            >= int(gate["per_trigger_minimum_confirmed_events"]),
            "minimum_events_each_permission_on_year": min(on_yearly, default=0)
            >= int(gate["per_trigger_minimum_events_each_permission_on_calendar_year"]),
            "minimum_distinct_signal_days": len(days)
            >= int(gate["per_trigger_minimum_distinct_signal_days"]),
            "no_bse": not any(row["ts_code"].endswith(".BJ") for row in selected),
        }
        per_trigger[trigger] = {
            "confirmed_event_count": len(selected),
            "distinct_signal_day_count": len(days),
            "events_by_calendar_year": yearly,
            "events_by_permission_on_year": {year: yearly[year] for year in on_years},
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


def real_events_v2(scope: TQC2Scope, temporary: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
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
    permission = permission_on_years(rows)
    events: list[dict[str, Any]] = []
    per_security: dict[str, list[Mapping[str, Any]]] = {}
    for row in rows:
        per_security.setdefault(str(row["ts_code"]), []).append(row)
    for trigger in TRIGGERS:
        for code in sorted(per_security):
            found, _ = project_events(per_security[code], trigger)
            events.extend(found)
    events.sort(key=lambda row: (row["trigger_id"], row["ts_code"], row["signal_date"]))
    return events, permission


def build_profile_v2(
    scope: TQC2Scope, identity: Mapping[str, str], temporary: Path
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    events, permission = real_events_v2(scope, temporary)
    density = evaluate_density_v2(events, permission["permission_on_years"], scope.document["density_gate"])
    profile = {
        "schema_version": "ts-c-trigger-qualification-v2-profile-v1",
        "protocol_sha256": scope.sha256,
        "release_identity": dict(identity),
        "permission_on_year_rule": permission,
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


def run_profile_v2_once() -> dict[str, Any]:
    root = V2_OUTPUT_ROOT
    paths = {
        "marker": root / "semantic_read_started.json",
        "events": root / "events.parquet",
        "profile": root / "profile.json",
        "manifest": root / "manifest.json",
        "audit": root / "audit.json",
    }
    if any(path.exists() for path in paths.values()):
        raise TQCError("TS-C v2 output exists; same-scope rerun is forbidden")
    scope = TQC2Scope.load()
    validate_v2_bound_inputs(scope)
    identity = runtime_identity()
    root.mkdir(parents=True, exist_ok=True)
    marker_sha = _write_json_once(paths["marker"], {
        "schema_version": "ts-c-v2-semantic-read-marker-v1",
        "semantic_read_started": True,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "protocol_sha256": scope.sha256,
        "release_identity": identity,
    })
    first, events = build_profile_v2(scope, identity, root / "duckdb-tmp")
    second, events_replay = build_profile_v2(scope, identity, root / "duckdb-tmp-replay")
    if canonical_json(first) != canonical_json(second) or canonical_json(events) != canonical_json(events_replay):
        raise TQCError("TS-C v2 internal deterministic replay differs")
    v1_profile = json.loads(
        (PROJECT_ROOT / "data/research/trend_swing/ts-c-trigger-qualification-v1-r2/profile.json"
         ).read_text(encoding="utf-8")
    )
    expected_events_sha = v1_profile["machine_artifacts"]["events"]["sha256"]
    schema = pa.schema([
        ("trigger_id", pa.string()), ("ts_code", pa.string()), ("signal_date", pa.string()),
    ])
    table = pa.Table.from_pylist(events, schema=schema)
    pq.write_table(table, paths["events"], compression="zstd")
    events_sha = sha256_file(paths["events"])
    if events_sha != expected_events_sha:
        raise TQCError("TS-C v2 events do not reproduce the sealed v1 event set")
    artifacts = {
        "semantic_read_marker": {"path": _relative(paths["marker"]), "sha256": marker_sha},
        "events": {
            "path": _relative(paths["events"]), "row_count": table.num_rows,
            "sha256": events_sha, "contains_post_entry_outcome": False,
            "reproduces_sealed_v1_events": True,
        },
    }
    first["machine_artifacts"] = artifacts
    first["internal_deterministic_replay_pass"] = True
    first["canonical_payload_sha256"] = canonical_sha256(first)
    profile_sha = _write_json_once(paths["profile"], first)
    manifest = {
        "schema_version": "ts-c-trigger-qualification-v2-manifest-v1",
        "protocol_sha256": scope.sha256,
        "release_identity": identity,
        "artifacts": {**artifacts, "profile": {"path": _relative(paths["profile"]), "sha256": profile_sha}},
        "contains_outcome": False,
        "contains_security_identifiers": True,
        "production_authorization": "none",
    }
    _write_json_once(paths["manifest"], manifest)
    return first
