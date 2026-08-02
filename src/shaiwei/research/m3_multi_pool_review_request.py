"""Result-blind request builder and response validator for M3-3 reviews."""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any, Mapping

from shaiwei.research.llm_factor import D1ControlError
from shaiwei.research.llm_review_semantics import SemanticGateResult, evaluate_semantic_contract
from shaiwei.research.m3_multi_pool_review_contract import (
    DEFAULT_PROTOCOL_PATH,
    M3ReviewProtocol,
    ReviewPlan,
    canonical_json,
    sha256_text,
)
from shaiwei.research.m3_multi_pool_review_schema import M3ReviewResponse, M3_REVIEW_ROLES


def plan_review(protocol: M3ReviewProtocol, ordinal: int) -> ReviewPlan:
    if not 1 <= ordinal <= 8:
        raise D1ControlError("M3-3 review ordinal must be 1..8")
    candidate = protocol.candidates[(ordinal - 1) // len(M3_REVIEW_ROLES)]
    role = M3_REVIEW_ROLES[(ordinal - 1) % len(M3_REVIEW_ROLES)]
    identity = f"{protocol.document['protocol_id']}:{candidate.candidate_id}:{role}"
    return ReviewPlan(sha256_text(identity)[:20], ordinal, candidate, role)


def _assert_result_blind(value: object) -> None:
    forbidden = {
        "discovery_rank_ic",
        "discovery_coverage",
        "discovery_rank",
        "cross_pool_score",
        "secondary_score",
        "minimum_coverage",
        "discovery_artifact",
        "validation_result",
        "stress_result",
        "g1_result",
        "forward_result",
        "returns",
        "holdings",
        "security_list",
        "market_rows",
        "api_key",
    }
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).lower() in forbidden:
                raise D1ControlError(f"M3-3 request contains forbidden field: {key}")
            _assert_result_blind(child)
    elif isinstance(value, list):
        for child in value:
            _assert_result_blind(child)
    elif isinstance(value, str):
        lowered = value.lower()
        if any(token in lowered for token in ("rankic=", "rank_ic=", "validation_result=")):
            raise D1ControlError("M3-3 request contains forbidden result text")
        if re.search(r"/(?:Users|private|workspace)/", value):
            raise D1ControlError("M3-3 request contains a local absolute path")
        if re.search(r"\b\d{6}\.(?:SH|SZ|BJ)\b", value):
            raise D1ControlError("M3-3 request contains a security identifier")


def build_review_request(protocol: M3ReviewProtocol, plan: ReviewPlan) -> dict[str, Any]:
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
        "pool_context": protocol.document["pool_context"],
        "assigned_role": plan.role,
        "role_instruction": protocol.prompt_document["roles"][plan.role],
        "execution_clock": "signal-day fields are available after close; earliest trade is next official open",
        "response_schema": M3ReviewResponse.model_json_schema(),
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
    if len(canonical_json(request).encode("utf-8")) + 1024 > int(
        protocol.document["provider"]["maximum_prompt_tokens_per_attempt"]
    ):
        raise D1ControlError("M3-3 request exceeds its conservative input bound")
    return request


def validate_review_document(
    protocol: M3ReviewProtocol, plan: ReviewPlan, document: Mapping[str, Any]
) -> tuple[M3ReviewResponse, SemanticGateResult]:
    review = M3ReviewResponse.model_validate(document)
    if review.candidate_id != plan.candidate.candidate_id or review.role != plan.role:
        raise ValueError("M3-3 review response identity differs")
    semantic = evaluate_semantic_contract(
        document, allowed_formulas=[candidate.formula for candidate in protocol.candidates]
    )
    return review, semantic


def preflight(protocol_path: Path = DEFAULT_PROTOCOL_PATH) -> dict[str, Any]:
    protocol = M3ReviewProtocol.load(protocol_path)
    requests = [build_review_request(protocol, plan_review(protocol, index)) for index in range(1, 9)]
    return {
        "protocol_id": protocol.document["protocol_id"],
        "protocol_sha256": protocol.sha256,
        "candidate_count": len(protocol.candidates),
        "review_count": len(requests),
        "request_bundle_sha256": sha256_text(canonical_json(requests)),
        "semantic_gate_sha256": protocol.semantic_protocol.sha256,
        "worst_case_batch_cost_usd": float(
            protocol.document["cost_budget"]["planned_worst_case_all_cache_miss_usd"]
        ),
        "discovery_metric_fields_parsed": False,
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
        print(canonical_json({"preflight_gate": "FAIL", "error_class": "M3ReviewContractError"}))
        return 2
    print(canonical_json(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
