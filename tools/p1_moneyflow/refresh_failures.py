"""Refresh failed full-audit dates once to distinguish revisions from stable source gaps."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from shaiwei.config import PROJECT_ROOT, load
from shaiwei.ingest.core import RawBatchWriter
from shaiwei.ingest.tushare import create_client
from shaiwei.ledger import ingest_snapshot_sha256, sha256_file
from shaiwei.provenance import code_snapshot_sha256, git_head
from tools.p1_moneyflow.contract import (
    PRIMARY_MONEYFLOW_API,
    MoneyflowIngestor,
    build_moneyflow_plan,
    public_request_params,
    request_evidence_history,
    tool_snapshot_sha256,
    write_project_json,
)


class RefreshFailureError(RuntimeError):
    pass


def failed_trade_dates(document: dict[str, object]) -> list[str]:
    if document.get("schema_version") != "p1-moneyflow-full-quality-v1":
        raise RefreshFailureError("input is not a full-history moneyflow quality report")
    rows = document.get("per_trade_date")
    if not isinstance(rows, list):
        raise RefreshFailureError("quality report lacks per_trade_date rows")
    failures = sorted(
        {
            str(row["trade_date"])
            for row in rows
            if isinstance(row, dict) and row.get("gate_status") == "FAIL"
        }
    )
    if not failures:
        raise RefreshFailureError("quality report has no failed trade dates to refresh")
    return failures


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
    document = json.loads(quality_path.read_text(encoding="utf-8"))
    dates = failed_trade_dates(document)
    plan = build_moneyflow_plan(dates)
    prior = {
        request.trade_date: request_evidence_history(
            f"tushare.{PRIMARY_MONEYFLOW_API}", public_request_params(request)
        )
        for request in plan
    }
    settings = load()
    secret = settings.runtime.tushare_token
    if secret is None or not secret.get_secret_value().strip():
        raise SystemExit("TUSHARE_TOKEN is missing from local .env")
    started_at = datetime.now(timezone.utc).isoformat()
    batches = MoneyflowIngestor(
        client=create_client(secret.get_secret_value()),
        writer=RawBatchWriter(settings.runtime.data_root),
        settings=settings,
    ).run(plan)
    observations = []
    revision_dates = []
    for request, batch in zip(plan, batches, strict=True):
        history = request_evidence_history(
            f"tushare.{PRIMARY_MONEYFLOW_API}", public_request_params(request)
        )
        prior_hashes = {str(item["content_sha256"]) for item in prior[request.trade_date]}
        latest_hash = str(history[-1]["content_sha256"])
        revised = latest_hash not in prior_hashes
        if revised:
            revision_dates.append(request.trade_date)
        observations.append(
            {
                "trade_date": request.trade_date,
                "prior_observation_count": len(prior[request.trade_date]),
                "prior_unique_content_sha256_count": len(prior_hashes),
                "latest_batch_id": batch.batch_id,
                "latest_row_count": batch.row_count,
                "latest_content_sha256": latest_hash,
                "revised": revised,
            }
        )
    status = "REVISION_OBSERVED" if revision_dates else "STABLE_REFRESH"
    report = {
        "schema_version": "p1-moneyflow-failed-date-refresh-v1",
        "started_at": started_at,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "git_head": git_head(),
        "production_code_snapshot_sha256": code_snapshot_sha256(),
        "p1_tool_snapshot_sha256": tool_snapshot_sha256(),
        "input_quality_report_path": str(quality_path.relative_to(PROJECT_ROOT)),
        "input_quality_report_sha256": sha256_file(quality_path),
        "requested_trade_date_count": len(dates),
        "collected_batch_count": len(batches),
        "revision_trade_dates": revision_dates,
        "observations": observations,
        "ingest_snapshot_sha256": ingest_snapshot_sha256(),
        "status": status,
        "production_authorization": "none",
    }
    report_path = args.report if args.report.is_absolute() else PROJECT_ROOT / args.report
    write_project_json(report_path, report)
    print(
        json.dumps(
            {
                "status": status,
                "requested_trade_date_count": len(dates),
                "revision_trade_date_count": len(revision_dates),
                "report": str(report_path.relative_to(PROJECT_ROOT)),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if status == "STABLE_REFRESH" else 1


if __name__ == "__main__":
    raise SystemExit(main())
