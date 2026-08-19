"""Frozen contract and immutable paths for the TS-B holdout one-shot effect."""

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


class TSBError(RuntimeError):
    """Fail-closed TS-B contract violation."""


PROTOCOL_PATH = PROJECT_ROOT / "config/ts_b_holdout_effect_v1.yaml"
PROTOCOL_SHA256 = "77fceb27f60f143954f6675bf108edca1a65b4523f403c983d7debc3b787b225"
OUTPUT_ROOT = PROJECT_ROOT / "data/research/trend_swing/ts-b-holdout-effect-v1"
PARENT_POINT_HASH = "81833a47b1edb59455c997c422bb36b63454f1da84e29696269c9c950e019784"
V64_FIRST_PASS_ROOT = PROJECT_ROOT / (
    "data/research/trend_swing/ts-v6-4-no-takeprofit-effect-v1/first_pass"
)
V64_FIRST_PASS_BUNDLE_SHA256 = (
    "02b336300b0df3f9786e06f5222bfebe01538f8cfaece7acdbcb732d151e47e4"
)


def _mapping(path: Path) -> dict[str, Any]:
    if path.is_symlink() or sha256_file(path) != PROTOCOL_SHA256:
        raise TSBError(f"TS-B frozen protocol differs: {path.name}")
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise TSBError(f"TS-B frozen YAML is invalid: {path.name}") from exc
    if not isinstance(value, dict):
        raise TSBError(f"TS-B frozen YAML is not a mapping: {path.name}")
    return value


@dataclass(frozen=True)
class TSBScope:
    document: dict[str, Any]
    sha256: str = PROTOCOL_SHA256

    @classmethod
    def load(cls) -> "TSBScope":
        document = _mapping(PROTOCOL_PATH)
        authority = document.get("authority_at_freeze", {})
        enabled = {key for key, value in authority.items() if value is True}
        point = document.get("selected_effect_point", {})
        roles = document.get("chronological_roles", {})
        execution = document.get("future_execution_not_authorized_here", {})
        verdicts = document.get("verdicts", {})
        budget = document.get("user_rulings_20260819_binding", {})
        if (
            document.get("schema_version") != "ts-b-holdout-effect-protocol-v1"
            or document.get("status")
            != "RESULT_BLIND_EFFECT_PROTOCOL_FROZEN_PENDING_USER_APPROVAL_AND_ENGINEERING"
            or document.get("production_authorization") != "none"
            or document.get("new_identity") != "TS-B"
            or enabled != {"protocol_and_contract_tests"}
            or authority.get("user_approval_of_this_frozen_protocol_before_engineering")
            != "required"
            or point.get("mechanism") != "BREAKOUT_RETEST"
            or point.get("point_hash") != PARENT_POINT_HASH
            or point.get("sensitivity_neighbours") != "none"
            or point.get("event_subset") != "full_parent_180_holdout_events_no_quality_filter"
            or roles.get("discovery_effect", {}).get("status") != "ABOLISHED_NO_2021_2023_READ"
            or roles.get("current_partial_year", {}).get("role") != "RESERVED_NOT_READ"
            or document.get("attempt_and_firewall", {}).get("discovery_2021_2023_read")
            != "forbidden"
            or document.get("attempt_and_firewall", {}).get(
                "strategy_effect_attempt_count_on_first_effect_read"
            ) != 1
            or budget.get("budget_after_this_protocol") != 0
            or budget.get("on_reject") != "ts_b_closes_and_research_moves_to_next_method"
            or execution.get("docker_network_mode") != "none"
            or execution.get("project_env_or_secret_mount") != "forbidden"
            or verdicts.get("holdout_pass_authorizes_paper_or_production") is not False
            or verdicts.get("production_authorization_for_every_outcome") != "none"
        ):
            raise TSBError("TS-B authority, role, or effect contract differs")
        return cls(document)

    @property
    def selected_point_hashes(self) -> tuple[str, ...]:
        return (self.document["selected_effect_point"]["point_hash"],)

    def candidate_parameters(self) -> dict[str, str]:
        point = self.document["selected_effect_point"]
        return {key: str(value) for key, value in point["parameters"].items()}


def validate_authorized_effect_inputs(scope: TSBScope, root: Path = PROJECT_ROOT) -> None:
    checks: dict[str, str] = {}
    for row in scope.document["predecessors"].values():
        if isinstance(row, dict) and {"path", "sha256"} <= set(row):
            checks[row["path"]] = row["sha256"]
    benchmark = scope.document["benchmark"]
    checks[benchmark["path"]] = benchmark["sha256"]
    lineage = scope.document["ranking_lineage"]
    for row in lineage["clean_m6_lineage"]["reusable_predictions"].values():
        checks[row["path"]] = row["sha256"]
    w7 = lineage["frozen_w7_extension"]
    checks[w7["path"]] = w7["sha256"]
    for relative, expected in checks.items():
        path = root / relative
        if path.is_symlink() or not path.is_file() or sha256_file(path) != expected:
            raise TSBError(f"TS-B bound input differs: {relative}")


def runtime_identity() -> dict[str, str]:
    embedded = os.getenv("SHAIWEI_RELEASE_GIT_HEAD", "").strip().lower()
    if re.fullmatch(r"[0-9a-f]{40}", embedded) is None or git_head() != embedded:
        raise TSBError("TS-B release Git identity differs")
    return {"git_head": embedded, "code_snapshot_sha256": code_snapshot_sha256()}
