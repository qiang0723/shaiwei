"""Run the single preregistered real P2-2 decision and its deterministic replay."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from shaiwei.config import PROJECT_ROOT
from shaiwei.ledger import (
    append_p2_star50_effect_admission,
    append_p2_star50_effect_run,
    sha256_file,
)

from tools.p2_star50_effect.contract import (
    EffectGateFailure,
    PROTOCOL_PATH,
    canonical_sha256,
    load_protocol,
    training_code_sha256,
    verify_frozen_inputs,
    verify_pushed_clean_freeze,
)
from tools.p2_star50_effect.executor import ExecutionResult, execute_period
from tools.p2_star50_effect.metrics import diversification_metrics, judge_effect, net_excess_return
from tools.p2_star50_effect.model import train_window


SCENARIOS = {
    "base": (1.0, 0.0),
    "cost_1_5x": (1.5, 0.0),
    "cost_2x": (2.0, 0.0),
    "extra_slippage": (1.0, 0.001),
}


def _frame_hash(frame: pd.DataFrame, sort_columns: list[str]) -> str:
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
    return {"path": path.relative_to(PROJECT_ROOT).as_posix(), "sha256": sha256_file(path), "rows": len(frame)}


def _save_execution(result: ExecutionResult, root: Path, name: str) -> dict[str, Any]:
    return {
        "daily": _write_frame(result.daily, root / f"{name}_daily.parquet"),
        "holdings": _write_frame(result.holdings, root / f"{name}_holdings.parquet"),
        "trades": _write_frame(result.trades, root / f"{name}_trades.parquet"),
        "canonical": {
            "daily": _frame_hash(result.daily, ["trade_date"]),
            "holdings": _frame_hash(result.holdings, ["trade_date", "ts_code"]),
            "trades": _frame_hash(result.trades, ["trade_date", "ts_code", "side"]),
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
    window_by_name = {row["name"]: row for row in protocol["evaluation"]["windows"]}
    pressure_by_window = {
        row["frozen_model_window"]: row for row in protocol["evaluation"]["pressure_periods"]
    }
    models: dict[str, Any] = {}
    window_metrics: list[dict[str, Any]] = []
    pressure_metrics: list[dict[str, Any]] = []
    all_daily: dict[str, list[pd.DataFrame]] = {name: [] for name in SCENARIOS}
    base_holdings: list[pd.DataFrame] = []
    artifact_canonical: dict[str, Any] = {}

    for window_name in ("STAR-W1", "STAR-W2", "STAR-W3"):
        window = window_by_name[window_name]
        pressure = pressure_by_window[window_name]
        trained = train_window(
            protocol=protocol,
            window=window,
            pressure=pressure,
            pass_root=pass_root / "models",
        )
        models[window_name] = {
            "model_sha256": trained["model_sha256"],
            "prediction_hashes": trained["prediction_hashes"],
            "metadata": trained["metadata"],
            "metadata_sha256": trained["metadata_sha256"],
        }
        scenario_metrics: dict[str, dict[str, Any]] = {}
        artifact_canonical[window_name] = {}
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
            artifact_canonical[window_name][scenario] = saved["canonical"]
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
        pressure_saved = _save_execution(
            pressure_execution,
            pass_root / "executions" / window_name,
            f"pressure_{pressure['name']}",
        )
        artifact_canonical[window_name][f"pressure_{pressure['name']}"] = pressure_saved["canonical"]
        pressure_metrics.append(
            {
                "period": pressure["name"],
                "frozen_model_window": window_name,
                "trade_days": int(pressure_execution.metrics["trade_days"]),
                "rebalance_count": int(pressure_execution.metrics["rebalance_count"]),
                "base_net_excess": float(pressure_execution.metrics["net_excess"]),
                "base_maximum_drawdown": float(pressure_execution.metrics["maximum_drawdown"]),
            }
        )

    pooled: dict[str, Any] = {}
    pooled_frames: dict[str, pd.DataFrame] = {}
    for scenario, frames in all_daily.items():
        daily = pd.concat(frames, ignore_index=True).sort_values("trade_date").reset_index(drop=True)
        if daily["trade_date"].duplicated().any():
            raise EffectGateFailure(f"pooled OOS dates overlap in scenario {scenario}")
        pooled_frames[scenario] = daily
        pooled[f"{scenario}_net_excess"] = net_excess_return(
            daily["daily_net_return"], daily["benchmark_return"]
        )
    pooled_summary = {
        "trade_days": int(len(pooled_frames["base"])),
        "base_net_excess": float(pooled["base_net_excess"]),
        "cost_1_5x_net_excess": float(pooled["cost_1_5x_net_excess"]),
        "double_cost_net_excess": float(pooled["cost_2x_net_excess"]),
        "extra_slippage_net_excess": float(pooled["extra_slippage_net_excess"]),
    }
    holdings = pd.concat(base_holdings, ignore_index=True)
    return {
        "models": models,
        "window_metrics": window_metrics,
        "pressure_metrics": pressure_metrics,
        "pooled": pooled_summary,
        "pooled_base_daily": pooled_frames["base"],
        "base_holdings": holdings,
        "canonical": {
            "models": canonical_sha256(
                {
                    name: {
                        "model_sha256": row["model_sha256"],
                        "prediction_hashes": row["prediction_hashes"],
                    }
                    for name, row in models.items()
                }
            ),
            "executions": canonical_sha256(artifact_canonical),
            "pooled_base_daily": _frame_hash(pooled_frames["base"], ["trade_date"]),
            "base_holdings": _frame_hash(holdings, ["trade_date", "ts_code"]),
        },
    }


def _append_ledgers(report: dict[str, Any], report_sha256: str, protocol: dict[str, Any]) -> None:
    decision = report["decision"]
    append_p2_star50_effect_run(
        run_id=report["run_id"],
        protocol_frozen_at=str(protocol["frozen_at"]),
        run_started_at=report["run_started_at"],
        run_finished_at=report["run_finished_at"],
        research_family=protocol["identity"]["research_family"],
        protocol_sha256=report["protocol_sha256"],
        freeze_commit=report["freeze_commit"],
        input_manifest_sha256=report["input_manifest_sha256"],
        training_code_sha256=report["training_code_sha256"],
        model_bundle_sha256=report["artifact_hashes"]["model_bundle_sha256"],
        prediction_bundle_sha256=report["artifact_hashes"]["prediction_bundle_sha256"],
        nav_bundle_sha256=report["artifact_hashes"]["nav_bundle_sha256"],
        holding_bundle_sha256=report["artifact_hashes"]["holding_bundle_sha256"],
        determinism_pass=str(decision["determinism_pass"]).lower(),
        window_gate_pass=str(decision["window_gate_pass"]).lower(),
        cost_gate_pass=str(decision["cost_gate_pass"]).lower(),
        drawdown_gate_pass=str(decision["drawdown_gate_pass"]).lower(),
        diversification_gate_status=decision["diversification_gate_status"],
        historical_effect_gate=decision["historical_effect_gate"],
        strategy_results_inspected="true",
        strategy_effective=decision["strategy_effective"],
        production_authorization="none",
        effect_report_sha256=report_sha256,
        operator="p2-star50-effect",
    )
    append_p2_star50_effect_admission(
        decision_id=f"{report['run_id']}-historical-decision",
        protocol_frozen_at=str(protocol["frozen_at"]),
        evaluated_at=report["evaluated_at"],
        research_family=protocol["identity"]["research_family"],
        protocol_sha256=report["protocol_sha256"],
        decision=f"P2_2_{decision['historical_effect_gate']}",
        window_gate_pass=str(decision["window_gate_pass"]).lower(),
        cost_gate_pass=str(decision["cost_gate_pass"]).lower(),
        drawdown_gate_pass=str(decision["drawdown_gate_pass"]).lower(),
        diversification_gate_status=decision["diversification_gate_status"],
        determinism_pass=str(decision["determinism_pass"]).lower(),
        historical_effect_gate=decision["historical_effect_gate"],
        strategy_effective=decision["strategy_effective"],
        strategy_results_inspected="true",
        production_authorization="none",
        reason=(
            "historical gates passed; forward-only review remains separately gated"
            if decision["historical_effect_gate"] == "GO"
            else "frozen historical effect contract did not pass; no production authorization"
        ),
        effect_report_sha256=report_sha256,
        operator="p2-star50-effect",
    )


def _tracked_manifest(report: dict[str, Any], report_sha256: str) -> dict[str, Any]:
    protocol = load_protocol()
    return {
        "schema_version": "p2-star50-effect-manifest-v1",
        "research_family": protocol["identity"]["research_family"],
        "freeze_commit": report["freeze_commit"],
        "protocol_sha256": report["protocol_sha256"],
        "input_manifest_sha256": report["input_manifest_sha256"],
        "training_code_sha256": report["training_code_sha256"],
        "effect_report": {
            "path": protocol["identity"]["result_report"],
            "sha256": report_sha256,
        },
        "artifact_hashes": report["artifact_hashes"],
        "window_metrics": report["window_metrics"],
        "pressure_metrics": report["pressure_metrics"],
        "pooled": report["pooled"],
        "diversification": report["diversification"],
        "decision": report["decision"],
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
        report = json.loads(report_path.read_text(encoding="utf-8"))
        report_sha256 = sha256_file(report_path)
        _append_ledgers(report, report_sha256, protocol)
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
        raise EffectGateFailure("P2-2 input contains forbidden .BJ securities")

    first = _run_pass(
        protocol=protocol,
        pass_name="first_pass",
        result_root=result_root,
        market=market,
        member_days=member_days,
        benchmark=benchmark,
    )
    verify_frozen_inputs(protocol)
    second = _run_pass(
        protocol=protocol,
        pass_name="determinism_replay",
        result_root=result_root,
        market=market,
        member_days=member_days,
        benchmark=benchmark,
    )
    determinism = {
        "model_bundle_equal": first["canonical"]["models"] == second["canonical"]["models"],
        "execution_bundle_equal": first["canonical"]["executions"]
        == second["canonical"]["executions"],
        "pooled_nav_equal": first["canonical"]["pooled_base_daily"]
        == second["canonical"]["pooled_base_daily"],
        "holding_bundle_equal": first["canonical"]["base_holdings"]
        == second["canonical"]["base_holdings"],
    }
    determinism_pass = all(determinism.values())

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
    run_id = f"p2-star50-effect-v1-{inputs['input_manifest_sha256'][:12]}"
    report = {
        "schema_version": "p2-star50-effect-report-v1",
        "run_id": run_id,
        "research_family": protocol["identity"]["research_family"],
        "protocol_frozen_at": protocol["frozen_at"],
        "run_started_at": run_started_at,
        "run_finished_at": finished_at,
        "evaluated_at": finished_at,
        "freeze_commit": freeze_commit,
        "protocol_sha256": protocol_sha,
        "input_manifest_sha256": inputs["input_manifest_sha256"],
        "training_code_sha256": training_code_sha256(),
        "upstream_reports_recalculated": False,
        "model_runtime": {
            name: row["metadata"] for name, row in first["models"].items()
        },
        "window_metrics": first["window_metrics"],
        "pressure_metrics": first["pressure_metrics"],
        "pooled": first["pooled"],
        "diversification": diversification,
        "determinism": determinism,
        "decision": decision,
        "artifact_hashes": {
            "model_bundle_sha256": first["canonical"]["models"],
            "prediction_bundle_sha256": canonical_sha256(
                {name: row["prediction_hashes"] for name, row in first["models"].items()}
            ),
            "nav_bundle_sha256": first["canonical"]["executions"],
            "holding_bundle_sha256": first["canonical"]["base_holdings"],
            "determinism_replay_bundle_sha256": canonical_sha256(second["canonical"]),
        },
        "strategy_results_inspected": True,
        "historical_effect_gate": decision["historical_effect_gate"],
        "strategy_effective": decision["strategy_effective"],
        "production_authorization": "none",
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
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
                "historical_effect_gate": report["historical_effect_gate"],
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
