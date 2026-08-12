"""Final R3 lineage and three-index request contract for TS recovery."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from shaiwei.config import PROJECT_ROOT
from shaiwei.research.trend_swing.contract import TrendSwingError, project_path, sha256_file
from shaiwei.research.trend_swing.recovery_contract import (
    EXPECTED_R3_REQUESTS,
    RecoveryR2,
    RecoveryR2Addendum,
)


RECOVERY_R3_PATH = PROJECT_ROOT / "config/ts_v3_data_gate_recovery_r3_v1.yaml"


def _load(path: Path) -> dict[str, Any]:
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise TrendSwingError("TS recovery R3 protocol must be a mapping")
    return document


@dataclass(frozen=True)
class RecoveryR3:
    path: Path
    document: dict[str, Any]
    sha256: str

    @classmethod
    def load(
        cls,
        recovery_r2: RecoveryR2,
        recovery_r2_addendum: RecoveryR2Addendum,
        path: Path = RECOVERY_R3_PATH,
    ) -> "RecoveryR3":
        resolved = project_path(path)
        document = _load(resolved)
        if (
            document.get("protocol_id") != "ts-v3-result-blind-data-contract-recovery-r3-v1"
            or document.get("stage") != "RESULT_BLIND_COMPLETE_INDEX_RECOVERY_AND_PROFILE_ONLY"
        ):
            raise TrendSwingError("unexpected TS recovery R3 identity or stage")
        predecessor = document.get("predecessor", {})
        if (
            predecessor.get("protocol_sha256") != recovery_r2.sha256
            or predecessor.get("operationalization_addendum_sha256")
            != recovery_r2_addendum.sha256
            or predecessor.get("release_created") is not False
            or predecessor.get("network_claim_created") is not False
            or predecessor.get("provider_request_count") != 0
            or predecessor.get("recovery_profile_attempt_count") != 0
        ):
            raise TrendSwingError("TS recovery R3 predecessor execution boundary differs")
        authority = document.get("authorization", {})
        forbidden = (
            "read_post_entry_return", "read_alpha158_prediction_values",
            "model_training_or_prediction", "strategy_backtest_or_effect",
            "paper_web_or_production_change", "deepseek_or_other_llm",
            "network_execution_authorized", "env_or_secret_read_authorized",
        )
        if any(authority.get(name) is not False for name in forbidden):
            raise TrendSwingError("TS recovery R3 broadened authority")
        network = document.get("network_recovery", {})
        requests = tuple(item.get("params") for item in network.get("requests", []))
        if (
            network.get("status") != "PENDING_EXACT_USER_APPROVAL"
            or network.get("logical_request_count") != 3
            or network.get("successful_response_count_maximum") != 3
            or requests != EXPECTED_R3_REQUESTS
            or network.get("collect_all_responses_before_any_commit") is not True
            or network.get("same_scope_retry_after_claim") != "forbidden"
        ):
            raise TrendSwingError("TS recovery R3 network scope differs")
        expected_ranges = {
            "000906.SH": ["20160104", "20260811"],
            "399006.SZ": ["20160104", "20260811"],
            "000688.SH": ["20191231", "20260811"],
        }
        if document.get("index_completeness", {}).get("required_ranges") != expected_ranges:
            raise TrendSwingError("TS recovery R3 index completeness ranges differ")
        return cls(resolved, document, sha256_file(resolved))
