"""Frozen authority for the M7 exact network-release construction stage."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from shaiwei.research_gates.m7_moneyflow.contract import sha256_file

from shaiwei.research_gates.m7_moneyflow_recovery.contract import RecoveryError


PROTOCOL_ID = "m7-moneyflow-evidence-recovery-network-release-v1"
PROTOCOL_SHA256 = "3b487b9a58ae7a376cc640899277885897372cac643118290ab59057cf0cf9d3"


def _mapping(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RecoveryError("recovery network protocol must contain a mapping")
    return value


def _bound_file(root: Path, relative: str) -> Path:
    path = root / relative
    if path.is_symlink():
        raise RecoveryError("recovery network predecessor cannot be a symlink")
    try:
        resolved = path.resolve(strict=True)
        resolved.relative_to(root.resolve(strict=True))
    except (FileNotFoundError, ValueError) as error:
        raise RecoveryError("recovery network predecessor is missing or outside project") from error
    if not resolved.is_file():
        raise RecoveryError("recovery network predecessor is not a regular file")
    return resolved


@dataclass(frozen=True)
class NetworkReleaseProtocol:
    project_root: Path
    document: dict[str, Any]
    sha256: str

    @classmethod
    def load(cls, path: Path, *, project_root: Path) -> NetworkReleaseProtocol:
        document = _mapping(path)
        if (
            sha256_file(path) != PROTOCOL_SHA256
            or document.get("protocol_id") != PROTOCOL_ID
            or document.get("stage") != "EXACT_NETWORK_RELEASE_CONSTRUCTION_ONLY"
        ):
            raise RecoveryError("recovery network protocol identity differs")
        for item in document["frozen_predecessors"].values():
            if not isinstance(item, dict) or "path" not in item:
                continue
            frozen = _bound_file(project_root, str(item["path"]))
            if sha256_file(frozen) != item["sha256"]:
                raise RecoveryError("recovery network predecessor identity differs")
        supersession = document["supersession"]
        predecessors = document["frozen_predecessors"]
        if (
            supersession["preserved_protocol_modified"] is not False
            or supersession["authoritative_core_sha256"]
            != predecessors["authoritative_lineage_core_sha256"]
            or supersession["recovery_semantics_changed"] is not False
        ):
            raise RecoveryError("recovery network core correction differs")
        authority = document["construction_authority"]
        if (
            authority["offline_real_target_key_read_authorized"] is not True
            or authority["exact_request_plan_generation_authorized"] is not True
            or authority["live_role_engineering_authorized"] is not True
            or authority["exact_release_scope_generation_authorized"] is not True
            or authority["external_network_authorized"] is not False
            or authority["live_provider_call_authorized"] is not False
            or authority["secret_read_authorized"] is not False
            or authority["production_authorization"] != "none"
        ):
            raise RecoveryError("recovery network construction authority differs")
        collection = document["collection_contract"]
        if (
            collection["current_collection_authorized"] is not False
            or collection["same_release_rerun_authorized"] is not False
            or collection["provider_cost_usd_cap"] != 0
        ):
            raise RecoveryError("recovery network collection authority differs")
        return cls(project_root.resolve(strict=True), document, PROTOCOL_SHA256)

    @property
    def target_projection_root(self) -> str:
        return str(self.document["frozen_predecessors"]["target_projection_root"])

    @property
    def lineage_bundle_relative_path(self) -> str:
        projection = _mapping(
            self.project_root / "config/m7_moneyflow_recovery_target_projection_v2.yaml"
        )
        return str(
            projection["frozen_predecessors"]["lineage_input_bundle"]["relative_path"]
        )

    @property
    def lineage_bundle_manifest_sha256(self) -> str:
        projection = _mapping(
            self.project_root / "config/m7_moneyflow_recovery_target_projection_v2.yaml"
        )
        return str(
            projection["frozen_predecessors"]["lineage_input_bundle"][
                "bundle_manifest_sha256"
            ]
        )
