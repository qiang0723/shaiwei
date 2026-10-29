"""TP-F-1 adapter over the audited DeepSeek transport; the secret is read only under an approved release."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping

import httpx

from shaiwei.research.deepseek_client import DeepSeekProvider
from shaiwei.research.tp_f_1.contract import TPF1Error, TPF1Scope
from shaiwei.research.tp_f_1.prompt import PromptBundle

BASE_URL = "https://api.deepseek.com"
REQUEST_TIMEOUT_SECONDS = 900  # 与 M3 相同：thinking 开启、reasoning high、8k 输出时单次可超过数分钟
OPERATOR = "docker-tp-f-1-research"


@dataclass(frozen=True)
class TPF1TransportProtocol:
    """Structural adapter consumed by the existing transport implementation."""

    document: dict[str, Any]
    sha256: str
    provider_name: str = "deepseek"
    requested_model: str = "deepseek-v4-pro"
    returned_model_identity: str = "DeepSeek-V4-Pro"

    @classmethod
    def load(cls, scope: TPF1Scope, prompt: PromptBundle) -> "TPF1TransportProtocol":
        batch = scope.document["batch_contract"]
        document = {
            "provider": {"base_url": BASE_URL, "request_timeout_seconds": REQUEST_TIMEOUT_SECONDS},
            "attempt_budget": {"maximum_transport_retries_per_attempt": int(batch["transport_retries_per_attempt_maximum"])},
        }
        identity = {"protocol_sha256": scope.sha256, "addendum_sha256": scope.addendum_sha256, "prompt_sha256": prompt.sha256,
                    "transport": document}
        digest = hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        return cls(document, digest, requested_model=str(batch["model"]))


@dataclass(frozen=True)
class TPF1ExecutionRelease:
    """The approved scope seen by the transport: id, scope hash and the transport protocol it binds."""

    release_id: str
    sha256: str
    protocol_sha256: str


@dataclass(frozen=True)
class Prices:
    """Per-million USD prices frozen into the scope after the pre-execution official recheck."""

    cache_hit_per_million: Decimal
    cache_miss_per_million: Decimal
    output_per_million: Decimal

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "Prices":
        return cls(*(Decimal(str(value[key])) for key in ("input_cache_hit_per_million_usd", "input_cache_miss_per_million_usd",
                                                         "output_per_million_usd")))

    def cost(self, usage: Mapping[str, Any] | None) -> Decimal:
        if not usage:
            raise TPF1Error("TP-F-1 completed response lacks usage; cost cannot be bounded")
        hit = Decimal(int(usage.get("prompt_cache_hit_tokens", 0)))
        miss = Decimal(int(usage.get("prompt_cache_miss_tokens", usage.get("prompt_tokens", 0))))
        output = Decimal(int(usage.get("completion_tokens", 0)))
        return (hit * self.cache_hit_per_million + miss * self.cache_miss_per_million + output * self.output_per_million) / Decimal(1_000_000)

    def worst_case(self, prompt_tokens: int, output_tokens: int) -> Decimal:
        return (Decimal(prompt_tokens) * self.cache_miss_per_million + Decimal(output_tokens) * self.output_per_million) / Decimal(1_000_000)


def create_live_provider(
    protocol: TPF1TransportProtocol,
    release: TPF1ExecutionRelease | None,
    *,
    attempt_id: str,
    transport_ledger_path: Path,
    artifact_root: Path,
) -> DeepSeekProvider:
    if release is None or release.protocol_sha256 != protocol.sha256:
        raise TPF1Error("TP-F-1 live transport is not authorized; secret and network were not accessed")
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        raise TPF1Error("TP-F-1 DeepSeek API key is missing")
    return DeepSeekProvider(
        protocol,  # type: ignore[arg-type]
        attempt_id=attempt_id,
        api_key=api_key,
        transport_ledger_path=transport_ledger_path,
        artifact_root=artifact_root,
        transport=httpx.HTTPTransport(retries=0),
        execution_release=release,  # type: ignore[arg-type]
        operator=OPERATOR,
    )
