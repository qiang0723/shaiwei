"""Zero-network M3-1 pre-execution gate using only upstream identity and synthetic data."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from shaiwei.config import PROJECT_ROOT
from shaiwei.provenance import code_snapshot_sha256, git_head
from shaiwei.research.llm_factor import CandidateProposal, D1ControlError
from shaiwei.research.m3_multi_pool_contract import M3Protocol, POOL_IDS, verify_m3_inputs
from shaiwei.research.m3_multi_pool_evaluation import (
    evaluate_cross_pool_candidate,
    rank_candidates,
    synthetic_three_pool_frames,
    validate_m3_candidate_semantics,
)


DEFAULT_PROTOCOL = PROJECT_ROOT / "config/m3_multi_pool_factor_research_v1.yaml"


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _proposal(**updates: object) -> CandidateProposal:
    payload: dict[str, object] = {
        "schema_version": "d1-candidate-v1",
        "topic": "trend_momentum",
        "hypothesis": "历史价格路径的平滑状态可能包含尚未完全消化的横截面趋势信息。",
        "expression": "Mean(close,5)",
        "expected_direction": "positive",
        "economic_rationale_draft": "该唯一表达式只刻画历史价格状态，并在三个自建研究池保持同一定义。",
        "lineage": {"mode": "independent", "parent_attempt_ids": []},
        "known_failure_risks": ["cross_segment_instability"],
    }
    payload.update(updates)
    return CandidateProposal.model_validate(payload)


def run_preexecution(
    protocol_path: Path = DEFAULT_PROTOCOL,
    *,
    project_root: Path = PROJECT_ROOT,
) -> dict[str, Any]:
    protocol = M3Protocol.load(protocol_path, project_root=project_root)
    identity = verify_m3_inputs(protocol, project_root=project_root)
    good = _proposal()
    if validate_m3_candidate_semantics(good) is not None:
        raise D1ControlError("M3-1 compliant semantic fixture was rejected")
    bad = _proposal(
        economic_rationale_draft="全市场采用正向，而小盘单独翻转为负向以改善分池表现。"
    )
    if validate_m3_candidate_semantics(bad) != "pool_specific_formula_or_direction":
        raise D1ControlError("M3-1 pool-specific semantic fixture did not fail closed")
    expressions = ("Mean(close,5)", "EMA(close,8)")
    candidates = [
        evaluate_cross_pool_candidate(
            expression,
            synthetic_three_pool_frames(expression),
            protocol,
            global_ordinal=ordinal,
        )
        for ordinal, expression in enumerate(expressions, start=1)
    ]
    promoted = rank_candidates(
        candidates,
        promoted_count=int(protocol.document["discovery_evaluation"]["promoted_count"]),
    )
    if len(promoted) != 2 or any(not candidate.eligible for candidate in candidates):
        raise D1ControlError("M3-1 cross-pool synthetic selection did not produce two eligible fixtures")
    feedback = protocol.prompt_bundle.serialize_feedback(
        topic="trend_momentum",
        current_global_ordinal=7,
        records=[
            {
                "attempt_id": "fixture-001",
                "global_ordinal": 1,
                "topic": "trend_momentum",
                "parse_status": "PASS",
                "sandbox_status": "PASS",
                "semantic_status": "PASS",
                "canonical_expression": promoted[0].normalized_expression,
                "failure_class": "",
                "cross_pool_min_coverage": promoted[0].minimum_coverage,
                "cross_pool_worst_directed_rank_ic": promoted[0].cross_pool_score,
                "cross_pool_median_directed_rank_ic": promoted[0].secondary_score,
                "expression_tokens": promoted[0].audit.expression_tokens,
                "ast_nodes": promoted[0].audit.ast_nodes,
                "max_lookback_days": promoted[0].audit.max_lookback_days,
            }
        ],
    )
    attempt_budget = int(protocol.document["attempt_budget"]["completed_llm_responses_exact"])
    pool_count = len(POOL_IDS)
    evaluation_cells = attempt_budget * pool_count
    if evaluation_cells != int(protocol.document["attempt_budget"]["cross_pool_evaluation_cells_exact"]):
        raise D1ControlError("M3-1 attempt and evaluation-cell accounting differs")
    body = {
        "schema_version": "m3-multi-pool-factor-preexecution-report-v1",
        "verdict": "GO_M3_1_PREEXECUTION_ONLY",
        "protocol_sha256": protocol.sha256,
        "release_git_head": git_head(),
        "code_snapshot_sha256": code_snapshot_sha256(),
        "input_snapshot_sha256": identity.snapshot_sha256,
        "membership_sha256": identity.membership_sha256,
        "membership_rows": identity.full_rows,
        "discovery_trade_days": identity.discovery_trade_days,
        "discovery_rows": identity.discovery_rows,
        "sealed_membership_trade_days_verified_without_factor_access": identity.sealed_trade_days,
        "synthetic_fixture": {
            "candidate_count": len(candidates),
            "eligible_count": sum(candidate.eligible for candidate in candidates),
            "promoted_count": len(promoted),
            "semantic_pass_fixture": True,
            "pool_specific_semantic_rejection_fixture": True,
            "dsl_pit_shift_pass": all(
                candidate.audit.pit_sentinel_pass and candidate.audit.shift_sentinel_pass
                for candidate in candidates
            ),
            "direction_anchor_and_cross_pool_positive_pass": all(
                candidate.direction in {-1, 1}
                and len(candidate.directed_rank_ic) == 3
                and min(candidate.directed_rank_ic.values()) > 0
                for candidate in candidates
            ),
            "feedback_record_count": len(feedback),
            "completed_response_budget": attempt_budget,
            "cross_pool_evaluation_cells": evaluation_cells,
            "effective_related_trial_count": int(
                protocol.document["multiple_testing_contract"][
                    "effective_trial_count_after_complete_batch"
                ]
            ),
        },
        "real_candidate_count": 0,
        "real_factor_results_inspected": False,
        "sealed_factor_results_inspected": False,
        "provider_calls": 0,
        "api_key_read": False,
        "model_or_portfolio_run": False,
        "production_authorization": "none",
        "strategy_effective": "NOT_EVALUATED",
    }
    return {
        **body,
        "report_sha256": hashlib.sha256(_canonical_json(body).encode("utf-8")).hexdigest(),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    args = parser.parse_args(argv)
    try:
        report = run_preexecution(args.protocol)
    except (D1ControlError, OSError, RuntimeError, TypeError, ValueError) as error:
        print(_canonical_json({"status": "FAIL", "error_class": type(error).__name__}))
        return 2
    print(_canonical_json(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
