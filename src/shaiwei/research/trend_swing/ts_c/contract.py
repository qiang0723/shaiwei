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
