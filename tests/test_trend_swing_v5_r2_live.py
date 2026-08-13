import csv
import json
from pathlib import Path

import httpx
import yaml

from shaiwei.research.deepseek_client import DeepSeekProvider, TRANSPORT_LEDGER_HEADER_V2
from shaiwei.research.trend_swing.v5_evidence import ATTEMPT_HEADER
from shaiwei.research.trend_swing.v5_r2_audit import audit_batch
from shaiwei.research.trend_swing.v5_r2_live import run_batch, run_preflight
from shaiwei.research.trend_swing.v5_r2_release import REQUEST_BUNDLE_SHA256
from shaiwei.research.trend_swing.v5_response_contract import CONTRACT_SHA256
from shaiwei.research.trend_swing.v5_transport import (
    BUDGET_RECORD_SHA256,
    V5TransportProtocol,
)
from test_trend_swing_v5_candidate_contract import candidate_document


IMPLEMENTATION_HEAD = "a" * 40
CODE_SNAPSHOT = "c" * 64


def release_document(protocol: V5TransportProtocol) -> dict[str, object]:
    return {
        "schema_version": "ts-v5-r2-llm-execution-release-v1",
        "release_id": "ts-v5-r2-response-contract-canary-001",
        "status": "TS_V5_R2_RESULT_BEFORE_EXECUTION_FROZEN",
        "execution_authorized": True,
        "production_authorization": "none",
        "user_approval": {
            "source": "user_explicit_approval_primary_codex_thread",
            "approved_on": "2026-08-13",
            "approved_scope_path": "config/ts_v5_r2_llm_canary_scope_v1.yaml",
            "approved_scope_sha256": "e2d7218fc77e918ce3f389263290be6fc5fb15d274ec7affcf75d94e48e1a8ef",
            "completed_responses_exact": 4,
            "independent_candidates": 4,
            "adversarial_revisions": 0,
            "batch_hard_ceiling_usd": 0.1,
            "replacement_or_fifth_response_authorized": False,
        },
        "provider_identity": {
            "requested_model": "deepseek-v4-pro",
            "expected_model_version": "DeepSeek-V4-Pro",
            "response_model_field": "deepseek-v4-pro",
            "version_and_response_field_are_distinct": True,
            "correction_frozen_before_any_paid_response": True,
        },
        "program_budget_context": {
            "record_path": "config/ts_v5_llm_research_scope_v2.yaml",
            "record_sha256": BUDGET_RECORD_SHA256,
            "program_hard_ceiling_usd": 5.0,
            "approved_r2_scope_controls_this_batch": True,
            "program_ceiling_does_not_expand_this_batch": True,
            "future_batches_require_new_scope_and_user_approval": True,
        },
        "frozen_contract": {
            **protocol.bundle.identity(),
            "transport_protocol_sha256": protocol.sha256,
            "response_contract_sha256": CONTRACT_SHA256,
            "request_bundle_sha256": REQUEST_BUNDLE_SHA256,
        },
        "authorization": {
            "completed_responses_exact": 4,
            "batch_hard_ceiling_usd": 0.1,
            "concurrency": 1,
            "replacement_responses_authorized": False,
            "fifth_response_authorized": False,
            "unused_budget_carryover": False,
            "new_user_approval_required": True,
        },
        "egress": {
            "scheme": "https", "host": "api.deepseek.com", "port": 443,
            "path": "/chat/completions", "trust_environment_proxy": False,
        },
        "forbidden_payload": [
            "raw_market_data", "security_identity", "holdings_orders_or_signals",
            "returns_or_sealed_results", "first_batch_responses_or_reasoning", "paths_or_secrets",
        ],
        "runtime": {
            "implementation_git_head": IMPLEMENTATION_HEAD,
            "image_tag": "shaiwei:ts-v5-r2-canary-001",
            "image_id": "sha256:" + "d" * 64,
            "code_snapshot_sha256": CODE_SNAPSHOT,
            "output_root": "data/research/trend_swing/ts-v5-r2-canary-001",
            "attempt_ledger": "ledger/ts_v5_r2_llm_attempts.csv",
            "transport_ledger": "ledger/ts_v5_r2_llm_transports.csv",
        },
        "pre_execution_gates": {
            "release_commit_pushed_and_head_equals_origin_main": True,
            "implementation_image_identity_matches": True,
            "only_deepseek_api_key_passed_to_container": True,
            "tls_hostname_probe_before_secret_read": True,
            "outbound_request_bundle_matches": True,
            "dedicated_ledgers_pristine": True,
            "scheduler_identity_unchanged_and_healthy": True,
            "no_market_effect_backtest_or_production_access": True,
        },
    }


def completion(request: httpx.Request) -> httpx.Response:
    task = json.loads(json.loads(request.content)["messages"][1]["content"])
    response = {
        "id": f"fixture-{task['attempt_id']}",
        "created": 1786579200 + task["ordinal"],
        "model": "deepseek-v4-pro",
        "choices": [{
            "message": {"content": json.dumps(candidate_document(task["primary_mechanism"]), ensure_ascii=False)},
            "finish_reason": "stop",
        }],
        "usage": {
            "prompt_tokens": 1200, "prompt_cache_hit_tokens": 0,
            "prompt_cache_miss_tokens": 1200, "completion_tokens": 600,
        },
    }
    return httpx.Response(200, json=response, request=request)


def paths(tmp_path: Path) -> tuple[Path, Path, Path, Path, Path]:
    project = tmp_path / "project"
    output = project / "data/research/trend_swing/ts-v5-r2-canary-001"
    attempt = project / "ledger/ts_v5_r2_llm_attempts.csv"
    transport = project / "ledger/ts_v5_r2_llm_transports.csv"
    release = project / "release.yaml"
    output.mkdir(parents=True)
    attempt.parent.mkdir(parents=True)
    attempt.write_text(",".join(ATTEMPT_HEADER) + "\n", encoding="utf-8")
    transport.write_text(",".join(TRANSPORT_LEDGER_HEADER_V2) + "\n", encoding="utf-8")
    release.write_text(yaml.safe_dump(release_document(V5TransportProtocol.load()), sort_keys=False))
    return project, output, attempt, transport, release


def test_r2_preflight_requires_pristine_ledgers_and_bound_runtime(tmp_path: Path) -> None:
    _, _, attempt, transport, release = paths(tmp_path)
    report = run_preflight(
        release_path=release, attempt_path=attempt, transport_path=transport,
        runtime_git_head=lambda: IMPLEMENTATION_HEAD,
        runtime_code_sha=lambda: CODE_SNAPSHOT,
    )
    assert report["gate"] == "PASS"
    assert report["provider_calls"] == 0
    assert report["secret_read"] is False


def test_r2_calls_exactly_four_then_reuses_and_audits_offline(tmp_path: Path) -> None:
    project, output, attempt, transport, release = paths(tmp_path)
    calls = 0

    def provider_factory(protocol, **kwargs):
        nonlocal calls

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            return completion(request)

        return DeepSeekProvider(
            protocol, attempt_id=kwargs["attempt_id"], api_key="fixture-key-never-persisted",
            transport_ledger_path=kwargs["transport_ledger_path"],
            artifact_root=kwargs["artifact_root"], transport=httpx.MockTransport(handler),
            execution_release=kwargs["release"], clock=lambda: "2026-08-13T00:00:00+00:00",
            sleeper=lambda _: None, operator="fixture-ts-v5-r2",
        )

    kwargs = {
        "release_path": release, "output_root": output, "attempt_path": attempt,
        "transport_path": transport, "project_root": project,
        "provider_factory": provider_factory, "tls_probe": lambda _: "b" * 64,
        "runtime_git_head": lambda: IMPLEMENTATION_HEAD,
        "runtime_code_sha": lambda: CODE_SNAPSHOT,
    }
    report = run_batch(**kwargs)
    replay = run_batch(**kwargs)
    audit = audit_batch(
        release_path=release, output_root=output, attempt_path=attempt,
        transport_path=transport, project_root=project,
    )
    assert calls == 4
    assert report["completed_response_count"] == 4
    assert report["independent_response_count"] == 4
    assert report["adversarial_response_count"] == 0
    assert report["actual_cost_usd"] < 0.1
    assert replay["external_api_calls_this_run"] == 0
    assert replay["idempotent_reuse"] is True
    assert audit["verdict"] == "PASS"
    with attempt.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 4
    assert all(row["operator"] == "docker-ts-v5-r2" for row in rows)
    assert all(
        "fixture-key-never-persisted" not in file.read_text(encoding="utf-8")
        for file in project.rglob("*") if file.is_file()
    )


def test_r2_modules_stay_below_architecture_limit() -> None:
    root = Path(__file__).resolve().parents[1]
    modules = (
        "v5_r2_release.py", "v5_r2_live.py", "v5_r2_audit.py",
    )
    assert all(
        len((root / "src/shaiwei/research/trend_swing" / name).read_text().splitlines()) <= 300
        for name in modules
    )


def test_r2_compose_is_short_lived_and_audit_has_no_network() -> None:
    root = Path(__file__).resolve().parents[1]
    compose = yaml.safe_load((root / "compose.ts-v5-r2.yaml").read_text(encoding="utf-8"))
    live, audit = compose["services"]["ts-v5-r2"], compose["services"]["ts-v5-r2-audit"]
    assert live["read_only"] is True
    assert live["cap_drop"] == ["ALL"]
    assert live["environment"] == [
        "DEEPSEEK_API_KEY", "HOME=/tmp", "PYTHONPYCACHEPREFIX=/tmp/pycache",
    ]
    assert audit["network_mode"] == "none"
    assert "DEEPSEEK_API_KEY" not in audit["environment"]
    assert all("/workspace/data/raw" not in str(item) for item in live["volumes"])
