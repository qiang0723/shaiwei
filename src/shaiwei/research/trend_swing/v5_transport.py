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
from shaiwei.research.trend_swing.v5_contract import V5Bundle, canonical_json, sha256_file, sha256_text


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
        return cls(
            path=path,
            document=document,
            sha256=sha256_file(path),
            release_id=release_id,
            protocol_sha256=protocol.sha256,
            completed_responses_exact=12,
            batch_hard_ceiling_usd=0.5,
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
