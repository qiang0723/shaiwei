"""Independent artifact auditor for the one-shot TS-v6-3 discovery effect."""

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
from shaiwei.research.trend_swing.v6_3.contract import (
    AUDIT_PATH,
    OUTPUT_ROOT,
    PREFLIGHT_PATH,
    REPORT_PATH,
    V63Error,
    V63Scope,
    validate_authorized_effect_inputs,
)
from shaiwei.research.trend_swing.v6_3.inputs import V63Adapter, frozen_candidate_keys
from shaiwei.research.trend_swing.v6_3.metrics import (
    candidate_diagnostics,
    evaluate_candidate,
    legacy_r3g2_sharpes,
)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise V63Error(f"TS-v6-3 audit input is invalid: {path.name}") from exc
    if not isinstance(value, dict):
        raise V63Error(f"TS-v6-3 audit input is not an object: {path.name}")
    return value


def _manifest(root: Path) -> dict[str, Any]:
    document = _read_json(root / "manifest.json")
    observed = tree_manifest(root)
    if document != observed:
        raise V63Error("TS-v6-3 independent artifact manifest differs")
    return document


def _pass_trees_equal(first: Path, replay: Path) -> bool:
    def files(root: Path) -> dict[str, str]:
        return {
            path.relative_to(root).as_posix(): sha256_file(path)
            for path in sorted(root.rglob("*"))
            if path.is_file() and path.name != "manifest.json"
        }

    return files(first) == files(replay)


def audit_once() -> dict[str, Any]:
    if AUDIT_PATH.exists():
        raise V63Error("TS-v6-3 audit exists; same-scope audit rerun is forbidden")
    scope = V63Scope.load()
    validate_authorized_effect_inputs(scope)
    report = _read_json(REPORT_PATH)
    point = scope.selected_point_hashes[0]
    first = OUTPUT_ROOT / "first_pass"
    replay = OUTPUT_ROOT / "replay"
    _manifest(first)
    _manifest(replay)
    if not _pass_trees_equal(first, replay):
        raise V63Error("TS-v6-3 first pass and replay artifact trees differ")
    summaries: dict[str, dict[str, Any]] = {}
    base_nav = base_trades = None
    for name in SCENARIOS:
        artifact = first / "discovery" / point / name
        nav = pd.read_parquet(artifact / "nav.parquet").sort_values("trade_date")
        orders = pd.read_parquet(artifact / "orders.parquet")
        trades = pd.read_parquet(artifact / "trades.parquet")
        written = _read_json(artifact / "summary.json")
        recomputed = summarize(nav, orders, trades, blocked_reason=written["blocked_reason"])
        if json.loads(canonical_json(written)) != json.loads(canonical_json(recomputed)):
            raise V63Error(f"TS-v6-3 audited summary differs: {name}")
        summaries[name] = recomputed
        if name == SCENARIOS[0]:
            base_nav, base_trades = nav, trades
    gate_config = dict(scope.document["discovery_gate"]["candidate"])
    gate_config["trial_count"] = int(scope.document["discovery_gate"]["deflated_sharpe"]["trial_count"])
    gate = evaluate_candidate(summaries, base_nav, base_trades, gate_config, legacy_r3g2_sharpes())
    diagnostics = candidate_diagnostics(summaries, base_nav, base_trades)
    candidate_keys = frozen_candidate_keys(scope)
    traded = pd.read_parquet(first / "discovery" / point / SCENARIOS[0] / "trades.parquet")
    episodes = traded.drop_duplicates(["episode_id"])
    traded_key_projection = {
        (str(row.ts_code), str(row.episode_id).rsplit(":", 1)[-1])
        for row in episodes.itertuples(index=False)
    }
    candidate_projection = {(code, signal) for code, signal, _ in candidate_keys}
    adapter = V63Adapter(scope, OUTPUT_ROOT / "duckdb-tmp-audit")
    preflight = adapter.preflight()
    sealed = _read_json(PREFLIGHT_PATH)
    expected_verdict = (
        "GO_TS_V6_3_DRAFT_SEPARATE_HOLDOUT_PROTOCOL_ONLY"
        if gate["passed"]
        else "REJECT_TS_V6_3_RANKED_SUBSET_DISCOVERY"
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
        "traded_episodes_within_frozen_94": traded_key_projection <= candidate_projection,
        "holdout_unopened": report.get("holdout_outcomes_opened") is False
        and not (first / "holdout").exists(),
        "attempt_count": report.get("strategy_effect_attempt_count") == 1,
        "authority": report.get("production_authorization") == "none"
        and report.get("verdict") == expected_verdict,
    }
    verdict = "PASS" if all(checks.values()) else "FAIL"
    audit = {
        "schema_version": "ts-v6-3-ranked-subset-effect-independent-audit-v1",
        "protocol_sha256": scope.sha256,
        "report_sha256": sha256_file(REPORT_PATH),
        "checks": checks,
        "independent_recomputed_payload_sha256": hashlib.sha256(
            canonical_json({"gate": gate, "verdict": expected_verdict})
        ).hexdigest(),
        "post_entry_outcome_read_by_auditor": "recomputed_from_sealed_artifacts_only",
        "holdout_outcomes_read": False,
        "strategy_effective": report.get("strategy_effective"),
        "production_authorization": "none",
        "independent_audit": verdict,
    }
    write_once_json(AUDIT_PATH, audit)
    if verdict != "PASS":
        raise V63Error("TS-v6-3 independent audit failed")
    return audit
