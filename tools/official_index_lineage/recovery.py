"""Bounded M2-0R2 recovery: refresh one Tushare partition and rescan official lineage."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Protocol

import pandas as pd

from shaiwei.config import Settings, load
from shaiwei.ingest.catalog import latest_request_evidence
from shaiwei.ingest.core import RawBatchWriter
from shaiwei.ingest.tushare import create_client
from shaiwei.ledger import ingest_snapshot_sha256
from shaiwei.provenance import git_head
from tools.official_index_lineage.audit import audit
from tools.official_index_lineage.contract import (
    DataGateError,
    Request,
    StableCollector,
    load_protocol,
    project_path,
    sha256_file,
    tool_snapshot_sha256,
    write_immutable_json,
)
from tools.official_index_lineage.discovery import discover
from tools.official_index_lineage.recovery_contract import (
    DEFAULT_RECOVERY,
    build_effective_protocol,
    load_recovery,
    request_pair,
    target_request,
    validate_original_collection,
    write_immutable_yaml,
)
from tools.official_index_lineage.source_store import ContentAddressedFetcher


class QueryClient(Protocol):
    def query(self, api_name: str, **kwargs: object) -> pd.DataFrame: ...


class _CountingClient:
    def __init__(self, client: QueryClient, maximum: int) -> None:
        self.client = client
        self.maximum = maximum
        self.query_count = 0

    def query(self, api_name: str, **kwargs: object) -> pd.DataFrame:
        self.query_count += 1
        if self.query_count > self.maximum:
            raise DataGateError("recovery query count exceeded frozen maximum")
        return self.client.query(api_name, **kwargs)


def _current_evidence(plan: list[Request]) -> list[dict[str, object]]:
    return [latest_request_evidence(f"tushare.{item.api_name}", item.public_params) for item in plan]


def _verify_reused(
    plan: list[Request], old: dict[tuple[str, str], dict[str, object]], current: list[dict[str, object]], target: Request
) -> None:
    for request, item in zip(plan, current, strict=True):
        if request_pair(request) == request_pair(target):
            continue
        if item != old[request_pair(request)]:
            raise DataGateError(f"reused evidence drift: {request.api_name}:{request.partition_name}")


def _single_attempt(settings: Settings) -> Settings:
    ingest = settings.ingest.model_copy(update={"max_attempts": 1})
    return settings.model_copy(update={"ingest": ingest})


def _refresh_target(config: dict[str, object], request: Request, probe_path: Path) -> dict[str, object]:
    settings = load()
    token = settings.runtime.tushare_token
    if token is None or not token.get_secret_value().strip():
        raise DataGateError("TUSHARE_TOKEN is missing from project .env")
    client = _CountingClient(create_client(token.get_secret_value()), maximum=2)
    collector = StableCollector(
        client=client,
        writer=RawBatchWriter(settings.runtime.data_root),
        settings=_single_attempt(settings),
        operator="docker-m2-star200-recovery-v2",
    )
    batch, probe = collector.collect(request)
    if client.query_count != 2:
        raise DataGateError("recovery did not make exactly two provider queries")
    evidence = latest_request_evidence(f"tushare.{request.api_name}", request.public_params)
    if evidence["batch_id"] != batch.batch_id or evidence["content_sha256"] != batch.content_sha256:
        raise DataGateError("refreshed batch is not the latest committed evidence")
    payload = {
        "schema_version": "m2-star200-target-refresh-probe-v2",
        "recovery_id": config["recovery_id"],
        "tool_snapshot_sha256": tool_snapshot_sha256(),
        "git_head": git_head(),
        "query_count": client.query_count,
        "probe": probe,
        "refreshed_target_evidence": evidence,
    }
    write_immutable_json(probe_path, payload)
    return payload


def _load_or_refresh_target(
    config: dict[str, object], plan: list[Request], old: dict[tuple[str, str], dict[str, object]], target: Request
) -> dict[str, object]:
    root = project_path(str(config["outputs"]["root"]))
    probe_path = root / "target_refresh_probe.json"
    current = _current_evidence(plan)
    _verify_reused(plan, old, current, target)
    target_current = current[plan.index(target)]
    original_target = old[request_pair(target)]
    if target_current == original_target:
        if probe_path.exists():
            raise DataGateError("refresh probe exists but latest target is still original")
        return _refresh_target(config, target, probe_path)
    if not probe_path.exists():
        raise DataGateError("new target batch exists without immutable double-query probe")
    payload = json.loads(probe_path.read_text(encoding="utf-8"))
    if payload.get("query_count") != 2 or payload.get("refreshed_target_evidence") != target_current:
        raise DataGateError("target refresh probe differs from latest evidence")
    return payload


def build_collection_report(
    config: dict[str, object], effective_path: Path, original_report: dict[str, object],
    plan: list[Request], old: dict[tuple[str, str], dict[str, object]],
    old_probes: dict[tuple[str, str], dict[str, object]], refresh: dict[str, object],
) -> dict[str, object]:
    current = _current_evidence(plan)
    target = target_request(config)
    _verify_reused(plan, old, current, target)
    refreshed = refresh["refreshed_target_evidence"]
    if (
        current[plan.index(target)] != refreshed
        or refreshed["batch_id"] == old[request_pair(target)]["batch_id"]
    ):
        raise DataGateError("target request was not refreshed into a new immutable batch")
    probes = dict(old_probes)
    probes[request_pair(target)] = refresh["probe"]
    return {
        "schema_version": "official-index-source-recovery-collection-v2",
        "protocol_schema_version": "m2-star200-data-protocol-v1",
        "protocol_config_sha256": sha256_file(effective_path),
        "protocol_document_sha256": config["recovery_document_sha256"],
        "tool_snapshot_sha256": tool_snapshot_sha256(),
        "git_head": git_head(),
        "index_code": "000699.SH",
        "start_date": "2024-08-20",
        "end_date": "2026-07-31",
        "request_count": 27,
        "reused_request_count": 26,
        "refreshed_request_count": 1,
        "new_request_count": 1,
        "refresh_query_count": 2,
        "request_evidence": current,
        "revision_probes": [probes[request_pair(item)] for item in plan],
        "revision_mismatch_count": 0,
        "original_collection_report_sha256": sha256_file(project_path(str(config["original_evidence"]["collection_report"]["path"]))),
        "original_ingest_snapshot_sha256": original_report["ingest_snapshot_sha256"],
        "ingest_snapshot_sha256": ingest_snapshot_sha256(),
        "original_target_evidence": old[request_pair(target)],
        "refreshed_target_evidence": refreshed,
        "scope": "official_membership_lineage_and_source_data_recovery_v2_only",
        "factor_results_inspected": False,
        "production_changed": False,
        "status": "COLLECTED_PENDING_OFFICIAL_LINEAGE_GATE",
    }


def _load_completed_collection(
    path: Path,
    effective_path: Path,
    plan: list[Request],
    old: dict[tuple[str, str], dict[str, object]],
    target: Request,
    probe_path: Path,
) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("protocol_config_sha256") != sha256_file(effective_path):
        raise DataGateError("completed collection is bound to another effective protocol")
    current = _current_evidence(plan)
    if payload.get("request_evidence") != current:
        raise DataGateError("latest request evidence differs from completed recovery")
    refreshed = current[plan.index(target)]
    original = old[request_pair(target)]
    if (
        payload.get("reused_request_count") != 26
        or payload.get("refreshed_request_count") != 1
        or payload.get("refresh_query_count") != 2
        or payload.get("revision_mismatch_count") != 0
        or payload.get("original_target_evidence") != original
        or payload.get("refreshed_target_evidence") != refreshed
        or refreshed["batch_id"] == original["batch_id"]
    ):
        raise DataGateError("completed recovery query proof is invalid")
    if not probe_path.exists():
        raise DataGateError("completed recovery target probe is missing")
    probe = json.loads(probe_path.read_text(encoding="utf-8"))
    if probe.get("query_count") != 2 or probe.get("refreshed_target_evidence") != refreshed:
        raise DataGateError("completed recovery target probe differs")
    return payload


def run(recovery_path: Path = DEFAULT_RECOVERY) -> dict[str, object]:
    config = load_recovery(recovery_path)
    original_path = project_path(str(config["original_protocol"]["path"]))
    original = load_protocol(original_path)
    original_collection_path = project_path(str(config["original_evidence"]["collection_report"]["path"]))
    original_report = json.loads(original_collection_path.read_text(encoding="utf-8"))
    plan, old, old_probes = validate_original_collection(config, original, original_report)
    effective = build_effective_protocol(config, original)
    effective_path = project_path(str(config["outputs"]["effective_protocol"]))
    write_immutable_yaml(effective_path, effective)
    load_protocol(effective_path)
    collection_path = project_path(str(config["outputs"]["collection_report"]))
    probe_path = project_path(str(config["outputs"]["root"])) / "target_refresh_probe.json"
    if collection_path.exists():
        collection = _load_completed_collection(
            collection_path, effective_path, plan, old, target_request(config), probe_path
        )
        collection_created = False
    else:
        refresh = _load_or_refresh_target(config, plan, old, target_request(config))
        collection = build_collection_report(
            config, effective_path, original_report, plan, old, old_probes, refresh
        )
        collection_created = write_immutable_json(collection_path, collection)
    discovery = discover(ContentAddressedFetcher(effective), effective, effective_path)
    discovery_path = project_path(str(discovery["report_path"]))
    result = audit(
        effective_path,
        collection_path,
        discovery_path,
        report_override=project_path(str(config["outputs"]["quality_report"])),
        manifest_override=project_path(str(config["outputs"]["tracked_manifest"])),
    )
    report = result["report"]
    return {
        "status": "COMPLETED" if collection_created else "REUSED_COMPLETED_COLLECTION",
        "refresh_query_count": 2 if collection_created else 0,
        "archive_page_count": discovery["archive_page_count"],
        "candidate_announcement_count": discovery["candidate_announcement_count"],
        "attachment_count": discovery["attachment_count"],
        "tushare_source_collection_pass": report["tushare_source_collection_pass"],
        "official_adjustment_lineage_complete": report["official_adjustment_lineage_complete"],
        "pit_constructible": report["pit_constructible"],
        "strategy_results_inspected": report["strategy_results_inspected"],
        "production_authorization": report["production_authorization"],
        "verdict": report["verdict"],
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recovery", type=Path, default=DEFAULT_RECOVERY)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    output = run(parse_args(argv).recovery)
    print(json.dumps(output, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
