"""TS-v6-3 candidate metrics and the frozen discovery gate."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

import pandas as pd

from shaiwei.research.g1 import G1Error, deflated_sharpe_probability, periodic_sharpe
from shaiwei.research.trend_swing.r3g2.effect_artifacts import tree_manifest
from shaiwei.research.trend_swing.r3g2.effect_metrics import _point_gate
from shaiwei.research.trend_swing.r3g2.effect_models import SCENARIOS
from shaiwei.research.trend_swing.v6_3.contract import (
    LEGACY_POINT_HASHES,
    PARENT_BASELINE_EXPECTANCY_RMB,
    PARENT_EXIT_GROUP_PNL_RMB,
    PARENT_EXIT_GROUP_SOURCE,
    PARENT_FIRST_PASS_BUNDLE_SHA256,
    PARENT_FIRST_PASS_ROOT,
    V63Error,
)


def pre_fee_expectancy(trades: pd.DataFrame) -> float:
    """Exact pre-fee per-trade expectancy: (closed pnl + all fees) / closed trades."""
    if trades.empty:
        raise V63Error("TS-v6-3 trade artifact is empty")
    closed = trades.loc[trades["closed_trade"].astype(bool)]
    if closed.empty:
        raise V63Error("TS-v6-3 has no closed trades")
    total = float(closed["closed_trade_pnl"].astype(float).sum()) + float(
        trades["fees"].astype(float).sum()
    )
    return total / int(len(closed))


def exit_reason_groups(trades: pd.DataFrame) -> dict[str, dict[str, Any]]:
    closed = trades.loc[trades["closed_trade"].astype(bool)]
    groups: dict[str, dict[str, Any]] = {}
    for reason, rows in closed.groupby("reason", sort=True):
        groups[str(reason)] = {
            "count": int(len(rows)),
            "pnl_rmb": float(rows["closed_trade_pnl"].astype(float).sum()),
        }
    return groups


def exposure_matched_benchmark(nav: pd.DataFrame) -> dict[str, float]:
    """H00906 scaled by mean gross weight; the cash leg earns zero."""
    exposure = float(nav["gross_weight"].astype(float).mean())
    values = nav["benchmark_return"].astype(float).tolist()
    compounded = 1.0
    for value in values:
        compounded *= 1.0 + value
    pooled = compounded - 1.0
    return {
        "mean_gross_weight": exposure,
        "h00906_pooled_return": pooled,
        "exposure_matched_h00906_plus_cash_return": exposure * pooled,
    }


def sector_context(trades: pd.DataFrame) -> list[dict[str, Any]]:
    closed = trades.loc[trades["closed_trade"].astype(bool)]
    if closed.empty:
        return []
    absolute = float(closed["closed_trade_pnl"].astype(float).abs().sum())
    rows = []
    for industry, group in closed.groupby("industry", sort=True):
        pnl = float(group["closed_trade_pnl"].astype(float).sum())
        rows.append({
            "industry": str(industry),
            "closed_trades": int(len(group)),
            "pnl_rmb": pnl,
            "absolute_pnl_share": (abs(pnl) / absolute) if absolute > 0 else None,
        })
    return rows


def legacy_r3g2_sharpes(
    root: Path | None = None, expected_bundle: str = PARENT_FIRST_PASS_BUNDLE_SHA256
) -> tuple[float, float, float]:
    """Recompute the three frozen R3G-2 discovery Sharpes from the bound bundle only."""
    base = PARENT_FIRST_PASS_ROOT if root is None else root
    manifest = tree_manifest(base)
    if manifest["bundle_sha256"] != expected_bundle:
        raise V63Error("TS-v6-3 bound R3G-2 first-pass bundle differs")
    sharpes = []
    for point in LEGACY_POINT_HASHES:
        nav = pd.read_parquet(base / "discovery" / point / "base_1x" / "nav.parquet")
        sharpes.append(
            periodic_sharpe(nav["active_return"].astype(float).tolist(), minimum=252)
        )
    return tuple(sharpes)  # type: ignore[return-value]


def candidate_diagnostics(
    summaries: Mapping[str, Mapping[str, Any]],
    nav: pd.DataFrame,
    trades: pd.DataFrame,
) -> dict[str, Any]:
    base = summaries[SCENARIOS[0]]
    expectancy = float(base["expectancy_rmb"]) if base["expectancy_rmb"] is not None else None
    return {
        "pre_fee_per_trade_expectancy_rmb": pre_fee_expectancy(trades),
        "parent_baseline_pre_fee_expectancy_rmb": PARENT_BASELINE_EXPECTANCY_RMB,
        "after_fee_per_trade_expectancy_rmb": expectancy,
        "exit_reason_groups": exit_reason_groups(trades),
        "parent_exit_reason_groups_reference": {
            "groups": PARENT_EXIT_GROUP_PNL_RMB,
            "source": PARENT_EXIT_GROUP_SOURCE,
        },
        "exposure_matched_benchmark": exposure_matched_benchmark(nav),
        "sector_context": sector_context(trades),
    }


def evaluate_candidate(
    summaries: Mapping[str, Mapping[str, Any]],
    nav: pd.DataFrame,
    trades: pd.DataFrame,
    gate: Mapping[str, Any],
    legacy_sharpes: Sequence[float],
) -> dict[str, Any]:
    if tuple(summaries) != SCENARIOS:
        raise V63Error("TS-v6-3 cost scenario set differs")
    result = _point_gate(
        summaries, gate, positive_excess_years=int(
            gate["minimum_positive_h00906_net_excess_calendar_years"]
        )
    )
    expectancy = pre_fee_expectancy(trades)
    result["checks"]["pre_fee_expectancy_positive"] = expectancy > 0.0
    probability, details = 0.0, {}
    try:
        returns = nav["active_return"].astype(float).tolist()
        candidate_sharpe = periodic_sharpe(returns, minimum=252)
        trial_sharpes = tuple(legacy_sharpes) + (candidate_sharpe,)
        probability, details = deflated_sharpe_probability(
            returns,
            trial_sharpes=trial_sharpes,
            trial_count=int(gate.get("trial_count", 4)),
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
