"""One-shot Docker entry point for the isolated 2016-2026 money-flow backfill."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from shaiwei.config import PROJECT_ROOT, load
from shaiwei.ingest.catalog import canonical_params_key, committed_params_keys, load_latest_api
from shaiwei.ingest.core import RawBatchWriter
from shaiwei.ingest.tushare import create_client
from shaiwei.ledger import ingest_snapshot_sha256
from shaiwei.provenance import code_snapshot_sha256, git_head
from tools.p1_moneyflow.contract import (
    PIT_POLICY,
    PRIMARY_MONEYFLOW_API,
    MoneyflowIngestor,
    build_moneyflow_plan,
    public_request_params,
    tool_snapshot_sha256,
    write_project_json,
)


def open_trade_dates(
    trade_calendar: pd.DataFrame,
    *,
    start_date: str,
    end_date: str,
) -> list[str]:
    required = {"exchange", "cal_date", "is_open"}
    if missing := required - set(trade_calendar.columns):
        raise ValueError(f"trade calendar missing fields: {sorted(missing)}")
    if start_date > end_date:
        raise ValueError("start_date must not exceed end_date")
    calendar = trade_calendar.loc[
        trade_calendar["exchange"].astype(str).eq("SSE")
        & pd.to_numeric(trade_calendar["is_open"], errors="coerce").eq(1)
    ].copy()
    calendar["cal_date"] = calendar["cal_date"].astype(str)
    dates = sorted(set(calendar.loc[calendar["cal_date"].between(start_date, end_date), "cal_date"]))
    if not dates:
        raise ValueError("no official open trade dates in requested range")
    return dates


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-date", default="20160101", help="inclusive YYYYMMDD")
    parser.add_argument("--end-date", required=True, help="inclusive YYYYMMDD")
    parser.add_argument("--report", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    for field in ("start_date", "end_date"):
        value = getattr(args, field)
        parsed = pd.to_datetime(value, format="%Y%m%d", errors="coerce")
        if pd.isna(parsed) or parsed.strftime("%Y%m%d") != value:
            parser.error(f"--{field.replace('_', '-')} must be YYYYMMDD")
    if not args.dry_run and args.report is None:
        parser.error("--report is required unless --dry-run is used")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    trade_dates = open_trade_dates(
        load_latest_api("tushare.trade_cal"),
        start_date=args.start_date,
        end_date=args.end_date,
    )
    plan = build_moneyflow_plan(trade_dates)
    committed = committed_params_keys(f"tushare.{PRIMARY_MONEYFLOW_API}")
    pending = [
        request
        for request in plan
        if canonical_params_key(public_request_params(request)) not in committed
    ]
    summary = {
        "source_api": f"tushare.{PRIMARY_MONEYFLOW_API}",
        "start_date": trade_dates[0],
        "end_date": trade_dates[-1],
        "official_trade_date_count": len(trade_dates),
        "requested_count": len(plan),
        "already_committed_count": len(plan) - len(pending),
        "pending_count": len(pending),
    }
    if args.dry_run:
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
        return 0

    settings = load()
    secret = settings.runtime.tushare_token
    if secret is None or not secret.get_secret_value().strip():
        raise SystemExit("TUSHARE_TOKEN is missing from local .env")
    started_at = datetime.now(timezone.utc).isoformat()
    batches = MoneyflowIngestor(
        client=create_client(secret.get_secret_value()),
        writer=RawBatchWriter(settings.runtime.data_root),
        settings=settings,
    ).run(pending)
    report = {
        "schema_version": "p1-moneyflow-backfill-v1",
        "started_at": started_at,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "git_head": git_head(),
        "production_code_snapshot_sha256": code_snapshot_sha256(),
        "p1_tool_snapshot_sha256": tool_snapshot_sha256(),
        "feature_availability_policy": PIT_POLICY,
        "scope": "isolated_collection_only",
        "production_model_or_signal_changed": False,
        "collection": {
            **summary,
            "collected_count": len(batches),
            "collected_row_count": sum(batch.row_count for batch in batches),
        },
        "new_batches": [
            {
                "batch_id": batch.batch_id,
                "source_api": batch.source_api,
                "row_count": batch.row_count,
                "path": str(batch.parquet_path.relative_to(PROJECT_ROOT)),
                "content_sha256": batch.content_sha256,
            }
            for batch in batches
        ],
        "ingest_snapshot_sha256": ingest_snapshot_sha256(),
        "status": "COLLECTED_PENDING_FULL_QUALITY_AUDIT",
        "production_authorization": "none",
    }
    report_path = args.report if args.report.is_absolute() else PROJECT_ROOT / args.report
    write_project_json(report_path, report)
    print(
        json.dumps(
            {
                **summary,
                "collected_count": len(batches),
                "collected_row_count": sum(batch.row_count for batch in batches),
                "report": str(report_path.relative_to(PROJECT_ROOT)),
                "status": report["status"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
