"""Frozen R3G-2 portfolio summaries and discovery/holdout gates."""

from __future__ import annotations

from typing import Any, Mapping

import numpy as np
import pandas as pd

from shaiwei.research.g1 import G1Error, deflated_sharpe_probability, periodic_sharpe
from shaiwei.research.trend_swing.r3g2.contract import R3G2Error
from shaiwei.research.trend_swing.r3g2.effect_models import SCENARIOS


def _compound(values: list[float]) -> float:
    array = np.asarray(values, dtype=float)
    if array.size == 0 or not np.isfinite(array).all() or (array <= -1).any():
        raise R3G2Error("R3G-2 return series cannot be compounded")
    return float(np.prod(1.0 + array) - 1.0)


def _maximum_drawdown(nav: pd.Series) -> tuple[float, int]:
    values = pd.to_numeric(nav, errors="raise").to_numpy(dtype=float)
    if values.size == 0 or not np.isfinite(values).all() or (values <= 0).any():
        raise R3G2Error("R3G-2 NAV is invalid")
    peak = np.maximum.accumulate(np.concatenate(([500_000.0], values)))
    path = np.concatenate(([500_000.0], values))
    drawdown = 1.0 - path / peak
    maximum = float(drawdown.max())
    longest = current = 0
    for value in drawdown:
        current = current + 1 if value > 0 else 0
        longest = max(longest, current)
    return maximum, longest


def summarize(
    nav: pd.DataFrame,
    orders: pd.DataFrame,
    trades: pd.DataFrame,
    *,
    blocked_reason: str,
) -> dict[str, Any]:
    required = {"trade_date", "nav", "daily_return", "benchmark_return", "active_return"}
    if nav.empty or required - set(nav.columns):
        raise R3G2Error("R3G-2 NAV artifact is incomplete")
    nav = nav.sort_values("trade_date").reset_index(drop=True)
    net = _compound(nav["daily_return"].astype(float).tolist())
    benchmark = _compound(nav["benchmark_return"].astype(float).tolist())
    drawdown, duration = _maximum_drawdown(nav["nav"])
    annual: dict[str, dict[str, float]] = {}
    for year, rows in nav.groupby(nav["trade_date"].astype(str).str[:4], sort=True):
        strategy = _compound(rows["daily_return"].astype(float).tolist())
        comparator = _compound(rows["benchmark_return"].astype(float).tolist())
        annual[str(year)] = {
            "net_return": strategy,
            "benchmark_return": comparator,
            "net_excess": strategy - comparator,
        }
    closed = trades.loc[trades.get("closed_trade", False).astype(bool)] if not trades.empty else trades
    pnls = closed.get("closed_trade_pnl", pd.Series(dtype=float)).astype(float)
    wins, losses = pnls[pnls > 0], pnls[pnls < 0]
    ratio = float(wins.mean() / abs(losses.mean())) if not wins.empty and not losses.empty else None
    total_fees = float(trades.get("fees", pd.Series(dtype=float)).astype(float).sum())
    turnover = float(trades.get("gross_notional", pd.Series(dtype=float)).astype(float).sum()) / 500_000.0
    years = sorted(annual)
    observed_counts = closed.get("trade_date", pd.Series(dtype=str)).astype(str).str[:4].value_counts()
    date_index = {str(day): index for index, day in enumerate(nav["trade_date"].astype(str))}
    first_entries = (
        trades.loc[trades.get("side", pd.Series(dtype=str)).eq("BUY")]
        .groupby("episode_id", sort=False)["trade_date"]
        .min()
        if not trades.empty
        else pd.Series(dtype=str)
    )
    holding_days = [
        date_index[str(row.trade_date)] - date_index[str(first_entries[row.episode_id])]
        for row in closed.itertuples(index=False)
    ]
    absolute_pnl = float(pnls.abs().sum())

    def concentration(column: str) -> float | None:
        if closed.empty or absolute_pnl <= 0:
            return None
        grouped = closed.groupby(column, sort=False)["closed_trade_pnl"].sum().abs()
        return float(grouped.max() / absolute_pnl)

    return {
        "calendar_day_count": len(nav),
        "closed_trade_count": len(closed),
        "closed_trade_count_by_year": {year: int(observed_counts.get(year, 0)) for year in years},
        "pooled_net_return": net,
        "pooled_benchmark_return": benchmark,
        "pooled_h00906_net_excess": net - benchmark,
        "annual": annual,
        "maximum_drawdown": drawdown,
        "maximum_drawdown_duration_days": duration,
        "win_rate": float((pnls > 0).mean()) if len(pnls) else None,
        "profit_loss_ratio": ratio,
        "expectancy_rmb": float(pnls.mean()) if len(pnls) else None,
        "turnover": turnover,
        "fees_rmb": total_fees,
        "unfilled_or_pending_order_count": int(
            orders.get("status", pd.Series(dtype=str)).isin(["REJECTED", "PENDING", "PARTIAL"]).sum()
        ),
        "mean_cash_ratio": float(nav["cash_ratio"].astype(float).mean()),
        "maximum_gross_weight": float(nav["gross_weight"].astype(float).max()),
        "maximum_position_count": int(nav["position_count"].astype(int).max()),
        "maximum_security_weight": float(nav["maximum_security_weight"].astype(float).max()),
        "maximum_industry_weight": float(nav["maximum_industry_weight"].astype(float).max()),
        "corporate_action_overlap_count": int(
            nav["corporate_action_overlap_count"].astype(int).max()
        ),
        "capacity_limited_order_count": int(
            orders.get("capacity_limited", pd.Series(dtype=bool)).astype(bool).sum()
        ),
        "mean_holding_days": float(np.mean(holding_days)) if holding_days else None,
        "maximum_holding_days": int(max(holding_days)) if holding_days else None,
        "maximum_absolute_trade_pnl_share": (
            float(pnls.abs().max() / absolute_pnl) if absolute_pnl > 0 else None
        ),
        "maximum_absolute_security_pnl_share": concentration("ts_code"),
        "maximum_absolute_industry_pnl_share": concentration("industry"),
        "blocked_reason": blocked_reason,
    }


def _basic_gate(summary: Mapping[str, Any], gate: Mapping[str, Any]) -> dict[str, bool]:
    yearly = summary["closed_trade_count_by_year"]
    checks = {
        "closed_trades": int(summary["closed_trade_count"]) >= int(gate["minimum_closed_trades"]),
        "closed_trades_each_year": bool(yearly)
        and min(int(value) for value in yearly.values())
        >= int(gate["minimum_closed_trades_each_calendar_year"]),
        "positive_net": float(summary["pooled_net_return"]) > 0,
        "positive_excess": float(summary["pooled_h00906_net_excess"]) > 0,
        "maximum_drawdown": float(summary["maximum_drawdown"]) <= float(gate["maximum_drawdown"]),
        "unblocked": not summary["blocked_reason"],
    }
    return checks


def _point_gate(
    summaries: Mapping[str, Mapping[str, Any]],
    gate: Mapping[str, Any],
    *,
    positive_excess_years: int | None = None,
    each_year_minimum: float | None = None,
) -> dict[str, Any]:
    if tuple(summaries) != SCENARIOS:
        raise R3G2Error("R3G-2 cost scenario set differs")
    base = summaries[SCENARIOS[0]]
    checks = _basic_gate(base, gate)
    checks["all_costs_2x"] = float(summaries[SCENARIOS[1]]["pooled_net_return"]) >= float(
        gate["all_costs_2x_pooled_net_return_minimum"]
    )
    checks["extra_10bp"] = float(summaries[SCENARIOS[2]]["pooled_net_return"]) >= float(
        gate["extra_10bp_each_side_pooled_net_return_minimum"]
    )
    if positive_excess_years is not None:
        checks["positive_excess_years"] = sum(
            float(row["net_excess"]) > 0 for row in base["annual"].values()
        ) >= positive_excess_years
    if each_year_minimum is not None:
        checks["each_year_net_minimum"] = bool(base["annual"]) and min(
            float(row["net_return"]) for row in base["annual"].values()
        ) >= each_year_minimum
    return {"checks": checks, "passed": all(checks.values())}


def _dsr(
    nav_by_point: Mapping[str, pd.DataFrame], primary: str, trial_count: int
) -> tuple[float, dict[str, Any]]:
    returns = nav_by_point[primary]["active_return"].astype(float).tolist()
    try:
        trial_sharpes = tuple(
            periodic_sharpe(frame["active_return"].astype(float).tolist(), minimum=252)
            for frame in nav_by_point.values()
        )
        return deflated_sharpe_probability(
            returns, trial_sharpes=trial_sharpes, trial_count=trial_count, minimum=252
        )
    except (G1Error, ValueError, ArithmeticError) as error:
        return 0.0, {"failure": type(error).__name__}


def evaluate_partition(
    summaries: Mapping[str, Mapping[str, Mapping[str, Any]]],
    nav_by_point: Mapping[str, pd.DataFrame],
    protocol: Mapping[str, Any],
    *,
    partition: str,
) -> dict[str, Any]:
    primary = protocol["selected_effect_points"]["primary_anchor"]["point_hash"]
    neighbours = [row["point_hash"] for row in protocol["selected_effect_points"]["sensitivity_neighbours"]]
    if set(summaries) != {primary, *neighbours} or set(nav_by_point) != set(summaries):
        raise R3G2Error("R3G-2 point set differs during gate evaluation")
    if partition == "discovery":
        gate = protocol["discovery_gate"]
        point_results = {
            primary: _point_gate(
                summaries[primary], gate["primary_anchor"],
                positive_excess_years=int(
                    gate["primary_anchor"]["minimum_positive_h00906_net_excess_calendar_years"]
                ),
            )
        }
        point_results.update(
            {
                point: _point_gate(summaries[point], gate["each_sensitivity_neighbour"])
                for point in neighbours
            }
        )
        probability, details = _dsr(nav_by_point, primary, 3)
        point_results[primary]["checks"]["deflated_sharpe"] = probability >= float(
            gate["primary_anchor"]["minimum_deflated_sharpe_probability"]
        )
        point_results[primary]["passed"] = all(point_results[primary]["checks"].values())
        passed = all(row["passed"] for row in point_results.values())
        return {
            "partition": partition, "points": point_results,
            "deflated_sharpe_probability": probability, "deflated_sharpe_details": details,
            "passed": passed,
            "verdict": "DISCOVERY_PASS" if passed else gate["failure_verdict"],
        }
    gate = protocol["conditional_holdout_gate"]
    point_results = {
        primary: _point_gate(
            summaries[primary], gate["primary_anchor"],
            positive_excess_years=int(
                gate["primary_anchor"]["minimum_positive_h00906_net_excess_calendar_years"]
            ),
            each_year_minimum=float(gate["primary_anchor"]["each_calendar_year_net_return_minimum"]),
        )
    }
    point_results.update(
        {
            point: _point_gate(summaries[point], gate["neighbour_robustness"])
            for point in neighbours
        }
    )
    neighbour_count = sum(point_results[point]["passed"] for point in neighbours)
    passed = point_results[primary]["passed"] and neighbour_count >= int(
        gate["neighbour_robustness"]["minimum_passing_neighbour_count"]
    )
    return {
        "partition": partition, "points": point_results,
        "passing_neighbour_count": neighbour_count, "passed": passed,
        "verdict": gate["pass_verdict"] if passed else gate["failure_verdict"],
    }
