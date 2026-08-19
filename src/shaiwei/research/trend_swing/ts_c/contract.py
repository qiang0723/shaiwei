"""Frozen contract and immutable paths for the TS-C trigger qualification."""

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


class TQCError(RuntimeError):
    """Fail-closed TS-C qualification contract violation."""


PROTOCOL_PATH = PROJECT_ROOT / "config/ts_c_trigger_qualification_v1.yaml"
PROTOCOL_SHA256 = "0cf969edf29dfe103d9538e35c1efe983f91d505f027688f89c6dc5815c0bcef"
OUTPUT_ROOT = PROJECT_ROOT / "data/research/trend_swing/ts-c-trigger-qualification-v1"
MARKER_PATH = OUTPUT_ROOT / "semantic_read_started.json"
EVENTS_PATH = OUTPUT_ROOT / "events.parquet"
PROFILE_PATH = OUTPUT_ROOT / "profile.json"
MANIFEST_PATH = OUTPUT_ROOT / "manifest.json"
AUDIT_PATH = OUTPUT_ROOT / "audit.json"

TRIGGER_IDS = ("VWAP_ANCHOR_PULLBACK", "HIGH20_DRAWDOWN", "MA20_PULLBACK")
RECOVERY_SCOPE_PATH = PROJECT_ROOT / "config/ts_c_trigger_qualification_recovery_r2.yaml"
RECOVERY_SCOPE_SHA256 = "efebfb103c495e5edd1519f1c0439628b070432168f9e452351cf4f1cd767477"
RECOVERY_OUTPUT_ROOT = PROJECT_ROOT / "data/research/trend_swing/ts-c-trigger-qualification-v1-r2"


@dataclass(frozen=True)
class TQCRecovery:
    document: dict[str, Any]
    sha256: str = RECOVERY_SCOPE_SHA256

    @classmethod
    def load_if_present(cls) -> "TQCRecovery | None":
        if not RECOVERY_SCOPE_PATH.is_file():
            return None
        if RECOVERY_SCOPE_PATH.is_symlink() or sha256_file(RECOVERY_SCOPE_PATH) != RECOVERY_SCOPE_SHA256:
            raise TQCError("TS-C recovery scope differs")
        try:
            document = yaml.safe_load(RECOVERY_SCOPE_PATH.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            raise TQCError("TS-C recovery YAML is invalid") from exc
        if not isinstance(document, dict):
            raise TQCError("TS-C recovery YAML is not a mapping")
        parent = document.get("parent_scope", {})
        authority = document.get("authority", {})
        if (
            document.get("schema_version") != "ts-c-trigger-qualification-recovery-r2-v1"
            or document.get("status") != "RESULT_BLIND_RECOVERY_SCOPE_FROZEN"
            or document.get("production_authorization") != "none"
            or parent.get("protocol_sha256") != PROTOCOL_SHA256
            or parent.get("profile_values_computed_or_written_before_failure") is not False
            or parent.get("original_scope_closed_no_same_scope_rerun") is not True
            or document.get("recovery", {}).get("candidate_or_effect_attempts_consumed") != 0
            or document.get("recovery", {}).get("density_gates_unchanged") is not True
            or authority.get("docker_network_mode") != "none"
            or authority.get("env_or_secret_read") is not False
        ):
            raise TQCError("TS-C recovery authority or contract differs")
        return cls(document)

    def validate_parent_evidence(self, root: Path = PROJECT_ROOT) -> None:
        parent = self.document["parent_scope"]
        relative, expected = parent["marker_path"], parent["marker_sha256"]
        path = root / relative
        if path.is_symlink() or not path.is_file() or sha256_file(path) != expected:
            raise TQCError("TS-C recovery parent evidence differs")


def active_root(recovery: TQCRecovery | None) -> Path:
    return RECOVERY_OUTPUT_ROOT if recovery is not None else OUTPUT_ROOT


@dataclass(frozen=True)
class TQCScope:
    document: dict[str, Any]
    sha256: str = PROTOCOL_SHA256

    @classmethod
    def load(cls) -> "TQCScope":
        if PROTOCOL_PATH.is_symlink() or sha256_file(PROTOCOL_PATH) != PROTOCOL_SHA256:
            raise TQCError("TS-C frozen protocol differs")
        try:
            document = yaml.safe_load(PROTOCOL_PATH.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            raise TQCError("TS-C frozen YAML is invalid") from exc
        if not isinstance(document, dict):
            raise TQCError("TS-C frozen YAML is not a mapping")
        objective = document.get("objective", {})
        execution = document.get("execution_control", {})
        gate = document.get("density_gate", {})
        if (
            document.get("schema_version") != "ts-c-trigger-qualification-v1"
            or document.get("status")
            != "RESULT_BLIND_QUALIFICATION_PREFLIGHT_FROZEN_PENDING_USER_APPROVAL"
            or document.get("production_authorization") != "none"
            or objective.get("strategy_effect_evaluation") is not False
            or objective.get("post_entry_outcomes_allowed") is not False
            or [row.get("trigger_id") for row in document.get("trigger_arms", [])]
            != list(TRIGGER_IDS)
            or gate.get("per_trigger_minimum_confirmed_events") != 120
            or gate.get("per_trigger_minimum_events_each_calendar_year") != 10
            or gate.get("per_trigger_minimum_distinct_signal_days") != 40
            or gate.get("threshold_change_after_profile") != "forbidden"
            or gate.get("no_trigger_parameter_tuning") is not True
            or execution.get("external_network_or_provider") is not False
            or execution.get("env_or_secret_read") is not False
            or execution.get("docker_network_mode") != "none"
            or execution.get("same_scope_rerun") != "forbidden"
            or document.get("verdicts", {}).get("strategy_effective") != "NOT_EVALUATED"
        ):
            raise TQCError("TS-C authority or contract differs")
        return cls(document)


def validate_bound_inputs(scope: TQCScope, root: Path = PROJECT_ROOT) -> None:
    manifest = scope.document["frozen_inputs"]["raw_market_store"]["r3_frozen_input_manifest"]
    path = root / manifest["path"]
    if path.is_symlink() or not path.is_file() or sha256_file(path) != manifest["sha256"]:
        raise TQCError("TS-C bound raw snapshot manifest differs")


def runtime_identity() -> dict[str, str]:
    embedded = os.getenv("SHAIWEI_RELEASE_GIT_HEAD", "").strip().lower()
    if re.fullmatch(r"[0-9a-f]{40}", embedded) is None or git_head() != embedded:
        raise TQCError("TS-C release Git identity differs")
    return {"git_head": embedded, "code_snapshot_sha256": code_snapshot_sha256()}
