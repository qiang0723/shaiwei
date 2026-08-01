"""Result-before execution release for the M1-2 STAR50 review batch."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from shaiwei.ledger import sha256_file
from shaiwei.research.llm_factor import D1ControlError
from shaiwei.research.m1_star50_review_contract import (
    CANDIDATE_IDS,
    DEFAULT_RELEASE_PATH,
    M1ReviewProtocol,
)


@dataclass(frozen=True)
class M1ReviewRelease:
    path: Path
    document: dict[str, Any]
    sha256: str
    release_id: str
    protocol_sha256: str
    batch_hard_ceiling_usd: float
    response_model_identity: str
    implementation_git_head: str
    image_tag: str

    @classmethod
    def load(
        cls, path: Path = DEFAULT_RELEASE_PATH, protocol: M1ReviewProtocol | None = None
    ) -> "M1ReviewRelease":
        active_protocol = protocol or M1ReviewProtocol.load()
        try:
            document = yaml.safe_load(path.read_text(encoding="utf-8"))
        except OSError as error:
            raise D1ControlError("M1-2 execution release is missing") from error
        if not isinstance(document, dict):
            raise D1ControlError("M1-2 execution release must be an object")
        if (
            document.get("schema_version")
            != "m1-star50-factor-review-execution-release-v1"
            or document.get("status") != "M1_2_RESULT_BLIND_EXECUTION_FROZEN"
            or document.get("execution_authorized") is not True
            or document.get("production_authorization") != "none"
        ):
            raise D1ControlError("M1-2 execution release identity differs")
        release_id = str(document.get("release_id", ""))
        if re.fullmatch(r"m1-star50-review-v1-batch-[0-9]{3}", release_id) is None:
            raise D1ControlError("M1-2 execution release id is invalid")
        _validate_contract(document, active_protocol)
        authorization = document.get("authorization", {})
        batch = float(authorization.get("review_hard_ceiling_usd", -1))
        if (
            authorization.get("completed_responses_exact") != 8
            or batch != 0.25
            or float(authorization.get("d1_total_authorization_usd", -1)) != 10.0
            or authorization.get("unused_budget_is_not_automatic_authority") is not True
        ):
            raise D1ControlError("M1-2 execution budget differs")
        if document.get("egress") != {
            "scheme": "https",
            "host": "api.deepseek.com",
            "port": 443,
            "path": "/chat/completions",
            "trust_environment_proxy": False,
        }:
            raise D1ControlError("M1-2 egress allowlist differs")
        _validate_provider_and_scope(document, active_protocol)
        contract = document["frozen_contract"]
        return cls(
            path=path,
            document=document,
            sha256=sha256_file(path),
            release_id=release_id,
            protocol_sha256=active_protocol.sha256,
            batch_hard_ceiling_usd=batch,
            response_model_identity=str(active_protocol.document["provider"]["response_model_field"]),
            implementation_git_head=str(contract["implementation_git_head"]),
            image_tag=str(contract["image_tag"]),
        )


def _validate_contract(document: dict[str, Any], protocol: M1ReviewProtocol) -> None:
    contract = document.get("frozen_contract", {})
    source = protocol.document["source_binding"]
    if (
        contract.get("protocol_path") != "config/m1_star50_factor_review_v1.yaml"
        or contract.get("protocol_sha256") != protocol.sha256
        or contract.get("prompt_sha256") != protocol.prompt_sha256
        or contract.get("semantic_protocol_sha256") != protocol.semantic_protocol.sha256
        or contract.get("discovery_manifest_sha256") != source["discovery_manifest_sha256"]
        or contract.get("discovery_report_sha256") != source["discovery_report_sha256"]
        or contract.get("candidate_ids") != list(CANDIDATE_IDS)
        or contract.get("selection_and_formula_identity_immutable") is not True
        or re.fullmatch(r"[0-9a-f]{40}", str(contract.get("implementation_git_head", "")))
        is None
        or contract.get("image_tag") != "shaiwei:m1-star50-review-v1"
    ):
        raise D1ControlError("M1-2 execution release does not bind frozen inputs")


def _validate_provider_and_scope(
    document: dict[str, Any], protocol: M1ReviewProtocol
) -> None:
    scope = document.get("scope", {})
    if any(value is not False for value in scope.values()):
        raise D1ControlError("M1-2 execution scope expands beyond review")
    provider = protocol.document["provider"]
    prices = protocol.document["cost_budget"]
    expected = {
        "rechecked_on": "2026-08-01",
        "model": provider["model"],
        "model_version": "DeepSeek-V4-Pro",
        "response_model_field": provider["response_model_field"],
        "thinking": provider["thinking"],
        "reasoning_effort": provider["reasoning_effort"],
        "input_cache_hit_per_million_usd": float(prices["pro_input_cache_hit_per_million"]),
        "input_cache_miss_per_million_usd": float(prices["pro_input_cache_miss_per_million"]),
        "output_per_million_usd": float(prices["pro_output_per_million"]),
        "price_change_policy": "fail_closed_before_first_request",
    }
    if document.get("provider_contract") != expected:
        raise D1ControlError("M1-2 provider contract differs")
    if document.get("ledgers") != {
        "review": "ledger/m1_star50_factor_reviews.csv",
        "transport": "ledger/m1_star50_factor_review_transports.csv",
        "m1_1_and_d1_ledgers_are_read_only": True,
    }:
        raise D1ControlError("M1-2 ledger boundary differs")
    gates = document.get("pre_execution_gates", {})
    required = (
        "release_commit_pushed_and_HEAD_equals_origin_main",
        "clean_worktree",
        "implementation_image_identity_matches",
        "only_DEEPSEEK_API_KEY_passed_to_container",
        "TLS_hostname_probe_before_secret_read",
        "outbound_payload_result_blind_scan",
        "semantic_gate_runs_before_review_validity",
        "scheduler_identity_unchanged_and_healthy",
        "primary_window_not_used_as_adjudicator",
    )
    if any(gates.get(key) is not True for key in required):
        raise D1ControlError("M1-2 pre-execution gates differ")
