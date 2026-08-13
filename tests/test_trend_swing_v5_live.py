import csv
from hashlib import sha256
import json
from pathlib import Path

import httpx
import yaml

from shaiwei.research.deepseek_client import DeepSeekProvider
from shaiwei.research.trend_swing.v5_audit import audit_batch
from shaiwei.research.trend_swing.v5_evidence import ATTEMPT_HEADER, candidate_gate
from shaiwei.research.trend_swing.v5_live import run_batch
from shaiwei.research.trend_swing.v5_transport import (
    APPROVED_SCOPE_SHA256,
    BUDGET_RECORD_SHA256,
    INDEPENDENT_REQUEST_BUNDLE_SHA256,
    V5TransportProtocol,
)
from test_trend_swing_v5_candidate_contract import candidate_document


IMPLEMENTATION_HEAD = "a" * 40


def release_document(protocol: V5TransportProtocol) -> dict[str, object]:
    return {
        "schema_version": "ts-v5-llm-execution-release-v1",
        "release_id": "ts-v5-llm-research-batch-001",
        "status": "TS_V5_LLM_RESULT_BEFORE_EXECUTION_FROZEN",
        "execution_authorized": True,
        "production_authorization": "none",
        "user_approval": {
            "source": "user_explicit_approval_primary_codex_thread",
            "approved_on": "2026-08-13",
            "approved_scope_path": "config/ts_v5_llm_research_scope_v1.yaml",
            "approved_scope_sha256": APPROVED_SCOPE_SHA256,
            "completed_responses_exact": 12,
            "independent_candidates": 6,
            "adversarial_revisions": 6,
            "batch_hard_ceiling_usd": 0.5,
        },
        "program_budget_context": {
            "record_path": "config/ts_v5_llm_research_scope_v2.yaml",
            "record_sha256": BUDGET_RECORD_SHA256,
            "program_hard_ceiling_usd": 5.0,
            "approved_v1_scope_controls_this_batch": True,
            "program_ceiling_does_not_expand_this_batch": True,
            "future_batches_require_new_scope_and_user_approval": True,
        },
        "provider_identity": {
            "requested_model": "deepseek-v4-pro",
            "expected_model_version": "DeepSeek-V4-Pro",
            "response_model_field": "deepseek-v4-pro",
            "version_and_response_field_are_distinct": True,
            "correction_frozen_before_any_paid_response": True,
        },
        "frozen_contract": {
            **protocol.bundle.identity(),
            "transport_protocol_sha256": protocol.sha256,
            "independent_request_bundle_sha256": INDEPENDENT_REQUEST_BUNDLE_SHA256,
        },
        "authorization": {
            "completed_responses_exact": 12,
            "batch_hard_ceiling_usd": 0.5,
            "concurrency": 1,
            "replacement_responses_authorized": False,
            "unused_budget_carryover": False,
            "new_user_approval_required": True,
        },
        "egress": {
            "scheme": "https",
            "host": "api.deepseek.com",
            "port": 443,
            "path": "/chat/completions",
            "trust_environment_proxy": False,
        },
        "forbidden_payload": [
            "raw_market_data",
            "security_identity",
            "holdings_orders_or_signals",
            "sealed_validation_or_locked_test",
            "forward_or_production_results",
            "paths_or_secrets",
        ],
        "runtime": {
            "implementation_git_head": IMPLEMENTATION_HEAD,
            "image_tag": "shaiwei:ts-v5-llm-batch-001",
            "image_id": "sha256:" + "d" * 64,
            "code_snapshot_sha256": "c" * 64,
            "output_root": "data/research/trend_swing/ts-v5-llm-batch-001",
            "attempt_ledger": "ledger/ts_v5_llm_attempts.csv",
            "transport_ledger": "ledger/ts_v5_llm_transports.csv",
        },
        "pre_execution_gates": {
            "release_commit_pushed_and_head_equals_origin_main": True,
            "implementation_image_identity_matches": True,
            "only_deepseek_api_key_passed_to_container": True,
            "tls_hostname_probe_before_secret_read": True,
            "outbound_payload_allowlist_scan": True,
            "invalid_completed_response_counts_without_replacement": True,
            "scheduler_identity_unchanged_and_healthy": True,
            "no_market_effect_backtest_or_production_access": True,
        },
    }


def completion(request: httpx.Request) -> httpx.Response:
    payload = json.loads(request.content)
    task = json.loads(payload["messages"][1]["content"])
    document = candidate_document(task["primary_mechanism"])
    if task["mode"] == "ADVERSARIAL_REVISION":
        document["lineage"] = {
            "mode": "ADVERSARIAL_REVISION",
            "parent_candidate_fingerprints": [task["parent_attempt"]["fingerprint"]],
        }
        document["change_summary"] = "反向质疑后保留同一机制并收窄其证伪范围。"
    response = {
        "id": f"fixture-{task['attempt_id']}",
        "created": 1786579200 + task["ordinal"],
        "model": "deepseek-v4-pro",
        "choices": [
            {
                "message": {
                    "content": json.dumps(document, ensure_ascii=False),
                    "reasoning_content": "synthetic fixture reasoning",
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 1200,
            "prompt_cache_hit_tokens": 0,
            "prompt_cache_miss_tokens": 1200,
            "completion_tokens": 600,
        },
    }
    return httpx.Response(200, json=response, request=request)


def test_one_shot_batch_has_twelve_responses_and_offline_audit(tmp_path: Path) -> None:
    project = tmp_path / "project"
    output = project / "data/research/trend_swing/ts-v5-llm-batch-001"
    attempt_path = project / "ledger/ts_v5_llm_attempts.csv"
    transport_path = project / "ledger/ts_v5_llm_transports.csv"
    release_path = project / "release.yaml"
    output.mkdir(parents=True)
    attempt_path.parent.mkdir(parents=True)
    attempt_path.write_text(",".join(ATTEMPT_HEADER) + "\n", encoding="utf-8")
    transport_path.write_text(
        "event_id,attempt_id,request_sha256,sequence,event_type,recorded_at,http_status,"
        "completed_response,billing_status,response_id_sha256,response_artifact_path,"
        "response_artifact_sha256,source_response_sha256,error_class,provider,model,"
        "execution_release_id,execution_release_sha256,operator\n",
        encoding="utf-8",
    )
    protocol = V5TransportProtocol.load()
    release_path.write_text(yaml.safe_dump(release_document(protocol), sort_keys=False))
    calls = 0

    def provider_factory(protocol, **kwargs):
        nonlocal calls

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            return completion(request)

        return DeepSeekProvider(
            protocol,
            attempt_id=kwargs["attempt_id"],
            api_key="fixture-key-never-persisted",
            transport_ledger_path=kwargs["transport_ledger_path"],
            artifact_root=kwargs["artifact_root"],
            transport=httpx.MockTransport(handler),
            execution_release=kwargs["release"],
            clock=lambda: "2026-08-13T00:00:00+00:00",
            sleeper=lambda _: None,
            operator="fixture-ts-v5",
        )

    report = run_batch(
        release_path=release_path,
        output_root=output,
        attempt_path=attempt_path,
        transport_path=transport_path,
        project_root=project,
        provider_factory=provider_factory,
        tls_probe=lambda _: "b" * 64,
        runtime_git_head=lambda: IMPLEMENTATION_HEAD,
        runtime_code_sha=lambda: "c" * 64,
    )
    replay = run_batch(
        release_path=release_path,
        output_root=output,
        attempt_path=attempt_path,
        transport_path=transport_path,
        project_root=project,
        provider_factory=provider_factory,
        tls_probe=lambda _: "b" * 64,
        runtime_git_head=lambda: IMPLEMENTATION_HEAD,
        runtime_code_sha=lambda: "c" * 64,
    )
    audit = audit_batch(
        release_path=release_path,
        output_root=output,
        attempt_path=attempt_path,
        transport_path=transport_path,
        project_root=project,
    )

    assert report["completed_response_count"] == 12
    assert report["independent_response_count"] == 6
    assert report["adversarial_response_count"] == 6
    assert report["actual_cost_usd"] < 0.5
    assert replay["idempotent_reuse"] is True
    assert replay["external_api_calls_this_run"] == 0
    assert calls == 12
    assert audit["verdict"] == "PASS"
    with attempt_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 12
    assert all(
        "fixture-key-never-persisted" not in path.read_text(encoding="utf-8")
        for path in project.rglob("*")
        if path.is_file()
    )


def test_v5_live_modules_remain_below_architecture_soft_limit() -> None:
    root = Path(__file__).resolve().parents[1]
    modules = (
        "src/shaiwei/research/trend_swing/v5_transport.py",
        "src/shaiwei/research/trend_swing/v5_evidence.py",
        "src/shaiwei/research/trend_swing/v5_live.py",
        "src/shaiwei/research/trend_swing/v5_audit.py",
        "src/shaiwei/research/trend_swing/v5_response_contract.py",
        "src/shaiwei/research/trend_swing/v5_response_recovery.py",
    )
    assert all(len((root / name).read_text().splitlines()) <= 400 for name in modules)


def test_approved_scope_and_budget_records_remain_byte_immutable() -> None:
    root = Path(__file__).resolve().parents[1]
    assert sha256((root / "config/ts_v5_llm_research_scope_v1.yaml").read_bytes()).hexdigest() == (
        APPROVED_SCOPE_SHA256
    )
    assert sha256((root / "config/ts_v5_llm_research_scope_v2.yaml").read_bytes()).hexdigest() == (
        BUDGET_RECORD_SHA256
    )


def test_compose_is_short_lived_minimal_and_audit_is_offline() -> None:
    root = Path(__file__).resolve().parents[1]
    compose = yaml.safe_load((root / "compose.ts-v5-llm.yaml").read_text(encoding="utf-8"))
    live = compose["services"]["ts-v5-llm"]
    audit = compose["services"]["ts-v5-llm-audit"]

    assert live["read_only"] is True
    assert live["user"] == "${SHAIWEI_HOST_UID:-10001}:${SHAIWEI_HOST_GID:-10001}"
    assert live["cap_drop"] == ["ALL"]
    assert live["environment"] == [
        "DEEPSEEK_API_KEY",
        "HOME=/tmp",
        "PYTHONPYCACHEPREFIX=/tmp/pycache",
    ]
    assert live["cpus"] == 1.0
    assert live["mem_limit"] == "512m"
    assert audit["network_mode"] == "none"
    assert all("DEEPSEEK_API_KEY" not in item for item in audit["environment"])
    assert all("docker.sock" not in volume["source"] for volume in live["volumes"])
    assert all(volume["source"] not in (".", "./") for volume in live["volumes"])
    release_mount = [
        volume for volume in live["volumes"] if volume["target"].startswith("/opt/shaiwei/")
    ]
    assert release_mount == [
        {
            "type": "bind",
            "source": "./config/ts_v5_llm_execution_release_v2.yaml",
            "target": "/opt/shaiwei/ts_v5_llm_execution_release_v2.yaml",
            "read_only": True,
            "bind": {"create_host_path": False},
        }
    ]


def test_candidate_gate_stops_complete_batch_without_a_valid_candidate() -> None:
    rows = [
        {
            "schema_status": "NOT_EVALUATED",
            "duplicate_status": "NOT_EVALUATED",
            "failure_class": "PROVIDER_FINISH_REASON_INVALID",
        }
        for _ in range(12)
    ]
    assert candidate_gate(rows) == ("STOP_NO_VALID_CANDIDATES", 0)
    rows[0] = {
        "schema_status": "PASS",
        "duplicate_status": "UNIQUE",
        "failure_class": "",
    }
    assert candidate_gate(rows) == ("GO_CANDIDATES_ONLY", 1)
