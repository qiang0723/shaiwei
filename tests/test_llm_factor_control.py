import ast
import csv
import json
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from shaiwei.config import PROJECT_ROOT
from shaiwei.research import llm_factor
from shaiwei.research.llm_factor import (
    ATTEMPT_LEDGER_HEADER,
    CandidateProposal,
    D1ControlError,
    D1Protocol,
    MockProvider,
    ProviderResponse,
    execute_completed_attempt,
    initialize_attempt_ledger,
    plan_attempt,
    run_fixture,
    verify_attempt_experiment_bijection,
)


PROTOCOL_PATH = PROJECT_ROOT / "config/d1_llm_factor_research_v1.yaml"


def _proposal(*, topic: str = "trend_momentum", expression: str = "Mean(close,20)") -> dict:
    return {
        "schema_version": "d1-candidate-v1",
        "topic": topic,
        "hypothesis": "过去二十日平均收盘价可作为平滑趋势状态的受限工程样本。",
        "expression": expression,
        "expected_direction": "positive",
        "economic_rationale_draft": "该文本仅验证机器契约，不代表经济解释、研究结论或人工准入陈述。",
        "lineage": {"mode": "independent", "parent_attempt_ids": []},
        "known_failure_risks": ["synthetic_fixture_only"],
    }


def _response(
    protocol: D1Protocol,
    content: object,
    *,
    model: str | None = None,
    reasoning: str = "synthetic fixture only",
    finish_reason: str = "stop",
    usage: dict[str, int] | None = None,
) -> ProviderResponse:
    encoded = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)
    return ProviderResponse(
        model=model or protocol.returned_model_identity,
        content=encoded,
        reasoning_content=reasoning,
        finish_reason=finish_reason,
        usage=usage
        if usage is not None
        else {
            "prompt_tokens": 800,
            "prompt_cache_hit_tokens": 200,
            "prompt_cache_miss_tokens": 600,
            "completion_tokens": 120,
        },
        completed_at="2026-07-25T06:30:00+00:00",
    )


def _run(
    tmp_path: Path,
    protocol: D1Protocol,
    ordinal: int,
    response: ProviderResponse,
):
    ledger_path = tmp_path / "ledger/llm_factor_attempts.csv"
    experiment_ledger_path = tmp_path / "ledger/experiments.csv"
    provider = MockProvider([response])
    result = execute_completed_attempt(
        protocol,
        plan_attempt(protocol, ordinal),
        provider,
        ledger_path=ledger_path,
        experiment_ledger_path=experiment_ledger_path,
        artifact_root=tmp_path / "artifacts",
        operator="test",
        code_sha256="a" * 64,
    )
    return result, provider, ledger_path


def test_protocol_binds_exact_budget_allowlists_and_zero_call_boundary():
    protocol = D1Protocol.load(PROTOCOL_PATH)
    assert protocol.attempts_per_topic == 8
    assert protocol.independent_attempts == 4
    assert plan_attempt(protocol, 1).evolution_mode == "independent"
    assert plan_attempt(protocol, 5).evolution_mode == "mutation"
    assert plan_attempt(protocol, 40).topic == "price_volume_state"
    assert protocol.document["execution_authorized"] is False
    assert protocol.document["llm_api_called"] is False
    assert protocol.document["d1_1_engineering_complete"] is True
    with pytest.raises(D1ControlError, match="within 1..40"):
        plan_attempt(protocol, 41)


def test_protocol_fails_closed_if_real_execution_is_enabled(tmp_path: Path):
    document = yaml.safe_load(PROTOCOL_PATH.read_text(encoding="utf-8"))
    document["execution_authorized"] = True
    path = tmp_path / "unsafe.yaml"
    path.write_text(yaml.safe_dump(document), encoding="utf-8")
    with pytest.raises(D1ControlError, match="unauthorized"):
        D1Protocol.load(path)


def test_candidate_schema_forbids_extra_fields_and_invalid_lineage():
    valid = _proposal()
    assert CandidateProposal.model_validate(valid).expression == "Mean(close,20)"
    with pytest.raises(ValidationError):
        CandidateProposal.model_validate({**valid, "second_expression": "Mean(volume,10)"})
    invalid = _proposal()
    invalid["lineage"] = {"mode": "independent", "parent_attempt_ids": ["parent"]}
    with pytest.raises(ValidationError, match="cannot declare parents"):
        CandidateProposal.model_validate(invalid)


def test_valid_mock_attempt_is_audited_costed_and_replayed_without_second_call(tmp_path: Path):
    protocol = D1Protocol.load(PROTOCOL_PATH)
    response = _response(protocol, _proposal())
    result, provider, ledger_path = _run(tmp_path, protocol, 1, response)
    assert result.row["candidate_status"] == "CONTRACT_PASS"
    assert result.row["parse_status"] == "PASS"
    assert result.row["sandbox_status"] == "PASS"
    assert result.row["estimated_cost_usd"] == "0.000366125000"
    assert result.audit is not None and result.audit.shift_sentinel_pass
    assert provider.external_api_calls == 0
    replay = execute_completed_attempt(
        protocol,
        plan_attempt(protocol, 1),
        provider,
        ledger_path=ledger_path,
        experiment_ledger_path=tmp_path / "ledger/experiments.csv",
        artifact_root=tmp_path / "artifacts",
        operator="test",
        code_sha256="a" * 64,
    )
    assert replay.reused
    assert provider.responses_consumed == 1
    with ledger_path.open(newline="", encoding="utf-8") as handle:
        assert len(list(csv.DictReader(handle))) == 1


def test_second_attempt_with_same_canonical_ast_counts_and_rejects_duplicate(tmp_path: Path):
    protocol = D1Protocol.load(PROTOCOL_PATH)
    first, _, ledger_path = _run(tmp_path, protocol, 1, _response(protocol, _proposal()))
    second_provider = MockProvider([_response(protocol, _proposal())])
    second = execute_completed_attempt(
        protocol,
        plan_attempt(protocol, 2),
        second_provider,
        ledger_path=ledger_path,
        experiment_ledger_path=tmp_path / "ledger/experiments.csv",
        artifact_root=tmp_path / "artifacts",
        operator="test",
        code_sha256="a" * 64,
    )
    assert second.row["failure_class"] == "duplicate_ast"
    assert second.row["duplicate_of_attempt_id"] == first.row["attempt_id"]
    with ledger_path.open(newline="", encoding="utf-8") as handle:
        assert len(list(csv.DictReader(handle))) == 2


@pytest.mark.parametrize(
    ("response_factory", "failure_class", "parse_status", "sandbox_status"),
    [
        (lambda p: _response(p, []), "schema_invalid", "FAIL", "NOT_RUN"),
        (
            lambda p: _response(p, _proposal(expression="__import__('os').system('id')")),
            "sandbox_rejected",
            "PASS",
            "FAIL",
        ),
        (
            lambda p: _response(p, _proposal(), model="unexpected-model"),
            "model_identity_mismatch",
            "NOT_RUN",
            "NOT_RUN",
        ),
        (
            lambda p: _response(p, _proposal(), finish_reason="length"),
            "empty_or_truncated_output",
            "NOT_RUN",
            "NOT_RUN",
        ),
    ],
)
def test_completed_bad_responses_are_terminal_counted_failures(
    tmp_path: Path,
    response_factory,
    failure_class: str,
    parse_status: str,
    sandbox_status: str,
):
    protocol = D1Protocol.load(PROTOCOL_PATH)
    result, _, ledger_path = _run(tmp_path, protocol, 1, response_factory(protocol))
    assert result.row["failure_class"] == failure_class
    assert result.row["parse_status"] == parse_status
    assert result.row["sandbox_status"] == sandbox_status
    with ledger_path.open(newline="", encoding="utf-8") as handle:
        assert len(list(csv.DictReader(handle))) == 1


def test_sensitive_response_is_hashed_but_raw_payload_is_not_persisted(tmp_path: Path):
    protocol = D1Protocol.load(PROTOCOL_PATH)
    response = _response(protocol, _proposal(), reasoning="do not store sk-" + "A" * 24)
    result, _, _ = _run(tmp_path, protocol, 1, response)
    assert result.row["failure_class"] == "sensitive_output"
    assert not list((tmp_path / "artifacts/raw").glob("*"))
    manifest = json.loads(
        (tmp_path / "artifacts" / result.row["artifact_manifest_path"]).read_text(encoding="utf-8")
    )
    assert manifest["raw_response_path"] == ""


def test_missing_or_inconsistent_usage_fails_closed(tmp_path: Path):
    protocol = D1Protocol.load(PROTOCOL_PATH)
    bad_usage = {
        "prompt_tokens": 800,
        "prompt_cache_hit_tokens": 200,
        "prompt_cache_miss_tokens": 599,
        "completion_tokens": 120,
    }
    result, _, _ = _run(tmp_path, protocol, 1, _response(protocol, _proposal(), usage=bad_usage))
    assert result.row["failure_class"] == "usage_missing_or_invalid"


def test_mutation_parent_must_be_earlier_and_same_topic(tmp_path: Path):
    protocol = D1Protocol.load(PROTOCOL_PATH)
    proposal = _proposal()
    proposal["lineage"] = {"mode": "mutation", "parent_attempt_ids": ["absent"]}
    result, _, _ = _run(tmp_path, protocol, 5, _response(protocol, proposal))
    assert result.row["failure_class"] == "schema_invalid"
    assert result.row["candidate_status"] == "REJECT"


def test_tracked_attempt_ledger_has_exact_header_and_append_collision_is_fail_closed(tmp_path: Path):
    tracked = PROJECT_ROOT / "ledger/llm_factor_attempts.csv"
    assert tuple(tracked.read_text(encoding="utf-8").strip().split(",")) == ATTEMPT_LEDGER_HEADER
    path = tmp_path / "attempts.csv"
    initialize_attempt_ledger(path)
    assert tuple(path.read_text(encoding="utf-8").strip().split(",")) == ATTEMPT_LEDGER_HEADER


def test_attempt_and_experiment_ledgers_are_one_to_one_and_orphans_fail_closed(tmp_path: Path):
    protocol = D1Protocol.load(PROTOCOL_PATH)
    result, provider, ledger_path = _run(tmp_path, protocol, 1, _response(protocol, _proposal()))
    experiment_path = tmp_path / "ledger/experiments.csv"
    assert verify_attempt_experiment_bijection(ledger_path, experiment_path) == {
        "attempt_rows": 1,
        "experiment_rows": 1,
    }
    experiment_path.write_text(",".join(llm_factor.EXPERIMENT_LEDGER_HEADER) + "\n", encoding="utf-8")
    with pytest.raises(D1ControlError, match="exactly one experiment-ledger counterpart"):
        execute_completed_attempt(
            protocol,
            plan_attempt(protocol, 1),
            provider,
            ledger_path=ledger_path,
            experiment_ledger_path=experiment_path,
            artifact_root=tmp_path / "artifacts",
            operator="test",
            code_sha256="a" * 64,
        )
    assert provider.responses_consumed == 1
    assert result.row["experiment_id"]


def test_d1_control_module_has_no_real_network_client_import():
    source = Path(llm_factor.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_roots = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported_roots.update(
        node.module.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    )
    assert not imported_roots.intersection({"httpx", "openai", "requests", "urllib"})


def test_d1_fixture_compose_is_offline_secretless_and_project_scoped():
    compose = yaml.safe_load((PROJECT_ROOT / "compose.research.yaml").read_text(encoding="utf-8"))
    service = compose["services"]["d1-fixture"]
    assert service["pull_policy"] == "never"
    assert service["network_mode"] == "none"
    assert service["read_only"] is True
    assert service["user"] == "10001:10001"
    assert service["cap_drop"] == ["ALL"]
    assert "no-new-privileges:true" in service["security_opt"]
    assert "env_file" not in service
    assert "ports" not in service
    assert service.get("restart") is None
    assert service["pids_limit"] == 128
    assert service["mem_limit"] == "1g"
    assert service["cpus"] == 2.0
    assert service["volumes"] == [
        {
            "type": "bind",
            "source": "./vendor/alphagen",
            "target": "/workspace/vendor/alphagen",
            "read_only": True,
            "bind": {"create_host_path": False},
        }
    ]
    serialized = json.dumps(service, sort_keys=True)
    assert ".env" not in serialized
    assert "docker.sock" not in serialized
    assert "/workspace/data" not in serialized
    assert "/workspace/ledger" not in serialized
    assert service["command"][:4] == ["python", "-m", "shaiwei.research.llm_factor", "--fixture"]


def test_zero_network_fixture_is_complete_and_idempotent(tmp_path: Path):
    report = run_fixture(PROTOCOL_PATH, tmp_path / "fixture")
    assert report["fixture_pass"]
    assert report["external_api_calls"] == 0
    assert report["mock_responses_consumed"] == 1
    assert report["attempt_rows"] == 1
    assert report["experiment_rows"] == 1
    assert report["ledger_one_to_one"] is True
    assert report["real_market_data_read"] is False
    assert report["g1_run"] is False
