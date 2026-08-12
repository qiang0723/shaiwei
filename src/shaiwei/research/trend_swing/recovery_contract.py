"""Frozen TS-1A-R1 recovery, release-scope, and approval contracts."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any

import yaml

from shaiwei.config import PROJECT_ROOT
from shaiwei.research.trend_swing.contract import (
    TrendSwingError,
    canonical_sha256,
    project_path,
    sha256_file,
)

RECOVERY_PROTOCOL_PATH = PROJECT_ROOT / "config/ts_v3_data_gate_recovery_v1.yaml"
RECOVERY_ADDENDUM_PATH = PROJECT_ROOT / "config/ts_v3_data_gate_recovery_addendum_v1.yaml"
RECOVERY_R2_PATH = PROJECT_ROOT / "config/ts_v3_data_gate_recovery_r2_v1.yaml"
RECOVERY_R2_ADDENDUM_PATH = (
    PROJECT_ROOT / "config/ts_v3_data_gate_recovery_r2_addendum_v1.yaml"
)
RELEASE_SCOPE_PATH = PROJECT_ROOT / "docs/TS_V3_DATA_GATE_RECOVERY_R3_RELEASE_V1.yaml"
APPROVAL_SCOPE_ENV = "SHAIWEI_TS_R3_APPROVAL_SCOPE_SHA256"
RECOVERY_OUTPUT_DIR = PROJECT_ROOT / "data/research/trend_swing/ts-v3-data-gate-r3"
CLAIM_PATH = RECOVERY_OUTPUT_DIR / "network_claim.json"
MANIFEST_PATH = RECOVERY_OUTPUT_DIR / "input_manifest.json"
PROFILE_PATH = RECOVERY_OUTPUT_DIR / "profile_report.json"
AUDIT_PATH = RECOVERY_OUTPUT_DIR / "audit.json"
DAILY_PROFILE_PATH = RECOVERY_OUTPUT_DIR / "anonymous_daily_profile.parquet"
NETWORK_RECEIPT_PATH = RECOVERY_OUTPUT_DIR / "network_receipt.json"

CHINEXT_REQUEST = {
    "ts_code": "399006.SZ",
    "start_date": "20160101",
    "end_date": "20260811",
    "fields": "ts_code,trade_date,open,high,low,close,pre_close,change,pct_chg,vol,amount",
}
STAR50_TAIL_REQUEST = {
    "ts_code": "000688.SH",
    "start_date": "20260725",
    "end_date": "20260811",
    "fields": "ts_code,trade_date,open,high,low,close,pre_close,change,pct_chg,vol,amount",
}
EXPECTED_REQUESTS = (CHINEXT_REQUEST, STAR50_TAIL_REQUEST)
CSI800_GAP_REQUEST = {
    "ts_code": "000906.SH",
    "start_date": "20260715",
    "end_date": "20260715",
    "fields": "ts_code,trade_date,open,high,low,close,pre_close,change,pct_chg,vol,amount",
}
EXPECTED_R3_REQUESTS = (*EXPECTED_REQUESTS, CSI800_GAP_REQUEST)


def _load_yaml(path: Path) -> dict[str, Any]:
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise TrendSwingError(f"TS recovery document is not a mapping: {path.name}")
    return document


def _forbidden_authority(document: dict[str, Any]) -> None:
    authority = document.get("authorization", {})
    forbidden = (
        "read_post_entry_return",
        "read_mae_mfe",
        "model_training",
        "model_prediction",
        "strategy_backtest",
        "candidate_effect_evaluation",
        "paper_account",
        "production_change",
        "web_implementation",
        "deepseek_or_other_llm",
        "network_execution_authorized",
        "env_or_secret_read_authorized",
    )
    if any(authority.get(key) is not False for key in forbidden):
        raise TrendSwingError("TS recovery forbidden authority was broadened")


def _validate_protocol(document: dict[str, Any]) -> None:
    if document.get("protocol_id") != "ts-v3-result-blind-data-contract-recovery-v1":
        raise TrendSwingError("unexpected TS recovery protocol identity")
    if document.get("stage") != "RESULT_BLIND_DATA_CONTRACT_RECOVERY_AND_PROFILE_ONLY":
        raise TrendSwingError("unexpected TS recovery stage")
    _forbidden_authority(document)
    predecessor = document.get("predecessor", {})
    if predecessor.get("verdict") != "MULTIPLE_BLOCKS" or predecessor.get("immutable_and_not_reinterpreted") is not True:
        raise TrendSwingError("TS recovery predecessor boundary differs")
    network = document.get("network_recovery", {})
    if (
        network.get("status") != "PENDING_EXACT_USER_APPROVAL"
        or network.get("logical_request_count") != 1
        or network.get("successful_response_count_maximum") != 1
        or network.get("request") != CHINEXT_REQUEST
        or network.get("same_scope_retry_after_claim") != "forbidden"
    ):
        raise TrendSwingError("TS recovery network scope differs")
    if document.get("scope", {}).get("survival_interval") != "list_date_lte_trade_date_lt_delist_date":
        raise TrendSwingError("TS recovery lifecycle interval differs")
    availability = document.get("availability_evidence", {})
    expected_availability = {
        "independent_nontrading_source": "baostock.history_k_data_plus",
        "trade_status_0_and_bar_absent": "CONFIRMED_NONTRADING_INDEPENDENT",
        "trade_status_1_and_bar_absent": "CONFLICT_FAIL_CLOSED",
        "delist_date_is_effective_removal_date": True,
        "delist_date_is_not_expected_trading_day": True,
        "status_evidence_cannot_create_price_or_volume": True,
    }
    if any(availability.get(key) != value for key, value in expected_availability.items()):
        raise TrendSwingError("TS recovery availability contract differs")
    required = set(document.get("required_sources", []))
    if not {"tushare.stock_basic", "baostock.history_k_data_plus"} <= required:
        raise TrendSwingError("TS recovery required sources omit lifecycle or independent status")
    controls = document.get("attempt_and_change_control", {})
    if (
        controls.get("strategy_effect_attempt_count") != 0
        or controls.get("recovery_profile_attempt_count") != 1
        or controls.get("network_logical_request_count_maximum") != 1
        or controls.get("parameter_grid") != "forbidden"
        or controls.get("same_scope_network_retry") != "forbidden"
    ):
        raise TrendSwingError("TS recovery attempt controls differ")


@dataclass(frozen=True)
class RecoveryProtocol:
    path: Path
    document: dict[str, Any]
    sha256: str

    @classmethod
    def load(cls, path: Path = RECOVERY_PROTOCOL_PATH) -> "RecoveryProtocol":
        resolved = project_path(path)
        document = _load_yaml(resolved)
        _validate_protocol(document)
        return cls(resolved, document, sha256_file(resolved))

    @property
    def required_sources(self) -> tuple[str, ...]:
        return tuple(self.document["required_sources"])

    @property
    def start_date(self) -> str:
        return str(self.document["scope"]["start_date"]).replace("-", "")

    @property
    def end_date(self) -> str:
        return str(self.document["scope"]["end_date"]).replace("-", "")


@dataclass(frozen=True)
class RecoveryAddendum:
    path: Path
    document: dict[str, Any]
    sha256: str

    @classmethod
    def load(
        cls,
        protocol: RecoveryProtocol,
        path: Path = RECOVERY_ADDENDUM_PATH,
    ) -> "RecoveryAddendum":
        resolved = project_path(path)
        document = _load_yaml(resolved)
        if document.get("stage") != "RESULT_BLIND_OPERATIONALIZATION_ONLY":
            raise TrendSwingError("unexpected TS recovery addendum stage")
        predecessor = document.get("predecessor", {})
        if (
            predecessor.get("protocol_id") != protocol.document["protocol_id"]
            or predecessor.get("protocol_sha256") != protocol.sha256
            or predecessor.get("immutable_and_not_rewritten") is not True
        ):
            raise TrendSwingError("TS recovery addendum predecessor differs")
        authority = document.get("authority", {})
        required_false = (
            "change_thresholds",
            "read_post_entry_return",
            "read_mae_mfe",
            "model_training",
            "model_prediction",
            "strategy_backtest",
            "network_execution_authorized",
            "env_or_secret_read_authorized",
            "paper_web_or_production_change",
        )
        if any(authority.get(name) is not False for name in required_false):
            raise TrendSwingError("TS recovery addendum broadened authority")
        time = document.get("time_semantics", {})
        if (
            time.get("observation_time") != "AFTER_MARKET_CLOSE"
            or time.get("previous_day_high")
            != "IMMEDIATELY_PRECEDING_VALID_SECURITY_BAR_HIGH"
            or time.get("next_open_missing_or_suspended")
            != "NOT_EXECUTABLE_NO_FORWARD_SUBSTITUTION"
        ):
            raise TrendSwingError("TS recovery addendum time semantics differ")
        return cls(resolved, document, sha256_file(resolved))


@dataclass(frozen=True)
class RecoveryR2:
    path: Path
    document: dict[str, Any]
    sha256: str

    @classmethod
    def load(
        cls,
        protocol: RecoveryProtocol,
        addendum: RecoveryAddendum,
        path: Path = RECOVERY_R2_PATH,
    ) -> "RecoveryR2":
        resolved = project_path(path)
        document = _load_yaml(resolved)
        if (
            document.get("protocol_id") != "ts-v3-result-blind-data-contract-recovery-r2-v1"
            or document.get("stage")
            != "RESULT_BLIND_INDEX_COMPLETENESS_RECOVERY_AND_PROFILE_ONLY"
        ):
            raise TrendSwingError("unexpected TS recovery R2 identity or stage")
        predecessor = document.get("predecessor", {})
        if (
            predecessor.get("protocol_sha256") != protocol.sha256
            or predecessor.get("operationalization_addendum_sha256") != addendum.sha256
            or predecessor.get("release_created") is not False
            or predecessor.get("network_claim_created") is not False
            or predecessor.get("provider_request_count") != 0
            or predecessor.get("recovery_profile_attempt_count") != 0
        ):
            raise TrendSwingError("TS recovery R2 predecessor execution boundary differs")
        authority = document.get("authorization", {})
        forbidden = (
            "read_post_entry_return", "read_mae_mfe", "model_training", "model_prediction",
            "strategy_backtest", "candidate_effect_evaluation", "paper_account",
            "production_change", "web_implementation", "deepseek_or_other_llm",
            "network_execution_authorized", "env_or_secret_read_authorized",
        )
        if any(authority.get(name) is not False for name in forbidden):
            raise TrendSwingError("TS recovery R2 broadened authority")
        network = document.get("network_recovery", {})
        requests = [item.get("params") for item in network.get("requests", [])]
        if (
            network.get("status") != "PENDING_EXACT_USER_APPROVAL"
            or network.get("logical_request_count") != 2
            or network.get("successful_response_count_maximum") != 2
            or tuple(requests) != EXPECTED_REQUESTS
            or network.get("collect_all_responses_before_any_commit") is not True
            or network.get("same_scope_retry_after_claim") != "forbidden"
        ):
            raise TrendSwingError("TS recovery R2 network scope differs")
        expected_ranges = {
            "000906.SH": ["20160104", "20260811"],
            "399006.SZ": ["20160104", "20260811"],
            "000688.SH": ["20191231", "20260811"],
        }
        if document.get("index_completeness", {}).get("required_ranges") != expected_ranges:
            raise TrendSwingError("TS recovery R2 index completeness ranges differ")
        return cls(resolved, document, sha256_file(resolved))


@dataclass(frozen=True)
class RecoveryR2Addendum:
    path: Path
    document: dict[str, Any]
    sha256: str

    @classmethod
    def load(
        cls,
        recovery_r2: RecoveryR2,
        path: Path = RECOVERY_R2_ADDENDUM_PATH,
    ) -> "RecoveryR2Addendum":
        resolved = project_path(path)
        document = _load_yaml(resolved)
        if document.get("stage") != "RESULT_BLIND_IMPLEMENTATION_CLARIFICATION_ONLY":
            raise TrendSwingError("unexpected TS recovery R2 addendum stage")
        predecessor = document.get("predecessor", {})
        if (
            predecessor.get("protocol_id") != recovery_r2.document["protocol_id"]
            or predecessor.get("protocol_sha256") != recovery_r2.sha256
            or predecessor.get("immutable_and_not_rewritten") is not True
        ):
            raise TrendSwingError("TS recovery R2 addendum predecessor differs")
        authority = document.get("authority", {})
        if any(
            authority.get(name) is not False
            for name in (
                "change_thresholds", "read_post_entry_return", "read_alpha158_prediction_values",
                "rank_candidates", "model_training_or_prediction", "strategy_backtest_or_effect",
                "network_execution_authorized", "env_or_secret_read_authorized",
                "paper_web_or_production_change",
            )
        ):
            raise TrendSwingError("TS recovery R2 addendum broadened authority")
        if document.get("alpha158_key_only", {}).get("allowed_columns") != ["ts_code", "trade_date"]:
            raise TrendSwingError("TS recovery R2 Alpha158 key-only contract differs")
        return cls(resolved, document, sha256_file(resolved))


def release_scope_payload(
    protocol: RecoveryProtocol,
    addendum: RecoveryAddendum,
    recovery_r2: RecoveryR2,
    recovery_r2_addendum: RecoveryR2Addendum,
    recovery_r3: Any,
    *,
    implementation_snapshot_sha256: str,
    implementation_git_head: str,
    ingest_ledger_sha256: str,
) -> dict[str, Any]:
    scope = {
        "action": "TS_V3_THREE_INDEX_DAILY_RECOVERY_ONCE",
        "protocol_sha256": protocol.sha256,
        "operationalization_addendum_sha256": addendum.sha256,
        "recovery_r2_protocol_sha256": recovery_r2.sha256,
        "recovery_r2_addendum_sha256": recovery_r2_addendum.sha256,
        "recovery_r3_protocol_sha256": recovery_r3.sha256,
        "implementation_snapshot_sha256": implementation_snapshot_sha256,
        "implementation_git_head": implementation_git_head,
        "ingest_ledger_before_sha256": ingest_ledger_sha256,
        "logical_request_count": 3,
        "successful_response_count_maximum": 3,
        "bounded_transport_attempts_maximum_per_request": 6,
        "requests": list(EXPECTED_R3_REQUESTS),
        "deepseek_or_other_llm_authorized": False,
        "post_entry_outcome_authorized": False,
        "model_or_backtest_authorized": False,
        "paper_web_or_production_authorized": False,
    }
    return {
        "schema_version": "ts-v3-data-recovery-release-v1",
        "release_scope_sha256": canonical_sha256(scope),
        "execution_authorized": False,
        "scope": scope,
    }


@dataclass(frozen=True)
class RecoveryRelease:
    path: Path
    document: dict[str, Any]
    sha256: str

    @classmethod
    def load(
        cls,
        protocol: RecoveryProtocol,
        addendum: RecoveryAddendum,
        recovery_r2: RecoveryR2,
        recovery_r2_addendum: RecoveryR2Addendum,
        recovery_r3: Any,
        path: Path = RELEASE_SCOPE_PATH,
        *,
        project_root: Path = PROJECT_ROOT,
    ) -> "RecoveryRelease":
        resolved = project_path(path, root=project_root)
        document = _load_yaml(resolved)
        if set(document) != {"schema_version", "release_scope_sha256", "execution_authorized", "scope"}:
            raise TrendSwingError("TS recovery release schema differs")
        scope = document.get("scope", {})
        if document.get("schema_version") != "ts-v3-data-recovery-release-v1":
            raise TrendSwingError("TS recovery release version differs")
        if document.get("execution_authorized") is not False:
            raise TrendSwingError("TS recovery release cannot self-authorize")
        if document.get("release_scope_sha256") != canonical_sha256(scope):
            raise TrendSwingError("TS recovery release scope hash differs")
        if (
            scope.get("protocol_sha256") != protocol.sha256
            or scope.get("operationalization_addendum_sha256") != addendum.sha256
            or scope.get("recovery_r2_protocol_sha256") != recovery_r2.sha256
            or scope.get("recovery_r2_addendum_sha256") != recovery_r2_addendum.sha256
            or scope.get("recovery_r3_protocol_sha256") != recovery_r3.sha256
            or tuple(scope.get("requests", [])) != EXPECTED_R3_REQUESTS
        ):
            raise TrendSwingError("TS recovery release does not bind protocol and request")
        if scope.get("logical_request_count") != 3 or scope.get("successful_response_count_maximum") != 3:
            raise TrendSwingError("TS recovery release request counts differ")
        return cls(resolved, document, sha256_file(resolved))

    @property
    def scope_sha256(self) -> str:
        return str(self.document["release_scope_sha256"])

    def require_user_approval(self) -> None:
        supplied = os.getenv(APPROVAL_SCOPE_ENV, "").strip().lower()
        if supplied != self.scope_sha256:
            raise TrendSwingError("TS recovery exact user approval scope is missing or differs")
