"""Frozen protocol, release identity, and write-once helpers for M6-3C-R3."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Any

import yaml

from shaiwei.config import PROJECT_ROOT
from shaiwei.research.model_attribution.contract import sha256_file
from shaiwei.research.top30_diagnostic.contract import tree_identity, write_once_document
from shaiwei.research.top30_diagnostic.exact import DiagnosticError, canonical_sha256


PROTOCOL_PATH = PROJECT_ROOT / "config/m6_csi800_top30_numeric_provenance_v1.yaml"
SCOPE_PATH = PROJECT_ROOT / "config/m6_csi800_top30_numeric_provenance_scope_v1.json"
COMPOSE_PATH = PROJECT_ROOT / "compose.m6-top30-provenance.yaml"
DOCKERFILE_PATH = PROJECT_ROOT / "Dockerfile.m6-top30-provenance"
OUTPUT_ROOT = "data/research/m6_csi800_top30_numeric_provenance_v1"
ORIGINAL_IMAGE = "shaiwei:m6-top30-provenance-original-v1"
FAILED_IMAGE = "shaiwei:m6-top30-provenance-failed-v1"
SCOPE_SCHEMA = "m6-top30-numeric-provenance-release-scope-v1"
SCOPE_KIND = "TOP30_NUMERIC_PROVENANCE_READ_ONLY_EXECUTION"
RELEASE_MANIFEST_PATH = Path("/opt/shaiwei/m6-top30-provenance/release-manifest.json")


def load_mapping(path: Path, *, yaml_document: bool = False) -> dict[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8")
        value = yaml.safe_load(raw) if yaml_document else json.loads(raw)
    except (OSError, ValueError, yaml.YAMLError) as error:
        raise DiagnosticError(f"Top30 provenance document is invalid: {path.name}") from error
    if not isinstance(value, dict):
        raise DiagnosticError(f"Top30 provenance document is not a mapping: {path.name}")
    return value


@dataclass(frozen=True)
class Protocol:
    document: dict[str, Any]
    sha256: str

    @classmethod
    def load(cls, path: Path = PROTOCOL_PATH) -> "Protocol":
        document = load_mapping(path, yaml_document=True)
        if document.get("schema_version") != "m6-csi800-top30-numeric-provenance-protocol-v1":
            raise DiagnosticError("Top30 provenance protocol schema differs")
        authority = document.get("authority", {})
        execution = document.get("execution_contract", {})
        prohibited = (
            "top30_backtest_authorized",
            "top20_read_or_backtest_authorized",
            "qlib_provider_mount_or_read_authorized",
            "model_fit_authorized",
            "prediction_generation_authorized",
            "experiment_ledger_write_authorized",
            "external_network_authorized",
        )
        if any(authority.get(key) is not False for key in prohibited):
            raise DiagnosticError("Top30 provenance protocol authority widened")
        if (
            execution.get("collector_invocation_count") != 1
            or execution.get("independent_auditor_invocation_count") != 1
            or execution.get("total_top30_backtest_count") != 0
            or execution.get("top20_backtest_count") != 0
            or execution.get("same_scope_retry_authorized") is not False
        ):
            raise DiagnosticError("Top30 provenance execution contract differs")
        return cls(document=document, sha256=sha256_file(path))


@dataclass(frozen=True)
class ReleaseScope:
    document: dict[str, Any]
    scope: dict[str, Any]
    sha256: str

    @classmethod
    def load(cls, path: Path, protocol: Protocol) -> "ReleaseScope":
        document = load_mapping(path)
        if set(document) != {"schema_version", "provenance_scope_sha256", "scope"}:
            raise DiagnosticError("Top30 provenance release shape differs")
        scope = document["scope"]
        digest = canonical_sha256(scope)
        if (
            document.get("schema_version") != SCOPE_SCHEMA
            or document.get("provenance_scope_sha256") != digest
            or scope.get("scope_kind") != SCOPE_KIND
            or scope.get("protocol_sha256") != protocol.sha256
        ):
            raise DiagnosticError("Top30 provenance release identity differs")
        authority = scope.get("authority", {})
        if authority.get("execution_authorized") is not True:
            raise DiagnosticError("Top30 provenance execution is not authorized")
        if any(
            authority.get(key) is not False
            for key in (
                "top30_backtest_authorized",
                "top20_read_or_backtest_authorized",
                "qlib_read_authorized",
                "model_fit_authorized",
                "prediction_generation_authorized",
                "external_network_authorized",
            )
        ):
            raise DiagnosticError("Top30 provenance release authority widened")
        return cls(document=document, scope=scope, sha256=digest)


def code_bundle_identity(root: Path | None = None) -> dict[str, Any]:
    base = root or Path(__file__).resolve().parent
    roots = (base,) if root is not None else (base, base.parent / "top30_diagnostic")
    prefix = base if root is not None else base.parent
    rows = [
        {
            "path": path.relative_to(prefix).as_posix(),
            "sha256": sha256_file(path),
            "size": path.stat().st_size,
        }
        for package_root in roots
        for path in sorted(package_root.glob("*.py"))
        if path.is_file()
    ]
    if not rows:
        raise DiagnosticError("Top30 provenance code bundle is empty")
    return {"file_count": len(rows), "sha256": canonical_sha256(rows), "files": rows}


def runtime_identity(release: ReleaseScope, role: str) -> dict[str, str]:
    if role not in {"original", "failed"}:
        raise DiagnosticError("Top30 provenance runtime role differs")
    expected = release.scope["images"][role]
    observed = {
        "role": os.environ.get("SHAIWEI_M6_TOP30_PROVENANCE_ROLE", ""),
        "git_commit": os.environ.get("SHAIWEI_M6_TOP30_PROVENANCE_GIT_HEAD", ""),
        "base_image_id": os.environ.get("SHAIWEI_M6_TOP30_PROVENANCE_BASE_IMAGE_ID", ""),
    }
    manifest = load_mapping(RELEASE_MANIFEST_PATH)
    for key, value in observed.items():
        if value != expected[key] or manifest.get(key) != value:
            raise DiagnosticError(f"Top30 provenance runtime {key} differs")
    if (
        manifest.get("code_bundle_sha256") != expected["code_bundle_sha256"]
        or sha256_file(RELEASE_MANIFEST_PATH) != expected["release_manifest_sha256"]
    ):
        raise DiagnosticError("Top30 provenance image manifest differs")
    return observed


__all__ = [
    "COMPOSE_PATH",
    "DOCKERFILE_PATH",
    "FAILED_IMAGE",
    "ORIGINAL_IMAGE",
    "OUTPUT_ROOT",
    "PROTOCOL_PATH",
    "Protocol",
    "RELEASE_MANIFEST_PATH",
    "ReleaseScope",
    "SCOPE_KIND",
    "SCOPE_PATH",
    "SCOPE_SCHEMA",
    "code_bundle_identity",
    "load_mapping",
    "runtime_identity",
    "sha256_file",
    "tree_identity",
    "write_once_document",
]
