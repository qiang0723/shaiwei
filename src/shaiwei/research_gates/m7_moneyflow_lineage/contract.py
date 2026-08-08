"""Frozen identities and canonical contracts for the M7 lineage gate."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

import yaml

from shaiwei.research_gates.m7_moneyflow.contract import canonical_json, sha256_file, sha256_json


PROTOCOL_ID = "m7-moneyflow-gap-lineage-v1"
PROTOCOL_SHA256 = "bf5ebac79cb1b81699e5a8f4d1fae13b78dedb35e7ed19672e0c69ea8254ad9e"
ACTION = "M7_MONEYFLOW_GAP_LINEAGE_ONCE"
OLD_PROTOCOL_PATH = "config/m7_star_custom_pool_moneyflow_data_v1.yaml"
OLD_BUILD_PATH = "config/m7_star_custom_pool_moneyflow_data_gate_build_v1.yaml"
OLD_INPUT_MANIFEST_PATH = "config/m7_star_custom_pool_moneyflow_data_input_v1.json"
OLD_RELEASE_PATH = "config/m7_star_custom_pool_moneyflow_data_gate_release_scope_v1.json"
OLD_APPROVAL_PATH = "config/m7_star_custom_pool_moneyflow_data_gate_approval_v1.json"
UNIVERSE_IDS = (
    "star-board-all-pit-v1",
    "star-board-midcap-pit-v1",
    "star-board-smallcap-pit-v1",
)
CATEGORIES = (
    "QUARANTINED_SOURCE_DATE",
    "CONFLICTING_INDEPENDENT_TRADE_STATUS",
    "CONFLICT_DAILY_PRESENT_INDEPENDENT_NONTRADING",
    "CONFIRMED_MONEYFLOW_GAP_DAILY_PRESENT",
    "CONFLICT_DAILY_ABSENT_INDEPENDENT_TRADING",
    "CONFIRMED_NONTRADING_INDEPENDENT",
    "CONFLICTING_PRIMARY_SUSPENSION_ROWS",
    "PRIMARY_FULL_DAY_SUSPENSION_ONLY_UNRESOLVED",
    "INTRADAY_SUSPENSION_NOT_EXPLANATION",
    "UNRESOLVED_NO_TRADE_EVIDENCE",
)
SOURCE_COLUMNS = {
    "tushare.daily": ("ts_code", "trade_date"),
    "tushare.suspend_d": ("ts_code", "trade_date", "suspend_timing", "suspend_type"),
    "baostock.history_k_data_plus": ("ts_code", "trade_date", "trade_status"),
}
SHA_RE = re.compile(r"^[0-9a-f]{64}$")


class LineageError(RuntimeError):
    """A lineage identity, authorization, or quality invariant failed."""


def require_sha(value: Any, name: str) -> str:
    normalized = str(value)
    if SHA_RE.fullmatch(normalized) is None:
        raise LineageError(f"{name} must be a lowercase SHA-256")
    return normalized


def safe_relative(value: Any, name: str) -> str:
    path = PurePosixPath(str(value))
    if path.is_absolute() or not path.parts or ".." in path.parts:
        raise LineageError(f"{name} must be project-relative")
    return path.as_posix()


def _read_mapping(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise LineageError(f"{path.name} must contain a mapping")
    return value


def _bound_file(root: Path, relative: str) -> Path:
    path = root / safe_relative(relative, "frozen file")
    if path.is_symlink():
        raise LineageError("lineage frozen files cannot be symlinks")
    try:
        resolved = path.resolve(strict=True)
        resolved.relative_to(root.resolve(strict=True))
    except (FileNotFoundError, ValueError) as exc:
        raise LineageError("lineage frozen file is missing or outside its root") from exc
    if not resolved.is_file():
        raise LineageError("lineage frozen input is not a regular file")
    return resolved


@dataclass(frozen=True)
class LineageProtocol:
    path: Path
    project_root: Path
    document: dict[str, Any]
    sha256: str
    old_protocol: dict[str, Any]

    @classmethod
    def load(cls, path: Path, *, project_root: Path) -> LineageProtocol:
        document = _read_mapping(path)
        physical = sha256_file(path)
        if physical != PROTOCOL_SHA256 or document.get("protocol_id") != PROTOCOL_ID:
            raise LineageError("lineage protocol identity differs")
        if document.get("stage") != "GAP_LINEAGE_PROTOCOL_ONLY":
            raise LineageError("lineage stage differs")
        old_path = _bound_file(project_root, OLD_PROTOCOL_PATH)
        old = _read_mapping(old_path)
        predecessor = document.get("predecessor") or {}
        if (
            sha256_file(old_path) != predecessor.get("data_protocol_sha256")
            or predecessor.get("authoritative_verdict") != "NO_GO_M7_0_DATA_COMPATIBILITY"
            or predecessor.get("scope_closed") is not True
            or predecessor.get("retry_authorized") is not False
        ):
            raise LineageError("lineage predecessor identity or closure differs")
        engineering = document.get("engineering_predecessor") or {}
        for path_key, sha_key in (
            ("protocol_path", "protocol_sha256"),
            ("acceptance_path", "acceptance_sha256"),
        ):
            frozen = _bound_file(project_root, str(engineering[path_key]))
            if sha256_file(frozen) != engineering[sha_key]:
                raise LineageError("lineage engineering predecessor differs")
        execution = document.get("execution_contract") or {}
        authority = document.get("construction_authority") or {}
        if (
            execution.get("action") != ACTION
            or execution.get("same_scope_retry_authorized") is not False
            or authority.get("real_security_key_read_authorized") is not False
            or authority.get("lineage_execution_authorized") is not False
            or authority.get("numeric_moneyflow_value_read_authorized") is not False
            or authority.get("production_authorization") != "none"
        ):
            raise LineageError("lineage protocol expands authority")
        classification = document.get("lineage_classification") or {}
        if tuple(classification.get("priority", ())) != CATEGORIES:
            raise LineageError("lineage category order differs")
        if tuple((document.get("scope") or {}).get("universe_ids", ())) != UNIVERSE_IDS:
            raise LineageError("lineage universe identities differ")
        return cls(path, project_root, document, physical, old)

    @property
    def proposal(self) -> dict[str, Any]:
        value = self.old_protocol.get("source_proposal")
        if not isinstance(value, dict):
            raise LineageError("lineage predecessor proposal is absent")
        path = _bound_file(self.project_root, str(value["proposal_export_path"]))
        if sha256_file(path) != value["proposal_export_sha256"]:
            raise LineageError("lineage proposal export differs")
        return value

    @property
    def proposal_export(self) -> dict[str, Any]:
        value = json.loads(
            _bound_file(self.project_root, str(self.proposal["proposal_export_path"])).read_text(
                encoding="utf-8"
            )
        )
        if not isinstance(value, dict):
            raise LineageError("lineage proposal export must be an object")
        return value


@dataclass(frozen=True)
class LineageInputManifest:
    document: dict[str, Any]
    sha256: str
    physical_sha256: str

    @classmethod
    def load(cls, path: Path, protocol: LineageProtocol) -> LineageInputManifest:
        serialized = path.read_text(encoding="utf-8")
        document = json.loads(serialized)
        fields = {
            "schema_version",
            "created_at",
            "metadata_cutoff_utc",
            "protocol_sha256",
            "semantic_rows_read",
            "predecessor_bundle",
            "sources",
        }
        if (
            not isinstance(document, dict)
            or set(document) != fields
            or serialized != canonical_json(document) + "\n"
            or document.get("schema_version") != "m7-moneyflow-gap-lineage-input-v1"
            or document.get("protocol_sha256") != protocol.sha256
            or document.get("metadata_cutoff_utc")
            != protocol.document["input_contract"]["metadata_inventory_cutoff_utc"]
            or document.get("semantic_rows_read") is not False
        ):
            raise LineageError("lineage input manifest shape or identity differs")
        predecessor = document.get("predecessor_bundle") or {}
        expected = protocol.document["predecessor"]
        if (
            set(predecessor)
            != {
                "relative_path",
                "input_manifest_sha256",
                "bundle_manifest_sha256",
                "file_count",
            }
            or predecessor.get("input_manifest_sha256") != expected["input_manifest_sha256"]
            or predecessor.get("bundle_manifest_sha256") != expected["input_bundle_manifest_sha256"]
        ):
            raise LineageError("lineage predecessor bundle identity differs")
        sources = document.get("sources")
        if not isinstance(sources, dict) or set(sources) != set(SOURCE_COLUMNS):
            raise LineageError("lineage source inventory differs")
        for source_api, columns in SOURCE_COLUMNS.items():
            item = sources[source_api]
            batches = item.get("batches")
            if (
                set(item)
                != {
                    "projected_columns",
                    "selected_batch_count",
                    "selected_row_count",
                    "selected_bytes",
                    "catalog_sha256",
                    "batches",
                }
                or item.get("projected_columns") != list(columns)
                or not isinstance(batches, list)
                or not batches
            ):
                raise LineageError("lineage source projection or batches differ")
            if (
                item.get("selected_batch_count") != len(batches)
                or item.get("selected_row_count") != sum(int(batch["row_count"]) for batch in batches)
                or item.get("selected_bytes") != sum(int(batch["bytes"]) for batch in batches)
                or item.get("catalog_sha256") != sha256_json(batches)
            ):
                raise LineageError("lineage source batch count differs")
            for index, batch in enumerate(batches):
                if (
                    set(batch)
                    != {
                        "request_params_sha256",
                        "relative_path",
                        "bundle_relative_path",
                        "row_count",
                        "bytes",
                        "content_sha256",
                        "schema_fields",
                    }
                    or batch["bundle_relative_path"] != f"sources/{source_api}/{index:05d}.parquet"
                    or int(batch["row_count"]) < 0
                    or int(batch["bytes"]) <= 0
                    or require_sha(batch["request_params_sha256"], "request params SHA")
                    != batch["request_params_sha256"]
                    or require_sha(batch["content_sha256"], "source content SHA") != batch["content_sha256"]
                ):
                    raise LineageError("lineage source batch identity differs")
                safe_relative(batch["relative_path"], "source relative path")
                safe_relative(batch["bundle_relative_path"], "source bundle path")
        return cls(document, sha256_json(document), sha256_file(path))


def file_sha256(path: Path) -> str:
    """Local alias used by lineage modules and tests."""

    return hashlib.sha256(path.read_bytes()).hexdigest()
