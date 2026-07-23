"""Build the immutable T+1 raw candidate panel after the full-history audit passes."""

from __future__ import annotations

import argparse
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import pandas as pd

from shaiwei.config import PROJECT_ROOT
from shaiwei.ledger import INGEST, ingest_snapshot_sha256, resolve_artifact_path, sha256_file
from shaiwei.provenance import code_snapshot_sha256, git_head
from tools.p1_moneyflow.contract import MONEYFLOW_FIELDS, tool_snapshot_sha256, write_project_json
from tools.p1_moneyflow.full_audit import _catalog_sha256, _latest_entries
from tools.p1_moneyflow.features import (
    FEATURE_POLICY,
    FORMAL_CANDIDATES,
    audit_feature_lineage,
    build_moneyflow_features,
    feature_policy_sha256,
)


class FeatureBuilderError(RuntimeError):
    pass


def _read_json(path: Path) -> dict[str, object]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise FeatureBuilderError(f"invalid quality report: {path}") from error
    if not isinstance(document, dict):
        raise FeatureBuilderError("quality report must be a JSON object")
    return document


def _paths(entries: pd.DataFrame) -> list[str]:
    paths = []
    for value in entries["parquet_path"]:
        path = resolve_artifact_path(value)
        if not path.is_file():
            raise FeatureBuilderError(f"committed batch file is missing: {path}")
        paths.append(str(path))
    return paths


def _load_source_frames(
    moneyflow_paths: list[str],
    daily_paths: list[str],
    *,
    start_date: str,
    end_date: str,
    quarantined_source_dates: set[str],
) -> tuple[pd.DataFrame, pd.DataFrame]:
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
        fields = ", ".join(MONEYFLOW_FIELDS["moneyflow"])
        moneyflow = connection.execute(
            f"SELECT {fields} FROM moneyflow WHERE CAST(trade_date AS VARCHAR) BETWEEN ? AND ?",
            [start_date, end_date],
        ).df()
        moneyflow = moneyflow.loc[
            ~moneyflow["trade_date"].astype(str).isin(quarantined_source_dates)
        ].copy()
        daily = connection.execute(
            "SELECT ts_code, CAST(trade_date AS VARCHAR) AS trade_date, amount FROM daily "
            "WHERE CAST(trade_date AS VARCHAR) BETWEEN ? AND ?",
            [start_date, end_date],
        ).df()
        return moneyflow, daily
    finally:
        connection.close()


def write_content_addressed_parquet(
    frame: pd.DataFrame,
    directory: Path,
    *,
    stem: str,
) -> tuple[Path, str, bool]:
    directory.mkdir(parents=True, exist_ok=True)
    temporary = directory / f".{stem}.{uuid.uuid4().hex}.tmp.parquet"
    try:
        frame.to_parquet(temporary, index=False, compression="zstd")
        with temporary.open("rb") as handle:
            os.fsync(handle.fileno())
        content_hash = sha256_file(temporary)
        target = directory / f"{stem}-{content_hash[:16]}.parquet"
        if target.is_file():
            if sha256_file(target) != content_hash:
                raise FeatureBuilderError(f"content-addressed artifact hash mismatch: {target}")
            return target, content_hash, True
        os.link(temporary, target)
        return target, content_hash, False
    finally:
        temporary.unlink(missing_ok=True)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quality-report", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    quality_path = (
        args.quality_report
        if args.quality_report.is_absolute()
        else PROJECT_ROOT / args.quality_report
    )
    quality = _read_json(quality_path)
    if quality.get("schema_version") != "p1-moneyflow-quarantine-v2":
        raise FeatureBuilderError("quality report schema is not p1-moneyflow-quarantine-v2")
    summary = quality.get("summary")
    scope = quality.get("scope")
    source = quality.get("source")
    daily_reference = quality.get("daily_reference")
    if not all(isinstance(value, dict) for value in (summary, scope, source, daily_reference)):
        raise FeatureBuilderError("quality report is missing required sections")
    assert isinstance(summary, dict)
    assert isinstance(scope, dict)
    assert isinstance(source, dict)
    assert isinstance(daily_reference, dict)
    if summary.get("status") != "PASS":
        raise FeatureBuilderError("quarantine quality report is not PASS")
    if quality.get("feature_policy_sha256") != feature_policy_sha256():
        raise FeatureBuilderError("quality report feature policy differs from current frozen policy")
    current_ingest = ingest_snapshot_sha256()
    if quality.get("ingest_snapshot_sha256") != current_ingest:
        raise FeatureBuilderError("ingest snapshot changed after the full-history audit")

    ledger = pd.read_csv(INGEST, dtype=str, keep_default_na=False)
    latest_moneyflow = _latest_entries(ledger, "tushare.moneyflow")
    latest_daily = _latest_entries(ledger, "tushare.daily")
    if _catalog_sha256(latest_moneyflow) != source.get("latest_catalog_sha256"):
        raise FeatureBuilderError("moneyflow catalog differs from audited catalog")
    if _catalog_sha256(latest_daily) != daily_reference.get("latest_catalog_sha256"):
        raise FeatureBuilderError("daily catalog differs from audited catalog")

    start_date = str(scope["start_date"])
    end_date = str(scope["end_date"])
    evaluation = quality.get("evaluation")
    if not isinstance(evaluation, dict):
        raise FeatureBuilderError("quarantine quality report lacks evaluation")
    quarantined_rows = evaluation.get("quarantined_source_dates")
    if not isinstance(quarantined_rows, list):
        raise FeatureBuilderError("quarantine quality report lacks source-date mask")
    quarantined_source_dates = {
        str(row["trade_date"])
        for row in quarantined_rows
        if isinstance(row, dict) and "trade_date" in row
    }
    latest_calendar = _latest_entries(ledger, "tushare.trade_cal")
    calendar_connection = duckdb.connect(":memory:")
    try:
        calendar = calendar_connection.execute(
            "SELECT * FROM read_parquet(?, union_by_name=true, hive_partitioning=false)",
            [_paths(latest_calendar)],
        ).df()
    finally:
        calendar_connection.close()
    open_dates = sorted(
        set(
            calendar.loc[
                calendar["exchange"].astype(str).eq("SSE")
                & pd.to_numeric(calendar["is_open"], errors="coerce").eq(1),
                "cal_date",
            ].astype(str)
        )
    )
    if end_date not in open_dates:
        raise FeatureBuilderError("audited end date is absent from the official trade calendar")
    end_index = open_dates.index(end_date)
    if end_index + 1 >= len(open_dates):
        raise FeatureBuilderError("official trade calendar lacks the next trade date for T+1 mapping")
    feature_calendar = [
        trade_date
        for trade_date in open_dates
        if start_date <= trade_date <= open_dates[end_index + 1]
    ]

    moneyflow, daily = _load_source_frames(
        _paths(latest_moneyflow),
        _paths(latest_daily),
        start_date=start_date,
        end_date=end_date,
        quarantined_source_dates=quarantined_source_dates,
    )
    panel = build_moneyflow_features(
        moneyflow,
        daily,
        feature_calendar,
        min_cross_section=int(FEATURE_POLICY["minimum_cross_section"]),
    )
    lineage = audit_feature_lineage(panel, feature_calendar)
    artifact_path, artifact_sha256, reused = write_content_addressed_parquet(
        panel,
        PROJECT_ROOT / "data" / "research" / "moneyflow" / "features",
        stem="p1-moneyflow-raw-candidates-v1",
    )
    report = {
        "schema_version": "p1-moneyflow-feature-build-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git_head": git_head(),
        "production_code_snapshot_sha256": code_snapshot_sha256(),
        "p1_tool_snapshot_sha256": tool_snapshot_sha256(),
        "feature_policy": FEATURE_POLICY,
        "feature_policy_sha256": feature_policy_sha256(),
        "ingest_snapshot_sha256": current_ingest,
        "quality_report_path": str(quality_path.relative_to(PROJECT_ROOT)),
        "quality_report_sha256": sha256_file(quality_path),
        "source": {
            "moneyflow_row_count": int(len(moneyflow)),
            "daily_reference_row_count": int(len(daily)),
            "start_date": start_date,
            "end_date": end_date,
            "quarantined_source_date_count": len(quarantined_source_dates),
        },
        "artifact": {
            "path": str(artifact_path.relative_to(PROJECT_ROOT)),
            "sha256": artifact_sha256,
            "row_count": int(len(panel)),
            "reused": reused,
        },
        "lineage": lineage,
        "formal_candidates": list(FORMAL_CANDIDATES),
        "status": "PASS",
        "authorization": "build_isolated_residualized_candidates",
        "production_authorization": "none",
    }
    report_path = args.report if args.report.is_absolute() else PROJECT_ROOT / args.report
    write_project_json(report_path, report)
    print(
        json.dumps(
            {
                "status": "PASS",
                "artifact": str(artifact_path.relative_to(PROJECT_ROOT)),
                "artifact_sha256": artifact_sha256,
                "row_count": len(panel),
                "report": str(report_path.relative_to(PROJECT_ROOT)),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
