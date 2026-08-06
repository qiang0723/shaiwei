"""Load the immutable M5 terminal gate decision for the Web projection."""

from __future__ import annotations

from datetime import datetime
import hashlib
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
import yaml

from shaiwei.web.strategy_factory_contract import (
    SHA256_PATTERN,
    StrategyFactoryCatalog,
    StrategyFactoryContractError,
)


DEFAULT_TRUTH_ADDENDUM = Path("config/m5_strategy_factory_truth_projection_v3.yaml")
BASE_CATALOG = Path("config/m5_strategy_factory_v1.yaml")
COUNT_ADDENDUM = Path("config/m5_strategy_factory_authority_addendum_v2.yaml")


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class FileRef(FrozenModel):
    path: str = Field(pattern=r"^(?:config|docs)/[A-Za-z0-9_.-]+$")
    sha256: str = Field(pattern=SHA256_PATTERN)


class EvidenceRef(FileRef):
    evidence_id: Literal[
        "lineage_release_scope",
        "lineage_real_run_acceptance",
        "platform_route_review",
    ]


class BaseProjection(FrozenModel):
    catalog_path: Literal["config/m5_strategy_factory_v1.yaml"]
    catalog_sha256: str = Field(pattern=SHA256_PATTERN)
    authority_addendum_path: Literal["config/m5_strategy_factory_authority_addendum_v2.yaml"]
    authority_addendum_sha256: str = Field(pattern=SHA256_PATTERN)
    prior_snapshot_id: Literal[
        "fae1c53c410213e58bd10d938a5854afdd2cce1e3f4c9acd7affb73624c94a6b"
    ]
    prior_snapshot_sha256: Literal[
        "36f750639f5643a67ac0c2f9eb7505949542a9404edad9ff3d7fb970f7bd6f2b"
    ]
    preserve_prior_snapshot: Literal[True]


class GateDecision(FrozenModel):
    decision_id: Literal["m5-dynamic-fundamental-lineage-gate-20260806-v1"]
    display_name: Literal["动态基本面跨池研究"]
    family_id: Literal["fundamental_dynamic"]
    universe_ids: tuple[
        Literal["star50-official-pit-v2"],
        Literal["star-board-midcap-pit-v1"],
        Literal["star-board-smallcap-pit-v1"],
    ]
    gate_stage: Literal["SOURCE_LINEAGE_FEASIBILITY"]
    terminal_state: Literal["BLOCKED_DATA"]
    evidence_tier: Literal["LINEAGE_NO_GO_ONLY"]
    verdict: Literal["NO_GO_M5_2_SOURCE_LINEAGE_PREEXECUTION"]
    strategy_effective: Literal["NOT_EVALUATED"]
    effect_read: Literal[False]
    real_gate_run_count: Literal[1]
    conflict_group_count: Literal[23]
    forward_only_group_count: Literal[23]
    pit_resolved_group_count: Literal[0]
    route_status: Literal["PAUSE"]
    blocked_reason: str = Field(min_length=12, max_length=120)
    next_action: str = Field(min_length=12, max_length=120)
    release_scope_sha256: Literal[
        "f7904929991e90a3d4c220cbdaf88818953694803625c41eb3634731e376e2d5"
    ]
    run_id: Literal["8ffe2570e740dd84ce8d3ccfc0f75f429488d201cf0088ef54ba715cc9dd1fab"]
    independent_audit_sha256: Literal[
        "e056e41a3473206ebd806e8b917b33e953210ede4b71e15c3ebdfc009ba2ba45"
    ]
    registry_event_sha256: Literal[
        "9cfc67deb0d199d969a09f08494644b18c0aed72c0ab68ade4c834f19cba38d8"
    ]
    evidence_commit: Literal["fb134b91433003774945ab91f1dba02cf6daad5e"]
    route_review_commit: Literal["e8dab33217fcce7b9a89bd1d1c78727c91051f52"]
    production_authorization: Literal["none"]
    release_consumed: Literal[True]
    active_task: Literal[False]
    evidence_ids: tuple[
        Literal["lineage_release_scope"],
        Literal["lineage_real_run_acceptance"],
        Literal["platform_route_review"],
    ]


class ProjectionInvariants(FrozenModel):
    authority_projection_version: Literal["m5-strategy-factory-authority-projection-v1"]
    prior_registered_program_count: Literal[8]
    active_authorized_task_count: Literal[0]
    formal_factor_admission_count: Literal[0]
    external_calls_made_by_projection: Literal[0]
    production_authorization: Literal["none"]
    bse_count: Literal[0]


class TruthProjectionAddendum(FrozenModel):
    schema_version: Literal["m5-strategy-factory-truth-projection-addendum-v1"]
    addendum_id: Literal["m5-strategy-factory-m5-lineage-no-go-v1"]
    published_at: str
    timezone: Literal["Asia/Shanghai"]
    protocol: FileRef
    base_projection: BaseProjection
    evidence: tuple[EvidenceRef, EvidenceRef, EvidenceRef]
    decision: GateDecision
    invariants: ProjectionInvariants

    @model_validator(mode="after")
    def validate_identity(self) -> "TruthProjectionAddendum":
        try:
            timestamp = datetime.fromisoformat(self.published_at)
        except ValueError as error:
            raise ValueError("truth projection published_at must be ISO 8601") from error
        if timestamp.tzinfo is None:
            raise ValueError("truth projection published_at must include timezone")
        expected = {
            "lineage_release_scope",
            "lineage_real_run_acceptance",
            "platform_route_review",
        }
        if {item.evidence_id for item in self.evidence} != expected:
            raise ValueError("truth projection evidence identity set differs")
        return self


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _safe_file(root: Path, relative: str) -> Path:
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts:
        raise StrategyFactoryContractError(f"truth projection path is not project-relative: {relative}")
    cursor = root
    for part in path.parts:
        cursor /= part
        if cursor.is_symlink():
            raise StrategyFactoryContractError(f"truth projection path contains a symlink: {relative}")
    candidate = cursor.resolve()
    try:
        candidate.relative_to(root)
    except ValueError as error:
        raise StrategyFactoryContractError(f"truth projection path escapes project root: {relative}") from error
    if not candidate.is_file():
        raise StrategyFactoryContractError(f"truth projection file is missing: {relative}")
    return candidate


def load_truth_projection_addendum(
    root: Path,
    catalog: StrategyFactoryCatalog,
    catalog_payload: bytes,
    count_addendum_payload: bytes,
    addendum_path: Path = DEFAULT_TRUTH_ADDENDUM,
) -> tuple[TruthProjectionAddendum, bytes, dict[str, str]]:
    payload = _safe_file(root, str(addendum_path)).read_bytes()
    try:
        addendum = TruthProjectionAddendum.model_validate(yaml.safe_load(payload))
    except (yaml.YAMLError, ValidationError, ValueError) as error:
        raise StrategyFactoryContractError(f"invalid truth projection addendum: {error}") from error

    base = addendum.base_projection
    if Path(base.catalog_path) != BASE_CATALOG or Path(base.authority_addendum_path) != COUNT_ADDENDUM:
        raise StrategyFactoryContractError("truth projection is bound to another base catalog")
    if _sha256(catalog_payload) != base.catalog_sha256:
        raise StrategyFactoryContractError("truth projection base catalog SHA-256 differs")
    if _sha256(count_addendum_payload) != base.authority_addendum_sha256:
        raise StrategyFactoryContractError("truth projection count addendum SHA-256 differs")

    hashes: dict[str, str] = {}
    for reference in (addendum.protocol, *addendum.evidence):
        actual = _sha256(_safe_file(root, reference.path).read_bytes())
        if actual != reference.sha256:
            raise StrategyFactoryContractError(f"truth projection evidence SHA-256 differs: {reference.path}")
        hashes[reference.path] = actual

    family_ids = {item.family_id for item in catalog.research_families}
    universe_ids = {item.universe_id for item in catalog.universes}
    decision = addendum.decision
    if decision.family_id not in family_ids or not set(decision.universe_ids) <= universe_ids:
        raise StrategyFactoryContractError("truth projection decision references an unknown identity")
    invariants = addendum.invariants
    if (
        len(catalog.programs) != invariants.prior_registered_program_count
        or catalog.expected_counts.active_authorized_task_count
        != invariants.active_authorized_task_count
        or catalog.expected_counts.admitted_factor_count != invariants.formal_factor_admission_count
    ):
        raise StrategyFactoryContractError("truth projection base invariants differ")
    return addendum, payload, hashes
