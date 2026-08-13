"""Frozen scope and identities for TS-v5-R3G-1 recent density."""

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
from shaiwei.research.trend_swing.v5_contract import sha256_file


SCOPE_PATH = PROJECT_ROOT / "config/ts_v5_r3g1_recent_density_scope_v1.yaml"
SCOPE_SHA256 = "3b83d8a569886b2af78298c85789b8c6495b0cf8903975b2ddb0c48367040381"
ADDENDUM_PATH = PROJECT_ROOT / "config/ts_v5_r3g1_role_boundary_addendum_v1.yaml"
ADDENDUM_SHA256 = "59133b29891b3f2524ea5c4a05e832d165714bbf9fbd92666994399658530d29"
CORRECTION_PATH = PROJECT_ROOT / "config/ts_v5_r3g1_execution_clock_correction_addendum_v1.yaml"
CORRECTION_SHA256 = "5aa7f0b1385a3bab64f30f63bac812c56fdc8eb2b3268065b357894f7872710b"
RECOVERY_PATH = PROJECT_ROOT / "config/ts_v5_r3g1_execution_projection_recovery_r2.yaml"
RECOVERY_SHA256 = "01f0ae9fba381bfa9c6bd7d1f069339da6b26d8c06706549944403b00427b380"
IDENTITY_RECOVERY_PATH = PROJECT_ROOT / "config/ts_v5_r3g1_release_identity_recovery_r3.yaml"
IDENTITY_RECOVERY_SHA256 = "f82eed0cddf35dd7e1eecdbd205b13fde84e3dbfdc77e8e7fd878148acea9695"
OUTPUT_ROOT = PROJECT_ROOT / "data/research/trend_swing/ts-v5-r3g1-recent-density-r2"
EVENT_PATH = OUTPUT_ROOT / "events.parquet"
PROFILE_PATH = OUTPUT_ROOT / "density_profile.json"
AUDIT_PATH = OUTPUT_ROOT / "audit.json"


def _load_yaml(path: Path, expected_sha256: str) -> dict[str, Any]:
    if path.is_symlink() or sha256_file(path) != expected_sha256:
        raise D1ControlError(f"TS-v5-R3G-1 frozen input differs: {path.name}")
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise D1ControlError("TS-v5-R3G-1 frozen YAML is invalid") from exc
    if not isinstance(value, dict):
        raise D1ControlError("TS-v5-R3G-1 frozen YAML is not a mapping")
    return value


@dataclass(frozen=True)
class R3G1Scope:
    document: dict[str, Any]
    addendum: dict[str, Any]
    correction: dict[str, Any]
    recovery: dict[str, Any]
    identity_recovery: dict[str, Any]
    sha256: str = SCOPE_SHA256
    addendum_sha256: str = ADDENDUM_SHA256
    recovery_sha256: str = RECOVERY_SHA256
    identity_recovery_sha256: str = IDENTITY_RECOVERY_SHA256

    @classmethod
    def load(cls) -> "R3G1Scope":
        document = _load_yaml(SCOPE_PATH, SCOPE_SHA256)
        addendum = _load_yaml(ADDENDUM_PATH, ADDENDUM_SHA256)
        correction = _load_yaml(CORRECTION_PATH, CORRECTION_SHA256)
        recovery = _load_yaml(RECOVERY_PATH, RECOVERY_SHA256)
        identity_recovery = _load_yaml(IDENTITY_RECOVERY_PATH, IDENTITY_RECOVERY_SHA256)
        authority = document.get("authority", {})
        required_true = {
            "offline_engineering_and_fixture",
            "one_result_blind_density_profile",
            "one_independent_audit",
            "read_price_reference_market_sector_and_execution_gate_fields",
        }
        if (
            document.get("status") != "RESULT_BLIND_RECENT_DENSITY_FROZEN"
            or document.get("production_authorization") != "none"
            or any(value is not (key in required_true) for key, value in authority.items())
            or addendum.get("binds_scope", {}).get("sha256") != SCOPE_SHA256
            or any(value is not False for value in addendum.get("authority", {}).values())
            or correction.get("binds", {}).get("r3g1_scope_sha256") != SCOPE_SHA256
            or any(value is not False for value in correction.get("authority", {}).values())
            or recovery.get("status") != "RESULT_KNOWN_IMPLEMENTATION_DEFECT_RECOVERY_FROZEN"
            or recovery.get("frozen_parent", {}).get("scope_sha256") != SCOPE_SHA256
            or recovery.get("recovery_output", {}).get("root")
            != OUTPUT_ROOT.relative_to(PROJECT_ROOT).as_posix()
            or recovery.get("authority", {}).get("one_recovery_density_profile") is not True
            or recovery.get("authority", {}).get("one_recovery_independent_audit") is not True
            or any(
                recovery.get("authority", {}).get(key) is not False
                for key in (
                    "read_post_entry_return_or_effect",
                    "read_alpha158_value_or_rank",
                    "benchmark_value_read",
                    "model_training_prediction_or_backtest",
                    "external_network_or_provider",
                    "env_or_secret_read",
                    "paper_web_scheduler_or_production_change",
                )
            )
            or identity_recovery.get("status")
            != "RESULT_UNKNOWN_PRE_RUN_IMAGE_IDENTITY_RECOVERY_FROZEN"
            or identity_recovery.get("binds", {}).get("execution_projection_recovery_sha256")
            != RECOVERY_SHA256
            or identity_recovery.get("provisional_image", {}).get("image_process_started")
            is not False
            or identity_recovery.get("authority", {}).get("additional_density_attempt") is not False
        ):
            raise D1ControlError("TS-v5-R3G-1 authority or identity differs")
        return cls(document, addendum, correction, recovery, identity_recovery)

    @property
    def roles(self) -> tuple[tuple[str, str, str], ...]:
        roles = self.document["chronological_roles"]
        return tuple(
            (name, str(roles[name]["start"]), str(roles[name]["end"]))
            for name in (
                "selectable_discovery",
                "frozen_stability_holdout",
                "current_partial_year_monitor",
            )
        )


def validate_bound_inputs(scope: R3G1Scope, root: Path = PROJECT_ROOT) -> None:
    frozen = scope.document["frozen_inputs"]
    checks = {
        frozen["r3g_scope_path"]: frozen["r3g_scope_sha256"],
        frozen["r3g_registry_path"]: frozen["r3g_registry_sha256"],
        frozen["r3g_engineering_report_path"]: frozen["r3g_engineering_report_sha256"],
        frozen["r3g_audit_path"]: frozen["r3g_audit_sha256"],
        frozen["r3_manifest_path"]: frozen["r3_manifest_sha256"],
    }
    for relative, expected in checks.items():
        if sha256_file(root / relative) != expected:
            raise D1ControlError(f"TS-v5-R3G-1 bound input differs: {relative}")
    parent = scope.recovery["frozen_parent"]
    for key in ("profile", "event", "audit"):
        if sha256_file(root / parent[f"{key}_path"]) != parent[f"{key}_sha256"]:
            raise D1ControlError(f"TS-v5-R3G-1 immutable parent {key} differs")


def runtime_code_identity() -> dict[str, str]:
    embedded = os.getenv("SHAIWEI_RELEASE_GIT_HEAD", "").strip().lower()
    if re.fullmatch(r"[0-9a-f]{40}", embedded) is None or git_head() != embedded:
        raise D1ControlError("TS-v5-R3G-1 release Git identity differs")
    return {"git_head": embedded, "code_snapshot_sha256": code_snapshot_sha256()}
