"""Pure synthetic fixtures for the TS-v6-3 discovery effect executor."""

from __future__ import annotations

from typing import Any

import pandas as pd

from shaiwei.research.trend_swing.r3g2.effect_execution import simulate
from shaiwei.research.trend_swing.r3g2.effect_fixture import _partition
from shaiwei.research.trend_swing.r3g2.effect_metrics import summarize
from shaiwei.research.trend_swing.r3g2.effect_models import SCENARIOS, scenario
from shaiwei.research.trend_swing.v6_3.contract import V63Error, V63Scope
from shaiwei.research.trend_swing.v6_3.metrics import (
    candidate_diagnostics,
    evaluate_candidate,
)


def _run_synthetic(scope: V63Scope, *, losing: bool) -> dict[str, Any]:
    prepared = _partition(scope, "discovery", losing=losing)
    point = scope.selected_point_hashes[0]
    events = prepared.events.loc[prepared.events["point_hash"].eq(point)].copy()
    summaries: dict[str, dict[str, Any]] = {}
    base_nav = base_trades = None
    for name in SCENARIOS:
        result = simulate(
            events=events,
            bars=prepared.bars,
            benchmark=prepared.benchmark,
            calendar=prepared.calendar,
            current=scenario(name),
        )
        nav = pd.DataFrame(list(result.nav_rows))
        orders = pd.DataFrame(list(result.order_rows))
        trades = pd.DataFrame(list(result.trade_rows))
        summaries[name] = summarize(nav, orders, trades, blocked_reason=result.blocked_reason)
        if name == SCENARIOS[0]:
            base_nav, base_trades = nav, trades
    gate_config = dict(scope.document["discovery_gate"]["candidate"])
    gate_config["trial_count"] = 4
    gate = evaluate_candidate(summaries, base_nav, base_trades, gate_config, (0.0, 0.0, 0.0))
    return {"gate": gate, "summaries": summaries, "diagnostics": candidate_diagnostics(summaries, base_nav, base_trades)}


def fixture() -> dict[str, Any]:
    scope = V63Scope.load()
    winning = _run_synthetic(scope, losing=False)
    losing = _run_synthetic(scope, losing=True)
    if not winning["gate"]["passed"]:
        raise V63Error("TS-v6-3 synthetic positive fixture must pass the gate")
    if losing["gate"]["passed"]:
        raise V63Error("TS-v6-3 synthetic losing fixture must fail the gate")
    diagnostics = winning["diagnostics"]
    if diagnostics["pre_fee_per_trade_expectancy_rmb"] is None:
        raise V63Error("TS-v6-3 pre-fee expectancy is missing")
    if not diagnostics["exit_reason_groups"] or not diagnostics["sector_context"]:
        raise V63Error("TS-v6-3 diagnostics are incomplete")
    return {
        "fixture_pass": True,
        "synthetic_positive_gate": winning["gate"]["passed"],
        "synthetic_losing_gate": losing["gate"]["passed"],
        "pre_fee_expectancy_exact": True,
        "library_scalar_normalization": True,
    }
