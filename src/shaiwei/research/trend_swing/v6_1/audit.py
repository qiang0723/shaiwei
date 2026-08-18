"""Independent aggregate recomputation for the TS-v6-1 ranking preflight."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

from shaiwei.config import PROJECT_ROOT
from shaiwei.research.provider_contract import D1ControlError
from shaiwei.research.trend_swing.contract import sha256_file
from shaiwei.research.trend_swing.v6_1.contract import (
    AUDIT_PATH,
    MANIFEST_PATH,
    PROFILE_PATH,
    RANKED_EVENT_PATH,
    V61Scope,
    validate_bound_inputs,
)
from shaiwei.research.trend_swing.v6_1.profile import _write_json_once
from shaiwei.research.trend_swing.v6_1.score import (
    canonical_sha256,
    development_gate_report,
    holdout_gate_report,
    native,
    score_against_reference,
    score_events,
    select_by_cut,
    select_top_k,
)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise D1ControlError(f"TS-v6-1 audit input is invalid: {path.name}") from exc
    if not isinstance(value, dict):
        raise D1ControlError(f"TS-v6-1 audit input is not an object: {path.name}")
    return value


def audit_once() -> dict[str, Any]:
    if AUDIT_PATH.exists():
        raise D1ControlError("TS-v6-1 audit exists; same-scope audit rerun is forbidden")
    scope = V61Scope.load()
    validate_bound_inputs(scope)
    report, manifest = _read_json(PROFILE_PATH), _read_json(MANIFEST_PATH)
    observations = pq.read_table(_observation_path(scope)).to_pylist()
    development = [row for row in observations if str(row["role"]) == "selectable_discovery"]
    holdout = [row for row in observations if str(row["role"]) == "frozen_stability_holdout"]
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
    expected_verdict = (
        "GO_TS_V6_1_RANKING_EFFECT_SCOPE_PROPOSAL_ONLY"
        if dev_report["pass"] and holdout_report["pass"]
        else "STOP_TS_V6_1_RANKING_DEGENERATE_OR_SPARSE"
    )
    expected_selected = {
        (row["role"], row["ts_code"], row["signal_date"], row["next_open_date"])
        for row in (*selected_dev, *selected_holdout)
    }
    ranked_rows = pq.read_table(RANKED_EVENT_PATH).to_pylist()
    observed_selected = {
        (str(row["role"]), str(row["ts_code"]), str(row["signal_date"]), str(row["next_open_date"]))
        for row in ranked_rows
        if row["selected"] is True
    }
    artifact_hashes = {
        key: sha256_file(path) for key, path in {
            "ranked_events": RANKED_EVENT_PATH,
            "profile": PROFILE_PATH,
        }.items()
    }
    checks = {
        "protocol_identity": report.get("protocol_sha256") == scope.sha256,
        "cut_score": report.get("selection_rule", {}).get("cut_score") == format(cut_score, "f"),
        "development_gate_report": report.get("development") == native(dev_report),
        "holdout_gate_report": report.get("conditional_density_only_holdout") == native(holdout_report),
        "selected_event_keys": observed_selected == expected_selected
        and len(ranked_rows) == len(observations),
        "selected_event_counts": report.get("selected_event_counts") == {
            "selectable_discovery": len(selected_dev),
            "frozen_stability_holdout": len(selected_holdout),
        },
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
        "schema_version": "ts-v6-1-entry-quality-ranking-preflight-independent-audit-v1",
        "protocol_sha256": scope.sha256,
        "profile_sha256": artifact_hashes["profile"],
        "checks": native(checks),
        "independent_recomputed_payload_sha256": canonical_sha256({
            "cut_score": format(cut_score, "f"),
            "development": dev_report,
            "holdout": holdout_report,
            "verdict": expected_verdict,
        }),
        "post_entry_outcome_read": False,
        "strategy_effective": "NOT_EVALUATED",
        "production_authorization": "none",
        "independent_audit": verdict,
    }
    _write_json_once(AUDIT_PATH, audit)
    if verdict != "PASS":
        raise D1ControlError("TS-v6-1 independent audit failed")
    return audit


def _observation_path(scope: V61Scope) -> Path:
    return PROJECT_ROOT / scope.document["frozen_inputs"]["parent_observation_path"]
