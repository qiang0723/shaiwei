"""Frozen contract and immutable paths for TS-v6 entry-quality preflight."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
from typing import Any

import yaml

from shaiwei.config import PROJECT_ROOT
from shaiwei.provenance import code_snapshot_sha256, git_head
from shaiwei.research.provider_contract import D1ControlError
from shaiwei.research.trend_swing.contract import sha256_file


PROTOCOL_PATH = PROJECT_ROOT / "config/ts_v6_entry_quality_preflight_v1.yaml"
PROTOCOL_SHA256 = "a518862b224b120b04f0a0ab6d1543a7827cbb9c245a3e8806e443c062d7332b"
ADDENDUM_PATH = PROJECT_ROOT / "config/ts_v6_entry_quality_operationalization_addendum_v1.yaml"
ADDENDUM_SHA256 = "ffa0e1f745853841aa58e0eb0e0efc00142a61523cf4bd1c3f269bb2452f441b"
OUTPUT_ROOT = PROJECT_ROOT / "data/research/trend_swing/ts-v6-entry-quality-preflight-v1"
MARKER_PATH = OUTPUT_ROOT / "semantic_read_started.json"
OBSERVATION_PATH = OUTPUT_ROOT / "parent_observations.parquet"
CANDIDATE_EVENT_PATH = OUTPUT_ROOT / "candidate_events.parquet"
PROFILE_PATH = OUTPUT_ROOT / "profile.json"
MANIFEST_PATH = OUTPUT_ROOT / "manifest.json"
AUDIT_PATH = OUTPUT_ROOT / "audit.json"


def _load_yaml(path: Path, expected_sha256: str) -> dict[str, Any]:
    if path.is_symlink() or sha256_file(path) != expected_sha256:
        raise D1ControlError(f"TS-v6 frozen input differs: {path.name}")
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise D1ControlError(f"TS-v6 frozen YAML is invalid: {path.name}") from exc
    if not isinstance(value, dict):
        raise D1ControlError(f"TS-v6 frozen YAML is not a mapping: {path.name}")
    return value


@dataclass(frozen=True)
class V6Scope:
    document: dict[str, Any]
    addendum: dict[str, Any]
    sha256: str = PROTOCOL_SHA256
    addendum_sha256: str = ADDENDUM_SHA256

    @classmethod
    def load(cls) -> "V6Scope":
        document = _load_yaml(PROTOCOL_PATH, PROTOCOL_SHA256)
        addendum = _load_yaml(ADDENDUM_PATH, ADDENDUM_SHA256)
        roles = document.get("chronological_roles", {})
        execution = document.get("execution_control", {})
        if (
            document.get("status") != "RESULT_INFORMED_ZERO_EFFECT_PREFLIGHT_FROZEN"
            or document.get("production_authorization") != "none"
            or document.get("objective", {}).get("strategy_effect_evaluation") is not False
            or document.get("density_design", {}).get("effect_attempt_increment") != 0
            or document.get("inherited_parent_semantics", {}).get("alpha158_read") is not False
            or roles.get("current_partial_year", {}).get("data_read_allowed") is not False
            or execution.get("external_network_or_provider") is not False
            or execution.get("env_or_secret_read") is not False
            or execution.get("docker_network_mode") != "none"
            or addendum.get("status") != "RESULT_BLIND_OPERATIONALIZATION_FROZEN"
            or addendum.get("parent_protocol", {}).get("sha256") != PROTOCOL_SHA256
            or addendum.get("candidate_filter_semantics", {}).get(
                "rearm_or_retry_inside_same_parent_episode"
            ) != "forbidden"
            or addendum.get("firewall_and_authority", {}).get("effect_attempt_increment") != 0
        ):
            raise D1ControlError("TS-v6 authority, role, or operationalization contract differs")
        return cls(document, addendum)

    @property
    def roles(self) -> tuple[tuple[str, str, str], ...]:
        roles = self.document["chronological_roles"]
        return (
            (
                "selectable_discovery",
                str(roles["development_distribution_and_density"]["start"]),
                str(roles["development_distribution_and_density"]["end"]),
            ),
            (
                "frozen_stability_holdout",
                str(roles["conditional_density_only_holdout"]["start"]),
                str(roles["conditional_density_only_holdout"]["end"]),
            ),
        )


def validate_bound_inputs(scope: V6Scope, root: Path = PROJECT_ROOT) -> None:
    frozen = scope.document["frozen_inputs"]
    checks = {
        frozen["r3_manifest_path"]: frozen["r3_manifest_sha256"],
        frozen["parent_density_profile_path"]: frozen["parent_density_profile_sha256"],
        frozen["parent_event_path"]: frozen["parent_event_sha256"],
        frozen["parent_density_audit_path"]: frozen["parent_density_audit_sha256"],
    }
    parent = scope.document["result_informed_parent"]
    checks[parent["parent_protocol_path"]] = parent["parent_protocol_sha256"]
    diagnostic = parent["known_diagnostic"]
    for name in ("report", "manifest", "audit"):
        checks[diagnostic[f"{name}_path"]] = diagnostic[f"{name}_sha256"]
    for relative, expected in checks.items():
        path = root / relative
        if path.is_symlink() or sha256_file(path) != expected:
            raise D1ControlError(f"TS-v6 bound input differs: {relative}")


def runtime_identity() -> dict[str, str]:
    embedded = os.getenv("SHAIWEI_RELEASE_GIT_HEAD", "").strip().lower()
    if re.fullmatch(r"[0-9a-f]{40}", embedded) is None or git_head() != embedded:
        raise D1ControlError("TS-v6 release Git identity differs")
    return {"git_head": embedded, "code_snapshot_sha256": code_snapshot_sha256()}
