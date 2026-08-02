from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
import torch
import yaml

from shaiwei.config import PROJECT_ROOT
from shaiwei.research.llm_factor import (
    CandidateProposal,
    D1ControlError,
    MockProvider,
    ProviderResponse,
    execute_completed_attempt,
)
from shaiwei.research.m3_multi_pool_contract import M3Protocol
from shaiwei.research.m3_multi_pool_data import (
    M3DiscoveryIdentity,
    M3DiscoveryInput,
    PanelStockData,
)
from shaiwei.research.m3_multi_pool_discovery import (
    M3DiscoveryEvaluator,
    feedback_for_m3_attempt,
    feedback_row,
    plan_m3_attempt,
)
from shaiwei.research.m3_multi_pool_evaluation import synthetic_three_pool_frames
from shaiwei.research.m3_multi_pool_release import M3ExecutionRelease


PROTOCOL_PATH = PROJECT_ROOT / "config/m3_multi_pool_factor_research_v1.yaml"
RELEASE_PATH = PROJECT_ROOT / "config/m3_multi_pool_factor_execution_v1.yaml"


def _proposal(plan, expression: str) -> CandidateProposal:
    parents = [] if plan.evolution_mode == "independent" else ["placeholder"]
    return CandidateProposal.model_validate(
        {
            "schema_version": "d1-candidate-v1",
            "topic": plan.topic,
            "hypothesis": "历史价格路径可能包含可证伪的横截面状态信息。",
            "expression": expression,
            "expected_direction": "positive",
            "economic_rationale_draft": "该唯一表达式在三个自建研究池保持同一定义。",
            "lineage": {"mode": plan.evolution_mode, "parent_attempt_ids": parents},
            "known_failure_risks": ["cross_segment_instability"],
        }
    )


def _response(protocol: M3Protocol, proposal: CandidateProposal) -> ProviderResponse:
    return ProviderResponse(
        model=protocol.returned_model_identity,
        content=proposal.model_dump_json(),
        reasoning_content="synthetic M3 live-control fixture",
        finish_reason="stop",
        usage={
            "prompt_tokens": 800,
            "prompt_cache_hit_tokens": 200,
            "prompt_cache_miss_tokens": 600,
            "completion_tokens": 120,
        },
        completed_at="2026-08-02T10:00:00+00:00",
    )


def test_execution_release_binds_exact_inputs_budget_and_scope():
    protocol = M3Protocol.load(PROTOCOL_PATH)
    release = M3ExecutionRelease.load(RELEASE_PATH, protocol)
    inputs = release.document["input_contract"]
    identity = M3DiscoveryIdentity(
        snapshot_sha256=inputs["discovery_input_snapshot_sha256"],
        source_snapshots=inputs["source_snapshot_sha256"],
        source_rows={key: int(value) for key, value in inputs["source_loaded_rows"].items()},
        calendar_start=inputs["calendar_start"],
        calendar_end=inputs["calendar_end"],
        panel_security_count=int(inputs["panel_security_count"]),
        discovery_trade_days=int(inputs["discovery_trade_days"]),
        exposure_rows=int(inputs["exposure_rows"]),
    )
    release.verify_input(identity)
    assert release.release_id == "m3-star-three-pool-price-volume-v1-batch-001"
    assert release.total_authorization_usd == 10.0
    assert release.batch_hard_ceiling_usd == 0.5
    assert release.document["authorization"]["completed_responses_exact"] == 24
    assert release.document["scope"]["sealed_validation_access"] is False


@pytest.mark.parametrize(
    ("section", "field", "value"),
    [
        ("authorization", "completed_responses_exact", 25),
        ("input_contract", "calendar_start", "20210104"),
        ("selection_contract", "promoted_count", 3),
        ("scope", "sealed_validation_access", True),
        ("recovery_contract", "billing_uncertainty_fail_closed", False),
        ("egress", "trust_environment_proxy", True),
    ],
)
def test_execution_release_tampering_fails_closed(
    tmp_path: Path, section: str, field: str, value: object
):
    protocol = M3Protocol.load(PROTOCOL_PATH)
    document = yaml.safe_load(RELEASE_PATH.read_text(encoding="utf-8"))
    document[section][field] = value
    path = tmp_path / "release.yaml"
    path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
    with pytest.raises(D1ControlError):
        M3ExecutionRelease.load(path, protocol)


def test_plan_has_four_topics_six_attempts_and_exact_terminal_boundary():
    protocol = M3Protocol.load(PROTOCOL_PATH)
    plans = [plan_m3_attempt(protocol, ordinal) for ordinal in range(1, 25)]
    assert len({plan.attempt_id for plan in plans}) == 24
    assert [plan.topic for plan in plans[::6]] == [
        "trend_momentum",
        "reversal_mean_reversion",
        "volatility_range",
        "liquidity_volume",
    ]
    assert [plan.evolution_mode for plan in plans[:6]] == [
        "independent",
        "independent",
        "independent",
        "mutation",
        "mutation",
        "mutation",
    ]
    with pytest.raises(D1ControlError):
        plan_m3_attempt(protocol, 25)


def test_m3_feedback_projector_is_verified_against_immutable_rows(tmp_path: Path):
    protocol = M3Protocol.load(PROTOCOL_PATH)
    release = M3ExecutionRelease.load(RELEASE_PATH, protocol)
    ledger = tmp_path / "attempts.csv"
    experiments = tmp_path / "experiments.csv"
    artifacts = tmp_path / "artifacts"
    rows = []
    for ordinal, expression in enumerate(
        ("Mean(close,5)", "Mean(close,8)", "Mean(close,13)"), start=1
    ):
        plan = plan_m3_attempt(protocol, ordinal)
        proposal = _proposal(plan, expression)
        result = execute_completed_attempt(
            protocol,
            plan,
            MockProvider([_response(protocol, proposal)]),
            ledger_path=ledger,
            experiment_ledger_path=experiments,
            artifact_root=artifacts,
            operator="test-m3-live",
            execution_release_id=release.release_id,
            execution_release_sha256=release.sha256,
            cost_hard_ceiling_usd=release.batch_hard_ceiling_usd,
        )
        rows.append(result.row)

    mutation = plan_m3_attempt(protocol, 4)
    feedback = feedback_for_m3_attempt(rows, mutation, artifacts)
    proposal = _proposal(mutation, "EMA(close,5)")
    proposal.lineage.parent_attempt_ids = [rows[0]["attempt_id"]]
    result = execute_completed_attempt(
        protocol,
        mutation,
        MockProvider([_response(protocol, proposal)]),
        ledger_path=ledger,
        experiment_ledger_path=experiments,
        artifact_root=artifacts,
        operator="test-m3-live",
        execution_release_id=release.release_id,
        execution_release_sha256=release.sha256,
        cost_hard_ceiling_usd=release.batch_hard_ceiling_usd,
        feedback_records=feedback,
        feedback_row_projector=lambda row: feedback_row(row, artifacts),
    )
    assert result.row["candidate_status"] == "CONTRACT_PASS"
    assert len(feedback) == 3
    assert set(feedback[0]) == set(
        protocol.prompt_bundle.document["feedback_contract"]["allowed_fields"]
    )


def test_prior_family_duplicate_callback_rejects_and_counts_response(tmp_path: Path):
    protocol = M3Protocol.load(PROTOCOL_PATH)
    plan = plan_m3_attempt(protocol, 1)
    result = execute_completed_attempt(
        protocol,
        plan,
        MockProvider([_response(protocol, _proposal(plan, "Mean(close,5)"))]),
        ledger_path=tmp_path / "attempts.csv",
        experiment_ledger_path=tmp_path / "experiments.csv",
        artifact_root=tmp_path / "artifacts",
        operator="test-m3-live",
        duplicate_expression_lookup=lambda expression: (
            "stage1:fixture" if expression == "Mean($close,5d)" else None
        ),
    )
    assert result.row["failure_class"] == "duplicate_ast"
    assert result.row["duplicate_of_attempt_id"] == "stage1:fixture"
    assert result.row["candidate_status"] == "REJECT"


def test_discovery_evaluator_preserves_date_instrument_alignment(monkeypatch, tmp_path: Path):
    protocol = M3Protocol.load(PROTOCOL_PATH)
    frames = synthetic_three_pool_frames("Mean(close,5)")
    all_frame = frames["star-board-all-pit-v1"].copy()
    old_names = sorted(all_frame["instrument"].unique())
    mapping = {name: f"SH{688000 + index:06d}" for index, name in enumerate(old_names)}
    for frame in frames.values():
        frame["instrument"] = frame["instrument"].map(mapping)
    all_frame["instrument"] = all_frame["instrument"].map(mapping)
    dates = tuple(sorted(pd.to_datetime(all_frame["trade_date"]).unique()))
    instruments = tuple(sorted(mapping.values()))
    factor = (
        all_frame.pivot(index="trade_date", columns="instrument", values="factor")
        .reindex(index=dates, columns=instruments)
        .to_numpy()
    )

    class Parsed:
        @staticmethod
        def evaluate(_: object) -> torch.Tensor:
            return torch.tensor(factor, dtype=torch.float64)

    monkeypatch.setattr(
        "shaiwei.research.m3_multi_pool_discovery.parse_safe_expression",
        lambda _: Parsed(),
    )
    members = pd.concat(
        [
            frame[["trade_date", "instrument"]].assign(universe_id=pool)
            for pool, frame in frames.items()
        ],
        ignore_index=True,
    )
    members["trade_date"] = pd.to_datetime(members["trade_date"]).dt.strftime("%Y%m%d")
    members["ts_code"] = members["instrument"].map(
        lambda value: f"{value[2:]}.{value[:2]}"
    )
    identity = M3DiscoveryIdentity("a" * 64, {}, {}, "", "", 60, 474, len(all_frame))
    prepared = M3DiscoveryInput(
        identity=identity,
        stock_data=PanelStockData(torch.empty(0), 0, 0, 474, 60),
        instruments=instruments,
        discovery_dates=dates,
        labels=all_frame[["trade_date", "instrument", "label"]],
        exposures=all_frame[["trade_date", "instrument", "industry", "market_cap"]],
        members=members[["trade_date", "universe_id", "ts_code"]],
    )

    class Release:
        @staticmethod
        def verify_input(_: object) -> None:
            return None

    evaluator = M3DiscoveryEvaluator(protocol, Release(), tmp_path, prepared)
    evidence = evaluator(plan_m3_attempt(protocol, 1), "Mean(close,5)")
    assert evidence.status == "PASS"
    assert evidence.coverage == 1.0
    assert evidence.daily_ic_count == 474


def test_m3_live_compose_has_offline_preflight_and_narrow_live_writes():
    compose = yaml.safe_load((PROJECT_ROOT / "compose.research.yaml").read_text(encoding="utf-8"))
    preflight = compose["services"]["m3-multi-pool-live-preflight"]
    assert preflight["network_mode"] == "none"
    assert preflight["read_only"] is True
    assert all(volume["read_only"] is True for volume in preflight["volumes"])
    assert "DEEPSEEK_API_KEY" not in json.dumps(preflight, sort_keys=True)

    live = compose["services"]["m3-multi-pool-live"]
    assert live["image"] == "shaiwei:m3-multi-pool-factor-v1"
    assert live["read_only"] is True
    assert live["cap_drop"] == ["ALL"]
    assert "no-new-privileges:true" in live["security_opt"]
    assert "DEEPSEEK_API_KEY" in live["environment"]
    assert "env_file" not in live and "ports" not in live and live.get("restart") is None
    serialized = json.dumps(live, sort_keys=True)
    assert ".env" not in serialized and "docker.sock" not in serialized
    writable = {
        volume["target"]
        for volume in live["volumes"]
        if volume.get("read_only") is False
    }
    assert writable == {
        "/workspace/data/research/m3/m3-star-three-pool-price-volume-v1",
        "/workspace/ledger/m3_multi_pool_factor_attempts.csv",
        "/workspace/ledger/m3_multi_pool_factor_transports.csv",
        "/workspace/ledger/experiments.csv",
    }
