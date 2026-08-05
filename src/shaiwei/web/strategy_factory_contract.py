"""Strict M5-0 catalog and projection contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


SHA256_PATTERN = r"^[0-9a-f]{64}$"
ID_PATTERN = r"^[a-z0-9][a-z0-9-]{2,127}$"
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


class StrategyFactoryContractError(RuntimeError):
    """The frozen catalog or its evidence violates the M5-0 contract."""


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class ProtocolRef(FrozenModel):
    protocol_id: Literal["m5-strategy-factory-contract-v1"]
    path: str = Field(pattern=r"^docs/[A-Za-z0-9_.-]+$")
    sha256: str = Field(pattern=SHA256_PATTERN)


class Capabilities(FrozenModel):
    mode: Literal["LOCAL_READ_ONLY_DRAFTING"]
    write_api_authorized: Literal[False]
    real_research_authorized: Literal[False]
    external_calls_authorized: Literal[False]
    deepseek_authorized: Literal[False]
    model_training_authorized: Literal[False]
    backtest_authorized: Literal[False]
    forward_authorized: Literal[False]
    new_production_authorized: Literal[False]
    production_authorization: Literal["none"]
    active_authorized_task_count: Literal[0]


class ExpectedCounts(FrozenModel):
    registered_universe_count: Literal[8]
    research_eligible_universe_count: Literal[5]
    blocked_universe_count: Literal[3]
    existing_production_strategy_count: Literal[1]
    admitted_factor_count: Literal[0]
    active_authorized_task_count: Literal[0]
    registered_program_count: Literal[8]


class EvidenceSource(FrozenModel):
    evidence_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_]{2,63}$")
    path: str = Field(pattern=r"^(?:config|docs|ledger)/[A-Za-z0-9_.-]+$")
    sha256: str = Field(pattern=SHA256_PATTERN)


class ResearchFamily(FrozenModel):
    family_id: Literal[
        "baseline_model",
        "moneyflow",
        "fundamental_static",
        "fundamental_dynamic",
        "price_volume",
        "residual_risk",
    ]
    display_name: str = Field(min_length=2, max_length=40)
    draft_eligible: bool


class UniverseView(FrozenModel):
    universe_id: str = Field(pattern=ID_PATTERN)
    display_name: str = Field(min_length=2, max_length=80)
    identity_kind: Literal["OFFICIAL_INDEX", "CUSTOM_RULE_BASED"]
    official_index_code: str | None = Field(default=None, pattern=r"^[0-9]{6}\.SH$")
    data_status: Literal["READY", "BLOCKED_OFFICIAL_LINEAGE", "DATA_GATE_REQUIRED"]
    evidence_tier: Literal[
        "PRODUCTION_CURRENT",
        "HISTORICAL_EFFECT_AUDITED",
        "SOURCE_GO_ONLY",
        "SECONDARY_SOURCE_GO_ONLY",
        "PROTOCOL_ONLY",
        "DISCOVERY_ONLY",
    ]
    authoritative_outcome: Literal[
        "PRODUCTION_CURRENT_EXISTING",
        "REJECT_CURRENT_PROGRAMS",
        "NOT_EVALUATED",
        "STOPPED_CONTRACT",
    ]
    research_draft_eligible: bool
    existing_production: bool
    allowed_action: Literal[
        "CREATE_RESEARCH_DRAFT",
        "FREEZE_DATA_RECOVERY_PROTOCOL",
        "WAIT_AUTHORIZED_LINEAGE_SOURCE",
        "FREEZE_DATA_FEASIBILITY_PROTOCOL",
    ]
    blocker: str | None = Field(default=None, max_length=120)
    evidence_ids: tuple[str, ...] = Field(min_length=1, max_length=8)

    @model_validator(mode="after")
    def validate_identity_and_state(self) -> "UniverseView":
        if self.identity_kind == "OFFICIAL_INDEX":
            if self.official_index_code is None:
                raise ValueError("official universe requires an index code")
        elif self.official_index_code is not None:
            raise ValueError("custom universe cannot claim an official index code")
        if self.research_draft_eligible != (self.data_status == "READY"):
            raise ValueError("draft eligibility must match READY data status")
        if self.research_draft_eligible != (self.allowed_action == "CREATE_RESEARCH_DRAFT"):
            raise ValueError("allowed action conflicts with draft eligibility")
        if (self.blocker is None) != self.research_draft_eligible:
            raise ValueError("blocked universes require a blocker and eligible universes do not")
        return self


class ResearchProgram(FrozenModel):
    program_id: str = Field(pattern=ID_PATTERN)
    display_name: str = Field(min_length=2, max_length=80)
    family_id: str
    universe_ids: tuple[str, ...] = Field(min_length=1, max_length=8)
    lifecycle_state: Literal["CLOSED", "STOPPED_CONTRACT"]
    evidence_tier: Literal["PRODUCTION_CURRENT", "HISTORICAL_EFFECT_AUDITED", "DISCOVERY_ONLY"]
    authoritative_outcome: Literal["PRODUCTION_CURRENT_EXISTING", "REJECT", "STOPPED_CONTRACT"]
    strategy_effective: Literal["EXISTING_PRODUCTION_BASELINE", "REJECT", "NOT_EVALUATED"]
    generation_attempt_count: int = Field(ge=0, le=100_000)
    evaluation_unit_count: int = Field(ge=0, le=100_000)
    effect_test_count: int = Field(ge=0, le=100_000)
    candidate_count: int = Field(ge=0, le=100_000)
    production_authorization: Literal["none", "production_current"]
    summary: str = Field(min_length=4, max_length=200)
    next_action: str = Field(min_length=4, max_length=160)
    evidence_ids: tuple[str, ...] = Field(min_length=1, max_length=5)

    @model_validator(mode="after")
    def validate_program_state(self) -> "ResearchProgram":
        if self.effect_test_count > self.evaluation_unit_count:
            raise ValueError("effect tests cannot exceed evaluation units")
        if self.lifecycle_state == "STOPPED_CONTRACT":
            if self.authoritative_outcome != "STOPPED_CONTRACT" or self.strategy_effective != "NOT_EVALUATED":
                raise ValueError("stopped program must remain not evaluated")
        if self.production_authorization == "production_current":
            if self.authoritative_outcome != "PRODUCTION_CURRENT_EXISTING":
                raise ValueError("production authority only belongs to the existing baseline")
        return self


class DraftTemplate(FrozenModel):
    template_id: Literal["bounded-research-draft-v1"]
    display_name: str
    status: Literal["DRAFT_NOT_SUBMITTED"]
    eligible_universe_ids: tuple[str, ...] = Field(min_length=1, max_length=8)
    eligible_family_ids: tuple[str, ...] = Field(min_length=1, max_length=8)
    maximum_universe_count: int = Field(ge=1, le=3)
    maximum_candidate_count: int = Field(ge=1, le=24)
    external_call_authorization: Literal["NOT_GRANTED"]
    sealed_effect_authorization: Literal["NOT_GRANTED"]
    production_authorization: Literal["none"]
    disclaimer: str = Field(min_length=10, max_length=160)


class StrategyFactoryCatalog(FrozenModel):
    schema_version: Literal["m5-strategy-factory-catalog-v1"]
    catalog_id: Literal["m5-strategy-factory-v1"]
    published_at: str
    timezone: Literal["Asia/Shanghai"]
    protocol: ProtocolRef
    capabilities: Capabilities
    expected_counts: ExpectedCounts
    evidence_sources: tuple[EvidenceSource, ...] = Field(min_length=1, max_length=32)
    research_families: tuple[ResearchFamily, ...] = Field(min_length=1, max_length=16)
    universes: tuple[UniverseView, ...] = Field(min_length=1, max_length=16)
    programs: tuple[ResearchProgram, ...] = Field(min_length=1, max_length=32)
    draft_template: DraftTemplate

    @model_validator(mode="after")
    def validate_catalog(self) -> "StrategyFactoryCatalog":
        try:
            timestamp = datetime.fromisoformat(self.published_at)
        except ValueError as error:
            raise ValueError("published_at must be ISO 8601") from error
        if timestamp.tzinfo is None:
            raise ValueError("published_at must include a timezone")

        source_ids = [item.evidence_id for item in self.evidence_sources]
        source_paths = [item.path for item in self.evidence_sources]
        universe_ids = [item.universe_id for item in self.universes]
        program_ids = [item.program_id for item in self.programs]
        family_ids = [item.family_id for item in self.research_families]
        for values, label in (
            (source_ids, "evidence IDs"),
            (source_paths, "evidence paths"),
            (universe_ids, "universe IDs"),
            (program_ids, "program IDs"),
            (family_ids, "family IDs"),
        ):
            if len(values) != len(set(values)):
                raise ValueError(f"catalog repeats {label}")
        if set(universe_ids) != EXPECTED_UNIVERSE_IDS:
            raise ValueError("catalog universe identity set differs from frozen M1")

        source_set, universe_set, family_set = set(source_ids), set(universe_ids), set(family_ids)
        for universe in self.universes:
            if not set(universe.evidence_ids) <= source_set:
                raise ValueError(f"unknown universe evidence: {universe.universe_id}")
        for program in self.programs:
            if program.family_id not in family_set or not set(program.universe_ids) <= universe_set:
                raise ValueError(f"unknown program identity: {program.program_id}")
            if not set(program.evidence_ids) <= source_set:
                raise ValueError(f"unknown program evidence: {program.program_id}")

        eligible = {item.universe_id for item in self.universes if item.research_draft_eligible}
        if set(self.draft_template.eligible_universe_ids) != eligible:
            raise ValueError("draft eligible universes differ from the current authority overlay")
        draft_families = {item.family_id for item in self.research_families if item.draft_eligible}
        if set(self.draft_template.eligible_family_ids) != draft_families:
            raise ValueError("draft families differ from the frozen family registry")
        counts = self.expected_counts
        actual = (
            len(self.universes),
            len(eligible),
            sum(not item.research_draft_eligible for item in self.universes),
            sum(item.existing_production for item in self.universes),
            len(self.programs),
        )
        expected = (
            counts.registered_universe_count,
            counts.research_eligible_universe_count,
            counts.blocked_universe_count,
            counts.existing_production_strategy_count,
            counts.registered_program_count,
        )
        if actual != expected:
            raise ValueError("catalog counts differ from the frozen expected counts")
        return self


class StrategyFactoryPointer(FrozenModel):
    schema_version: Literal["m5-strategy-factory-pointer-v1"]
    protocol_id: Literal["m5-strategy-factory-contract-v1"]
    snapshot_id: str = Field(pattern=SHA256_PATTERN)
    snapshot_path: str = Field(pattern=r"^snapshots/[0-9a-f]{64}\.json$")
    snapshot_sha256: str = Field(pattern=SHA256_PATTERN)
