"""Hash-verified full-history quality audit for the isolated P1 money-flow source."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import pandas as pd
import pyarrow.parquet as pq

from shaiwei.config import PROJECT_ROOT
from shaiwei.ingest.catalog import canonical_params_key
from shaiwei.ledger import INGEST, ingest_snapshot_sha256, resolve_artifact_path, sha256_file
from shaiwei.provenance import code_snapshot_sha256, git_head
from tools.p1_moneyflow.backfill import open_trade_dates
from tools.p1_moneyflow.contract import (
    MONEYFLOW_FIELDS,
    PRIMARY_MAX_SOURCE_ONLY_RATE,
    PRIMARY_MIN_DAILY_COVERAGE,
    PIT_POLICY,
    tool_snapshot_sha256,
    write_project_json,
)
from tools.p1_moneyflow.features import feature_policy_sha256


class MoneyflowFullAuditError(RuntimeError):
    pass


def _catalog_sha256(entries: pd.DataFrame) -> str:
    payload = hashlib.sha256()
    for entry in entries.sort_values(["source_api", "_params_key"]).to_dict("records"):
        document = {
            "source_api": str(entry["source_api"]),
            "params_key": str(entry["_params_key"]),
            "row_count": int(entry["row_count"]),
            "content_sha256": str(entry["content_sha256"]),
            "parquet_path": str(entry["parquet_path"]),
        }
        payload.update(
            json.dumps(document, sort_keys=True, separators=(",", ":")).encode("utf-8")
        )
        payload.update(b"\n")
    return payload.hexdigest()


def _latest_entries(ledger: pd.DataFrame, source_api: str) -> pd.DataFrame:
    entries = ledger.loc[ledger["source_api"].eq(source_api)].copy()
    if entries.empty:
        raise MoneyflowFullAuditError(f"no committed batches for {source_api}")
    entries["_params_key"] = entries["params_json"].map(
        lambda value: canonical_params_key(json.loads(value))
    )
    entries["_time"] = pd.to_datetime(entries["ingest_time"], utc=True, errors="raise")
    return entries.sort_values("_time").drop_duplicates("_params_key", keep="last")


def _verify_entries(entries: pd.DataFrame, *, expected_dates: dict[str, str] | None = None) -> list[str]:
    paths = []
    for entry in entries.to_dict("records"):
        path = resolve_artifact_path(entry["parquet_path"])
        if not path.is_file():
            raise MoneyflowFullAuditError(f"committed batch file is missing: {path}")
        metadata = pq.read_metadata(path)
        if metadata.num_rows != int(entry["row_count"]):
            raise MoneyflowFullAuditError(f"row count mismatch: {path}")
        if sha256_file(path) != entry["content_sha256"]:
            raise MoneyflowFullAuditError(f"content hash mismatch: {path}")
        if expected_dates is not None:
            expected = expected_dates[str(entry["_params_key"])]
            observed = {
                str(value)
                for value in pq.ParquetFile(path).read(columns=["trade_date"])
                .column("trade_date")
                .to_pylist()
                if value is not None
            }
            if observed and observed != {expected}:
                raise MoneyflowFullAuditError(
                    f"request/payload trade date mismatch: expected={expected}, observed={sorted(observed)}"
                )
        paths.append(str(path))
    return paths


def evaluate_quality_table(frame: pd.DataFrame) -> pd.DataFrame:
    required = {
        "trade_date",
        "moneyflow_rows",
        "moneyflow_distinct_codes",
        "daily_rows",
        "daily_distinct_codes",
        "intersection_codes",
        "source_only_codes",
        "daily_only_codes",
        "null_or_nonfinite_rows",
        "negative_gross_rows",
        "bse_rows",
        "classified_amount_ratio_median",
        "classified_volume_ratio_median",
        "net_scale_tail_rows",
    }
    if missing := required - set(frame.columns):
        raise ValueError(f"quality table missing fields: {sorted(missing)}")
    result = frame.copy().sort_values("trade_date").reset_index(drop=True)
    issues = []
    warnings = []
    coverage_values = []
    source_only_rates = []
    for row in result.itertuples(index=False):
        row_issues = []
        row_warnings = []
        daily_rows = int(row.daily_rows)
        intersection = int(row.intersection_codes)
        source_only = int(row.source_only_codes)
        coverage = intersection / daily_rows if daily_rows else float("nan")
        source_only_rate = source_only / daily_rows if daily_rows else float("nan")
        if daily_rows <= 0:
            row_issues.append("DAILY_REFERENCE_MISSING")
        if int(row.moneyflow_rows) <= 0:
            row_issues.append("NO_MONEYFLOW_ON_OPEN_DAY")
        if int(row.moneyflow_rows) != int(row.moneyflow_distinct_codes):
            row_issues.append("DUPLICATE_MONEYFLOW_KEY")
        if int(row.daily_rows) != int(row.daily_distinct_codes):
            row_issues.append("DUPLICATE_DAILY_KEY")
        if int(row.null_or_nonfinite_rows):
            row_issues.append("NULL_OR_NONFINITE_MONEYFLOW")
        if int(row.negative_gross_rows):
            row_issues.append("NEGATIVE_GROSS_FLOW")
        if int(row.bse_rows):
            row_issues.append("BSE_ROW_PRESENT")
        if not pd.notna(coverage) or coverage < PRIMARY_MIN_DAILY_COVERAGE:
            row_issues.append("PRIMARY_COVERAGE_BELOW_GATE")
        if not pd.notna(source_only_rate) or source_only_rate > PRIMARY_MAX_SOURCE_ONLY_RATE:
            row_issues.append("PRIMARY_SOURCE_ONLY_ABOVE_GATE")
        amount_ratio = float(row.classified_amount_ratio_median)
        volume_ratio = float(row.classified_volume_ratio_median)
        if not 1.9 <= amount_ratio <= 2.1:
            row_issues.append("PRIMARY_AMOUNT_SCALE_MISMATCH")
        if not 1.9 <= volume_ratio <= 2.1:
            row_issues.append("PRIMARY_VOLUME_SCALE_MISMATCH")
        if int(row.net_scale_tail_rows):
            row_warnings.append("NET_FLOW_EXCEEDS_DAILY_SCALE_TAIL")
        coverage_values.append(coverage)
        source_only_rates.append(source_only_rate)
        issues.append(sorted(set(row_issues)))
        warnings.append(sorted(set(row_warnings)))
    result["daily_coverage_rate"] = coverage_values
    result["source_only_rate"] = source_only_rates
    result["issues"] = issues
    result["warnings"] = warnings
    result["gate_status"] = ["FAIL" if row_issues else "PASS" for row_issues in issues]
    return result


def _quality_query(
    moneyflow_paths: list[str],
    daily_paths: list[str],
    official_dates: list[str],
) -> pd.DataFrame:
    amount_fields = [
        f"{side}_{size}_amount"
        for size in ("sm", "md", "lg", "elg")
        for side in ("buy", "sell")
    ]
    volume_fields = [
        f"{side}_{size}_vol"
        for size in ("sm", "md", "lg", "elg")
        for side in ("buy", "sell")
    ]
    numeric_fields = [field for field in MONEYFLOW_FIELDS["moneyflow"] if field not in {"ts_code", "trade_date"}]
    invalid_expression = " OR ".join(
        f'{field} IS NULL OR NOT isfinite(CAST({field} AS DOUBLE))' for field in numeric_fields
    )
    negative_expression = " OR ".join(f"{field} < 0" for field in [*amount_fields, *volume_fields])
    amount_sum = " + ".join(amount_fields)
    volume_sum = " + ".join(volume_fields)
    connection = duckdb.connect(":memory:")
    try:
        connection.read_parquet(
            moneyflow_paths,
            union_by_name=True,
            hive_partitioning=False,
        ).create_view("moneyflow")
        connection.read_parquet(
            daily_paths,
            union_by_name=True,
            hive_partitioning=False,
        ).create_view("daily")
        connection.register("official_dates", pd.DataFrame({"trade_date": official_dates}))
        start_date, end_date = official_dates[0], official_dates[-1]
        query = f"""
            WITH mf AS (
                SELECT * FROM moneyflow
                WHERE CAST(trade_date AS VARCHAR) BETWEEN ? AND ?
            ), d AS (
                SELECT ts_code, CAST(trade_date AS VARCHAR) AS trade_date, amount, vol
                FROM daily
                WHERE CAST(trade_date AS VARCHAR) BETWEEN ? AND ?
            ), mf_day AS (
                SELECT CAST(trade_date AS VARCHAR) AS trade_date,
                       count(*) AS moneyflow_rows,
                       count(DISTINCT ts_code) AS moneyflow_distinct_codes,
                       sum(CASE WHEN ts_code IS NULL OR trade_date IS NULL OR {invalid_expression}
                                THEN 1 ELSE 0 END) AS null_or_nonfinite_rows,
                       sum(CASE WHEN {negative_expression} THEN 1 ELSE 0 END) AS negative_gross_rows,
                       sum(CASE WHEN ends_with(CAST(ts_code AS VARCHAR), '.BJ') THEN 1 ELSE 0 END) AS bse_rows
                FROM mf GROUP BY 1
            ), d_day AS (
                SELECT trade_date, count(*) AS daily_rows,
                       count(DISTINCT ts_code) AS daily_distinct_codes
                FROM d GROUP BY 1
            ), intersected AS (
                SELECT CAST(m.trade_date AS VARCHAR) AS trade_date,
                       count(*) AS intersection_codes,
                       median(CAST(({amount_sum}) AS DOUBLE) / (CAST(d.amount AS DOUBLE) / 10.0))
                           FILTER (WHERE CAST(d.amount AS DOUBLE) > 0) AS classified_amount_ratio_median,
                       median(CAST(({volume_sum}) AS DOUBLE) / CAST(d.vol AS DOUBLE))
                           FILTER (WHERE CAST(d.vol AS DOUBLE) > 0) AS classified_volume_ratio_median,
                       sum(CASE WHEN CAST(d.amount AS DOUBLE) > 0
                                      AND abs(CAST(m.net_mf_amount AS DOUBLE))
                                          / (CAST(d.amount AS DOUBLE) / 10.0) > 1.01
                                THEN 1 ELSE 0 END) AS net_scale_tail_rows
                FROM mf m INNER JOIN d
                  ON CAST(m.trade_date AS VARCHAR) = d.trade_date AND m.ts_code = d.ts_code
                GROUP BY 1
            ), source_only AS (
                SELECT CAST(m.trade_date AS VARCHAR) AS trade_date, count(*) AS source_only_codes
                FROM mf m LEFT JOIN d
                  ON CAST(m.trade_date AS VARCHAR) = d.trade_date AND m.ts_code = d.ts_code
                WHERE d.ts_code IS NULL GROUP BY 1
            ), daily_only AS (
                SELECT d.trade_date, count(*) AS daily_only_codes
                FROM d LEFT JOIN mf m
                  ON CAST(m.trade_date AS VARCHAR) = d.trade_date AND m.ts_code = d.ts_code
                WHERE m.ts_code IS NULL GROUP BY 1
            )
            SELECT o.trade_date,
                   coalesce(m.moneyflow_rows, 0) AS moneyflow_rows,
                   coalesce(m.moneyflow_distinct_codes, 0) AS moneyflow_distinct_codes,
                   coalesce(d.daily_rows, 0) AS daily_rows,
                   coalesce(d.daily_distinct_codes, 0) AS daily_distinct_codes,
                   coalesce(i.intersection_codes, 0) AS intersection_codes,
                   coalesce(s.source_only_codes, 0) AS source_only_codes,
                   coalesce(x.daily_only_codes, 0) AS daily_only_codes,
                   coalesce(m.null_or_nonfinite_rows, 0) AS null_or_nonfinite_rows,
                   coalesce(m.negative_gross_rows, 0) AS negative_gross_rows,
                   coalesce(m.bse_rows, 0) AS bse_rows,
                   i.classified_amount_ratio_median,
                   i.classified_volume_ratio_median,
                   coalesce(i.net_scale_tail_rows, 0) AS net_scale_tail_rows
            FROM official_dates o
            LEFT JOIN mf_day m USING (trade_date)
            LEFT JOIN d_day d USING (trade_date)
            LEFT JOIN intersected i USING (trade_date)
            LEFT JOIN source_only s USING (trade_date)
            LEFT JOIN daily_only x USING (trade_date)
            ORDER BY o.trade_date
        """
        return connection.execute(
            query,
            [start_date, end_date, start_date, end_date],
        ).df()
    finally:
        connection.close()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-date", default="20160101")
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--report", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    ledger = pd.read_csv(INGEST, dtype=str, keep_default_na=False)
    trade_calendar = _latest_entries(ledger, "tushare.trade_cal")
    trade_calendar_paths = _verify_entries(trade_calendar)
    calendar_connection = duckdb.connect(":memory:")
    try:
        calendar = calendar_connection.execute(
            "SELECT * FROM read_parquet(?, union_by_name=true, hive_partitioning=false)",
            [trade_calendar_paths],
        ).df()
    finally:
        calendar_connection.close()
    official_dates = open_trade_dates(
        calendar,
        start_date=args.start_date,
        end_date=args.end_date,
    )

    all_moneyflow = ledger.loc[ledger["source_api"].eq("tushare.moneyflow")].copy()
    all_moneyflow["_params_key"] = all_moneyflow["params_json"].map(
        lambda value: canonical_params_key(json.loads(value))
    )
    all_moneyflow["_trade_date"] = all_moneyflow["params_json"].map(
        lambda value: str(json.loads(value).get("trade_date", ""))
    )
    all_moneyflow = all_moneyflow.loc[all_moneyflow["_trade_date"].isin(official_dates)].copy()
    revisions = (
        all_moneyflow.groupby("_params_key")["content_sha256"].nunique().loc[lambda values: values > 1]
    )
    latest_moneyflow = _latest_entries(ledger, "tushare.moneyflow")
    latest_moneyflow["_trade_date"] = latest_moneyflow["params_json"].map(
        lambda value: str(json.loads(value).get("trade_date", ""))
    )
    latest_moneyflow = latest_moneyflow.loc[
        latest_moneyflow["_trade_date"].isin(official_dates)
    ].copy()
    expected_by_key = dict(
        zip(latest_moneyflow["_params_key"], latest_moneyflow["_trade_date"], strict=True)
    )
    moneyflow_paths = _verify_entries(latest_moneyflow, expected_dates=expected_by_key)
    if len(latest_moneyflow) != len(official_dates):
        raise MoneyflowFullAuditError(
            f"moneyflow request coverage differs: {len(latest_moneyflow)} != {len(official_dates)}"
        )
    saturated = latest_moneyflow.loc[pd.to_numeric(latest_moneyflow["row_count"]).ge(6000)]

    latest_daily = _latest_entries(ledger, "tushare.daily")
    daily_paths = _verify_entries(latest_daily)
    quality = evaluate_quality_table(_quality_query(moneyflow_paths, daily_paths, official_dates))
    failures = quality.loc[quality["gate_status"].eq("FAIL")]
    status = (
        "PASS"
        if failures.empty and revisions.empty and saturated.empty
        else "FAIL"
    )
    report = {
        "schema_version": "p1-moneyflow-full-quality-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git_head": git_head(),
        "production_code_snapshot_sha256": code_snapshot_sha256(),
        "p1_tool_snapshot_sha256": tool_snapshot_sha256(),
        "feature_policy_sha256": feature_policy_sha256(),
        "ingest_snapshot_sha256": ingest_snapshot_sha256(),
        "pit_policy": PIT_POLICY,
        "scope": {
            "start_date": official_dates[0],
            "end_date": official_dates[-1],
            "official_trade_date_count": len(official_dates),
        },
        "source": {
            "latest_batch_count": int(len(latest_moneyflow)),
            "latest_row_count": int(pd.to_numeric(latest_moneyflow["row_count"]).sum()),
            "latest_catalog_sha256": _catalog_sha256(latest_moneyflow),
            "revision_observed_count": int(len(revisions)),
            "saturated_response_count": int(len(saturated)),
        },
        "daily_reference": {
            "latest_batch_count": int(len(latest_daily)),
            "latest_catalog_sha256": _catalog_sha256(latest_daily),
        },
        "summary": {
            "status": status,
            "pass_trade_date_count": int(quality["gate_status"].eq("PASS").sum()),
            "failed_trade_date_count": int(len(failures)),
            "minimum_daily_coverage_rate": float(quality["daily_coverage_rate"].min()),
            "maximum_source_only_rate": float(quality["source_only_rate"].max()),
            "warning_trade_date_count": int(quality["warnings"].map(bool).sum()),
            "authorization": "build_isolated_feature_panel" if status == "PASS" else "none",
            "production_authorization": "none",
        },
        "per_trade_date": quality.to_dict("records"),
    }
    report_path = args.report if args.report.is_absolute() else PROJECT_ROOT / args.report
    write_project_json(report_path, report)
    print(
        json.dumps(
            {
                "status": status,
                "official_trade_date_count": len(official_dates),
                "failed_trade_date_count": len(failures),
                "revision_observed_count": len(revisions),
                "report": str(report_path.relative_to(PROJECT_ROOT)),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
