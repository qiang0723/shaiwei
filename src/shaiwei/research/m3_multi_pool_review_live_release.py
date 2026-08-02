"""User-authorized result-before release for the M3-3 live review batch."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from shaiwei.config import PROJECT_ROOT
from shaiwei.ledger import sha256_file
from shaiwei.research.llm_factor import D1ControlError
from shaiwei.research.m3_multi_pool_review_contract import CANDIDATE_IDS, M3ReviewProtocol
from shaiwei.research.m3_multi_pool_review_release import M3ReviewRelease
from shaiwei.research.m3_multi_pool_review_request import preflight


DEFAULT_LIVE_RELEASE_PATH = (
    PROJECT_ROOT / "config/m3_multi_pool_factor_review_live_execution_v1.yaml"
)


@dataclass(frozen=True)
class M3ReviewLiveRelease:
    path: Path
    document: dict[str, Any]
    sha256: str
    release_id: str
    protocol_sha256: str
    total_authorization_usd: float
    batch_hard_ceiling_usd: float
    response_model_identity: str
    implementation_git_head: str
    image_tag: str

    @classmethod
    def load(
        cls,
        path: Path = DEFAULT_LIVE_RELEASE_PATH,
        protocol: M3ReviewProtocol | None = None,
    ) -> "M3ReviewLiveRelease":
        active_protocol = protocol or M3ReviewProtocol.load()
        try:
            document = yaml.safe_load(path.read_text(encoding="utf-8"))
        except OSError as error:
            raise D1ControlError("M3-3 live release is missing") from error
        if not isinstance(document, dict):
            raise D1ControlError("M3-3 live release must be an object")
        if (
            document.get("schema_version") != "m3-multi-pool-factor-review-live-release-v1"
            or document.get("status") != "M3_3_RESULT_BEFORE_LIVE_EXECUTION_FROZEN"
            or document.get("execution_authorized") is not True
            or document.get("strategy_effective") != "NOT_EVALUATED"
            or document.get("production_authorization") != "none"
        ):
            raise D1ControlError("M3-3 live authority differs")
        release_id = str(document.get("release_id", ""))
        if re.fullmatch(r"m3-star-three-pool-review-v1-batch-[0-9]{3}", release_id) is None:
            raise D1ControlError("M3-3 live release id differs")
        _validate_authorization(document)
        implementation_head, image_tag = _validate_contract(document, active_protocol)
        _validate_provider_scope_and_gates(document, active_protocol)
        authorization = document["authorization"]
        return cls(
            path=path,
            document=document,
            sha256=sha256_file(path),
            release_id=release_id,
            protocol_sha256=active_protocol.sha256,
            total_authorization_usd=float(authorization["d1_total_authorization_usd"]),
            batch_hard_ceiling_usd=float(authorization["review_hard_ceiling_usd"]),
            response_model_identity=str(
                active_protocol.document["provider"]["response_model_field"]
            ),
            implementation_git_head=implementation_head,
            image_tag=image_tag,
        )


def _validate_authorization(document: dict[str, Any]) -> None:
    authorization = document.get("authorization", {})
    payload = document.get("user_payload_contract", {})
    expected_payload = {
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
    }
    if (
        authorization.get("source") != "user_explicit_approval_primary_codex_thread"
        or authorization.get("authorized_on") != "2026-08-02"
        or authorization.get("model") != "deepseek-v4-pro"
        or authorization.get("completed_responses_exact") != 8
        or authorization.get("concurrency") != 1
        or float(authorization.get("review_hard_ceiling_usd", -1)) != 0.25
        or float(authorization.get("d1_total_authorization_usd", -1)) != 10.0
        or authorization.get("unused_budget_is_not_automatic_authority") is not True
        or authorization.get("future_batches_require_new_protocol_and_instruction") is not True
        or payload != expected_payload
    ):
        raise D1ControlError("M3-3 live user authority or payload differs")


def _validate_contract(
    document: dict[str, Any], protocol: M3ReviewProtocol
) -> tuple[str, str]:
    frozen = document.get("frozen_contract", {})
    source = protocol.document["source_binding"]
    preexecution = M3ReviewRelease.load(protocol=protocol)
    implementation_head = str(frozen.get("implementation_git_head", ""))
    image_tag = str(frozen.get("image_tag", ""))
    if (
        frozen.get("protocol_path") != "config/m3_multi_pool_factor_review_v1.yaml"
        or frozen.get("protocol_sha256") != protocol.sha256
        or frozen.get("prompt_sha256") != protocol.prompt_sha256
        or frozen.get("semantic_protocol_sha256") != protocol.semantic_protocol.sha256
        or frozen.get("knowledge_sha256") != protocol.document["knowledge_binding"]["sha256"]
        or frozen.get("discovery_manifest_sha256") != source["discovery_manifest_sha256"]
        or frozen.get("discovery_report_sha256") != source["discovery_report_sha256"]
        or frozen.get("preexecution_release_path")
        != "config/m3_multi_pool_factor_review_execution_v1.yaml"
        or frozen.get("preexecution_release_sha256") != preexecution.sha256
        or frozen.get("preexecution_gate") != "GO_M3_3_PREEXECUTION_ONLY"
        or frozen.get("request_bundle_sha256")
        != preflight(protocol.path)["request_bundle_sha256"]
        or frozen.get("candidate_ids") != list(CANDIDATE_IDS)
        or frozen.get("selection_formula_direction_and_order_immutable") is not True
        or re.fullmatch(r"[0-9a-f]{40}", implementation_head) is None
        or image_tag != "shaiwei:m3-multi-pool-review-v1"
        or frozen.get("output_root")
        != "data/research/m3/m3-star-three-pool-price-volume-v1/m3_3_reviews"
    ):
        raise D1ControlError("M3-3 live release does not bind frozen inputs")
    return implementation_head, image_tag


def _validate_provider_scope_and_gates(
    document: dict[str, Any], protocol: M3ReviewProtocol
) -> None:
    provider = protocol.document["provider"]
    prices = protocol.document["cost_budget"]
    expected_provider = {
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
    }
    expected_scope = {
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
    }
    if document.get("provider_contract") != expected_provider:
        raise D1ControlError("M3-3 live provider contract differs")
    if document.get("scope") != expected_scope:
        raise D1ControlError("M3-3 live scope differs")
    if document.get("egress") != {
        "scheme": "https",
        "host": "api.deepseek.com",
        "port": 443,
        "path": "/chat/completions",
        "trust_environment_proxy": False,
    }:
        raise D1ControlError("M3-3 live egress differs")
    if document.get("ledgers") != {
        "review": "ledger/m3_multi_pool_factor_reviews.csv",
        "transport": "ledger/m3_multi_pool_factor_review_transports.csv",
        "prior_ledgers_remain_byte_immutable": True,
    }:
        raise D1ControlError("M3-3 live ledger boundary differs")
    required = (
        "release_commit_pushed_and_HEAD_equals_origin_main",
        "clean_worktree",
        "implementation_image_identity_matches",
        "only_DEEPSEEK_API_KEY_passed_to_container",
        "TLS_hostname_probe_before_secret_read",
        "outbound_payload_result_blind_scan",
        "schema_and_semantic_gate_before_review_validity",
        "invalid_response_counts_stops_and_is_not_replaced",
        "scheduler_identity_unchanged_and_healthy",
        "primary_window_not_used_as_adjudicator",
    )
    gates = document.get("pre_execution_gates", {})
    if any(gates.get(key) is not True for key in required):
        raise D1ControlError("M3-3 live pre-execution gates differ")
