"""One-shot TS-v6-3 discovery effect runner with write-once evidence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Sequence

import pandas as pd

from shaiwei.research.trend_swing.r3g2.effect_artifacts import save_simulation, seal_pass
from shaiwei.research.trend_swing.r3g2.effect_execution import simulate
from shaiwei.research.trend_swing.r3g2.effect_metrics import summarize
from shaiwei.research.trend_swing.r3g2.effect_models import SCENARIOS, scenario
from shaiwei.research.trend_swing.r3g2.evidence import canonical_json, write_once_json
from shaiwei.research.trend_swing.v6_3.contract import (
    FAILURE_PATH,
    MARKER_PATH,
    OUTPUT_ROOT,
    PREFLIGHT_PATH,
    REPORT_PATH,
    V63Error,
    V63Scope,
    runtime_identity,
    validate_authorized_effect_inputs,
)
from shaiwei.research.trend_swing.v6_3.inputs import V63Adapter
from shaiwei.research.trend_swing.v6_3.metrics import (
    candidate_diagnostics,
    evaluate_candidate,
    legacy_r3g2_sharpes,
)


def _frame(rows: tuple[dict[str, Any], ...]) -> pd.DataFrame:
    return pd.DataFrame(list(rows))


def _pre_marker_receipts() -> list[dict[str, Any]]:
    receipts = []
    for path in sorted(OUTPUT_ROOT.glob("pre_marker_failure_*.json")):
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise V63Error("TS-v6-3 pre-marker failure receipt is invalid") from exc
        if (
            not isinstance(document, dict)
            or document.get("real_effect_read") is not False
            or document.get("effect_read_marker_exists") is not False
            or document.get("strategy_effect_attempt_increment") != 0
        ):
            raise V63Error("TS-v6-3 pre-marker failure receipt authority differs")
        receipts.append({
            "path": path.name,
            "failure_class": document.get("failure_class"),
        })
    if len(receipts) > 2:
        raise V63Error("TS-v6-3 pre-marker technical repair budget exceeded")
    return receipts


def execute_discovery(
    root: Path,
    scope: V63Scope,
    adapter: V63Adapter,
    legacy_sharpes: Sequence[float],
) -> dict[str, Any]:
    prepared = adapter.load_partition("discovery")
    point = scope.selected_point_hashes[0]
    events = prepared.events.loc[prepared.events["point_hash"].eq(point)].copy()
    if events.empty:
        raise V63Error("TS-v6-3 candidate events are empty")
    summaries: dict[str, dict[str, Any]] = {}
    artifacts: dict[str, Any] = {}
    base_nav = base_trades = None
    for name in SCENARIOS:
        result = simulate(
            events=events,
            bars=prepared.bars,
            benchmark=prepared.benchmark,
            calendar=prepared.calendar,
            current=scenario(name),
        )
        nav, orders, trades = _frame(result.nav_rows), _frame(result.order_rows), _frame(
            result.trade_rows
        )
        summary = summarize(nav, orders, trades, blocked_reason=result.blocked_reason)
        summaries[name] = summary
        artifacts[name] = save_simulation(root / "discovery" / point / name, result, summary)
        if name == SCENARIOS[0]:
            base_nav, base_trades = nav, trades
    gate_config = dict(scope.document["discovery_gate"]["candidate"])
    gate_config["trial_count"] = int(scope.document["discovery_gate"]["deflated_sharpe"]["trial_count"])
    gate = evaluate_candidate(summaries, base_nav, base_trades, gate_config, legacy_sharpes)
    document = {
        "schema_version": "ts-v6-3-discovery-effect-v1",
        "partition": "discovery",
        "point": point,
        "candidate_event_count": int(len(events)),
        "points": {point: summaries},
        "artifacts": {point: artifacts},
        "diagnostics": candidate_diagnostics(summaries, base_nav, base_trades),
        "gate": gate,
        "verdict": (
            "GO_TS_V6_3_DRAFT_SEPARATE_HOLDOUT_PROTOCOL_ONLY"
            if gate["passed"]
            else "REJECT_TS_V6_3_RANKED_SUBSET_DISCOVERY"
        ),
        "production_authorization": "none",
    }
    write_once_json(root / "discovery" / "partition_summary.json", document)
    return document


def _execute_pass(
    root: Path, scope: V63Scope, adapter: V63Adapter, legacy_sharpes: Sequence[float]
) -> dict[str, Any]:
    discovery = execute_discovery(root, scope, adapter, legacy_sharpes)
    summary = {
        "schema_version": "ts-v6-3-effect-pass-summary-v1",
        "effect_protocol_sha256": scope.sha256,
        "discovery_gate": discovery["gate"],
        "holdout_gate": None,
        "holdout_outcomes_opened": False,
        "strategy_effect_attempt_count": 1,
        "verdict": discovery["verdict"],
        "strategy_effective": "NOT_YET_INDEPENDENTLY_AUDITED",
        "production_authorization": "none",
    }
    return {**seal_pass(root, summary), "verdict": discovery["verdict"]}


def run_once() -> dict[str, Any]:
    scope = V63Scope.load()
    validate_authorized_effect_inputs(scope)
    identity = runtime_identity()
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    if MARKER_PATH.exists() or REPORT_PATH.exists() or FAILURE_PATH.exists():
        raise V63Error("TS-v6-3 effect output exists; same-scope rerun is forbidden")
    if not PREFLIGHT_PATH.is_file():
        raise V63Error("TS-v6-3 key-only preflight must be sealed before the effect read")
    try:
        preflight = json.loads(PREFLIGHT_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise V63Error("TS-v6-3 sealed preflight is invalid") from exc
    effect_started = False
    try:
        adapter = V63Adapter(scope, OUTPUT_ROOT / "duckdb-tmp")
        recomputed = adapter.preflight()
        if canonical_json(recomputed) != canonical_json(preflight):
            raise V63Error("TS-v6-3 pre-effect key preflight identity differs")
        receipts = _pre_marker_receipts()
        write_once_json(
            MARKER_PATH,
            {
                "schema_version": "ts-v6-3-effect-read-marker-v1",
                "effect_read_started": True,
                "protocol_sha256": scope.sha256,
                "release_identity": identity,
                "strategy_effect_attempt_count": 1,
                "discovery_only_holdout_physically_unread": True,
                "pre_marker_technical_failure_receipts": receipts,
            },
        )
        effect_started = True
        legacy = legacy_r3g2_sharpes()
        first = _execute_pass(OUTPUT_ROOT / "first_pass", scope, adapter, legacy)
        replay = _execute_pass(OUTPUT_ROOT / "replay", scope, adapter, legacy)
        comparable = ("bundle_sha256", "summary_sha256", "verdict")
        if any(first[key] != replay[key] for key in comparable):
            raise V63Error("TS-v6-3 first pass and replay differ")
        report = {
            "schema_version": "ts-v6-3-effect-report-v1",
            "protocol_sha256": scope.sha256,
            "release_identity": identity,
            "pre_effect_key_preflight": recomputed,
            "first_pass": first,
            "replay": replay,
            "deterministic_replay": True,
            "strategy_effect_attempt_count": 1,
            "holdout_outcomes_opened": False,
            "verdict": first["verdict"],
            "strategy_effective": "PENDING_INDEPENDENT_AUDIT",
            "production_authorization": "none",
        }
        digest, _ = write_once_json(REPORT_PATH, report)
        return {
            "report_sha256": digest,
            "verdict": report["verdict"],
            "strategy_effective": report["strategy_effective"],
            "production_authorization": "none",
        }
    except Exception as error:
        write_once_json(
            FAILURE_PATH,
            {
                "schema_version": "ts-v6-3-effect-failure-v1",
                "protocol_sha256": scope.sha256,
                "effect_read_started": effect_started,
                "strategy_effect_attempt_count": 1 if effect_started else 0,
                "same_scope_retry_authorized": False,
                "error_type": type(error).__name__,
                "error_message": str(error)[:500],
                "strategy_effective": "NOT_EVALUATED",
                "production_authorization": "none",
            },
        )
        raise


def preflight_once() -> dict[str, Any]:
    scope = V63Scope.load()
    validate_authorized_effect_inputs(scope)
    runtime_identity()
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    if any(
        path.exists()
        for path in (PREFLIGHT_PATH, MARKER_PATH, REPORT_PATH, FAILURE_PATH)
    ):
        raise V63Error("TS-v6-3 preflight or effect output exists; rerun is forbidden")
    adapter = V63Adapter(scope, OUTPUT_ROOT / "duckdb-tmp-preflight")
    document = adapter.preflight()
    write_once_json(PREFLIGHT_PATH, document)
    return document
