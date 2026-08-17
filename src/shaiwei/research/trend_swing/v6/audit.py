"""Independent aggregate recomputation for the TS-v6 preflight."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

from shaiwei.research.provider_contract import D1ControlError
from shaiwei.research.trend_swing.contract import sha256_file
from shaiwei.research.trend_swing.v6.contract import (
    AUDIT_PATH,
    CANDIDATE_EVENT_PATH,
    MANIFEST_PATH,
    OBSERVATION_PATH,
    PROFILE_PATH,
    V6Scope,
    validate_bound_inputs,
)
from shaiwei.research.trend_swing.v6.engine import (
    AXES,
    canonical_sha256,
    density,
    derive_levels,
    design_points,
    development_eligible,
    filter_events,
    native,
    select_point,
)
from shaiwei.research.trend_swing.v6.profile import _write_json_once


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise D1ControlError(f"TS-v6 audit input is invalid: {path.name}") from exc
    if not isinstance(value, dict):
        raise D1ControlError(f"TS-v6 audit input is not an object: {path.name}")
    return value


def _rows(path: Path) -> list[dict[str, Any]]:
    return pq.read_table(path).to_pylist()


def audit_once() -> dict[str, Any]:
    if AUDIT_PATH.exists():
        raise D1ControlError("TS-v6 audit exists; same-scope audit rerun is forbidden")
    scope = V6Scope.load()
    validate_bound_inputs(scope)
    report, manifest = _read_json(PROFILE_PATH), _read_json(MANIFEST_PATH)
    observations, candidate_rows = _rows(OBSERVATION_PATH), _rows(CANDIDATE_EVENT_PATH)
    development = [row for row in observations if row["role"] == "selectable_discovery"]
    holdout = [row for row in observations if row["role"] == "frozen_stability_holdout"]
    levels = derive_levels(development)
    gate_source = scope.document["density_and_distinctness_gate"]
    development_gate = dict(gate_source["development"])
    development_gate.update(
        retention_minimum=gate_source["parent_event_retention_ratio"]["minimum"],
        retention_maximum=gate_source["parent_event_retention_ratio"]["maximum"],
    )
    profiles, expected_event_keys = [], set()
    for point in design_points(levels):
        accepted, reasons, axis_rejected = filter_events(development, point["parameters"])
        evidence = density(accepted, (2021, 2022, 2023))
        passed, retention = development_eligible(
            evidence, len(development), axis_rejected, development_gate
        )
        profiles.append({
            **point, "development": evidence, "development_pass": passed,
            "parent_event_retention_ratio": round(retention, 12),
            "first_rejection_reason_counts": reasons,
            "per_axis_rejected_parent_event_counts": axis_rejected,
        })
        expected_event_keys.update((
            "selectable_discovery", point["point_hash"], row["ts_code"],
            row["signal_date"], row["next_open_date"],
        ) for row in accepted)
    selected = select_point(profiles)
    holdout_evidence, holdout_pass = None, False
    if selected is not None:
        accepted, _, _ = filter_events(holdout, selected["parameters"])
        holdout_evidence = density(accepted, (2024, 2025))
        gate = gate_source["conditional_density_only_holdout"]
        holdout_pass = (
            holdout_evidence["distinct_signal_day_count"] >= gate["minimum_distinct_signal_days"]
            and min(holdout_evidence["legal_event_count_by_calendar_year"].values(), default=0)
            >= gate["minimum_events_each_calendar_year"]
        )
        expected_event_keys.update((
            "frozen_stability_holdout", selected["point_hash"], row["ts_code"],
            row["signal_date"], row["next_open_date"],
        ) for row in accepted)
    observed_event_keys = {(
        row["role"], row["point_hash"], row["ts_code"], row["signal_date"], row["next_open_date"]
    ) for row in candidate_rows}
    selected_summary = None if selected is None else {
        "point_hash": selected["point_hash"], "level_indices": selected["level_indices"],
        "parameters": selected["parameters"],
    }
    expected_verdict = (
        "GO_TS_V6_ENTRY_QUALITY_EFFECT_SCOPE_PROPOSAL_ONLY"
        if selected is not None and holdout_pass
        else "STOP_TS_V6_ENTRY_QUALITY_NO_DENSE_NONDUPLICATE_POINT"
    )
    artifact_hashes = {
        key: sha256_file(path) for key, path in {
            "parent_observations": OBSERVATION_PATH,
            "candidate_events": CANDIDATE_EVENT_PATH,
            "profile": PROFILE_PATH,
        }.items()
    }
    checks = {
        "protocol_identity": report.get("protocol_sha256") == scope.sha256,
        "addendum_identity": report.get("operationalization_addendum_sha256") == scope.addendum_sha256,
        "parameter_levels": report.get("derived_parameter_levels") == {
            axis: [format(value, "f") for value in levels[axis]] for axis in AXES
        },
        "point_profiles": report.get("point_profiles") == native(profiles),
        "selected_point": report.get("selected_point") == native(selected_summary),
        "holdout_density": report.get("conditional_density_only_holdout") == native(holdout_evidence),
        "holdout_pass": report.get("conditional_density_only_holdout_pass") is holdout_pass,
        "candidate_event_keys": observed_event_keys == expected_event_keys
        and len(observed_event_keys) == len(candidate_rows),
        "manifest_hashes": all(
            manifest["artifacts"][name]["sha256"] == digest for name, digest in artifact_hashes.items()
        ),
        "profile_payload_hash": report.get("canonical_payload_sha256") == canonical_sha256({
            key: value for key, value in report.items() if key != "canonical_payload_sha256"
        }),
        "current_partial_year_excluded": all(
            str(row["signal_date"]) < "20260101" for row in observations
        ),
        "verdict": report.get("verdict") == expected_verdict,
        "authority": report.get("strategy_effective") == "NOT_EVALUATED"
        and report.get("production_authorization") == "none"
        and all(value is False or value == 0 for value in report.get("authority", {}).values()),
    }
    verdict = "PASS" if checks and all(checks.values()) else "FAIL"
    audit = {
        "schema_version": "ts-v6-entry-quality-preflight-independent-audit-v1",
        "protocol_sha256": scope.sha256,
        "profile_sha256": artifact_hashes["profile"],
        "checks": native(checks),
        "independent_recomputed_payload_sha256": canonical_sha256({
            "levels": report.get("derived_parameter_levels"), "profiles": profiles,
            "selected": selected_summary, "holdout": holdout_evidence,
            "holdout_pass": holdout_pass, "verdict": expected_verdict,
        }),
        "post_entry_outcome_read": False,
        "strategy_effective": "NOT_EVALUATED",
        "production_authorization": "none",
        "independent_audit": verdict,
    }
    _write_json_once(AUDIT_PATH, audit)
    if verdict != "PASS":
        raise D1ControlError("TS-v6 independent audit failed")
    return audit
