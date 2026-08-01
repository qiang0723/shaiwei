"""Frozen input and request contract for M1-2 STAR50 factor review."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import yaml

from shaiwei.config import PROJECT_ROOT
from shaiwei.ledger import sha256_file
from shaiwei.research.alphagen_expression import audit_expression
from shaiwei.research.llm_factor import D1ControlError
from shaiwei.research.llm_review_semantics import (
    SemanticGateProtocol,
    SemanticGateResult,
    evaluate_semantic_contract,
)
from shaiwei.research.m1_star50_review_schema import M1ReviewResponse


ROLES = (
    "construct_and_units",
    "economic_direction",
    "pit_and_numerical_stability",
    "redundancy_and_falsifiability",
)
CANDIDATE_IDS = ("5c3c30d8b3a01f76", "47f690ef14487a25")
DEFAULT_PROTOCOL_PATH = PROJECT_ROOT / "config/m1_star50_factor_review_v1.yaml"
DEFAULT_RELEASE_PATH = PROJECT_ROOT / "config/m1_star50_factor_review_execution_v1.yaml"


def canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def project_path(value: str | Path, *, label: str) -> Path:
    relative = Path(value)
    if relative.is_absolute():
        raise D1ControlError(f"M1-2 {label} must be project-relative")
    candidate = (PROJECT_ROOT / relative).resolve()
    if not candidate.is_relative_to(PROJECT_ROOT.resolve()):
        raise D1ControlError(f"M1-2 {label} escapes the project")
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


def _load_mapping(path: Path, *, label: str) -> dict[str, Any]:
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise D1ControlError(f"M1-2 {label} is missing") from error
    if not isinstance(document, dict):
        raise D1ControlError(f"M1-2 {label} must be an object")
    return document


def _verify_hash(binding: Mapping[str, Any], stem: str) -> Path:
    path = project_path(str(binding.get(f"{stem}_path", "")), label=stem)
    if sha256_file(path) != binding.get(f"{stem}_sha256"):
        raise D1ControlError(f"M1-2 {stem} hash differs")
    return path


@dataclass(frozen=True)
class M1ReviewProtocol:
    path: Path
    document: dict[str, Any]
    sha256: str
    prompt_document: dict[str, Any]
    prompt_sha256: str
    semantic_protocol: SemanticGateProtocol
    candidates: tuple[CandidateBinding, ...]

    @property
    def provider_name(self) -> str:
        return str(self.document["provider"]["provider"])

    @property
    def requested_model(self) -> str:
        return str(self.document["provider"]["model"])

    @property
    def maximum_output_tokens(self) -> int:
        return int(self.document["provider"]["maximum_output_tokens"])

    @classmethod
    def load(cls, path: Path = DEFAULT_PROTOCOL_PATH) -> "M1ReviewProtocol":
        document = _load_mapping(path, label="protocol")
        if (
            document.get("schema_version") != "m1-star50-factor-review-protocol-v1"
            or document.get("protocol_id") != "m1-star50-price-volume-review-v1"
            or document.get("status")
            != "M1_2_RESULT_BLIND_REVIEW_PROTOCOL_FROZEN_EXECUTION_NOT_RELEASED"
            or document.get("execution_authorized") is not False
            or document.get("production_authorization") != "none"
        ):
            raise D1ControlError("M1-2 protocol identity differs")
        source = document.get("source_binding", {})
        manifest_path = _verify_hash(source, "discovery_manifest")
        _verify_hash(source, "discovery_report")
        _verify_hash(source, "attempt_ledger")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        selected = manifest.get("mechanical_top2", [])
        if (
            manifest.get("verdict") != "GO_DISCOVERY_TOP2_LOCKED"
            or manifest.get("completed_response_count") != 40
            or manifest.get("selected_count") != 2
            or [item.get("attempt_id") for item in selected] != list(CANDIDATE_IDS)
        ):
            raise D1ControlError("M1-2 discovery source is ineligible")

        prompt = document.get("prompt", {})
        prompt_path = project_path(str(prompt.get("path", "")), label="prompt")
        if sha256_file(prompt_path) != prompt.get("sha256"):
            raise D1ControlError("M1-2 prompt hash differs")
        prompt_document = _load_mapping(prompt_path, label="prompt")
        if (
            prompt_document.get("schema_version") != prompt.get("schema_version")
            or prompt_document.get("prompt_id") != prompt.get("prompt_id")
        ):
            raise D1ControlError("M1-2 prompt identity differs")
        semantic = document.get("semantic_gate", {})
        semantic_path = project_path(str(semantic.get("protocol_path", "")), label="semantic protocol")
        if sha256_file(semantic_path) != semantic.get("protocol_sha256"):
            raise D1ControlError("M1-2 semantic protocol hash differs")
        semantic_protocol = SemanticGateProtocol.load(semantic_path)
        knowledge = document.get("knowledge_binding", {})
        knowledge_path = project_path(str(knowledge.get("path", "")), label="knowledge")
        if sha256_file(knowledge_path) != knowledge.get("sha256"):
            raise D1ControlError("M1-2 knowledge hash differs")

        raw_candidates = document.get("candidates", [])
        if [item.get("candidate_id") for item in raw_candidates] != list(CANDIDATE_IDS):
            raise D1ControlError("M1-2 candidate order differs")
        bindings: list[CandidateBinding] = []
        selected_by_id = {item["attempt_id"]: item for item in selected}
        for item in raw_candidates:
            candidate_id = str(item["candidate_id"])
            source_item = selected_by_id.get(candidate_id)
            if source_item is None or any(
                source_item.get(key) != item.get(key)
                for key in ("global_ordinal", "topic", "expression_sha256")
            ):
                raise D1ControlError("M1-2 candidate differs from mechanical Top2")
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
                or proposal.get("expected_direction") != item.get("expected_direction")
                or not audit.pit_sentinel_pass
                or not audit.shift_sentinel_pass
            ):
                raise D1ControlError("M1-2 frozen formula identity or PIT gate differs")
            bindings.append(
                CandidateBinding(
                    candidate_id=candidate_id,
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
        _validate_protocol_controls(document)
        return cls(
            path=path,
            document=document,
            sha256=sha256_file(path),
            prompt_document=prompt_document,
            prompt_sha256=sha256_file(prompt_path),
            semantic_protocol=semantic_protocol,
            candidates=tuple(bindings),
        )


def _validate_protocol_controls(document: Mapping[str, Any]) -> None:
    schedule = document.get("review_schedule", {})
    if (
        schedule.get("candidate_order") != list(CANDIDATE_IDS)
        or schedule.get("role_order") != list(ROLES)
        or schedule.get("completed_responses_exact") != 8
        or schedule.get("invalid_response_replacement") is not False
    ):
        raise D1ControlError("M1-2 review schedule differs")
    blindness = document.get("blindness", {})
    forbidden = (
        "discovery_rank_ic_visible_to_reviewers",
        "discovery_coverage_visible_to_reviewers",
        "discovery_ordering_score_visible_to_reviewers",
        "sealed_validation_visible",
        "stress_results_visible",
        "g1_results_visible",
        "forward_results_visible",
        "production_results_visible",
    )
    contamination = blindness.get("primary_window_contamination", {})
    if (
        any(blindness.get(key) is not False for key in forbidden)
        or blindness.get("deepseek_payloads_are_result_blind") is not True
        or blindness.get("primary_window_may_adjudicate_review") is not False
        or contamination.get("candidate_ids") != list(CANDIDATE_IDS)
        or contamination.get("exposed_values_must_not_be_repeated_or_exported") is not True
    ):
        raise D1ControlError("M1-2 blindness or contamination boundary differs")


def plan_review(protocol: M1ReviewProtocol, ordinal: int) -> ReviewPlan:
    if not 1 <= ordinal <= 8:
        raise D1ControlError("M1-2 review ordinal must be 1..8")
    candidate = protocol.candidates[(ordinal - 1) // len(ROLES)]
    role = ROLES[(ordinal - 1) % len(ROLES)]
    identity = f"{protocol.document['protocol_id']}:{candidate.candidate_id}:{role}"
    return ReviewPlan(sha256_text(identity)[:20], ordinal, candidate, role)


def _assert_result_blind(value: object) -> None:
    forbidden_keys = {
        "discovery_rank_ic",
        "discovery_coverage",
        "discovery_rank",
        "validation_result",
        "stress_result",
        "g1_result",
        "forward_result",
        "returns",
        "holdings",
        "api_key",
    }
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).lower() in forbidden_keys:
                raise D1ControlError(f"M1-2 request contains forbidden field: {key}")
            _assert_result_blind(child)
    elif isinstance(value, list):
        for child in value:
            _assert_result_blind(child)
    elif isinstance(value, str) and any(
        token in value.lower() for token in ("rankic=", "rank_ic=", "validation_result=")
    ):
        raise D1ControlError("M1-2 request contains forbidden result text")


def build_review_request(protocol: M1ReviewProtocol, plan: ReviewPlan) -> dict[str, Any]:
    peer = next(item for item in protocol.candidates if item != plan.candidate)
    task = {
        "candidate": {
            "candidate_id": plan.candidate.candidate_id,
            "frozen_formula": plan.candidate.formula,
            "frozen_expected_direction": plan.candidate.expected_direction,
            "non_authoritative_hypothesis": plan.candidate.original_hypothesis,
            "non_authoritative_rationale": plan.candidate.original_rationale,
            "research_context": list(plan.candidate.research_context),
            "expression_tokens": plan.candidate.expression_tokens,
            "ast_nodes": plan.candidate.ast_nodes,
            "max_lookback_days": plan.candidate.max_lookback_days,
        },
        "peer_for_redundancy_only": {
            "candidate_id": peer.candidate_id,
            "frozen_formula": peer.formula,
        },
        "assigned_role": plan.role,
        "role_instruction": protocol.prompt_document["roles"][plan.role],
        "execution_clock": "signal-day fields are available after close; earliest trade is next official open",
        "response_schema": M1ReviewResponse.model_json_schema(),
        "constraints": {
            "reject_as_is_instead_of_repair": True,
            "no_formula_direction_or_window_change": True,
            "no_new_candidate_or_variant": True,
            "no_performance_or_admission_inference": True,
            "english_output_only": True,
        },
    }
    request = {
        "model": protocol.requested_model,
        "messages": [
            {"role": "system", "content": protocol.prompt_document["system_prompt"]},
            {"role": "user", "content": canonical_json(task)},
        ],
        "thinking": {"type": protocol.document["provider"]["thinking"]},
        "reasoning_effort": protocol.document["provider"]["reasoning_effort"],
        "response_format": {"type": protocol.document["provider"]["response_format"]},
        "max_tokens": protocol.maximum_output_tokens,
        "tools": [],
        "stream": False,
    }
    _assert_result_blind(request)
    serialized = canonical_json(request)
    if len(serialized.encode("utf-8")) + 1024 > int(
        protocol.document["provider"]["maximum_prompt_tokens_per_attempt"]
    ):
        raise D1ControlError("M1-2 request exceeds its conservative input bound")
    return request


def validate_review_document(
    protocol: M1ReviewProtocol, plan: ReviewPlan, document: Mapping[str, Any]
) -> tuple[M1ReviewResponse, SemanticGateResult]:
    review = M1ReviewResponse.model_validate(document)
    if review.candidate_id != plan.candidate.candidate_id or review.role != plan.role:
        raise ValueError("M1-2 review response identity differs")
    semantic = evaluate_semantic_contract(
        document, allowed_formulas=[candidate.formula for candidate in protocol.candidates]
    )
    return review, semantic


def worst_case_cost(protocol: M1ReviewProtocol) -> float:
    provider = protocol.document["provider"]
    prices = protocol.document["cost_budget"]
    return (
        int(provider["maximum_prompt_tokens_per_attempt"])
        * float(prices["pro_input_cache_miss_per_million"])
        + int(provider["maximum_output_tokens"])
        * float(prices["pro_output_per_million"])
    ) / 1_000_000


def preflight(protocol_path: Path = DEFAULT_PROTOCOL_PATH) -> dict[str, Any]:
    protocol = M1ReviewProtocol.load(protocol_path)
    requests = [build_review_request(protocol, plan_review(protocol, ordinal)) for ordinal in range(1, 9)]
    return {
        "protocol_id": protocol.document["protocol_id"],
        "protocol_sha256": protocol.sha256,
        "candidate_count": len(protocol.candidates),
        "review_count": len(requests),
        "request_bundle_sha256": sha256_text(canonical_json(requests)),
        "semantic_gate_sha256": protocol.semantic_protocol.sha256,
        "worst_case_batch_cost_usd": worst_case_cost(protocol) * len(requests),
        "discovery_metrics_read": False,
        "sealed_validation_read": False,
        "provider_calls": 0,
        "preflight_gate": "PASS",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL_PATH)
    args = parser.parse_args(argv)
    try:
        report = preflight(args.protocol)
    except (D1ControlError, OSError, TypeError, ValueError):
        print(canonical_json({"preflight_gate": "FAIL", "error_class": "M1ReviewContractError"}))
        return 2
    print(canonical_json(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
