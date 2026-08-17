"""One-shot R3G-2 effect runner with discovery-first holdout firewall."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from shaiwei.research.trend_swing.r3g2.contract import EffectProtocol, R3G2Error
from shaiwei.research.trend_swing.r3g2.effect_artifacts import save_simulation, seal_pass
from shaiwei.research.trend_swing.r3g2.effect_authority import load_effect_authority
from shaiwei.research.trend_swing.r3g2.effect_execution import simulate
from shaiwei.research.trend_swing.r3g2.effect_inputs import RealInputAdapter
from shaiwei.research.trend_swing.r3g2.effect_metrics import evaluate_partition, summarize
from shaiwei.research.trend_swing.r3g2.effect_models import SCENARIOS, scenario
from shaiwei.research.trend_swing.r3g2.evidence import write_once_json


AdapterFactory = Callable[[EffectProtocol, Path], RealInputAdapter]
PassRunner = Callable[[Path, EffectProtocol, RealInputAdapter], dict[str, Any]]


def _empty(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    if any(root.iterdir()):
        raise R3G2Error("R3G-2 effect output exists before the approved one-shot run")


def _frame(rows: tuple[dict[str, Any], ...]) -> pd.DataFrame:
    return pd.DataFrame(list(rows))


def execute_partition(
    root: Path,
    protocol: EffectProtocol,
    adapter: RealInputAdapter,
    partition: str,
) -> dict[str, Any]:
    prepared = adapter.load_partition(partition)
    summaries: dict[str, dict[str, dict[str, Any]]] = {}
    base_nav: dict[str, pd.DataFrame] = {}
    point_artifacts: dict[str, Any] = {}
    for point_hash in protocol.selected_point_hashes:
        events = prepared.events.loc[prepared.events["point_hash"].eq(point_hash)].copy()
        if events.empty:
            raise R3G2Error(f"R3G-2 {partition} point events are empty")
        summaries[point_hash], point_artifacts[point_hash] = {}, {}
        for scenario_name in SCENARIOS:
            result = simulate(
                events=events,
                bars=prepared.bars,
                benchmark=prepared.benchmark,
                calendar=prepared.calendar,
                current=scenario(scenario_name),
            )
            nav, orders, trades = _frame(result.nav_rows), _frame(result.order_rows), _frame(
                result.trade_rows
            )
            summary = summarize(
                nav, orders, trades, blocked_reason=result.blocked_reason
            )
            summaries[point_hash][scenario_name] = summary
            point_artifacts[point_hash][scenario_name] = save_simulation(
                root / partition / point_hash / scenario_name, result, summary
            )
            if scenario_name == SCENARIOS[0]:
                base_nav[point_hash] = nav
    gate = evaluate_partition(
        summaries, base_nav, protocol.document, partition=partition
    )
    document = {
        "schema_version": "ts-v5-r3g2-partition-effect-v1",
        "partition": partition,
        "points": summaries,
        "artifacts": point_artifacts,
        "gate": gate,
        "production_authorization": "none",
    }
    write_once_json(root / partition / "partition_summary.json", document)
    return document


def execute_pass(
    root: Path,
    protocol: EffectProtocol,
    adapter: RealInputAdapter,
) -> dict[str, Any]:
    discovery = execute_partition(root, protocol, adapter, "discovery")
    holdout = None
    if discovery["gate"]["passed"]:
        holdout = execute_partition(root, protocol, adapter, "holdout")
    verdict = (
        discovery["gate"]["verdict"]
        if holdout is None
        else holdout["gate"]["verdict"]
    )
    summary = {
        "schema_version": "ts-v5-r3g2-effect-pass-summary-v1",
        "effect_protocol_sha256": protocol.sha256,
        "discovery_gate": discovery["gate"],
        "holdout_gate": None if holdout is None else holdout["gate"],
        "holdout_outcomes_opened": holdout is not None,
        "strategy_effect_attempt_count": 3,
        "verdict": verdict,
        "strategy_effective": "NOT_YET_INDEPENDENTLY_AUDITED",
        "production_authorization": "none",
    }
    sealed = seal_pass(root, summary)
    return {**sealed, "verdict": verdict, "holdout_outcomes_opened": holdout is not None}


def run(
    *,
    release_path: Path,
    approval_path: Path,
    output_root: Path,
    temporary_root: Path,
    adapter_factory: AdapterFactory = RealInputAdapter,
    pass_runner: PassRunner = execute_pass,
) -> dict[str, Any]:
    protocol = EffectProtocol.load()
    release, approval = load_effect_authority(release_path, approval_path, protocol)
    runtime = release.verify_runtime()
    _empty(output_root)
    effect_started = False
    try:
        adapter = adapter_factory(protocol, temporary_root)
        preflight = adapter.preflight()
        from shaiwei.research.trend_swing.r3g2.effect_control import canonical_sha256

        if canonical_sha256(preflight) != release.scope["inputs"]["pre_effect_preflight_sha256"]:
            raise R3G2Error("R3G-2 pre-effect key preflight identity differs")
        write_once_json(
            output_root / "authorization.json",
            {
                "schema_version": "ts-v5-r3g2-effect-run-authorization-v1",
                "release_scope_sha256": release.sha256,
                "approval_sha256": approval.sha256,
                "action": approval.document["action"],
                "production_authorization": "none",
            },
        )
        write_once_json(
            output_root / "effect_read_started.json",
            {
                "release_scope_sha256": release.sha256,
                "strategy_effect_attempt_count": 3,
                "discovery_first_holdout_firewall": True,
                "same_release_retry_authorized": False,
            },
        )
        effect_started = True
        first = pass_runner(output_root / "first_pass", protocol, adapter)
        replay = pass_runner(output_root / "replay", protocol, adapter)
        comparable = ("bundle_sha256", "summary_sha256", "verdict", "holdout_outcomes_opened")
        if any(first[key] != replay[key] for key in comparable):
            raise R3G2Error("R3G-2 first pass and replay differ")
        report = {
            "schema_version": "ts-v5-r3g2-effect-report-v1",
            "release_scope_sha256": release.sha256,
            "approval_sha256": approval.sha256,
            "runtime_identity": runtime,
            "pre_effect_key_preflight": preflight,
            "first_pass": first,
            "replay": replay,
            "deterministic_replay": True,
            "strategy_effect_attempt_count": 3,
            "holdout_outcomes_opened": first["holdout_outcomes_opened"],
            "verdict": first["verdict"],
            "strategy_effective": "PENDING_INDEPENDENT_AUDIT",
            "production_authorization": "none",
        }
        digest, reused = write_once_json(output_root / "report.json", report)
        return {
            "report_sha256": digest, "reused": reused, "verdict": report["verdict"],
            "strategy_effective": report["strategy_effective"],
            "production_authorization": "none",
        }
    except Exception as error:
        write_once_json(
            output_root / "failure.json",
            {
                "schema_version": "ts-v5-r3g2-effect-failure-v1",
                "release_scope_sha256": release.sha256,
                "approval_sha256": approval.sha256,
                "effect_read_started": effect_started,
                "strategy_effect_attempt_count": 3 if effect_started else 0,
                "same_release_retry_authorized": False,
                "error_type": type(error).__name__,
                "error_message": str(error)[:500],
                "strategy_effective": "NOT_EVALUATED",
                "production_authorization": "none",
            },
        )
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--approval", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--temporary-root", type=Path, required=True)
    args = vars(parser.parse_args())
    args["release_path"] = args.pop("release")
    args["approval_path"] = args.pop("approval")
    print(json.dumps(run(**args), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
