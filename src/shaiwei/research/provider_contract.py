"""Lightweight provider errors, response envelope, and secret-output sentinels."""

from __future__ import annotations

from dataclasses import dataclass
import re


SENSITIVE_OUTPUT_PATTERNS = (
    re.compile(r"(?<![A-Za-z0-9])sk-[A-Za-z0-9]{20,}"),
    re.compile(r"https://open\.feishu\.cn/open-apis/bot/v2/hook/[0-9a-fA-F-]{32,}"),
)


class D1ControlError(RuntimeError):
    """Fail-closed control boundary shared by provider adapters."""


@dataclass(frozen=True)
class ProviderResponse:
    model: str
    content: str
    reasoning_content: str
    finish_reason: str
    usage: dict[str, int] | None
    completed_at: str
    sensitive_output_detected: bool = False
    source_response_sha256: str = ""
