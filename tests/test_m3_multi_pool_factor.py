from __future__ import annotations

import copy
import json
from dataclasses import replace
from pathlib import Path

import pytest
import yaml

from shaiwei.config import PROJECT_ROOT
from shaiwei.research.llm_factor import CandidateProposal, D1ControlError
from shaiwei.research.m3_multi_pool_contract import (
    M3Protocol,
    POOL_IDS,
    verify_m3_inputs,
)
from shaiwei.research.m3_multi_pool_evaluation import (
    evaluate_cross_pool_candidate,
    rank_candidates,
    synthetic_three_pool_frames,
    validate_m3_candidate_semantics,
)
from shaiwei.research.m3_multi_pool_preexecution import run_preexecution


PROTOCOL_PATH = PROJECT_ROOT / "config/m3_multi_pool_factor_research_v1.yaml"


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


def test_protocol_freezes_zero_execution_and_global_attempt_accounting():
    protocol = M3Protocol.load(PROTOCOL_PATH)
    document = protocol.document
    assert document["execution_authorized"] is False
    assert document["llm_api_called"] is False
    assert document["factor_results_inspected"] is False
    assert document["attempt_budget"]["completed_llm_responses_exact"] == 24
    assert document["attempt_budget"]["cross_pool_evaluation_cells_exact"] == 72
    assert document["multiple_testing_contract"]["prior_related_trial_count"] == 246
    assert document["multiple_testing_contract"]["effective_trial_count_after_complete_batch"] == 270


def test_prompt_feedback_is_same_topic_bounded_and_allowlisted():
    protocol = M3Protocol.load(PROTOCOL_PATH)
    record = {
        "attempt_id": "fixture-1",
        "global_ordinal": 1,
        "topic": "trend_momentum",
        "parse_status": "PASS",
        "sandbox_status": "PASS",
        "semantic_status": "PASS",
        "canonical_expression": "Mean($close,5d)",
        "failure_class": "",
        "cross_pool_min_coverage": 1.0,
        "cross_pool_worst_directed_rank_ic": 0.01,
        "cross_pool_median_directed_rank_ic": 0.02,
        "expression_tokens": 3,
        "ast_nodes": 3,
        "max_lookback_days": 5,
    }
    assert protocol.prompt_bundle.serialize_feedback(
        topic="trend_momentum", current_global_ordinal=2, records=[record]
    )[0]["attempt_id"] == "fixture-1"
    with pytest.raises(D1ControlError, match="non-allowlisted"):
        protocol.prompt_bundle.serialize_feedback(
            topic="trend_momentum",
            current_global_ordinal=2,
            records=[{**record, "sealed_validation": 0.9}],
        )


def test_semantic_gate_rejects_pool_specific_formula_or_direction():
    assert validate_m3_candidate_semantics(_proposal()) is None
    bad = _proposal(
        economic_rationale_draft="全市场采用正向，而小盘单独翻转为负向以改善分池表现。"
    )
    assert validate_m3_candidate_semantics(bad) == "pool_specific_formula_or_direction"


def test_real_dsl_runs_on_three_synthetic_nested_pools():
    frames = synthetic_three_pool_frames("Mean(close,5)")
    assert set(frames) == set(POOL_IDS.values())
    assert frames[POOL_IDS["all"]]["trade_date"].nunique() == 474
    assert frames[POOL_IDS["all"]]["instrument"].nunique() == 60
    assert frames[POOL_IDS["midcap"]]["instrument"].nunique() == 20
    assert frames[POOL_IDS["smallcap"]]["instrument"].nunique() == 20
    all_names = set(frames[POOL_IDS["all"]]["instrument"])
    mid_names = set(frames[POOL_IDS["midcap"]]["instrument"])
    small_names = set(frames[POOL_IDS["smallcap"]]["instrument"])
    assert not mid_names.intersection(small_names)
    assert mid_names.union(small_names).issubset(all_names)


def test_anchor_direction_is_shared_and_negative_child_fails_joint_gate():
    protocol = M3Protocol.load(PROTOCOL_PATH)
    frames = synthetic_three_pool_frames("Mean(close,5)")
    passed = evaluate_cross_pool_candidate("Mean(close,5)", frames, protocol, global_ordinal=1)
    assert passed.eligible
    assert passed.direction == 1
    assert min(passed.directed_rank_ic.values()) > 0

    broken = {pool: frame.copy() for pool, frame in frames.items()}
    broken[POOL_IDS["smallcap"]]["label"] *= -1
    failed = evaluate_cross_pool_candidate("Mean(close,5)", broken, protocol, global_ordinal=1)
    assert not failed.eligible
    assert failed.direction == passed.direction
    assert any("directed_rank_ic_not_positive" in reason for reason in failed.failures)


def test_mechanical_ranking_is_deterministic_after_all_pool_cells():
    protocol = M3Protocol.load(PROTOCOL_PATH)
    candidates = [
        evaluate_cross_pool_candidate(
            expression,
            synthetic_three_pool_frames(expression),
            protocol,
            global_ordinal=ordinal,
        )
        for ordinal, expression in enumerate(("Mean(close,5)", "EMA(close,8)"), start=1)
    ]
    first = rank_candidates(candidates, promoted_count=2)
    second = rank_candidates(list(reversed(candidates)), promoted_count=2)
    assert [candidate.candidate_id for candidate in first] == [
        candidate.candidate_id for candidate in second
    ]


def test_read_only_input_gate_binds_m3_membership_without_factor_access():
    protocol = M3Protocol.load(PROTOCOL_PATH)
    identity = verify_m3_inputs(protocol)
    assert identity.full_rows == 779_271
    assert identity.discovery_trade_days == 474
    assert identity.sealed_trade_days == 727
    assert identity.discovery_rows == {
        "star-board-all-pit-v1": 73_839,
        "star-board-midcap-pit-v1": 24_676,
        "star-board-smallcap-pit-v1": 24_387,
    }


def test_upstream_manifest_tampering_fails_closed_before_data_read():
    protocol = M3Protocol.load(PROTOCOL_PATH)
    document = copy.deepcopy(protocol.document)
    document["upstream_contract"]["membership_rows"] += 1
    with pytest.raises(D1ControlError, match="membership manifest binding differs"):
        verify_m3_inputs(replace(protocol, document=document))


def test_preexecution_report_is_deterministic_and_has_zero_external_authority():
    first = run_preexecution()
    second = run_preexecution()
    assert first == second
    assert first["verdict"] == "GO_M3_1_PREEXECUTION_ONLY"
    assert first["provider_calls"] == 0
    assert first["api_key_read"] is False
    assert first["real_candidate_count"] == 0
    assert first["real_factor_results_inspected"] is False
    assert first["sealed_factor_results_inspected"] is False
    assert first["production_authorization"] == "none"
    assert first["synthetic_fixture"]["cross_pool_evaluation_cells"] == 72


def test_compose_preflight_is_read_only_offline_and_has_no_secret_mount():
    compose = yaml.safe_load((PROJECT_ROOT / "compose.research.yaml").read_text(encoding="utf-8"))
    service = compose["services"]["m3-multi-pool-preflight"]
    assert service["network_mode"] == "none"
    assert service["read_only"] is True
    assert service["cap_drop"] == ["ALL"]
    assert "no-new-privileges:true" in service["security_opt"]
    assert "env_file" not in service
    assert "ports" not in service
    serialized = json.dumps(service, sort_keys=True)
    assert "DEEPSEEK_API_KEY" not in serialized
    assert "TUSHARE_TOKEN" not in serialized
    assert "FEISHU" not in serialized
    assert ".env" not in serialized
    assert "docker.sock" not in serialized
    assert all(volume["read_only"] is True for volume in service["volumes"])


@pytest.mark.parametrize(
    ("section", "key", "value"),
    [
        (None, "execution_authorized", True),
        ("attempt_budget", "completed_llm_responses_exact", 25),
        ("multiple_testing_contract", "effective_trial_count_after_complete_batch", 24),
        ("discovery_evaluation", "direction_anchor_universe", "star-board-smallcap-pit-v1"),
        ("sealed_evaluation_contract", "access_authorized_now", True),
    ],
)
def test_protocol_tampering_fails_closed(
    tmp_path: Path,
    section: str | None,
    key: str,
    value: object,
):
    document = yaml.safe_load(PROTOCOL_PATH.read_text(encoding="utf-8"))
    target = document if section is None else document[section]
    target[key] = value
    path = tmp_path / "protocol.yaml"
    path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
    with pytest.raises(D1ControlError):
        M3Protocol.load(path)
