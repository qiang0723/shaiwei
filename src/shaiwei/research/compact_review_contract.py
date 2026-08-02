"""Schema and deterministic validation for compact LLM reviews."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Mapping, Sequence

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from shaiwei.config import PROJECT_ROOT
from shaiwei.ledger import sha256_file
from shaiwei.research.llm_factor import D1ControlError
from shaiwei.research.llm_review_semantics import (
    SemanticGateProtocol,
    SemanticGateResult,
    evaluate_semantic_contract,
)


DEFAULT_PROTOCOL_PATH = PROJECT_ROOT / "config/llm_review_contract_v2.yaml"
SCHEMA_VERSION = "shaiwei-compact-adversarial-review-response-v2"
ROLES = (
    "construct_and_units",
    "economic_direction_and_cross_pool_coherence",
    "pit_and_numerical_stability",
    "redundancy_and_falsifiability",
)
CATEGORIES = (
    "construct_mismatch",
    "units_or_scale",
    "corporate_action_dependency",
    "direction_mechanism",
    "cross_pool_coherence",
    "pit_clock",
    "numerical_stability",
    "missing_or_suspension",
    "peer_redundancy",
    "falsifiability",
    "scope_limitation",
)
SYNTHETIC_CANDIDATE_ID = "0123456789abcdef"
SYNTHETIC_FORMULA = "Div(Mean($close,5d),Mean($close,20d))"


def canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def _printable_ascii(value: str) -> str:
    if any(ord(character) < 32 or ord(character) > 126 for character in value):
        raise ValueError("compact review narratives must use printable ASCII")
    return value


class CompactFinding(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    severity: Literal["critical", "major", "minor"]
    category: Literal[
        "construct_mismatch",
        "units_or_scale",
        "corporate_action_dependency",
        "direction_mechanism",
        "cross_pool_coherence",
        "pit_clock",
        "numerical_stability",
        "missing_or_suspension",
        "peer_redundancy",
        "falsifiability",
        "scope_limitation",
    ]
    statement: str = Field(min_length=20, max_length=320)
    falsification_condition: str = Field(min_length=20, max_length=240)

    @field_validator("statement", "falsification_condition")
    @classmethod
    def narratives_are_printable_ascii(cls, value: str) -> str:
        return _printable_ascii(value)


class CompactReviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: Literal["shaiwei-compact-adversarial-review-response-v2"]
    candidate_id: str = Field(pattern=r"^[0-9a-f]{16}$")
    role: Literal[
        "construct_and_units",
        "economic_direction_and_cross_pool_coherence",
        "pit_and_numerical_stability",
        "redundancy_and_falsifiability",
    ]
    role_verdict: Literal["NO_BLOCKER_FOUND", "BLOCKER_FOUND"]
    summary: str = Field(min_length=40, max_length=320)
    findings: list[CompactFinding] = Field(min_length=1, max_length=3)
    disposition: Literal[
        "REJECT_EXACT_EXPRESSION_AS_IS",
        "LATER_FROZEN_VALIDATION_ONLY",
    ]
    formula_change_or_new_candidate_proposed: Literal[False]
    performance_or_admission_claim_made: Literal[False]

    @field_validator("summary")
    @classmethod
    def summary_is_printable_ascii(cls, value: str) -> str:
        return _printable_ascii(value)

    @model_validator(mode="after")
    def verdict_findings_and_disposition_agree(self) -> "CompactReviewResponse":
        blocking = any(item.severity in {"critical", "major"} for item in self.findings)
        if blocking != (self.role_verdict == "BLOCKER_FOUND"):
            raise ValueError("compact review verdict differs from blocking findings")
        expected = (
            "REJECT_EXACT_EXPRESSION_AS_IS"
            if blocking
            else "LATER_FROZEN_VALIDATION_ONLY"
        )
        if self.disposition != expected:
            raise ValueError("compact review disposition differs from verdict")
        categories = [item.category for item in self.findings]
        if len(categories) != len(set(categories)):
            raise ValueError("compact review finding categories must be unique")
        return self


def _project_file(value: object, *, label: str) -> Path:
    relative = Path(str(value))
    if relative.is_absolute() or ".." in relative.parts:
        raise D1ControlError(f"{label} must be project-relative")
    path = (PROJECT_ROOT / relative).resolve()
    if not path.is_relative_to(PROJECT_ROOT.resolve()) or not path.is_file():
        raise D1ControlError(f"{label} is missing or escapes the project")
    return path


@dataclass(frozen=True)
class CompactReviewProtocol:
    path: Path
    document: dict[str, Any]
    sha256: str
    semantic_protocol: SemanticGateProtocol

    @classmethod
    def load(cls, path: Path = DEFAULT_PROTOCOL_PATH) -> "CompactReviewProtocol":
        try:
            document = yaml.safe_load(path.read_text(encoding="utf-8"))
        except OSError as error:
            raise D1ControlError("compact review protocol is missing") from error
        if not isinstance(document, dict):
            raise D1ControlError("compact review protocol must be an object")
        _validate_protocol(document)
        semantic = document["semantic_gate"]
        semantic_path = _project_file(semantic["protocol_path"], label="semantic protocol")
        if sha256_file(semantic_path) != semantic["protocol_sha256"]:
            raise D1ControlError("compact review semantic protocol hash differs")
        return cls(
            path=path,
            document=document,
            sha256=sha256_file(path),
            semantic_protocol=SemanticGateProtocol.load(semantic_path),
        )


def _validate_protocol(document: Mapping[str, Any]) -> None:
    authority = document.get("authority_boundary", {})
    provider = document.get("provider_contract", {})
    schema = document.get("compact_schema", {})
    acceptance = document.get("engineering_acceptance", {})
    if (
        document.get("schema_version") != "shaiwei-llm-review-contract-v2"
        or document.get("protocol_id") != "llm-review-contract-v2-engineering"
        or document.get("status") != "RESULT_BEFORE_ENGINEERING_PROTOCOL_FROZEN"
        or authority.get("engineering_only") is not True
        or authority.get("provider_calls_authorized") is not False
        or authority.get("api_key_read_authorized") is not False
        or authority.get("real_candidate_read_authorized") is not False
        or authority.get("prior_batches_reopened") is not False
        or provider.get("thinking") != "disabled"
        or provider.get("reasoning_effort_field_present") is not False
        or provider.get("response_format") != "json_object"
        or provider.get("maximum_output_tokens") != 6000
        or provider.get("maximum_response_json_bytes") != 4096
        or provider.get("narrative_character_set") != "printable_ascii"
        or provider.get("tools") != []
        or provider.get("valid_finish_reason") != "stop"
        or schema.get("schema_version") != SCHEMA_VERSION
        or schema.get("roles") != list(ROLES)
        or schema.get("categories") != list(CATEGORIES)
        or schema.get("free_form_repair_or_resolution_field_forbidden") is not True
        or acceptance.get("provider_calls") != 0
        or acceptance.get("api_key_read") is not False
        or acceptance.get("frozen_m1_m3_modules_unchanged") is not True
    ):
        raise D1ControlError("compact review protocol controls differ")
    prices = document.get("budget_proof", {})
    single = (
        int(provider["maximum_prompt_tokens_per_attempt"])
        * float(prices["input_cache_miss_per_million_usd"])
        + int(provider["maximum_output_tokens"])
        * float(prices["output_per_million_usd"])
    ) / 1_000_000
    if not math.isclose(single, 0.01044) or not math.isclose(single * 8, 0.08352):
        raise D1ControlError("compact review illustrative cost proof differs")


def _legacy_semantic_document(response: CompactReviewResponse) -> dict[str, Any]:
    return {
        "summary": response.summary,
        "findings": [
            {
                "category": finding.category,
                "statement": finding.statement,
                "falsification_or_resolution": finding.falsification_condition,
            }
            for finding in response.findings
        ],
        "formula_change_or_new_candidate_proposed": (
            response.formula_change_or_new_candidate_proposed
        ),
        "performance_claim_made": response.performance_or_admission_claim_made,
    }


def validate_response(
    protocol: CompactReviewProtocol,
    document: Mapping[str, Any],
    *,
    expected_candidate_id: str,
    expected_role: str,
    allowed_formulas: Sequence[str],
) -> tuple[CompactReviewResponse, SemanticGateResult]:
    payload = canonical_json(document).encode("ascii", errors="strict")
    limit = int(protocol.document["provider_contract"]["maximum_response_json_bytes"])
    if len(payload) > limit:
        raise D1ControlError("compact review response exceeds its byte ceiling")
    response = CompactReviewResponse.model_validate(document)
    if response.candidate_id != expected_candidate_id or response.role != expected_role:
        raise D1ControlError("compact review response identity differs")
    narratives = [response.summary]
    narratives.extend(
        value
        for finding in response.findings
        for value in (finding.statement, finding.falsification_condition)
    )
    if any("$" in value for value in narratives):
        raise D1ControlError("compact review response repeats DSL text")
    semantic = evaluate_semantic_contract(
        _legacy_semantic_document(response), allowed_formulas=allowed_formulas
    )
    return response, semantic
