"""Apply append-only authority corrections to the frozen M5 strategy catalog."""

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


DEFAULT_ADDENDUM = Path("config/m5_strategy_factory_authority_addendum_v2.yaml")
BASE_CATALOG = Path("config/m5_strategy_factory_v1.yaml")


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class FileRef(FrozenModel):
    path: str = Field(pattern=r"^(?:config|docs)/[A-Za-z0-9_.-]+$")
    sha256: str = Field(pattern=SHA256_PATTERN)


class BaseCatalogRef(FileRef):
    catalog_id: Literal["m5-strategy-factory-v1"]
    snapshot_id: str = Field(pattern=SHA256_PATTERN)
    snapshot_sha256: str = Field(pattern=SHA256_PATTERN)


class CountCorrection(FrozenModel):
    correction_id: Literal["m3-cross-pool-evaluation-units-24x3"]
    program_id: Literal["m3-custom-pools-price-volume-v1"]
    field: Literal["evaluation_unit_count"]
    prior_value: Literal[24]
    corrected_value: Literal[72]
    evidence: tuple[FileRef, FileRef]

    @model_validator(mode="after")
    def evidence_is_unique(self) -> "CountCorrection":
        if len({item.path for item in self.evidence}) != 2:
            raise ValueError("count correction requires two distinct evidence files")
        return self


class CorrectionInvariants(FrozenModel):
    generation_attempt_count: Literal[24]
    candidate_count: Literal[24]
    effect_test_count: Literal[0]
    related_price_volume_attempt_n: Literal[270]
    strategy_effective: Literal["NOT_EVALUATED"]
    authoritative_outcome: Literal["STOPPED_CONTRACT"]
    production_authorization: Literal["none"]
    external_calls_made: Literal[0]
    real_research_runs: Literal[0]


class AuthorityAddendum(FrozenModel):
    schema_version: Literal["m5-strategy-factory-authority-addendum-v1"]
    addendum_id: Literal["m5-strategy-factory-count-correction-v1"]
    published_at: str
    timezone: Literal["Asia/Shanghai"]
    protocol: FileRef
    base_catalog: BaseCatalogRef
    corrections: tuple[CountCorrection]
    invariants: CorrectionInvariants

    @model_validator(mode="after")
    def timestamp_is_zoned(self) -> "AuthorityAddendum":
        try:
            timestamp = datetime.fromisoformat(self.published_at)
        except ValueError as error:
            raise ValueError("addendum published_at must be ISO 8601") from error
        if timestamp.tzinfo is None:
            raise ValueError("addendum published_at must include timezone")
        return self


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _safe_file(root: Path, relative: str) -> Path:
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts:
        raise StrategyFactoryContractError(f"authority path is not project-relative: {relative}")
    cursor = root
    for part in path.parts:
        cursor /= part
        if cursor.is_symlink():
            raise StrategyFactoryContractError(f"authority path contains a symlink: {relative}")
    candidate = cursor.resolve()
    try:
        candidate.relative_to(root)
    except ValueError as error:
        raise StrategyFactoryContractError(f"authority path escapes project root: {relative}") from error
    if not candidate.is_file():
        raise StrategyFactoryContractError(f"authority file is missing: {relative}")
    return candidate


def apply_authority_addendum(
    root: Path,
    catalog: StrategyFactoryCatalog,
    catalog_payload: bytes,
    addendum_path: Path = DEFAULT_ADDENDUM,
) -> tuple[StrategyFactoryCatalog, bytes, dict[str, str]]:
    path = _safe_file(root, str(addendum_path))
    payload = path.read_bytes()
    try:
        addendum = AuthorityAddendum.model_validate(yaml.safe_load(payload))
    except (yaml.YAMLError, ValidationError, ValueError) as error:
        raise StrategyFactoryContractError(f"invalid strategy-factory authority addendum: {error}") from error

    base = addendum.base_catalog
    if Path(base.path) != BASE_CATALOG or base.catalog_id != catalog.catalog_id:
        raise StrategyFactoryContractError("authority addendum is bound to another base catalog")
    if _sha256(catalog_payload) != base.sha256:
        raise StrategyFactoryContractError("base strategy-factory catalog differs from authority addendum")

    evidence_hashes: dict[str, str] = {}
    for reference in (addendum.protocol, *addendum.corrections[0].evidence):
        actual = _sha256(_safe_file(root, reference.path).read_bytes())
        if actual != reference.sha256:
            raise StrategyFactoryContractError(f"authority evidence SHA-256 differs: {reference.path}")
        evidence_hashes[reference.path] = actual

    correction = addendum.corrections[0]
    programs = list(catalog.programs)
    matches = [index for index, item in enumerate(programs) if item.program_id == correction.program_id]
    if len(matches) != 1:
        raise StrategyFactoryContractError("authority correction target is not unique")
    index = matches[0]
    program = programs[index]
    invariants = addendum.invariants
    actual_invariants = (
        program.generation_attempt_count,
        program.candidate_count,
        program.effect_test_count,
        program.strategy_effective,
        program.authoritative_outcome,
        program.production_authorization,
    )
    expected_invariants = (
        invariants.generation_attempt_count,
        invariants.candidate_count,
        invariants.effect_test_count,
        invariants.strategy_effective,
        invariants.authoritative_outcome,
        invariants.production_authorization,
    )
    if program.evaluation_unit_count != correction.prior_value or actual_invariants != expected_invariants:
        raise StrategyFactoryContractError("authority correction prior state or invariants differ")
    programs[index] = program.model_copy(update={correction.field: correction.corrected_value})
    corrected = catalog.model_copy(update={"published_at": addendum.published_at, "programs": tuple(programs)})
    StrategyFactoryCatalog.model_validate(corrected.model_dump(mode="json"))
    return corrected, payload, evidence_hashes
