"""Strict M5 proposal contracts and canonical serialization."""

from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SAFE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")
COMMAND_ID_RE = re.compile(r"^m5cmd-[0-9a-f]{64}$")
FORBIDDEN_TEXT_RE = re.compile(
    r"(?:https?://|file://|(?:^|\s)/|\.\./|\$\{|\b(?:select|insert|update|delete|drop)\b|"
    r"\b(?:python|bash|zsh|sh|docker|curl|wget)\b|sk-[A-Za-z0-9]{8,})",
    re.IGNORECASE,
)

StrictModelConfig = ConfigDict(extra="forbid", strict=True)


def canonical_json(value: Any) -> str:
    """Serialize a JSON-compatible value deterministically."""
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class FixedAuthority(BaseModel):
    model_config = StrictModelConfig

    evidence_tier: Literal["PROPOSAL_ONLY"]
    authority_status: Literal["NON_AUTHORITATIVE_PROPOSAL"]
    authoritative_outcome: Literal["NOT_EVALUATED"]
    production_authorization: Literal["none"]
    approval_authorized: Literal[False]
    protocol_freeze_authorized: Literal[False]
    execution_release_authorized: Literal[False]
    worker_dispatch_authorized: Literal[False]
    provider_spend_authorized: Literal[False]
    external_call_authorized: Literal[False]
    deepseek_authorized: Literal[False]
    data_collection_authorized: Literal[False]
    real_data_read_authorized: Literal[False]
    label_read_authorized: Literal[False]
    sealed_effect_read_authorized: Literal[False]
    model_training_authorized: Literal[False]
    backtest_authorized: Literal[False]
    paper_authorized: Literal[False]
    forward_authorized: Literal[False]
    production_authorized: Literal[False]
    scheduler_mutation_authorized: Literal[False]
    docker_write_authorized: Literal[False]
    git_write_authorized: Literal[False]


class ProposalCreate(BaseModel):
    model_config = StrictModelConfig

    template_id: Literal["bounded-research-proposal-v1"]
    template_version: Literal[2]
    universe_ids: Annotated[list[str], Field(min_length=1, max_length=3)]
    home_universe_id: str
    family_id: str
    hypothesis_id: str
    falsification_rule_id: Literal["frozen-gates-reject-v1"]
    generation_mode: Literal["DETERMINISTIC_CODE", "LLM_BOUNDED_DSL"]
    generation_attempt_cap: Literal[8, 12, 24]
    candidate_cap: Annotated[int, Field(ge=1, le=24)]
    provider_identity: Literal["NONE_NOT_APPLICABLE", "TO_BE_REVIEWED_NOT_AUTHORIZED"]
    provider_call_intent_count: Annotated[int, Field(ge=0, le=24)]
    completed_response_target: Annotated[int, Field(ge=0, le=24)]
    provider_budget_usd: str
    valid_days: Annotated[int, Field(ge=1, le=14)]
    authority: FixedAuthority

    @field_validator("universe_ids")
    @classmethod
    def validate_universe_ids(cls, values: list[str]) -> list[str]:
        if len(set(values)) != len(values):
            raise ValueError("universe_ids must be unique")
        if any(not SAFE_ID_RE.fullmatch(value) or value.upper().endswith(".BJ") for value in values):
            raise ValueError("universe_ids contains an invalid or .BJ identifier")
        return values

    @field_validator("home_universe_id", "family_id", "hypothesis_id")
    @classmethod
    def validate_safe_id(cls, value: str) -> str:
        if not SAFE_ID_RE.fullmatch(value) or value.upper().endswith(".BJ"):
            raise ValueError("invalid identifier")
        return value

    @field_validator("provider_budget_usd")
    @classmethod
    def validate_budget(cls, value: str) -> str:
        if not re.fullmatch(r"(?:0|0\.\d{1,2}|1(?:\.0{1,2})?)", value):
            raise ValueError("budget must be an exact decimal string from 0 to 1.00")
        try:
            parsed = Decimal(value)
        except InvalidOperation as exc:
            raise ValueError("invalid exact decimal") from exc
        if not parsed.is_finite() or not (Decimal("0") <= parsed <= Decimal("1.00")):
            raise ValueError("budget is outside the frozen range")
        return f"{parsed:.2f}"

    @model_validator(mode="after")
    def validate_relationships(self) -> "ProposalCreate":
        if self.home_universe_id not in self.universe_ids:
            raise ValueError("home_universe_id must be selected")
        if self.candidate_cap > self.generation_attempt_cap:
            raise ValueError("candidate_cap exceeds generation_attempt_cap")
        if self.provider_call_intent_count > self.generation_attempt_cap:
            raise ValueError("provider_call_intent_count exceeds generation_attempt_cap")
        if self.completed_response_target > self.generation_attempt_cap:
            raise ValueError("completed_response_target exceeds generation_attempt_cap")
        budget = Decimal(self.provider_budget_usd)
        if self.generation_mode == "DETERMINISTIC_CODE" and (
            self.provider_identity != "NONE_NOT_APPLICABLE"
            or self.provider_call_intent_count != 0
            or self.completed_response_target != 0
            or budget != Decimal("0.00")
        ):
            raise ValueError("deterministic generation requires zero provider intent and budget")
        if self.generation_mode == "LLM_BOUNDED_DSL" and (
            self.provider_identity != "TO_BE_REVIEWED_NOT_AUTHORIZED"
            or self.provider_call_intent_count != self.generation_attempt_cap
            or self.completed_response_target != self.generation_attempt_cap
            or budget <= Decimal("0.00")
        ):
            raise ValueError("LLM generation requires exact bounded provider intent and positive budget")
        if FORBIDDEN_TEXT_RE.search(canonical_json(self.model_dump(mode="json"))):
            raise ValueError("request contains prohibited executable, path, URL, or secret text")
        return self


class SubmitReviewCommand(BaseModel):
    model_config = StrictModelConfig

    command_id: str
    expected_event_seq: Annotated[int, Field(ge=1)]
    proposal_request_sha256: str
    reason_code: Literal["READY_FOR_HUMAN_REVIEW"]

    @field_validator("command_id")
    @classmethod
    def validate_command_id(cls, value: str) -> str:
        if not COMMAND_ID_RE.fullmatch(value) or FORBIDDEN_TEXT_RE.search(value):
            raise ValueError("invalid command_id")
        return value

    @field_validator("proposal_request_sha256")
    @classmethod
    def validate_request_sha(cls, value: str) -> str:
        if not SHA256_RE.fullmatch(value):
            raise ValueError("invalid proposal request SHA-256")
        return value


class CancelCommand(SubmitReviewCommand):
    reason_code: Literal["NO_LONGER_NEEDED", "REPLACED_BY_NEW_PROPOSAL", "CREATED_IN_ERROR"]


class StoredResponse(BaseModel):
    model_config = StrictModelConfig

    status_code: int
    body_json: str
    replayed: bool = False


class ProposalView(BaseModel):
    """Response shape; payload is kept JSON-compatible and explicit."""

    model_config = StrictModelConfig

    proposal_id: str
    current_state: Literal["DRAFT", "REVIEW_REQUIRED", "CANCELLED"]
    current_event_seq: int
    available_actions: list[str]
    proposal_request_sha256: str
    canonical_proposal: dict[str, Any]
    events: list[dict[str, Any]] = Field(default_factory=list)


def ensure_finite_numbers(value: Any) -> None:
    """Defence in depth for values decoded outside Pydantic JSON parsing."""
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("non-finite number")
    if isinstance(value, dict):
        for nested in value.values():
            ensure_finite_numbers(nested)
    elif isinstance(value, list):
        for nested in value:
            ensure_finite_numbers(nested)


def utc_iso(now: datetime) -> str:
    return now.astimezone().isoformat(timespec="seconds")
