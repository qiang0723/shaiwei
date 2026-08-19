"""Frozen contract and immutable paths for the RF-0C preflight."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
from typing import Any

import yaml

from shaiwei.config import PROJECT_ROOT
from shaiwei.provenance import code_snapshot_sha256, git_head
from shaiwei.research.trend_swing.contract import sha256_file


class RFCError(RuntimeError):
    """Fail-closed RF-0C contract violation."""


PROTOCOL_PATH = PROJECT_ROOT / "config/rf_0c_field_identity_preflight_v1.yaml"
PROTOCOL_SHA256 = "28c8524b96f726968a507d42ef661b435ca000746d218634d76b768d5cd5cc66"
OUTPUT_ROOT = PROJECT_ROOT / "data/research/rf/rf-0c-field-identity-preflight-v1"
MARKER_PATH = OUTPUT_ROOT / "semantic_read_started.json"
REGISTRY_PATH = OUTPUT_ROOT / "identity_registry.json"
FIELD_PROFILE_PATH = OUTPUT_ROOT / "field_profile.json"
PROFILE_PATH = OUTPUT_ROOT / "profile.json"
MANIFEST_PATH = OUTPUT_ROOT / "manifest.json"
AUDIT_PATH = OUTPUT_ROOT / "audit.json"
SEALED_RF_0B_REGISTRY_PATH = PROJECT_ROOT / (
    "data/research/rf/rf-0b-field-identity-preflight-v1-r2/identity_registry.json"
)
RECOVERY_SCOPE_PATH = PROJECT_ROOT / "config/rf_0c_field_identity_preflight_recovery_r2.yaml"
RECOVERY_SCOPE_SHA256 = "b992c90cc592ee6527f070037163007b53d730fb46de338c43d43c10a8d8f83d"
RECOVERY_OUTPUT_ROOT = PROJECT_ROOT / "data/research/rf/rf-0c-field-identity-preflight-v1-r2"


@dataclass(frozen=True)
class RFCRecovery:
    document: dict[str, Any]
    sha256: str = RECOVERY_SCOPE_SHA256

    @classmethod
    def load_if_present(cls) -> "RFCRecovery | None":
        if not RECOVERY_SCOPE_PATH.is_file():
            return None
        if RECOVERY_SCOPE_PATH.is_symlink() or sha256_file(RECOVERY_SCOPE_PATH) != RECOVERY_SCOPE_SHA256:
            raise RFCError("RF-0C recovery scope differs")
        try:
            document = yaml.safe_load(RECOVERY_SCOPE_PATH.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            raise RFCError("RF-0C recovery YAML is invalid") from exc
        if not isinstance(document, dict):
            raise RFCError("RF-0C recovery YAML is not a mapping")
        parent = document.get("parent_scope", {})
        authority = document.get("authority", {})
        if (
            document.get("schema_version") != "rf-0c-field-identity-preflight-recovery-r2-v1"
            or document.get("status") != "RESULT_BLIND_RECOVERY_SCOPE_FROZEN"
            or document.get("production_authorization") != "none"
            or parent.get("protocol_sha256") != PROTOCOL_SHA256
            or parent.get("original_scope_closed_no_same_scope_rerun") is not True
            or document.get("recovery", {}).get("candidate_or_effect_attempts_consumed") != 0
            or authority.get("fixture_must_pass_before_profile") is not True
            or authority.get("docker_network_mode") != "none"
            or authority.get("env_or_secret_read") is not False
            or authority.get("original_output_mount_read_only") is not True
        ):
            raise RFCError("RF-0C recovery authority or contract differs")
        return cls(document)

    def validate_parent_evidence(self, root: Path = PROJECT_ROOT) -> None:
        parent = self.document["parent_scope"]
        for name in ("marker", "profile"):
            relative, expected = parent[f"{name}_path"], parent[f"{name}_sha256"]
            path = root / relative
            if path.is_symlink() or not path.is_file() or sha256_file(path) != expected:
                raise RFCError(f"RF-0C recovery parent evidence differs: {relative}")


def active_root(recovery: RFCRecovery | None) -> Path:
    return RECOVERY_OUTPUT_ROOT if recovery is not None else OUTPUT_ROOT


@dataclass(frozen=True)
class RFCScope:
    document: dict[str, Any]
    sha256: str = PROTOCOL_SHA256

    @classmethod
    def load(cls) -> "RFCScope":
        if PROTOCOL_PATH.is_symlink() or sha256_file(PROTOCOL_PATH) != PROTOCOL_SHA256:
            raise RFCError("RF-0C frozen protocol differs")
        try:
            document = yaml.safe_load(PROTOCOL_PATH.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            raise RFCError("RF-0C frozen YAML is invalid") from exc
        if not isinstance(document, dict):
            raise RFCError("RF-0C frozen YAML is not a mapping")
        objective = document.get("objective", {})
        execution = document.get("execution_control", {})
        caliber = document.get("caliber_change_vs_rf_0b", {})
        registry = document.get("identity_registry", {})
        if (
            document.get("schema_version") != "rf-0c-field-identity-preflight-v1"
            or document.get("status")
            != "RESULT_BLIND_DATA_AND_IDENTITY_PREFLIGHT_FROZEN_PENDING_USER_APPROVAL"
            or document.get("production_authorization") != "none"
            or objective.get("candidate_generation") is not False
            or objective.get("strategy_effect_evaluation") is not False
            or caliber.get("single_change") != "supplementary_suspension_evidence_layer"
            or caliber.get("gate_thresholds_unchanged_from_rf_0b") is not True
            or caliber.get("no_other_semantics_change") is not True
            or registry.get("must_equal_sealed_rf_0b_registry") is not True
            or document.get("frozen_inputs", {}).get("bse_allowed") is not False
            or execution.get("external_network_or_provider") is not False
            or execution.get("env_or_secret_read") is not False
            or execution.get("docker_network_mode") != "none"
            or execution.get("deepseek_or_any_llm_call") is not False
            or execution.get("same_scope_rerun") != "forbidden"
            or document.get("verdicts", {}).get("strategy_effective") != "NOT_EVALUATED"
            or document.get("verdicts", {}).get("production_authorization") != "none"
        ):
            raise RFCError("RF-0C authority or contract differs")
        return cls(document)


def validate_bound_inputs(scope: RFCScope, root: Path = PROJECT_ROOT) -> None:
    frozen = scope.document["frozen_inputs"]
    checks = {
        frozen["attempt_ledger_d1_v2"]["path"]: frozen["attempt_ledger_d1_v2"]["sha256"],
        frozen["attempt_ledger_m1"]["path"]: frozen["attempt_ledger_m1"]["sha256"],
        frozen["attempt_ledger_m3"]["path"]: frozen["attempt_ledger_m3"]["sha256"],
        frozen["g1_admission_ledger"]["path"]: frozen["g1_admission_ledger"]["sha256"],
    }
    manifest = frozen["raw_market_store"]["r3_frozen_input_manifest"]
    checks[manifest["path"]] = manifest["sha256"]
    for row in scope.document["predecessor_chain"].values():
        if isinstance(row, dict) and {"path", "sha256"} <= set(row):
            checks[row["path"]] = row["sha256"]
    for relative, expected in checks.items():
        path = root / relative
        if path.is_symlink() or not path.is_file() or sha256_file(path) != expected:
            raise RFCError(f"RF-0C bound input differs: {relative}")


def runtime_identity() -> dict[str, str]:
    embedded = os.getenv("SHAIWEI_RELEASE_GIT_HEAD", "").strip().lower()
    if re.fullmatch(r"[0-9a-f]{40}", embedded) is None or git_head() != embedded:
        raise RFCError("RF-0C release Git identity differs")
    return {"git_head": embedded, "code_snapshot_sha256": code_snapshot_sha256()}
