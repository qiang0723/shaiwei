"""Build and judge the offline F1-0 CSI800 fundamental PIT feature gate."""

from __future__ import annotations

import argparse
import os
import tempfile
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
    GO_VERDICT,
    NO_GO_VERDICT,
    FundamentalPitError,
    FundamentalPitProtocol,
    canonical_json,
    sha256_json,
    verify_source_evidence,
)


STATEMENT_FIELDS = {
    "income": ("n_income_attr_p", "operate_profit", "total_revenue"),
    "balancesheet": ("total_assets", "total_liab", "money_cap"),
    "cashflow": ("n_cashflow_act",),
}
IDENTITY_FIELDS = ("ts_code", "f_ann_date", "end_date", "report_type", "update_flag")


def _canonical_statement(name: str, frames: list[pd.DataFrame]) -> tuple[pd.DataFrame, int]:
    required = set(IDENTITY_FIELDS) | set(STATEMENT_FIELDS[name])
    if any(missing := required - set(frame.columns) for frame in frames):
        raise FundamentalPitError(f"{name} missing required columns: {sorted(missing)}")
    combined = pd.concat([frame.loc[:, sorted(required)] for frame in frames], ignore_index=True)
    for column in IDENTITY_FIELDS:
        combined[column] = combined[column].astype("string")
    combined = combined.loc[
        combined["end_date"].str.endswith("1231", na=False)
        & combined["report_type"].isin(["1", "5"])
    ].copy()
    conflicts = 0
    if not combined.empty:
        grouped = combined.groupby(list(IDENTITY_FIELDS), dropna=False)
        conflicts = int(
            sum(
                group.loc[:, STATEMENT_FIELDS[name]].nunique(dropna=False).gt(1).any()
                for _, group in grouped
            )
        )
    if conflicts:
        raise FundamentalPitError(f"{name} contains conflicting duplicate identities")
    combined = combined.drop_duplicates(list(IDENTITY_FIELDS), keep="last").copy()
    for column in STATEMENT_FIELDS[name]:
        combined[column] = pd.to_numeric(combined[column], errors="coerce")
    return combined.reset_index(drop=True), conflicts


def _open_days(trade_cal: pd.DataFrame, start: str, end: str) -> list[str]:
    required = {"cal_date", "is_open"}
    if missing := required - set(trade_cal.columns):
        raise FundamentalPitError(f"trade calendar missing columns: {sorted(missing)}")
    calendar = trade_cal.copy()
    if "exchange" in calendar:
        calendar = calendar.loc[calendar["exchange"].astype(str).eq("SSE")]
    days = sorted(
        day
        for day in calendar.loc[calendar["is_open"].astype(str).eq("1"), "cal_date"]
        .astype(str)
        .drop_duplicates()
        if start <= day <= end
    )
    if not days:
        raise FundamentalPitError("F1-0 trade calendar has no open days")
    return days


def _formation_dates(open_days: list[str]) -> list[str]:
    frame = pd.DataFrame({"trade_date": open_days})
    frame["month"] = frame["trade_date"].str[:6]
    return frame.groupby("month", sort=True)["trade_date"].max().tolist()


def _members(index_weight: pd.DataFrame, formations: list[str], index_code: str) -> pd.DataFrame:
    required = {"index_code", "con_code", "trade_date"}
    if missing := required - set(index_weight.columns):
        raise FundamentalPitError(f"index weight missing columns: {sorted(missing)}")
    snapshots = index_weight.loc[index_weight["index_code"].astype(str).eq(index_code)].copy()
    snapshots["trade_date"] = snapshots["trade_date"].astype(str)
    rows = []
    for formation in formations:
        eligible = snapshots.loc[snapshots["trade_date"].le(formation)]
        if eligible.empty:
            continue
        latest = eligible["trade_date"].max()
        codes = sorted(eligible.loc[eligible["trade_date"].eq(latest), "con_code"].astype(str).unique())
        rows.extend((formation, code, latest) for code in codes)
    return pd.DataFrame(rows, columns=["formation_date", "ts_code", "membership_snapshot_date"])


def _with_availability(statement: pd.DataFrame, open_days: list[str]) -> pd.DataFrame:
    result = statement.copy()
    announcements = pd.to_datetime(result["f_ann_date"], format="%Y%m%d", errors="coerce")
    calendar = pd.to_datetime(pd.Series(open_days), format="%Y%m%d")
    positions = calendar.searchsorted(announcements, side="right")
    available = pd.Series(pd.NA, index=result.index, dtype="string")
    valid = announcements.notna() & (positions < len(calendar))
    available.loc[valid] = calendar.iloc[positions[valid]].dt.strftime("%Y%m%d").to_numpy()
    result["available_date"] = available
    result["_report_priority"] = result["report_type"].map({"1": 2, "5": 1}).fillna(0)
    result["_update_priority"] = pd.to_numeric(result["update_flag"], errors="coerce").fillna(-1)
    return result.loc[result["available_date"].notna()].copy()


def _latest_statement(members: pd.DataFrame, statement: pd.DataFrame, name: str) -> pd.DataFrame:
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
            LEFT JOIN statement s
              ON m.ts_code = s.ts_code AND s.available_date <= m.formation_date
            QUALIFY row_number() OVER (
              PARTITION BY m.formation_date, m.ts_code
              ORDER BY s.end_date DESC NULLS LAST,
                       s.f_ann_date DESC NULLS LAST,
                       s._report_priority DESC NULLS LAST,
                       s._update_priority DESC NULLS LAST
            ) = 1
            ORDER BY m.formation_date, m.ts_code
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


def build_feature_panel(
    protocol: FundamentalPitProtocol,
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
        raise FundamentalPitError("F1-0 has no CSI800 formation members")
    snapshots = []
    source_rows: dict[str, int] = {}
    conflict_count = 0
    for name in STATEMENT_FIELDS:
        statement, conflicts = _canonical_statement(
            name,
            [frames[f"tushare.{name}"], frames[f"tushare.{name}_vip"]],
        )
        source_rows[name] = len(statement)
        conflict_count += conflicts
        snapshots.append(_latest_statement(members, _with_availability(statement, availability_days), name))
    panel = members.copy()
    for snapshot in snapshots:
        panel = panel.merge(snapshot, on=["formation_date", "ts_code"], how="left", validate="one_to_one")
    period_columns = [f"{name}_end_date" for name in STATEMENT_FIELDS]
    available_columns = [f"{name}_available_date" for name in STATEMENT_FIELDS]
    complete_periods = panel[period_columns].notna().all(axis=1)
    mixed = complete_periods & panel[period_columns].nunique(axis=1, dropna=False).gt(1)
    same_period = complete_periods & ~mixed
    panel["end_date"] = panel["income_end_date"].where(same_period)
    panel["available_date"] = panel[available_columns].max(axis=1).where(same_period)
    assets = pd.to_numeric(panel["balancesheet_total_assets"], errors="coerce")
    revenue = pd.to_numeric(panel["income_total_revenue"], errors="coerce")
    valid_assets = same_period & np.isfinite(assets) & assets.gt(0)
    valid_revenue = same_period & np.isfinite(revenue) & revenue.gt(0)
    income = pd.to_numeric(panel["income_n_income_attr_p"], errors="coerce")
    operating = pd.to_numeric(panel["income_operate_profit"], errors="coerce")
    cashflow = pd.to_numeric(panel["cashflow_n_cashflow_act"], errors="coerce")
    liabilities = pd.to_numeric(panel["balancesheet_total_liab"], errors="coerce")
    cash = pd.to_numeric(panel["balancesheet_money_cap"], errors="coerce")
    panel["fundamental_net_income_to_assets_v1"] = (income / assets).where(valid_assets)
    panel["fundamental_operating_margin_v1"] = (operating / revenue).where(valid_revenue)
    panel["fundamental_cash_return_on_assets_v1"] = (cashflow / assets).where(valid_assets)
    panel["fundamental_leverage_v1"] = (liabilities / assets).where(valid_assets)
    panel["fundamental_cash_to_assets_v1"] = (cash / assets).where(valid_assets)
    panel["fundamental_accruals_to_assets_v1"] = ((income - cashflow) / assets).where(valid_assets)
    feature_ids = [item.feature_id for item in protocol.features]
    panel[feature_ids] = panel[feature_ids].replace([np.inf, -np.inf], np.nan)
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
        future |= panel[column].notna() & panel[column].gt(panel["formation_date"])
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
        "mixed_component_period_rows": int(mixed.sum()),
        "future_availability_rows": int(future.sum()),
        "source_identity_conflicts": conflict_count,
        "canonical_annual_rows": source_rows,
        "coverage": coverage,
    }
    keep = ["formation_date", "ts_code", "membership_snapshot_date", "end_date", "available_date", *feature_ids]
    return panel.loc[:, keep].sort_values(["formation_date", "ts_code"]).reset_index(drop=True), diagnostics


def _gate_results(protocol: FundamentalPitProtocol, diagnostics: dict[str, Any]) -> dict[str, bool]:
    gates = protocol.document["gates"]
    count_gate = gates["membership_count_each_formation"]
    coverage = diagnostics["coverage"]
    return {
        "calendar_scope": diagnostics["open_day_first"] <= "20160104"
        and diagnostics["open_day_last"] == "20260731",
        "formation_count": diagnostics["quality_formation_count"] >= int(
            str(gates["formation_dates_after_quality_start"]).split("_")[-1]
        ),
        "membership_count": diagnostics["membership_min"] >= int(count_gate["minimum"])
        and diagnostics["membership_max"] <= int(count_gate["maximum"]),
        "bse_absent": diagnostics["bse_rows"] == int(gates["bse_rows"]),
        "no_mixed_periods": diagnostics["mixed_component_period_rows"]
        == int(gates["mixed_component_period_rows"]),
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


def _write_json_once(path: Path, value: dict[str, Any]) -> str:
    payload = (canonical_json(value) + "\n").encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != payload:
            raise FundamentalPitError(f"immutable F1-0 JSON differs: {path.name}")
    else:
        path.write_bytes(payload)
    return sha256_file(path)


def _write_parquet_once(path: Path, panel: pd.DataFrame) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".f1-", suffix=".parquet", dir=path.parent)
    os.close(descriptor)
    candidate = Path(temporary)
    try:
        panel.to_parquet(candidate, index=False, compression="zstd")
        candidate_sha = sha256_file(candidate)
        if path.exists():
            if sha256_file(path) != candidate_sha:
                raise FundamentalPitError("immutable F1-0 feature panel differs")
        else:
            os.link(candidate, path)
        return candidate_sha
    finally:
        candidate.unlink(missing_ok=True)


def run(
    protocol: FundamentalPitProtocol,
    *,
    project_root: Path = PROJECT_ROOT,
    manifest_output: Path | None = None,
) -> dict[str, Any]:
    evidence = verify_source_evidence(protocol)
    frames = {source_api: load_latest_api(source_api) for source_api in protocol.required_apis}
    panel, diagnostics = build_feature_panel(protocol, frames)
    gates = _gate_results(protocol, diagnostics)
    verdict = GO_VERDICT if all(gates.values()) else NO_GO_VERDICT
    input_identity = sha256_json({"protocol_sha256": protocol.sha256, "sources": evidence})
    code_identity = sha256_json(
        {
            "contract": sha256_file(project_root / "src/shaiwei/research/fundamental_pit_contract.py"),
            "gate": sha256_file(project_root / "src/shaiwei/research/fundamental_pit_gate.py"),
        }
    )
    feature_path = protocol.project_path("ignored_feature_panel", project_root=project_root)
    feature_sha = _write_parquet_once(feature_path, panel)
    report = {
        "schema_version": "f1-csi800-fundamental-pit-report-v1",
        "protocol_id": protocol.document["protocol_id"],
        "protocol_sha256": protocol.sha256,
        "input_snapshot_sha256": input_identity,
        "code_snapshot_sha256": code_identity,
        "code_git_head": git_head(),
        "source_evidence": evidence,
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
        "schema_version": "f1-csi800-fundamental-pit-manifest-v1",
        "protocol_id": protocol.document["protocol_id"],
        "protocol_sha256": protocol.sha256,
        "input_snapshot_sha256": input_identity,
        "code_snapshot_sha256": code_identity,
        "code_git_head": git_head(),
        "report": {"path": report_path.relative_to(project_root).as_posix(), "sha256": report_sha},
        "feature_panel": {
            "path": feature_path.relative_to(project_root).as_posix(),
            "row_count": len(panel),
            "sha256": feature_sha,
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
        default=PROJECT_ROOT / "config/f1_csi800_fundamental_pit_v1.yaml",
    )
    parser.add_argument("--manifest-output", type=Path, default=None)
    args = parser.parse_args(argv)
    try:
        result = run(
            FundamentalPitProtocol.load(args.protocol),
            manifest_output=args.manifest_output,
        )
    except (FundamentalPitError, OSError, RuntimeError, TypeError, ValueError) as error:
        print(canonical_json({"status": "FAIL", "error_class": type(error).__name__, "message": str(error)}))
        return 2
    print(canonical_json(result))
    return 0 if result["verdict"] == GO_VERDICT else 3


if __name__ == "__main__":
    raise SystemExit(main())
