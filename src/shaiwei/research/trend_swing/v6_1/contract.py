"""Frozen contract and immutable paths for the TS-v6-1 ranking preflight."""

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


PROTOCOL_PATH = PROJECT_ROOT / "config/ts_v6_1_entry_quality_ranking_preflight_v1.yaml"
PROTOCOL_SHA256 = "378e3ebc5e8af42e95cb1a43dfad04d19c4815fb63e60b85638a0808bc18920c"
OUTPUT_ROOT = PROJECT_ROOT / "data/research/trend_swing/ts-v6-1-entry-quality-ranking-preflight-v1"
MARKER_PATH = OUTPUT_ROOT / "semantic_read_started.json"
RANKED_EVENT_PATH = OUTPUT_ROOT / "ranked_events.parquet"
PROFILE_PATH = OUTPUT_ROOT / "profile.json"
MANIFEST_PATH = OUTPUT_ROOT / "manifest.json"
AUDIT_PATH = OUTPUT_ROOT / "audit.json"


def _load_yaml(path: Path, expected_sha256: str) -> dict[str, Any]:
    if path.is_symlink() or sha256_file(path) != expected_sha256:
        raise D1ControlError(f"TS-v6-1 frozen input differs: {path.name}")
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise D1ControlError(f"TS-v6-1 frozen YAML is invalid: {path.name}") from exc
    if not isinstance(value, dict):
        raise D1ControlError(f"TS-v6-1 frozen YAML is not a mapping: {path.name}")
    return value


@dataclass(frozen=True)
class V61Scope:
    document: dict[str, Any]
    sha256: str = PROTOCOL_SHA256

    @classmethod
    def load(cls) -> "V61Scope":
        document = _load_yaml(PROTOCOL_PATH, PROTOCOL_SHA256)
        roles = document.get("chronological_roles", {})
        execution = document.get("execution_control", {})
        mechanism = document.get("entry_quality_ranking_mechanism", {})
        selection = mechanism.get("selection_rule", {})
        semantics = document.get("inherited_parent_semantics", {})
        budget = document.get("user_rulings_20260818", {}).get(
            "ruling_ts_lane_effect_budget", {}
        )
        if (
            document.get("schema_version") != "ts-v6-1-entry-quality-ranking-preflight-v1"
            or document.get("status") != "RESULT_INFORMED_ZERO_EFFECT_PREFLIGHT_FROZEN"
            or document.get("production_authorization") != "none"
            or document.get("objective", {}).get("strategy_effect_evaluation") is not False
            or semantics.get("alpha158_read") is not False
            or semantics.get("exit_rules_changed") is not False
            or semantics.get("sizing_or_risk_rules_changed") is not False
            or roles.get("current_partial_year", {}).get("data_read_allowed") is not False
            or document.get("frozen_inputs", {}).get("new_market_or_security_data_read") is not False
            or mechanism.get("hard_quality_gates_on_events") != 0
            or mechanism.get("one_primary_mechanism_change_only") is not True
            or selection.get("development_top_k") != 94
            or float(selection.get("frozen_retention_fraction_of_188_parent_events")) != 0.5
            or budget.get("remaining_independent_effect_protocols") != 2
            or execution.get("external_network_or_provider") is not False
            or execution.get("env_or_secret_read") is not False
            or execution.get("docker_network_mode") != "none"
            or execution.get("post_marker_same_scope_rerun") != "forbidden"
            or not document.get("result_firewall", {}).get("forbidden")
            or document.get("verdicts", {}).get("strategy_effective") != "NOT_EVALUATED"
            or document.get("verdicts", {}).get("production_authorization") != "none"
        ):
            raise D1ControlError("TS-v6-1 authority, role, or ranking contract differs")
        return cls(document)

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

    @property
    def development_top_k(self) -> int:
        return int(
            self.document["entry_quality_ranking_mechanism"]["selection_rule"]["development_top_k"]
        )


def validate_bound_inputs(scope: V61Scope, root: Path = PROJECT_ROOT) -> None:
    frozen = scope.document["frozen_inputs"]
    checks = {
        frozen["parent_observation_path"]: frozen["parent_observation_sha256"],
        frozen["parent_event_path"]: frozen["parent_event_sha256"],
        frozen["parent_density_profile_path"]: frozen["parent_density_profile_sha256"],
        frozen["parent_density_audit_path"]: frozen["parent_density_audit_sha256"],
    }
    parent = scope.document["result_informed_parent"]
    checks[parent["parent_protocol_path"]] = parent["parent_protocol_sha256"]
    sibling = parent["stopped_sibling_preflight"]
    for name in ("protocol", "operationalization_addendum", "profile", "manifest", "audit"):
        checks[sibling[f"{name}_path"]] = sibling[f"{name}_sha256"]
    for relative, expected in checks.items():
        path = root / relative
        if path.is_symlink() or sha256_file(path) != expected:
            raise D1ControlError(f"TS-v6-1 bound input differs: {relative}")


def runtime_identity() -> dict[str, str]:
    embedded = os.getenv("SHAIWEI_RELEASE_GIT_HEAD", "").strip().lower()
    if re.fullmatch(r"[0-9a-f]{40}", embedded) is None or git_head() != embedded:
        raise D1ControlError("TS-v6-1 release Git identity differs")
    return {"git_head": embedded, "code_snapshot_sha256": code_snapshot_sha256()}
