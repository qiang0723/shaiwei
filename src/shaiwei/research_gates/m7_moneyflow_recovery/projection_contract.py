"""Frozen contract and evidence identities for the real key-only projection."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from shaiwei.research_gates.m7_moneyflow.contract import sha256_file

from .contract import RecoveryError


PROTOCOL_ID = "m7-moneyflow-recovery-target-projection-v2"
PROTOCOL_SHA256 = "345316477d789b255aeb259adcf3411a5f8c7889ed4eecd6f0a34d7e33dac1fd"
ACTION = "M7_MONEYFLOW_RECOVERY_TARGET_PROJECTION_ONCE"


def _mapping(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RecoveryError("recovery target projection protocol must be a mapping")
    return value


def _bound(root: Path, relative: str) -> Path:
    path = root / relative
    if path.is_symlink():
        raise RecoveryError("recovery target projection frozen file cannot be a symlink")
    try:
        resolved = path.resolve(strict=True)
        resolved.relative_to(root.resolve(strict=True))
    except (FileNotFoundError, ValueError) as error:
        raise RecoveryError("recovery target projection frozen file is absent or outside root") from error
    return resolved


@dataclass(frozen=True)
class TargetProjectionProtocol:
    document: dict[str, Any]
    sha256: str

    @classmethod
    def load(cls, path: Path, *, project_root: Path) -> TargetProjectionProtocol:
        document = _mapping(path)
        if (
            sha256_file(path) != PROTOCOL_SHA256
            or document.get("protocol_id") != PROTOCOL_ID
            or document.get("action") != ACTION
            or document.get("stage") != "REAL_KEY_PROJECTION_RELEASE_PROTOCOL_ONLY"
            or document.get("supersession", {}).get("v1_execution_authorized") is not False
            or document.get("supersession", {}).get("v1_execution_occurred") is not False
        ):
            raise RecoveryError("recovery target projection protocol identity differs")
        predecessors = document["frozen_predecessors"]
        for name in (
            "recovery_protocol",
            "release_build_contract",
            "release_engineering_acceptance",
            "lineage_protocol",
        ):
            item = predecessors[name]
            if sha256_file(_bound(project_root, item["path"])) != item["sha256"]:
                raise RecoveryError("recovery target projection predecessor differs")
        manifest = predecessors["lineage_input_manifest"]
        if sha256_file(_bound(project_root, manifest["path"])) != manifest["physical_sha256"]:
            raise RecoveryError("recovery target projection input manifest differs")
        execution_item = predecessors["lineage_execution_manifest"]
        execution_path = _bound(project_root, execution_item["path"])
        if sha256_file(execution_path) != execution_item["sha256"]:
            raise RecoveryError("recovery target projection execution manifest differs")
        execution = json.loads(execution_path.read_text(encoding="utf-8"))
        if (
            execution.get("input_manifest_sha256") != manifest["canonical_sha256"]
            or execution.get("independent_audit", {}).get("independent_recomputed_core_sha256")
            != predecessors["lineage_report"]["core_sha256"]
            or execution.get("artifacts", {}).get("bundle_manifest", {}).get("sha256")
            != predecessors["lineage_input_bundle"]["bundle_manifest_sha256"]
        ):
            raise RecoveryError("recovery target projection execution evidence differs")
        authority = document["construction_authority"]
        if (
            authority["projector_auditor_and_release_engineering_authorized"] is not True
            or authority["exact_release_scope_generation_authorized"] is not True
            or authority["real_security_key_read_authorized"] is not False
            or authority["real_projection_execution_authorized"] is not False
            or authority["external_network_authorized"] is not False
            or authority["production_authorization"] != "none"
        ):
            raise RecoveryError("recovery target projection authority differs")
        return cls(document, PROTOCOL_SHA256)

    @property
    def expected_lineage_core_sha256(self) -> str:
        return str(self.document["frozen_predecessors"]["lineage_report"]["core_sha256"])

    @property
    def input_bundle_relative_path(self) -> str:
        return str(self.document["frozen_predecessors"]["lineage_input_bundle"]["relative_path"])
