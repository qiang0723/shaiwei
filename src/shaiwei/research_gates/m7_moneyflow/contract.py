"""Frozen contracts and canonical identities for the M7 key-only data gate."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

import yaml


PROTOCOL_ID = "m7-star-custom-pool-moneyflow-data-compatibility-v1"
BUILD_PROTOCOL_ID = "m7-star-custom-pool-moneyflow-data-gate-build-v1"
PROTOCOL_SCOPE_SHA256 = "3b137d0b84e557c4fa38ea5072fe22241802f7a714f5890fc365705f2b71d59b"
UNIVERSE_IDS = (
    "star-board-all-pit-v1",
    "star-board-midcap-pit-v1",
    "star-board-smallcap-pit-v1",
)
SOURCE_API = "tushare.moneyflow"
PROJECTED_SOURCE_COLUMNS = ("ts_code", "trade_date")
MEMBERSHIP_COLUMNS = ("trade_date", "formation_date", "universe_id", "ts_code", "segment")
SHA_RE = re.compile(r"^[0-9a-f]{64}$")


class M7GateError(RuntimeError):
    """A frozen M7 identity, input, authorization, or quality rule failed."""


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def require_sha256(value: Any, name: str) -> str:
    normalized = str(value)
    if SHA_RE.fullmatch(normalized) is None:
        raise M7GateError(f"{name} must be a lowercase SHA-256")
    return normalized


def safe_relative(value: Any, name: str) -> str:
    path = PurePosixPath(str(value))
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise M7GateError(f"{name} must be a safe project-relative path")
    return path.as_posix()


def _verify_frozen_inputs(build: dict[str, Any], project_root: Path) -> None:
    frozen = build.get("frozen_inputs")
    if not isinstance(frozen, dict) or not frozen:
        raise M7GateError("M7 build contract lacks frozen inputs")
    root = project_root.resolve(strict=True)
    for item in frozen.values():
        relative = safe_relative(item.get("path"), "frozen input")
        path = project_root / relative
        if path.is_symlink():
            raise M7GateError("M7 frozen input cannot be a symlink")
        try:
            resolved = path.resolve(strict=True)
            resolved.relative_to(root)
        except (FileNotFoundError, ValueError) as exc:
            raise M7GateError("M7 frozen input is missing or outside the input root") from exc
        if not resolved.is_file() or sha256_file(resolved) != require_sha256(
            item.get("sha256"), "frozen input"
        ):
            raise M7GateError("M7 frozen input content differs")


@dataclass(frozen=True)
class M7Protocol:
    path: Path
    document: dict[str, Any]
    build_document: dict[str, Any]
    sha256: str
    build_sha256: str

    @classmethod
    def load(cls, path: Path, *, build_path: Path, project_root: Path) -> M7Protocol:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        build = yaml.safe_load(build_path.read_text(encoding="utf-8"))
        if not isinstance(document, dict) or not isinstance(build, dict):
            raise M7GateError("M7 protocol and build contract must be mappings")
        if document.get("protocol_id") != PROTOCOL_ID:
            raise M7GateError("M7 protocol identity differs")
        if build.get("build_protocol_id") != BUILD_PROTOCOL_ID:
            raise M7GateError("M7 build protocol identity differs")
        if build.get("protocol_scope_sha256") != PROTOCOL_SCOPE_SHA256:
            raise M7GateError("M7 protocol scope identity differs")
        _verify_frozen_inputs(build, project_root)
        scope = document.get("scope") or {}
        if (
            scope.get("stage") != "DATA_COMPATIBILITY_PROTOCOL_ONLY"
            or scope.get("candidate_definition_count") != 0
            or scope.get("evaluation_unit_count") != 0
            or scope.get("effect_test_count") != 0
            or scope.get("generation_attempt_increment") != 0
        ):
            raise M7GateError("M7 protocol silently expands research scope")
        moneyflow = document.get("moneyflow_input") or {}
        boundary = document.get("execution_boundary") or {}
        if (
            tuple(moneyflow.get("projected_columns_only", ())) != PROJECTED_SOURCE_COLUMNS
            or moneyflow.get("numeric_moneyflow_value_read_authorized") is not False
            or boundary.get("real_data_read_authorized") is not False
            or boundary.get("candidate_generation_authorized") is not False
            or boundary.get("network_authorized") is not False
            or boundary.get("production_authorization") != "none"
        ):
            raise M7GateError("M7 protocol contains unauthorized reads or execution")
        memberships = document.get("membership_input") or {}
        if tuple(memberships.get("universe_ids", ())) != UNIVERSE_IDS:
            raise M7GateError("M7 universe identities differ")
        quality = document.get("quality_gate") or {}
        if (
            quality.get("aggregate_member_key_coverage_minimum_by_universe") != 0.995
            or quality.get("half_year_member_key_coverage_minimum_by_universe") != 0.99
            or quality.get("worst_feature_date_member_key_coverage_minimum_by_universe") != 0.95
            or len(quality.get("complete_half_year_segments", ())) != 11
        ):
            raise M7GateError("M7 quality thresholds differ")
        return cls(
            path=path,
            document=document,
            build_document=build,
            sha256=sha256_file(path),
            build_sha256=sha256_file(build_path),
        )

    @property
    def proposal(self) -> dict[str, Any]:
        return self.document["source_proposal"]

    @property
    def quality(self) -> dict[str, Any]:
        return self.document["quality_gate"]

    @property
    def pit(self) -> dict[str, Any]:
        return self.document["point_in_time"]


@dataclass(frozen=True)
class InputManifest:
    document: dict[str, Any]
    sha256: str
    physical_sha256: str

    @classmethod
    def load(cls, path: Path, protocol: M7Protocol) -> InputManifest:
        serialized = path.read_text(encoding="utf-8")
        document = json.loads(serialized)
        fields = {
            "schema_version",
            "created_at",
            "protocol_scope_sha256",
            "protocol_sha256",
            "build_contract_sha256",
            "semantic_rows_read",
            "source_audit",
            "source_batches",
            "membership",
            "evidence_files",
        }
        if not isinstance(document, dict) or set(document) != fields:
            raise M7GateError("M7 input manifest fields differ")
        if serialized != canonical_json(document) + "\n":
            raise M7GateError("M7 input manifest is not canonical")
        if (
            document["schema_version"] != "m7-moneyflow-data-input-manifest-v1"
            or document["protocol_scope_sha256"] != PROTOCOL_SCOPE_SHA256
            or document["protocol_sha256"] != protocol.sha256
            or document["build_contract_sha256"] != protocol.build_sha256
            or document["semantic_rows_read"] is not False
        ):
            raise M7GateError("M7 input manifest upstream identity differs")
        source = document.get("source_audit") or {}
        expected = protocol.document["moneyflow_input"]
        if (
            source.get("source_api") != SOURCE_API
            or source.get("full_catalog_sha256") != expected["audited_catalog_sha256"]
            or source.get("full_catalog_batch_count") != expected["audited_trade_date_count"]
            or source.get("full_catalog_row_count") != expected["audited_row_count"]
        ):
            raise M7GateError("M7 input manifest source audit differs")
        batches = document.get("source_batches")
        if not isinstance(batches, list) or not batches:
            raise M7GateError("M7 input manifest has no source batches")
        dates = [str(item.get("trade_date", "")) for item in batches]
        if dates != sorted(set(dates)):
            raise M7GateError("M7 input manifest source dates are duplicated or unordered")
        membership = document.get("membership") or {}
        expected_membership = protocol.document["membership_input"]
        if (
            membership.get("content_sha256") != expected_membership["daily_membership_sha256"]
            or membership.get("row_count") != expected_membership["daily_membership_row_count"]
            or tuple(membership.get("schema_fields", ())) != MEMBERSHIP_COLUMNS
        ):
            raise M7GateError("M7 membership manifest identity differs")
        return cls(document, sha256_json(document), sha256_file(path))
