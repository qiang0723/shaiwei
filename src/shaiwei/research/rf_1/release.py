"""RF-1 execution release gate: the LLM batch is fail-closed without a frozen release."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from shaiwei.research.rf_1.contract import (
    EXECUTION_RELEASE_PATH,
    RF1Error,
    RF1Scope,
)


def load_execution_release(scope: RF1Scope, path: Path = EXECUTION_RELEASE_PATH) -> dict[str, Any]:
    """Fail-closed: no batch call without a frozen release bound to the checkpoint evidence."""
    if not path.is_file():
        raise RF1Error(
            "RELEASE_NOT_AUTHORIZED: RF-1 batch requires a frozen execution release, the "
            "completed R2-1 checkpoint evidence, and explicit per-batch user approval"
        )
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise RF1Error("RF-1 execution release is invalid") from exc
    if not isinstance(document, dict):
        raise RF1Error("RF-1 execution release is not a mapping")
    batch = scope.document["batch_contract"]
    required = {
        "schema_version": "rf-1-execution-release-v1",
        "protocol_sha256": scope.sha256,
        "production_authorization": "none",
    }
    for key, expected in required.items():
        if document.get(key) != expected:
            raise RF1Error(f"RF-1 execution release contract differs: {key}")
    if document.get("status") != "FROZEN_R2_1_CHECKPOINT_COMPLETE_USER_BATCH_AUTHORIZED":
        raise RF1Error("RF-1 execution release status differs")
    ceilings = document.get("budget", {})
    ceiling = ceilings.get("single_batch_hard_ceiling_usd")
    if ceiling is None or float(ceiling) != float(batch["single_batch_hard_ceiling_usd"]):
        raise RF1Error("RF-1 release ceiling differs from the frozen protocol")
    for name in ("r2_1_checkpoint_evidence_sha256", "user_batch_authorization_note"):
        value = document.get(name)
        if not isinstance(value, str) or not value.strip():
            raise RF1Error(f"RF-1 execution release is missing {name}")
    return document
