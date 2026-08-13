"""Shared read-only primitives for TS-v5 runtime evidence audits."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Protocol

from shaiwei.research.deepseek_client import TRANSPORT_LEDGER_HEADER_V2
from shaiwei.research.provider_contract import D1ControlError, ProviderResponse


class ReleaseIdentity(Protocol):
    release_id: str
    sha256: str


def json_object(path: Path, *, label: str = "TS-v5") -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise D1ControlError(f"{label} audit JSON is invalid: {path.name}") from exc
    if not isinstance(value, dict):
        raise D1ControlError(f"{label} audit JSON must be an object")
    return value


def transport_rows(
    path: Path, release: ReleaseIdentity, *, label: str = "TS-v5"
) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
    if tuple(reader.fieldnames or ()) != TRANSPORT_LEDGER_HEADER_V2:
        raise D1ControlError(f"{label} transport ledger schema differs")
    if len({row["event_id"] for row in rows}) != len(rows):
        raise D1ControlError(f"{label} transport event ids are duplicated")
    if any(
        row["execution_release_id"] != release.release_id
        or row["execution_release_sha256"] != release.sha256 for row in rows
    ):
        raise D1ControlError(f"{label} transport release differs")
    if any(row["event_type"] == "BILLING_UNCERTAIN" for row in rows):
        raise D1ControlError(f"{label} audit found billing uncertainty")
    return rows


def provider_response(document: dict[str, Any], *, label: str = "TS-v5") -> ProviderResponse:
    try:
        return ProviderResponse(
            model=str(document["model"]), content=str(document["content"]),
            reasoning_content=str(document["reasoning_content"]),
            finish_reason=str(document["finish_reason"]), usage=document["usage"],
            completed_at=str(document["completed_at"]),
            sensitive_output_detected=bool(document["sensitive_output_detected"]),
            source_response_sha256=str(document["source_response_sha256"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise D1ControlError(f"{label} raw envelope schema differs") from exc
