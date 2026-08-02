"""Build and judge the F1-0R latest-common-period PIT recovery gate."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import duckdb
import numpy as np
import pandas as pd

from shaiwei.config import PROJECT_ROOT
from shaiwei.ingest.catalog import load_latest_api
from shaiwei.ledger import sha256_file
from shaiwei.provenance import git_head
from shaiwei.research.fundamental_pit_contract import (
    FundamentalPitError,
    canonical_json,
    sha256_json,
    verify_source_evidence,
)
from shaiwei.research.fundamental_pit_gate import (
    STATEMENT_FIELDS,
    _canonical_statement,
    _formation_dates,
    _members,
    _open_days,
    _with_availability,
    _write_json_once,
    _write_parquet_once,
)
from shaiwei.research.fundamental_pit_recovery_contract import (
    GO_VERDICT,
    NO_GO_VERDICT,
    FundamentalPitRecoveryProtocol,
    verify_predecessor,
)


def _statement_periods(members: pd.DataFrame, statement: pd.DataFrame, name: str) -> pd.DataFrame:
    connection = duckdb.connect(":memory:")
    try:
        connection.register("members", members[["formation_date", "ts_code"]])
        connection.register("statement", statement)
        fields = ", ".join(f's."{field}"' for field in STATEMENT_FIELDS[name])
        selected = connection.execute(
            f"""
            SELECT m.formation_date, m.ts_code, s.end_date,
                   s.available_date, s.f_ann_date, {fields}
            FROM members m
            JOIN statement s
              ON m.ts_code = s.ts_code AND s.available_date <= m.formation_date
            QUALIFY row_number() OVER (
              PARTITION BY m.formation_date, m.ts_code, s.end_date
              ORDER BY s.f_ann_date DESC,
                       s._report_priority DESC,
                       s._update_priority DESC
            ) = 1
            ORDER BY m.formation_date, m.ts_code, s.end_date
            """
        ).df()
    finally:
        connection.close()
    return selected.rename(
        columns={
            "end_date": f"{name}_end_date",
            "available_date": f"{name}_available_date",
            "f_ann_date": f"{name}_f_ann_date",
            **{field: f"{name}_{field}" for field in STATEMENT_FIELDS[name]},
        }
    )


def _latest_common_period(
    members: pd.DataFrame,
    periods: dict[str, pd.DataFrame],
) -> tuple[pd.DataFrame, pd.Series]:
    join_keys = ["formation_date", "ts_code"]
    common = periods["income"].rename(columns={"income_end_date": "end_date"})
    for name in ("balancesheet", "cashflow"):
        candidate = periods[name].rename(columns={f"{name}_end_date": "end_date"})
        common = common.merge(candidate, on=[*join_keys, "end_date"], how="inner", validate="one_to_one")
    common = common.sort_values([*join_keys, "end_date"]).drop_duplicates(join_keys, keep="last")
    common["income_end_date"] = common["end_date"]
    common["balancesheet_end_date"] = common["end_date"]
    common["cashflow_end_date"] = common["end_date"]
    panel = members.merge(common, on=join_keys, how="left", validate="one_to_one")
    latest_columns = []
    for name, frame in periods.items():
        column = f"latest_{name}_end_date"
        latest = frame.groupby(join_keys, as_index=False)[f"{name}_end_date"].max().rename(
            columns={f"{name}_end_date": column}
        )
        panel = panel.merge(latest, on=join_keys, how="left", validate="one_to_one")
        latest_columns.append(column)
    common_period = panel["end_date"].astype("string").fillna("")
    staggered = pd.Series(False, index=panel.index)
    for column in latest_columns:
        staggered |= panel[column].astype("string").fillna("").gt(common_period)
    return panel, staggered


def _feature_values(panel: pd.DataFrame, feature_ids: list[str]) -> pd.DataFrame:
    result = panel.copy()
    assets = pd.to_numeric(result["balancesheet_total_assets"], errors="coerce")
    revenue = pd.to_numeric(result["income_total_revenue"], errors="coerce")
    valid_common = result["end_date"].notna()
    valid_assets = valid_common & np.isfinite(assets) & assets.gt(0)
    valid_revenue = valid_common & np.isfinite(revenue) & revenue.gt(0)
    income = pd.to_numeric(result["income_n_income_attr_p"], errors="coerce")
    operating = pd.to_numeric(result["income_operate_profit"], errors="coerce")
    cashflow = pd.to_numeric(result["cashflow_n_cashflow_act"], errors="coerce")
    liabilities = pd.to_numeric(result["balancesheet_total_liab"], errors="coerce")
    cash = pd.to_numeric(result["balancesheet_money_cap"], errors="coerce")
    values = (
        (income / assets).where(valid_assets),
        (operating / revenue).where(valid_revenue),
        (cashflow / assets).where(valid_assets),
        (liabilities / assets).where(valid_assets),
        (cash / assets).where(valid_assets),
        ((income - cashflow) / assets).where(valid_assets),
    )
    for feature_id, value in zip(feature_ids, values, strict=True):
        result[feature_id] = value.replace([np.inf, -np.inf], np.nan)
    return result


def build_recovery_panel(
    protocol: FundamentalPitRecoveryProtocol,
    frames: dict[str, pd.DataFrame],
) -> tuple[pd.DataFrame, dict[str, Any]]:
    scope = protocol.document["scope"]
    start = str(scope["start_date"]).replace("-", "")
    quality_start = str(scope["quality_start_date"]).replace("-", "")
    end = str(scope["end_date"]).replace("-", "")
    availability_days = _open_days(frames["tushare.trade_cal"], "19000101", end)
    open_days = [day for day in availability_days if day >= start]
    formations = _formation_dates(open_days)
    members = _members(frames["tushare.index_weight"], formations, str(scope["official_index_code"]))
    if members.empty:
        raise FundamentalPitError("F1-0R has no CSI800 formation members")
    periods: dict[str, pd.DataFrame] = {}
    source_rows: dict[str, int] = {}
    conflict_count = 0
    for name in STATEMENT_FIELDS:
        statement, conflicts = _canonical_statement(
            name,
            [frames[f"tushare.{name}"], frames[f"tushare.{name}_vip"]],
        )
        source_rows[name] = len(statement)
        conflict_count += conflicts
        periods[name] = _statement_periods(
            members,
            _with_availability(statement, availability_days),
            name,
        )
    panel, staggered = _latest_common_period(members, periods)
    available_columns = [f"{name}_available_date" for name in STATEMENT_FIELDS]
    normalized = panel[available_columns].astype("string").fillna("")
    panel["available_date"] = normalized.max(axis=1).replace("", pd.NA).where(panel["end_date"].notna())
    feature_ids = [item.feature_id for item in protocol.features]
    panel = _feature_values(panel, feature_ids)
    quality = panel.loc[panel["formation_date"].ge(quality_start)].copy()
    coverage = {}
    for feature_id in feature_ids:
        by_date = quality.groupby("formation_date")[feature_id].apply(lambda values: float(values.notna().mean()))
        coverage[feature_id] = {
            "aggregate": float(quality[feature_id].notna().mean()),
            "worst_formation": float(by_date.min()) if not by_date.empty else 0.0,
        }
    future = pd.Series(False, index=panel.index)
    for column in available_columns:
        future |= panel[column].astype("string").fillna("").gt(panel["formation_date"].astype("string"))
    component_periods = panel[[f"{name}_end_date" for name in STATEMENT_FIELDS]]
    constructed_mixed = component_periods.notna().all(axis=1) & component_periods.nunique(axis=1).gt(1)
    quality_mask = panel["formation_date"].ge(quality_start)
    diagnostics = {
        "open_day_count": len(open_days),
        "open_day_first": open_days[0],
        "open_day_last": open_days[-1],
        "formation_count": len(formations),
        "quality_formation_count": int(quality["formation_date"].nunique()),
        "member_rows": len(panel),
        "membership_min": int(quality.groupby("formation_date")["ts_code"].nunique().min()),
        "membership_max": int(quality.groupby("formation_date")["ts_code"].nunique().max()),
        "security_count": int(panel["ts_code"].nunique()),
        "bse_rows": int(panel["ts_code"].astype(str).str.endswith(".BJ").sum()),
        "constructed_mixed_component_period_rows": int(constructed_mixed.sum()),
        "quality_no_common_period_rows": int((quality_mask & panel["end_date"].isna()).sum()),
        "newer_unmatched_statement_rows": int(staggered.sum()),
        "quality_newer_unmatched_statement_rows": int((staggered & quality_mask).sum()),
        "future_availability_rows": int(future.sum()),
        "source_identity_conflicts": conflict_count,
        "canonical_annual_rows": source_rows,
        "coverage": coverage,
    }
    keep = ["formation_date", "ts_code", "membership_snapshot_date", "end_date", "available_date", *feature_ids]
    return panel.loc[:, keep].sort_values(["formation_date", "ts_code"]).reset_index(drop=True), diagnostics


def _gate_results(protocol: FundamentalPitRecoveryProtocol, diagnostics: dict[str, Any]) -> dict[str, bool]:
    gates = protocol.document["gates"]
    count_gate = gates["membership_count_each_formation"]
    coverage = diagnostics["coverage"]
    return {
        "predecessor_identity_preserved": True,
        "calendar_scope": diagnostics["open_day_first"] <= "20160104"
        and diagnostics["open_day_last"] == "20260731",
        "formation_count": diagnostics["quality_formation_count"]
        >= int(str(gates["formation_dates_after_quality_start"]).split("_")[-1]),
        "membership_count": diagnostics["membership_min"] >= int(count_gate["minimum"])
        and diagnostics["membership_max"] <= int(count_gate["maximum"]),
        "bse_absent": diagnostics["bse_rows"] == int(gates["bse_rows"]),
        "no_constructed_mixed_periods": diagnostics["constructed_mixed_component_period_rows"]
        == int(gates["constructed_mixed_component_period_rows"]),
        "quality_common_period_complete": diagnostics["quality_no_common_period_rows"]
        == int(gates["quality_no_common_period_rows"]),
        "no_future_availability": diagnostics["future_availability_rows"]
        == int(gates["future_availability_rows"]),
        "no_source_conflicts": diagnostics["source_identity_conflicts"]
        == int(gates["source_identity_conflicts"]),
        "aggregate_coverage": all(
            value["aggregate"] >= float(gates["feature_aggregate_coverage_minimum"])
            for value in coverage.values()
        ),
        "worst_formation_coverage": all(
            value["worst_formation"] >= float(gates["feature_worst_formation_coverage_minimum"])
            for value in coverage.values()
        ),
    }


def run(
    protocol: FundamentalPitRecoveryProtocol,
    *,
    project_root: Path = PROJECT_ROOT,
    manifest_output: Path | None = None,
) -> dict[str, Any]:
    predecessor = verify_predecessor(protocol, project_root=project_root)
    source_evidence = verify_source_evidence(protocol)
    frames = {source_api: load_latest_api(source_api) for source_api in protocol.required_apis}
    panel, diagnostics = build_recovery_panel(protocol, frames)
    gates = _gate_results(protocol, diagnostics)
    verdict = GO_VERDICT if all(gates.values()) else NO_GO_VERDICT
    input_identity = sha256_json(
        {"protocol_sha256": protocol.sha256, "predecessor": predecessor, "sources": source_evidence}
    )
    code_identity = sha256_json(
        {
            name: sha256_file(project_root / path)
            for name, path in {
                "v1_contract": "src/shaiwei/research/fundamental_pit_contract.py",
                "v1_gate_helpers": "src/shaiwei/research/fundamental_pit_gate.py",
                "recovery_contract": "src/shaiwei/research/fundamental_pit_recovery_contract.py",
                "recovery_gate": "src/shaiwei/research/fundamental_pit_recovery_gate.py",
            }.items()
        }
    )
    feature_path = protocol.project_path("ignored_feature_panel", project_root=project_root)
    feature_sha = _write_parquet_once(feature_path, panel)
    report = {
        "schema_version": "f1-csi800-fundamental-pit-recovery-report-v2",
        "protocol_id": protocol.document["protocol_id"],
        "protocol_sha256": protocol.sha256,
        "input_snapshot_sha256": input_identity,
        "code_snapshot_sha256": code_identity,
        "code_git_head": git_head(),
        "predecessor": predecessor,
        "source_evidence": source_evidence,
        "diagnostics": diagnostics,
        "gates": gates,
        "feature_panel": {"row_count": len(panel), "sha256": feature_sha},
        "factor_results_inspected": False,
        "model_training_run": False,
        "backtest_run": False,
        "deepseek_calls": 0,
        "strategy_effective": "NOT_EVALUATED",
        "production_authorization": "none",
        "verdict": verdict,
    }
    report_path = protocol.project_path("ignored_report", project_root=project_root)
    report_sha = _write_json_once(report_path, report)
    manifest = {
        "schema_version": "f1-csi800-fundamental-pit-recovery-manifest-v2",
        "protocol_id": protocol.document["protocol_id"],
        "protocol_sha256": protocol.sha256,
        "input_snapshot_sha256": input_identity,
        "code_snapshot_sha256": code_identity,
        "code_git_head": git_head(),
        "predecessor": predecessor,
        "report": {"path": report_path.relative_to(project_root).as_posix(), "sha256": report_sha},
        "feature_panel": {
            "path": feature_path.relative_to(project_root).as_posix(),
            "row_count": len(panel),
            "sha256": feature_sha,
        },
        "diagnostic_counts": {
            key: diagnostics[key]
            for key in (
                "quality_no_common_period_rows",
                "newer_unmatched_statement_rows",
                "quality_newer_unmatched_statement_rows",
                "constructed_mixed_component_period_rows",
                "future_availability_rows",
            )
        },
        "gates": gates,
        "coverage": diagnostics["coverage"],
        "factor_results_inspected": False,
        "strategy_effective": "NOT_EVALUATED",
        "production_authorization": "none",
        "verdict": verdict,
    }
    _write_json_once(
        manifest_output or protocol.project_path("tracked_manifest", project_root=project_root),
        manifest,
    )
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--protocol",
        type=Path,
        default=PROJECT_ROOT / "config/f1_csi800_fundamental_pit_recovery_v2.yaml",
    )
    parser.add_argument("--manifest-output", type=Path, default=None)
    args = parser.parse_args(argv)
    try:
        result = run(FundamentalPitRecoveryProtocol.load(args.protocol), manifest_output=args.manifest_output)
    except (FundamentalPitError, OSError, RuntimeError, TypeError, ValueError) as error:
        print(canonical_json({"status": "FAIL", "error_class": type(error).__name__, "message": str(error)}))
        return 2
    print(canonical_json(result))
    return 0 if result["verdict"] == GO_VERDICT else 3


if __name__ == "__main__":
    raise SystemExit(main())
