"""Mechanism-specific TS-v5 proposal projection and deterministic compiler."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
import re
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
import yaml

from shaiwei.config import PROJECT_ROOT
from shaiwei.research.provider_contract import D1ControlError
from shaiwei.research.trend_swing.v5_contract import (
    V5Bundle,
    canonical_json,
    sha256_file,
    sha256_text,
)
from shaiwei.research.trend_swing.v5_models import (
    ARCHETYPE_CONTRACT,
    COMMON_FEATURES,
    FORBIDDEN_TEXT,
    MECHANISM_FEATURES,
    PARAMETER_BOUNDS,
    SAFE_TEXT,
    CancellationRule,
    CandidateLineage,
    Confirmation,
    Mechanism,
    MechanismCandidate,
    ParameterId,
    ParameterSlot,
)

CONTRACT_PATH = PROJECT_ROOT / "config/ts_v5_mechanism_proposal_v2.yaml"
CONTRACT_SHA256 = "538326777bdeb3c0793e729b1c4dc086b804e07743aca8adba7e9f251e9b09a0"
STRICT = ConfigDict(extra="forbid")
MANDATORY_CANCELLATIONS = (
    CancellationRule.STRUCTURE_LOW_BROKEN,
    CancellationRule.MARKET_OR_SECTOR_GATE_LOST,
)
OPTIONAL_CANCELLATIONS = tuple(
    item for item in CancellationRule if item not in MANDATORY_CANCELLATIONS
)
SHARED_PARAMETERS = (
    ParameterId.RECOVERY_CONFIRMATION_DAYS,
    ParameterId.MAXIMUM_WAIT_DAYS,
)
NUMERIC_STRING_PATTERN = r"-?(?:0|[1-9]\d*)(?:\.\d{1,6})?"


class ProposalParameterSlot(BaseModel):
    model_config = STRICT

    parameter_id: ParameterId
    value_type: Literal["INTEGER", "DECIMAL"]
    minimum: str
    maximum: str
    search_points_maximum: Annotated[int, Field(ge=2, le=7)]

    def as_candidate_slot(self) -> ParameterSlot:
        return ParameterSlot.model_validate(self.model_dump(mode="json"))


class MechanismProposalBase(BaseModel):
    model_config = STRICT

    schema_version: Literal["ts-v5-mechanism-proposal-v2"]
    hypothesis: Annotated[str, Field(min_length=20, max_length=500)]
    economic_rationale_draft: Annotated[str, Field(min_length=20, max_length=800)]
    change_summary: Annotated[str, Field(min_length=10, max_length=300)]
    recovery_confirmation: Confirmation
    optional_cancellation_rules: Annotated[
        list[CancellationRule], Field(max_length=len(OPTIONAL_CANCELLATIONS))
    ]
    parameter_slots: Annotated[list[ProposalParameterSlot], Field(min_length=1, max_length=5)]
    falsification_conditions: Annotated[list[str], Field(min_length=2, max_length=5)]
    lineage: CandidateLineage

    @field_validator("hypothesis", "economic_rationale_draft", "change_summary")
    @classmethod
    def validate_text(cls, value: str) -> str:
        if not SAFE_TEXT.fullmatch(value) or FORBIDDEN_TEXT.search(value):
            raise ValueError("proposal text contains a prohibited value")
        return value

    @field_validator("falsification_conditions")
    @classmethod
    def validate_falsification(cls, values: list[str]) -> list[str]:
        if len(set(values)) != len(values) or any(
            not SAFE_TEXT.fullmatch(value) or FORBIDDEN_TEXT.search(value) for value in values
        ):
            raise ValueError("proposal falsification conditions are unsafe or duplicated")
        return values

    @field_validator("optional_cancellation_rules")
    @classmethod
    def validate_optional_cancellations(
        cls, values: list[CancellationRule]
    ) -> list[CancellationRule]:
        if len(set(values)) != len(values) or any(item not in OPTIONAL_CANCELLATIONS for item in values):
            raise ValueError("proposal cancellation rules are not optional or unique")
        return values

    @model_validator(mode="after")
    def validate_parameter_uniqueness_and_product(self) -> "MechanismProposalBase":
        ids = [item.parameter_id for item in self.parameter_slots]
        if len(set(ids)) != len(ids):
            raise ValueError("proposal parameter slots must be unique")
        product = 1
        for item in self.parameter_slots:
            product *= item.search_points_maximum
        if product > 196:
            raise ValueError("proposal parameter search exceeds 196 evaluations")
        return self


@dataclass(frozen=True)
class ProposalContract:
    document: dict[str, Any]
    sha256: str
    system_prompt: str

    @classmethod
    def load(cls, path: Path = CONTRACT_PATH) -> "ProposalContract":
        if path.is_symlink() or sha256_file(path) != CONTRACT_SHA256:
            raise D1ControlError("TS-v5 proposal contract identity differs")
        try:
            document = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            raise D1ControlError("TS-v5 proposal contract is invalid") from exc
        authority = document.get("authority", {}) if isinstance(document, dict) else {}
        profile = document.get("response_profile", {}) if isinstance(document, dict) else {}
        if (
            not isinstance(document, dict)
            or document.get("schema_version") != "ts-v5-mechanism-proposal-contract-v2"
            or document.get("status") != "ENGINEERING_ONLY_NO_LIVE_AUTHORITY"
            or authority.get("external_api_calls") != 0
            or authority.get("future_live_calls_require_new_scope_release_and_user_approval") is not True
            or authority.get("production_authorization") != "none"
            or profile != {
                "thinking": "disabled", "reasoning_effort": "omitted",
                "response_format": "json_object", "maximum_output_tokens": 1800,
                "tools": False, "stream": False,
            }
        ):
            raise D1ControlError("TS-v5 proposal contract authority differs")
        prompt = document.get("system_prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            raise D1ControlError("TS-v5 proposal system prompt is missing")
        return cls(document, CONTRACT_SHA256, prompt)


def allowed_parameter_ids(mechanism: Mechanism) -> tuple[ParameterId, ...]:
    mandatory = sorted(ARCHETYPE_CONTRACT[mechanism][2], key=lambda item: item.value)
    return tuple([*mandatory, *SHARED_PARAMETERS])


def proposal_model(mechanism: Mechanism) -> type[MechanismProposalBase]:
    """Create a strict mechanism-bound model while retaining a single validator source."""
    allowed = set(allowed_parameter_ids(mechanism))

    class BoundProposal(MechanismProposalBase):
        @model_validator(mode="after")
        def validate_mechanism_parameters(self) -> "BoundProposal":
            ids = {item.parameter_id for item in self.parameter_slots}
            mandatory = ARCHETYPE_CONTRACT[mechanism][2]
            if not mandatory.issubset(ids) or not ids.issubset(allowed):
                raise ValueError("proposal parameter ids differ from the mechanism projection")
            return self

    BoundProposal.__name__ = f"{mechanism.value.title().replace('_', '')}Proposal"
    return BoundProposal


def mechanism_projection(mechanism: Mechanism) -> dict[str, Any]:
    reference, measure, mandatory = ARCHETYPE_CONTRACT[mechanism]
    parameters = []
    for parameter in allowed_parameter_ids(mechanism):
        minimum, maximum, value_type = PARAMETER_BOUNDS[parameter]
        parameters.append({
            "parameter_id": parameter.value,
            "required": parameter in mandatory,
            "value_type": value_type,
            "minimum_inclusive": str(minimum),
            "maximum_inclusive": str(maximum),
            "search_points_minimum": 2,
            "search_points_maximum": 7,
        })
    required_features = sorted(
        (COMMON_FEATURES | MECHANISM_FEATURES[mechanism]), key=lambda item: item.value
    )
    return {
        "schema_version": "ts-v5-mechanism-projection-v2",
        "primary_mechanism": mechanism.value,
        "deterministic_reference_frame": reference.value,
        "deterministic_pullback_measure": measure.value,
        "deterministic_mandatory_cancellation_rules": [item.value for item in MANDATORY_CANCELLATIONS],
        "optional_cancellation_rule_enum": [item.value for item in OPTIONAL_CANCELLATIONS],
        "deterministic_required_features": [item.value for item in required_features],
        "mandatory_parameter_ids": sorted(item.value for item in mandatory),
        "optional_parameter_ids": [item.value for item in SHARED_PARAMETERS],
        "parameter_contracts": parameters,
        "maximum_search_evaluations": 196,
        "parameter_slots_must_be_unique": True,
        "parameter_minimum_must_be_less_than_maximum": True,
        "integer_parameter_bounds_must_be_integral": True,
        "numeric_string_pattern": NUMERIC_STRING_PATTERN,
        "optional_cancellation_rules_must_be_unique": True,
        "falsification_conditions_must_be_unique": True,
        "lineage_contract": {
            "INDEPENDENT_parent_count": 0,
            "ADVERSARIAL_REVISION_parent_count": 1,
            "parent_fingerprint_pattern": "^[0-9a-f]{64}$",
        },
        "prohibited_text_categories": [
            "code_or_shell_or_sql",
            "url_or_local_path",
            "secret_shaped_value",
            "validated_profit_or_production_claim",
        ],
    }


def proposal_schema(mechanism: Mechanism) -> dict[str, Any]:
    schema = proposal_model(mechanism).model_json_schema()
    parameter_definition = schema["$defs"]["ProposalParameterSlot"]
    parameter_definition["properties"]["parameter_id"] = {
        "enum": [item.value for item in allowed_parameter_ids(mechanism)], "type": "string"
    }
    optional_definition = schema["properties"]["optional_cancellation_rules"]["items"]
    if "$ref" in optional_definition:
        schema["properties"]["optional_cancellation_rules"]["items"] = {
            "enum": [item.value for item in OPTIONAL_CANCELLATIONS], "type": "string"
        }
    schema["x-ts-mechanism-projection"] = mechanism_projection(mechanism)
    schema["x-ts-text-contract"] = {
        "safe_text_pattern": SAFE_TEXT.pattern,
        "forbidden_pattern": FORBIDDEN_TEXT.pattern,
        "falsification_conditions_must_be_unique": True,
    }
    return schema


def _validate_parameter_projection(
    mechanism: Mechanism, slots: list[ProposalParameterSlot]
) -> None:
    contracts = {
        row["parameter_id"]: row for row in mechanism_projection(mechanism)["parameter_contracts"]
    }
    for slot in slots:
        contract = contracts.get(slot.parameter_id.value)
        if contract is None:
            raise D1ControlError("TS-v5 proposal contains a cross-mechanism parameter")
        try:
            candidate = slot.as_candidate_slot()
        except ValueError as exc:
            raise D1ControlError("TS-v5 proposal parameter is outside the frozen safe range") from exc
        if (
            candidate.value_type != contract["value_type"]
            or Decimal(candidate.minimum) < Decimal(contract["minimum_inclusive"])
            or Decimal(candidate.maximum) > Decimal(contract["maximum_inclusive"])
        ):
            raise D1ControlError("TS-v5 proposal parameter differs from its visible projection")


def compile_proposal(mechanism: Mechanism, document: dict[str, Any]) -> MechanismCandidate:
    """Compile bounded research choices into the original frozen candidate contract."""
    model = proposal_model(mechanism)
    try:
        proposal = model.model_validate(document)
    except ValueError as exc:
        raise D1ControlError("TS-v5 proposal violates its mechanism-specific contract") from exc
    _validate_parameter_projection(mechanism, proposal.parameter_slots)
    reference, measure, _ = ARCHETYPE_CONTRACT[mechanism]
    cancellations = [*MANDATORY_CANCELLATIONS, *proposal.optional_cancellation_rules]
    features = sorted(COMMON_FEATURES | MECHANISM_FEATURES[mechanism], key=lambda item: item.value)
    candidate = {
        "schema_version": "ts-v5-mechanism-candidate-v1",
        "primary_mechanism": mechanism.value,
        "hypothesis": proposal.hypothesis,
        "economic_rationale_draft": proposal.economic_rationale_draft,
        "change_summary": proposal.change_summary,
        "entry_design": {
            "reference_frame": reference.value,
            "pullback_measure": measure.value,
            "recovery_confirmation": proposal.recovery_confirmation.value,
            "cancellation_rules": [item.value for item in cancellations],
        },
        "parameter_slots": [item.model_dump(mode="json") for item in proposal.parameter_slots],
        "required_features": [item.value for item in features],
        "falsification_conditions": proposal.falsification_conditions,
        "lineage": proposal.lineage.model_dump(mode="json"),
    }
    return MechanismCandidate.model_validate(candidate)


def build_request_v3(
    mechanism: Mechanism, *, attempt_id: str, ordinal: int,
    contract: ProposalContract | None = None,
) -> dict[str, Any]:
    active = contract or ProposalContract.load()
    bundle = V5Bundle.load()
    task = {
        "attempt_id": attempt_id,
        "ordinal": ordinal,
        "proposal_schema": proposal_schema(mechanism),
        "mechanism_projection": mechanism_projection(mechanism),
        "product_constraints": bundle.governance["product_constraints"],
        "public_knowledge_summary": bundle.prompt["public_knowledge_summary"],
        "frozen_failure_memory": bundle.prompt["frozen_failure_memory"],
        "instructions": {
            "return_one_json_object_only": True,
            "do_not_emit_deterministic_fields": True,
            "maximum_search_evaluations": 196,
            "no_performance_or_production_claim": True,
        },
    }
    request = {
        "model": "deepseek-v4-pro",
        "messages": [
            {"role": "system", "content": active.system_prompt},
            {"role": "user", "content": canonical_json(task)},
        ],
        "thinking": {"type": "disabled"},
        "response_format": {"type": "json_object"},
        "max_tokens": 1800,
        "tools": [],
        "stream": False,
    }
    serialized = canonical_json(request)
    if re.search(r"\b\d{6}\.(?:SH|SZ|BJ)\b|/(?:Users|private|workspace)/|sk-[A-Za-z0-9]", serialized):
        raise D1ControlError("TS-v5 proposal request contains a forbidden identity")
    if len(serialized.encode("utf-8")) > 48_000:
        raise D1ControlError("TS-v5 proposal request exceeds its byte bound")
    return request


def projection_bundle_identity() -> dict[str, Any]:
    projections = [mechanism_projection(mechanism) for mechanism in Mechanism]
    schemas = [proposal_schema(mechanism) for mechanism in Mechanism]
    return {
        "proposal_contract_sha256": CONTRACT_SHA256,
        "projection_bundle_sha256": sha256_text(canonical_json(projections)),
        "schema_bundle_sha256": sha256_text(canonical_json(schemas)),
        "mechanism_count": len(projections),
    }
