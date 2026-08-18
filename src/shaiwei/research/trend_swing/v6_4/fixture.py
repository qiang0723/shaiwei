"""Pure synthetic fixtures for the TS-v6-4 no-take-profit executor."""

from __future__ import annotations

from typing import Any

import pandas as pd

from shaiwei.research.trend_swing.r3g2.effect_fixture import _partition
from shaiwei.research.trend_swing.r3g2.effect_metrics import summarize
from shaiwei.research.trend_swing.r3g2.effect_models import SCENARIOS, scenario
from shaiwei.research.trend_swing.v6_3.metrics import evaluate_candidate
from shaiwei.research.trend_swing.v6_4.contract import V64Error, V64Scope
from shaiwei.research.trend_swing.v6_4.execution import simulate_no_takeprofit


def _run_synthetic(scope: V64Scope, *, losing: bool) -> dict[str, Any]:
    prepared = _partition(scope, "discovery", losing=losing)
    point = scope.selected_point_hashes[0]
    events = prepared.events.loc[prepared.events["point_hash"].eq(point)].copy()
    summaries: dict[str, dict[str, Any]] = {}
    base_nav = base_trades = None
    for name in SCENARIOS:
        result = simulate_no_takeprofit(
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
    gate_config["trial_count"] = 5
    gate = evaluate_candidate(summaries, base_nav, base_trades, gate_config, (0.0,) * 4)
    reasons = set(base_trades["reason"].astype(str))
    return {"gate": gate, "reasons": reasons, "summaries": summaries}


def fixture() -> dict[str, Any]:
    scope = V64Scope.load()
    winning = _run_synthetic(scope, losing=False)
    losing = _run_synthetic(scope, losing=True)
    if "TAKE_PROFIT" in winning["reasons"] or "TAKE_PROFIT" in losing["reasons"]:
        raise V64Error("TS-v6-4 removed take-profit fired in synthetic fixture")
    if "TIME_EXIT" not in winning["reasons"]:
        raise V64Error("TS-v6-4 structural exits are missing in synthetic fixture")
    if losing["gate"]["passed"]:
        raise V64Error("TS-v6-4 synthetic losing fixture must fail the gate")
    return {
        "fixture_pass": True,
        "take_profit_removed": True,
        "structural_exits_retained": True,
    }
