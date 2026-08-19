"""TS-B legacy Sharpe lineage and the frozen holdout gate."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

import pandas as pd

from shaiwei.research.g1 import G1Error, deflated_sharpe_probability, periodic_sharpe
from shaiwei.research.trend_swing.r3g2.effect_artifacts import tree_manifest
from shaiwei.research.trend_swing.r3g2.effect_metrics import _point_gate
from shaiwei.research.trend_swing.r3g2.effect_models import SCENARIOS
from shaiwei.research.trend_swing.v6_3.metrics import pre_fee_expectancy
from shaiwei.research.trend_swing.v6_4.metrics import legacy_sharpes as v6_4_legacy_sharpes
from shaiwei.research.trend_swing.ts_b.contract import (
    PARENT_POINT_HASH,
    TSBError,
    V64_FIRST_PASS_BUNDLE_SHA256,
    V64_FIRST_PASS_ROOT,
)


def legacy_sharpes() -> tuple[float, ...]:
    """Recompute the five sealed discovery Sharpes from bound artifacts only."""
    four = v6_4_legacy_sharpes()
    manifest = tree_manifest(V64_FIRST_PASS_ROOT)
    if manifest["bundle_sha256"] != V64_FIRST_PASS_BUNDLE_SHA256:
        raise TSBError("TS-B bound TS-v6-4 first-pass bundle differs")
    nav = pd.read_parquet(
        V64_FIRST_PASS_ROOT / "discovery" / PARENT_POINT_HASH / "base_1x" / "nav.parquet"
    )
    v64 = periodic_sharpe(nav["active_return"].astype(float).tolist(), minimum=252)
    return tuple(four) + (v64,)


def evaluate_holdout(
    summaries: Mapping[str, Mapping[str, Any]],
    nav: pd.DataFrame,
    trades: pd.DataFrame,
    gate: Mapping[str, Any],
    legacy: Sequence[float],
) -> dict[str, Any]:
    if tuple(summaries) != SCENARIOS:
        raise TSBError("TS-B cost scenario set differs")
    result = _point_gate(
        summaries, gate, positive_excess_years=int(
            gate["minimum_positive_h00906_net_excess_calendar_years"]
        ), each_year_minimum=float(gate["each_calendar_year_net_return_minimum"]),
    )
    expectancy = pre_fee_expectancy(trades)
    result["checks"]["pre_fee_expectancy_positive"] = expectancy > 0.0
    probability, details = 0.0, {}
    try:
        returns = nav["active_return"].astype(float).tolist()
        candidate_sharpe = periodic_sharpe(returns, minimum=252)
        trial_sharpes = tuple(legacy) + (candidate_sharpe,)
        probability, details = deflated_sharpe_probability(
            returns,
            trial_sharpes=trial_sharpes,
            trial_count=int(gate.get("trial_count", 6)),
            minimum=252,
        )
    except (G1Error, ValueError, ArithmeticError) as error:
        details = {"failure": type(error).__name__}
    result["checks"]["deflated_sharpe"] = probability >= float(
        gate["minimum_deflated_sharpe_probability"]
    )
    result["passed"] = all(result["checks"].values())
    return {
        "checks": result["checks"],
        "deflated_sharpe_probability": probability,
        "deflated_sharpe_details": details,
        "passed": result["passed"],
    }
