"""Pure P2-2 metric definitions and frozen historical-effect judge."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from tools.p2_star50_effect.contract import EffectGateFailure


def compounded_return(returns: pd.Series) -> float:
    values = pd.to_numeric(returns, errors="coerce")
    if values.isna().any() or not np.isfinite(values.to_numpy(dtype=float)).all():
        raise EffectGateFailure("daily return series contains null or non-finite values")
    return float((1.0 + values).prod() - 1.0)


def net_excess_return(strategy_returns: pd.Series, benchmark_returns: pd.Series) -> float:
    if len(strategy_returns) != len(benchmark_returns):
        raise EffectGateFailure("strategy/benchmark return lengths differ")
    return compounded_return(strategy_returns) - compounded_return(benchmark_returns)


def maximum_drawdown_from_returns(returns: pd.Series) -> float:
    values = pd.to_numeric(returns, errors="coerce")
    if values.isna().any() or not np.isfinite(values.to_numpy(dtype=float)).all():
        raise EffectGateFailure("drawdown input contains null or non-finite values")
    nav = (1.0 + values).cumprod()
    drawdown = 1.0 - nav / nav.cummax()
    return float(drawdown.max()) if len(drawdown) else 0.0


def diversification_metrics(
    star_returns: pd.Series,
    star_weights: pd.DataFrame,
    comparator: dict[str, pd.DataFrame] | None,
    protocol: dict[str, Any],
) -> dict[str, Any]:
    """Evaluate only a pre-bound CSI800 truth; absence is NOT_EVALUABLE."""
    gate = protocol["diversification_gate"]
    if comparator is None:
        if gate.get("bound_comparator") is not None:
            raise EffectGateFailure("bound comparator declared but no comparator data supplied")
        return {
            "status": "NOT_EVALUABLE",
            "pass": False,
            "reason": "no preregistered CSI800 2023-2025 daily return and holding-weight truth",
            "weighted_name_overlap": None,
            "return_correlation": None,
            "joint_star50_risk_contribution": None,
            "common_return_trade_days": 0,
        }

    returns = comparator["returns"].copy()
    weights = comparator["weights"].copy()
    required_return = {"trade_date", "daily_net_return"}
    required_weight = {"trade_date", "ts_code", "weight"}
    if required_return - set(returns) or required_weight - set(weights):
        raise EffectGateFailure("bound comparator schema is incomplete")
    star = star_returns.rename("star").to_frame()
    star.index = pd.to_datetime(star.index)
    csi = returns.assign(trade_date=pd.to_datetime(returns["trade_date"])).set_index("trade_date")
    aligned = star.join(csi[["daily_net_return"]].rename(columns={"daily_net_return": "csi"}), how="inner")
    minimum = int(gate["return_correlation"]["minimum_common_trade_days"])
    if len(aligned) < minimum or not np.isfinite(aligned.to_numpy(dtype=float)).all():
        return {
            "status": "FAIL",
            "pass": False,
            "reason": "insufficient or non-finite common daily returns",
            "weighted_name_overlap": None,
            "return_correlation": None,
            "joint_star50_risk_contribution": None,
            "common_return_trade_days": int(len(aligned)),
        }
    correlation = float(aligned["star"].corr(aligned["csi"]))

    star_w = star_weights.copy()
    star_w["trade_date"] = pd.to_datetime(star_w["trade_date"])
    weights["trade_date"] = pd.to_datetime(weights["trade_date"])
    overlap_rows = star_w.merge(weights, on=["trade_date", "ts_code"], suffixes=("_star", "_csi"))
    overlap = overlap_rows.assign(
        minimum=np.minimum(overlap_rows["weight_star"], overlap_rows["weight_csi"])
    ).groupby("trade_date")["minimum"].sum()
    common_weight_days = sorted(set(star_w["trade_date"]) & set(weights["trade_date"]))
    if not common_weight_days:
        max_overlap = np.nan
    else:
        max_overlap = float(overlap.reindex(common_weight_days, fill_value=0.0).max())

    covariance = aligned[["csi", "star"]].cov().to_numpy(dtype=float)
    capital = np.array(
        [
            float(gate["joint_risk_contribution"]["csi800_capital_weight"]),
            float(gate["joint_risk_contribution"]["star50_capital_weight"]),
        ]
    )
    denominator = float(capital @ covariance @ capital)
    if not np.isfinite(denominator) or denominator <= 0:
        risk_contribution = np.nan
    else:
        risk_contribution = float(capital[1] * (covariance @ capital)[1] / denominator)

    passed = bool(
        np.isfinite(max_overlap)
        and max_overlap <= float(gate["weighted_name_overlap"]["maximum"])
        and np.isfinite(correlation)
        and correlation <= float(gate["return_correlation"]["maximum"])
        and np.isfinite(risk_contribution)
        and risk_contribution <= float(gate["joint_risk_contribution"]["maximum"])
    )
    return {
        "status": "PASS" if passed else "FAIL",
        "pass": passed,
        "reason": "all preregistered diversification metrics evaluated",
        "weighted_name_overlap": max_overlap if np.isfinite(max_overlap) else None,
        "return_correlation": correlation if np.isfinite(correlation) else None,
        "joint_star50_risk_contribution": (
            risk_contribution if np.isfinite(risk_contribution) else None
        ),
        "common_return_trade_days": int(len(aligned)),
    }


def judge_effect(
    window_metrics: list[dict[str, Any]],
    pressure_metrics: list[dict[str, Any]],
    pooled: dict[str, Any],
    diversification: dict[str, Any],
    determinism_pass: bool,
    protocol: dict[str, Any],
) -> dict[str, Any]:
    evaluation = protocol["evaluation"]
    minimum_days = int(evaluation["minimum_test_trade_days_per_window"])
    minimum_rebalances = int(evaluation["minimum_rebalances_per_window"])
    max_drawdown = float(evaluation["maximum_test_or_pressure_strategy_nav_drawdown"])
    observations_pass = all(int(row["trade_days"]) >= minimum_days for row in window_metrics)
    rebalance_pass = all(int(row["rebalance_count"]) >= minimum_rebalances for row in window_metrics)
    positive_windows = sum(float(row["base_net_excess"]) > 0.0 for row in window_metrics)
    positive_windows_pass = positive_windows >= int(evaluation["minimum_positive_net_excess_windows"])
    pooled_base_pass = float(pooled["base_net_excess"]) > 0.0
    pooled_double_pass = float(pooled["double_cost_net_excess"]) >= 0.0
    pooled_extra_pass = float(pooled["extra_slippage_net_excess"]) >= 0.0
    drawdown_pass = all(
        float(row["base_maximum_drawdown"]) <= max_drawdown
        for row in [*window_metrics, *pressure_metrics]
    )
    window_gate_pass = observations_pass and rebalance_pass and positive_windows_pass
    cost_gate_pass = pooled_base_pass and pooled_double_pass and pooled_extra_pass
    diversification_pass = bool(diversification["pass"])
    evaluable = diversification["status"] != "NOT_EVALUABLE"
    all_pass = bool(
        window_gate_pass
        and cost_gate_pass
        and drawdown_pass
        and diversification_pass
        and determinism_pass
    )
    historical_gate = "GO" if all_pass else ("REJECT" if evaluable else "NO_GO")
    strategy_effective = (
        protocol["verdict_contract"]["historical_go_effective_label"]
        if historical_gate == "GO"
        else protocol["verdict_contract"]["reject_effective_label"]
    )
    return {
        "observations_gate_pass": observations_pass,
        "rebalance_gate_pass": rebalance_pass,
        "positive_base_net_excess_window_count": int(positive_windows),
        "positive_windows_gate_pass": positive_windows_pass,
        "window_gate_pass": window_gate_pass,
        "pooled_base_gate_pass": pooled_base_pass,
        "pooled_double_cost_gate_pass": pooled_double_pass,
        "pooled_extra_slippage_gate_pass": pooled_extra_pass,
        "cost_gate_pass": cost_gate_pass,
        "drawdown_gate_pass": drawdown_pass,
        "diversification_gate_status": diversification["status"],
        "diversification_gate_pass": diversification_pass,
        "determinism_pass": bool(determinism_pass),
        "historical_effect_gate": historical_gate,
        "strategy_results_inspected": True,
        "strategy_effective": strategy_effective,
        "production_authorization": "none",
    }
