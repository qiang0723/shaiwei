"""D1 LLM-factor control plane with a zero-network engineering fixture.

The real provider adapter lives in ``deepseek_client`` so this control module
cannot acquire network capability by import. D1-2A binds the frozen prompt and
knowledge identities while real execution remains disabled.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Literal, Protocol

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from shaiwei.config import PROJECT_ROOT
from shaiwei.ledger import append_llm_factor_attempt, append_llm_factor_experiment, sha256_file
from shaiwei.provenance import code_snapshot_sha256
from shaiwei.research.alphagen_expression import (
    ALLOWED_FEATURES,
    ALLOWED_OPERATOR_NAMES,
    ExpressionAudit,
    ExpressionSafetyError,
    audit_expression,
)
from shaiwei.research.llm_factor_prompt import (
    KnowledgeManifest,
    PromptBundle,
    PromptContractError,
)


TOPICS = (
    "trend_momentum",
    "reversal_mean_reversion",
    "volatility_range",
    "liquidity_volume",
    "price_volume_state",
)
SENSITIVE_OUTPUT_PATTERNS = (
    re.compile(r"(?<![A-Za-z0-9])sk-[A-Za-z0-9]{20,}"),
    re.compile(r"https://open\.feishu\.cn/open-apis/bot/v2/hook/[0-9a-fA-F-]{32,}"),
)
ATTEMPT_LEDGER_HEADER_V1 = (
    "attempt_id",
    "protocol_id",
    "research_family",
    "global_ordinal",
    "topic",
    "topic_ordinal",
    "evolution_mode",
    "parent_attempt_ids_json",
    "completed_at",
    "provider_mode",
    "provider",
    "requested_model",
    "returned_model",
    "protocol_sha256",
    "request_sha256",
    "response_sha256",
    "candidate_schema_sha256",
    "code_snapshot_sha256",
    "data_snapshot_sha256",
    "knowledge_manifest_sha256",
    "finish_reason",
    "prompt_tokens",
    "prompt_cache_hit_tokens",
    "prompt_cache_miss_tokens",
    "completion_tokens",
    "estimated_cost_usd",
    "parse_status",
    "sandbox_status",
    "canonical_expression",
    "expression_sha256",
    "duplicate_of_attempt_id",
    "failure_class",
    "candidate_status",
    "artifact_manifest_path",
    "artifact_manifest_sha256",
    "experiment_id",
    "operator",
)
ATTEMPT_LEDGER_HEADER = ATTEMPT_LEDGER_HEADER_V1
ATTEMPT_LEDGER_HEADER_V2 = (
    "attempt_id",
    "protocol_id",
    "research_family",
    "global_ordinal",
    "topic",
    "topic_ordinal",
    "evolution_mode",
    "parent_attempt_ids_json",
    "completed_at",
    "provider_mode",
    "provider",
    "requested_model",
    "returned_model",
    "protocol_sha256",
    "execution_release_id",
    "execution_release_sha256",
    "batch_hard_ceiling_usd",
    "request_sha256",
    "response_sha256",
    "candidate_schema_sha256",
    "code_snapshot_sha256",
    "data_snapshot_sha256",
    "knowledge_manifest_sha256",
    "finish_reason",
    "prompt_tokens",
    "prompt_cache_hit_tokens",
    "prompt_cache_miss_tokens",
    "completion_tokens",
    "estimated_cost_usd",
    "parse_status",
    "sandbox_status",
    "canonical_expression",
    "expression_sha256",
    "expression_tokens",
    "ast_nodes",
    "max_lookback_days",
    "duplicate_of_attempt_id",
    "discovery_status",
    "discovery_eligible_rows",
    "discovery_covered_rows",
    "discovery_coverage",
    "discovery_daily_ic_count",
    "discovery_rank_ic",
    "discovery_error",
    "discovery_artifact_path",
    "discovery_artifact_sha256",
    "failure_class",
    "candidate_status",
    "artifact_manifest_path",
    "artifact_manifest_sha256",
    "experiment_id",
    "operator",
)
EXPERIMENT_LEDGER_HEADER = (
    "experiment_id",
    "parent_experiment_id",
    "ts",
    "candidate_source",
    "model_or_engine",
    "engine_version",
    "seed",
    "prompt_hash",
    "code_sha256",
    "data_snapshot_sha256",
    "feature_or_formula",
    "params_json",
    "train_period",
    "valid_period",
    "result_json",
    "admitted",
    "reject_reason",
)


class D1ControlError(RuntimeError):
    pass


class CandidateSemanticContractError(RuntimeError):
    """Stop one completed response after a deterministic narrative/DSL mismatch."""


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
            sha256=sha256_file(path),
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


@dataclass(frozen=True)
class ProviderResponse:
    model: str
    content: str
    reasoning_content: str
    finish_reason: str
    usage: dict[str, int] | None
    completed_at: str
    sensitive_output_detected: bool = False
    source_response_sha256: str = ""


class Provider(Protocol):
    mode: str
    external_api_calls: int

    def complete(self, request: dict[str, Any]) -> ProviderResponse: ...


class MockProvider:
    """An in-memory provider used by D1-1; it has no network implementation."""

    mode = "mock"
    external_api_calls = 0

    def __init__(self, responses: list[ProviderResponse]):
        self._responses = list(responses)
        self.responses_consumed = 0

    def complete(self, request: dict[str, Any]) -> ProviderResponse:
        if request.get("model") is None:
            raise D1ControlError("mock request is missing model identity")
        if not self._responses:
            raise D1ControlError("mock provider has no remaining response")
        self.responses_consumed += 1
        return self._responses.pop(0)


@dataclass(frozen=True)
class AttemptResult:
    row: dict[str, str]
    reused: bool
    audit: ExpressionAudit | None


@dataclass(frozen=True)
class DiscoveryEvidence:
    """Bounded discovery-only evidence returned by the D1-2B evaluator."""

    status: Literal["PASS", "FAIL"]
    eligible_rows: int
    covered_rows: int
    coverage: float | None
    daily_ic_count: int
    rank_ic: float | None
    error: str
    artifact_path: str
    artifact_sha256: str


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def candidate_schema() -> dict[str, Any]:
    return CandidateProposal.model_json_schema()


def candidate_schema_sha256() -> str:
    return _sha256_text(_canonical_json(candidate_schema()))


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


def initialize_attempt_ledger(
    path: Path, *, header: tuple[str, ...] = ATTEMPT_LEDGER_HEADER_V1
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized_header = ",".join(header) + "\n"
    if path.is_file():
        if path.read_text(encoding="utf-8").splitlines()[:1] != [
            serialized_header.rstrip("\n")
        ]:
            raise D1ControlError(f"D1 attempt ledger header differs: {path}")
        return
    path.write_text(serialized_header, encoding="utf-8")


def initialize_experiment_ledger(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    header = ",".join(EXPERIMENT_LEDGER_HEADER) + "\n"
    if path.is_file():
        if path.read_text(encoding="utf-8").splitlines()[:1] != [header.rstrip("\n")]:
            raise D1ControlError(f"experiment ledger header differs: {path}")
        return
    path.write_text(header, encoding="utf-8")


def _attempt_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    attempt_ids = [row["attempt_id"] for row in rows]
    if len(attempt_ids) != len(set(attempt_ids)):
        raise D1ControlError("D1 attempt ledger contains duplicate attempt ids")
    return rows


def _experiment_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    experiment_ids = [row["experiment_id"] for row in rows]
    if len(experiment_ids) != len(set(experiment_ids)):
        raise D1ControlError("experiment ledger contains duplicate experiment ids")
    return rows


def _experiment_id(attempt_id: str) -> str:
    return _sha256_text(f"{attempt_id}:experiment")[:12]


def _verify_experiment_link(
    attempt: dict[str, str], experiment_rows: list[dict[str, str]]
) -> dict[str, str]:
    experiment_id = attempt["experiment_id"]
    linked = [row for row in experiment_rows if row["experiment_id"] == experiment_id]
    if len(linked) != 1:
        raise D1ControlError(
            f"D1 attempt must have exactly one experiment-ledger counterpart: {attempt['attempt_id']}"
        )
    experiment = linked[0]
    if experiment["prompt_hash"] != attempt["request_sha256"]:
        raise D1ControlError("D1 attempt and experiment prompt hashes differ")
    if experiment["code_sha256"] != attempt["code_snapshot_sha256"]:
        raise D1ControlError("D1 attempt and experiment code snapshots differ")
    if experiment["data_snapshot_sha256"] != attempt["data_snapshot_sha256"]:
        raise D1ControlError("D1 attempt and experiment data snapshots differ")
    result = json.loads(experiment["result_json"])
    if result.get("attempt_id") != attempt["attempt_id"]:
        raise D1ControlError("D1 experiment result does not identify its attempt")
    return experiment


def verify_attempt_experiment_bijection(
    attempt_ledger_path: Path, experiment_ledger_path: Path
) -> dict[str, int]:
    attempts = _attempt_rows(attempt_ledger_path)
    experiments = _experiment_rows(experiment_ledger_path)
    attempt_experiment_ids = {row["experiment_id"] for row in attempts}
    related = [
        row
        for row in experiments
        if row["candidate_source"] == "LLM_DSL"
        and json.loads(row["result_json"]).get("protocol_id")
    ]
    related_ids = {row["experiment_id"] for row in related}
    if len(related) != len(attempts) or related_ids != attempt_experiment_ids:
        raise D1ControlError("D1 attempt and experiment ledgers are not one-to-one")
    for attempt in attempts:
        _verify_experiment_link(attempt, experiments)
    return {"attempt_rows": len(attempts), "experiment_rows": len(related)}


def _write_once(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file():
        if path.read_text(encoding="utf-8") != payload:
            raise D1ControlError(f"immutable D1 artifact differs: {path}")
        return
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(payload, encoding="utf-8")
        with temporary.open("rb") as handle:
            os.fsync(handle.fileno())
        os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _has_sensitive_output(response: ProviderResponse) -> bool:
    if response.sensitive_output_detected:
        return True
    combined = f"{response.content}\n{response.reasoning_content}"
    return any(pattern.search(combined) for pattern in SENSITIVE_OUTPUT_PATTERNS)


def _validate_usage(protocol: D1Protocol, usage: dict[str, int] | None) -> tuple[dict[str, int], float]:
    required = (
        "prompt_tokens",
        "prompt_cache_hit_tokens",
        "prompt_cache_miss_tokens",
        "completion_tokens",
    )
    if not isinstance(usage, dict) or any(key not in usage for key in required):
        raise D1ControlError("provider usage is missing required fields")
    normalized: dict[str, int] = {}
    for key in required:
        value = usage[key]
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise D1ControlError(f"provider usage field is invalid: {key}")
        normalized[key] = value
    if normalized["prompt_cache_hit_tokens"] + normalized["prompt_cache_miss_tokens"] != normalized[
        "prompt_tokens"
    ]:
        raise D1ControlError("provider cache hit/miss usage does not sum to prompt tokens")
    maximum_prompt = int(protocol.document["provider"]["maximum_prompt_tokens_per_attempt"])
    if normalized["prompt_tokens"] > maximum_prompt:
        raise D1ControlError("provider prompt usage exceeds the frozen per-attempt limit")
    if normalized["completion_tokens"] > protocol.maximum_output_tokens:
        raise D1ControlError("provider completion usage exceeds the frozen per-attempt limit")
    prices = protocol.document["cost_budget"]
    cost = (
        normalized["prompt_cache_hit_tokens"] * float(prices["pro_input_cache_hit_per_million"])
        + normalized["prompt_cache_miss_tokens"] * float(prices["pro_input_cache_miss_per_million"])
        + normalized["completion_tokens"] * float(prices["pro_output_per_million"])
    ) / 1_000_000
    return normalized, cost


def _validate_lineage(
    plan: AttemptPlan,
    proposal: CandidateProposal,
    rows: list[dict[str, str]],
    *,
    eligible_parent_ids: set[str],
) -> None:
    if proposal.lineage.mode != plan.evolution_mode:
        raise D1ControlError("candidate lineage mode differs from the frozen attempt schedule")
    if proposal.topic != plan.topic:
        raise D1ControlError("candidate topic differs from the frozen attempt schedule")
    if plan.evolution_mode == "independent":
        return
    indexed = {row["attempt_id"]: row for row in rows}
    for parent_id in proposal.lineage.parent_attempt_ids:
        if parent_id not in eligible_parent_ids:
            raise D1ControlError("mutation parent is not in the frozen eligible-parent set")
        parent = indexed.get(parent_id)
        if parent is None:
            raise D1ControlError(f"mutation parent is absent from the attempt ledger: {parent_id}")
        if parent["topic"] != plan.topic or int(parent["global_ordinal"]) >= plan.global_ordinal:
            raise D1ControlError("mutation parent must be an earlier attempt from the same topic")


def _response_envelope(response: ProviderResponse) -> dict[str, Any]:
    return {
        "model": response.model,
        "content": response.content,
        "reasoning_content": response.reasoning_content,
        "finish_reason": response.finish_reason,
        "usage": response.usage,
        "completed_at": response.completed_at,
        "sensitive_output_detected": response.sensitive_output_detected,
        "source_response_sha256": response.source_response_sha256,
    }


def _parse_timezone_timestamp(value: str) -> None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise D1ControlError("provider completed_at is not ISO-8601") from error
    if parsed.tzinfo is None:
        raise D1ControlError("provider completed_at must contain a timezone")


def execute_completed_attempt(
    protocol: D1Protocol,
    plan: AttemptPlan,
    provider: Provider,
    *,
    ledger_path: Path,
    experiment_ledger_path: Path,
    artifact_root: Path,
    operator: str,
    code_sha256: str | None = None,
    feedback_records: list[dict[str, Any]] | None = None,
    execution_release_id: str = "",
    execution_release_sha256: str = "",
    cost_hard_ceiling_usd: float | None = None,
    data_sha256: str | None = None,
    discovery_evaluator: Callable[[AttemptPlan, str], DiscoveryEvidence] | None = None,
    returned_model_identity: str | None = None,
    candidate_semantic_validator: Callable[[CandidateProposal], str | None] | None = None,
) -> AttemptResult:
    attempt_header = (
        ATTEMPT_LEDGER_HEADER_V2 if execution_release_id else ATTEMPT_LEDGER_HEADER_V1
    )
    initialize_attempt_ledger(ledger_path, header=attempt_header)
    initialize_experiment_ledger(experiment_ledger_path)
    serialized_feedback = protocol.prompt_bundle.serialize_feedback(
        topic=plan.topic,
        current_global_ordinal=plan.global_ordinal,
        records=feedback_records or [],
    )
    request = build_request(protocol, plan, feedback_records=serialized_feedback)
    request_sha256 = _sha256_text(_canonical_json(request))
    rows = _attempt_rows(ledger_path)
    existing = next((row for row in rows if row["attempt_id"] == plan.attempt_id), None)
    if existing is not None:
        if existing["protocol_sha256"] != protocol.sha256 or existing["request_sha256"] != request_sha256:
            raise D1ControlError("existing attempt identity collides with a different protocol or request")
        _verify_experiment_link(existing, _experiment_rows(experiment_ledger_path))
        return AttemptResult(existing, reused=True, audit=None)
    indexed_rows = {row["attempt_id"]: row for row in rows}
    for feedback in serialized_feedback:
        prior = indexed_rows.get(str(feedback["attempt_id"]))
        if prior is None:
            raise D1ControlError("feedback attempt is absent from the immutable attempt ledger")
        expected = {
            "attempt_id": prior["attempt_id"],
            "global_ordinal": int(prior["global_ordinal"]),
            "topic": prior["topic"],
            "parse_status": prior["parse_status"],
            "sandbox_status": prior["sandbox_status"],
            "canonical_expression": prior["canonical_expression"],
            "duplicate_of_attempt_id": prior["duplicate_of_attempt_id"],
            "failure_class": prior["failure_class"],
            "discovery_coverage": (
                float(prior["discovery_coverage"])
                if prior["discovery_coverage"]
                else None
            ),
            "discovery_rank_ic": (
                float(prior["discovery_rank_ic"])
                if prior["discovery_rank_ic"]
                else None
            ),
            "expression_tokens": (
                int(prior["expression_tokens"]) if prior["expression_tokens"] else None
            ),
            "ast_nodes": int(prior["ast_nodes"]) if prior["ast_nodes"] else None,
            "max_lookback_days": (
                int(prior["max_lookback_days"]) if prior["max_lookback_days"] else None
            ),
        }
        if feedback != expected:
            raise D1ControlError("feedback differs from the immutable attempt ledger")
    fatal_failures = {
        "cost_budget_exceeded",
        "model_identity_mismatch",
        "sensitive_output",
        "usage_missing_or_invalid",
        "discovery_evaluation_error",
    }
    prior_fatal = next(
        (row for row in rows if row["failure_class"] in fatal_failures),
        None,
    )
    if prior_fatal is not None:
        raise D1ControlError(
            "a prior D1 attempt requires operator review before any further provider call"
        )

    committed_cost = sum(float(row["estimated_cost_usd"]) for row in rows)
    effective_hard_ceiling = (
        protocol.cost_hard_ceiling_usd
        if cost_hard_ceiling_usd is None
        else float(cost_hard_ceiling_usd)
    )
    if not 0 < effective_hard_ceiling <= 10.0:
        raise D1ControlError("D1 effective hard ceiling must be within (0, 10]")
    price = protocol.document["cost_budget"]
    worst_case_next = (
        int(protocol.document["provider"]["maximum_prompt_tokens_per_attempt"])
        * float(price["pro_input_cache_miss_per_million"])
        + protocol.maximum_output_tokens * float(price["pro_output_per_million"])
    ) / 1_000_000
    if committed_cost + worst_case_next > effective_hard_ceiling:
        raise D1ControlError("cumulative worst-case cost would exceed the frozen hard ceiling")

    response = provider.complete(request)
    _parse_timezone_timestamp(response.completed_at)
    response_payload = _canonical_json(_response_envelope(response)) + "\n"
    response_sha256 = _sha256_text(response_payload)
    parse_status = "NOT_RUN"
    sandbox_status = "NOT_RUN"
    canonical_expression = ""
    expression_sha256 = ""
    duplicate_of = ""
    discovery_status = "NOT_RUN"
    discovery_eligible_rows = ""
    discovery_covered_rows = ""
    discovery_coverage = ""
    discovery_daily_ic_count = ""
    discovery_rank_ic = ""
    discovery_error = ""
    discovery_artifact_path = ""
    discovery_artifact_sha256 = ""
    candidate_semantic_error = ""
    failure_class = ""
    candidate_status = "REJECT"
    audit: ExpressionAudit | None = None
    parents: list[str] = []
    usage = {
        "prompt_tokens": 0,
        "prompt_cache_hit_tokens": 0,
        "prompt_cache_miss_tokens": 0,
        "completion_tokens": 0,
    }
    estimated_cost = 0.0

    try:
        usage, estimated_cost = _validate_usage(protocol, response.usage)
    except D1ControlError:
        failure_class = "usage_missing_or_invalid"
    if not failure_class and committed_cost + estimated_cost > effective_hard_ceiling:
        failure_class = "cost_budget_exceeded"
    expected_returned_model = returned_model_identity or protocol.returned_model_identity
    if not failure_class and response.model != expected_returned_model:
        failure_class = "model_identity_mismatch"
    if not failure_class and _has_sensitive_output(response):
        failure_class = "sensitive_output"
    if not failure_class and (response.finish_reason != "stop" or not response.content.strip()):
        failure_class = "empty_or_truncated_output"
    if not failure_class:
        try:
            proposal = CandidateProposal.model_validate_json(response.content)
            parse_status = "PASS"
            parents = proposal.lineage.parent_attempt_ids
            _validate_lineage(
                plan,
                proposal,
                rows,
                eligible_parent_ids={
                    str(record["attempt_id"]) for record in serialized_feedback
                },
            )
            if candidate_semantic_validator is not None:
                candidate_semantic_error = candidate_semantic_validator(proposal) or ""
                if candidate_semantic_error:
                    failure_class = "semantic_contract_violation"
            if failure_class:
                raise CandidateSemanticContractError
            audit = audit_expression(proposal.expression)
            limits = protocol.document["candidate_contract"]
            if audit.expression_tokens > int(limits["maximum_expression_tokens"]):
                raise ExpressionSafetyError("expression exceeds the frozen token limit")
            if audit.ast_nodes > int(limits["maximum_ast_nodes"]):
                raise ExpressionSafetyError("expression exceeds the frozen AST node limit")
            if audit.max_lookback_days > int(
                protocol.document["data_contract"]["maximum_lookback_trade_days"]
            ):
                raise ExpressionSafetyError("expression exceeds the frozen lookback limit")
            if not (audit.pit_sentinel_pass and audit.shift_sentinel_pass):
                raise ExpressionSafetyError("expression failed PIT/shift sentinels")
            sandbox_status = "PASS"
            canonical_expression = audit.normalized_expression
            expression_sha256 = _sha256_text(canonical_expression)
            duplicate = next(
                (
                    row
                    for row in rows
                    if row["canonical_expression"] == canonical_expression
                    and row["sandbox_status"] == "PASS"
                ),
                None,
            )
            if duplicate is not None:
                duplicate_of = duplicate["attempt_id"]
                failure_class = "duplicate_ast"
            elif discovery_evaluator is not None:
                try:
                    discovery = discovery_evaluator(plan, canonical_expression)
                    if discovery.status not in {"PASS", "FAIL"}:
                        raise D1ControlError("discovery evaluator returned an invalid status")
                    if discovery.eligible_rows < 0 or not 0 <= discovery.covered_rows <= discovery.eligible_rows:
                        raise D1ControlError("discovery evaluator returned invalid row counts")
                    if discovery.daily_ic_count < 0:
                        raise D1ControlError("discovery evaluator returned an invalid IC count")
                    if discovery.coverage is not None and not 0 <= discovery.coverage <= 1:
                        raise D1ControlError("discovery evaluator returned invalid coverage")
                    if discovery.rank_ic is not None and not -1 <= discovery.rank_ic <= 1:
                        raise D1ControlError("discovery evaluator returned invalid RankIC")
                    if Path(discovery.artifact_path).is_absolute():
                        raise D1ControlError("discovery artifact path must be relative")
                    if len(discovery.artifact_sha256) != 64:
                        raise D1ControlError("discovery artifact hash is invalid")
                    discovery_status = discovery.status
                    discovery_eligible_rows = str(discovery.eligible_rows)
                    discovery_covered_rows = str(discovery.covered_rows)
                    discovery_coverage = (
                        "" if discovery.coverage is None else f"{discovery.coverage:.12f}"
                    )
                    discovery_daily_ic_count = str(discovery.daily_ic_count)
                    discovery_rank_ic = (
                        "" if discovery.rank_ic is None else f"{discovery.rank_ic:.12f}"
                    )
                    discovery_error = discovery.error
                    discovery_artifact_path = discovery.artifact_path
                    discovery_artifact_sha256 = discovery.artifact_sha256
                    if discovery.status == "PASS":
                        candidate_status = "DISCOVERY_EVALUATED"
                    else:
                        failure_class = "insufficient_coverage"
                except (D1ControlError, OSError, RuntimeError, TypeError, ValueError):
                    discovery_status = "FAIL"
                    discovery_error = "discovery_evaluation_error"
                    failure_class = "discovery_evaluation_error"
            else:
                candidate_status = "CONTRACT_PASS"
        except ValidationError:
            parse_status = "FAIL"
            failure_class = "schema_invalid"
        except CandidateSemanticContractError:
            pass
        except ExpressionSafetyError:
            sandbox_status = "FAIL"
            failure_class = "sandbox_rejected"
        except D1ControlError:
            parse_status = "FAIL"
            failure_class = "schema_invalid"

    raw_relative = f"raw/{plan.attempt_id}-{response_sha256[:12]}.json"
    if failure_class != "sensitive_output":
        _write_once(artifact_root / raw_relative, response_payload)
    else:
        raw_relative = ""
    manifest = {
        "schema_version": "d1-attempt-artifact-manifest-v1",
        "attempt_id": plan.attempt_id,
        "protocol_sha256": protocol.sha256,
        "request_sha256": request_sha256,
        "response_sha256": response_sha256,
        "raw_response_path": raw_relative,
        "parse_status": parse_status,
        "sandbox_status": sandbox_status,
        "canonical_expression": canonical_expression,
        "expression_sha256": expression_sha256,
        "expression_tokens": audit.expression_tokens if audit is not None else None,
        "ast_nodes": audit.ast_nodes if audit is not None else None,
        "max_lookback_days": audit.max_lookback_days if audit is not None else None,
        "failure_class": failure_class,
        "candidate_semantic_error": candidate_semantic_error,
        "candidate_status": candidate_status,
        "discovery_status": discovery_status,
        "discovery_coverage": discovery_coverage or None,
        "discovery_rank_ic": discovery_rank_ic or None,
        "discovery_artifact_path": discovery_artifact_path,
        "discovery_artifact_sha256": discovery_artifact_sha256,
    }
    manifest_payload = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    manifest_relative = f"manifests/{plan.attempt_id}.json"
    manifest_path = artifact_root / manifest_relative
    _write_once(manifest_path, manifest_payload)
    manifest_sha256 = sha256_file(manifest_path)
    resolved_data_sha256 = data_sha256 or _sha256_text("d1-synthetic-fixture-v1")
    resolved_code_sha256 = code_sha256 or code_snapshot_sha256()
    experiment_id = _experiment_id(plan.attempt_id)
    full_row = {
        "attempt_id": plan.attempt_id,
        "protocol_id": protocol.protocol_id,
        "research_family": protocol.research_family,
        "global_ordinal": str(plan.global_ordinal),
        "topic": plan.topic,
        "topic_ordinal": str(plan.topic_ordinal),
        "evolution_mode": plan.evolution_mode,
        "parent_attempt_ids_json": _canonical_json(parents),
        "completed_at": response.completed_at,
        "provider_mode": provider.mode,
        "provider": protocol.provider_name,
        "requested_model": protocol.requested_model,
        "returned_model": response.model,
        "protocol_sha256": protocol.sha256,
        "execution_release_id": execution_release_id,
        "execution_release_sha256": execution_release_sha256,
        "batch_hard_ceiling_usd": (
            f"{effective_hard_ceiling:.12f}" if execution_release_id else ""
        ),
        "request_sha256": request_sha256,
        "response_sha256": response_sha256,
        "candidate_schema_sha256": candidate_schema_sha256(),
        "code_snapshot_sha256": resolved_code_sha256,
        "data_snapshot_sha256": resolved_data_sha256,
        "knowledge_manifest_sha256": protocol.knowledge_manifest.sha256,
        "finish_reason": response.finish_reason,
        "prompt_tokens": str(usage["prompt_tokens"]),
        "prompt_cache_hit_tokens": str(usage["prompt_cache_hit_tokens"]),
        "prompt_cache_miss_tokens": str(usage["prompt_cache_miss_tokens"]),
        "completion_tokens": str(usage["completion_tokens"]),
        "estimated_cost_usd": f"{estimated_cost:.12f}",
        "parse_status": parse_status,
        "sandbox_status": sandbox_status,
        "canonical_expression": canonical_expression,
        "expression_sha256": expression_sha256,
        "expression_tokens": str(audit.expression_tokens) if audit is not None else "",
        "ast_nodes": str(audit.ast_nodes) if audit is not None else "",
        "max_lookback_days": str(audit.max_lookback_days) if audit is not None else "",
        "duplicate_of_attempt_id": duplicate_of,
        "discovery_status": discovery_status,
        "discovery_eligible_rows": discovery_eligible_rows,
        "discovery_covered_rows": discovery_covered_rows,
        "discovery_coverage": discovery_coverage,
        "discovery_daily_ic_count": discovery_daily_ic_count,
        "discovery_rank_ic": discovery_rank_ic,
        "discovery_error": discovery_error,
        "discovery_artifact_path": discovery_artifact_path,
        "discovery_artifact_sha256": discovery_artifact_sha256,
        "failure_class": failure_class,
        "candidate_status": candidate_status,
        "artifact_manifest_path": manifest_relative,
        "artifact_manifest_sha256": manifest_sha256,
        "experiment_id": experiment_id,
        "operator": operator,
    }
    row = {field: full_row[field] for field in attempt_header}
    if tuple(row) != attempt_header:
        raise D1ControlError("D1 terminal row differs from the tracked ledger schema")
    appended = append_llm_factor_attempt(path=ledger_path, **row)
    if not appended:
        raise D1ControlError("D1 attempt unexpectedly existed after the preflight check")
    parent_experiment_id = _experiment_id(parents[0]) if parents else ""
    experiment_row = {
        "experiment_id": experiment_id,
        "parent_experiment_id": parent_experiment_id,
        "ts": response.completed_at,
        "candidate_source": "LLM_DSL",
        "model_or_engine": protocol.requested_model,
        "engine_version": response.model,
        "seed": "",
        "prompt_hash": request_sha256,
        "code_sha256": resolved_code_sha256,
        "data_snapshot_sha256": resolved_data_sha256,
        "feature_or_formula": canonical_expression or f"D1_ATTEMPT:{plan.attempt_id}",
        "params_json": {
            "attempt_id": plan.attempt_id,
            "candidate_schema_sha256": candidate_schema_sha256(),
            "evolution_mode": plan.evolution_mode,
            "global_ordinal": plan.global_ordinal,
            "parent_attempt_ids": parents,
            "protocol_id": protocol.protocol_id,
            "protocol_sha256": protocol.sha256,
            "execution_release_id": execution_release_id,
            "execution_release_sha256": execution_release_sha256,
            "provider_mode": provider.mode,
            "response_sha256": response_sha256,
            "topic": plan.topic,
        },
        "train_period": "NOT_RUN_D1_GENERATION",
        "valid_period": "NOT_RUN_D1_GENERATION",
        "result_json": {
            "attempt_id": plan.attempt_id,
            "candidate_status": candidate_status,
            "failure_class": failure_class,
            "g1_run": False,
            "market_results_inspected": False,
            "protocol_id": protocol.protocol_id,
            "stage": (
                "D1_DISCOVERY_ONLY" if discovery_evaluator is not None else "D1_GENERATION_CONTRACT"
            ),
        },
        "admitted": False,
        "reject_reason": failure_class or "D1_GENERATION_ONLY_NOT_EVALUATED",
    }
    if not append_llm_factor_experiment(path=experiment_ledger_path, **experiment_row):
        raise D1ControlError("D1 experiment unexpectedly existed after the preflight check")
    _verify_experiment_link(row, _experiment_rows(experiment_ledger_path))
    return AttemptResult(row, reused=False, audit=audit)


def _tree_sha256(root: Path) -> str:
    entries = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        entries.append({"path": path.relative_to(root).as_posix(), "sha256": sha256_file(path)})
    return _sha256_text(_canonical_json(entries))


def run_fixture(protocol_path: Path, output_dir: Path) -> dict[str, Any]:
    from shaiwei.research.deepseek_client import run_mock_transport_fixture

    protocol = D1Protocol.load(protocol_path)
    ledger_path = output_dir / "ledger/llm_factor_attempts.csv"
    experiment_ledger_path = output_dir / "ledger/experiments.csv"
    artifact_root = output_dir / "artifacts"
    plan = plan_attempt(protocol, 1)
    proposal = {
        "schema_version": "d1-candidate-v1",
        "topic": plan.topic,
        "hypothesis": "过去二十日平均收盘价可作为平滑趋势状态的受限工程样本。",
        "expression": "Mean(close,20)",
        "expected_direction": "positive",
        "economic_rationale_draft": "该文本仅验证机器契约，不代表经济解释、研究结论或 G1 人工陈述。",
        "lineage": {"mode": "independent", "parent_attempt_ids": []},
        "known_failure_risks": ["synthetic_fixture_only"],
    }
    provider = MockProvider(
        [
            ProviderResponse(
                model=protocol.returned_model_identity,
                content=_canonical_json(proposal),
                reasoning_content="synthetic fixture reasoning; no external model was called",
                finish_reason="stop",
                usage={
                    "prompt_tokens": 800,
                    "prompt_cache_hit_tokens": 200,
                    "prompt_cache_miss_tokens": 600,
                    "completion_tokens": 120,
                },
                completed_at="2026-07-25T06:30:00+00:00",
            )
        ]
    )
    first = execute_completed_attempt(
        protocol,
        plan,
        provider,
        ledger_path=ledger_path,
        experiment_ledger_path=experiment_ledger_path,
        artifact_root=artifact_root,
        operator="docker-d1-fixture",
    )
    replay = execute_completed_attempt(
        protocol,
        plan,
        provider,
        ledger_path=ledger_path,
        experiment_ledger_path=experiment_ledger_path,
        artifact_root=artifact_root,
        operator="docker-d1-fixture",
    )
    rows = _attempt_rows(ledger_path)
    linkage = verify_attempt_experiment_bijection(ledger_path, experiment_ledger_path)
    transport_fixture = run_mock_transport_fixture(protocol, output_dir / "transport")
    fixture_pass = bool(
        len(rows) == 1
        and first.row["candidate_status"] == "CONTRACT_PASS"
        and first.row["parse_status"] == "PASS"
        and first.row["sandbox_status"] == "PASS"
        and replay.reused
        and provider.external_api_calls == 0
        and provider.responses_consumed == 1
        and linkage == {"attempt_rows": 1, "experiment_rows": 1}
        and transport_fixture["fixture_pass"]
    )
    return {
        "schema_version": "d1-preexecution-fixture-report-v1",
        "fixture_pass": fixture_pass,
        "protocol_id": protocol.protocol_id,
        "protocol_sha256": protocol.sha256,
        "prompt_bundle_sha256": protocol.prompt_bundle.sha256,
        "knowledge_manifest_sha256": protocol.knowledge_manifest.sha256,
        "candidate_schema_sha256": candidate_schema_sha256(),
        "attempt_id": plan.attempt_id,
        "attempt_rows": len(rows),
        "experiment_rows": linkage["experiment_rows"],
        "ledger_one_to_one": linkage["attempt_rows"] == linkage["experiment_rows"],
        "candidate_status": first.row["candidate_status"],
        "parse_status": first.row["parse_status"],
        "sandbox_status": first.row["sandbox_status"],
        "idempotent_replay": replay.reused,
        "mock_responses_consumed": provider.responses_consumed,
        "external_api_calls": provider.external_api_calls,
        "live_execution_authorized": False,
        "mock_transport_fixture": transport_fixture,
        "real_market_data_read": False,
        "g1_run": False,
        "production_authorization": "none",
        "artifact_tree_sha256": _tree_sha256(output_dir),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", action="store_true")
    parser.add_argument(
        "--protocol",
        type=Path,
        default=PROJECT_ROOT / "config/d1_llm_factor_research_v1.yaml",
    )
    parser.add_argument("--output-dir", type=Path, default=Path("/tmp/shaiwei-d1-fixture"))
    args = parser.parse_args(argv)
    if not args.fixture:
        parser.error("D1-2A exposes only --fixture; real provider execution is not authorized")
    report = run_fixture(args.protocol, args.output_dir)
    print(_canonical_json(report))
    return 0 if report["fixture_pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
