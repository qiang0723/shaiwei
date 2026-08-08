"""Result-before M3-2 live authorization bound to exact discovery inputs."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from shaiwei.config import PROJECT_ROOT
from shaiwei.ledger import sha256_file
from shaiwei.research.llm_factor import D1ControlError
from shaiwei.research.m3_multi_pool_contract import M3DiscoveryIdentityContract, M3Protocol


RELEASE_SCHEMA = "m3-multi-pool-factor-execution-release-v1"
RELEASE_ID = "m3-star-three-pool-price-volume-v1-batch-001"


@dataclass(frozen=True)
class M3ExecutionRelease:
    path: Path
    document: dict[str, Any]
    sha256: str
    release_id: str
    protocol_sha256: str
    total_authorization_usd: float
    batch_hard_ceiling_usd: float
    response_model_identity: str

    @classmethod
    def load(cls, path: Path, protocol: M3Protocol) -> "M3ExecutionRelease":
        try:
            document = yaml.safe_load(path.read_text(encoding="utf-8"))
        except OSError as error:
            raise D1ControlError("M3-2 execution release is missing") from error
        if not isinstance(document, dict):
            raise D1ControlError("M3-2 execution release must be a YAML object")
        try:
            authorization = document["authorization"]
            frozen = document["frozen_contract"]
            inputs = document["input_contract"]
            adjustment = document["adjustment_contract"]
            selection = document["selection_contract"]
            scope = document["scope"]
            ledgers = document["ledgers"]
            egress = document["egress"]
            official = document["official_contract_recheck"]
            recovery = document["recovery_contract"]
        except (KeyError, TypeError) as error:
            raise D1ControlError("M3-2 execution release is incomplete") from error
        if (
            document.get("schema_version") != RELEASE_SCHEMA
            or document.get("release_id") != RELEASE_ID
            or document.get("status") != "M3_2_RESULT_BEFORE_EXECUTION_FROZEN"
            or document.get("execution_authorized") is not True
            or document.get("production_authorization") != "none"
        ):
            raise D1ControlError("M3-2 execution authority differs")
        cls._validate_authorization(authorization)
        cls._validate_frozen_contract(frozen, protocol)
        cls._validate_inputs(inputs, adjustment)
        cls._validate_selection(selection)
        cls._validate_scope(scope, ledgers, egress)
        cls._validate_official(official, protocol)
        cls._validate_recovery(recovery)
        return cls(
            path=path,
            document=document,
            sha256=sha256_file(path),
            release_id=RELEASE_ID,
            protocol_sha256=protocol.sha256,
            total_authorization_usd=float(authorization["d1_total_authorization_usd"]),
            batch_hard_ceiling_usd=float(authorization["batch_hard_ceiling_usd"]),
            response_model_identity=str(official["response_model_field"]),
        )

    @staticmethod
    def _validate_authorization(value: dict[str, Any]) -> None:
        if (
            value.get("source") != "user_continue_instruction_in_primary_codex_thread"
            or value.get("authorized_on") != "2026-08-02"
            or value.get("model") != "deepseek-v4-pro"
            or int(value.get("completed_responses_exact", 0)) != 24
            or float(value.get("d1_total_authorization_usd", -1)) != 10.0
            or float(value.get("batch_hard_ceiling_usd", -1)) != 0.5
            or value.get("future_batches_require_new_protocol_and_instruction") is not True
        ):
            raise D1ControlError("M3-2 user authority or budget differs")

    @staticmethod
    def _validate_frozen_contract(value: dict[str, Any], protocol: M3Protocol) -> None:
        manifest_path = PROJECT_ROOT / str(value.get("preexecution_manifest_path", ""))
        implementation = str(value.get("preexecution_implementation_commit", ""))
        manifest = (
            json.loads(manifest_path.read_text(encoding="utf-8"))
            if manifest_path.is_file()
            else {}
        )
        if (
            value.get("protocol_path") != "config/m3_multi_pool_factor_research_v1.yaml"
            or value.get("protocol_sha256") != protocol.sha256
            or value.get("prompt_sha256") != protocol.prompt_bundle.sha256
            or value.get("knowledge_manifest_sha256") != protocol.knowledge_manifest.sha256
            or value.get("preexecution_manifest_path")
            != "config/m3_multi_pool_factor_manifest_v1.json"
            or not manifest_path.is_file()
            or value.get("preexecution_manifest_sha256") != sha256_file(manifest_path)
            or value.get("preexecution_verdict") != "GO_M3_1_PREEXECUTION_ONLY"
            or re.fullmatch(r"[0-9a-f]{40}", implementation) is None
            or manifest.get("verdict") != "GO_M3_1_PREEXECUTION_ONLY"
            or manifest.get("identity", {}).get("implementation_commit") != implementation
            or manifest.get("scope", {}).get("deepseek_api_calls") != 0
            or manifest.get("scope", {}).get("real_factor_results_inspected") is not False
        ):
            raise D1ControlError("M3-2 frozen M3-1 binding differs")

    @staticmethod
    def _validate_inputs(inputs: dict[str, Any], adjustment: dict[str, Any]) -> None:
        sources = inputs.get("source_snapshot_sha256")
        rows = inputs.get("source_loaded_rows")
        expected_sources = {
            "tushare.adj_factor",
            "tushare.daily",
            "tushare.daily_basic",
            "tushare.dividend",
            "tushare.index_member_all",
            "tushare.trade_cal",
        }
        if (
            not isinstance(inputs.get("discovery_input_snapshot_sha256"), str)
            or len(inputs["discovery_input_snapshot_sha256"]) != 64
            or not isinstance(sources, dict)
            or set(sources) != expected_sources
            or any(not isinstance(value, str) or len(value) != 64 for value in sources.values())
            or not isinstance(rows, dict)
            or set(rows) != expected_sources
            or any(int(value) < 0 for value in rows.values())
            or inputs.get("membership_sha256")
            != "1983169ef42489e544ce9c71e55e64ba853d27491a723024102b5699ae475101"
            or inputs.get("calendar_start") != "20201023"
            or inputs.get("calendar_end") != "20221230"
        ):
            raise D1ControlError("M3-2 discovery input identity differs")
        transform_path = PROJECT_ROOT / "src/shaiwei/transform/market.py"
        if (
            adjustment.get("price_basis")
            != "sanitized_backward_adjusted_from_first_window_observation"
            or adjustment.get("sanitizer") != "shaiwei.transform.market.sanitize_adj_factors"
            or adjustment.get("transform") != "shaiwei.transform.market.transform_market_data"
            or adjustment.get("market_transform_sha256") != sha256_file(transform_path)
            or adjustment.get("raw_unadjusted_factor_or_label_forbidden") is not True
        ):
            raise D1ControlError("M3-2 adjustment contract differs")

    @staticmethod
    def _validate_selection(value: dict[str, Any]) -> None:
        if (
            value.get("run_only_after_all_24_completed_responses") is not True
            or value.get("eligible_requires_all_three_pool_positive_directed_rank_ic") is not True
            or value.get("direction_anchor_universe") != "star-board-all-pit-v1"
            or value.get("per_pool_direction_flip_forbidden") is not True
            or int(value.get("promoted_count", 0)) != 2
            or value.get("fewer_than_two_eligible")
            != "PAUSE_INSUFFICIENT_CROSS_POOL_CANDIDATES"
        ):
            raise D1ControlError("M3-2 selection contract differs")

    @staticmethod
    def _validate_scope(
        scope: dict[str, Any], ledgers: dict[str, Any], egress: dict[str, Any]
    ) -> None:
        expected_false = {
            "sealed_validation_access",
            "stress_period_access",
            "g1_run",
            "model_or_portfolio_run",
            "forward_access",
            "scheduler_changes",
            "web_changes",
            "guanxiang_access",
            "new_market_collection",
        }
        if (
            scope.get("discovery_signal_period_only") != ["2021-01-04", "2022-12-15"]
            or any(scope.get(key) is not False for key in expected_false)
            or ledgers
            != {
                "attempt": "ledger/m3_multi_pool_factor_attempts.csv",
                "transport": "ledger/m3_multi_pool_factor_transports.csv",
                "experiment": "ledger/experiments.csv",
                "prior_family_ledgers_remain_byte_immutable": True,
            }
            or egress
            != {
                "scheme": "https",
                "host": "api.deepseek.com",
                "port": 443,
                "path": "/chat/completions",
                "trust_environment_proxy": False,
            }
        ):
            raise D1ControlError("M3-2 scope, ledger, or egress boundary differs")

    @staticmethod
    def _validate_official(value: dict[str, Any], protocol: M3Protocol) -> None:
        provider = protocol.document["provider"]
        prices = protocol.document["cost_budget"]
        expected = {
            "rechecked_on": "2026-08-02",
            "model": provider["model"],
            "model_version": provider["model_version_expected"],
            "response_model_field": provider["model"],
            "thinking": provider["thinking"],
            "reasoning_effort": provider["reasoning_effort"],
            "input_cache_hit_per_million_usd": float(
                prices["pro_input_cache_hit_per_million"]
            ),
            "input_cache_miss_per_million_usd": float(
                prices["pro_input_cache_miss_per_million"]
            ),
            "output_per_million_usd": float(prices["pro_output_per_million"]),
        }
        if any(value.get(key) != expected_value for key, expected_value in expected.items()):
            raise D1ControlError("M3-2 provider contract differs")

    @staticmethod
    def _validate_recovery(value: dict[str, Any]) -> None:
        if value != {
            "same_release_resume_allowed": True,
            "immutable_context_required_before_first_request": True,
            "completed_prefix_static_rehash_required": True,
            "billing_uncertainty_fail_closed": True,
            "same_code_snapshot_and_release_git_head_required": True,
            "changed_code_or_release_requires_result_before_addendum": True,
            "terminal_report_may_assemble_from_existing_24_responses_without_provider_call": True,
            "response_replacement_or_retry_after_completion_forbidden": True,
        }:
            raise D1ControlError("M3-2 recovery contract differs")

    def verify_input(self, identity: M3DiscoveryIdentityContract) -> None:
        inputs = self.document["input_contract"]
        if (
            inputs["discovery_input_snapshot_sha256"] != identity.snapshot_sha256
            or inputs["source_snapshot_sha256"] != identity.source_snapshots
            or {key: int(value) for key, value in inputs["source_loaded_rows"].items()}
            != identity.source_rows
            or int(inputs["panel_security_count"]) != identity.panel_security_count
            or int(inputs["discovery_trade_days"]) != identity.discovery_trade_days
            or int(inputs["exposure_rows"]) != identity.exposure_rows
            or inputs["calendar_start"] != identity.calendar_start
            or inputs["calendar_end"] != identity.calendar_end
        ):
            raise D1ControlError("M3-2 physical discovery input differs from the release")
