"""Strict result-sealed contract for the M6-5C-B execution adapter."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from shaiwei.config import PROJECT_ROOT
from shaiwei.research.model_attribution.contract import sha256_file
from shaiwei.research.production_conversion.contract import ProtocolError


BASE_CONFIG_PATH = (
    PROJECT_ROOT
    / "config/m6_csi800_production_head30_delisting_risk_execution_adapter_v1.yaml"
)
CONFIG_PATH = (
    PROJECT_ROOT
    / "config/m6_csi800_production_head30_delisting_risk_execution_adapter_recovery_v1.yaml"
)


def load_execution_adapter(path: Path = CONFIG_PATH) -> dict[str, Any]:
    recovery = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(recovery, dict):
        raise ProtocolError("M6-5C-B-R1 adapter recovery is not a mapping")
    if (
        recovery.get("schema_version")
        != "m6-csi800-production-head30-delisting-risk-execution-adapter-recovery-v1"
        or recovery.get("stage")
        != "RESULT_SEALED_EXECUTION_ADAPTER_RECOVERY_ENGINEERING_ONLY"
    ):
        raise ProtocolError("M6-5C-B-R1 adapter recovery identity differs")
    base_identity = recovery.get("base_protocol", {})
    if (
        base_identity.get("config_path") != str(BASE_CONFIG_PATH.relative_to(PROJECT_ROOT))
        or sha256_file(BASE_CONFIG_PATH) != base_identity.get("config_sha256")
    ):
        raise ProtocolError("M6-5C-B base protocol identity differs")
    base_document = PROJECT_ROOT / str(base_identity.get("document_path", ""))
    if (
        not base_document.is_file()
        or sha256_file(base_document) != base_identity.get("document_sha256")
        or base_identity.get("freeze_commit")
        != "c6da4005f37dc8f5b9ce43b7e62a154fa46de6fe"
    ):
        raise ProtocolError("M6-5C-B base protocol document differs")
    document = yaml.safe_load(BASE_CONFIG_PATH.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ProtocolError("M6-5C-B adapter contract is not a mapping")
    if (
        document.get("schema_version")
        != "m6-csi800-production-head30-delisting-risk-execution-adapter-v1"
        or document.get("stage")
        != "RESULT_SEALED_EXECUTION_ADAPTER_ENGINEERING_ONLY"
    ):
        raise ProtocolError("M6-5C-B adapter identity differs")
    predecessor = document.get("predecessor", {})
    paths = {
        "method_config_sha256": predecessor.get("method_config"),
        "method_module_sha256": "src/shaiwei/research/capital_feasibility/delisting_risk.py",
        "method_acceptance_sha256": (
            "docs/M6_CSI800_PRODUCTION_HEAD30_DELISTING_RISK_METHOD_ACCEPTANCE_20260823.md"
        ),
    }
    if any(
        not relative or sha256_file(PROJECT_ROOT / relative) != predecessor.get(key)
        for key, relative in paths.items()
    ):
        raise ProtocolError("M6-5C-B predecessor identity differs")
    regression = document.get("paper_v1_regression", {})
    if regression != {
        "engine_before_sha256": (
            "44e64d1a776973b0eb5b9ba5ce6d8a7d103a7e8a20aaeb172929c7ca4b1d6b94"
        ),
        "engine_before_lines": 860,
        "synthetic_two_day_canonical_sha256": (
            "dd7b40b33b75f7e5b261bebaf64b8d1e748d6e42f62225da0b4d490f6e9d1faa"
        ),
        "default_and_explicit_empty_directive_must_match": True,
        "order_and_fill_schema_change_authorized": False,
    }:
        raise ProtocolError("M6-5C-B paper-v1 regression identity differs")
    adapter = document.get("adapter_contract", {})
    expected_adapter = {
        "policy_type": "PaperDelistingRiskPortfolio",
        "account_id": "m6_head30_delisting_risk",
        "execution_policy_version": "paper-v2-delisting-risk-exit",
        "forced_exit_parameter": "forced_exit_codes",
        "parameter_default": [],
        "non_rebalance_exit_authorized": True,
        "execution_reason": "DELISTING_PRICE_RISK_EXIT",
        "target_intersection_authorized": False,
        "unheld_or_duplicate_or_bj_authorized": False,
        "target_weight_sum_below_one_authorized_for_v2_only": True,
        "failed_exit_may_create_cash_or_remove_position": False,
        "paper_v1_default_semantics_change_authorized": False,
    }
    if adapter != expected_adapter:
        raise ProtocolError("M6-5C-B adapter semantics differ")
    failure = recovery.get("failure_ruling", {})
    if failure != {
        "original_engine_refactor_verdict": (
            "NO_GO_DUE_TO_ARCHIVED_PREDECESSOR_IDENTITY"
        ),
        "full_regression_failure_count_before_recovery": 23,
        "failure_root": "ARCHIVED_M6_RELEASES_BIND_PAPER_ENGINE_BYTES",
        "real_target_read_count": 0,
        "real_price_read_count": 0,
        "real_effect_read_count": 0,
        "canonical_ledger_write_count": 0,
    }:
        raise ProtocolError("M6-5C-B-R1 failure ruling differs")
    compatibility = recovery.get("compatibility_recovery", {})
    engine_path = PROJECT_ROOT / str(compatibility.get("legacy_engine_path", ""))
    if (
        compatibility.get("legacy_engine_sha256")
        != "44e64d1a776973b0eb5b9ba5ce6d8a7d103a7e8a20aaeb172929c7ca4b1d6b94"
        or sha256_file(engine_path) != compatibility.get("legacy_engine_sha256")
        or compatibility.get("legacy_engine_lines") != 860
        or len(engine_path.read_text(encoding="utf-8").splitlines()) != 860
        or compatibility.get("legacy_engine_mutation_authorized") is not False
        or compatibility.get("maximum_new_module_lines") != 400
        or compatibility.get("explicit_legacy_private_seam_authorized") is not True
        or compatibility.get("paper_v1_dispatch")
        != "EXACT_DELEGATION_WHEN_DIRECTIVE_EMPTY"
        or compatibility.get("paper_v1_nonempty_directive_authorized") is not False
        or compatibility.get("paper_v1_synthetic_two_day_canonical_sha256")
        != "dd7b40b33b75f7e5b261bebaf64b8d1e748d6e42f62225da0b4d490f6e9d1faa"
    ):
        raise ProtocolError("M6-5C-B-R1 compatibility recovery differs")
    for key in ("risk_engine_path", "sell_execution_path", "risk_policy_path"):
        module = PROJECT_ROOT / str(compatibility.get(key, ""))
        if not module.is_file() or len(module.read_text(encoding="utf-8").splitlines()) > 400:
            raise ProtocolError(f"M6-5C-B-R1 module boundary differs: {key}")
    authority = recovery.get("authority", {})
    if (
        authority.get("synthetic_adapter_fixture_authorized") is not True
        or authority.get("compatibility_recovery_authorized") is not True
        or authority.get("paper_engine_refactor_authorized") is not False
    ):
        raise ProtocolError("M6-5C-B engineering authority is absent")
    allowed = {
        "synthetic_adapter_fixture_authorized",
        "compatibility_recovery_authorized",
        "paper_engine_refactor_authorized",
    }
    if any(value not in (False, "none") for key, value in authority.items() if key not in allowed):
        raise ProtocolError("M6-5C-B authority was broadened")
    if authority.get("production_authorization") != "none":
        raise ProtocolError("M6-5C-B cannot authorize production")
    merged = dict(document)
    merged["authority"] = authority
    merged["recovery"] = recovery
    return merged
