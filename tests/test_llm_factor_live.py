import json
from pathlib import Path

import pytest
import yaml

from shaiwei.config import PROJECT_ROOT
from shaiwei.research.deepseek_client import D1ExecutionRelease
from shaiwei.research.llm_factor import (
    ATTEMPT_LEDGER_HEADER_V2,
    D1ControlError,
    D1Protocol,
    DiscoveryEvidence,
    MockProvider,
    ProviderResponse,
    execute_completed_attempt,
    plan_attempt,
)
from shaiwei.research.llm_factor_live import D1RecoveryAddendum, feedback_for_attempt


PROTOCOL_PATH = PROJECT_ROOT / "config/d1_llm_factor_research_v1.yaml"
RELEASE_PATH = PROJECT_ROOT / "config/d1_llm_factor_execution_v1.yaml"
RECOVERY_PATH = PROJECT_ROOT / "config/d1_llm_factor_execution_recovery_v1.yaml"


def _proposal() -> dict:
    return {
        "schema_version": "d1-candidate-v1",
        "topic": "trend_momentum",
        "hypothesis": "过去二十日平均收盘价格可能刻画平滑后的横截面趋势状态。",
        "expression": "Mean(close,20)",
        "expected_direction": "positive",
        "economic_rationale_draft": "该解释仅是发现期可证伪草稿，不构成收益、准入或生产结论。",
        "lineage": {"mode": "independent", "parent_attempt_ids": []},
        "known_failure_risks": ["regime_instability"],
    }


def _response(protocol: D1Protocol) -> ProviderResponse:
    return ProviderResponse(
        model="deepseek-v4-pro",
        content=json.dumps(_proposal(), ensure_ascii=False),
        reasoning_content="synthetic live-release contract fixture",
        finish_reason="stop",
        usage={
            "prompt_tokens": 800,
            "prompt_cache_hit_tokens": 200,
            "prompt_cache_miss_tokens": 600,
            "completion_tokens": 120,
        },
        completed_at="2026-07-25T08:00:00+00:00",
    )


def test_execution_release_binds_user_budget_scope_and_response_model_correction():
    protocol = D1Protocol.load(PROTOCOL_PATH)
    release = D1ExecutionRelease.load(RELEASE_PATH, protocol)
    assert release.release_id == "d1-llm-dsl-v1-batch-001"
    assert release.total_authorization_usd == 10.0
    assert release.batch_hard_ceiling_usd == 1.0
    assert release.response_model_identity == "deepseek-v4-pro"
    assert release.document["scope"]["W1_W6_access"] is False
    assert release.document["authorization"]["completed_responses_exact"] == 40


@pytest.mark.parametrize(
    ("section", "field", "value", "match"),
    [
        ("authorization", "batch_hard_ceiling_usd", 10.0, "budget differs"),
        ("authorization", "completed_responses_exact", 41, "exactly 40"),
        ("scope", "W1_W6_access", True, "scope differs"),
        ("egress", "host", "example.com", "egress allowlist"),
        ("official_contract_recheck", "response_model_field", "DeepSeek-V4-Pro", "official contract"),
    ],
)
def test_execution_release_tamper_fails_closed(
    tmp_path: Path, section: str, field: str, value: object, match: str
):
    protocol = D1Protocol.load(PROTOCOL_PATH)
    document = yaml.safe_load(RELEASE_PATH.read_text(encoding="utf-8"))
    document[section][field] = value
    path = tmp_path / "tampered.yaml"
    path.write_text(yaml.safe_dump(document), encoding="utf-8")
    with pytest.raises(D1ControlError, match=match):
        D1ExecutionRelease.load(path, protocol)


def test_live_release_accepts_official_response_field_and_binds_discovery(tmp_path: Path):
    protocol = D1Protocol.load(PROTOCOL_PATH)
    release = D1ExecutionRelease.load(RELEASE_PATH, protocol)
    artifact_payload = "{}\n"
    artifact_sha = __import__("hashlib").sha256(artifact_payload.encode()).hexdigest()

    def evaluate(*_: object) -> DiscoveryEvidence:
        path = tmp_path / "artifacts/discovery/evidence.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(artifact_payload, encoding="utf-8")
        return DiscoveryEvidence(
            status="PASS",
            eligible_rows=1000,
            covered_rows=990,
            coverage=0.99,
            daily_ic_count=300,
            rank_ic=0.0123,
            error="",
            artifact_path="discovery/evidence.json",
            artifact_sha256=artifact_sha,
        )

    provider = MockProvider([_response(protocol)])
    result = execute_completed_attempt(
        protocol,
        plan_attempt(protocol, 1),
        provider,
        ledger_path=tmp_path / "ledger/llm_factor_attempts.csv",
        experiment_ledger_path=tmp_path / "ledger/experiments.csv",
        artifact_root=tmp_path / "artifacts",
        operator="test",
        code_sha256="a" * 64,
        execution_release_id=release.release_id,
        execution_release_sha256=release.sha256,
        cost_hard_ceiling_usd=release.batch_hard_ceiling_usd,
        data_sha256="b" * 64,
        discovery_evaluator=evaluate,
        returned_model_identity=release.response_model_identity,
    )
    assert result.row["candidate_status"] == "DISCOVERY_EVALUATED"
    assert result.row["returned_model"] == "deepseek-v4-pro"
    assert result.row["execution_release_sha256"] == release.sha256
    assert result.row["discovery_rank_ic"] == "0.012300000000"
    assert result.row["data_snapshot_sha256"] == "b" * 64


def test_feedback_is_derived_only_from_bound_ledger_fields():
    protocol = D1Protocol.load(PROTOCOL_PATH)
    rows = []
    for ordinal in range(1, 5):
        row = {field: "" for field in ATTEMPT_LEDGER_HEADER_V2}
        row.update(
            {
                "attempt_id": f"attempt-{ordinal}",
                "global_ordinal": str(ordinal),
                "topic": "trend_momentum",
                "parse_status": "PASS",
                "sandbox_status": "PASS",
                "canonical_expression": f"Mean(close,{ordinal + 10})",
                "discovery_coverage": "0.990000000000",
                "discovery_rank_ic": f"0.0{ordinal}",
                "expression_tokens": "3",
                "ast_nodes": "3",
                "max_lookback_days": str(ordinal + 10),
            }
        )
        rows.append(row)
    feedback = feedback_for_attempt(rows, plan_attempt(protocol, 5))
    assert [item["attempt_id"] for item in feedback] == [
        "attempt-1",
        "attempt-2",
        "attempt-3",
        "attempt-4",
    ]
    assert feedback[-1]["discovery_rank_ic"] == 0.04
    assert set(feedback[-1]) == set(
        protocol.prompt_bundle.document["feedback_contract"]["allowed_fields"]
    )


def test_independent_attempt_ignores_prior_same_topic_rows():
    protocol = D1Protocol.load(PROTOCOL_PATH)
    row = {field: "" for field in ATTEMPT_LEDGER_HEADER_V2}
    row.update(
        {
            "attempt_id": "attempt-1",
            "global_ordinal": "1",
            "topic": "trend_momentum",
        }
    )
    assert plan_attempt(protocol, 2).evolution_mode == "independent"
    assert feedback_for_attempt([row], plan_attempt(protocol, 2)) == []


def test_recovery_addendum_binds_first_response_and_append_only_prefixes(tmp_path: Path):
    protocol = D1Protocol.load(PROTOCOL_PATH)
    release = D1ExecutionRelease.load(RELEASE_PATH, protocol)
    with (PROJECT_ROOT / "ledger/llm_factor_attempts_v2.csv").open(
        newline="", encoding="utf-8"
    ) as handle:
        rows = list(__import__("csv").DictReader(handle))
    recovery = D1RecoveryAddendum.load(
        RECOVERY_PATH,
        release=release,
        batch_rows=rows,
    )
    assert recovery.recovery_id.endswith("control-flow-recovery-001")

    document = yaml.safe_load(RECOVERY_PATH.read_text(encoding="utf-8"))
    document["immutable_prefixes"]["ledger/llm_factor_attempts_v2.csv"]["byte_count"] -= 1
    tampered = tmp_path / "recovery.yaml"
    tampered.write_text(yaml.safe_dump(document), encoding="utf-8")
    with pytest.raises(D1ControlError, match="ledger prefix differs"):
        D1RecoveryAddendum.load(tampered, release=release, batch_rows=rows)


def test_live_compose_has_narrow_secret_and_mount_boundary():
    compose = yaml.safe_load((PROJECT_ROOT / "compose.research.yaml").read_text(encoding="utf-8"))
    service = compose["services"]["d1-live"]
    assert service["image"] == "shaiwei:d1-live-v1-r1"
    assert service["pull_policy"] == "never"
    assert service["read_only"] is True
    assert service["cap_drop"] == ["ALL"]
    assert "no-new-privileges:true" in service["security_opt"]
    assert "env_file" not in service
    assert "ports" not in service
    assert service.get("restart") is None
    assert "DEEPSEEK_API_KEY" in service["environment"]
    assert "/workspace/config/d1_llm_factor_execution_recovery_v1.yaml" in service["command"]
    assert not any(
        marker in str(item)
        for marker in ("TUSHARE_TOKEN", "FEISHU_WEBHOOK", "FEISHU_SIGNING")
        for item in service["environment"]
    )
    serialized = json.dumps(service, sort_keys=True)
    assert ".env" not in serialized
    assert "docker.sock" not in serialized
    assert "/workspace/src" not in serialized
    writable = {
        volume["target"]
        for volume in service["volumes"]
        if volume.get("read_only") is False
    }
    assert writable == {
        "/workspace/data/research/d1/d1-llm-dsl-v1",
        "/workspace/ledger/llm_factor_attempts_v2.csv",
        "/workspace/ledger/llm_factor_transports_v2.csv",
        "/workspace/ledger/experiments.csv",
        "/workspace/logs",
    }
