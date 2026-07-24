"""Run the single P2-2C method correction and one deterministic replay."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from shaiwei.config import PROJECT_ROOT
from shaiwei.ledger import (
    append_p2_star50_effect_correction_admission,
    append_p2_star50_effect_correction_run,
    sha256_file,
)
from tools.p2_star50_effect.metrics import diversification_metrics, judge_effect, net_excess_return
from tools.p2_star50_effect_correction.audit import (
    label_maturity_audit,
    member_listing_lead_audit,
    opening_flag_audit,
    original_capacity_audit,
)
from tools.p2_star50_effect_correction.calendar import official_calendar
from tools.p2_star50_effect_correction.contract import (
    PROTOCOL_PATH,
    CorrectionGateFailure,
    canonical_sha256,
    correction_code_sha256,
    load_protocol,
    verify_frozen_inputs,
    verify_pushed_clean_freeze,
)
from tools.p2_star50_effect_correction.executor import ExecutionResult, execute_period
from tools.p2_star50_effect_correction.model import train_window


SCENARIOS = {
    "base": (1.0, 0.0),
    "cost_1_5x": (1.5, 0.0),
    "cost_2x": (2.0, 0.0),
    "extra_slippage": (1.0, 0.001),
}


def frame_hash(frame: pd.DataFrame, sort_columns: list[str]) -> str:
    ordered = frame.sort_values(sort_columns).reset_index(drop=True) if len(frame) else frame.copy()
    records: list[dict[str, Any]] = []
    for row in ordered.to_dict("records"):
        normalized: dict[str, Any] = {}
        for key, value in row.items():
            if isinstance(value, (float, np.floating)):
                normalized[key] = None if pd.isna(value) else float(value).hex()
            elif isinstance(value, (int, np.integer)):
                normalized[key] = int(value)
            elif pd.isna(value):
                normalized[key] = None
            else:
                normalized[key] = str(value)
        records.append(normalized)
    return canonical_sha256(records)


def _write_frame(frame: pd.DataFrame, path: Path) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(path, index=False, compression="zstd")
    return {
        "path": path.relative_to(PROJECT_ROOT).as_posix(),
        "sha256": sha256_file(path),
        "rows": len(frame),
    }


def _save_execution(result: ExecutionResult, root: Path, name: str) -> dict[str, Any]:
    return {
        "daily": _write_frame(result.daily, root / f"{name}_daily.parquet"),
        "holdings": _write_frame(result.holdings, root / f"{name}_holdings.parquet"),
        "trades": _write_frame(result.trades, root / f"{name}_trades.parquet"),
        "canonical": {
            "daily": frame_hash(result.daily, ["trade_date"]),
            "holdings": frame_hash(result.holdings, ["trade_date", "ts_code"]),
            "trades": frame_hash(result.trades, ["trade_date", "ts_code", "side"]),
        },
    }


def _run_pass(
    *,
    protocol: dict[str, Any],
    pass_name: str,
    result_root: Path,
    market: pd.DataFrame,
    member_days: pd.DataFrame,
    benchmark: pd.DataFrame,
) -> dict[str, Any]:
    pass_root = result_root / pass_name
    calendar = official_calendar(benchmark)
    window_by_name = {row["name"]: row for row in protocol["evaluation"]["windows"]}
    pressure_by_window = {
        row["frozen_model_window"]: row for row in protocol["evaluation"]["pressure_periods"]
    }
    models: dict[str, Any] = {}
    window_metrics: list[dict[str, Any]] = []
    pressure_metrics: list[dict[str, Any]] = []
    all_daily: dict[str, list[pd.DataFrame]] = {name: [] for name in SCENARIOS}
    base_holdings: list[pd.DataFrame] = []
    canonical_daily: dict[str, Any] = {}
    canonical_trades: dict[str, Any] = {}
    canonical_holdings: dict[str, Any] = {}
    comparable_physical: dict[str, str] = {}

    for window_name in ("STAR-W1", "STAR-W2", "STAR-W3"):
        window = window_by_name[window_name]
        pressure = pressure_by_window[window_name]
        trained = train_window(
            protocol=protocol,
            window=window,
            pressure=pressure,
            calendar=calendar,
            pass_root=pass_root / "models",
        )
        models[window_name] = {
            "model_sha256": trained["model_sha256"],
            "prediction_hashes": trained["prediction_hashes"],
            "prediction_file_hashes": trained["prediction_file_hashes"],
            "metadata": trained["metadata"],
            "metadata_sha256": trained["metadata_sha256"],
        }
        comparable_physical[f"models/{window_name}/model.txt"] = trained["model_sha256"]
        for kind, digest in trained["prediction_file_hashes"].items():
            comparable_physical[f"models/{window_name}/{kind}_predictions.parquet"] = digest

        scenario_metrics: dict[str, dict[str, Any]] = {}
        canonical_daily[window_name] = {}
        canonical_trades[window_name] = {}
        canonical_holdings[window_name] = {}
        for scenario, (multiplier, extra) in SCENARIOS.items():
            execution = execute_period(
                predictions=trained["predictions"]["test"],
                market=market,
                member_days=member_days,
                benchmark=benchmark,
                start=window["test"][0],
                end=window["test"][1],
                cost_multiplier=multiplier,
                extra_slippage_each_side=extra,
                protocol=protocol,
            )
            saved = _save_execution(execution, pass_root / "executions" / window_name, scenario)
            canonical_daily[window_name][scenario] = saved["canonical"]["daily"]
            canonical_trades[window_name][scenario] = saved["canonical"]["trades"]
            canonical_holdings[window_name][scenario] = saved["canonical"]["holdings"]
            for kind in ("daily", "holdings", "trades"):
                comparable_physical[
                    f"executions/{window_name}/{scenario}_{kind}.parquet"
                ] = saved[kind]["sha256"]
            daily = execution.daily.copy()
            daily["window"] = window_name
            all_daily[scenario].append(daily)
            scenario_metrics[scenario] = execution.metrics
            if scenario == "base":
                holdings = execution.holdings.copy()
                holdings["window"] = window_name
                base_holdings.append(holdings)

        base = scenario_metrics["base"]
        window_metrics.append(
            {
                "window": window_name,
                "trade_days": int(base["trade_days"]),
                "rebalance_count": int(base["rebalance_count"]),
                "base_net_excess": float(base["net_excess"]),
                "cost_1_5x_net_excess": float(scenario_metrics["cost_1_5x"]["net_excess"]),
                "double_cost_net_excess": float(scenario_metrics["cost_2x"]["net_excess"]),
                "extra_slippage_net_excess": float(scenario_metrics["extra_slippage"]["net_excess"]),
                "base_maximum_drawdown": float(base["maximum_drawdown"]),
                "base_strategy_return": float(base["strategy_return"]),
                "benchmark_return": float(base["benchmark_return"]),
                "base_trade_count": int(base["trade_count"]),
                "base_cost_rmb": float(base["cost_rmb"]),
                "maximum_capacity_utilization": float(base["maximum_capacity_utilization"]),
                "blocked_invalid_execution_bar_count": int(
                    base["blocked_invalid_execution_bar_count"]
                ),
                "blocked_open_limit_count": int(base["blocked_open_limit_count"]),
                "blocked_sell_capacity_count": int(base["blocked_sell_capacity_count"]),
                "minimum_selected_names": int(base["minimum_selected_names"]),
                "maximum_selected_names": int(base["maximum_selected_names"]),
            }
        )

        pressure_execution = execute_period(
            predictions=trained["predictions"]["pressure"],
            market=market,
            member_days=member_days,
            benchmark=benchmark,
            start=pressure["start"],
            end=pressure["end"],
            cost_multiplier=1.0,
            extra_slippage_each_side=0.0,
            protocol=protocol,
        )
        pressure_name = f"pressure_{pressure['name']}"
        saved = _save_execution(
            pressure_execution,
            pass_root / "executions" / window_name,
            pressure_name,
        )
        canonical_daily[window_name][pressure_name] = saved["canonical"]["daily"]
        canonical_trades[window_name][pressure_name] = saved["canonical"]["trades"]
        canonical_holdings[window_name][pressure_name] = saved["canonical"]["holdings"]
        for kind in ("daily", "holdings", "trades"):
            comparable_physical[
                f"executions/{window_name}/{pressure_name}_{kind}.parquet"
            ] = saved[kind]["sha256"]
        pressure_metrics.append(
            {
                "period": pressure["name"],
                "frozen_model_window": window_name,
                "trade_days": int(pressure_execution.metrics["trade_days"]),
                "rebalance_count": int(pressure_execution.metrics["rebalance_count"]),
                "base_net_excess": float(pressure_execution.metrics["net_excess"]),
                "base_maximum_drawdown": float(pressure_execution.metrics["maximum_drawdown"]),
                "maximum_capacity_utilization": float(
                    pressure_execution.metrics["maximum_capacity_utilization"]
                ),
            }
        )

    pooled_frames: dict[str, pd.DataFrame] = {}
    pooled_summary: dict[str, Any] = {}
    for scenario, frames in all_daily.items():
        daily = pd.concat(frames, ignore_index=True).sort_values("trade_date").reset_index(drop=True)
        if daily["trade_date"].duplicated().any():
            raise CorrectionGateFailure(f"pooled OOS dates overlap in scenario {scenario}")
        pooled_frames[scenario] = daily
        pooled_summary[f"{scenario}_net_excess"] = net_excess_return(
            daily["daily_net_return"], daily["benchmark_return"]
        )
    pooled = {
        "trade_days": int(len(pooled_frames["base"])),
        "base_net_excess": float(pooled_summary["base_net_excess"]),
        "cost_1_5x_net_excess": float(pooled_summary["cost_1_5x_net_excess"]),
        "double_cost_net_excess": float(pooled_summary["cost_2x_net_excess"]),
        "extra_slippage_net_excess": float(pooled_summary["extra_slippage_net_excess"]),
    }
    holdings = pd.concat(base_holdings, ignore_index=True)
    canonical = {
        "models": canonical_sha256(
            {
                name: {
                    "model_sha256": row["model_sha256"],
                    "prediction_hashes": row["prediction_hashes"],
                }
                for name, row in models.items()
            }
        ),
        "predictions": canonical_sha256(
            {name: row["prediction_hashes"] for name, row in models.items()}
        ),
        "nav": canonical_sha256(canonical_daily),
        "trades": canonical_sha256(canonical_trades),
        "holdings": canonical_sha256(canonical_holdings),
        "pooled_base_daily": frame_hash(pooled_frames["base"], ["trade_date"]),
        "base_holdings": frame_hash(holdings, ["trade_date", "ts_code"]),
    }
    if len(comparable_physical) != 54:
        raise CorrectionGateFailure(
            f"unexpected deterministic artifact count: {len(comparable_physical)}"
        )
    return {
        "models": models,
        "window_metrics": window_metrics,
        "pressure_metrics": pressure_metrics,
        "pooled": pooled,
        "pooled_base_daily": pooled_frames["base"],
        "base_holdings": holdings,
        "canonical": canonical,
        "comparable_physical": comparable_physical,
    }


def _runtime_preflight(
    protocol: dict[str, Any],
    market: pd.DataFrame,
    member_days: pd.DataFrame,
    benchmark: pd.DataFrame,
) -> dict[str, Any]:
    original_root = PROJECT_ROOT / "data/research/star50/p2-star50-effect-v1/first_pass/executions"
    trades = {
        name: pd.read_parquet(original_root / name / "base_trades.parquet")
        for name in ("STAR-W1", "STAR-W2", "STAR-W3")
    }
    quality = {
        "label_maturity": label_maturity_audit(protocol, benchmark),
        "opening_flag_baseline": opening_flag_audit(market, member_days),
        "original_capacity_baseline": original_capacity_audit(
            market,
            benchmark,
            trades,
            protocol["evaluation"]["windows"],
        ),
        "member_listing_lead": member_listing_lead_audit(market, member_days, benchmark),
    }
    expected = protocol["preflight_evidence"]
    capacity = quality["original_capacity_baseline"]
    if capacity["original_sell_capacity_violation_count"] != expected[
        "original_sell_capacity_violation_count"
    ]:
        raise CorrectionGateFailure("original sell-cap violation baseline is not reproducible")
    if abs(
        capacity["original_maximum_sell_capacity_ratio"]
        - float(expected["original_maximum_sell_capacity_ratio"])
    ) > 1e-15:
        raise CorrectionGateFailure("original maximum sell-cap ratio is not reproducible")
    opening = quality["opening_flag_baseline"]
    if (
        opening["all_market"]["buy_flag_mismatch_count"],
        opening["all_market"]["sell_flag_mismatch_count"],
        opening["official"]["buy_flag_mismatch_count"],
        opening["official"]["sell_flag_mismatch_count"],
    ) != (283, 35, 90, 3):
        raise CorrectionGateFailure("open/close execution-flag mismatch baseline drift")
    lead = quality["member_listing_lead"]
    if lead["minimum_first_member_bar_lead_trade_days"] < 74:
        raise CorrectionGateFailure("a member lacks the frozen minimum pre-membership bar lead")
    if lead["missing_first_valid_bar_count"] or lead["forbidden_bj_member_day_count"]:
        raise CorrectionGateFailure("member listing/BJ preflight failed")
    return quality


def _append_ledgers(report: dict[str, Any], report_sha256: str, protocol: dict[str, Any]) -> None:
    decision = report["decision"]
    scope = "|".join(report["correction_scope"])
    append_p2_star50_effect_correction_run(
        run_id=report["run_id"],
        protocol_frozen_at=report["protocol_frozen_at"],
        run_started_at=report["run_started_at"],
        run_finished_at=report["run_finished_at"],
        research_family=report["research_family"],
        protocol_sha256=report["protocol_sha256"],
        freeze_commit=report["freeze_commit"],
        input_manifest_sha256=report["input_manifest_sha256"],
        correction_code_sha256=report["correction_code_sha256"],
        original_p2_2_model_valid="false",
        original_p2_2_execution_valid="false",
        correction_scope=scope,
        results_known_before_correction="true",
        model_retrained="true",
        predictions_recomputed="true",
        model_bundle_sha256=report["artifact_hashes"]["model_bundle_sha256"],
        prediction_bundle_sha256=report["artifact_hashes"]["prediction_bundle_sha256"],
        nav_bundle_sha256=report["artifact_hashes"]["nav_bundle_sha256"],
        trade_bundle_sha256=report["artifact_hashes"]["trade_bundle_sha256"],
        holding_bundle_sha256=report["artifact_hashes"]["holding_bundle_sha256"],
        determinism_pass=str(decision["determinism_pass"]).lower(),
        window_gate_pass=str(decision["window_gate_pass"]).lower(),
        cost_gate_pass=str(decision["cost_gate_pass"]).lower(),
        drawdown_gate_pass=str(decision["drawdown_gate_pass"]).lower(),
        diversification_gate_status=decision["diversification_gate_status"],
        authoritative_historical_effect_gate=decision["historical_effect_gate"],
        strategy_effective=decision["strategy_effective"],
        production_authorization="none",
        effect_report_sha256=report_sha256,
        operator="p2-star50-effect-correction",
    )
    append_p2_star50_effect_correction_admission(
        decision_id=f"{report['run_id']}-authoritative-decision",
        protocol_frozen_at=report["protocol_frozen_at"],
        evaluated_at=report["evaluated_at"],
        research_family=report["research_family"],
        protocol_sha256=report["protocol_sha256"],
        decision=f"P2_2C_{decision['historical_effect_gate']}",
        original_p2_2_model_valid="false",
        original_p2_2_execution_valid="false",
        correction_scope=scope,
        results_known_before_correction="true",
        model_retrained="true",
        predictions_recomputed="true",
        window_gate_pass=str(decision["window_gate_pass"]).lower(),
        cost_gate_pass=str(decision["cost_gate_pass"]).lower(),
        drawdown_gate_pass=str(decision["drawdown_gate_pass"]).lower(),
        diversification_gate_status=decision["diversification_gate_status"],
        determinism_pass=str(decision["determinism_pass"]).lower(),
        authoritative_historical_effect_gate=decision["historical_effect_gate"],
        strategy_effective=decision["strategy_effective"],
        strategy_results_inspected="true",
        production_authorization="none",
        reason=(
            "three audited method defects corrected; all frozen gates passed only for forward review"
            if decision["historical_effect_gate"] == "GO"
            else "three audited method defects corrected; frozen historical contract did not pass"
        ),
        effect_report_sha256=report_sha256,
        operator="p2-star50-effect-correction",
    )


def _tracked_manifest(report: dict[str, Any], report_sha256: str) -> dict[str, Any]:
    protocol = load_protocol()
    return {
        "schema_version": "p2-star50-effect-correction-manifest-v1",
        "research_family": report["research_family"],
        "freeze_commit": report["freeze_commit"],
        "protocol_sha256": report["protocol_sha256"],
        "input_manifest_sha256": report["input_manifest_sha256"],
        "correction_code_sha256": report["correction_code_sha256"],
        "effect_correction_report": {
            "path": protocol["identity"]["result_report"],
            "sha256": report_sha256,
        },
        "original_p2_2_model_valid": False,
        "original_p2_2_execution_valid": False,
        "correction_scope": report["correction_scope"],
        "results_known_before_correction": True,
        "model_retrained": True,
        "predictions_recomputed": True,
        "input_quality": report["input_quality"],
        "artifact_hashes": report["artifact_hashes"],
        "window_metrics": report["window_metrics"],
        "pressure_metrics": report["pressure_metrics"],
        "pooled": report["pooled"],
        "diversification": report["diversification"],
        "decision": report["decision"],
        "authoritative_historical_effect_gate": report["authoritative_historical_effect_gate"],
        "strategy_effective": report["strategy_effective"],
        "ledger": {
            "runs_path": protocol["identity"]["run_ledger"],
            "runs_sha256": sha256_file(PROJECT_ROOT / protocol["identity"]["run_ledger"]),
            "admissions_path": protocol["identity"]["admission_ledger"],
            "admissions_sha256": sha256_file(PROJECT_ROOT / protocol["identity"]["admission_ledger"]),
        },
        "production_authorization": "none",
    }


def run() -> dict[str, Any]:
    protocol = load_protocol()
    report_path = PROJECT_ROOT / protocol["identity"]["result_report"]
    if report_path.is_file():
        verify_frozen_inputs(protocol)
        verify_pushed_clean_freeze(protocol)
        report = json.loads(report_path.read_text(encoding="utf-8"))
        report_sha256 = sha256_file(report_path)
        _append_ledgers(report, report_sha256, protocol)
        manifest = _tracked_manifest(report, report_sha256)
        manifest_path = PROJECT_ROOT / protocol["identity"]["tracked_manifest"]
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return report

    freeze_commit = verify_pushed_clean_freeze(protocol)
    inputs = verify_frozen_inputs(protocol)
    run_started_at = datetime.now(timezone.utc).isoformat()
    result_root = PROJECT_ROOT / protocol["identity"]["result_root"]
    market = pd.read_parquet(PROJECT_ROOT / protocol["identity"]["market_dataset"])
    member_days = pd.read_parquet(PROJECT_ROOT / protocol["identity"]["member_day_dataset"])
    benchmark = pd.read_parquet(PROJECT_ROOT / protocol["identity"]["benchmark_dataset"])
    if market["ts_code"].astype(str).str.endswith(".BJ").any() or member_days["ts_code"].astype(
        str
    ).str.endswith(".BJ").any():
        raise CorrectionGateFailure("P2-2C input contains forbidden .BJ securities")
    input_quality = _runtime_preflight(protocol, market, member_days, benchmark)
    verify_frozen_inputs(protocol)

    first = _run_pass(
        protocol=protocol,
        pass_name="first_pass",
        result_root=result_root,
        market=market,
        member_days=member_days,
        benchmark=benchmark,
    )
    verify_frozen_inputs(protocol)
    replay = _run_pass(
        protocol=protocol,
        pass_name="determinism_replay",
        result_root=result_root,
        market=market,
        member_days=member_days,
        benchmark=benchmark,
    )
    determinism = {
        "model_bundle_equal": first["canonical"]["models"] == replay["canonical"]["models"],
        "prediction_bundle_equal": first["canonical"]["predictions"]
        == replay["canonical"]["predictions"],
        "nav_bundle_equal": first["canonical"]["nav"] == replay["canonical"]["nav"],
        "trade_bundle_equal": first["canonical"]["trades"] == replay["canonical"]["trades"],
        "holding_bundle_equal": first["canonical"]["holdings"]
        == replay["canonical"]["holdings"],
        "pooled_nav_equal": first["canonical"]["pooled_base_daily"]
        == replay["canonical"]["pooled_base_daily"],
        "comparable_physical_artifact_count": len(first["comparable_physical"]),
        "all_comparable_physical_sha256_equal": first["comparable_physical"]
        == replay["comparable_physical"],
    }
    determinism_pass = all(
        value for key, value in determinism.items() if key != "comparable_physical_artifact_count"
    ) and determinism["comparable_physical_artifact_count"] == 54

    base_returns = first["pooled_base_daily"].set_index("trade_date")["daily_net_return"]
    diversification = diversification_metrics(
        base_returns,
        first["base_holdings"],
        comparator=None,
        protocol=protocol,
    )
    decision = judge_effect(
        first["window_metrics"],
        first["pressure_metrics"],
        first["pooled"],
        diversification,
        determinism_pass,
        protocol,
    )
    finished_at = datetime.now(timezone.utc).isoformat()
    protocol_sha = sha256_file(PROTOCOL_PATH)
    run_id = f"p2-star50-effect-correction-v1-{inputs['input_manifest_sha256'][:12]}"
    report = {
        "schema_version": "p2-star50-effect-correction-report-v1",
        "run_id": run_id,
        "research_family": protocol["identity"]["research_family"],
        "protocol_frozen_at": protocol["frozen_at"],
        "run_started_at": run_started_at,
        "run_finished_at": finished_at,
        "evaluated_at": finished_at,
        "freeze_commit": freeze_commit,
        "protocol_sha256": protocol_sha,
        "input_manifest_sha256": inputs["input_manifest_sha256"],
        "correction_code_sha256": correction_code_sha256(),
        "original_p2_2_model_valid": False,
        "original_p2_2_execution_valid": False,
        "original_p2_2_numeric_results_reproducible_but_not_authoritative": True,
        "correction_scope": protocol["correction_scope"],
        "results_known_before_correction": True,
        "model_retrained": True,
        "predictions_recomputed": True,
        "upstream_reports_recalculated": False,
        "original_p2_2_evidence_mutated": False,
        "input_quality": input_quality,
        "model_runtime": {name: row["metadata"] for name, row in first["models"].items()},
        "window_metrics": first["window_metrics"],
        "pressure_metrics": first["pressure_metrics"],
        "pooled": first["pooled"],
        "diversification": diversification,
        "determinism": determinism,
        "decision": decision,
        "corrected_gates": {
            "window_gate_pass": decision["window_gate_pass"],
            "cost_gate_pass": decision["cost_gate_pass"],
            "drawdown_gate_pass": decision["drawdown_gate_pass"],
            "diversification_gate_status": decision["diversification_gate_status"],
            "diversification_gate_pass": decision["diversification_gate_pass"],
            "determinism_pass": decision["determinism_pass"],
        },
        "artifact_hashes": {
            "model_bundle_sha256": first["canonical"]["models"],
            "prediction_bundle_sha256": first["canonical"]["predictions"],
            "nav_bundle_sha256": first["canonical"]["nav"],
            "trade_bundle_sha256": first["canonical"]["trades"],
            "holding_bundle_sha256": first["canonical"]["holdings"],
            "pooled_base_daily_sha256": first["canonical"]["pooled_base_daily"],
            "determinism_replay_bundle_sha256": canonical_sha256(replay["canonical"]),
            "original_p2_2_result_tree_sha256": inputs["original_p2_2_result_tree"][
                "canonical_tree_sha256"
            ],
        },
        "strategy_results_inspected": True,
        "historical_effect_gate": decision["historical_effect_gate"],
        "authoritative_historical_effect_gate": decision["historical_effect_gate"],
        "strategy_effective": decision["strategy_effective"],
        "production_authorization": "none",
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    report_sha256 = sha256_file(report_path)
    _append_ledgers(report, report_sha256, protocol)
    manifest = _tracked_manifest(report, report_sha256)
    manifest_path = PROJECT_ROOT / protocol["identity"]["tracked_manifest"]
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report


def main() -> int:
    report = run()
    print(
        json.dumps(
            {
                "authoritative_historical_effect_gate": report[
                    "authoritative_historical_effect_gate"
                ],
                "strategy_effective": report["strategy_effective"],
                "strategy_results_inspected": report["strategy_results_inspected"],
                "production_authorization": report["production_authorization"],
                "run_id": report["run_id"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
