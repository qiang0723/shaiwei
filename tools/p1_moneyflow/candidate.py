"""CLI for isolated P1 money-flow collection and quality evidence."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from shaiwei.config import PROJECT_ROOT, load
from shaiwei.ingest.catalog import (
    CatalogError,
    canonical_params_key,
    committed_params_keys,
    latest_request_evidence,
    load_latest_api,
    load_latest_request,
)
from shaiwei.ingest.core import RawBatchWriter
from shaiwei.ingest.tushare import create_client
from shaiwei.ledger import ingest_snapshot_sha256
from shaiwei.provenance import code_snapshot_sha256, git_head
from tools.p1_moneyflow.contract import (
    MONEYFLOW_APIS,
    PIT_POLICY,
    PRIMARY_MONEYFLOW_API,
    MoneyflowIngestor,
    build_moneyflow_plan,
    profile_moneyflow_batch,
    public_request_params,
    request_evidence_history,
    tool_snapshot_sha256,
    write_project_json,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="筛微 P1 隔离资金流采集与数据质量验证（不接生产信号）"
    )
    parser.add_argument("--trade-date", action="append", required=True, help="YYYYMMDD；可重复")
    parser.add_argument("--api", action="append", choices=MONEYFLOW_APIS)
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)
    if not args.dry_run and args.report is None:
        parser.error("--report is required unless --dry-run is used")
    return args


def _revision_summary(source_api: str, params: dict[str, object]) -> dict[str, object]:
    history = request_evidence_history(source_api, params)
    hashes = [str(item["content_sha256"]) for item in history]
    if len(set(hashes)) > 1:
        status = "REVISION_OBSERVED"
    elif len(hashes) >= 2:
        status = "STABLE_WITHIN_OBSERVATIONS"
    else:
        status = "SINGLE_OBSERVATION"
    return {
        "status": status,
        "observation_count": len(history),
        "unique_content_sha256_count": len(set(hashes)),
        "observations": history,
    }


def _build_report(
    *,
    plan: list,
    started_at: str,
    requested_count: int,
    collected_count: int,
    skipped_count: int,
) -> dict[str, object]:
    wanted_dates = {request.trade_date for request in plan}
    daily = load_latest_api("tushare.daily")
    daily = daily.loc[daily["trade_date"].astype(str).isin(wanted_dates)].copy()
    try:
        suspensions = load_latest_api("tushare.suspend_d")
        suspensions = suspensions.loc[
            suspensions["trade_date"].astype(str).isin(wanted_dates)
        ].copy()
    except CatalogError:
        suspensions = pd.DataFrame(columns=["ts_code", "trade_date", "suspend_type"])

    observations = []
    for request in plan:
        params = public_request_params(request)
        source_api = f"tushare.{request.api_name}"
        frame = load_latest_request(source_api, params)
        profile = profile_moneyflow_batch(
            request.api_name,
            request.trade_date,
            frame,
            daily=daily,
            suspensions=suspensions,
        )
        observations.append(
            {
                "request": {"source_api": source_api, "params": params},
                "latest_evidence": latest_request_evidence(source_api, params),
                "revision": _revision_summary(source_api, params),
                "profile": profile,
            }
        )

    primary = [item for item in observations if item["profile"]["api"] == PRIMARY_MONEYFLOW_API]
    primary_failures = [
        item["profile"]["trade_date"]
        for item in primary
        if item["profile"]["gate_status"] != "PASS"
    ]
    primary_revisions = [
        item["profile"]["trade_date"]
        for item in primary
        if item["revision"]["status"] == "REVISION_OBSERVED"
    ]
    decision = "GO_DATA_ONLY" if primary and not primary_failures and not primary_revisions else "NO_GO"
    return {
        "schema_version": "p1-moneyflow-quality-v1",
        "started_at": started_at,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "git_head": git_head(),
        "production_code_snapshot_sha256": code_snapshot_sha256(),
        "p1_tool_snapshot_sha256": tool_snapshot_sha256(),
        "ingest_snapshot_sha256": ingest_snapshot_sha256(),
        "scope": "isolated_data_feasibility_only",
        "production_model_or_signal_changed": False,
        "pit_policy": PIT_POLICY,
        "collection": {
            "requested_count": requested_count,
            "collected_count": collected_count,
            "skipped_committed_count": skipped_count,
        },
        "decision": {
            "status": decision,
            "primary_api": f"tushare.{PRIMARY_MONEYFLOW_API}",
            "primary_failure_dates": primary_failures,
            "primary_revision_dates": primary_revisions,
            "authorization": (
                "isolated_incremental_factor_experiment" if decision == "GO_DATA_ONLY" else "none"
            ),
            "production_authorization": "none",
        },
        "observations": observations,
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    apis = tuple(args.api or (PRIMARY_MONEYFLOW_API,))
    plan = build_moneyflow_plan(args.trade_date, apis=apis)
    requested_count = len(plan)
    if args.dry_run:
        print(
            json.dumps(
                {
                    "apis": list(apis),
                    "refresh": args.refresh,
                    "request_count": requested_count,
                    "trade_dates": sorted(set(args.trade_date)),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0

    started_at = datetime.now(timezone.utc).isoformat()
    settings = load()
    pending = plan
    if not args.refresh:
        committed = {
            api: committed_params_keys(f"tushare.{api}")
            for api in apis
        }
        pending = [
            request
            for request in plan
            if canonical_params_key(public_request_params(request))
            not in committed[request.api_name]
        ]

    batches = []
    if pending:
        secret = settings.runtime.tushare_token
        if secret is None or not secret.get_secret_value().strip():
            raise SystemExit("TUSHARE_TOKEN is missing from local .env")
        batches = MoneyflowIngestor(
            client=create_client(secret.get_secret_value()),
            writer=RawBatchWriter(settings.runtime.data_root),
            settings=settings,
        ).run(pending)

    report = _build_report(
        plan=plan,
        started_at=started_at,
        requested_count=requested_count,
        collected_count=len(batches),
        skipped_count=requested_count - len(pending),
    )
    report_path = args.report if args.report.is_absolute() else PROJECT_ROOT / args.report
    write_project_json(report_path, report)
    print(
        json.dumps(
            {
                "decision": report["decision"]["status"],
                "report": str(report_path.relative_to(PROJECT_ROOT)),
                "requested_count": requested_count,
                "collected_count": len(batches),
                "skipped_committed_count": requested_count - len(pending),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if report["decision"]["status"] == "GO_DATA_ONLY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
