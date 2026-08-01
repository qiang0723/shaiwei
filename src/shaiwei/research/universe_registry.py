"""Strict, read-only registry for multi-universe factor research boundaries."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_REGISTRY_PATH = PROJECT_ROOT / "config/m1_multi_universe_v1.yaml"

IdentityKind = Literal["OFFICIAL_INDEX", "CUSTOM_RULE_BASED"]
PitStatus = Literal[
    "READY",
    "BLOCKED_OFFICIAL_LINEAGE",
    "DATA_GATE_REQUIRED",
    "RULES_NOT_FROZEN",
]
Permission = Literal[
    "CONTINUE_EXISTING_PRODUCTION",
    "FREEZE_NEW_FACTOR_PROTOCOL",
    "FREEZE_DATA_RECOVERY_PROTOCOL",
    "FREEZE_DATA_FEASIBILITY_PROTOCOL",
    "FREEZE_RULE_DESIGN_PROTOCOL",
]

EXPECTED_UNIVERSE_IDS = {
    "csi800-pit-v1",
    "star50-official-pit-v2",
    "star100-official-pit-v1",
    "star200-official-pit-v1",
    "star-composite-official-v1",
    "star-board-all-pit-v1",
    "star-board-midcap-pit-v1",
    "star-board-smallcap-pit-v1",
}
EXPECTED_EVALUATION_FIELDS = (
    "factor_id",
    "factor_version",
    "universe_id",
    "benchmark_id",
    "label_id",
    "horizon_id",
    "neutralization_id",
    "window_set_id",
    "cost_policy_id",
    "decision_rule_version",
)
EXPECTED_GATE_FAMILIES = (
    "PIT",
    "COVERAGE",
    "RANK_IC",
    "STABILITY",
    "TURNOVER",
    "COST",
    "CAPACITY",
    "STRESS",
    "MULTIPLE_TESTING",
)


class UniverseRegistryError(RuntimeError):
    """The frozen registry or requested use violates an M1-0 boundary."""


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class EvaluationContract(FrozenModel):
    factor_identity_scope: Literal["GLOBAL_EXACT_DEFINITION"]
    admission_scope: Literal["UNIVERSE_SPECIFIC"]
    target_universes_frozen_before_results: Literal[True]
    generated_attempt_count_scope: Literal["GLOBAL_PER_COMPLETED_RESPONSE"]
    evaluation_cells_are_independent_generation_attempts: Literal[False]
    new_universe_after_results_requires_new_protocol: Literal[True]
    identity_fields: tuple[str, ...]
    required_gate_families: tuple[str, ...]

    @model_validator(mode="after")
    def validate_frozen_contract(self) -> "EvaluationContract":
        if self.identity_fields != EXPECTED_EVALUATION_FIELDS:
            raise ValueError("evaluation identity fields differ from the frozen ordered contract")
        if self.required_gate_families != EXPECTED_GATE_FAMILIES:
            raise ValueError("required gate families differ from the frozen ordered contract")
        return self


class NextProtocolCandidate(FrozenModel):
    universe_id: Literal["star50-official-pit-v2"]
    stage: Literal["FREEZE_NEW_FACTOR_PROTOCOL_ONLY"]
    factor_results_authorized: Literal[False]
    llm_execution_authorized: Literal[False]
    model_training_authorized: Literal[False]
    production_authorization: Literal["none"]


class UniverseDefinition(FrozenModel):
    universe_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{2,63}$")
    display_name: str = Field(min_length=1, max_length=80)
    identity_kind: IdentityKind
    official_index_code: str | None = Field(default=None, pattern=r"^[0-9]{6}\.SH$")
    segment: Literal["broad_large_mid", "star_large", "star_mid", "star_small", "star_all"]
    pit_status: PitStatus
    evidence_status: str = Field(pattern=r"^[A-Z][A-Z0-9_]{2,95}$")
    evidence_documents: tuple[str, ...] = Field(min_length=1, max_length=8)
    permissions: frozenset[Permission] = Field(min_length=1, max_length=2)
    bse_included: Literal[False]

    @model_validator(mode="after")
    def validate_identity_and_permissions(self) -> "UniverseDefinition":
        if self.identity_kind == "OFFICIAL_INDEX":
            if self.official_index_code is None:
                raise ValueError("official universes require an official index code")
        else:
            if self.official_index_code is not None:
                raise ValueError("custom rule-based universes cannot claim an official index code")
            if "指数" in self.display_name:
                raise ValueError("custom rule-based universes cannot use an official index label")

        expected: frozenset[str]
        if self.pit_status == "READY":
            expected = frozenset({"FREEZE_NEW_FACTOR_PROTOCOL"})
            if self.universe_id == "csi800-pit-v1":
                expected |= {"CONTINUE_EXISTING_PRODUCTION"}
        elif self.pit_status == "BLOCKED_OFFICIAL_LINEAGE":
            expected = frozenset({"FREEZE_DATA_RECOVERY_PROTOCOL"})
        elif self.pit_status == "DATA_GATE_REQUIRED":
            expected = frozenset({"FREEZE_DATA_FEASIBILITY_PROTOCOL"})
        else:
            expected = frozenset({"FREEZE_RULE_DESIGN_PROTOCOL"})
        if self.permissions != expected:
            raise ValueError(
                f"permissions for {self.universe_id} do not match PIT status {self.pit_status}"
            )
        return self


class UniverseRegistry(FrozenModel):
    schema_version: Literal["m1-multi-universe-registry-v1"]
    protocol_id: Literal["m1-multi-universe-foundation-v1"]
    protocol_document: str
    protocol_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    protocol_git_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    factor_results_inspected: Literal[False]
    llm_execution_authorized: Literal[False]
    new_production_authorized: Literal[False]
    production_authorization: Literal["none"]
    scheduler_changes_authorized: Literal[False]
    existing_production_universe_id: Literal["csi800-pit-v1"]
    evaluation_contract: EvaluationContract
    next_protocol_candidate: NextProtocolCandidate
    universes: tuple[UniverseDefinition, ...] = Field(min_length=1, max_length=16)

    @model_validator(mode="after")
    def validate_registry_topology(self) -> "UniverseRegistry":
        ids = [item.universe_id for item in self.universes]
        if len(ids) != len(set(ids)):
            raise ValueError("universe registry contains duplicate universe IDs")
        if set(ids) != EXPECTED_UNIVERSE_IDS:
            raise ValueError("universe registry differs from the frozen M1-0 identity set")

        official_codes = [
            item.official_index_code
            for item in self.universes
            if item.official_index_code is not None
        ]
        if len(official_codes) != len(set(official_codes)):
            raise ValueError("universe registry contains duplicate official index codes")

        production = [
            item.universe_id
            for item in self.universes
            if "CONTINUE_EXISTING_PRODUCTION" in item.permissions
        ]
        if production != [self.existing_production_universe_id]:
            raise ValueError("only the frozen CSI800 universe may retain existing production use")

        factor_protocol_eligible = {
            item.universe_id
            for item in self.universes
            if "FREEZE_NEW_FACTOR_PROTOCOL" in item.permissions
        }
        if factor_protocol_eligible != {"csi800-pit-v1", "star50-official-pit-v2"}:
            raise ValueError("factor-protocol eligibility differs from the frozen M1-0 boundary")
        return self

    def universe(self, universe_id: str) -> UniverseDefinition:
        for item in self.universes:
            if item.universe_id == universe_id:
                return item
        raise UniverseRegistryError(f"unregistered universe: {universe_id}")


class FactorEvaluationIdentity(FrozenModel):
    factor_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    factor_version: str = Field(min_length=1, max_length=128)
    universe_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{2,63}$")
    benchmark_id: str = Field(min_length=1, max_length=128)
    label_id: str = Field(min_length=1, max_length=256)
    horizon_id: str = Field(min_length=1, max_length=128)
    neutralization_id: str = Field(min_length=1, max_length=128)
    window_set_id: str = Field(min_length=1, max_length=128)
    cost_policy_id: str = Field(min_length=1, max_length=128)
    decision_rule_version: str = Field(min_length=1, max_length=128)


def _canonical_value(value: object) -> object:
    if isinstance(value, dict):
        return {str(key): _canonical_value(item) for key, item in value.items()}
    if isinstance(value, (set, frozenset)):
        return sorted(_canonical_value(item) for item in value)
    if isinstance(value, (list, tuple)):
        return [_canonical_value(item) for item in value]
    return value


def _canonical_payload(registry: UniverseRegistry) -> bytes:
    return json.dumps(
        _canonical_value(registry.model_dump(mode="python")),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def registry_sha256(registry: UniverseRegistry) -> str:
    return hashlib.sha256(_canonical_payload(registry)).hexdigest()


def _project_file(project_root: Path, relative: str) -> Path:
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts:
        raise UniverseRegistryError(f"registry evidence path is not project-relative: {relative}")
    root = project_root.resolve()
    candidate = (root / path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as error:
        raise UniverseRegistryError(f"registry evidence path escapes project root: {relative}") from error
    if not candidate.is_file():
        raise UniverseRegistryError(f"registry evidence file is missing: {relative}")
    return candidate


def load_registry(
    path: Path = DEFAULT_REGISTRY_PATH,
    *,
    project_root: Path = PROJECT_ROOT,
) -> UniverseRegistry:
    if not path.is_file():
        raise UniverseRegistryError(f"multi-universe registry is missing: {path}")
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        registry = UniverseRegistry.model_validate(document)
    except (OSError, yaml.YAMLError, ValueError) as error:
        raise UniverseRegistryError(f"invalid multi-universe registry: {error}") from error

    protocol_path = _project_file(project_root, registry.protocol_document)
    actual_protocol_sha256 = hashlib.sha256(protocol_path.read_bytes()).hexdigest()
    if actual_protocol_sha256 != registry.protocol_sha256:
        raise UniverseRegistryError("multi-universe protocol hash differs from the registry")
    for universe in registry.universes:
        if len(universe.evidence_documents) != len(set(universe.evidence_documents)):
            raise UniverseRegistryError(
                f"universe {universe.universe_id} repeats an evidence document"
            )
        for relative in universe.evidence_documents:
            _project_file(project_root, relative)
    return registry


def validate_evaluation_identity(
    registry: UniverseRegistry,
    payload: dict[str, object],
) -> FactorEvaluationIdentity:
    identity = FactorEvaluationIdentity.model_validate(payload)
    universe = registry.universe(identity.universe_id)
    if "FREEZE_NEW_FACTOR_PROTOCOL" not in universe.permissions:
        raise UniverseRegistryError(
            f"universe {identity.universe_id} is not eligible for a new factor protocol"
        )
    return identity


def validation_summary(registry: UniverseRegistry) -> dict[str, object]:
    return {
        "schema_version": "m1-multi-universe-validation-v1",
        "protocol_id": registry.protocol_id,
        "registry_sha256": registry_sha256(registry),
        "universe_count": len(registry.universes),
        "existing_production_universe_id": registry.existing_production_universe_id,
        "factor_protocol_eligible": sorted(
            item.universe_id
            for item in registry.universes
            if "FREEZE_NEW_FACTOR_PROTOCOL" in item.permissions
        ),
        "data_or_rule_gate_only": sorted(
            item.universe_id for item in registry.universes if item.pit_status != "READY"
        ),
        "factor_results_inspected": registry.factor_results_inspected,
        "llm_execution_authorized": registry.llm_execution_authorized,
        "new_production_authorized": registry.new_production_authorized,
        "production_authorization": registry.production_authorization,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate the frozen M1-0 universe registry")
    parser.add_argument("--config", type=Path, default=DEFAULT_REGISTRY_PATH)
    args = parser.parse_args()
    registry = load_registry(args.config)
    print(json.dumps(validation_summary(registry), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
