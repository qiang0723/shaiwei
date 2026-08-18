"""Frozen contract and immutable paths for the TS-v6-3 ranked-subset effect."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
from typing import Any

import yaml

from shaiwei.config import PROJECT_ROOT
from shaiwei.provenance import code_snapshot_sha256, git_head
from shaiwei.research.trend_swing.r3g2.contract import sha256_file


class V63Error(RuntimeError):
    """Fail-closed TS-v6-3 contract violation."""


PROTOCOL_PATH = PROJECT_ROOT / "config/ts_v6_3_ranked_subset_effect_v1.yaml"
PROTOCOL_SHA256 = "74a9111ae620f15072555188e48ba25ef22cf98daa81ad31a7f471412169b3f9"
OUTPUT_ROOT = PROJECT_ROOT / "data/research/trend_swing/ts-v6-3-ranked-subset-effect-v1"
PREFLIGHT_PATH = OUTPUT_ROOT / "pre_effect_preflight.json"
MARKER_PATH = OUTPUT_ROOT / "effect_read_started.json"
REPORT_PATH = OUTPUT_ROOT / "report.json"
FAILURE_PATH = OUTPUT_ROOT / "failure.json"
AUDIT_PATH = OUTPUT_ROOT / "audit.json"
PARENT_FIRST_PASS_ROOT = PROJECT_ROOT / (
    "data/research/trend_swing/ts-v5-r3g2-effect-entrypoint-recovery-v1/first_pass"
)
PARENT_FIRST_PASS_BUNDLE_SHA256 = (
    "d00f2fce1c4be5cd6a8af07436416e65d015f3f053470525ee8bd5e005bac41c"
)
PARENT_POINT_HASH = "81833a47b1edb59455c997c422bb36b63454f1da84e29696269c9c950e019784"
LEGACY_POINT_HASHES = (
    "81833a47b1edb59455c997c422bb36b63454f1da84e29696269c9c950e019784",
    "09bceb50259b20a82b8af30c41d24af7e2b543ff78790aa893c814f72dfc2ea5",
    "355926341879e2a55dc3268d9e0f80c3a82bae5c56c96f59516087b365ac8076",
)
PARENT_BASELINE_EXPECTANCY_RMB = -88.80
PARENT_EXIT_GROUP_PNL_RMB = {
    "STOP_EXIT": -48641.00,
    "TAKE_PROFIT": 41309.72,
    "TIME_EXIT": 1736.68,
}
PARENT_EXIT_GROUP_SOURCE = "docs/TS_V5_R3G3_DISCOVERY_DIAGNOSTIC_ACCEPTANCE_20260817.md"


def _mapping(path: Path) -> dict[str, Any]:
    if path.is_symlink() or sha256_file(path) != PROTOCOL_SHA256:
        raise V63Error(f"TS-v6-3 frozen protocol differs: {path.name}")
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise V63Error(f"TS-v6-3 frozen YAML is invalid: {path.name}") from exc
    if not isinstance(value, dict):
        raise V63Error(f"TS-v6-3 frozen YAML is not a mapping: {path.name}")
    return value


@dataclass(frozen=True)
class V63Scope:
    document: dict[str, Any]
    sha256: str = PROTOCOL_SHA256

    @classmethod
    def load(cls) -> "V63Scope":
        document = _mapping(PROTOCOL_PATH)
        authority = document.get("authority_at_freeze", {})
        enabled = {key for key, value in authority.items() if value is True}
        point = document.get("selected_effect_point", {})
        roles = document.get("chronological_roles", {})
        execution = document.get("future_execution_not_authorized_here", {})
        verdicts = document.get("verdicts", {})
        budget = document.get("user_rulings_20260818_binding", {})
        if (
            document.get("schema_version") != "ts-v6-3-ranked-subset-effect-protocol-v1"
            or document.get("status")
            != "RESULT_BLIND_EFFECT_PROTOCOL_FROZEN_PENDING_USER_APPROVAL_AND_ENGINEERING"
            or document.get("production_authorization") != "none"
            or enabled != {"protocol_and_contract_tests"}
            or authority.get("user_approval_of_this_frozen_protocol_before_engineering")
            != "required"
            or point.get("mechanism") != "BREAKOUT_RETEST"
            or point.get("point_hash") != PARENT_POINT_HASH
            or point.get("sensitivity_neighbours") != "none"
            or point.get("event_subset") != "v6_1_frozen_top_94_development_keys"
            or document.get("event_identity_gate", {}).get(
                "candidate_set_must_equal_v6_1_frozen_94_keys_exactly"
            ) is not True
            or roles.get("conditional_frozen_holdout_effect", {}).get("status")
            != "NOT_PART_OF_THIS_PROTOCOL"
            or roles.get("current_partial_year", {}).get("role") != "RESERVED_NOT_READ"
            or document.get("ranking_lineage", {}).get("w7", {}).get("status")
            != "NOT_USED_DISCOVERY_ONLY_PROTOCOL"
            or document.get("attempt_and_firewall", {}).get(
                "strategy_effect_attempt_count_on_first_effect_read"
            ) != 1
            or document.get("attempt_and_firewall", {}).get("holdout_outcomes_read")
            != "forbidden_by_this_protocol"
            or budget.get("budget_after_this_protocol") != 1
            or execution.get("docker_network_mode") != "none"
            or execution.get("project_env_or_secret_mount") != "forbidden"
            or verdicts.get("discovery_pass_authorizes_holdout_read") is not False
            or verdicts.get("discovery_pass_authorizes_paper_or_production") is not False
            or verdicts.get("production_authorization_for_every_outcome") != "none"
        ):
            raise V63Error("TS-v6-3 authority, role, or effect contract differs")
        return cls(document)

    @property
    def selected_point_hashes(self) -> tuple[str, ...]:
        return (self.document["selected_effect_point"]["point_hash"],)

    def candidate_parameters(self) -> dict[str, str]:
        point = self.document["selected_effect_point"]
        return {key: str(value) for key, value in point["parameters"].items()}


def _bound_input_rows(scope: V63Scope, *, include_disallowed_reference: bool) -> dict[str, str]:
    checks: dict[str, str] = {}
    for row in scope.document["predecessors"].values():
        if isinstance(row, dict) and {"path", "sha256"} <= set(row):
            checks[row["path"]] = row["sha256"]
    benchmark = scope.document["benchmark"]
    checks[benchmark["path"]] = benchmark["sha256"]
    lineage = scope.document["ranking_lineage"]
    if include_disallowed_reference:
        checks[lineage["old_p1_cache"]["path"]] = lineage["old_p1_cache"]["sha256"]
    clean = lineage["clean_m6_lineage"]
    checks[clean["protocol_path"]] = clean["protocol_sha256"]
    for row in clean["reusable_predictions"].values():
        checks[row["path"]] = row["sha256"]
    return checks


def _validate_rows(checks: dict[str, str], root: Path) -> None:
    for relative, expected in checks.items():
        path = root / relative
        if path.is_symlink() or not path.is_file() or sha256_file(path) != expected:
            raise V63Error(f"TS-v6-3 bound input differs: {relative}")


def validate_bound_inputs(scope: V63Scope, root: Path = PROJECT_ROOT) -> None:
    _validate_rows(_bound_input_rows(scope, include_disallowed_reference=True), root)


def validate_authorized_effect_inputs(scope: V63Scope, root: Path = PROJECT_ROOT) -> None:
    """Validate only inputs that the real-effect runtime may actually mount."""
    _validate_rows(_bound_input_rows(scope, include_disallowed_reference=False), root)


def runtime_identity() -> dict[str, str]:
    embedded = os.getenv("SHAIWEI_RELEASE_GIT_HEAD", "").strip().lower()
    if re.fullmatch(r"[0-9a-f]{40}", embedded) is None or git_head() != embedded:
        raise V63Error("TS-v6-3 release Git identity differs")
    return {"git_head": embedded, "code_snapshot_sha256": code_snapshot_sha256()}
