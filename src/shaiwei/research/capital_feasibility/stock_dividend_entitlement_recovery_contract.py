"""Frozen result-blind contract for the M6-5C-C-R3 entitlement adapter."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import yaml

from shaiwei.config import PROJECT_ROOT
from shaiwei.research.model_attribution.contract import sha256_file
from shaiwei.research.production_conversion.contract import ProtocolError


PROTOCOL_PATH = (
    PROJECT_ROOT
    / "config/m6_csi800_production_head30_stock_dividend_entitlement_recovery_v1.yaml"
)
LEGACY_ENGINE_SHA256 = "44e64d1a776973b0eb5b9ba5ce6d8a7d103a7e8a20aaeb172929c7ca4b1d6b94"
LEGACY_RISK_ENGINE_SHA256 = (
    "634b4bb32428f3646e2805ab745dfb600544f0802517c3d8a5df767b53c9fd31"
)


def _mapping(path: Path) -> dict[str, Any]:
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise ProtocolError("M6-5C-C-R3 protocol is missing or invalid") from error
    if not isinstance(document, dict):
        raise ProtocolError("M6-5C-C-R3 protocol is not a mapping")
    return document


def _validate_predecessor(document: dict[str, Any]) -> None:
    predecessor = document.get("predecessor", {})
    failure_path = PROJECT_ROOT / str(predecessor.get("failure_evidence", ""))
    document_path = PROJECT_ROOT / str(predecessor.get("failure_document", ""))
    if (
        sha256_file(failure_path) != predecessor.get("failure_evidence_sha256")
        or sha256_file(document_path) != predecessor.get("failure_document_sha256")
        or predecessor.get("failed_release_scope_sha256")
        != "94a4560553cd67899988276f336cc103de052b2088a2d4adbb63e5ff2d2e9829"
        or predecessor.get("failed_experiment_id") != "6797875cf3c0"
        or predecessor.get("attempt_family")
        != "m6_head30_500k_delisting_risk_overlay_v1"
        or predecessor.get("family_attempts_before_future_recovery") != 1
        or predecessor.get("same_failed_scope_retry_authorized") is not False
    ):
        raise ProtocolError("M6-5C-C-R3 predecessor identity differs")


def _validate_frozen_legacy(document: dict[str, Any]) -> None:
    frozen = document.get("frozen_legacy", {})
    engine = PROJECT_ROOT / "src/shaiwei/paper/engine.py"
    risk_engine = PROJECT_ROOT / "src/shaiwei/paper/risk_exit_engine.py"
    sell = PROJECT_ROOT / "src/shaiwei/paper/sell_execution.py"
    if (
        frozen.get("paper_v1_engine_sha256") != LEGACY_ENGINE_SHA256
        or sha256_file(engine) != LEGACY_ENGINE_SHA256
        or len(engine.read_text(encoding="utf-8").splitlines()) != 860
        or frozen.get("paper_v1_mutation_authorized") is not False
        or frozen.get("paper_v1_two_day_golden_sha256")
        != "dd7b40b33b75f7e5b261bebaf64b8d1e748d6e42f62225da0b4d490f6e9d1faa"
        or frozen.get("risk_engine_before_sha256") != LEGACY_RISK_ENGINE_SHA256
        or sha256_file(risk_engine) != LEGACY_RISK_ENGINE_SHA256
        or sha256_file(sell) != frozen.get("sell_execution_before_sha256")
    ):
        raise ProtocolError("M6-5C-C-R3 frozen legacy identity differs")


def _validate_change(document: dict[str, Any]) -> None:
    change = document.get("single_change", {})
    credit = change.get("detached_stock_credit", {})
    if (
        change.get("strategy_version") != "paper-v2-delisting-risk-exit"
        or change.get("adapter_module")
        != "src/shaiwei/paper/stock_dividend_entitlement.py"
        or change.get("record_date_entitlement_survives_position_sale") is not True
        or credit.get("position_cost_basis") != "0.00"
        or credit.get("cash_change") != "0.00"
        or credit.get("fee_change") != "0.00"
        or credit.get("order_or_fill_created") is not False
        or credit.get("event_schema_change_authorized") is not False
        or any(
            change.get(key) is not False
            for key in (
                "existing_position_semantics_change_authorized",
                "cash_dividend_semantics_change_authorized",
                "fractional_share_semantics_change_authorized",
                "receivable_valuation_between_record_and_listing_authorized",
                "risk_trigger_or_exit_parameter_change_authorized",
            )
        )
    ):
        raise ProtocolError("M6-5C-C-R3 single change differs")


def _validate_authority(document: dict[str, Any]) -> None:
    authority = document.get("authority", {})
    allowed = {
        "protocol_freeze_authorized",
        "synthetic_adapter_engineering_authorized",
        "synthetic_fixture_authorized",
    }
    if any(authority.get(key) is not True for key in allowed) or any(
        value not in (False, "none")
        for key, value in authority.items()
        if key not in allowed
    ):
        raise ProtocolError("M6-5C-C-R3 authority was broadened")
    attempt = document.get("future_attempt", {})
    if attempt != {
        "attempt_family": "m6_head30_500k_delisting_risk_overlay_v1",
        "attempt_ordinal": 2,
        "family_attempts_before_run": 1,
        "new_attempts_if_later_authorized": 1,
        "same_scope_retry_authorized": False,
    }:
        raise ProtocolError("M6-5C-C-R3 future attempt differs")


def load_entitlement_recovery(path: Path = PROTOCOL_PATH) -> dict[str, Any]:
    document = _mapping(path)
    if (
        document.get("schema_version")
        != "m6-csi800-production-head30-stock-dividend-entitlement-recovery-v1"
        or document.get("stage")
        != "RESULT_BLIND_PAPER_V2_STOCK_DIVIDEND_ENTITLEMENT_ENGINEERING_ONLY"
        or document.get("production_authorization") != "none"
    ):
        raise ProtocolError("M6-5C-C-R3 protocol identity differs")
    _validate_predecessor(document)
    _validate_frozen_legacy(document)
    _validate_change(document)
    _validate_authority(document)
    document["protocol_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    return document
