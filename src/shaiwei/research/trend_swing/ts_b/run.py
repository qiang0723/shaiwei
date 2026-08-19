"""One-shot TS-B holdout effect runner with write-once evidence."""

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
from shaiwei.research.trend_swing.v6_3.metrics import candidate_diagnostics
from shaiwei.research.trend_swing.ts_b.contract import (
    OUTPUT_ROOT,
    TSBError,
    TSBScope,
    runtime_identity,
    validate_authorized_effect_inputs,
)
from shaiwei.research.trend_swing.ts_b.inputs import TSBAdapter
from shaiwei.research.trend_swing.ts_b.metrics import evaluate_holdout, legacy_sharpes


def _frame(rows: tuple[dict[str, Any], ...]) -> pd.DataFrame:
    return pd.DataFrame(list(rows))


def execute_holdout(
    root: Path,
    scope: TSBScope,
    adapter: TSBAdapter,
    legacy: Sequence[float],
) -> dict[str, Any]:
    prepared = adapter.load_partition("holdout")
    point = scope.selected_point_hashes[0]
    events = prepared.events.loc[prepared.events["point_hash"].eq(point)].copy()
    if events.empty:
        raise TSBError("TS-B candidate events are empty")
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
        artifacts[name] = save_simulation(root / "holdout" / point / name, result, summary)
        if name == SCENARIOS[0]:
            base_nav, base_trades = nav, trades
    gate_config = dict(scope.document["holdout_gate"]["candidate"])
    gate_config["trial_count"] = int(scope.document["holdout_gate"]["deflated_sharpe"]["trial_count"])
    gate = evaluate_holdout(summaries, base_nav, base_trades, gate_config, legacy)
    document = {
        "schema_version": "ts-b-holdout-effect-v1",
        "partition": "holdout",
        "point": point,
        "candidate_event_count": int(len(events)),
        "points": {point: summaries},
        "artifacts": {point: artifacts},
        "diagnostics": candidate_diagnostics(summaries, base_nav, base_trades),
        "gate": gate,
        "verdict": (
            "GO_TS_B_DRAFT_FORWARD_PAPER_PROTOCOL_REQUIRES_NEW_BUDGET_DECISION"
            if gate["passed"]
            else "REJECT_TS_B_HOLDOUT_AND_CLOSE"
        ),
        "production_authorization": "none",
    }
    write_once_json(root / "holdout" / "partition_summary.json", document)
    return document


def _execute_pass(
    root: Path, scope: TSBScope, adapter: TSBAdapter, legacy: Sequence[float]
) -> dict[str, Any]:
    holdout = execute_holdout(root, scope, adapter, legacy)
    summary = {
        "schema_version": "ts-b-effect-pass-summary-v1",
        "effect_protocol_sha256": scope.sha256,
        "holdout_gate": holdout["gate"],
        "strategy_effect_attempt_count": 1,
        "verdict": holdout["verdict"],
        "strategy_effective": "NOT_YET_INDEPENDENTLY_AUDITED",
        "production_authorization": "none",
    }
    return {**seal_pass(root, summary), "verdict": holdout["verdict"]}


def run_once() -> dict[str, Any]:
    scope = TSBScope.load()
    validate_authorized_effect_inputs(scope)
    identity = runtime_identity()
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    marker_path = OUTPUT_ROOT / "effect_read_started.json"
    report_path = OUTPUT_ROOT / "report.json"
    failure_path = OUTPUT_ROOT / "failure.json"
    preflight_path = OUTPUT_ROOT / "pre_effect_preflight.json"
    if marker_path.exists() or report_path.exists() or failure_path.exists():
        raise TSBError("TS-B effect output exists; same-scope rerun is forbidden")
    if not preflight_path.is_file():
        raise TSBError("TS-B key-only preflight must be sealed before the effect read")
    try:
        preflight = json.loads(preflight_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise TSBError("TS-B sealed preflight is invalid") from exc
    effect_started = False
    try:
        adapter = TSBAdapter(scope, OUTPUT_ROOT / "duckdb-tmp")
        recomputed = adapter.preflight()
        if canonical_json(recomputed) != canonical_json(preflight):
            raise TSBError("TS-B pre-effect key preflight identity differs")
        legacy = legacy_sharpes()
        write_once_json(
            marker_path,
            {
                "schema_version": "ts-b-effect-read-marker-v1",
                "effect_read_started": True,
                "protocol_sha256": scope.sha256,
                "release_identity": identity,
                "strategy_effect_attempt_count": 1,
                "discovery_2021_2023_physically_unread": True,
            },
        )
        effect_started = True
        first = _execute_pass(OUTPUT_ROOT / "first_pass", scope, adapter, legacy)
        replay = _execute_pass(OUTPUT_ROOT / "replay", scope, adapter, legacy)
        comparable = ("bundle_sha256", "summary_sha256", "verdict")
        if any(first[key] != replay[key] for key in comparable):
            raise TSBError("TS-B first pass and replay differ")
        report = {
            "schema_version": "ts-b-effect-report-v1",
            "protocol_sha256": scope.sha256,
            "release_identity": identity,
            "pre_effect_key_preflight": recomputed,
            "first_pass": first,
            "replay": replay,
            "deterministic_replay": True,
            "strategy_effect_attempt_count": 1,
            "verdict": first["verdict"],
            "strategy_effective": "PENDING_INDEPENDENT_AUDIT",
            "production_authorization": "none",
        }
        digest, _ = write_once_json(report_path, report)
        return {
            "report_sha256": digest,
            "verdict": report["verdict"],
            "strategy_effective": report["strategy_effective"],
            "production_authorization": "none",
        }
    except Exception as error:
        write_once_json(
            failure_path,
            {
                "schema_version": "ts-b-effect-failure-v1",
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
    scope = TSBScope.load()
    validate_authorized_effect_inputs(scope)
    runtime_identity()
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    if any(
        (OUTPUT_ROOT / name).exists()
        for name in (
            "pre_effect_preflight.json", "effect_read_started.json", "report.json", "failure.json"
        )
    ):
        raise TSBError("TS-B preflight or effect output exists; rerun is forbidden")
    adapter = TSBAdapter(scope, OUTPUT_ROOT / "duckdb-tmp-preflight")
    document = adapter.preflight()
    write_once_json(OUTPUT_ROOT / "pre_effect_preflight.json", document)
    return document
