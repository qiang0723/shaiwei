"""Pure synthetic fixtures for the TS-B holdout one-shot executor."""

from __future__ import annotations

from typing import Any

import pandas as pd

from shaiwei.research.trend_swing.r3g2.effect_execution import simulate
from shaiwei.research.trend_swing.r3g2.effect_fixture import _partition
from shaiwei.research.trend_swing.r3g2.effect_metrics import summarize
from shaiwei.research.trend_swing.r3g2.effect_models import SCENARIOS, scenario
from shaiwei.research.trend_swing.ts_b.contract import TSBError, TSBScope
from shaiwei.research.trend_swing.ts_b.metrics import evaluate_holdout


def _run_synthetic(scope: TSBScope, *, losing: bool) -> dict[str, Any]:
    prepared = _partition(scope, "holdout", losing=losing)
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
    gate_config = dict(scope.document["holdout_gate"]["candidate"])
    gate_config["trial_count"] = 6
    gate = evaluate_holdout(summaries, base_nav, base_trades, gate_config, (0.0,) * 5)
    return {"gate": gate}


def fixture() -> dict[str, Any]:
    scope = TSBScope.load()
    winning = _run_synthetic(scope, losing=False)
    losing = _run_synthetic(scope, losing=True)
    if not winning["gate"]["passed"]:
        raise TSBError("TS-B synthetic positive fixture must pass the holdout gate")
    if losing["gate"]["passed"]:
        raise TSBError("TS-B synthetic losing fixture must fail the holdout gate")
    return {
        "fixture_pass": True,
        "synthetic_positive_gate": winning["gate"]["passed"],
        "synthetic_losing_gate": losing["gate"]["passed"],
    }
