"""One-shot result-blind TS-v6-1 entry-quality ranking profile."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import pyarrow as pa
import pyarrow.parquet as pq

from shaiwei.config import PROJECT_ROOT
from shaiwei.research.provider_contract import D1ControlError
from shaiwei.research.trend_swing.contract import sha256_file
from shaiwei.research.trend_swing.v6.observations import (
    frozen_parent_keys,
    reconcile_parent_keys,
)
from shaiwei.research.trend_swing.v6_1.contract import (
    AUDIT_PATH,
    MANIFEST_PATH,
    MARKER_PATH,
    PROFILE_PATH,
    PROTOCOL_SHA256,
    RANKED_EVENT_PATH,
    OUTPUT_ROOT,
    V61Scope,
    runtime_identity,
    validate_bound_inputs,
)
from shaiwei.research.trend_swing.v6_1.score import (
    AXES,
    DIRECTIONS,
    canonical_json,
    canonical_sha256,
    development_gate_report,
    holdout_gate_report,
    native,
    score_against_reference,
    score_events,
    select_by_cut,
    select_top_k,
)


def _write_json_once(path: Path, document: Mapping[str, Any]) -> str:
    if path.exists():
        raise D1ControlError(f"TS-v6-1 write-once output already exists: {path.name}")
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
            raise D1ControlError("TS-v6-1 pre-marker failure receipt is invalid") from exc
        if (
            not isinstance(document, dict)
            or document.get("real_feature_read") is not False
            or document.get("semantic_read_marker_exists") is not False
            or document.get("strategy_or_density_attempt_increment") != 0
        ):
            raise D1ControlError("TS-v6-1 pre-marker failure receipt authority differs")
        receipts.append({
            "path": path.relative_to(PROJECT_ROOT).as_posix(),
            "sha256": sha256_file(path),
            "failure_class": document.get("failure_class"),
        })
    if len(receipts) > 2:
        raise D1ControlError("TS-v6-1 pre-marker technical repair budget exceeded")
    return receipts


def _write_ranked_events(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if RANKED_EVENT_PATH.exists():
        raise D1ControlError("TS-v6-1 ranked-event output already exists")
    schema = pa.schema([
        ("role", pa.string()), ("ts_code", pa.string()), ("signal_date", pa.string()),
        ("next_open_date", pa.string()), ("score", pa.string()), ("selected", pa.bool_()),
    ])
    ordered = sorted(rows, key=lambda row: (
        str(row["role"]), str(row["ts_code"]), str(row["signal_date"]), str(row["next_open_date"])
    ))
    table = pa.Table.from_pylist(
        [{**row, "score": format(row["score"], "f")} for row in ordered], schema=schema
    )
    pq.write_table(table, RANKED_EVENT_PATH, compression="zstd")
    return {
        "path": RANKED_EVENT_PATH.relative_to(PROJECT_ROOT).as_posix(),
        "row_count": table.num_rows,
        "sha256": sha256_file(RANKED_EVENT_PATH),
        "gitignored": True,
        "contains_post_entry_outcome": False,
    }


def _load_parent_observations(scope: V61Scope) -> list[dict[str, Any]]:
    path = PROJECT_ROOT / scope.document["frozen_inputs"]["parent_observation_path"]
    rows = pq.read_table(path).to_pylist()
    observations = []
    for row in rows:
        observations.append({
            "role": str(row["role"]),
            "ts_code": str(row["ts_code"]),
            "signal_date": str(row["signal_date"]),
            "next_open_date": str(row["next_open_date"]),
            "pullback_amount_ratio": row["pullback_amount_ratio"],
            "recovery_close_location": row["recovery_close_location"],
            "pre_entry_10d_return_percentile": row["pre_entry_10d_return_percentile"],
        })
    reconcile_parent_keys(observations, frozen_parent_keys(scope))
    if any(str(row["signal_date"]) >= "20260101" for row in observations):
        raise D1ControlError("TS-v6-1 current partial-year data entered the preflight")
    return observations


def build_ranking(
    observations: Sequence[Mapping[str, Any]], scope: V61Scope, identity: Mapping[str, str]
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    roles = scope.document["chronological_roles"]
    development = [row for row in observations if row["role"] == "selectable_discovery"]
    holdout = [row for row in observations if row["role"] == "frozen_stability_holdout"]
    expected_dev = int(roles["development_distribution_and_density"]["frozen_parent_event_count"])
    expected_holdout = int(roles["conditional_density_only_holdout"]["frozen_parent_event_count"])
    if len(development) != expected_dev or len(holdout) != expected_holdout:
        raise D1ControlError("TS-v6-1 frozen parent observation counts differ")
    scored_dev = score_events(development)
    selected_dev, cut_score = select_top_k(scored_dev, scope.development_top_k)
    scored_holdout = score_against_reference(development, holdout)
    selected_holdout = select_by_cut(scored_holdout, cut_score)
    gate_source = scope.document["density_dispersion_and_integration_gate"]
    dev_report = development_gate_report(
        selected_dev, scored_dev, development, gate_source["development"], scope.development_top_k
    )
    holdout_report = holdout_gate_report(
        selected_holdout, gate_source["conditional_density_only_holdout"]
    )
    verdict = (
        "GO_TS_V6_1_RANKING_EFFECT_SCOPE_PROPOSAL_ONLY"
        if dev_report["pass"] and holdout_report["pass"]
        else "STOP_TS_V6_1_RANKING_DEGENERATE_OR_SPARSE"
    )
    selected_keys = {
        (row["role"], row["ts_code"], row["signal_date"], row["next_open_date"])
        for row in (*selected_dev, *selected_holdout)
    }
    ranked_rows = [
        {**row, "selected": (row["role"], row["ts_code"], row["signal_date"], row["next_open_date"]) in selected_keys}
        for row in (*scored_dev, *scored_holdout)
    ]
    report = {
        "schema_version": "ts-v6-1-entry-quality-ranking-preflight-profile-v1",
        "protocol_sha256": PROTOCOL_SHA256,
        "release_identity": dict(identity),
        "parent_primary_point_hash": scope.document["result_informed_parent"][
            "parent_primary_point_hash"
        ],
        "parent_effect_verdict_retained": scope.document["result_informed_parent"][
            "parent_effect_verdict"
        ],
        "score_formula": {
            "axes": list(AXES),
            "directions": dict(DIRECTIONS),
            "axis_position": "development_ecdf_mid_rank_quantile_position_q8_decimal",
            "aggregation": "equal_weight_arithmetic_mean",
        },
        "selection_rule": {
            "development_top_k": scope.development_top_k,
            "frozen_retention_fraction": 0.5,
            "cut_score": format(cut_score, "f"),
            "holdout_rule": "score_greater_than_or_equal_to_frozen_cut_score",
        },
        "parent_observation_counts": {
            "selectable_discovery": len(development),
            "frozen_stability_holdout": len(holdout),
        },
        "development": dev_report,
        "conditional_density_only_holdout": holdout_report,
        "selected_event_counts": {
            "selectable_discovery": len(selected_dev),
            "frozen_stability_holdout": len(selected_holdout),
        },
        "authority": {
            "post_entry_outcome_read": False,
            "holdout_outcome_read": False,
            "current_partial_year_read": False,
            "alpha158_value_or_rank_read": False,
            "benchmark_value_read": False,
            "new_market_or_security_data_read": False,
            "external_api_calls": 0,
            "secret_read": False,
            "strategy_effect_attempt_increment": 0,
        },
        "strategy_effective": "NOT_EVALUATED",
        "production_authorization": "none",
        "verdict": verdict,
    }
    report["canonical_payload_sha256"] = canonical_sha256(report)
    return native(report), ranked_rows


def run_profile_once() -> dict[str, Any]:
    outputs = (MARKER_PATH, RANKED_EVENT_PATH, PROFILE_PATH, MANIFEST_PATH, AUDIT_PATH)
    if any(path.exists() for path in outputs):
        raise D1ControlError("TS-v6-1 output exists; same-scope rerun is forbidden")
    scope = V61Scope.load()
    validate_bound_inputs(scope)
    identity = runtime_identity()
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    receipts = _pre_marker_receipts()
    marker = {
        "schema_version": "ts-v6-1-semantic-read-marker-v1",
        "semantic_read_started": True,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "protocol_sha256": scope.sha256,
        "release_identity": identity,
        "pre_marker_technical_failure_receipts": receipts,
    }
    marker_sha = _write_json_once(MARKER_PATH, marker)
    observations = _load_parent_observations(scope)
    first, ranked_rows = build_ranking(observations, scope, identity)
    second, replay_rows = build_ranking(observations, scope, identity)
    if canonical_json(first) != canonical_json(second) or canonical_json(ranked_rows) != canonical_json(replay_rows):
        raise D1ControlError("TS-v6-1 internal deterministic replay differs")
    artifacts = {
        "semantic_read_marker": {
            "path": MARKER_PATH.relative_to(PROJECT_ROOT).as_posix(), "sha256": marker_sha
        },
        "ranked_events": _write_ranked_events(ranked_rows),
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
        "schema_version": "ts-v6-1-entry-quality-ranking-preflight-manifest-v1",
        "protocol_sha256": scope.sha256,
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
    development, holdout = [], []
    for index in range(120):
        year = 2021 + index % 3
        development.append({
            "role": "selectable_discovery",
            "ts_code": f"{index:06d}.SZ",
            "signal_date": f"{year}{1 + index % 12:02d}{1 + index % 27:02d}",
            "next_open_date": f"{year}{1 + index % 12:02d}{2 + index % 26:02d}",
            "pullback_amount_ratio": (index % 30 + 1) / 10,
            "recovery_close_location": (index % 20 + 1) / 21,
            "pre_entry_10d_return_percentile": (index % 25 + 1) / 26,
        })
    for index in range(60):
        year = 2024 + index % 2
        holdout.append({
            "role": "frozen_stability_holdout",
            "ts_code": f"{index:06d}.SH",
            "signal_date": f"{year}{1 + index % 12:02d}{1 + index % 27:02d}",
            "next_open_date": f"{year}{1 + index % 12:02d}{2 + index % 26:02d}",
            "pullback_amount_ratio": (index % 30 + 1) / 10,
            "recovery_close_location": (index % 20 + 1) / 21,
            "pre_entry_10d_return_percentile": (index % 25 + 1) / 26,
        })
    scored = score_events(development)
    selected, cut = select_top_k(scored, 60)
    if len(selected) != 60 or selected[0]["score"] < selected[-1]["score"]:
        raise D1ControlError("TS-v6-1 fixture ranking order differs")
    gate = {"minimum_legal_events": 60, "minimum_distinct_signal_days": 30,
            "minimum_events_each_calendar_year": 10}
    dev_report = development_gate_report(selected, scored, development, gate, 60)
    holdout_selected = select_by_cut(score_against_reference(development, holdout), cut)
    holdout_report = holdout_gate_report(
        holdout_selected, {"minimum_distinct_signal_days": 10, "minimum_events_each_calendar_year": 10}
    )
    if not dev_report["pass"] or not holdout_report["pass"]:
        raise D1ControlError("TS-v6-1 fixture gate report differs")
    replay = score_events(development)
    if canonical_json(scored) != canonical_json(replay):
        raise D1ControlError("TS-v6-1 fixture deterministic replay differs")
    return {
        "fixture_pass": True,
        "score_axes": list(AXES),
        "library_scalar_normalization": True,
    }
