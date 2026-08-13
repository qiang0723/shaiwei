"""Versioned TS-v5 proposal contract with locally bound authority and search budget."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
import yaml

from shaiwei.config import PROJECT_ROOT
from shaiwei.research.provider_contract import D1ControlError
from shaiwei.research.trend_swing.v5_contract import V5Bundle, canonical_json, sha256_file
from shaiwei.research.trend_swing.v5_models import (
    ARCHETYPE_CONTRACT,
    COMMON_FEATURES,
    FORBIDDEN_TEXT,
    MECHANISM_FEATURES,
    PARAMETER_BOUNDS,
    SAFE_TEXT,
    CancellationRule,
    Confirmation,
    Mechanism,
    MechanismCandidate,
    ParameterId,
    ParameterSlot,
)
from shaiwei.research.trend_swing.v5_proposal_contract import (
    MANDATORY_CANCELLATIONS,
    OPTIONAL_CANCELLATIONS,
    SHARED_PARAMETERS,
)

CONTRACT_PATH = PROJECT_ROOT / "config/ts_v5_mechanism_proposal_v3.yaml"
CONTRACT_SHA256 = "c46ee09cf6d1039e85f797e8510284533e0b8980cda255bfb827c30e69942dc8"
STRICT = ConfigDict(extra="forbid")
NUMERIC_PATTERN = r"-?(?:0|[1-9]\d*)(?:\.\d{1,6})?"
SEARCH_POINTS_BY_SLOT_COUNT = {1: 7, 2: 7, 3: 5, 4: 3, 5: 2}


class BoundAttemptAuthority(BaseModel):
    """Result-before authority that a response cannot supply or override."""

    model_config = STRICT

    schema_version: Literal["ts-v5-bound-attempt-authority-v1"]
    attempt_id: Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9-]{2,79}$")]
    ordinal: Annotated[int, Field(ge=1, le=6)]
    mode: Literal["INDEPENDENT"]
    parent_candidate_fingerprints: Annotated[list[str], Field(max_length=0)]
    source: Literal["RESULT_BLIND_SCOPE_ATTEMPT_PLAN"]


class BoundProposalParameterSlot(BaseModel):
    model_config = STRICT

    parameter_id: ParameterId
    value_type: Literal["INTEGER", "DECIMAL"]
    minimum: Annotated[str, Field(pattern=NUMERIC_PATTERN)]
    maximum: Annotated[str, Field(pattern=NUMERIC_PATTERN)]


class BoundMechanismProposalBase(BaseModel):
    model_config = STRICT

    schema_version: Literal["ts-v5-mechanism-proposal-v3"]
    hypothesis: Annotated[str, Field(min_length=20, max_length=500)]
    economic_rationale_draft: Annotated[str, Field(min_length=20, max_length=800)]
    change_summary: Annotated[str, Field(min_length=10, max_length=300)]
    recovery_confirmation: Confirmation
    optional_cancellation_rules: Annotated[
        list[CancellationRule], Field(max_length=len(OPTIONAL_CANCELLATIONS))
    ]
    parameter_slots: Annotated[list[BoundProposalParameterSlot], Field(min_length=1, max_length=5)]
    falsification_conditions: Annotated[list[str], Field(min_length=2, max_length=5)]

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
    def validate_parameter_uniqueness(self) -> "BoundMechanismProposalBase":
        ids = [item.parameter_id for item in self.parameter_slots]
        if len(set(ids)) != len(ids):
            raise ValueError("proposal parameter slots must be unique")
        return self


@dataclass(frozen=True)
class BoundProposalContract:
    document: dict[str, Any]
    sha256: str
    system_prompt: str

    @classmethod
    def load(cls, path: Path = CONTRACT_PATH) -> "BoundProposalContract":
        if path.is_symlink() or sha256_file(path) != CONTRACT_SHA256:
            raise D1ControlError("TS-v5 bound proposal contract identity differs")
        try:
            document = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            raise D1ControlError("TS-v5 bound proposal contract is invalid") from exc
        authority = document.get("authority", {}) if isinstance(document, dict) else {}
        if (
            not isinstance(document, dict)
            or document.get("schema_version") != "ts-v5-mechanism-proposal-contract-v3"
            or document.get("status") != "ENGINEERING_ONLY_NO_LIVE_AUTHORITY"
            or authority.get("external_api_calls") != 0
            or authority.get("attempt_mode_from_local_approved_scope_only") is not True
            or authority.get("search_budget_from_local_compiler_only") is not True
            or authority.get("future_live_calls_require_new_scope_release_and_user_approval") is not True
            or authority.get("production_authorization") != "none"
        ):
            raise D1ControlError("TS-v5 bound proposal authority differs")
        prompt = document.get("system_prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            raise D1ControlError("TS-v5 bound proposal system prompt is missing")
        return cls(document, CONTRACT_SHA256, prompt)


@dataclass(frozen=True)
class BoundCompilation:
    authority: BoundAttemptAuthority
    candidate: MechanismCandidate
    search_evaluations: int

    def evidence_mode(self) -> str:
        mode = self.candidate.lineage.mode
        if mode != self.authority.mode:
            raise D1ControlError("TS-v5 evidence mode differs from compiled candidate lineage")
        return mode


def independent_authority(attempt_id: str, ordinal: int) -> BoundAttemptAuthority:
    return BoundAttemptAuthority.model_validate({
        "schema_version": "ts-v5-bound-attempt-authority-v1",
        "attempt_id": attempt_id,
        "ordinal": ordinal,
        "mode": "INDEPENDENT",
        "parent_candidate_fingerprints": [],
        "source": "RESULT_BLIND_SCOPE_ATTEMPT_PLAN",
    })


def allowed_parameter_ids(mechanism: Mechanism) -> tuple[ParameterId, ...]:
    mandatory = sorted(ARCHETYPE_CONTRACT[mechanism][2], key=lambda item: item.value)
    return tuple([*mandatory, *SHARED_PARAMETERS])


def bound_proposal_model(mechanism: Mechanism) -> type[BoundMechanismProposalBase]:
    allowed = set(allowed_parameter_ids(mechanism))

    class BoundProposal(BoundMechanismProposalBase):
        @model_validator(mode="after")
        def validate_mechanism_parameters(self) -> "BoundProposal":
            ids = {item.parameter_id for item in self.parameter_slots}
            mandatory = ARCHETYPE_CONTRACT[mechanism][2]
            if not mandatory.issubset(ids) or not ids.issubset(allowed):
                raise ValueError("proposal parameter ids differ from the mechanism projection")
            return self

    BoundProposal.__name__ = f"{mechanism.value.title().replace('_', '')}BoundProposal"
    return BoundProposal


def deterministic_search_points(slot_count: int) -> int:
    try:
        points = SEARCH_POINTS_BY_SLOT_COUNT[slot_count]
    except KeyError as exc:
        raise D1ControlError("TS-v5 proposal slot count has no frozen search budget") from exc
    if points**slot_count > 196:
        raise D1ControlError("TS-v5 deterministic search budget exceeds 196 evaluations")
    return points


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
        })
    return {
        "schema_version": "ts-v5-mechanism-projection-v3",
        "primary_mechanism": mechanism.value,
        "deterministic_reference_frame": reference.value,
        "deterministic_pullback_measure": measure.value,
        "deterministic_mandatory_cancellation_rules": [
            item.value for item in MANDATORY_CANCELLATIONS
        ],
        "optional_cancellation_rule_enum": [item.value for item in OPTIONAL_CANCELLATIONS],
        "deterministic_required_features": [
            item.value
            for item in sorted(
                COMMON_FEATURES | MECHANISM_FEATURES[mechanism], key=lambda item: item.value
            )
        ],
        "mandatory_parameter_ids": sorted(item.value for item in mandatory),
        "optional_parameter_ids": [item.value for item in SHARED_PARAMETERS],
        "parameter_contracts": parameters,
        "deterministic_search_points_by_slot_count": SEARCH_POINTS_BY_SLOT_COUNT,
        "maximum_search_evaluations": 196,
        "parameter_slots_must_be_unique": True,
        "parameter_minimum_must_be_less_than_maximum": True,
        "integer_parameter_bounds_must_be_integral": True,
        "numeric_string_pattern": NUMERIC_PATTERN,
        "optional_cancellation_rules_must_be_unique": True,
        "falsification_conditions_must_be_unique": True,
        "response_lineage_field_allowed": False,
        "response_search_points_field_allowed": False,
        "prohibited_text_categories": [
            "code_or_shell_or_sql",
            "url_or_local_path",
            "secret_shaped_value",
            "validated_profit_or_production_claim",
        ],
    }


def proposal_schema(mechanism: Mechanism) -> dict[str, Any]:
    schema = bound_proposal_model(mechanism).model_json_schema()
    slot_definition = schema["$defs"]["BoundProposalParameterSlot"]
    slot_definition["properties"]["parameter_id"] = {
        "enum": [item.value for item in allowed_parameter_ids(mechanism)], "type": "string"
    }
    optional = schema["properties"]["optional_cancellation_rules"]["items"]
    if "$ref" in optional:
        schema["properties"]["optional_cancellation_rules"]["items"] = {
            "enum": [item.value for item in OPTIONAL_CANCELLATIONS], "type": "string"
        }
    schema["x-ts-mechanism-projection"] = mechanism_projection(mechanism)
    schema["x-ts-text-contract"] = {
        "safe_text_pattern": SAFE_TEXT.pattern,
        "forbidden_pattern": FORBIDDEN_TEXT.pattern,
        "falsification_conditions_must_be_unique": True,
    }
    schema["x-ts-assigned-authority-is-not-a-response-field"] = True
    return schema


def _candidate_slots(proposal: BoundMechanismProposalBase) -> tuple[list[dict[str, Any]], int]:
    points = deterministic_search_points(len(proposal.parameter_slots))
    slots = []
    for slot in proposal.parameter_slots:
        payload = {**slot.model_dump(mode="json"), "search_points_maximum": points}
        try:
            validated = ParameterSlot.model_validate(payload)
        except ValueError as exc:
            raise D1ControlError("TS-v5 bound proposal parameter violates the frozen range") from exc
        slots.append(validated.model_dump(mode="json"))
    return slots, points ** len(slots)


def compile_bound_proposal(
    mechanism: Mechanism,
    document: dict[str, Any],
    authority: BoundAttemptAuthority,
) -> BoundCompilation:
    try:
        approved = BoundAttemptAuthority.model_validate(authority)
        proposal = bound_proposal_model(mechanism).model_validate(document)
    except ValueError as exc:
        raise D1ControlError("TS-v5 proposal violates its bound mechanism contract") from exc
    slots, evaluations = _candidate_slots(proposal)
    reference, measure, _ = ARCHETYPE_CONTRACT[mechanism]
    features = sorted(COMMON_FEATURES | MECHANISM_FEATURES[mechanism], key=lambda item: item.value)
    candidate = MechanismCandidate.model_validate({
        "schema_version": "ts-v5-mechanism-candidate-v1",
        "primary_mechanism": mechanism.value,
        "hypothesis": proposal.hypothesis,
        "economic_rationale_draft": proposal.economic_rationale_draft,
        "change_summary": proposal.change_summary,
        "entry_design": {
            "reference_frame": reference.value,
            "pullback_measure": measure.value,
            "recovery_confirmation": proposal.recovery_confirmation.value,
            "cancellation_rules": [
                *[item.value for item in MANDATORY_CANCELLATIONS],
                *[item.value for item in proposal.optional_cancellation_rules],
            ],
        },
        "parameter_slots": slots,
        "required_features": [item.value for item in features],
        "falsification_conditions": proposal.falsification_conditions,
        "lineage": {
            "mode": approved.mode,
            "parent_candidate_fingerprints": approved.parent_candidate_fingerprints,
        },
    })
    result = BoundCompilation(approved, candidate, evaluations)
    result.evidence_mode()
    return result


def build_request_v4(
    mechanism: Mechanism,
    authority: BoundAttemptAuthority,
    *,
    contract: BoundProposalContract | None = None,
) -> dict[str, Any]:
    active = contract or BoundProposalContract.load()
    approved = BoundAttemptAuthority.model_validate(authority)
    bundle = V5Bundle.load()
    task = {
        "attempt_id": approved.attempt_id,
        "ordinal": approved.ordinal,
        "assigned_attempt_authority": approved.model_dump(mode="json"),
        "proposal_schema": proposal_schema(mechanism),
        "mechanism_projection": mechanism_projection(mechanism),
        "product_constraints": bundle.governance["product_constraints"],
        "public_knowledge_summary": bundle.prompt["public_knowledge_summary"],
        "frozen_failure_memory": bundle.prompt["frozen_failure_memory"],
        "instructions": {
            "return_one_json_object_only": True,
            "do_not_emit_deterministic_fields": True,
            "lineage_and_search_points_are_local_only": True,
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
        raise D1ControlError("TS-v5 bound proposal request contains a forbidden identity")
    if len(serialized.encode("utf-8")) > 48_000:
        raise D1ControlError("TS-v5 bound proposal request exceeds its byte bound")
    return request
