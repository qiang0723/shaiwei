"""Frozen contract and immutable paths for the RF-0B gap-lineage diagnostic."""

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


class RFDError(RuntimeError):
    """Fail-closed RF diagnostic contract violation."""


PROTOCOL_PATH = PROJECT_ROOT / "config/rf_0b_gap_lineage_diagnostic_v1.yaml"
PROTOCOL_SHA256 = "0a04c12edf5bad56c1571227c48b0e081cad0c10f60b69e9e5035702e1453bb3"
OUTPUT_ROOT = PROJECT_ROOT / "data/research/rf/rf-0b-gap-lineage-diagnostic-v1"
MARKER_PATH = OUTPUT_ROOT / "semantic_read_started.json"
REPORT_PATH = OUTPUT_ROOT / "report.json"
MANIFEST_PATH = OUTPUT_ROOT / "manifest.json"
AUDIT_PATH = OUTPUT_ROOT / "audit.json"

EXPECTED_UNEXPLAINED_KEY_COUNT = 5


@dataclass(frozen=True)
class RFDScope:
    document: dict[str, Any]
    sha256: str = PROTOCOL_SHA256

    @classmethod
    def load(cls) -> "RFDScope":
        if PROTOCOL_PATH.is_symlink() or sha256_file(PROTOCOL_PATH) != PROTOCOL_SHA256:
            raise RFDError("RF diagnostic frozen protocol differs")
        try:
            document = yaml.safe_load(PROTOCOL_PATH.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            raise RFDError("RF diagnostic frozen YAML is invalid") from exc
        if not isinstance(document, dict):
            raise RFDError("RF diagnostic frozen YAML is not a mapping")
        objective = document.get("objective", {})
        execution = document.get("execution_control", {})
        boundary = document.get("successor_boundary", {})
        if (
            document.get("schema_version") != "rf-0b-gap-lineage-diagnostic-v1"
            or document.get("status")
            != "RESULT_BLIND_DATA_LINEAGE_DIAGNOSTIC_FROZEN_PENDING_USER_APPROVAL"
            or document.get("production_authorization") != "none"
            or objective.get("candidate_value_or_score_computation") is not False
            or objective.get("outcome_or_return_read") is not False
            or objective.get("gate_change_or_re_evaluation") != "forbidden"
            or boundary.get("diagnosis_does_not_reopen_rf") is not True
            or boundary.get("diagnosis_does_not_lower_the_failed_gate") is not True
            or execution.get("external_network_or_provider") is not False
            or execution.get("env_or_secret_read") is not False
            or execution.get("docker_network_mode") != "none"
            or execution.get("same_scope_rerun") != "forbidden"
            or document.get("verdicts", {}).get("strategy_effective") != "NOT_EVALUATED"
        ):
            raise RFDError("RF diagnostic authority or contract differs")
        return cls(document)


def validate_bound_inputs(scope: RFDScope, root: Path = PROJECT_ROOT) -> None:
    parent = scope.document["parent_authority"]
    frozen = scope.document["frozen_inputs"]["raw_market_store"]["r3_frozen_input_manifest"]
    checks = {
        parent["rf_0b_protocol"]["path"]: parent["rf_0b_protocol"]["sha256"],
        parent["r2_profile"]["path"]: parent["r2_profile"]["sha256"],
        parent["r2_field_profile"]["path"]: parent["r2_field_profile"]["sha256"],
        parent["r2_audit_r3"]["path"]: parent["r2_audit_r3"]["sha256"],
        frozen["path"]: frozen["sha256"],
    }
    for relative, expected in checks.items():
        path = root / relative
        if path.is_symlink() or not path.is_file() or sha256_file(path) != expected:
            raise RFDError(f"RF diagnostic bound input differs: {relative}")


def runtime_identity() -> dict[str, str]:
    embedded = os.getenv("SHAIWEI_RELEASE_GIT_HEAD", "").strip().lower()
    if re.fullmatch(r"[0-9a-f]{40}", embedded) is None or git_head() != embedded:
        raise RFDError("RF diagnostic release Git identity differs")
    return {"git_head": embedded, "code_snapshot_sha256": code_snapshot_sha256()}
