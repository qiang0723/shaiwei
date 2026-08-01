"""Collect frozen index_daily/index_weight partitions with immediate double queries."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from shaiwei.config import PROJECT_ROOT, load
from shaiwei.ingest.catalog import canonical_params_key, committed_params_keys, latest_request_evidence
from shaiwei.ingest.core import RawBatchWriter
from shaiwei.ingest.tushare import create_client
from shaiwei.ledger import ingest_snapshot_sha256
from shaiwei.provenance import git_head
from tools.official_index_lineage.contract import (
    StableCollector,
    build_plan,
    load_protocol,
    sha256_file,
    tool_snapshot_sha256,
    write_immutable_json,
)

DEFAULT_PROTOCOL = PROJECT_ROOT / "config" / "m2_star200_v1.yaml"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--report", type=Path)
    return parser.parse_args(argv)


def _project_path(path: Path) -> Path:
    return path if path.is_absolute() else PROJECT_ROOT / path


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    protocol_path = _project_path(args.protocol)
    protocol = load_protocol(protocol_path)
    plan = build_plan(protocol)
    report_path = _project_path(
        args.report or Path(str(protocol["identity"]["collection_report"]))
    )
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
    existing = json.loads(report_path.read_text(encoding="utf-8")) if report_path.exists() else None
    if existing is not None:
        recorded = {
            (item["api_name"], item["params_key"])
            for item in existing.get("revision_probes", [])
            if item.get("stable") is True
        }
        unproven = [
            request
            for request in pending
            if (request.api_name, canonical_params_key(request.public_params)) not in recorded
        ]
        if unproven:
            raise SystemExit("immutable collection report does not cover pending request plan")

    settings = load()
    token = settings.runtime.tushare_token
    if pending and (token is None or not token.get_secret_value().strip()):
        raise SystemExit("TUSHARE_TOKEN is missing from project .env")

    probes = [] if existing is None else list(existing.get("revision_probes", []))
    if pending:
        collector = StableCollector(
            client=create_client(token.get_secret_value()),
            writer=RawBatchWriter(settings.runtime.data_root),
            settings=settings,
            operator="docker-m2-star200",
        )
        for request in pending:
            _, probe = collector.collect(request)
            probes.append(probe)

    evidence = [
        latest_request_evidence(f"tushare.{request.api_name}", request.public_params)
        for request in plan
    ]
    planned_pairs = {
        (request.api_name, canonical_params_key(request.public_params)) for request in plan
    }
    recorded_pairs = {
        (item["api_name"], item["params_key"])
        for item in probes
        if item.get("stable") is True
    }
    if recorded_pairs != planned_pairs:
        raise SystemExit("stable double-query evidence does not cover the full request plan")

    if existing is not None and not pending:
        if evidence != existing.get("request_evidence"):
            raise SystemExit("committed request evidence differs from immutable report")
        output = {
            "status": "REUSED_IMMUTABLE_COLLECTION",
            "request_count": len(plan),
            "new_request_count": 0,
            "row_count": sum(int(item["row_count"]) for item in evidence),
            "revision_mismatch_count": existing["revision_mismatch_count"],
            "report": str(report_path.relative_to(PROJECT_ROOT)),
            "report_created": False,
        }
        print(json.dumps(output, ensure_ascii=False, sort_keys=True))
        return 0

    payload = {
        "schema_version": "official-index-source-collection-v1",
        "protocol_schema_version": protocol["schema_version"],
        "protocol_config_sha256": sha256_file(protocol_path),
        "protocol_document_sha256": protocol["protocol_sha256"],
        "tool_snapshot_sha256": tool_snapshot_sha256(),
        "git_head": git_head(),
        "index_code": protocol["identity"]["index_code"],
        "start_date": protocol["tushare_source_contract"]["index_daily_start"],
        "end_date": protocol["tushare_source_contract"]["index_daily_end"],
        "request_count": len(plan),
        "new_request_count": len(pending),
        "request_evidence": evidence,
        "revision_probes": sorted(
            probes,
            key=lambda item: (str(item["api_name"]), str(item["params_key"])),
        ),
        "revision_mismatch_count": sum(not bool(item["stable"]) for item in probes),
        "ingest_snapshot_sha256": ingest_snapshot_sha256(),
        "scope": protocol["scope"],
        "factor_results_inspected": False,
        "production_changed": False,
        "status": "COLLECTED_PENDING_OFFICIAL_LINEAGE_GATE",
    }
    created = write_immutable_json(report_path, payload)
    output = {
        "status": payload["status"],
        "request_count": len(plan),
        "new_request_count": len(pending),
        "row_count": sum(int(item["row_count"]) for item in evidence),
        "revision_mismatch_count": payload["revision_mismatch_count"],
        "report": str(report_path.relative_to(PROJECT_ROOT)),
        "report_created": created,
    }
    print(json.dumps(output, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
