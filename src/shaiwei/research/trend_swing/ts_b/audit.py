"""Independent artifact auditor for the one-shot TS-B holdout effect."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd

from shaiwei.research.trend_swing.r3g2.contract import sha256_file
from shaiwei.research.trend_swing.r3g2.effect_artifacts import tree_manifest
from shaiwei.research.trend_swing.r3g2.effect_metrics import summarize
from shaiwei.research.trend_swing.r3g2.effect_models import SCENARIOS
from shaiwei.research.trend_swing.r3g2.evidence import canonical_json, write_once_json
from shaiwei.research.trend_swing.v6_3.metrics import candidate_diagnostics
from shaiwei.research.trend_swing.ts_b.contract import (
    OUTPUT_ROOT,
    TSBError,
    TSBScope,
    validate_authorized_effect_inputs,
)
from shaiwei.research.trend_swing.ts_b.inputs import TSBAdapter
from shaiwei.research.trend_swing.ts_b.metrics import evaluate_holdout, legacy_sharpes


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise TSBError(f"TS-B audit input is invalid: {path.name}") from exc
    if not isinstance(value, dict):
        raise TSBError(f"TS-B audit input is not an object: {path.name}")
    return value


def _manifest(root: Path) -> None:
    document = _read_json(root / "manifest.json")
    if document != tree_manifest(root):
        raise TSBError("TS-B independent artifact manifest differs")


def _pass_trees_equal(first: Path, replay: Path) -> bool:
    def files(root: Path) -> dict[str, str]:
        return {
            path.relative_to(root).as_posix(): sha256_file(path)
            for path in sorted(root.rglob("*"))
            if path.is_file() and path.name != "manifest.json"
        }

    return files(first) == files(replay)


def audit_once() -> dict[str, Any]:
    audit_path = OUTPUT_ROOT / "audit.json"
    if audit_path.exists():
        raise TSBError("TS-B audit exists; same-scope audit rerun is forbidden")
    scope = TSBScope.load()
    validate_authorized_effect_inputs(scope)
    report = _read_json(OUTPUT_ROOT / "report.json")
    point = scope.selected_point_hashes[0]
    first = OUTPUT_ROOT / "first_pass"
    replay = OUTPUT_ROOT / "replay"
    _manifest(first)
    _manifest(replay)
    if not _pass_trees_equal(first, replay):
        raise TSBError("TS-B first pass and replay artifact trees differ")
    summaries: dict[str, dict[str, Any]] = {}
    base_nav = base_trades = None
    for name in SCENARIOS:
        artifact = first / "holdout" / point / name
        nav = pd.read_parquet(artifact / "nav.parquet").sort_values("trade_date")
        orders = pd.read_parquet(artifact / "orders.parquet")
        trades = pd.read_parquet(artifact / "trades.parquet")
        written = _read_json(artifact / "summary.json")
        recomputed = summarize(nav, orders, trades, blocked_reason=written["blocked_reason"])
        if json.loads(canonical_json(written)) != json.loads(canonical_json(recomputed)):
            raise TSBError(f"TS-B audited summary differs: {name}")
        summaries[name] = recomputed
        if name == SCENARIOS[0]:
            base_nav, base_trades = nav, trades
    gate_config = dict(scope.document["holdout_gate"]["candidate"])
    gate_config["trial_count"] = int(scope.document["holdout_gate"]["deflated_sharpe"]["trial_count"])
    gate = evaluate_holdout(summaries, base_nav, base_trades, gate_config, legacy_sharpes())
    diagnostics = candidate_diagnostics(summaries, base_nav, base_trades)
    adapter = TSBAdapter(scope, OUTPUT_ROOT / "duckdb-tmp-audit")
    preflight = adapter.preflight()
    sealed = _read_json(OUTPUT_ROOT / "pre_effect_preflight.json")
    expected_verdict = (
        "GO_TS_B_DRAFT_FORWARD_PAPER_PROTOCOL_REQUIRES_NEW_BUDGET_DECISION"
        if gate["passed"]
        else "REJECT_TS_B_HOLDOUT_AND_CLOSE"
    )
    checks = {
        "protocol_identity": report.get("protocol_sha256") == scope.sha256,
        "preflight_identity": json.loads(canonical_json(preflight)) == json.loads(
            canonical_json(sealed)
        ) and report.get("pre_effect_key_preflight") == sealed,
        "pass_manifests": True,
        "first_replay_trees_equal": True,
        "gate_recomputed": report.get("first_pass", {}).get("verdict") == expected_verdict
        and gate["passed"] == (expected_verdict.startswith("GO")),
        "diagnostics_recomputed": bool(diagnostics),
        "discovery_physically_absent": not (first / "discovery").exists(),
        "attempt_count": report.get("strategy_effect_attempt_count") == 1,
        "authority": report.get("production_authorization") == "none"
        and report.get("verdict") == expected_verdict,
    }
    verdict = "PASS" if all(checks.values()) else "FAIL"
    audit = {
        "schema_version": "ts-b-holdout-effect-independent-audit-v1",
        "protocol_sha256": scope.sha256,
        "report_sha256": sha256_file(OUTPUT_ROOT / "report.json"),
        "checks": checks,
        "independent_recomputed_payload_sha256": hashlib.sha256(
            canonical_json({"gate": gate, "verdict": expected_verdict})
        ).hexdigest(),
        "discovery_2021_2023_read": False,
        "strategy_effective": report.get("strategy_effective"),
        "production_authorization": "none",
        "independent_audit": verdict,
    }
    write_once_json(audit_path, audit)
    if verdict != "PASS":
        raise TSBError("TS-B independent audit failed")
    return audit
