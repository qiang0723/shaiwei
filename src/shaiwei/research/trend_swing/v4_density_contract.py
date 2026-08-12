"""Frozen contract and artifact identities for TS-v4B density preflight."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
from typing import Any

import yaml

from shaiwei.config import PROJECT_ROOT
from shaiwei.provenance import code_snapshot_sha256, git_head
from shaiwei.research.trend_swing.contract import (
    TrendSwingError,
    project_path,
    sha256_file,
)


RELEASE_PATH = PROJECT_ROOT / "config/ts_v4_density_preflight_release_v1.yaml"
RECOVERY_PATH = PROJECT_ROOT / "config/ts_v4_density_preflight_recovery_r1.yaml"
ORIGINAL_OUTPUT_DIR = PROJECT_ROOT / "data/research/trend_swing/ts-v4-density-preflight-v1"
OUTPUT_DIR = PROJECT_ROOT / "data/research/trend_swing/ts-v4-density-preflight-r1"
EVENT_PATH = OUTPUT_DIR / "arm_events.parquet"
DAILY_PATH = OUTPUT_DIR / "anonymous_arm_daily.parquet"
REPORT_PATH = OUTPUT_DIR / "profile_report.json"
AUDIT_PATH = OUTPUT_DIR / "audit.json"


def _yaml(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(project_path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TrendSwingError(f"TS v4B expected YAML mapping: {path.name}")
    return value


def _validate_authority(document: dict[str, Any]) -> None:
    allowed_true = {
        "offline_engineering_and_fixture",
        "one_result_blind_density_profile",
        "one_independent_audit",
        "read_price_and_reference_fields_through_candidate_next_open",
        "alpha158_event_key_only",
    }
    for key, value in document.get("authorization", {}).items():
        expected = key in allowed_true
        if value is not expected:
            raise TrendSwingError(f"TS v4B authority differs: {key}")


def _validate_release(document: dict[str, Any]) -> None:
    if (
        document.get("release_id") != "ts-v4-density-preflight-release-v1"
        or document.get("stage") != "RESULT_BLIND_DENSITY_PREFLIGHT_AUTHORIZED_ONCE"
    ):
        raise TrendSwingError("unexpected TS v4B release identity or stage")
    _validate_authority(document)
    arms = document.get("arms")
    expected_arms = [
        {"arm_id": "TS4-D015", "pullback_depth_fraction": 0.015},
        {"arm_id": "TS4-D025", "pullback_depth_fraction": 0.025},
        {"arm_id": "TS4-D035", "pullback_depth_fraction": 0.035},
        {"arm_id": "TS4-D040", "pullback_depth_fraction": 0.04},
    ]
    if arms != expected_arms:
        raise TrendSwingError("TS v4B arm set differs")
    expected_pairs = [
        ["TS4-D015", "TS4-D025"],
        ["TS4-D025", "TS4-D035"],
        ["TS4-D035", "TS4-D040"],
    ]
    if document.get("adjacent_pairs") != expected_pairs:
        raise TrendSwingError("TS v4B adjacency differs")
    gate = document.get("density_gate", {})
    expected_gate = {
        "per_arm_minimum_legal_events": 30,
        "per_arm_minimum_distinct_signal_days": 20,
        "per_arm_minimum_events_each_calendar_year": 5,
        "required_calendar_years": [2019, 2020, 2021],
        "alpha158_event_key_coverage_required": 1.0,
        "alpha158_duplicate_event_key_count_required": 0,
        "minimum_passing_adjacent_pair_count": 1,
        "pass_verdict": "GO_DENSE_PARAMETER_REGION",
        "failure_verdict": "STOP_NO_DENSE_PARAMETER_REGION",
        "threshold_change_after_profile": "forbidden",
    }
    if gate != expected_gate:
        raise TrendSwingError("TS v4B density gate differs")
    attempts = document.get("attempt_control", {})
    if attempts != {
        "proposed_strategy_attempt_count": 4,
        "density_profile_attempt_count": 1,
        "independent_audit_attempt_count": 1,
        "strategy_effect_attempt_count": 0,
        "same_scope_profile_rerun": "forbidden",
        "same_scope_audit_rerun": "forbidden",
        "parameter_grid_expansion": "forbidden",
    }:
        raise TrendSwingError("TS v4B attempt control differs")


@dataclass(frozen=True)
class V4DensityRelease:
    path: Path
    document: dict[str, Any]
    sha256: str

    @classmethod
    def load(cls, path: Path = RELEASE_PATH) -> "V4DensityRelease":
        resolved = project_path(path)
        document = _yaml(resolved)
        _validate_release(document)
        return cls(resolved, document, sha256_file(resolved))

    @property
    def arms(self) -> tuple[tuple[str, float], ...]:
        return tuple(
            (str(item["arm_id"]), float(item["pullback_depth_fraction"]))
            for item in self.document["arms"]
        )

    @property
    def adjacent_pairs(self) -> tuple[tuple[str, str], ...]:
        return tuple(tuple(pair) for pair in self.document["adjacent_pairs"])

    @property
    def inputs(self) -> dict[str, Any]:
        return self.document["bound_inputs"]


@dataclass(frozen=True)
class V4DensityRecovery:
    path: Path
    document: dict[str, Any]
    sha256: str

    @classmethod
    def load(
        cls,
        release: V4DensityRelease,
        path: Path = RECOVERY_PATH,
    ) -> "V4DensityRecovery":
        resolved = project_path(path)
        document = _yaml(resolved)
        parent = document.get("frozen_parent", {})
        delta = document.get("single_recovery_delta", {})
        if (
            document.get("recovery_id") != "ts-v4-density-preflight-recovery-r1"
            or document.get("stage")
            != "RESULT_BLIND_SERIALIZATION_RECOVERY_AUTHORIZED_ONCE"
            or parent.get("release_id") != release.document["release_id"]
            or parent.get("release_sha256") != release.sha256
            or parent.get("immutable_and_not_rewritten") is not True
        ):
            raise TrendSwingError("unexpected TS v4B-R1 identity or parent")
        if (
            delta.get("data_logic_changed") is not False
            or delta.get("state_machine_changed") is not False
            or delta.get("arm_or_threshold_changed") is not False
            or delta.get("alpha_key_projection_changed") is not False
            or delta.get("output_scope")
            != "data/research/trend_swing/ts-v4-density-preflight-r1"
        ):
            raise TrendSwingError("TS v4B-R1 recovery delta broadened")
        allowed_true = {
            "offline_engineering_and_fixture",
            "one_recovery_density_profile",
            "one_recovery_independent_audit",
            "read_price_and_reference_fields_through_candidate_next_open",
            "alpha158_event_key_only",
        }
        for key, value in document.get("authorization", {}).items():
            if value is not (key in allowed_true):
                raise TrendSwingError(f"TS v4B-R1 authority differs: {key}")
        return cls(resolved, document, sha256_file(resolved))


def validate_bound_inputs(release: V4DensityRelease) -> None:
    predecessor = release.document["predecessor"]
    inputs = release.inputs
    checks = (
        (predecessor["protocol_path"], predecessor["protocol_sha256"]),
        (inputs["r3_manifest_path"], inputs["r3_manifest_sha256"]),
        (inputs["alpha158_path"], inputs["alpha158_sha256"]),
    )
    for relative, expected in checks:
        path = project_path(relative)
        if not path.is_file() or sha256_file(path) != expected:
            raise TrendSwingError(f"TS v4B bound input differs: {relative}")


def runtime_code_identity() -> dict[str, str]:
    embedded = os.getenv("SHAIWEI_RELEASE_GIT_HEAD", "").strip().lower()
    if re.fullmatch(r"[0-9a-f]{40}", embedded) is None:
        raise TrendSwingError("TS v4B requires an embedded 40-character release Git head")
    actual = git_head()
    if actual != embedded:
        raise TrendSwingError("TS v4B embedded and runtime Git heads differ")
    return {"git_head": actual, "code_snapshot_sha256": code_snapshot_sha256()}
