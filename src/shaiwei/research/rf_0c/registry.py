"""RF-0C registry reproduction against the sealed RF-0B registry."""

from __future__ import annotations

import json
from typing import Any

from shaiwei.research.trend_swing.v6.engine import canonical_json
from shaiwei.research.rf_0b.registry import build_identity_registry
from shaiwei.research.rf_0c.contract import (
    RFCError,
    RFCScope,
    SEALED_RF_0B_REGISTRY_PATH,
)


def build_registry_with_reproduction_check(scope: RFCScope) -> dict[str, Any]:
    registry = build_identity_registry(scope)  # duck-typed: identical frozen_inputs block
    try:
        sealed = json.loads(SEALED_RF_0B_REGISTRY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RFCError("RF-0C sealed RF-0B registry is unavailable") from exc
    if not isinstance(sealed, dict):
        raise RFCError("RF-0C sealed RF-0B registry is not an object")

    def strip(doc: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in doc.items() if key != "protocol_sha256"}

    if canonical_json(strip(registry)) != canonical_json(strip(sealed)):
        raise RFCError("RF-0C identity registry differs from the sealed RF-0B registry")
    return registry
