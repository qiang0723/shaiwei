"""Strict schema and effective-protocol contract for M2-0R2 recovery."""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path

import yaml

from shaiwei.config import PROJECT_ROOT
from shaiwei.ingest.catalog import canonical_params_key
from tools.official_index_lineage.contract import (
    DataGateError,
    Request,
    build_plan,
    project_path,
    sha256_file,
)

DEFAULT_RECOVERY = PROJECT_ROOT / "config" / "m2_star200_data_recovery_v2.yaml"
TOP_LEVEL_KEYS = {
    "schema_version", "recovery_id", "frozen_at", "recovery_document",
    "recovery_document_sha256", "original_protocol", "original_evidence",
    "original_target_batch", "target_request", "evidence_reuse", "official_refresh",
    "outputs", "factor_results_inspected", "llm_execution_authorized", "production_authorization",
}
EVIDENCE_KEYS = {"collection_report", "discovery_report", "quality_report", "tracked_manifest"}
OUTPUT_KEYS = {"root", "effective_protocol", "collection_report", "quality_report", "tracked_manifest"}
EXPECTED_OUTPUTS = {
    "root": "data/research/star200/m2-star200-data-recovery-v2",
    "effective_protocol": "data/research/star200/m2-star200-data-recovery-v2/effective_protocol.yaml",
    "collection_report": "data/research/star200/m2-star200-data-recovery-v2/collection_report.json",
    "quality_report": "data/research/star200/m2-star200-data-recovery-v2/quality_report.json",
    "tracked_manifest": "config/m2_star200_manifest_recovery_v2.json",
}
TARGET_VALUES = {
    "api_name": "index_weight",
    "index_code": "000699.SH",
    "start_date": "20260701",
    "end_date": "20260731",
    "fields": "index_code,con_code,trade_date,weight",
    "partition_name": "2026-07",
    "immediate_double_query_required": True,
    "maximum_query_count": 2,
    "bse_row_count_maximum": 0,
}


def _strict_keys(payload: object, expected: set[str], label: str) -> dict[str, object]:
    if not isinstance(payload, dict) or set(payload) != expected:
        observed = set(payload) if isinstance(payload, dict) else set()
        raise DataGateError(
            f"{label} schema drift: missing={sorted(expected - observed)}, "
            f"extra={sorted(observed - expected)}"
        )
    return payload


def _verify_identity(item: object, label: str) -> dict[str, object]:
    value = _strict_keys(item, {"path", "sha256"}, label)
    path = project_path(str(value["path"]))
    if sha256_file(path) != value["sha256"]:
        raise DataGateError(f"{label} hash mismatch")
    return value


def load_recovery(path: Path = DEFAULT_RECOVERY) -> dict[str, object]:
    config_path = path if path.is_absolute() else PROJECT_ROOT / path
    payload = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    value = _strict_keys(payload, TOP_LEVEL_KEYS, "recovery")
    if value["schema_version"] != "m2-star200-data-recovery-v2":
        raise DataGateError("unexpected recovery schema")
    if value["recovery_id"] != "m2-star200-data-recovery-v2":
        raise DataGateError("unexpected recovery identity")
    if value["frozen_at"] != "2026-08-04T21:45:00+08:00":
        raise DataGateError("recovery freeze timestamp drift")
    if value["recovery_document"] != "docs/M2_STAR200_DATA_RECOVERY_V2_PROTOCOL_20260804.md":
        raise DataGateError("recovery document identity drift")
    if value["factor_results_inspected"] is not False:
        raise DataGateError("recovery cannot inspect factor results")
    if value["llm_execution_authorized"] is not False or value["production_authorization"] != "none":
        raise DataGateError("recovery cannot authorize LLM or production execution")
    document = project_path(str(value["recovery_document"]))
    if sha256_file(document) != value["recovery_document_sha256"]:
        raise DataGateError("recovery document hash mismatch")
    _verify_identity(value["original_protocol"], "original protocol")
    evidence = _strict_keys(value["original_evidence"], EVIDENCE_KEYS, "original evidence")
    for name in sorted(EVIDENCE_KEYS):
        _verify_identity(evidence[name], f"original {name}")
    if value["target_request"] != TARGET_VALUES:
        raise DataGateError("target request drift")
    target_batch = _strict_keys(
        value["original_target_batch"], {"batch_id", "row_count", "content_sha256"}, "target batch"
    )
    if target_batch != {
        "batch_id": "33aa80a00744",
        "row_count": 0,
        "content_sha256": "4d83ccdf175fc9ed59d5e06d441fa58da65728622c80e3456bcf9caa9d7c899c",
    }:
        raise DataGateError("original target batch identity drift")
    reuse = _strict_keys(
        value["evidence_reuse"],
        {"total_request_count", "reused_request_count", "refreshed_request_count", "old_request_files_must_rehash"},
        "evidence reuse",
    )
    if reuse != {
        "total_request_count": 27, "reused_request_count": 26,
        "refreshed_request_count": 1, "old_request_files_must_rehash": True,
    }:
        raise DataGateError("evidence reuse contract drift")
    refresh = _strict_keys(
        value["official_refresh"],
        {"discovery_end_date", "raw_source_root", "full_archive_rescan_from_launch", "old_official_cache_reuse"},
        "official refresh",
    )
    if refresh["discovery_end_date"] != "2026-08-04":
        raise DataGateError("official discovery cutoff drift")
    if refresh["full_archive_rescan_from_launch"] is not True or refresh["old_official_cache_reuse"] is not False:
        raise DataGateError("official refresh isolation drift")
    outputs = _strict_keys(value["outputs"], OUTPUT_KEYS, "outputs")
    if outputs != EXPECTED_OUTPUTS:
        raise DataGateError("recovery output identity drift")
    root = project_path(str(outputs["root"]))
    for name in ("effective_protocol", "collection_report", "quality_report"):
        output = project_path(str(outputs[name]))
        if output != root / output.name:
            raise DataGateError(f"{name} must be a direct child of the recovery root")
    if project_path(str(refresh["raw_source_root"])) != root / "official_sources":
        raise DataGateError("official raw root must be isolated under recovery root")
    project_path(str(outputs["tracked_manifest"]))
    return value


def target_request(config: dict[str, object]) -> Request:
    target = config["target_request"]
    return Request(
        str(target["api_name"]), str(target["index_code"]), str(target["start_date"]),
        str(target["end_date"]), str(target["partition_name"]),
    )


def _diff_paths(left: object, right: object, prefix: str = "") -> set[str]:
    if isinstance(left, dict) and isinstance(right, dict):
        paths: set[str] = set()
        for key in set(left) | set(right):
            child = f"{prefix}.{key}" if prefix else str(key)
            paths.add(child) if key not in left or key not in right else paths.update(
                _diff_paths(left[key], right[key], child)
            )
        return paths
    return set() if left == right else {prefix}


def build_effective_protocol(config: dict[str, object], original: dict[str, object]) -> dict[str, object]:
    effective = copy.deepcopy(original)
    outputs, refresh = config["outputs"], config["official_refresh"]
    root = str(outputs["root"])
    effective.update(
        frozen_at=config["frozen_at"],
        scope="official_membership_lineage_and_source_data_recovery_v2_only",
        protocol_document=config["recovery_document"],
        protocol_sha256=config["recovery_document_sha256"],
    )
    effective["identity"].update(
        research_family=config["recovery_id"], source_cutoff_date=refresh["discovery_end_date"],
        dataset_id="star200-official-lineage-recovery-v2", config_id=config["schema_version"],
        raw_source_root=refresh["raw_source_root"], initial_set_artifact=f"{root}/initial_set.parquet",
        membership_events_artifact=f"{root}/membership_events.parquet",
        daily_membership_artifact=f"{root}/daily_membership.parquet",
        collection_report=outputs["collection_report"], quality_report=outputs["quality_report"],
        tracked_manifest=outputs["tracked_manifest"],
    )
    effective["official_source_policy"]["discovery_end_date"] = refresh["discovery_end_date"]
    allowed = {
        "frozen_at", "scope", "protocol_document", "protocol_sha256",
        "identity.research_family", "identity.source_cutoff_date", "identity.dataset_id",
        "identity.config_id", "identity.raw_source_root", "identity.initial_set_artifact",
        "identity.membership_events_artifact", "identity.daily_membership_artifact",
        "identity.collection_report", "identity.quality_report", "identity.tracked_manifest",
        "official_source_policy.discovery_end_date",
    }
    if observed := _diff_paths(original, effective) - allowed:
        raise DataGateError(f"effective protocol changed forbidden fields: {sorted(observed)}")
    return effective


def write_immutable_yaml(path: Path, payload: dict[str, object]) -> bool:
    rendered = yaml.safe_dump(payload, allow_unicode=True, sort_keys=False)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_text(encoding="utf-8") != rendered:
            raise FileExistsError(f"immutable protocol differs: {path}")
        return False
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(rendered, encoding="utf-8")
    os.link(temporary, path)
    temporary.unlink()
    return True


def request_pair(request: Request) -> tuple[str, str]:
    return request.api_name, canonical_params_key(request.public_params)


def validate_original_collection(
    config: dict[str, object], original: dict[str, object], report: dict[str, object]
) -> tuple[list[Request], dict[tuple[str, str], dict[str, object]], dict[tuple[str, str], dict[str, object]]]:
    plan = build_plan(original)
    if len(plan) != 27 or report.get("request_count") != 27:
        raise DataGateError("original collection request count drift")
    evidence = {
        (str(item["source_api"]).removeprefix("tushare."), canonical_params_key(json.loads(str(item["params_json"])))): item
        for item in report.get("request_evidence", [])
    }
    probes = {
        (str(item["api_name"]), str(item["params_key"])): item
        for item in report.get("revision_probes", [])
    }
    expected = {request_pair(request) for request in plan}
    if set(evidence) != expected or set(probes) != expected:
        raise DataGateError("original evidence does not cover the frozen request plan")
    target_evidence = evidence[request_pair(target_request(config))]
    for key in ("batch_id", "row_count", "content_sha256"):
        if target_evidence[key] != config["original_target_batch"][key]:
            raise DataGateError(f"original target batch {key} drift")
    return plan, evidence, probes
