"""Frozen M6-5A protocol loader and value objects."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml

from shaiwei.config import PROJECT_ROOT
from shaiwei.research.production_conversion.contract import ProtocolError


PROTOCOL_PATH = PROJECT_ROOT / "config/m6_csi800_production_head30_500k_feasibility_v1.yaml"


@dataclass(frozen=True)
class Policy:
    initial_cash: Decimal = Decimal("500000")
    commission_rate: Decimal = Decimal("0.0003")
    minimum_commission: Decimal = Decimal("5")
    stamp_tax_rate: Decimal = Decimal("0.0005")
    transfer_fee_rate: Decimal = Decimal("0.00001")
    main_lot: int = 100
    star_minimum: int = 200
    capacity_fraction: Decimal = Decimal("0.05")


@dataclass(frozen=True)
class Gates:
    median_positions_minimum: int = 24
    minimum_positions: int = 20
    median_cash_ratio_maximum: float = 0.20
    maximum_cash_ratio: float = 0.35
    median_l1_maximum: float = 0.30
    maximum_l1: float = 0.50
    minimum_lot_rejection_fraction_maximum: float = 0.20
    positive_windows_minimum: int = 4
    pooled_nav_ratio_minimum: float = 0.95


def load_protocol(path: Path = PROTOCOL_PATH) -> dict[str, Any]:
    document = yaml.safe_load(path.read_text())
    if not isinstance(document, dict):
        raise ProtocolError("M6-5A protocol is not a mapping")
    if document.get("schema_version") != "m6-csi800-production-head30-500k-feasibility-protocol-v1":
        raise ProtocolError("M6-5A protocol schema differs")
    if document.get("protocol_stage") != "RESULT_BLIND_PROTOCOL_FREEZE_ONLY":
        raise ProtocolError("M6-5A protocol stage differs")
    variable = document.get("single_variable_contract", {})
    execution = document.get("execution_contract", {})
    if (
        variable.get("variable_name") != "capital_execution_envelope"
        or variable.get("changed_capital_rmb") != 500000
        or execution.get("reset_cash_each_window_rmb") != 500000
        or execution.get("rebalance_trade_days") != 10
    ):
        raise ProtocolError("M6-5A frozen capital envelope differs")
    policy = execution.get("paper_policy", {})
    expected_policy = {
        "commission_rate": 0.0003, "minimum_commission_rmb": 5.0,
        "sell_stamp_tax_rate": 0.0005, "transfer_fee_rate": 0.00001,
        "main_and_chinext_buy_lot": 100, "star_initial_buy_minimum": 200,
    }
    if any(policy.get(key) != value for key, value in expected_policy.items()):
        raise ProtocolError("M6-5A paper policy differs")
    capacity = document.get("capacity_contract", {})
    if (
        capacity.get("trailing_trade_observations") != 20
        or capacity.get("minimum_valid_observations") != 15
        or capacity.get("maximum_order_notional_fraction") != 0.05
        or capacity.get("current_execution_day_amount_forbidden") is not True
    ):
        raise ProtocolError("M6-5A capacity contract differs")
    gates = document.get("hard_feasibility_gates", {})
    expected_gates = {
        "median_realized_position_count_minimum": 24,
        "minimum_post_rebalance_position_count": 20,
        "median_post_rebalance_cash_ratio_maximum": 0.20,
        "maximum_post_rebalance_cash_ratio": 0.35,
        "median_post_rebalance_target_l1_error_maximum": 0.30,
        "maximum_post_rebalance_target_l1_error": 0.50,
        "below_minimum_lot_rejection_fraction_maximum": 0.20,
    }
    if any(gates.get(key) != value for key, value in expected_gates.items()):
        raise ProtocolError("M6-5A hard feasibility gates differ")
    effect = document.get("historical_effect_retention_gates", {})
    expected_effect = {
        "base_cost_positive_net_excess_window_minimum": 4,
        "combined_1_5x_cost_cumulative_net_excess_minimum": 0.0,
        "executable_to_ideal_pooled_nav_ratio_minimum": 0.95,
    }
    if any(effect.get(key) != value for key, value in expected_effect.items()):
        raise ProtocolError("M6-5A effect-retention gates differ")
    authority = document.get("engineering_authority", {})
    forbidden = (
        "sealed_target_prediction_price_or_return_read_authorized",
        "real_qlib_read_authorized",
        "real_500k_simulation_authorized",
        "formal_output_write_authorized",
        "external_network_authorized",
        "env_or_secret_read_authorized",
        "forward_signal_change_authorized",
        "paper_portfolio_change_authorized",
        "scheduler_change_or_restart_authorized",
    )
    if any(authority.get(key) is not False for key in forbidden):
        raise ProtocolError("M6-5A result-blind authority was broadened")
    if document.get("production_authorization") != "none":
        raise ProtocolError("M6-5A cannot authorize production")
    return document
