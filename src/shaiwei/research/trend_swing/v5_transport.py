"""TS-v5 adapter over the audited DeepSeek transport without live authority."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
from typing import Any

import httpx
import yaml

from shaiwei.research.deepseek_client import DeepSeekProvider
from shaiwei.research.llm_factor_contract import D1ControlError
from shaiwei.config import PROJECT_ROOT
from shaiwei.research.trend_swing.v5_contract import V5Bundle, canonical_json, sha256_file, sha256_text

APPROVED_SCOPE_PATH = PROJECT_ROOT / "config/ts_v5_llm_research_scope_v1.yaml"
APPROVED_SCOPE_SHA256 = "9947e1bebc10d5da32df63ff462a8c8e9403a12986dbfef0a891f69956325a88"
BUDGET_RECORD_PATH = PROJECT_ROOT / "config/ts_v5_llm_research_scope_v2.yaml"
BUDGET_RECORD_SHA256 = "a7ab6407db4037be53b7496246e4e200ca2a1d8081d4c31fa1de024b9ee32d56"
INDEPENDENT_REQUEST_BUNDLE_SHA256 = (
    "7de4b42dd849f7298183a97b3622661940c60facf3e69218dba64b523bf8fb25"
)


@dataclass(frozen=True)
class V5TransportProtocol:
    """Small structural adapter consumed by the existing transport implementation."""

    bundle: V5Bundle
    document: dict[str, Any]
    sha256: str
    provider_name: str = "deepseek"
    requested_model: str = "deepseek-v4-pro"
    returned_model_identity: str = "DeepSeek-V4-Pro"

    @classmethod
    def load(cls) -> "V5TransportProtocol":
        bundle = V5Bundle.load()
        document = {
            "provider": {
                "base_url": "https://api.deepseek.com",
                "request_timeout_seconds": 120,
            },
            "attempt_budget": {"maximum_transport_retries_per_attempt": 2},
        }
        identity = {**bundle.identity(), "transport": document}
        return cls(bundle, document, sha256_text(canonical_json(identity)))


@dataclass(frozen=True)
class V5ExecutionRelease:
    path: Path
    document: dict[str, Any]
    sha256: str
    release_id: str
    protocol_sha256: str
    completed_responses_exact: int
    batch_hard_ceiling_usd: float
    response_model_identity: str
    implementation_git_head: str
    image_tag: str
    output_root: str
    attempt_ledger: str
    transport_ledger: str

    @classmethod
    def load(
        cls,
        path: Path,
        protocol: V5TransportProtocol,
        *,
        independent_request_bundle_sha256: str,
    ) -> "V5ExecutionRelease":
        try:
            document = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            raise D1ControlError("TS-v5 live release is missing or invalid") from exc
        if not isinstance(document, dict):
            raise D1ControlError("TS-v5 live release must be an object")
        release_id = str(document.get("release_id", ""))
        if (
            document.get("schema_version") != "ts-v5-llm-execution-release-v1"
            or document.get("status") != "TS_V5_LLM_RESULT_BEFORE_EXECUTION_FROZEN"
            or document.get("execution_authorized") is not True
            or document.get("production_authorization") != "none"
            or re.fullmatch(r"ts-v5-llm-research-batch-[0-9]{3}", release_id) is None
        ):
            raise D1ControlError("TS-v5 live release identity or authority differs")
        approval = document.get("user_approval", {})
        if approval != {
            "source": "user_explicit_approval_primary_codex_thread",
            "approved_on": "2026-08-13",
            "approved_scope_path": "config/ts_v5_llm_research_scope_v1.yaml",
            "approved_scope_sha256": APPROVED_SCOPE_SHA256,
            "completed_responses_exact": 12,
            "independent_candidates": 6,
            "adversarial_revisions": 6,
            "batch_hard_ceiling_usd": 0.5,
        }:
            raise D1ControlError("TS-v5 live release does not match the explicit user approval")
        if sha256_file(APPROVED_SCOPE_PATH) != APPROVED_SCOPE_SHA256:
            raise D1ControlError("TS-v5 approved scope identity differs")
        if document.get("provider_identity") != {
            "requested_model": "deepseek-v4-pro",
            "expected_model_version": "DeepSeek-V4-Pro",
            "response_model_field": "deepseek-v4-pro",
            "version_and_response_field_are_distinct": True,
            "correction_frozen_before_any_paid_response": True,
        }:
            raise D1ControlError("TS-v5 provider identity contract differs")
        budget = document.get("program_budget_context", {})
        if budget != {
            "record_path": "config/ts_v5_llm_research_scope_v2.yaml",
            "record_sha256": BUDGET_RECORD_SHA256,
            "program_hard_ceiling_usd": 5.0,
            "approved_v1_scope_controls_this_batch": True,
            "program_ceiling_does_not_expand_this_batch": True,
            "future_batches_require_new_scope_and_user_approval": True,
        } or sha256_file(BUDGET_RECORD_PATH) != BUDGET_RECORD_SHA256:
            raise D1ControlError("TS-v5 program budget context differs")
        identity = document.get("frozen_contract", {})
        expected_identity = {
            **protocol.bundle.identity(),
            "transport_protocol_sha256": protocol.sha256,
            "independent_request_bundle_sha256": independent_request_bundle_sha256,
        }
        if identity != expected_identity:
            raise D1ControlError("TS-v5 live release does not bind the offline preflight")
        authorization = document.get("authorization", {})
        if authorization != {
            "completed_responses_exact": 12,
            "batch_hard_ceiling_usd": 0.5,
            "concurrency": 1,
            "replacement_responses_authorized": False,
            "unused_budget_carryover": False,
            "new_user_approval_required": True,
        }:
            raise D1ControlError("TS-v5 live release budget or attempt scope differs")
        if document.get("egress") != {
            "scheme": "https",
            "host": "api.deepseek.com",
            "port": 443,
            "path": "/chat/completions",
            "trust_environment_proxy": False,
        }:
            raise D1ControlError("TS-v5 live release egress differs")
        if document.get("forbidden_payload") != [
            "raw_market_data",
            "security_identity",
            "holdings_orders_or_signals",
            "sealed_validation_or_locked_test",
            "forward_or_production_results",
            "paths_or_secrets",
        ]:
            raise D1ControlError("TS-v5 live release payload boundary differs")
        runtime = document.get("runtime", {})
        implementation_head = str(runtime.get("implementation_git_head", ""))
        if (
            re.fullmatch(r"[0-9a-f]{40}", implementation_head) is None
            or runtime.get("image_tag") != "shaiwei:ts-v5-llm-batch-001"
            or runtime.get("output_root")
            != "data/research/trend_swing/ts-v5-llm-batch-001"
            or runtime.get("attempt_ledger") != "ledger/ts_v5_llm_attempts.csv"
            or runtime.get("transport_ledger") != "ledger/ts_v5_llm_transports.csv"
        ):
            raise D1ControlError("TS-v5 live runtime boundary differs")
        gates = document.get("pre_execution_gates", {})
        required_gates = (
            "release_commit_pushed_and_head_equals_origin_main",
            "implementation_image_identity_matches",
            "only_deepseek_api_key_passed_to_container",
            "tls_hostname_probe_before_secret_read",
            "outbound_payload_allowlist_scan",
            "invalid_completed_response_counts_without_replacement",
            "scheduler_identity_unchanged_and_healthy",
            "no_market_effect_backtest_or_production_access",
        )
        if any(gates.get(key) is not True for key in required_gates):
            raise D1ControlError("TS-v5 live pre-execution gates differ")
        return cls(
            path=path,
            document=document,
            sha256=sha256_file(path),
            release_id=release_id,
            protocol_sha256=protocol.sha256,
            completed_responses_exact=12,
            batch_hard_ceiling_usd=0.5,
            response_model_identity=str(document["provider_identity"]["response_model_field"]),
            implementation_git_head=implementation_head,
            image_tag=str(runtime["image_tag"]),
            output_root=str(runtime["output_root"]),
            attempt_ledger=str(runtime["attempt_ledger"]),
            transport_ledger=str(runtime["transport_ledger"]),
        )


def create_live_provider(
    protocol: V5TransportProtocol,
    *,
    release: V5ExecutionRelease | None,
    attempt_id: str,
    transport_ledger_path: Path,
    artifact_root: Path,
) -> DeepSeekProvider:
    """Read the secret only after an exact TS-v5 execution release is supplied."""
    if release is None or release.protocol_sha256 != protocol.sha256:
        raise D1ControlError("TS-v5 live transport is not authorized; secret and network were not accessed")
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        raise D1ControlError("TS-v5 DeepSeek API key is missing")
    return DeepSeekProvider(
        protocol,  # type: ignore[arg-type]
        attempt_id=attempt_id,
        api_key=api_key,
        transport_ledger_path=transport_ledger_path,
        artifact_root=artifact_root,
        transport=httpx.HTTPTransport(retries=0),
        execution_release=release,  # type: ignore[arg-type]
        operator="docker-ts-v5-research",
    )
