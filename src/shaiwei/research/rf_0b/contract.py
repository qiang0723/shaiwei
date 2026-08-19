"""Frozen contract and immutable paths for the RF-0B preflight."""

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


class RFBError(RuntimeError):
    """Fail-closed RF-0B contract violation."""


PROTOCOL_PATH = PROJECT_ROOT / "config/rf_0b_field_identity_preflight_v1.yaml"
PROTOCOL_SHA256 = "f98cecc7568b91d3ba30a1389127227d42d5646e85dd9acd69585fe70910a5b7"
OUTPUT_ROOT = PROJECT_ROOT / "data/research/rf/rf-0b-field-identity-preflight-v1"
RECOVERY_SCOPE_PATH = PROJECT_ROOT / "config/rf_0b_field_identity_preflight_recovery_r2.yaml"
RECOVERY_SCOPE_SHA256 = "5b6144419ece0600104edba3fe63264af3abcc1bcf30fd1876dba9d760d63267"
ORIGINAL_OUTPUT_ROOT = OUTPUT_ROOT
RECOVERY_OUTPUT_ROOT = PROJECT_ROOT / "data/research/rf/rf-0b-field-identity-preflight-v1-r2"
MARKER_NAME = "semantic_read_started.json"
MARKER_PATH = OUTPUT_ROOT / MARKER_NAME
REGISTRY_PATH = OUTPUT_ROOT / "identity_registry.json"
FIELD_PROFILE_PATH = OUTPUT_ROOT / "field_profile.json"
PROFILE_PATH = OUTPUT_ROOT / "profile.json"
MANIFEST_PATH = OUTPUT_ROOT / "manifest.json"
AUDIT_PATH = OUTPUT_ROOT / "audit.json"


@dataclass(frozen=True)
class OutputPaths:
    root: Path

    @property
    def marker(self) -> Path:
        return self.root / MARKER_NAME

    @property
    def registry(self) -> Path:
        return self.root / "identity_registry.json"

    @property
    def field_profile(self) -> Path:
        return self.root / "field_profile.json"

    @property
    def profile(self) -> Path:
        return self.root / "profile.json"

    @property
    def manifest(self) -> Path:
        return self.root / "manifest.json"

    @property
    def audit(self) -> Path:
        return self.root / "audit.json"


@dataclass(frozen=True)
class RFBRecovery:
    document: dict[str, Any]
    sha256: str = RECOVERY_SCOPE_SHA256

    @classmethod
    def load_if_present(cls) -> "RFBRecovery | None":
        if not RECOVERY_SCOPE_PATH.is_file():
            return None
        if RECOVERY_SCOPE_PATH.is_symlink() or sha256_file(RECOVERY_SCOPE_PATH) != RECOVERY_SCOPE_SHA256:
            raise RFBError("RF-0B recovery scope differs")
        try:
            document = yaml.safe_load(RECOVERY_SCOPE_PATH.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            raise RFBError("RF-0B recovery YAML is invalid") from exc
        if not isinstance(document, dict):
            raise RFBError("RF-0B recovery YAML is not a mapping")
        parent = document.get("parent_scope", {})
        authority = document.get("authority", {})
        if (
            document.get("schema_version") != "rf-0b-field-identity-preflight-recovery-r2-v1"
            or document.get("status") != "RESULT_BLIND_RECOVERY_SCOPE_FROZEN"
            or document.get("production_authorization") != "none"
            or parent.get("protocol_sha256") != PROTOCOL_SHA256
            or parent.get("market_or_ledger_data_read_before_failure") is not False
            or parent.get("outputs_created_before_failure") != "marker_only"
            or parent.get("original_scope_closed_no_same_scope_rerun") is not True
            or document.get("recovery", {}).get("candidate_or_effect_attempts_consumed") != 0
            or authority.get("docker_network_mode") != "none"
            or authority.get("env_or_secret_read") is not False
            or authority.get("original_output_mount_read_only") is not True
        ):
            raise RFBError("RF-0B recovery authority or contract differs")
        return cls(document)

    def validate_parent_evidence(self, root: Path = PROJECT_ROOT) -> None:
        parent = self.document["parent_scope"]
        for name in ("marker",):
            relative, expected = parent[f"{name}_path"], parent[f"{name}_sha256"]
            path = root / relative
            if path.is_symlink() or not path.is_file() or sha256_file(path) != expected:
                raise RFBError(f"RF-0B recovery parent evidence differs: {relative}")


def active_output_paths(recovery: RFBRecovery | None) -> OutputPaths:
    root = RECOVERY_OUTPUT_ROOT if recovery is not None else ORIGINAL_OUTPUT_ROOT
    return OutputPaths(root)


@dataclass(frozen=True)
class RFBScope:
    document: dict[str, Any]
    sha256: str = PROTOCOL_SHA256

    @classmethod
    def load(cls) -> "RFBScope":
        if PROTOCOL_PATH.is_symlink() or sha256_file(PROTOCOL_PATH) != PROTOCOL_SHA256:
            raise RFBError("RF-0B frozen protocol differs")
        try:
            document = yaml.safe_load(PROTOCOL_PATH.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            raise RFBError("RF-0B frozen YAML is invalid") from exc
        if not isinstance(document, dict):
            raise RFBError("RF-0B frozen YAML is not a mapping")
        objective = document.get("objective", {})
        execution = document.get("execution_control", {})
        gates = document.get("field_quality_gate", {})
        if (
            document.get("schema_version") != "rf-0b-field-identity-preflight-v1"
            or document.get("status")
            != "RESULT_BLIND_DATA_AND_IDENTITY_PREFLIGHT_FROZEN_PENDING_USER_APPROVAL"
            or document.get("production_authorization") != "none"
            or objective.get("candidate_generation") is not False
            or objective.get("strategy_effect_evaluation") is not False
            or document.get("frozen_inputs", {}).get("bse_allowed") is not False
            or gates.get("threshold_change_after_profile") != "forbidden"
            or execution.get("external_network_or_provider") is not False
            or execution.get("env_or_secret_read") is not False
            or execution.get("docker_network_mode") != "none"
            or execution.get("deepseek_or_any_llm_call") is not False
            or execution.get("model_training_prediction_or_backtest") is not False
            or execution.get("same_scope_rerun") != "forbidden"
            or document.get("verdicts", {}).get("strategy_effective") != "NOT_EVALUATED"
            or document.get("verdicts", {}).get("production_authorization") != "none"
        ):
            raise RFBError("RF-0B authority or contract differs")
        return cls(document)


def validate_bound_inputs(scope: RFBScope, root: Path = PROJECT_ROOT) -> None:
    frozen = scope.document["frozen_inputs"]
    checks = {
        frozen["attempt_ledger_d1_v2"]["path"]: frozen["attempt_ledger_d1_v2"]["sha256"],
        frozen["attempt_ledger_m1"]["path"]: frozen["attempt_ledger_m1"]["sha256"],
        frozen["attempt_ledger_m3"]["path"]: frozen["attempt_ledger_m3"]["sha256"],
        frozen["g1_admission_ledger"]["path"]: frozen["g1_admission_ledger"]["sha256"],
    }
    manifest = frozen["raw_market_store"]["r3_frozen_input_manifest"]
    checks[manifest["path"]] = manifest["sha256"]
    for relative, expected in checks.items():
        path = root / relative
        if path.is_symlink() or not path.is_file() or sha256_file(path) != expected:
            raise RFBError(f"RF-0B bound input differs: {relative}")


def runtime_identity() -> dict[str, str]:
    embedded = os.getenv("SHAIWEI_RELEASE_GIT_HEAD", "").strip().lower()
    if re.fullmatch(r"[0-9a-f]{40}", embedded) is None or git_head() != embedded:
        raise RFBError("RF-0B release Git identity differs")
    return {"git_head": embedded, "code_snapshot_sha256": code_snapshot_sha256()}
