"""Pure D1 protocol, candidate, attempt, and request contracts.

This module deliberately has no HTTP client, environment access, ledger writes,
or research execution. Provider adapters and control-plane lifecycles depend on
these values without depending on one another.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
import yaml

from shaiwei.config import PROJECT_ROOT
from shaiwei.research.alphagen_expression import ALLOWED_FEATURES, ALLOWED_OPERATOR_NAMES
from shaiwei.research.llm_factor_prompt import (
    KnowledgeManifest,
    PromptBundle,
    PromptContractError,
)
from shaiwei.research.provider_contract import (
    D1ControlError as D1ControlError,
    ProviderResponse as ProviderResponse,
    SENSITIVE_OUTPUT_PATTERNS as SENSITIVE_OUTPUT_PATTERNS,
)


TOPICS = (
    "trend_momentum",
    "reversal_mean_reversion",
    "volatility_range",
    "liquidity_volume",
    "price_volume_state",
)
def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class CandidateLineage(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    mode: Literal["independent", "mutation"]
    parent_attempt_ids: list[str] = Field(max_length=2)

    @model_validator(mode="after")
    def validate_parent_contract(self) -> "CandidateLineage":
        if self.mode == "independent" and self.parent_attempt_ids:
            raise ValueError("independent candidates cannot declare parents")
        if self.mode == "mutation" and not self.parent_attempt_ids:
            raise ValueError("mutation candidates require at least one parent")
        if len(set(self.parent_attempt_ids)) != len(self.parent_attempt_ids):
            raise ValueError("parent attempt ids must be unique")
        return self


class CandidateProposal(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    schema_version: Literal["d1-candidate-v1"]
    topic: Literal[
        "trend_momentum",
        "reversal_mean_reversion",
        "volatility_range",
        "liquidity_volume",
        "price_volume_state",
    ]
    hypothesis: str = Field(min_length=20, max_length=1000)
    expression: str = Field(min_length=1, max_length=1000)
    expected_direction: Literal["positive", "negative"]
    economic_rationale_draft: str = Field(min_length=20, max_length=2000)
    lineage: CandidateLineage
    known_failure_risks: list[str] = Field(max_length=8)


def _project_contract_path(value: object) -> Path:
    relative = Path(str(value))
    if relative.is_absolute():
        raise D1ControlError("D1 prompt and knowledge paths must be project-relative")
    resolved = (PROJECT_ROOT / relative).resolve()
    try:
        resolved.relative_to(PROJECT_ROOT.resolve())
    except ValueError as error:
        raise D1ControlError("D1 prompt or knowledge path escapes the project") from error
    return resolved


@dataclass(frozen=True)
class D1Protocol:
    path: Path
    document: dict[str, Any]
    sha256: str
    protocol_id: str
    research_family: str
    provider_name: str
    requested_model: str
    returned_model_identity: str
    attempts_per_topic: int
    independent_attempts: int
    maximum_output_tokens: int
    cost_hard_ceiling_usd: float
    prompt_bundle: PromptBundle
    knowledge_manifest: KnowledgeManifest

    @classmethod
    def load(cls, path: Path) -> "D1Protocol":
        if not path.is_file():
            raise D1ControlError(f"D1 protocol is missing: {path}")
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(document, dict):
            raise D1ControlError("D1 protocol must be a YAML object")
        try:
            scope = document["scope"]
            identity = document["identity"]
            budget = document["attempt_budget"]
            schedule = budget["topic_schedule"]
            provider = document["provider"]
            cost = document["cost_budget"]
            candidate = document["candidate_contract"]
            data = document["data_contract"]
            prompt_contract = document["prompt_contract"]
            knowledge_contract = document["knowledge_manifest"]
        except (KeyError, TypeError) as error:
            raise D1ControlError(f"D1 protocol is missing a required section: {error}") from error
        if document.get("d1_1_engineering_authorized") is not True:
            raise D1ControlError("D1-1 engineering is not authorized")
        if document.get("d1_1_engineering_complete") is not True:
            raise D1ControlError("D1-1 engineering is not marked complete")
        if document.get("d1_2a_preexecution_frozen") is not True:
            raise D1ControlError("D1-2A pre-execution contracts are not frozen")
        if document.get("execution_authorized") is not False or document.get("llm_api_called") is not False:
            raise D1ControlError("D1-1 requires real LLM execution to remain unauthorized")
        if scope.get("scheduler_changes") is not False or scope.get("production_model_changes") is not False:
            raise D1ControlError("D1-1 cannot change production or scheduler scope")
        if provider.get("tool_calls") is not False or provider.get("strict_beta_tool_calling") is not False:
            raise D1ControlError("D1-1 provider tools and beta strict mode must remain disabled")
        if int(provider.get("concurrency", 0)) != 1:
            raise D1ControlError("D1 concurrency must be exactly one")
        expected_provider = {
            "name": "deepseek",
            "base_url": "https://api.deepseek.com",
            "model": "deepseek-v4-pro",
            "model_version_observed_on_2026_07_25": "DeepSeek-V4-Pro",
            "thinking": "enabled",
            "reasoning_effort": "high",
            "response_format": "json_object",
            "temperature": None,
        }
        if any(provider.get(field) != value for field, value in expected_provider.items()):
            raise D1ControlError("D1 provider identity differs from the D1-2A official-contract freeze")
        expected_prices = {
            "pro_input_cache_hit_per_million": 0.003625,
            "pro_input_cache_miss_per_million": 0.435,
            "pro_output_per_million": 0.87,
        }
        if any(float(cost.get(field, -1)) != value for field, value in expected_prices.items()):
            raise D1ControlError("D1 provider prices differ from the D1-2A official-contract freeze")
        planned_worst_case = (
            int(budget.get("completed_llm_responses_exact", 0))
            * (
                int(provider["maximum_prompt_tokens_per_attempt"])
                * expected_prices["pro_input_cache_miss_per_million"]
                + int(provider["maximum_output_tokens_per_attempt"])
                * expected_prices["pro_output_per_million"]
            )
            / 1_000_000
        )
        if abs(float(cost.get("planned_worst_case_all_cache_miss_usd", -1)) - planned_worst_case) > 1e-12:
            raise D1ControlError("D1 planned worst-case cost is inconsistent")
        if planned_worst_case > float(cost.get("hard_ceiling_usd", -1)):
            raise D1ControlError("D1 planned worst-case cost exceeds the hard ceiling")
        if tuple(budget.get("topic_order", ())) != TOPICS:
            raise D1ControlError("D1 topic order differs from the frozen contract")
        attempts_per_topic = int(budget.get("attempts_per_topic", 0))
        if attempts_per_topic * len(TOPICS) != int(budget.get("completed_llm_responses_exact", 0)):
            raise D1ControlError("D1 attempt budget is not exactly 40")
        independent = int(schedule.get("independent_proposals", 0))
        mutations = int(schedule.get("bounded_mutations", 0))
        if independent + mutations != attempts_per_topic:
            raise D1ControlError("D1 topic schedule does not exhaust its fixed budget")
        if set(candidate.get("allowed_operators", ())) != ALLOWED_OPERATOR_NAMES:
            raise D1ControlError("D1 operator allowlist differs from the executable parser")
        if set(data.get("features", ())) != ALLOWED_FEATURES:
            raise D1ControlError("D1 feature allowlist differs from the executable parser")
        try:
            prompt_bundle = PromptBundle.load(
                _project_contract_path(prompt_contract["path"]),
                expected_sha256=str(prompt_contract["sha256"]),
            )
            knowledge_manifest = KnowledgeManifest.load(
                _project_contract_path(knowledge_contract["path"]),
                expected_sha256=str(knowledge_contract["sha256"]),
                expected_cutoff=str(data["knowledge_cutoff"]),
            )
            CandidateProposal.model_validate(prompt_bundle.document["candidate_output_contract"]["example"])
            if (
                prompt_bundle.document.get("schema_version") != prompt_contract["schema_version"]
                or prompt_bundle.document.get("prompt_id") != prompt_contract["prompt_id"]
                or knowledge_manifest.document.get("schema_version")
                != knowledge_contract["schema_version"]
                or knowledge_manifest.document.get("manifest_id")
                != knowledge_contract["manifest_id"]
            ):
                raise D1ControlError("D1-2A prompt or knowledge named identity differs")
        except (KeyError, PromptContractError, ValidationError) as error:
            raise D1ControlError(f"D1-2A prompt or knowledge contract is invalid: {error}") from error
        return cls(
            path=path,
            document=document,
            sha256=_sha256_file(path),
            protocol_id=str(document["protocol_id"]),
            research_family=str(identity["research_family"]),
            provider_name=str(provider["name"]),
            requested_model=str(provider["model"]),
            returned_model_identity=str(provider["model_version_observed_on_2026_07_25"]),
            attempts_per_topic=attempts_per_topic,
            independent_attempts=independent,
            maximum_output_tokens=int(provider["maximum_output_tokens_per_attempt"]),
            cost_hard_ceiling_usd=float(cost["hard_ceiling_usd"]),
            prompt_bundle=prompt_bundle,
            knowledge_manifest=knowledge_manifest,
        )


@dataclass(frozen=True)
class AttemptPlan:
    attempt_id: str
    global_ordinal: int
    topic: str
    topic_ordinal: int
    evolution_mode: Literal["independent", "mutation"]


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def candidate_schema() -> dict[str, Any]:
    return CandidateProposal.model_json_schema()


def candidate_schema_sha256() -> str:
    return _sha256_text(_canonical_json(candidate_schema()))


def plan_attempt(protocol: D1Protocol, global_ordinal: int) -> AttemptPlan:
    total = len(TOPICS) * protocol.attempts_per_topic
    if not 1 <= global_ordinal <= total:
        raise D1ControlError(f"global ordinal must be within 1..{total}")
    topic_index, zero_based = divmod(global_ordinal - 1, protocol.attempts_per_topic)
    topic_ordinal = zero_based + 1
    mode: Literal["independent", "mutation"] = (
        "independent" if topic_ordinal <= protocol.independent_attempts else "mutation"
    )
    attempt_identity = f"{protocol.protocol_id}:{protocol.sha256}:{global_ordinal}"
    return AttemptPlan(
        attempt_id=hashlib.sha256(attempt_identity.encode()).hexdigest()[:16],
        global_ordinal=global_ordinal,
        topic=TOPICS[topic_index],
        topic_ordinal=topic_ordinal,
        evolution_mode=mode,
    )


def build_request(
    protocol: D1Protocol,
    plan: AttemptPlan,
    *,
    feedback_records: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    feedback = protocol.prompt_bundle.serialize_feedback(
        topic=plan.topic,
        current_global_ordinal=plan.global_ordinal,
        records=feedback_records or [],
    )
    if plan.evolution_mode == "independent" and feedback:
        raise PromptContractError("independent attempts cannot receive prior-attempt feedback")
    if plan.evolution_mode == "mutation":
        expected_ordinals = set(
            range(plan.global_ordinal - plan.topic_ordinal + 1, plan.global_ordinal)
        )
        actual_ordinals = {int(record["global_ordinal"]) for record in feedback}
        if actual_ordinals != expected_ordinals:
            raise PromptContractError(
                "mutation feedback must contain every earlier attempt from the same topic"
            )
    task = {
        "candidate_schema": candidate_schema(),
        "candidate_example": protocol.prompt_bundle.document["candidate_output_contract"]["example"],
        "topic": plan.topic,
        "topic_template": protocol.prompt_bundle.topic_template(plan.topic),
        "evolution_mode": plan.evolution_mode,
        "allowed_features": sorted(ALLOWED_FEATURES),
        "allowed_operators": sorted(ALLOWED_OPERATOR_NAMES),
        "maximum_expression_tokens": protocol.document["candidate_contract"][
            "maximum_expression_tokens"
        ],
        "maximum_ast_nodes": protocol.document["candidate_contract"]["maximum_ast_nodes"],
        "maximum_lookback_trade_days": protocol.document["data_contract"][
            "maximum_lookback_trade_days"
        ],
        "retrospective_discovery": True,
        "knowledge_packet": protocol.knowledge_manifest.packet_for_topic(plan.topic),
        "knowledge_manifest_sha256": protocol.knowledge_manifest.sha256,
        "feedback": feedback,
        "eligible_parent_attempt_ids": [record["attempt_id"] for record in feedback],
        "prompt_bundle_sha256": protocol.prompt_bundle.sha256,
    }
    request = {
        "model": protocol.requested_model,
        "messages": [
            {"role": "system", "content": protocol.prompt_bundle.system_prompt},
            {"role": "user", "content": _canonical_json(task)},
        ],
        "thinking": {"type": protocol.document["provider"]["thinking"]},
        "reasoning_effort": protocol.document["provider"]["reasoning_effort"],
        "response_format": {"type": protocol.document["provider"]["response_format"]},
        "max_tokens": protocol.maximum_output_tokens,
        "tools": [],
        "stream": False,
    }
    conservative_input_bound = len(_canonical_json(request).encode("utf-8")) + 1024
    if conservative_input_bound > int(
        protocol.document["provider"]["maximum_prompt_tokens_per_attempt"]
    ):
        raise D1ControlError("D1 request exceeds the conservative frozen input-token bound")
    return request
