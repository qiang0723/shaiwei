"""Collect immutable Star100 index history after two-query stability probes."""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

import pandas as pd

from shaiwei.config import PROJECT_ROOT, load
from shaiwei.ingest.catalog import canonical_params_key, committed_params_keys, latest_request_evidence
from shaiwei.ingest.core import RawBatchWriter
from shaiwei.ingest.tushare import create_client
from shaiwei.ledger import ingest_snapshot_sha256
from shaiwei.provenance import git_head
from tools.p4_star100.contract import (
    PROTOCOL_PATH,
    StableCollector,
    build_plan,
    sha256_file,
    tool_snapshot_sha256,
    write_immutable_json,
)


def _parse_date(value: str) -> date:
    parsed = pd.to_datetime(value, format="%Y%m%d", errors="coerce")
    if pd.isna(parsed) or parsed.strftime("%Y%m%d") != value:
        raise argparse.ArgumentTypeError("must be YYYYMMDD")
    return parsed.date()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-date", type=_parse_date, default=date(2023, 8, 7))
    parser.add_argument("--end-date", type=_parse_date, required=True)
    parser.add_argument("--report", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    plan = build_plan(args.start_date, args.end_date)
    committed_by_api = {
        api: committed_params_keys(f"tushare.{api}")
        for api in ("index_daily", "index_weight")
    }
    pending = [
        request
        for request in plan
        if canonical_params_key(request.public_params)
        not in committed_by_api[request.api_name]
    ]
    report_path = args.report if args.report.is_absolute() else PROJECT_ROOT / args.report
    existing_report: dict[str, object] | None = None
    if report_path.exists():
        existing_report = json.loads(report_path.read_text(encoding="utf-8"))
        recorded = {
            (item["api_name"], item["params_key"]): item
            for item in existing_report.get("revision_probes", [])
        }
        unproven = [
            request
            for request in pending
            if (request.api_name, canonical_params_key(request.public_params)) not in recorded
        ]
        if unproven:
            raise SystemExit("existing collection report does not cover pending request plan")

    settings = load()
    token = settings.runtime.tushare_token
    if pending and (token is None or not token.get_secret_value().strip()):
        raise SystemExit("TUSHARE_TOKEN is missing from project .env")

    probes = [] if existing_report is None else list(existing_report.get("revision_probes", []))
    if pending:
        collector = StableCollector(
            client=create_client(token.get_secret_value()),
            writer=RawBatchWriter(settings.runtime.data_root),
            settings=settings,
        )
        for request in pending:
            _, probe = collector.collect(request)
            probes.append(probe)

    evidence = [
        latest_request_evidence(f"tushare.{request.api_name}", request.public_params)
        for request in plan
    ]
    if existing_report is not None and not pending:
        if evidence != existing_report.get("request_evidence"):
            raise SystemExit("committed request evidence differs from immutable collection report")
        recorded_pairs = {
            (item["api_name"], item["params_key"])
            for item in existing_report.get("revision_probes", [])
            if item.get("stable") is True
        }
        planned_pairs = {
            (request.api_name, canonical_params_key(request.public_params))
            for request in plan
        }
        if recorded_pairs != planned_pairs:
            raise SystemExit("immutable collection report lacks a stable probe for the full plan")
        print(
            json.dumps(
                {
                    "status": "REUSED_IMMUTABLE_COLLECTION",
                    "request_count": len(plan),
                    "new_request_count": 0,
                    "row_count": sum(int(item["row_count"]) for item in evidence),
                    "revision_mismatch_count": existing_report["revision_mismatch_count"],
                    "report": str(report_path.relative_to(PROJECT_ROOT)),
                    "report_created": False,
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0

    payload = {
        "schema_version": "p4-star100-collection-v1",
        "protocol_sha256": sha256_file(PROTOCOL_PATH),
        "tool_snapshot_sha256": tool_snapshot_sha256(),
        "git_head": git_head(),
        "index_code": "000698.SH",
        "start_date": args.start_date.isoformat(),
        "end_date": args.end_date.isoformat(),
        "request_count": len(plan),
        "new_request_count": len(pending),
        "request_evidence": evidence,
        "revision_probes": sorted(
            probes,
            key=lambda item: (str(item["api_name"]), str(item["params_key"])),
        ),
        "revision_mismatch_count": sum(not bool(item["stable"]) for item in probes),
        "ingest_snapshot_sha256": ingest_snapshot_sha256(),
        "scope": "isolated_p4_data_only",
        "production_model_or_signal_changed": False,
        "status": "COLLECTED_PENDING_OFFICIAL_LINEAGE_GATE",
    }
    created = write_immutable_json(report_path, payload)
    print(
        json.dumps(
            {
                "status": payload["status"],
                "request_count": len(plan),
                "new_request_count": len(pending),
                "row_count": sum(int(item["row_count"]) for item in evidence),
                "revision_mismatch_count": payload["revision_mismatch_count"],
                "report": str(report_path.relative_to(PROJECT_ROOT)),
                "report_created": created,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
