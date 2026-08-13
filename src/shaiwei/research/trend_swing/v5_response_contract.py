"""Explicit TS-v5 response profile and terminal-response gate."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import yaml

from shaiwei.config import PROJECT_ROOT
from shaiwei.research.provider_contract import D1ControlError, ProviderResponse
from shaiwei.research.trend_swing.v5_contract import V5Bundle, sha256_file
from shaiwei.research.trend_swing.v5_models import MechanismCandidate
from shaiwei.research.trend_swing.v5_prompt import AttemptPlan, build_request

CONTRACT_PATH = PROJECT_ROOT / "config/ts_v5_llm_response_contract_v2.yaml"
CONTRACT_SHA256 = "c254b41e9ab8f37254944cf9f759ae55c77c69f15119e1e87d296e3a0d091a02"


@dataclass(frozen=True)
class V5ResponseContract:
    """Fail-closed v2 profile; selecting it must remain explicit."""

    document: dict[str, Any]
    sha256: str
    max_tokens: int

    @classmethod
    def load(cls, path: Path = CONTRACT_PATH) -> "V5ResponseContract":
        try:
            resolved = path.resolve(strict=True)
            resolved.relative_to(PROJECT_ROOT.resolve(strict=True))
        except (FileNotFoundError, RuntimeError, ValueError) as exc:
            raise D1ControlError("TS-v5 response contract is missing or outside the project") from exc
        if path.is_symlink() or sha256_file(resolved) != CONTRACT_SHA256:
            raise D1ControlError("TS-v5 response contract identity differs")
        try:
            document = yaml.safe_load(resolved.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            raise D1ControlError("TS-v5 response contract is invalid") from exc
        if not isinstance(document, dict):
            raise D1ControlError("TS-v5 response contract must be an object")
        profile = document.get("future_request_profile", {})
        gate = document.get("terminal_response_gate", {})
        authority = document.get("authority", {})
        if (
            document.get("schema_version") != "ts-v5-llm-response-contract-v2"
            or document.get("status") != "FROZEN_ENGINEERING_ONLY_NO_LIVE_AUTHORITY"
            or profile.get("thinking") != {"type": "disabled"}
            or profile.get("reasoning_effort") != "OMITTED"
            or profile.get("response_format") != {"type": "json_object"}
            or profile.get("max_tokens") != 1800
            or profile.get("tools") != []
            or profile.get("stream") is not False
            or gate.get("accepted_finish_reasons") != ["stop"]
            or gate.get("reasoning_content_is_never_candidate") is not True
            or gate.get("length_is_always_failure") is not True
            or authority.get("external_api_calls") != 0
            or authority.get("future_live_calls_require_new_scope_and_user_approval") is not True
            or authority.get("production_authorization") != "none"
        ):
            raise D1ControlError("TS-v5 response contract broadens its frozen boundary")
        return cls(document=document, sha256=CONTRACT_SHA256, max_tokens=1800)

    def apply_request_profile(self, request: Mapping[str, Any]) -> dict[str, Any]:
        """Derive v2 from a valid v1 request without changing its research content."""
        if (
            request.get("thinking") != {"type": "enabled"}
            or request.get("reasoning_effort") != "high"
            or request.get("response_format") != {"type": "json_object"}
            or request.get("max_tokens") != self.max_tokens
            or request.get("tools") != []
            or request.get("stream") is not False
        ):
            raise D1ControlError("TS-v5 legacy request profile differs before v2 derivation")
        profiled = dict(request)
        profiled["thinking"] = {"type": "disabled"}
        del profiled["reasoning_effort"]
        return profiled

    def terminal_failure(self, response: ProviderResponse) -> str:
        """Classify transport completion before JSON or candidate validation."""
        if response.finish_reason == "length":
            usage = response.usage if isinstance(response.usage, dict) else {}
            if (
                not response.content.strip()
                and bool(response.reasoning_content.strip())
                and usage.get("completion_tokens") == self.max_tokens
            ):
                return "OUTPUT_BUDGET_EXHAUSTED_IN_REASONING"
            return "PROVIDER_OUTPUT_TRUNCATED"
        if response.finish_reason != "stop":
            return "PROVIDER_FINISH_REASON_INVALID"
        if not response.content.strip():
            return "PROVIDER_EMPTY_FINAL_CONTENT"
        return ""


def build_request_v2(
    bundle: V5Bundle,
    plan: AttemptPlan,
    *,
    contract: V5ResponseContract | None = None,
    parent: MechanismCandidate | None = None,
    parent_attempt_fingerprint: str | None = None,
    parent_failure_class: str | None = None,
    discovery_feedback: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the same bounded task with the explicit v2 response profile."""
    request = build_request(
        bundle,
        plan,
        parent=parent,
        parent_attempt_fingerprint=parent_attempt_fingerprint,
        parent_failure_class=parent_failure_class,
        discovery_feedback=discovery_feedback,
    )
    return (contract or V5ResponseContract.load()).apply_request_profile(request)
