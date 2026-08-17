"""Typed domain records for the frozen R3G-2 economic portfolio."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


SCENARIOS = ("base_1x", "all_costs_2x", "base_plus_10bp_slippage_each_side")
PARTITIONS = ("discovery", "holdout")


@dataclass(frozen=True)
class Scenario:
    name: str
    fee_multiplier: float
    slippage: float


def scenario(name: str) -> Scenario:
    values = {
        "base_1x": Scenario("base_1x", 1.0, 0.0),
        "all_costs_2x": Scenario("all_costs_2x", 2.0, 0.0),
        "base_plus_10bp_slippage_each_side": Scenario(
            "base_plus_10bp_slippage_each_side", 1.0, 0.001
        ),
    }
    try:
        return values[name]
    except KeyError as error:
        raise ValueError(f"unknown R3G-2 cost scenario: {name}") from error


@dataclass
class Lot:
    batch: int
    fill_date: str
    raw_shares: int
    entry_raw_price: float
    entry_adjusted_price: float
    entry_notional: float
    entry_fees: float
    remaining_fraction: float = 1.0

    def value(self, adjusted_price: float) -> float:
        return self.entry_notional * adjusted_price / self.entry_adjusted_price * self.remaining_fraction


@dataclass
class Position:
    episode_id: str
    ts_code: str
    industry: str
    original_rank: int
    reference_adjusted: float
    stop_adjusted: float
    target_adjusted: float
    first_fill_date: str
    first_fill_index: int
    first_fill_adjusted: float
    initial_risk_fraction: float
    last_adj_factor: float
    lots: list[Lot] = field(default_factory=list)
    pending_exit: str = ""
    second_attempted: bool = False
    second_scheduled_date: str = ""
    cumulative_entry_cash: float = 0.0
    cumulative_exit_cash: float = 0.0

    def value(self, adjusted_price: float) -> float:
        return sum(lot.value(adjusted_price) for lot in self.lots)

    def is_empty(self) -> bool:
        return not any(lot.remaining_fraction > 1e-12 for lot in self.lots)


@dataclass
class PortfolioState:
    cash: float
    positions: dict[str, Position] = field(default_factory=dict)
    orders: list[dict[str, Any]] = field(default_factory=list)
    trades: list[dict[str, Any]] = field(default_factory=list)
    corporate_action_overlap_count: int = 0


@dataclass(frozen=True)
class SimulationResult:
    nav_rows: tuple[dict[str, Any], ...]
    order_rows: tuple[dict[str, Any], ...]
    trade_rows: tuple[dict[str, Any], ...]
    blocked_reason: str
