import copy
import json
from dataclasses import replace
from pathlib import Path

import pytest
import yaml

from shaiwei.config import PROJECT_ROOT
from shaiwei.research.candidate_semantics import validate_candidate_semantics
from shaiwei.research.llm_factor import (
    CandidateProposal,
    D1ControlError,
    D1Protocol,
    MockProvider,
    ProviderResponse,
    execute_completed_attempt,
    plan_attempt,
)
from shaiwei.research.m1_star50_contract import M1Star50ExecutionRelease, verify_star50_inputs
from shaiwei.research.m1_star50_discovery import discovery_input_summary, load_star50_exposures


PROTOCOL_PATH = PROJECT_ROOT / "config/m1_star50_factor_research_v1.yaml"
RELEASE_PATH = PROJECT_ROOT / "config/m1_star50_factor_execution_v1.yaml"


def _proposal(**updates: object) -> CandidateProposal:
    payload = {
        "schema_version": "d1-candidate-v1",
        "topic": "trend_momentum",
        "hypothesis": "价格路径平滑程度可能描述尚未完全消化的横截面趋势状态。",
        "expression": "Mean(close,20)",
        "expected_direction": "positive",
        "economic_rationale_draft": "该唯一表达式只刻画历史价格状态，不构成收益或准入结论。",
        "lineage": {"mode": "independent", "parent_attempt_ids": []},
        "known_failure_risks": ["regime_instability"],
    }
    payload.update(updates)
    return CandidateProposal.model_validate(payload)


@pytest.mark.parametrize(
    ("updates", "reason"),
    [
        ({}, None),
        (
            {"economic_rationale_draft": "还可以改用EMA(close,10)形成另一条候选表达式。"},
            "dsl_expression_in_narrative",
        ),
        (
            {"economic_rationale_draft": "该表达式也可以调整窗口为30日以提高稳定性。"},
            "formula_or_parameter_variant_in_narrative",
        ),
        (
            {"hypothesis": "该假设预计能够稳定跑赢并降低回撤，适合实盘。"},
            "performance_or_production_claim",
        ),
        (
            {"hypothesis": "该假设用于2024压力期和G1准入结果判断。"},
            "sealed_or_admission_result_reference",
        ),
        (
            {"economic_rationale_draft": "该唯一表达式主要描述30日历史价格状态。"},
            "unbound_numeric_parameter_in_narrative",
        ),
        (
            {"economic_rationale_draft": "该唯一表达式同时参考volume状态来解释历史价格路径。"},
            "unbound_feature_in_narrative",
        ),
    ],
)
def test_candidate_semantic_gate_is_fail_closed(updates: dict[str, object], reason: str | None):
    assert validate_candidate_semantics(_proposal(**updates)) == reason


def test_semantic_failure_consumes_response_without_sandbox_or_discovery(tmp_path: Path):
    protocol = D1Protocol.load(PROTOCOL_PATH)
    proposal = _proposal(
        economic_rationale_draft="还可以改用EMA(close,10)形成另一条候选表达式。"
    )
    response = ProviderResponse(
        model=protocol.returned_model_identity,
        content=proposal.model_dump_json(),
        reasoning_content="synthetic semantic contract fixture",
        finish_reason="stop",
        usage={
            "prompt_tokens": 800,
            "prompt_cache_hit_tokens": 200,
            "prompt_cache_miss_tokens": 600,
            "completion_tokens": 120,
        },
        completed_at="2026-08-01T07:30:00+00:00",
    )
    result = execute_completed_attempt(
        protocol,
        plan_attempt(protocol, 1),
        MockProvider([response]),
        ledger_path=tmp_path / "attempts.csv",
        experiment_ledger_path=tmp_path / "experiments.csv",
        artifact_root=tmp_path / "artifacts",
        operator="test-m1-star50",
        candidate_semantic_validator=validate_candidate_semantics,
    )
    assert result.row["parse_status"] == "PASS"
    assert result.row["sandbox_status"] == "NOT_RUN"
    assert result.row["failure_class"] == "semantic_contract_violation"
    assert result.row["candidate_status"] == "REJECT"
    manifest = json.loads(
        (tmp_path / "artifacts" / result.row["artifact_manifest_path"]).read_text(
            encoding="utf-8"
        )
    )
    assert manifest["candidate_semantic_error"] == "dsl_expression_in_narrative"


def test_star50_input_gate_binds_pit_membership_and_sealed_clock():
    protocol = D1Protocol.load(PROTOCOL_PATH)
    identity = verify_star50_inputs(protocol, PROJECT_ROOT)
    assert identity.discovery_rows == 28_850
    assert identity.discovery_trade_days == 577
    assert identity.qlib_artifact_sha256 == protocol.document["data_contract"][
        "qlib_artifact_sha256"
    ]
    summary = discovery_input_summary(protocol)
    assert summary["provider_calls"] == 0
    assert summary["factor_results_inspected"] is False


def test_star50_exposures_are_unique_positive_and_bse_free():
    protocol = D1Protocol.load(PROTOCOL_PATH)
    exposures = load_star50_exposures(protocol, PROJECT_ROOT)
    assert len(exposures) == 28_850
    assert not exposures.duplicated(["trade_date", "instrument"]).any()
    assert exposures["industry"].notna().all()
    assert not exposures["instrument"].str.startswith("BJ").any()


def test_star50_input_tampering_fails_closed():
    protocol = D1Protocol.load(PROTOCOL_PATH)
    document = copy.deepcopy(protocol.document)
    document["data_contract"]["discovery_member_day_rows_expected"] += 1
    tampered = replace(protocol, document=document)
    with pytest.raises(D1ControlError, match="coverage differs"):
        verify_star50_inputs(tampered, PROJECT_ROOT)


def test_m1_execution_release_binds_authority_budget_scope_and_inputs():
    protocol = D1Protocol.load(PROTOCOL_PATH)
    release = M1Star50ExecutionRelease.load(RELEASE_PATH, protocol)
    assert release.release_id == "m1-star50-price-volume-v1-batch-001"
    assert release.batch_hard_ceiling_usd == 1.0
    assert release.total_authorization_usd == 10.0
    assert release.document["input_contract"]["data_snapshot_sha256"] == (
        "f6ad4566a522281102dd84a993bf9e774228bc0271ee9adb1ea3e1d3103cf4c5"
    )
    assert release.document["scope"]["sealed_validation_access"] is False


@pytest.mark.parametrize(
    ("section", "key", "value"),
    [
        ("authorization", "batch_hard_ceiling_usd", 2.0),
        ("authorization", "model", "another-model"),
        ("scope", "sealed_validation_access", True),
        ("egress", "trust_environment_proxy", True),
        ("selection_contract", "promoted_count", 3),
    ],
)
def test_m1_execution_release_tampering_fails_closed(
    tmp_path: Path, section: str, key: str, value: object
):
    protocol = D1Protocol.load(PROTOCOL_PATH)
    document = yaml.safe_load(RELEASE_PATH.read_text(encoding="utf-8"))
    document[section][key] = value
    path = tmp_path / "release.yaml"
    path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
    with pytest.raises(D1ControlError):
        M1Star50ExecutionRelease.load(path, protocol)


def test_m1_compose_preflight_and_live_have_narrow_boundaries():
    compose = yaml.safe_load((PROJECT_ROOT / "compose.research.yaml").read_text(encoding="utf-8"))
    preflight = compose["services"]["m1-star50-preflight"]
    assert preflight["network_mode"] == "none"
    assert preflight["read_only"] is True
    assert "DEEPSEEK_API_KEY" not in json.dumps(preflight, sort_keys=True)
    assert any(
        volume["source"] == "./docs"
        and volume["target"] == "/workspace/docs"
        and volume["read_only"] is True
        for volume in preflight["volumes"]
    )

    live = compose["services"]["m1-star50-live"]
    assert live["image"] == "shaiwei:m1-star50-factor-v1"
    assert live["pull_policy"] == "never"
    assert live["read_only"] is True
    assert live["cap_drop"] == ["ALL"]
    assert "no-new-privileges:true" in live["security_opt"]
    assert "env_file" not in live
    assert "ports" not in live
    assert live.get("restart") is None
    assert live["environment"][0] == "DEEPSEEK_API_KEY"
    serialized = json.dumps(live, sort_keys=True)
    assert "TUSHARE_TOKEN" not in serialized
    assert "FEISHU" not in serialized
    assert ".env" not in serialized
    assert "docker.sock" not in serialized
    assert any(
        volume["source"] == "./docs"
        and volume["target"] == "/workspace/docs"
        and volume["read_only"] is True
        for volume in live["volumes"]
    )
    writable = {
        volume["target"]
        for volume in live["volumes"]
        if volume.get("read_only") is False
    }
    assert writable == {
        "/workspace/data/research/m1/m1-star50-price-volume-v1",
        "/workspace/ledger/m1_star50_factor_attempts.csv",
        "/workspace/ledger/m1_star50_factor_transports.csv",
        "/workspace/ledger/experiments.csv",
        "/workspace/logs",
    }
