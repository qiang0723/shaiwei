"""Frozen contract and immutable paths for the RF-1 formal batch."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from shaiwei.config import PROJECT_ROOT
from shaiwei.research.trend_swing.contract import sha256_file


class RF1Error(RuntimeError):
    """Fail-closed RF-1 contract violation."""


PROTOCOL_PATH = PROJECT_ROOT / "config/rf_1_formal_single_mechanism_v1.yaml"
PROTOCOL_SHA256 = "357975f23a039672bd46d4ba4f77bbf528797f1749980271a7170223ac37afdc"
SEALED_REGISTRY_PATH = PROJECT_ROOT / (
    "data/research/rf/rf-0c-field-identity-preflight-v1-r2/identity_registry.json"
)
SEALED_REGISTRY_SHA256 = "ab97bf51e54f09a189c926275f864184fee5d9c62b32aa5bec4f34237dd9e323"
EXECUTION_RELEASE_PATH = PROJECT_ROOT / "config/rf_1_execution_release_v1.yaml"


@dataclass(frozen=True)
class RF1Scope:
    document: dict[str, Any]
    sha256: str = PROTOCOL_SHA256

    @classmethod
    def load(cls) -> "RF1Scope":
        if PROTOCOL_PATH.is_symlink() or sha256_file(PROTOCOL_PATH) != PROTOCOL_SHA256:
            raise RF1Error("RF-1 frozen protocol differs")
        try:
            document = yaml.safe_load(PROTOCOL_PATH.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            raise RF1Error("RF-1 frozen YAML is invalid") from exc
        if not isinstance(document, dict):
            raise RF1Error("RF-1 frozen YAML is not a mapping")
        batch = document.get("batch_contract", {})
        candidate = document.get("candidate_contract", {})
        execution = document.get("execution_control", {})
        if (
            document.get("schema_version") != "rf-1-formal-single-mechanism-protocol-v1"
            or document.get("status")
            != "RESULT_BLIND_FORMAL_PROTOCOL_FROZEN_PENDING_USER_APPROVAL_AND_R2_1_CHECKPOINT"
            or document.get("production_authorization") != "none"
            or batch.get("completed_responses_maximum") != 8
            or batch.get("qualified_candidates_maximum") != 3
            or float(batch.get("single_batch_hard_ceiling_usd")) != 1.0
            or float(batch.get("total_rf1_ceiling_usd")) != 2.0
            or candidate.get("must_reference_open_and_close") is not True
            or candidate.get("maximum_lookback_trade_days") != 50
            or candidate.get("maximum_expression_tokens") != 20
            or candidate.get("maximum_ast_nodes") != 80
            or execution.get("external_network_only_deepseek_https") is not True
            or execution.get("secret_read_scoped_to_deepseek_key_only") is not True
            or execution.get("same_scope_rerun") != "forbidden"
            or document.get("verdicts", {}).get("production_authorization") != "none"
        ):
            raise RF1Error("RF-1 authority or contract differs")
        return cls(document)


def validate_bound_inputs(scope: RF1Scope, root: Path = PROJECT_ROOT) -> None:
    chain = scope.document["authority_chain"]
    checks = {}
    for name in ("rf_0c_preflight_protocol", "rf_0c_identity_registry"):
        row = chain[name]
        checks[row["path"]] = row["sha256"]
    for relative, expected in checks.items():
        path = root / relative
        if path.is_symlink() or not path.is_file() or sha256_file(path) != expected:
            raise RF1Error(f"RF-1 bound input differs: {relative}")
