"""Result-before execution release contract for the TS-v5-R3F canary."""

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
from shaiwei.research.trend_swing.v5_bound_proposal_contract import CONTRACT_SHA256
from shaiwei.research.trend_swing.v5_contract import sha256_file
from shaiwei.research.trend_swing.v5_r3f_canary import (
    R3FTransportProtocol,
    SCOPE_PATH,
    SCOPE_SHA256,
)
from shaiwei.research.trend_swing.v5_response_contract import (
    CONTRACT_SHA256 as TERMINAL_CONTRACT_SHA256,
)
from shaiwei.research.trend_swing.v5_transport import (
    BUDGET_RECORD_PATH,
    BUDGET_RECORD_SHA256,
)

REQUEST_BUNDLE_SHA256 = "74eca6f39f088f837c7137d6861f5b61b6c1cac3c89da90d053e1821ca7c3a45"
PROPOSAL_COMPILER_SHA256 = "6b790b50664cf7304ffecc52ad0f6b0878ac2517cbdceeb075260949eebc15dc"
DEFAULT_RELEASE = PROJECT_ROOT / "config/ts_v5_r3f_llm_execution_release_v1.yaml"


@dataclass(frozen=True)
class R3FExecutionRelease:
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
    def load(
        cls, path: Path, protocol: R3FTransportProtocol
    ) -> "R3FExecutionRelease":
        try:
            document = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            raise D1ControlError("TS-v5-R3F execution release is missing or invalid") from exc
        if not isinstance(document, dict):
            raise D1ControlError("TS-v5-R3F execution release must be an object")
        cls._validate_authority(document)
        cls._validate_contract(document, protocol)
        runtime = cls._validate_runtime(document)
        return cls(
            path=path,
            document=document,
            sha256=sha256_file(path),
            release_id=str(document["release_id"]),
            protocol_sha256=protocol.sha256,
            completed_responses_exact=6,
            batch_hard_ceiling_usd=0.15,
            response_model_identity="deepseek-v4-pro",
            implementation_git_head=str(runtime["implementation_git_head"]),
            image_tag=str(runtime["image_tag"]),
            image_id=str(runtime["image_id"]),
            code_snapshot_sha256=str(runtime["code_snapshot_sha256"]),
            output_root=str(runtime["output_root"]),
            attempt_ledger=str(runtime["attempt_ledger"]),
            transport_ledger=str(runtime["transport_ledger"]),
        )

    @staticmethod
    def _validate_authority(document: dict[str, Any]) -> None:
        if (
            document.get("schema_version") != "ts-v5-r3f-llm-execution-release-v1"
            or document.get("release_id") != "ts-v5-r3f-bound-proposal-canary-001"
            or document.get("status") != "TS_V5_R3F_RESULT_BEFORE_EXECUTION_FROZEN"
            or document.get("execution_authorized") is not True
            or document.get("production_authorization") != "none"
        ):
            raise D1ControlError("TS-v5-R3F release identity or authority differs")
        approval = document.get("user_approval", {})
        if (
            approval.get("source") != "user_explicit_approval_primary_codex_thread"
            or re.fullmatch(r"20\d{2}-\d{2}-\d{2}", str(approval.get("approved_on", ""))) is None
            or approval.get("approved_scope_path")
            != "config/ts_v5_r3f_llm_canary_scope_v1.yaml"
            or approval.get("approved_scope_sha256") != SCOPE_SHA256
            or approval.get("completed_responses_exact") != 6
            or approval.get("independent_candidates") != 6
            or approval.get("adversarial_revisions") != 0
            or approval.get("external_request_maximum") != 6
            or approval.get("batch_hard_ceiling_usd") != 0.15
            or approval.get("transport_retry_authorized") is not False
            or approval.get("replacement_or_seventh_response_authorized") is not False
            or sha256_file(SCOPE_PATH) != SCOPE_SHA256
        ):
            raise D1ControlError("TS-v5-R3F release does not match explicit approval")

    @staticmethod
    def _validate_contract(
        document: dict[str, Any], protocol: R3FTransportProtocol
    ) -> None:
        if document.get("frozen_contract") != {
            "scope_sha256": SCOPE_SHA256,
            "transport_protocol_sha256": protocol.sha256,
            "proposal_contract_sha256": CONTRACT_SHA256,
            "proposal_compiler_sha256": PROPOSAL_COMPILER_SHA256,
            "terminal_contract_sha256": TERMINAL_CONTRACT_SHA256,
            "request_bundle_sha256": REQUEST_BUNDLE_SHA256,
        }:
            raise D1ControlError("TS-v5-R3F frozen contract differs")
        budget = document.get("program_budget_context", {})
        if budget != {
            "record_path": "config/ts_v5_llm_research_scope_v2.yaml",
            "record_sha256": BUDGET_RECORD_SHA256,
            "program_hard_ceiling_usd": 5.0,
            "approved_r3f_scope_controls_this_batch": True,
            "program_ceiling_does_not_expand_this_batch": True,
            "future_batches_require_new_scope_and_user_approval": True,
        } or sha256_file(BUDGET_RECORD_PATH) != BUDGET_RECORD_SHA256:
            raise D1ControlError("TS-v5-R3F program budget context differs")
        if document.get("authorization") != {
            "completed_responses_exact": 6,
            "external_request_maximum": 6,
            "maximum_transport_attempts_per_slot": 1,
            "batch_hard_ceiling_usd": 0.15,
            "concurrency": 1,
            "transport_retry_authorized": False,
            "replacement_responses_authorized": False,
            "seventh_response_authorized": False,
            "unused_budget_carryover": False,
            "new_user_approval_required": True,
        }:
            raise D1ControlError("TS-v5-R3F authorization differs")
        if document.get("provider_identity") != {
            "requested_model": "deepseek-v4-pro",
            "expected_model_version": "DeepSeek-V4-Pro",
            "response_model_field": "deepseek-v4-pro",
            "version_and_response_field_are_distinct": True,
            "thinking": "disabled",
            "correction_frozen_before_any_paid_response": True,
        }:
            raise D1ControlError("TS-v5-R3F provider identity differs")
        if document.get("egress") != {
            "scheme": "https", "host": "api.deepseek.com", "port": 443,
            "path": "/chat/completions", "trust_environment_proxy": False,
        }:
            raise D1ControlError("TS-v5-R3F egress differs")
        if document.get("forbidden_payload") != [
            "raw_market_data", "security_identity", "holdings_orders_or_signals",
            "returns_or_sealed_results", "prior_raw_responses_or_reasoning",
            "paths_or_secrets",
        ]:
            raise D1ControlError("TS-v5-R3F payload boundary differs")

    @staticmethod
    def _validate_runtime(document: dict[str, Any]) -> dict[str, Any]:
        runtime = document.get("runtime", {})
        if (
            re.fullmatch(r"[0-9a-f]{40}", str(runtime.get("implementation_git_head", ""))) is None
            or runtime.get("image_tag") != "shaiwei:ts-v5-r3f-canary-001"
            or re.fullmatch(r"sha256:[0-9a-f]{64}", str(runtime.get("image_id", ""))) is None
            or re.fullmatch(r"[0-9a-f]{64}", str(runtime.get("code_snapshot_sha256", ""))) is None
            or runtime.get("output_root")
            != "data/research/trend_swing/ts-v5-r3f-canary-001"
            or runtime.get("attempt_ledger") != "ledger/ts_v5_r3f_llm_attempts.csv"
            or runtime.get("transport_ledger") != "ledger/ts_v5_r3f_llm_transports.csv"
        ):
            raise D1ControlError("TS-v5-R3F runtime differs")
        required = (
            "release_commit_pushed_and_head_equals_origin_main",
            "implementation_image_identity_matches", "only_deepseek_api_key_passed_to_container",
            "tls_hostname_probe_before_secret_read", "outbound_request_bundle_matches",
            "dedicated_ledgers_pristine", "single_transport_attempt_per_slot",
            "scheduler_identity_unchanged_and_healthy",
            "no_market_effect_backtest_or_production_access",
        )
        if any(document.get("pre_execution_gates", {}).get(key) is not True for key in required):
            raise D1ControlError("TS-v5-R3F pre-execution gates differ")
        return runtime


def create_r3f_provider(
    protocol: R3FTransportProtocol,
    *,
    release: R3FExecutionRelease | None,
    attempt_id: str,
    transport_ledger_path: Path,
    artifact_root: Path,
) -> DeepSeekProvider:
    """Read the only secret after the exact no-retry release validates."""
    if release is None or release.protocol_sha256 != protocol.sha256:
        raise D1ControlError("TS-v5-R3F live transport is not authorized")
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        raise D1ControlError("TS-v5-R3F DeepSeek API key is missing")
    return DeepSeekProvider(
        protocol,  # type: ignore[arg-type]
        attempt_id=attempt_id,
        api_key=api_key,
        transport_ledger_path=transport_ledger_path,
        artifact_root=artifact_root,
        transport=httpx.HTTPTransport(retries=0),
        execution_release=release,  # type: ignore[arg-type]
        operator="docker-ts-v5-r3f",
    )
