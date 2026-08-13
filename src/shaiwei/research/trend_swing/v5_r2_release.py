"""Frozen execution release for the approved TS-v5-R2 contract canary."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
from typing import Any

import httpx
import yaml

from shaiwei.config import PROJECT_ROOT
from shaiwei.research.deepseek_client import DeepSeekProvider
from shaiwei.research.provider_contract import D1ControlError
from shaiwei.research.trend_swing.v5_canary import SCOPE_PATH, SCOPE_SHA256
from shaiwei.research.trend_swing.v5_contract import sha256_file
from shaiwei.research.trend_swing.v5_response_contract import CONTRACT_SHA256
from shaiwei.research.trend_swing.v5_transport import (
    BUDGET_RECORD_PATH,
    BUDGET_RECORD_SHA256,
    V5TransportProtocol,
)

REQUEST_BUNDLE_SHA256 = "0068357f586749d97d40660b3bd737f31afedafc3f7b6671c00f4641c4fe489b"
DEFAULT_RELEASE = PROJECT_ROOT / "config/ts_v5_r2_llm_execution_release_v1.yaml"


@dataclass(frozen=True)
class V5R2ExecutionRelease:
    """Exact live authority layered over immutable R2 engineering contracts."""

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
    image_id: str
    code_snapshot_sha256: str
    output_root: str
    attempt_ledger: str
    transport_ledger: str

    @classmethod
    def load(cls, path: Path, protocol: V5TransportProtocol) -> "V5R2ExecutionRelease":
        try:
            document = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            raise D1ControlError("TS-v5-R2 execution release is missing or invalid") from exc
        if not isinstance(document, dict):
            raise D1ControlError("TS-v5-R2 execution release must be an object")
        if (
            document.get("schema_version") != "ts-v5-r2-llm-execution-release-v1"
            or document.get("release_id") != "ts-v5-r2-response-contract-canary-001"
            or document.get("status") != "TS_V5_R2_RESULT_BEFORE_EXECUTION_FROZEN"
            or document.get("execution_authorized") is not True
            or document.get("production_authorization") != "none"
        ):
            raise D1ControlError("TS-v5-R2 execution release identity or authority differs")
        if document.get("user_approval") != {
            "source": "user_explicit_approval_primary_codex_thread",
            "approved_on": "2026-08-13",
            "approved_scope_path": "config/ts_v5_r2_llm_canary_scope_v1.yaml",
            "approved_scope_sha256": SCOPE_SHA256,
            "completed_responses_exact": 4,
            "independent_candidates": 4,
            "adversarial_revisions": 0,
            "batch_hard_ceiling_usd": 0.1,
            "replacement_or_fifth_response_authorized": False,
        } or sha256_file(SCOPE_PATH) != SCOPE_SHA256:
            raise D1ControlError("TS-v5-R2 execution release does not match user approval")
        expected_contract = {
            **protocol.bundle.identity(),
            "transport_protocol_sha256": protocol.sha256,
            "response_contract_sha256": CONTRACT_SHA256,
            "request_bundle_sha256": REQUEST_BUNDLE_SHA256,
        }
        if document.get("frozen_contract") != expected_contract:
            raise D1ControlError("TS-v5-R2 execution release contract differs")
        if document.get("provider_identity") != {
            "requested_model": "deepseek-v4-pro",
            "expected_model_version": "DeepSeek-V4-Pro",
            "response_model_field": "deepseek-v4-pro",
            "version_and_response_field_are_distinct": True,
            "correction_frozen_before_any_paid_response": True,
        }:
            raise D1ControlError("TS-v5-R2 provider identity contract differs")
        if document.get("program_budget_context") != {
            "record_path": "config/ts_v5_llm_research_scope_v2.yaml",
            "record_sha256": BUDGET_RECORD_SHA256,
            "program_hard_ceiling_usd": 5.0,
            "approved_r2_scope_controls_this_batch": True,
            "program_ceiling_does_not_expand_this_batch": True,
            "future_batches_require_new_scope_and_user_approval": True,
        } or sha256_file(BUDGET_RECORD_PATH) != BUDGET_RECORD_SHA256:
            raise D1ControlError("TS-v5-R2 program budget context differs")
        if document.get("authorization") != {
            "completed_responses_exact": 4,
            "batch_hard_ceiling_usd": 0.1,
            "concurrency": 1,
            "replacement_responses_authorized": False,
            "fifth_response_authorized": False,
            "unused_budget_carryover": False,
            "new_user_approval_required": True,
        }:
            raise D1ControlError("TS-v5-R2 execution release budget or count differs")
        if document.get("egress") != {
            "scheme": "https",
            "host": "api.deepseek.com",
            "port": 443,
            "path": "/chat/completions",
            "trust_environment_proxy": False,
        }:
            raise D1ControlError("TS-v5-R2 execution release egress differs")
        if document.get("forbidden_payload") != [
            "raw_market_data",
            "security_identity",
            "holdings_orders_or_signals",
            "returns_or_sealed_results",
            "first_batch_responses_or_reasoning",
            "paths_or_secrets",
        ]:
            raise D1ControlError("TS-v5-R2 execution release payload boundary differs")
        runtime = document.get("runtime", {})
        head = str(runtime.get("implementation_git_head", ""))
        image_id = str(runtime.get("image_id", ""))
        code_sha = str(runtime.get("code_snapshot_sha256", ""))
        if (
            re.fullmatch(r"[0-9a-f]{40}", head) is None
            or runtime.get("image_tag") != "shaiwei:ts-v5-r2-canary-001"
            or re.fullmatch(r"sha256:[0-9a-f]{64}", image_id) is None
            or re.fullmatch(r"[0-9a-f]{64}", code_sha) is None
            or runtime.get("output_root") != "data/research/trend_swing/ts-v5-r2-canary-001"
            or runtime.get("attempt_ledger") != "ledger/ts_v5_r2_llm_attempts.csv"
            or runtime.get("transport_ledger") != "ledger/ts_v5_r2_llm_transports.csv"
        ):
            raise D1ControlError("TS-v5-R2 execution runtime differs")
        gates = document.get("pre_execution_gates", {})
        if any(
            gates.get(key) is not True
            for key in (
                "release_commit_pushed_and_head_equals_origin_main",
                "implementation_image_identity_matches",
                "only_deepseek_api_key_passed_to_container",
                "tls_hostname_probe_before_secret_read",
                "outbound_request_bundle_matches",
                "dedicated_ledgers_pristine",
                "scheduler_identity_unchanged_and_healthy",
                "no_market_effect_backtest_or_production_access",
            )
        ):
            raise D1ControlError("TS-v5-R2 pre-execution gates differ")
        return cls(
            path, document, sha256_file(path), str(document["release_id"]), protocol.sha256,
            4, 0.1, "deepseek-v4-pro", head, str(runtime["image_tag"]), image_id, code_sha,
            str(runtime["output_root"]), str(runtime["attempt_ledger"]),
            str(runtime["transport_ledger"]),
        )


def create_r2_provider(
    protocol: V5TransportProtocol,
    *,
    release: V5R2ExecutionRelease | None,
    attempt_id: str,
    transport_ledger_path: Path,
    artifact_root: Path,
) -> DeepSeekProvider:
    """Read the sole secret only after exact R2 release validation."""
    if release is None or release.protocol_sha256 != protocol.sha256:
        raise D1ControlError("TS-v5-R2 live transport is not authorized")
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        raise D1ControlError("TS-v5-R2 DeepSeek API key is missing")
    return DeepSeekProvider(
        protocol,  # type: ignore[arg-type]
        attempt_id=attempt_id,
        api_key=api_key,
        transport_ledger_path=transport_ledger_path,
        artifact_root=artifact_root,
        transport=httpx.HTTPTransport(retries=0),
        execution_release=release,  # type: ignore[arg-type]
        operator="docker-ts-v5-r2",
    )
