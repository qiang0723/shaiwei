"""Frozen M6-3 protocol identity, authority, and path boundaries."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
from typing import Any

import yaml

from shaiwei.config import PROJECT_ROOT
from shaiwei.research.topk_conversion.schema import ALTERNATIVES, ARMS, TOPK_KEYS, WINDOWS


RESULT_PROTOCOL = PROJECT_ROOT / "config/m6_csi800_topk20_conversion_v1.yaml"
ENGINEERING_PROTOCOL = (
    PROJECT_ROOT / "config/m6_csi800_topk20_conversion_engineering_v1.yaml"
)


class ConversionError(RuntimeError):
    """Fail-closed M6-3 contract, data, or evidence violation."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _mapping(path: Path) -> dict[str, Any]:
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ConversionError(f"M6-3 protocol is not a mapping: {path.name}")
    return document


def bounded_path(path: Path, *, root: Path = PROJECT_ROOT) -> Path:
    resolved_root = root.resolve()
    resolved = path.resolve()
    if not resolved.is_relative_to(resolved_root):
        raise ConversionError("M6-3 path escapes its allowed root")
    return resolved


def _validate_authority(engineering: dict[str, Any]) -> None:
    if engineering.get("stage") != "RESULT_BLIND_SYNTHETIC_ENGINEERING_ONLY":
        raise ConversionError("M6-3B engineering stage differs")
    authority = engineering.get("authority", {})
    required_true = {
        "engineering_implementation_authorized",
        "synthetic_fixture_authorized",
        "immutable_engineering_image_build_authorized",
        "dependency_build_network_only",
    }
    actual_true = {key for key, value in authority.items() if value is True}
    if actual_true != required_true:
        raise ConversionError("M6-3B authority differs")
    if authority.get("production_authorization") != "none":
        raise ConversionError("M6-3B cannot authorize production")
    if authority.get("tushare_calls") != 0 or authority.get("deepseek_calls") != 0:
        raise ConversionError("M6-3B external call count differs")


def _validate_result(result: dict[str, Any]) -> None:
    if result.get("protocol_id") != "m6-csi800-topk20-portfolio-conversion-v1":
        raise ConversionError("unexpected M6-3A protocol identity")
    if result.get("protocol_stage") != "RESULT_BEFORE_TOPK20_PORTFOLIO_PROTOCOL_FREEZE_ONLY":
        raise ConversionError("M6-3A stage differs")
    scope = result.get("scope", {})
    expected_scope = {
        "existing_score_arm_count": 3,
        "new_model_arm_count": 0,
        "new_model_fit_count": 0,
        "new_prediction_generation_count": 0,
        "changed_portfolio_variable_count": 1,
        "formal_portfolio_hypothesis_count": 2,
        "additional_topk_value_authorized": False,
    }
    if any(scope.get(key) != value for key, value in expected_scope.items()):
        raise ConversionError("M6-3A scope differs")
    if tuple(result.get("score_surfaces", {}).get("arms", ())) != ARMS:
        raise ConversionError("M6-3 score arm order differs")
    variable = result.get("single_variable_contract", {})
    if (
        variable.get("variable_path") != "portfolio.topk"
        or str(variable.get("control_value")) != TOPK_KEYS[0]
        or str(variable.get("treatment_value")) != TOPK_KEYS[1]
        or variable.get("all_other_portfolio_fields_byte_semantically_equal") is not True
    ):
        raise ConversionError("M6-3 TopK single-variable contract differs")
    inference = result.get("primary_inference", {})
    if tuple(inference.get("hypothesis_family", ())) != ALTERNATIVES:
        raise ConversionError("M6-3 hypothesis family differs")
    if inference.get("hypothesis_count") != 2 or inference.get("hac_lags") != 10:
        raise ConversionError("M6-3 inference contract differs")
    if tuple(result.get("windows_and_clock", {}).get("windows", ())) != WINDOWS:
        raise ConversionError("M6-3 window set differs")
    constants = result.get("portfolio_constants", {})
    expected_constants = {
        "strategy": "BiweeklyTopkDropoutStrategy",
        "account_rmb": 100000000,
        "n_drop": 3,
        "rebalance_trade_days": 10,
        "only_tradable": True,
        "forbid_all_trade_at_limit": False,
        "deal_price": "open",
        "benchmark": "SH000906",
        "open_cost": 0.0006,
        "close_cost": 0.0016,
        "minimum_cost_rmb": 5,
        "cost_multipliers": [1.0, 1.5, 2.0],
        "cost_scenario_method": "scale_recorded_base_daily_cost_without_rerunning_trades",
        "capacity_model_added": False,
        "allocation_and_cash_semantics": "inherit_unmodified_biweekly_topk_dropout_defaults",
    }
    if constants != expected_constants:
        raise ConversionError("M6-3 frozen portfolio constants differ")


def _validate_engineering(engineering: dict[str, Any]) -> None:
    if engineering.get("protocol_id") != "m6-csi800-topk20-conversion-engineering-v1":
        raise ConversionError("unexpected M6-3B protocol identity")
    _validate_authority(engineering)
    docker = engineering.get("docker", {})
    if (
        docker.get("network_mode") != "none"
        or docker.get("full_project_root_mounted") is not False
        or docker.get("qlib_or_m6_effect_mounted") is not False
        or docker.get("env_file_mounted") is not False
    ):
        raise ConversionError("M6-3B Docker isolation differs")


@dataclass(frozen=True)
class ProtocolBundle:
    result: dict[str, Any]
    engineering: dict[str, Any]
    result_sha256: str
    engineering_sha256: str

    @classmethod
    def load(
        cls,
        *,
        result_path: Path = RESULT_PROTOCOL,
        engineering_path: Path = ENGINEERING_PROTOCOL,
    ) -> "ProtocolBundle":
        result = _mapping(result_path)
        engineering = _mapping(engineering_path)
        _validate_result(result)
        _validate_engineering(engineering)
        result_sha = sha256_file(result_path)
        expected = engineering.get("predecessor", {}).get("config_sha256")
        if result_sha != expected:
            raise ConversionError("M6-3B predecessor protocol hash differs")
        if engineering.get("predecessor", {}).get("preserve_without_rewrite") is not True:
            raise ConversionError("M6-3B predecessor is not preserved")
        return cls(
            result=result,
            engineering=engineering,
            result_sha256=result_sha,
            engineering_sha256=sha256_file(engineering_path),
        )
