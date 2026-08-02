"""Frozen, result-blind input and request contract for M3-3 reviews."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import yaml

from shaiwei.config import PROJECT_ROOT
from shaiwei.ledger import sha256_file
from shaiwei.research.alphagen_expression import audit_expression
from shaiwei.research.llm_factor import D1ControlError
from shaiwei.research.llm_review_semantics import SemanticGateProtocol
from shaiwei.research.m3_multi_pool_review_schema import M3_REVIEW_ROLES


CANDIDATE_IDS = ("f6fd83e97bad3114", "ca552f379c62504d")
DEFAULT_PROTOCOL_PATH = PROJECT_ROOT / "config/m3_multi_pool_factor_review_v1.yaml"
DEFAULT_RELEASE_PATH = PROJECT_ROOT / "config/m3_multi_pool_factor_review_execution_v1.yaml"


def canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def project_path(value: str | Path, *, label: str, must_exist: bool = True) -> Path:
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts:
        raise D1ControlError(f"M3-3 {label} must be project-relative")
    candidate = (PROJECT_ROOT / relative).resolve()
    if not candidate.is_relative_to(PROJECT_ROOT.resolve()):
        raise D1ControlError(f"M3-3 {label} escapes the project")
    if must_exist and not candidate.is_file():
        raise D1ControlError(f"M3-3 {label} is missing")
    return candidate


@dataclass(frozen=True)
class CandidateBinding:
    candidate_id: str
    global_ordinal: int
    topic: str
    formula: str
    expression_sha256: str
    expression_tokens: int
    ast_nodes: int
    max_lookback_days: int
    expected_direction: str
    original_hypothesis: str
    original_rationale: str
    research_context: tuple[str, ...]


@dataclass(frozen=True)
class ReviewPlan:
    review_id: str
    review_ordinal: int
    candidate: CandidateBinding
    role: str


def _load_yaml(path: Path, *, label: str) -> dict[str, Any]:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise D1ControlError(f"M3-3 {label} is missing") from error
    if not isinstance(value, dict):
        raise D1ControlError(f"M3-3 {label} must be an object")
    return value


def _verify_hash(binding: Mapping[str, Any], stem: str) -> Path:
    path = project_path(str(binding.get(f"{stem}_path", "")), label=stem)
    if sha256_file(path) != binding.get(f"{stem}_sha256"):
        raise D1ControlError(f"M3-3 {stem} hash differs")
    return path


@dataclass(frozen=True)
class M3ReviewProtocol:
    path: Path
    document: dict[str, Any]
    sha256: str
    prompt_document: dict[str, Any]
    prompt_sha256: str
    semantic_protocol: SemanticGateProtocol
    candidates: tuple[CandidateBinding, ...]

    @property
    def requested_model(self) -> str:
        return str(self.document["provider"]["model"])

    @property
    def maximum_output_tokens(self) -> int:
        return int(self.document["provider"]["maximum_output_tokens"])

    @classmethod
    def load(cls, path: Path = DEFAULT_PROTOCOL_PATH) -> "M3ReviewProtocol":
        document = _load_yaml(path, label="protocol")
        _validate_identity(document)
        source = document["source_binding"]
        for stem in (
            "discovery_manifest",
            "discovery_report",
            "discovery_live_context",
            "discovery_attempt_ledger",
        ):
            _verify_hash(source, stem)
        prompt = document["prompt"]
        prompt_path = project_path(prompt["path"], label="prompt")
        if sha256_file(prompt_path) != prompt["sha256"]:
            raise D1ControlError("M3-3 prompt hash differs")
        prompt_document = _load_yaml(prompt_path, label="prompt")
        if (
            prompt_document.get("schema_version") != prompt["schema_version"]
            or prompt_document.get("prompt_id") != prompt["prompt_id"]
        ):
            raise D1ControlError("M3-3 prompt identity differs")
        semantic = document["semantic_gate"]
        semantic_path = project_path(semantic["protocol_path"], label="semantic protocol")
        if sha256_file(semantic_path) != semantic["protocol_sha256"]:
            raise D1ControlError("M3-3 semantic protocol hash differs")
        knowledge = document["knowledge_binding"]
        if sha256_file(project_path(knowledge["path"], label="knowledge")) != knowledge["sha256"]:
            raise D1ControlError("M3-3 knowledge hash differs")
        candidates = _load_candidates(document)
        _validate_controls(document)
        return cls(
            path=path,
            document=document,
            sha256=sha256_file(path),
            prompt_document=prompt_document,
            prompt_sha256=sha256_file(prompt_path),
            semantic_protocol=SemanticGateProtocol.load(semantic_path),
            candidates=candidates,
        )


def _validate_identity(document: Mapping[str, Any]) -> None:
    if (
        document.get("schema_version") != "m3-multi-pool-factor-review-protocol-v1"
        or document.get("protocol_id") != "m3-star-three-pool-price-volume-review-v1"
        or document.get("status")
        != "M3_3_RESULT_BLIND_REVIEW_PROTOCOL_FROZEN_EXECUTION_NOT_RELEASED"
        or document.get("execution_authorized") is not False
        or document.get("strategy_effective") != "NOT_EVALUATED"
        or document.get("production_authorization") != "none"
    ):
        raise D1ControlError("M3-3 protocol identity differs")


def _load_candidates(document: Mapping[str, Any]) -> tuple[CandidateBinding, ...]:
    items = document.get("candidates", [])
    if [item.get("candidate_id") for item in items] != list(CANDIDATE_IDS):
        raise D1ControlError("M3-3 candidate order differs")
    output: list[CandidateBinding] = []
    for item in items:
        raw_path = _verify_hash(item, "raw_artifact")
        _verify_hash(item, "artifact_manifest")
        envelope = json.loads(raw_path.read_text(encoding="utf-8"))
        proposal = json.loads(str(envelope["content"]))
        audit = audit_expression(str(proposal["expression"]))
        if (
            audit.normalized_expression != item.get("formula")
            or sha256_text(audit.normalized_expression) != item.get("expression_sha256")
            or audit.expression_tokens != item.get("expression_tokens")
            or audit.ast_nodes != item.get("ast_nodes")
            or audit.max_lookback_days != item.get("max_lookback_days")
            or proposal.get("topic") != item.get("topic")
            or proposal.get("expected_direction") != item.get("expected_direction")
            or proposal.get("hypothesis") != item.get("original_hypothesis")
            or not audit.pit_sentinel_pass
            or not audit.shift_sentinel_pass
        ):
            raise D1ControlError("M3-3 frozen formula identity or PIT gate differs")
        output.append(
            CandidateBinding(
                candidate_id=str(item["candidate_id"]),
                global_ordinal=int(item["global_ordinal"]),
                topic=str(item["topic"]),
                formula=str(item["formula"]),
                expression_sha256=str(item["expression_sha256"]),
                expression_tokens=int(item["expression_tokens"]),
                ast_nodes=int(item["ast_nodes"]),
                max_lookback_days=int(item["max_lookback_days"]),
                expected_direction=str(item["expected_direction"]),
                original_hypothesis=str(item["original_hypothesis"]),
                original_rationale=str(item["original_rationale"]),
                research_context=tuple(map(str, item["research_context"])),
            )
        )
    return tuple(output)


def _validate_controls(document: Mapping[str, Any]) -> None:
    source = document["source_binding"]
    schedule = document["review_schedule"]
    scope = document["scope"]
    blindness = document["blindness"]
    decision = document["decision_rule"]
    complexity = document["complexity_contract"]
    false_scope = {key for key, value in scope.items() if isinstance(value, bool)}
    if any(scope[key] is not False for key in false_scope):
        raise D1ControlError("M3-3 scope expands beyond result-blind review")
    if (
        source.get("completed_responses_exact") != 24
        or source.get("selected_count_exact") != 2
        or source.get("selection_rule_reopened") is not False
        or source.get("rejected_candidate_replacement_allowed") is not False
        or schedule.get("candidate_order") != list(CANDIDATE_IDS)
        or tuple(schedule.get("role_order", ())) != M3_REVIEW_ROLES
        or schedule.get("completed_responses_exact") != 8
        or schedule.get("concurrency") != 1
        or schedule.get("invalid_response_replacement") is not False
        or schedule.get("blocker_finding_early_stop") is not False
        or schedule.get("invalid_contract_early_stop") is not True
    ):
        raise D1ControlError("M3-3 source or review schedule differs")
    forbidden_visibility = (
        "discovery_rank_ic_visible_to_reviewers",
        "discovery_coverage_visible_to_reviewers",
        "discovery_ordering_score_visible_to_reviewers",
        "sealed_validation_visible",
        "stress_results_visible",
        "g1_results_visible",
        "forward_results_visible",
        "production_results_visible",
    )
    if (
        any(blindness.get(key) is not False for key in forbidden_visibility)
        or blindness.get("deepseek_payloads_are_result_blind") is not True
        or blindness.get("primary_window_may_adjudicate_review") is not False
        or blindness.get("result_blind_committee_is_the_only_review_authority") is not True
        or complexity.get("frozen_attempt_ledger_values_must_be_reused") is not True
        or decision.get("all_8_schema_and_semantic_valid_required") is not True
        or decision.get("rejected_candidate_is_not_repaired_or_replaced") is not True
    ):
        raise D1ControlError("M3-3 blindness, complexity, or decision boundary differs")
    _validate_cost(document)


def _validate_cost(document: Mapping[str, Any]) -> None:
    provider = document["provider"]
    cost = document["cost_budget"]
    planned = (
        int(provider["maximum_prompt_tokens_per_attempt"])
        * float(cost["pro_input_cache_miss_per_million"])
        + int(provider["maximum_output_tokens"])
        * float(cost["pro_output_per_million"])
    ) * 8 / 1_000_000
    if (
        provider.get("provider") != "deepseek"
        or provider.get("model") != "deepseek-v4-pro"
        or provider.get("thinking") != "enabled"
        or provider.get("reasoning_effort") != "high"
        or not math.isclose(planned, float(cost["planned_worst_case_all_cache_miss_usd"]))
        or planned > float(cost["review_hard_ceiling_usd"])
    ):
        raise D1ControlError("M3-3 provider or cost contract differs")
