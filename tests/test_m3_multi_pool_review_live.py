import hashlib
import json

import pytest
import yaml

from shaiwei.config import PROJECT_ROOT
from shaiwei.provenance import git_head
from shaiwei.research.llm_factor import D1ControlError, ProviderResponse
from shaiwei.research.llm_review_semantics import FAIL, PASS
from shaiwei.research.m3_multi_pool_review_contract import CANDIDATE_IDS, M3ReviewProtocol
from shaiwei.research.m3_multi_pool_review_live import classify_response, run_live_preflight
from shaiwei.research.m3_multi_pool_review_live_release import M3ReviewLiveRelease
from shaiwei.research.m3_multi_pool_review_release import M3ReviewRelease
from shaiwei.research.m3_multi_pool_review_request import plan_review, preflight


PROTOCOL_PATH = PROJECT_ROOT / "config/m3_multi_pool_factor_review_v1.yaml"
TERMINAL_MANIFEST_PATH = PROJECT_ROOT / "config/m3_multi_pool_factor_review_manifest_v1.json"


def _release_document(implementation_head: str) -> dict:
    protocol = M3ReviewProtocol.load(PROTOCOL_PATH)
    preexecution = M3ReviewRelease.load(protocol=protocol)
    provider = protocol.document["provider"]
    prices = protocol.document["cost_budget"]
    return {
        "schema_version": "m3-multi-pool-factor-review-live-release-v1",
        "release_id": "m3-star-three-pool-review-v1-batch-001",
        "prepared_at": "2026-08-02T21:00:00+08:00",
        "status": "M3_3_RESULT_BEFORE_LIVE_EXECUTION_FROZEN",
        "execution_authorized": True,
        "strategy_effective": "NOT_EVALUATED",
        "production_authorization": "none",
        "authorization": {
            "source": "user_explicit_approval_primary_codex_thread",
            "authorized_on": "2026-08-02",
            "model": "deepseek-v4-pro",
            "completed_responses_exact": 8,
            "concurrency": 1,
            "review_hard_ceiling_usd": 0.25,
            "d1_total_authorization_usd": 10.0,
            "unused_budget_is_not_automatic_authority": True,
            "future_batches_require_new_protocol_and_instruction": True,
        },
        "user_payload_contract": {
            "candidate_ids": list(CANDIDATE_IDS),
            "fixed_formulas": True,
            "non_authoritative_hypotheses_and_summaries": True,
            "public_knowledge_summary": True,
            "three_pool_definitions": True,
            "four_narrow_role_questions": True,
            "discovery_metrics": False,
            "raw_market_data": False,
            "security_list": False,
            "sealed_results": False,
            "returns_or_holdings": False,
            "local_paths_or_logs": False,
            "other_credentials": False,
        },
        "frozen_contract": {
            "protocol_path": "config/m3_multi_pool_factor_review_v1.yaml",
            "protocol_sha256": protocol.sha256,
            "prompt_sha256": protocol.prompt_sha256,
            "semantic_protocol_sha256": protocol.semantic_protocol.sha256,
            "knowledge_sha256": protocol.document["knowledge_binding"]["sha256"],
            "discovery_manifest_sha256": protocol.document["source_binding"][
                "discovery_manifest_sha256"
            ],
            "discovery_report_sha256": protocol.document["source_binding"][
                "discovery_report_sha256"
            ],
            "preexecution_release_path": "config/m3_multi_pool_factor_review_execution_v1.yaml",
            "preexecution_release_sha256": preexecution.sha256,
            "preexecution_gate": "GO_M3_3_PREEXECUTION_ONLY",
            "request_bundle_sha256": preflight(PROTOCOL_PATH)["request_bundle_sha256"],
            "candidate_ids": list(CANDIDATE_IDS),
            "selection_formula_direction_and_order_immutable": True,
            "implementation_git_head": implementation_head,
            "image_tag": "shaiwei:m3-multi-pool-review-v1",
            "output_root": (
                "data/research/m3/m3-star-three-pool-price-volume-v1/m3_3_reviews"
            ),
        },
        "provider_contract": {
            "rechecked_on": "2026-08-02",
            "official_pricing_url": "https://api-docs.deepseek.com/quick_start/pricing",
            "model": provider["model"],
            "model_version": "DeepSeek-V4-Pro",
            "response_model_field": provider["response_model_field"],
            "thinking": provider["thinking"],
            "reasoning_effort": provider["reasoning_effort"],
            "json_output": True,
            "input_cache_hit_per_million_usd": float(
                prices["pro_input_cache_hit_per_million"]
            ),
            "input_cache_miss_per_million_usd": float(
                prices["pro_input_cache_miss_per_million"]
            ),
            "output_per_million_usd": float(prices["pro_output_per_million"]),
            "price_or_model_change_policy": "fail_closed_before_first_request",
        },
        "scope": {
            "result_blind_review": True,
            "new_candidate_generation": False,
            "formula_direction_or_window_change": False,
            "third_place_replacement": False,
            "discovery_metric_access": False,
            "sealed_validation_access": False,
            "stress_period_access": False,
            "g1_run": False,
            "model_or_portfolio_run": False,
            "backtest_or_signal_run": False,
            "forward_or_production_access": False,
            "scheduler_changes": False,
            "web_changes": False,
            "guanxiang_access": False,
        },
        "egress": {
            "scheme": "https",
            "host": "api.deepseek.com",
            "port": 443,
            "path": "/chat/completions",
            "trust_environment_proxy": False,
        },
        "ledgers": {
            "review": "ledger/m3_multi_pool_factor_reviews.csv",
            "transport": "ledger/m3_multi_pool_factor_review_transports.csv",
            "prior_ledgers_remain_byte_immutable": True,
        },
        "pre_execution_gates": {
            "release_commit_pushed_and_HEAD_equals_origin_main": True,
            "clean_worktree": True,
            "implementation_image_identity_matches": True,
            "only_DEEPSEEK_API_KEY_passed_to_container": True,
            "TLS_hostname_probe_before_secret_read": True,
            "outbound_payload_result_blind_scan": True,
            "schema_and_semantic_gate_before_review_validity": True,
            "invalid_response_counts_stops_and_is_not_replaced": True,
            "scheduler_identity_unchanged_and_healthy": True,
            "primary_window_not_used_as_adjudicator": True,
        },
    }


def _write_release(tmp_path, document: dict):
    path = tmp_path / "live-release.yaml"
    path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
    return path


def _review_document(candidate_id: str, role: str) -> dict:
    return {
        "schema_version": "m3-adversarial-review-response-v1",
        "candidate_id": candidate_id,
        "role": role,
        "role_verdict": "NO_BLOCKER_FOUND",
        "summary": (
            "No blocking construct issue is identified for the exact frozen expression "
            "within this narrowly assigned review role."
        ),
        "findings": [
            {
                "severity": "minor",
                "category": "conditional_mechanism",
                "statement": (
                    "The exact frozen claim remains conditional on its stated market mechanism."
                ),
                "falsification_or_resolution": (
                    "Keep the frozen expression unchanged and test only under a later frozen protocol."
                ),
            }
        ],
        "formula_change_or_new_candidate_proposed": False,
        "performance_claim_made": False,
    }


def _provider_response(content: str, *, model: str = "deepseek-v4-pro") -> ProviderResponse:
    return ProviderResponse(
        model=model,
        content=content,
        reasoning_content="bounded fixture reasoning",
        finish_reason="stop",
        usage={
            "prompt_tokens": 1200,
            "prompt_cache_hit_tokens": 200,
            "prompt_cache_miss_tokens": 1000,
            "completion_tokens": 300,
            "total_tokens": 1500,
        },
        completed_at="2026-08-02T13:00:00+00:00",
        sensitive_output_detected=False,
        source_response_sha256=hashlib.sha256(content.encode()).hexdigest(),
    )


def test_live_release_binds_exact_user_payload_and_budget(tmp_path):
    path = _write_release(tmp_path, _release_document("a" * 40))
    release = M3ReviewLiveRelease.load(path, M3ReviewProtocol.load(PROTOCOL_PATH))
    assert release.batch_hard_ceiling_usd == 0.25
    assert release.response_model_identity == "deepseek-v4-pro"
    tampered = _release_document("a" * 40)
    tampered["user_payload_contract"]["raw_market_data"] = True
    with pytest.raises(D1ControlError, match="payload differs"):
        M3ReviewLiveRelease.load(
            _write_release(tmp_path, tampered), M3ReviewProtocol.load(PROTOCOL_PATH)
        )


def test_live_response_classification_runs_structure_and_semantics(tmp_path):
    protocol = M3ReviewProtocol.load(PROTOCOL_PATH)
    release = M3ReviewLiveRelease.load(
        _write_release(tmp_path, _release_document("a" * 40)), protocol
    )
    plan = plan_review(protocol, 1)
    document = _review_document(plan.candidate.candidate_id, plan.role)
    valid = classify_response(protocol, release, plan, _provider_response(json.dumps(document)))
    assert valid["schema_status"] == "PASS"
    assert valid["semantic_status"] == PASS
    assert valid["failure_class"] == ""

    document["findings"][0]["falsification_or_resolution"] = (
        "Replace the formula with a normalized alternative before validation."
    )
    changed = classify_response(protocol, release, plan, _provider_response(json.dumps(document)))
    assert changed["schema_status"] == "PASS"
    assert changed["semantic_status"] == FAIL
    assert changed["failure_class"] == "semantic_contract_violation"

    wrong_model = classify_response(
        protocol, release, plan, _provider_response("{}", model="deepseek-v4-flash")
    )
    assert wrong_model["schema_status"] == "NOT_EVALUATED"
    assert wrong_model["failure_class"] == "provider_model_identity_mismatch"


def test_live_preflight_is_pristine_zero_api_and_reads_no_secret(tmp_path, monkeypatch):
    path = _write_release(tmp_path, _release_document(git_head()))
    monkeypatch.setattr(
        "shaiwei.research.m3_multi_pool_review_live.review_rows",
        lambda review_path, release: [],
    )
    monkeypatch.setattr(
        "shaiwei.research.m3_multi_pool_review_live._transport_rows",
        lambda transport_path, release: [],
    )
    report = run_live_preflight(protocol_path=PROTOCOL_PATH, release_path=path)
    assert report["live_preflight_gate"] == "PASS"
    assert report["execution_authorized"] is True
    assert report["authorized_completed_responses_exact"] == 8
    assert report["provider_calls"] == 0
    assert report["api_key_read"] is False
    assert report["review_ledger_rows"] == 0
    assert report["transport_ledger_rows"] == 0
    assert report["sealed_validation_read"] is False


def test_live_compose_exposes_secret_only_to_live_service():
    compose = yaml.safe_load((PROJECT_ROOT / "compose.research.yaml").read_text())
    services = compose["services"]
    assert "DEEPSEEK_API_KEY" not in services["m3-multi-pool-review-live-preflight"].get(
        "environment", {}
    )
    assert "DEEPSEEK_API_KEY" not in services["m3-multi-pool-review-verify"].get(
        "environment", {}
    )
    assert "DEEPSEEK_API_KEY" in services["m3-multi-pool-review-live"]["environment"]
    assert services["m3-multi-pool-review-live-preflight"]["network_mode"] == "none"
    assert services["m3-multi-pool-review-verify"]["network_mode"] == "none"


def test_terminal_manifest_binds_append_only_ledgers_and_stops_before_m3_4():
    manifest = json.loads(TERMINAL_MANIFEST_PATH.read_text(encoding="utf-8"))
    assert manifest["verdict"] == "STOP_M3_3_REVIEW_CONTRACT"
    assert manifest["candidate_decisions"] == {}
    assert manifest["m3_4_validation_protocol_authorized"] is False
    assert manifest["response_gate"]["completed_response_count"] == 1
    assert manifest["response_gate"]["completed_responses_required"] == 8
    for key, relative_path in (
        ("review_ledger_sha256", "ledger/m3_multi_pool_factor_reviews.csv"),
        (
            "transport_ledger_sha256",
            "ledger/m3_multi_pool_factor_review_transports.csv",
        ),
        ("m3_2_attempt_ledger_sha256", "ledger/m3_multi_pool_factor_attempts.csv"),
    ):
        actual = hashlib.sha256((PROJECT_ROOT / relative_path).read_bytes()).hexdigest()
        assert actual == manifest["static_evidence"][key]
