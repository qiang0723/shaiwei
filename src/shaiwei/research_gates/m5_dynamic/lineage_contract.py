"""Strict value contracts for M5 statement-version lineage recovery."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

import yaml

from .contract import (
    IDENTITY_FIELDS,
    STATEMENT_FIELDS,
    M5GateError,
    canonical_json,
    sha256_file,
    sha256_json,
)


PROTOCOL_ID = "m5-dynamic-fundamental-source-lineage-recovery-v3"
BUILD_PROTOCOL_ID = "m5-dynamic-fundamental-source-lineage-build-v4"
PROTOCOL_SCOPE_SHA256 = "0e4ea4ee6c283b9fad28e1b289f146199154a3e2f5c65d5255d2e462cacb20bc"
CASE_ID = "8000c9e107c100cdb41edace547f5869dddda6807005c142ce2847d9433f49ff"
SOURCE_APIS = tuple(f"tushare.{name}{suffix}" for name in STATEMENT_FIELDS for suffix in ("", "_vip"))
EVIDENCE_TIERS = {
    "E0_VALUE_VARIANT_ONLY",
    "E1_LOCAL_OBSERVATION",
    "E2_PROVIDER_DECLARED_VERSION",
    "E3_AUTHORITATIVE_PRIMARY_DOCUMENT",
}
AUTHORITATIVE_TIERS = {
    "E2_PROVIDER_DECLARED_VERSION",
    "E3_AUTHORITATIVE_PRIMARY_DOCUMENT",
}
CONTROL_PATHS = {
    "protocol": "config/m5_dynamic_fundamental_source_lineage_recovery_v3.yaml",
    "build": "config/m5_dynamic_fundamental_source_lineage_build_v4.yaml",
    "scope": "config/m5_dynamic_fundamental_source_lineage_recovery_protocol_scope_v4.json",
    "research": "config/m5_dynamic_fundamental_cross_pool_v1.yaml",
    "manifest": "config/m5_dynamic_fundamental_source_lineage_input_v1.json",
    "release": "config/m5_dynamic_fundamental_source_lineage_release_scope_v2.json",
    "approval": "config/m5_dynamic_fundamental_source_lineage_approval_v1.json",
}


def require_sha256(value: Any, name: str) -> str:
    normalized = str(value)
    if len(normalized) != 64 or any(char not in "0123456789abcdef" for char in normalized):
        raise M5GateError(f"{name} must be a lowercase SHA-256")
    return normalized


def require_utc(value: Any, name: str) -> str:
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError as exc:
        raise M5GateError(f"{name} must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise M5GateError(f"{name} must include timezone")
    return parsed.astimezone(timezone.utc).isoformat()


def safe_relative(value: Any, name: str) -> str:
    path = PurePosixPath(str(value))
    if path.is_absolute() or not path.parts or ".." in path.parts:
        raise M5GateError(f"{name} must be project-relative")
    return path.as_posix()


@dataclass(frozen=True)
class LineageProtocol:
    document: dict[str, Any]
    build_document: dict[str, Any]
    scope_document: dict[str, Any]
    sha256: str

    @classmethod
    def load(
        cls,
        *,
        protocol_path: Path,
        build_path: Path,
        scope_path: Path,
        project_root: Path,
    ) -> LineageProtocol:
        document = yaml.safe_load(protocol_path.read_text(encoding="utf-8"))
        build = yaml.safe_load(build_path.read_text(encoding="utf-8"))
        serialized_scope = scope_path.read_text(encoding="utf-8")
        scope = json.loads(serialized_scope)
        if not all(isinstance(value, dict) for value in (document, build, scope)):
            raise M5GateError("M5 lineage control documents must be objects")
        if document.get("recovery_protocol_id") != PROTOCOL_ID:
            raise M5GateError("M5 lineage protocol ID differs")
        if build.get("build_protocol_id") != BUILD_PROTOCOL_ID:
            raise M5GateError("M5 lineage build protocol ID differs")
        if build.get("protocol_scope_sha256") != PROTOCOL_SCOPE_SHA256:
            raise M5GateError("M5 lineage build scope differs")
        if build.get("derived_case_id") != CASE_ID:
            raise M5GateError("M5 lineage case identity differs")
        if serialized_scope != json.dumps(scope, ensure_ascii=False, indent=2) + "\n":
            raise M5GateError("M5 lineage protocol scope serialization differs")
        scope_body = scope.get("scope")
        if (
            not isinstance(scope_body, dict)
            or scope.get("protocol_scope_sha256") != sha256_json(scope_body)
            or scope.get("protocol_scope_sha256") != PROTOCOL_SCOPE_SHA256
        ):
            raise M5GateError("M5 lineage protocol scope hash differs")
        for item in build.get("frozen_inputs", {}).values():
            relative = safe_relative(item.get("path"), "M5 lineage frozen input")
            path = project_root / relative
            if not path.is_file() or sha256_file(path) != require_sha256(
                item.get("sha256"), "M5 lineage frozen input"
            ):
                raise M5GateError("M5 lineage frozen input hash differs")
        return cls(
            document=document,
            build_document=build,
            scope_document=scope,
            sha256=sha256_file(protocol_path),
        )


@dataclass(frozen=True)
class Observation:
    table: str
    source_kind: str
    source_api: str
    statement_identity: tuple[str, ...]
    business_values: dict[str, Any]
    request_params_sha256: str
    batch_id: str
    content_sha256: str
    local_observed_at: str

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> Observation:
        expected = {
            "table",
            "source_kind",
            "source_api",
            "statement_identity",
            "business_values",
            "request_params_sha256",
            "batch_id",
            "content_sha256",
            "local_observed_at",
        }
        if not isinstance(value, dict) or set(value) != expected:
            raise M5GateError("M5 lineage observation fields differ")
        table = str(value["table"])
        if table not in STATEMENT_FIELDS:
            raise M5GateError("M5 lineage observation table differs")
        source_kind = str(value["source_kind"])
        expected_api = f"tushare.{table}{'_vip' if source_kind == 'VIP' else ''}"
        if source_kind not in {"STANDARD", "VIP"} or value["source_api"] != expected_api:
            raise M5GateError("M5 lineage observation source differs")
        identity = value["statement_identity"]
        if not isinstance(identity, dict) or set(identity) != set(IDENTITY_FIELDS):
            raise M5GateError("M5 lineage statement identity fields differ")
        normalized_identity = tuple(str(identity[field]).replace("-", "") for field in IDENTITY_FIELDS)
        if any(not item or item.lower() in {"none", "nan", "<na>"} for item in normalized_identity):
            raise M5GateError("M5 lineage statement identity is missing")
        business = value["business_values"]
        if not isinstance(business, dict) or set(business) != set(STATEMENT_FIELDS[table]):
            raise M5GateError("M5 lineage business fields differ")
        batch_id = str(value["batch_id"])
        if not batch_id or len(batch_id) > 200:
            raise M5GateError("M5 lineage batch identity is invalid")
        return cls(
            table=table,
            source_kind=source_kind,
            source_api=str(value["source_api"]),
            statement_identity=normalized_identity,
            business_values=dict(business),
            request_params_sha256=require_sha256(value["request_params_sha256"], "M5 lineage request params"),
            batch_id=batch_id,
            content_sha256=require_sha256(value["content_sha256"], "M5 lineage content"),
            local_observed_at=require_utc(value["local_observed_at"], "local_observed_at"),
        )


@dataclass(frozen=True)
class VersionEvidence:
    table: str
    statement_identity: tuple[str, ...]
    provider_version_id_sha256: str
    value_version_sha256: str
    predecessor_provider_version_id_sha256: str | None
    evidence_tier: str
    provider_revision_effective_at: str
    evidence_content_sha256: str
    evidence_locator_sha256: str

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> VersionEvidence:
        expected = {
            "table",
            "statement_identity",
            "provider_version_id_sha256",
            "value_version_sha256",
            "predecessor_provider_version_id_sha256",
            "evidence_tier",
            "provider_revision_effective_at",
            "evidence_content_sha256",
            "evidence_locator_sha256",
        }
        if not isinstance(value, dict) or set(value) != expected:
            raise M5GateError("M5 lineage evidence fields differ")
        table = str(value["table"])
        if table not in STATEMENT_FIELDS:
            raise M5GateError("M5 lineage evidence table differs")
        identity = value["statement_identity"]
        if not isinstance(identity, dict) or set(identity) != set(IDENTITY_FIELDS):
            raise M5GateError("M5 lineage evidence identity fields differ")
        tier = str(value["evidence_tier"])
        if tier not in AUTHORITATIVE_TIERS:
            raise M5GateError("M5 lineage evidence lacks historical authority")
        predecessor = value["predecessor_provider_version_id_sha256"]
        return cls(
            table=table,
            statement_identity=tuple(str(identity[field]).replace("-", "") for field in IDENTITY_FIELDS),
            provider_version_id_sha256=require_sha256(
                value["provider_version_id_sha256"], "provider version"
            ),
            value_version_sha256=require_sha256(value["value_version_sha256"], "value version"),
            predecessor_provider_version_id_sha256=(
                None if predecessor is None else require_sha256(predecessor, "predecessor provider version")
            ),
            evidence_tier=tier,
            provider_revision_effective_at=require_utc(
                value["provider_revision_effective_at"],
                "provider_revision_effective_at",
            ),
            evidence_content_sha256=require_sha256(value["evidence_content_sha256"], "evidence content"),
            evidence_locator_sha256=require_sha256(value["evidence_locator_sha256"], "evidence locator"),
        )


@dataclass(frozen=True)
class LineageInputManifest:
    document: dict[str, Any]
    sha256: str
    physical_sha256: str

    @classmethod
    def load(cls, path: Path) -> LineageInputManifest:
        serialized = path.read_text(encoding="utf-8")
        document = json.loads(serialized)
        expected = {
            "schema_version",
            "created_at",
            "protocol_scope_sha256",
            "semantic_rows_read",
            "prior_conflict_identity",
            "ledger_selection_scope",
            "anchor_sources",
            "history_sources",
            "authoritative_evidence",
        }
        if (
            not isinstance(document, dict)
            or set(document) != expected
            or document.get("schema_version") != "m5-source-lineage-input-v1"
            or serialized != canonical_json(document) + "\n"
            or document.get("protocol_scope_sha256") != PROTOCOL_SCOPE_SHA256
            or document.get("semantic_rows_read") is not False
        ):
            raise M5GateError("M5 lineage input manifest differs")
        require_utc(document["created_at"], "M5 lineage manifest created_at")
        if tuple(document["ledger_selection_scope"]) != SOURCE_APIS:
            raise M5GateError("M5 lineage input source allowlist differs")
        if document["authoritative_evidence"] != []:
            raise M5GateError("M5 lineage initial release must not smuggle external evidence")
        prior = document["prior_conflict_identity"]
        if (
            not isinstance(prior, dict)
            or prior.get("case_id") != "a2539149d588a0c19f9cb73331f19a66df63e301df03f56fbb2c8e5c74672068"
            or prior.get("release_scope_sha256")
            != "8858912f14577a8911e47f0ec338cde82208fe818b4c7a921578e42aeeed6f65"
            or prior.get("conflict_group_count") != 23
            or prior.get("conflict_groups_by_table") != {"balancesheet": 8, "cashflow": 15, "income": 0}
        ):
            raise M5GateError("M5 lineage prior conflict identity differs")
        for name in ("anchor_sources", "history_sources"):
            _validate_source_inventory(document[name], name)
        logical = sha256_json(document)
        return cls(document=document, sha256=logical, physical_sha256=sha256_file(path))


def _validate_source_inventory(value: Any, name: str) -> None:
    if not isinstance(value, list) or [item.get("source_api") for item in value] != list(SOURCE_APIS):
        raise M5GateError(f"M5 lineage {name} source ordering differs")
    seen: set[str] = set()
    required = {
        "batch_id",
        "batch_identity_sha256",
        "relative_path",
        "content_sha256",
        "request_params_sha256",
        "row_count",
        "bytes",
        "schema_fields",
        "ingest_time",
    }
    for source in value:
        if set(source) != {"source_api", "selection_sha256", "batches"}:
            raise M5GateError(f"M5 lineage {name} source fields differ")
        batches = source["batches"]
        if not isinstance(batches, list) or source["selection_sha256"] != sha256_json(batches):
            raise M5GateError(f"M5 lineage {name} source commitment differs")
        for batch in batches:
            if not isinstance(batch, dict) or set(batch) != required:
                raise M5GateError(f"M5 lineage {name} batch fields differ")
            batch_id = str(batch["batch_id"])
            if not batch_id or batch_id in seen:
                raise M5GateError(f"M5 lineage {name} batch identity differs")
            seen.add(batch_id)
            safe_relative(batch["relative_path"], f"M5 lineage {name} batch path")
            require_sha256(batch["batch_identity_sha256"], "batch identity")
            require_sha256(batch["content_sha256"], "batch content")
            require_sha256(batch["request_params_sha256"], "batch request params")
            require_utc(batch["ingest_time"], "batch ingest_time")
            if int(batch["row_count"]) < 0 or int(batch["bytes"]) < 0:
                raise M5GateError(f"M5 lineage {name} batch size differs")
